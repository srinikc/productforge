// Package gdrivestore is the Google Drive ObjectStore adapter (EDP-14-pattern, BI-PF-1434).
//
// It speaks the Google Drive v3 REST API directly over the shared, stdlib-only productforge/objstorerest core
// (ZERO provider SDK dependencies). Object keys are mapped deterministically to Drive files scoped within a
// designated root folder. Collision safety is guaranteed via Write-Then-Delete: new objects are uploaded and verified
// first before superseded versions are retired to trash. Capabilities are declared honestly (all false) and
// unsupported options fail-closed.
package gdrivestore

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"

	"productforge/datastore"
	"productforge/objstorerest"
)

const (
	// DefaultBaseURL is the Google Drive v3 REST API base URL.
	DefaultBaseURL = "https://www.googleapis.com"

	// checksumProp is the custom property key used to store SHA-256 checksums on Drive files.
	checksumProp = "pf_checksum"

	// keyProp is the custom property key used to record the object key on Drive files.
	keyProp = "pf_key"

	// maxListBytes bounds JSON list response decoding to 10MB to prevent memory exhaustion DOS.
	maxListBytes = 10 * 1024 * 1024

	// multipartBoundary is the MIME multipart boundary delimiter used for metadata + media uploads.
	multipartBoundary = "ProductForgeGDriveMultipartBoundary9876543210"
)

// BearerAuth supplies an OAuth2 / Google Service Account bearer token.
type BearerAuth struct {
	Token string
}

// Authorize sets the Authorization: Bearer <token> header on outgoing requests.
func (a BearerAuth) Authorize(_ context.Context, req *http.Request) error {
	tok := strings.TrimSpace(a.Token)
	if tok != "" {
		req.Header.Set("Authorization", "Bearer "+tok)
	}
	return nil
}

// AuthFromToken constructs an objstorerest.Auth from a bearer token string.
// Returns nil if token is empty (useful for mock/emulated testing).
func AuthFromToken(token string) objstorerest.Auth {
	tok := strings.TrimSpace(token)
	if tok == "" {
		return nil
	}
	return BearerAuth{Token: tok}
}

// Config configures the Google Drive ObjectStore adapter.
type Config struct {
	RootFolderID  string // required; designated Google Drive folder ID for object storage
	BaseURL       string // optional; default https://www.googleapis.com
	UploadBaseURL string // optional; default https://www.googleapis.com
	Auth          objstorerest.Auth
	HTTPClient    *http.Client
	MaxRetries    int
	UserAgent     string // optional; defaults to "productforge-gdrivestore/1"
}

// Store is the Google Drive ObjectStore adapter.
type Store struct {
	client        *objstorerest.Client
	rootFolderID  string
	baseURL       string
	uploadBaseURL string
}

// New constructs a Google Drive ObjectStore adapter (fail-closed on missing RootFolderID).
func New(cfg Config) (*Store, error) {
	rootFolderID := strings.TrimSpace(cfg.RootFolderID)
	if rootFolderID == "" {
		return nil, errors.New("gdrivestore: RootFolderID is required")
	}

	base := strings.TrimRight(strings.TrimSpace(cfg.BaseURL), "/")
	if base == "" {
		base = DefaultBaseURL
	}

	uploadBase := strings.TrimRight(strings.TrimSpace(cfg.UploadBaseURL), "/")
	if uploadBase == "" {
		uploadBase = base
	}

	ua := strings.TrimSpace(cfg.UserAgent)
	if ua == "" {
		ua = "productforge-gdrivestore/1"
	}

	cl, err := objstorerest.New(objstorerest.Config{
		BaseURL:    base,
		Auth:       cfg.Auth,
		HTTPClient: cfg.HTTPClient,
		MaxRetries: cfg.MaxRetries,
		UserAgent:  ua,
	})
	if err != nil {
		return nil, err
	}

	return &Store{
		client:        cl,
		rootFolderID:  rootFolderID,
		baseURL:       base,
		uploadBaseURL: uploadBase,
	}, nil
}

// Capabilities declares truthfully that optional capabilities are not supported.
func (s *Store) Capabilities() datastore.Capabilities {
	return datastore.Capabilities{}
}

// escapeSearchString escapes single quotes and backslashes per Google Drive search query syntax.
func escapeSearchString(v string) string {
	v = strings.ReplaceAll(v, "\\", "\\\\")
	return strings.ReplaceAll(v, "'", "\\'")
}

// boundKey ensures custom property values remain strictly within Google Drive's 124-byte limit
// while guaranteeing uniqueness for keys exceeding 100 bytes via a deterministic SHA256 suffix.
func boundKey(key string) string {
	if len(key) <= 100 {
		return key
	}
	sum := objstorerest.SHA256Hex([]byte(key))
	return key[:83] + "_" + sum[:16]
}

// driveFile represents the Google Drive v3 file resource wire model.
type driveFile struct {
	ID            string            `json:"id"`
	Name          string            `json:"name"`
	Size          string            `json:"size,omitempty"`
	MimeType      string            `json:"mimeType,omitempty"`
	Properties    map[string]string `json:"properties,omitempty"`
	AppProperties map[string]string `json:"appProperties,omitempty"`
	MD5Checksum   string            `json:"md5Checksum,omitempty"`
	Version       string            `json:"version,omitempty"`
	CreatedTime   string            `json:"createdTime,omitempty"`
	ModifiedTime  string            `json:"modifiedTime,omitempty"`
	Trashed       bool              `json:"trashed,omitempty"`
}

// driveFileList represents the response from drive/v3/files.
type driveFileList struct {
	NextPageToken string      `json:"nextPageToken"`
	Files         []driveFile `json:"files"`
}

// findActiveFile finds the latest active (non-trashed) file matching key within rootFolderID.
func (s *Store) findActiveFile(ctx context.Context, key string) (*driveFile, error) {
	q := fmt.Sprintf("'%s' in parents and name = '%s' and trashed = false",
		escapeSearchString(s.rootFolderID), escapeSearchString(key))

	u := fmt.Sprintf("%s/drive/v3/files?q=%s&fields=files(id,name,size,mimeType,properties,appProperties,md5Checksum,version,createdTime,modifiedTime,trashed)&pageSize=10",
		s.baseURL, url.QueryEscape(q))

	resp, err := s.client.Do(ctx, http.MethodGet, u, nil, nil, nil)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if err := s.client.EnsureOK(resp); err != nil {
		return nil, err
	}

	var fl driveFileList
	if err := json.NewDecoder(io.LimitReader(resp.Body, maxListBytes)).Decode(&fl); err != nil {
		return nil, fmt.Errorf("gdrivestore: decode files list: %w", err)
	}

	if len(fl.Files) == 0 {
		return nil, objstorerest.ErrNotFound
	}

	// If multiple active files exist, select the newest by modifiedTime / createdTime, with ID as tie-breaker
	selected := &fl.Files[0]
	for i := 1; i < len(fl.Files); i++ {
		if fl.Files[i].ModifiedTime > selected.ModifiedTime ||
			(fl.Files[i].ModifiedTime == selected.ModifiedTime && fl.Files[i].ID > selected.ID) {
			selected = &fl.Files[i]
		}
	}
	return selected, nil
}

// Put uploads an object using RFC 2387 multipart/related upload.
// Collision safety: Writes the new file first, validates upload, then moves older versions with the same key to trash.
// Unsupported optional capabilities (immutability, retention, CMK) fail-closed.
func (s *Store) Put(ctx context.Context, key string, r io.Reader, size int64, opts datastore.PutOptions) (datastore.ObjectInfo, error) {
	if strings.TrimSpace(key) == "" {
		return datastore.ObjectInfo{}, errors.New("gdrivestore: empty key")
	}
	if opts.Immutable {
		return datastore.ObjectInfo{}, &datastore.UnsupportedError{Provider: "gdrive", Capability: "immutability"}
	}
	if opts.Retention > 0 || opts.RetentionMode != "" {
		return datastore.ObjectInfo{}, &datastore.UnsupportedError{Provider: "gdrive", Capability: "retention"}
	}
	if opts.ServerSideEncryption != "" {
		return datastore.ObjectInfo{}, &datastore.UnsupportedError{Provider: "gdrive", Capability: "server-side-encryption"}
	}

	var payload []byte
	if size >= 0 {
		buf := make([]byte, size)
		n, err := io.ReadFull(r, buf)
		if err != nil && err != io.EOF && err != io.ErrUnexpectedEOF {
			return datastore.ObjectInfo{}, fmt.Errorf("gdrivestore: read payload: %w", err)
		}
		if int64(n) != size {
			return datastore.ObjectInfo{}, fmt.Errorf("gdrivestore: size mismatch: declared %d, read %d", size, n)
		}
		// Check for unexpected extra bytes
		var extra [1]byte
		if extraN, _ := r.Read(extra[:]); extraN > 0 {
			return datastore.ObjectInfo{}, fmt.Errorf("gdrivestore: size mismatch: declared %d, read more than declared", size)
		}
		payload = buf
	} else {
		var err error
		payload, err = io.ReadAll(r)
		if err != nil {
			return datastore.ObjectInfo{}, fmt.Errorf("gdrivestore: read payload: %w", err)
		}
	}

	ct := opts.ContentType
	if ct == "" {
		ct = "application/octet-stream"
	}
	sum := objstorerest.SHA256Hex(payload)
	if opts.Checksum != "" && opts.Checksum != sum {
		return datastore.ObjectInfo{}, fmt.Errorf("gdrivestore: checksum mismatch: declared %s, computed %s", opts.Checksum, sum)
	}

	boundary := fmt.Sprintf("ProductForgeGDriveBoundary%d", time.Now().UnixNano())

	// Build RFC 2387 multipart/related body
	metadata := driveFile{
		Name:     key,
		MimeType: ct,
		Properties: map[string]string{
			keyProp:      boundKey(key),
			checksumProp: sum,
		},
		AppProperties: map[string]string{
			keyProp:      boundKey(key),
			checksumProp: sum,
		},
	}
	metaJSON, err := json.Marshal(struct {
		Name          string            `json:"name"`
		Parents       []string          `json:"parents"`
		MimeType      string            `json:"mimeType"`
		Properties    map[string]string `json:"properties"`
		AppProperties map[string]string `json:"appProperties"`
	}{
		Name:          metadata.Name,
		Parents:       []string{s.rootFolderID},
		MimeType:      metadata.MimeType,
		Properties:    metadata.Properties,
		AppProperties: metadata.AppProperties,
	})
	if err != nil {
		return datastore.ObjectInfo{}, fmt.Errorf("gdrivestore: marshal metadata: %w", err)
	}

	var bodyBuf bytes.Buffer
	bodyBuf.WriteString("--" + boundary + "\r\n")
	bodyBuf.WriteString("Content-Type: application/json; charset=UTF-8\r\n\r\n")
	bodyBuf.Write(metaJSON)
	bodyBuf.WriteString("\r\n--" + boundary + "\r\n")
	bodyBuf.WriteString("Content-Type: " + ct + "\r\n\r\n")
	bodyBuf.Write(payload)
	bodyBuf.WriteString("\r\n--" + boundary + "--\r\n")

	uploadBytes := bodyBuf.Bytes()
	uploadURL := fmt.Sprintf("%s/upload/drive/v3/files?uploadType=multipart", s.uploadBaseURL)
	headers := map[string]string{
		"Content-Type":   "multipart/related; boundary=" + boundary,
		"Content-Length": strconv.Itoa(len(uploadBytes)),
	}

	resp, err := s.client.Do(ctx, http.MethodPost, uploadURL, bytes.NewReader(uploadBytes), func() (io.Reader, error) {
		return bytes.NewReader(uploadBytes), nil
	}, headers)
	if err != nil {
		return datastore.ObjectInfo{}, err
	}
	defer resp.Body.Close()

	if err := s.client.EnsureOK(resp); err != nil {
		return datastore.ObjectInfo{}, err
	}

	var created driveFile
	if err := json.NewDecoder(io.LimitReader(resp.Body, maxListBytes)).Decode(&created); err != nil {
		return datastore.ObjectInfo{}, fmt.Errorf("gdrivestore: decode created file: %w", err)
	}

	// Write-Then-Delete: Now that new file upload is verified, retire any superseded file with same key to trash.
	s.retireSuperseded(ctx, key, created.ID)

	return datastore.ObjectInfo{
		Key:         key,
		Size:        int64(len(payload)),
		Checksum:    sum,
		ContentType: ct,
		Version:     created.ID,
	}, nil
}

// retireSuperseded finds and trashes any older active files matching key in rootFolderID except exceptID.
func (s *Store) retireSuperseded(ctx context.Context, key, exceptID string) error {
	q := fmt.Sprintf("'%s' in parents and name = '%s' and trashed = false",
		escapeSearchString(s.rootFolderID), escapeSearchString(key))

	u := fmt.Sprintf("%s/drive/v3/files?q=%s&fields=files(id)&pageSize=50",
		s.baseURL, url.QueryEscape(q))

	resp, err := s.client.Do(ctx, http.MethodGet, u, nil, nil, nil)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return s.client.EnsureOK(resp)
	}

	var fl driveFileList
	if err := json.NewDecoder(io.LimitReader(resp.Body, maxListBytes)).Decode(&fl); err != nil {
		return err
	}

	for _, f := range fl.Files {
		if f.ID != "" && f.ID != exceptID {
			patchBody := []byte(`{"trashed":true}`)
			patchURL := fmt.Sprintf("%s/drive/v3/files/%s", s.baseURL, url.PathEscape(f.ID))
			patchHeaders := map[string]string{
				"Content-Type":   "application/json",
				"Content-Length": strconv.Itoa(len(patchBody)),
			}
			pResp, pErr := s.client.Do(ctx, http.MethodPatch, patchURL, bytes.NewReader(patchBody), nil, patchHeaders)
			if pErr != nil {
				return pErr
			}
			defer pResp.Body.Close()
			if pResp.StatusCode != http.StatusNotFound {
				if err := s.client.EnsureOK(pResp); err != nil {
					return err
				}
			}
		}
	}
	return nil
}

// Get streams an object over HTTP directly without in-memory buffering.
func (s *Store) Get(ctx context.Context, key, version string) (io.ReadCloser, datastore.ObjectInfo, error) {
	if strings.TrimSpace(key) == "" {
		return nil, datastore.ObjectInfo{}, errors.New("gdrivestore: empty key")
	}

	var fileID string
	var info datastore.ObjectInfo

	if version != "" {
		// Version is the Google Drive fileId
		fileID = version
		// Fetch metadata for info
		u := fmt.Sprintf("%s/drive/v3/files/%s?fields=id,name,size,mimeType,properties,appProperties,md5Checksum,version,trashed",
			s.baseURL, url.PathEscape(fileID))
		resp, err := s.client.Do(ctx, http.MethodGet, u, nil, nil, nil)
		if err != nil {
			return nil, datastore.ObjectInfo{}, err
		}
		defer resp.Body.Close()
		if err := s.client.EnsureOK(resp); err != nil {
			return nil, datastore.ObjectInfo{}, err
		}
		var f driveFile
		if err := json.NewDecoder(io.LimitReader(resp.Body, maxListBytes)).Decode(&f); err != nil {
			return nil, datastore.ObjectInfo{}, fmt.Errorf("gdrivestore: decode metadata: %w", err)
		}
		if f.Trashed {
			return nil, datastore.ObjectInfo{}, objstorerest.ErrNotFound
		}
		info = s.fileToObjectInfo(&f, key)
	} else {
		f, err := s.findActiveFile(ctx, key)
		if err != nil {
			return nil, datastore.ObjectInfo{}, err
		}
		fileID = f.ID
		info = s.fileToObjectInfo(f, key)
	}

	mediaURL := fmt.Sprintf("%s/drive/v3/files/%s?alt=media", s.baseURL, url.PathEscape(fileID))
	resp, err := s.client.Do(ctx, http.MethodGet, mediaURL, nil, nil, nil)
	if err != nil {
		return nil, datastore.ObjectInfo{}, err
	}

	if err := s.client.EnsureOK(resp); err != nil {
		_ = resp.Body.Close()
		return nil, datastore.ObjectInfo{}, err
	}

	if info.Size == 0 && resp.ContentLength > 0 {
		info.Size = resp.ContentLength
	}
	if info.ContentType == "" {
		info.ContentType = resp.Header.Get("Content-Type")
	}

	return resp.Body, info, nil
}

// Head returns metadata for an object without downloading media.
func (s *Store) Head(ctx context.Context, key string) (datastore.ObjectInfo, error) {
	if strings.TrimSpace(key) == "" {
		return datastore.ObjectInfo{}, errors.New("gdrivestore: empty key")
	}

	f, err := s.findActiveFile(ctx, key)
	if err != nil {
		return datastore.ObjectInfo{}, err
	}
	return s.fileToObjectInfo(f, key), nil
}

// Delete permanently removes matching file(s) (satisfying AC-1 permanent delete).
// Deleting a non-existent object is idempotent (returns nil).
func (s *Store) Delete(ctx context.Context, key, version string) error {
	if strings.TrimSpace(key) == "" {
		return errors.New("gdrivestore: empty key")
	}

	if version != "" {
		u := fmt.Sprintf("%s/drive/v3/files/%s", s.baseURL, url.PathEscape(version))
		resp, err := s.client.Do(ctx, http.MethodDelete, u, nil, nil, nil)
		if err != nil {
			return err
		}
		defer resp.Body.Close()
		if resp.StatusCode == http.StatusNotFound {
			return nil
		}
		return s.client.EnsureOK(resp)
	}

	q := fmt.Sprintf("'%s' in parents and name = '%s' and trashed = false",
		escapeSearchString(s.rootFolderID), escapeSearchString(key))

	u := fmt.Sprintf("%s/drive/v3/files?q=%s&fields=files(id)&pageSize=50",
		s.baseURL, url.QueryEscape(q))

	resp, err := s.client.Do(ctx, http.MethodGet, u, nil, nil, nil)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusNotFound {
		return nil
	}
	if err := s.client.EnsureOK(resp); err != nil {
		return err
	}

	var fl driveFileList
	if err := json.NewDecoder(io.LimitReader(resp.Body, maxListBytes)).Decode(&fl); err != nil {
		return fmt.Errorf("gdrivestore: decode files list: %w", err)
	}

	for _, f := range fl.Files {
		if f.ID != "" {
			delURL := fmt.Sprintf("%s/drive/v3/files/%s", s.baseURL, url.PathEscape(f.ID))
			dResp, dErr := s.client.Do(ctx, http.MethodDelete, delURL, nil, nil, nil)
			if dErr != nil {
				return dErr
			}
			defer dResp.Body.Close()
			if dResp.StatusCode != http.StatusNotFound {
				if err := s.client.EnsureOK(dResp); err != nil {
					return err
				}
			}
		}
	}
	return nil
}

// ListPage returns a page of objects matching prefix with bounded memory.
func (s *Store) ListPage(ctx context.Context, prefix, marker string, limit int) ([]datastore.ObjectInfo, string, error) {
	q := fmt.Sprintf("'%s' in parents and trashed = false", escapeSearchString(s.rootFolderID))

	pageSize := 100
	if limit > 0 && limit <= 1000 {
		pageSize = limit
	}

	params := url.Values{}
	params.Set("q", q)
	params.Set("fields", "nextPageToken,files(id,name,size,mimeType,properties,appProperties,md5Checksum,version,createdTime,modifiedTime,trashed)")
	params.Set("pageSize", strconv.Itoa(pageSize))
	if marker != "" {
		params.Set("pageToken", marker)
	}

	u := fmt.Sprintf("%s/drive/v3/files?%s", s.baseURL, params.Encode())
	resp, err := s.client.Do(ctx, http.MethodGet, u, nil, nil, nil)
	if err != nil {
		return nil, "", err
	}
	defer resp.Body.Close()

	if err := s.client.EnsureOK(resp); err != nil {
		return nil, "", err
	}

	var fl driveFileList
	if err := json.NewDecoder(io.LimitReader(resp.Body, maxListBytes)).Decode(&fl); err != nil {
		return nil, "", fmt.Errorf("gdrivestore: decode files list: %w", err)
	}

	var items []datastore.ObjectInfo
	for _, f := range fl.Files {
		key := f.Name
		if prefix != "" && !strings.HasPrefix(key, prefix) {
			continue
		}
		items = append(items, s.fileToObjectInfo(&f, key))
	}

	return items, fl.NextPageToken, nil
}

// List scans all objects under prefix, following pagination to completion.
func (s *Store) List(ctx context.Context, prefix string) ([]datastore.ObjectInfo, error) {
	var out []datastore.ObjectInfo
	marker := ""
	for {
		items, nextMarker, err := s.ListPage(ctx, prefix, marker, 0)
		if err != nil {
			return nil, err
		}
		out = append(out, items...)
		if nextMarker == "" {
			break
		}
		marker = nextMarker
	}
	return out, nil
}

// SignedURL is not supported by Google Drive (declared via Capabilities).
func (s *Store) SignedURL(_ context.Context, _, _ string, _ time.Duration) (string, error) {
	return "", &datastore.UnsupportedError{Provider: "gdrive", Capability: "signed-urls"}
}

// fileToObjectInfo extracts portable ObjectInfo from a driveFile resource.
func (s *Store) fileToObjectInfo(f *driveFile, defaultKey string) datastore.ObjectInfo {
	key := f.Name
	if key == "" {
		key = defaultKey
	}

	cs := ""
	if f.Properties != nil {
		cs = f.Properties[checksumProp]
	}
	if cs == "" && f.AppProperties != nil {
		cs = f.AppProperties[checksumProp]
	}
	if cs == "" {
		cs = f.MD5Checksum
	}

	size, _ := strconv.ParseInt(f.Size, 10, 64)

	return datastore.ObjectInfo{
		Key:         key,
		Size:        size,
		ContentType: f.MimeType,
		Checksum:    cs,
		Version:     f.ID,
	}
}
