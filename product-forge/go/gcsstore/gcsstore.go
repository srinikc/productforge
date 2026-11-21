// Package gcsstore is the Google Cloud Storage datastore.ObjectStore adapter (EDP-14-pattern, BI-PF-1395).
//
// It speaks the GCS JSON/Media REST API directly (via the shared, stdlib-only productforge/objstorerest core;
// NO provider SDK). Object content is content-addressed by sha256, persisted in object metadata (pf-checksum)
// so Head/List can report it. Capabilities are declared truthfully: this adapter implements only the base
// operations, so it advertises none of the optional features (callers degrade explicitly).
package gcsstore

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"net/textproto"
	"net/url"
	"strconv"
	"strings"
	"time"

	"productforge/datastore"
	"productforge/objstorerest"
)

const (
	checksumMeta       = "pf-checksum"
	ResumableThreshold = int64(5 * 1024 * 1024) // 5 MB threshold for resumable uploads (AC-1)
	ChunkSize          = 5 * 1024 * 1024         // 5 MB chunk size (20 * 256 KiB chunks)
)

// TokenAuth implements objstorerest.Auth for static OAuth2 / Bearer tokens (e.g. PF_GCS_TOKEN).
type TokenAuth struct {
	Token string
}

// Authorize adds the Bearer token to the Authorization header if non-empty.
func (a TokenAuth) Authorize(_ context.Context, req *http.Request) error {
	tok := strings.TrimSpace(a.Token)
	if tok != "" {
		req.Header.Set("Authorization", "Bearer "+tok)
	}
	return nil
}

// AuthFromCredentials parses raw credentials data (token string or JSON) into an objstorerest.Auth.
func AuthFromCredentials(data []byte) objstorerest.Auth {
	trimmed := strings.TrimSpace(string(data))
	if trimmed == "" {
		return nil
	}
	var m map[string]any
	if err := json.Unmarshal(data, &m); err == nil {
		if tok, ok := m["access_token"].(string); ok && strings.TrimSpace(tok) != "" {
			return TokenAuth{Token: strings.TrimSpace(tok)}
		}
		if tok, ok := m["token"].(string); ok && strings.TrimSpace(tok) != "" {
			return TokenAuth{Token: strings.TrimSpace(tok)}
		}
	}
	return TokenAuth{Token: trimmed}
}

// Config configures the GCS adapter.
type Config struct {
	Bucket     string
	BaseURL    string // default https://storage.googleapis.com (override for emulators/tests)
	Auth       objstorerest.Auth
	HTTPClient *http.Client
	MaxRetries int
}

// Store is the GCS ObjectStore adapter.
type Store struct {
	client *objstorerest.Client
	bucket string
}

// New builds the adapter (fail-closed on a missing bucket).
func New(cfg Config) (*Store, error) {
	if strings.TrimSpace(cfg.Bucket) == "" {
		return nil, errors.New("gcsstore: bucket is required")
	}
	base := cfg.BaseURL
	if base == "" {
		base = "https://storage.googleapis.com"
	}
	c, err := objstorerest.New(objstorerest.Config{
		BaseURL: base, Auth: cfg.Auth, HTTPClient: cfg.HTTPClient, MaxRetries: cfg.MaxRetries,
		UserAgent: "productforge-gcsstore/1",
	})
	if err != nil {
		return nil, err
	}
	return &Store{client: c, bucket: cfg.Bucket}, nil
}

// Capabilities declares the features this adapter actually implements (honest: none of the optional ones).
func (s *Store) Capabilities() datastore.Capabilities {
	return datastore.Capabilities{}
}

func (s *Store) objectURL(key string) string {
	return fmt.Sprintf("%s/storage/v1/b/%s/o/%s", s.client.BaseURL(), url.PathEscape(s.bucket), url.PathEscape(key))
}

// Put uploads an object and returns its content-addressed info.
// For objects > ResumableThreshold (or when size is not known upfront, size < 0), it uses
// the GCS resumable upload protocol to stream chunks without buffering the whole payload into memory.
// Objects <= ResumableThreshold use the fast multipart/related upload path.
func (s *Store) Put(ctx context.Context, key string, r io.Reader, size int64, opts datastore.PutOptions) (datastore.ObjectInfo, error) {
	if size > ResumableThreshold || size < 0 {
		return s.putResumable(ctx, key, r, size, opts)
	}
	return s.putMultipart(ctx, key, r, size, opts)
}

func (s *Store) putMultipart(ctx context.Context, key string, r io.Reader, size int64, opts datastore.PutOptions) (datastore.ObjectInfo, error) {
	body, err := io.ReadAll(r)
	if err != nil {
		return datastore.ObjectInfo{}, err
	}
	if size > 0 && int64(len(body)) != size {
		return datastore.ObjectInfo{}, fmt.Errorf("gcsstore: size mismatch: declared %d, read %d", size, len(body))
	}
	ct := opts.ContentType
	if ct == "" {
		ct = "application/octet-stream"
	}
	sum := objstorerest.SHA256Hex(body)
	if opts.Checksum != "" && opts.Checksum != sum {
		return datastore.ObjectInfo{}, fmt.Errorf("gcsstore: checksum mismatch: declared %s, computed %s", opts.Checksum, sum)
	}
	payload, contentType, err := multipartUpload(key, ct, sum, body)
	if err != nil {
		return datastore.ObjectInfo{}, err
	}
	upURL := fmt.Sprintf("%s/upload/storage/v1/b/%s/o?uploadType=multipart", s.client.BaseURL(), url.PathEscape(s.bucket))
	resp, err := s.client.Do(ctx, http.MethodPost, upURL, bytes.NewReader(payload),
		func() (io.Reader, error) { return bytes.NewReader(payload), nil },
		map[string]string{"Content-Type": contentType})
	if err != nil {
		return datastore.ObjectInfo{}, err
	}
	defer resp.Body.Close()
	if err := s.client.EnsureOK(resp); err != nil {
		return datastore.ObjectInfo{}, err
	}
	var o gcsObject
	if err := json.NewDecoder(resp.Body).Decode(&o); err != nil {
		return datastore.ObjectInfo{}, err
	}
	return o.toInfo(key, sum), nil
}

func (s *Store) putResumable(ctx context.Context, key string, r io.Reader, size int64, opts datastore.PutOptions) (datastore.ObjectInfo, error) {
	ct := opts.ContentType
	if ct == "" {
		ct = "application/octet-stream"
	}

	// 1. Initiate resumable upload session
	initURL := fmt.Sprintf("%s/upload/storage/v1/b/%s/o?uploadType=resumable", s.client.BaseURL(), url.PathEscape(s.bucket))
	initMeta := map[string]any{
		"name":        key,
		"contentType": ct,
	}
	if opts.Checksum != "" {
		initMeta["metadata"] = map[string]string{checksumMeta: opts.Checksum}
	}
	initBody, err := json.Marshal(initMeta)
	if err != nil {
		return datastore.ObjectInfo{}, err
	}

	headers := map[string]string{
		"Content-Type":          "application/json; charset=UTF-8",
		"X-Upload-Content-Type": ct,
	}
	if size >= 0 {
		headers["X-Upload-Content-Length"] = strconv.FormatInt(size, 10)
	}

	initResp, err := s.client.Do(ctx, http.MethodPost, initURL, bytes.NewReader(initBody), func() (io.Reader, error) {
		return bytes.NewReader(initBody), nil
	}, headers)
	if err != nil {
		return datastore.ObjectInfo{}, fmt.Errorf("gcsstore: initiate resumable upload: %w", err)
	}
	defer initResp.Body.Close()
	if err := s.client.EnsureOK(initResp); err != nil {
		return datastore.ObjectInfo{}, fmt.Errorf("gcsstore: initiate resumable upload: %w", err)
	}

	sessionURL := initResp.Header.Get("Location")
	if sessionURL == "" {
		return datastore.ObjectInfo{}, errors.New("gcsstore: resumable upload initiation missing Location header")
	}
	if !strings.HasPrefix(sessionURL, "http://") && !strings.HasPrefix(sessionURL, "https://") {
		sessionURL = s.client.BaseURL() + sessionURL
	}

	// 2. Stream chunks bounded to ChunkSize
	hasher := sha256.New()
	buf := make([]byte, ChunkSize)
	var totalStreamed int64
	var lastObj gcsObject

	for {
		n, readErr := io.ReadFull(r, buf)
		if n == 0 {
			if readErr == io.EOF || readErr == io.ErrUnexpectedEOF {
				break
			}
			if readErr != nil {
				return datastore.ObjectInfo{}, fmt.Errorf("gcsstore: read chunk: %w", readErr)
			}
		}

		chunkData := buf[:n]
		hasher.Write(chunkData)
		startByte := totalStreamed
		endByte := totalStreamed + int64(n) - 1
		totalStreamed += int64(n)

		isFinal := false
		if size >= 0 {
			if totalStreamed == size {
				isFinal = true
			} else if totalStreamed > size {
				return datastore.ObjectInfo{}, fmt.Errorf("gcsstore: size mismatch: declared %d, read more than declared", size)
			}
		} else if readErr == io.EOF || readErr == io.ErrUnexpectedEOF {
			isFinal = true
		}

		var contentRange string
		if isFinal {
			contentRange = fmt.Sprintf("bytes %d-%d/%d", startByte, endByte, totalStreamed)
		} else if size >= 0 {
			contentRange = fmt.Sprintf("bytes %d-%d/%d", startByte, endByte, size)
		} else {
			contentRange = fmt.Sprintf("bytes %d-%d/*", startByte, endByte)
		}

		chunkReader := bytes.NewReader(chunkData)
		putHeaders := map[string]string{
			"Content-Type":   ct,
			"Content-Range":  contentRange,
			"Content-Length": strconv.Itoa(n),
		}

		resp, err := s.client.Do(ctx, http.MethodPut, sessionURL, chunkReader, func() (io.Reader, error) {
			return bytes.NewReader(chunkData), nil
		}, putHeaders)
		if err != nil {
			return datastore.ObjectInfo{}, fmt.Errorf("gcsstore: put chunk [%d-%d]: %w", startByte, endByte, err)
		}

		if resp.StatusCode == 308 {
			_, _ = io.Copy(io.Discard, resp.Body)
			_ = resp.Body.Close()
			if isFinal {
				return datastore.ObjectInfo{}, fmt.Errorf("gcsstore: unexpected 308 on final chunk (%s)", contentRange)
			}
		} else if resp.StatusCode >= 200 && resp.StatusCode < 300 {
			defer resp.Body.Close()
			if err := json.NewDecoder(resp.Body).Decode(&lastObj); err != nil {
				return datastore.ObjectInfo{}, fmt.Errorf("gcsstore: decode resumable response: %w", err)
			}
			break
		} else {
			defer resp.Body.Close()
			return datastore.ObjectInfo{}, s.client.EnsureOK(resp)
		}

		if readErr == io.EOF || readErr == io.ErrUnexpectedEOF {
			break
		}
	}

	// 3. Size validation
	if size >= 0 && totalStreamed != size {
		return datastore.ObjectInfo{}, fmt.Errorf("gcsstore: size mismatch: declared %d, read %d", size, totalStreamed)
	}

	computedChecksum := hex.EncodeToString(hasher.Sum(nil))
	if opts.Checksum != "" && opts.Checksum != computedChecksum {
		return datastore.ObjectInfo{}, fmt.Errorf("gcsstore: checksum mismatch: declared %s, computed %s", opts.Checksum, computedChecksum)
	}

	// 4. If pf-checksum was not set in initial metadata, patch it now
	if opts.Checksum == "" {
		patched, err := s.patchMetadata(ctx, key, computedChecksum)
		if err != nil {
			return datastore.ObjectInfo{}, fmt.Errorf("gcsstore: patch checksum metadata: %w", err)
		}
		lastObj = patched
	}

	return lastObj.toInfo(key, computedChecksum), nil
}

func (s *Store) patchMetadata(ctx context.Context, key, checksum string) (gcsObject, error) {
	u := s.objectURL(key)
	body, err := json.Marshal(map[string]any{
		"metadata": map[string]string{checksumMeta: checksum},
	})
	if err != nil {
		return gcsObject{}, err
	}
	resp, err := s.client.Do(ctx, http.MethodPatch, u, bytes.NewReader(body), func() (io.Reader, error) {
		return bytes.NewReader(body), nil
	}, map[string]string{"Content-Type": "application/json; charset=UTF-8"})
	if err != nil {
		return gcsObject{}, err
	}
	defer resp.Body.Close()
	if err := s.client.EnsureOK(resp); err != nil {
		return gcsObject{}, err
	}
	var o gcsObject
	if err := json.NewDecoder(resp.Body).Decode(&o); err != nil {
		return gcsObject{}, err
	}
	return o, nil
}

// Get downloads an object; the returned info carries the recomputed sha256 (content-addressed).
func (s *Store) Get(ctx context.Context, key, version string) (io.ReadCloser, datastore.ObjectInfo, error) {
	u := s.objectURL(key) + "?alt=media"
	if version != "" {
		u += "&generation=" + url.QueryEscape(version)
	}
	resp, err := s.client.Do(ctx, http.MethodGet, u, nil, nil, nil)
	if err != nil {
		return nil, datastore.ObjectInfo{}, err
	}
	defer resp.Body.Close()
	if err := s.client.EnsureOK(resp); err != nil {
		return nil, datastore.ObjectInfo{}, err
	}
	b, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, datastore.ObjectInfo{}, err
	}
	info := datastore.ObjectInfo{
		Key: key, Checksum: objstorerest.SHA256Hex(b), Size: int64(len(b)),
		ContentType: resp.Header.Get("Content-Type"),
	}
	return io.NopCloser(bytes.NewReader(b)), info, nil
}

// Head returns object metadata (incl. the persisted pf-checksum).
func (s *Store) Head(ctx context.Context, key string) (datastore.ObjectInfo, error) {
	resp, err := s.client.Do(ctx, http.MethodGet, s.objectURL(key), nil, nil, nil)
	if err != nil {
		return datastore.ObjectInfo{}, err
	}
	defer resp.Body.Close()
	if err := s.client.EnsureOK(resp); err != nil {
		return datastore.ObjectInfo{}, err
	}
	var o gcsObject
	if err := json.NewDecoder(resp.Body).Decode(&o); err != nil {
		return datastore.ObjectInfo{}, err
	}
	return o.toInfo(key, o.Metadata[checksumMeta]), nil
}

// Delete removes an object (permanent; not a trash/soft delete).
func (s *Store) Delete(ctx context.Context, key, version string) error {
	u := s.objectURL(key)
	if version != "" {
		u += "?generation=" + url.QueryEscape(version)
	}
	resp, err := s.client.Do(ctx, http.MethodDelete, u, nil, nil, nil)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	return s.client.EnsureOK(resp)
}

// List returns ALL objects under prefix, following pagination (nextPageToken) to completion.
func (s *Store) List(ctx context.Context, prefix string) ([]datastore.ObjectInfo, error) {
	base := fmt.Sprintf("%s/storage/v1/b/%s/o", s.client.BaseURL(), url.PathEscape(s.bucket))
	out := []datastore.ObjectInfo{}
	pageToken := ""
	for {
		q := url.Values{}
		if prefix != "" {
			q.Set("prefix", prefix)
		}
		if pageToken != "" {
			q.Set("pageToken", pageToken)
		}
		u := base
		if len(q) > 0 {
			u += "?" + q.Encode()
		}
		resp, err := s.client.Do(ctx, http.MethodGet, u, nil, nil, nil)
		if err != nil {
			return nil, err
		}
		if resp.StatusCode < 200 || resp.StatusCode >= 300 {
			return nil, s.client.EnsureOK(resp) // EnsureOK closes the body
		}
		var lr struct {
			Items         []gcsObject `json:"items"`
			NextPageToken string      `json:"nextPageToken"`
		}
		derr := json.NewDecoder(resp.Body).Decode(&lr)
		_ = resp.Body.Close()
		if derr != nil {
			return nil, derr
		}
		for _, o := range lr.Items {
			out = append(out, o.toInfo(o.Name, o.Metadata[checksumMeta]))
		}
		if lr.NextPageToken == "" {
			return out, nil
		}
		pageToken = lr.NextPageToken
	}
}

// SignedURL is not implemented by this adapter (declared via Capabilities).
func (s *Store) SignedURL(ctx context.Context, key, method string, ttl time.Duration) (string, error) {
	return "", errors.New("gcsstore: SignedURL not implemented (use a V4 signer over the auth seam)")
}

// ---- wire helpers ----

type gcsObject struct {
	Name        string            `json:"name"`
	Size        string            `json:"size"` // GCS returns size as a string
	ContentType string            `json:"contentType"`
	Generation  string            `json:"generation"`
	Metadata    map[string]string `json:"metadata"`
}

func (o gcsObject) toInfo(key, checksum string) datastore.ObjectInfo {
	n, _ := strconv.ParseInt(o.Size, 10, 64)
	return datastore.ObjectInfo{Key: key, Version: o.Generation, Checksum: checksum, ContentType: o.ContentType, Size: n}
}

func multipartUpload(name, contentType, checksum string, body []byte) ([]byte, string, error) {
	var buf bytes.Buffer
	w := multipart.NewWriter(&buf)
	meta, _ := json.Marshal(map[string]any{
		"name": name, "contentType": contentType, "metadata": map[string]string{checksumMeta: checksum},
	})
	h1 := make(textproto.MIMEHeader)
	h1.Set("Content-Type", "application/json; charset=UTF-8")
	p1, err := w.CreatePart(h1)
	if err != nil {
		return nil, "", err
	}
	if _, err := p1.Write(meta); err != nil {
		return nil, "", err
	}
	h2 := make(textproto.MIMEHeader)
	h2.Set("Content-Type", contentType)
	p2, err := w.CreatePart(h2)
	if err != nil {
		return nil, "", err
	}
	if _, err := p2.Write(body); err != nil {
		return nil, "", err
	}
	if err := w.Close(); err != nil {
		return nil, "", err
	}
	// GCS multipart uploads use multipart/related (same body the writer produced).
	return buf.Bytes(), "multipart/related; boundary=" + w.Boundary(), nil
}
