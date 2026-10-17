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

const checksumMeta = "pf-checksum"

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

// Put uploads an object (multipart/related: metadata + media) and returns its content-addressed info.
func (s *Store) Put(ctx context.Context, key string, r io.Reader, size int64, opts datastore.PutOptions) (datastore.ObjectInfo, error) {
	body, err := io.ReadAll(r)
	if err != nil {
		return datastore.ObjectInfo{}, err
	}
	ct := opts.ContentType
	if ct == "" {
		ct = "application/octet-stream"
	}
	sum := objstorerest.SHA256Hex(body)
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

// Get downloads an object; the returned info carries the recomputed sha256 (content-addressed).
func (s *Store) Get(ctx context.Context, key, version string) (io.ReadCloser, datastore.ObjectInfo, error) {
	resp, err := s.client.Do(ctx, http.MethodGet, s.objectURL(key)+"?alt=media", nil, nil, nil)
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

// List returns objects under prefix (the provider filters by prefix).
func (s *Store) List(ctx context.Context, prefix string) ([]datastore.ObjectInfo, error) {
	u := fmt.Sprintf("%s/storage/v1/b/%s/o", s.client.BaseURL(), url.PathEscape(s.bucket))
	if prefix != "" {
		u += "?prefix=" + url.QueryEscape(prefix)
	}
	resp, err := s.client.Do(ctx, http.MethodGet, u, nil, nil, nil)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if err := s.client.EnsureOK(resp); err != nil {
		return nil, err
	}
	var lr struct {
		Items []gcsObject `json:"items"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&lr); err != nil {
		return nil, err
	}
	out := make([]datastore.ObjectInfo, 0, len(lr.Items))
	for _, o := range lr.Items {
		out = append(out, o.toInfo(o.Name, o.Metadata[checksumMeta]))
	}
	return out, nil
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
