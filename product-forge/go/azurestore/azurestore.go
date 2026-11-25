// Package azurestore is the Azure Blob Storage datastore.ObjectStore adapter (EDP-14-pattern, BI-PF-1433).
//
// It speaks the Azure Blob REST API directly over the shared, stdlib-only productforge/objstorerest core
// (ZERO provider SDK dependencies). Object content is content-addressed by sha256, persisted in object
// metadata (x-ms-meta-pf_checksum) so Head and List report it. Capabilities are declared honestly (all false)
// and unsupported options fail-closed.
package azurestore

import (
	"bytes"
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/xml"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"sort"
	"strconv"
	"strings"
	"time"

	"productforge/datastore"
	"productforge/objstorerest"
)

const (
	// DefaultAzureAPIVersion defines the target Azure Storage REST API protocol version.
	DefaultAzureAPIVersion = "2020-10-02"

	// checksumMeta is the canonical user-metadata key written by Put and read by Head/Get.
	checksumMeta = "pf_checksum"

	// maxListBytes bounds container XML payload processing to 10MB to prevent XML expansion / OOM DOS
	// while allowing up to ~50,000 blob metadata entries per page.
	maxListBytes = 10 * 1024 * 1024
)

// SharedKeyAuth signs requests using the Azure Storage Shared Key algorithm (HMAC-SHA256).
type SharedKeyAuth struct {
	Account    string
	Key        string // base64-encoded storage account key
	APIVersion string // optional; defaults to DefaultAzureAPIVersion ("2020-10-02")
}

// Authorize computes and adds the canonicalized SharedKey authorization header and x-ms-date.
func (a SharedKeyAuth) Authorize(_ context.Context, req *http.Request) error {
	ver := a.APIVersion
	if ver == "" {
		ver = DefaultAzureAPIVersion
	}

	now := time.Now().UTC().Format(http.TimeFormat)
	req.Header.Set("x-ms-date", now)
	req.Header.Set("x-ms-version", ver)

	if a.Key == "" || a.Account == "" {
		return nil
	}

	keyBytes, err := base64.StdEncoding.DecodeString(a.Key)
	if err != nil {
		return fmt.Errorf("azurestore: decode shared key: %w", err)
	}

	cl := req.Header.Get("Content-Length")
	if req.ContentLength > 0 && cl == "" {
		cl = strconv.FormatInt(req.ContentLength, 10)
	}
	if cl == "0" && (req.Method == http.MethodGet || req.Method == http.MethodHead || req.Method == http.MethodDelete) {
		cl = ""
	}

	// CanonicalizedHeaders: all x-ms- headers in lowercase, sorted lexicographically
	var msHeaders []string
	headerMap := make(map[string]string)
	for k, v := range req.Header {
		lk := strings.ToLower(k)
		if strings.HasPrefix(lk, "x-ms-") {
			headerMap[lk] = strings.Join(v, ",")
			msHeaders = append(msHeaders, lk)
		}
	}
	sort.Strings(msHeaders)
	var canonHeaders strings.Builder
	for _, k := range msHeaders {
		canonHeaders.WriteString(k)
		canonHeaders.WriteString(":")
		canonHeaders.WriteString(headerMap[k])
		canonHeaders.WriteString("\n")
	}

	// CanonicalizedResource: /<account><path> + sorted query parameters
	var canonRes strings.Builder
	canonRes.WriteString("/")
	canonRes.WriteString(a.Account)
	canonRes.WriteString(req.URL.Path)

	q := req.URL.Query()
	if len(q) > 0 {
		var qKeys []string
		for k := range q {
			qKeys = append(qKeys, strings.ToLower(k))
		}
		sort.Strings(qKeys)
		for _, k := range qKeys {
			canonRes.WriteString("\n")
			canonRes.WriteString(k)
			canonRes.WriteString(":")
			canonRes.WriteString(strings.Join(q[k], ","))
		}
	}

	stringToSign := fmt.Sprintf("%s\n%s\n%s\n%s\n%s\n%s\n%s\n%s\n%s\n%s\n%s\n%s\n%s%s",
		req.Method,
		req.Header.Get("Content-Encoding"),
		req.Header.Get("Content-Language"),
		cl,
		req.Header.Get("Content-MD5"),
		req.Header.Get("Content-Type"),
		"", // Date is empty since x-ms-date is set
		req.Header.Get("If-Modified-Since"),
		req.Header.Get("If-Match"),
		req.Header.Get("If-None-Match"),
		req.Header.Get("If-Unmodified-Since"),
		req.Header.Get("Range"),
		canonHeaders.String(),
		canonRes.String(),
	)

	h := hmac.New(sha256.New, keyBytes)
	h.Write([]byte(stringToSign))
	sig := base64.StdEncoding.EncodeToString(h.Sum(nil))
	req.Header.Set("Authorization", fmt.Sprintf("SharedKey %s:%s", a.Account, sig))
	return nil
}

// SASTokenAuth appends a Shared Access Signature query string to outgoing requests.
type SASTokenAuth struct {
	Token      string
	APIVersion string
}

// Authorize sets x-ms-version and appends the SAS query token.
func (a SASTokenAuth) Authorize(_ context.Context, req *http.Request) error {
	ver := a.APIVersion
	if ver == "" {
		ver = DefaultAzureAPIVersion
	}
	req.Header.Set("x-ms-version", ver)

	tok := strings.TrimPrefix(strings.TrimSpace(a.Token), "?")
	if tok == "" {
		return nil
	}
	if req.URL.RawQuery == "" {
		req.URL.RawQuery = tok
	} else {
		req.URL.RawQuery = req.URL.RawQuery + "&" + tok
	}
	return nil
}

// BearerAuth supplies an OAuth2 / Azure AD bearer token.
type BearerAuth struct {
	Token      string
	APIVersion string
}

// Authorize sets x-ms-version and the Authorization: Bearer <token> header.
func (a BearerAuth) Authorize(_ context.Context, req *http.Request) error {
	ver := a.APIVersion
	if ver == "" {
		ver = DefaultAzureAPIVersion
	}
	req.Header.Set("x-ms-version", ver)

	tok := strings.TrimSpace(a.Token)
	if tok != "" {
		req.Header.Set("Authorization", "Bearer "+tok)
	}
	return nil
}

// AuthFromCredentials constructs the appropriate objstorerest.Auth based on available credentials.
// Precedence order:
// 1. SharedKeyAuth (requires non-empty account and key)
// 2. SASTokenAuth (requires non-empty sas)
// 3. BearerAuth (requires non-empty token)
// Returns nil if no valid credential set is provided (useful for mock/emulated environments).
func AuthFromCredentials(account, key, sas, token string) objstorerest.Auth {
	if strings.TrimSpace(key) != "" && strings.TrimSpace(account) != "" {
		return SharedKeyAuth{Account: strings.TrimSpace(account), Key: strings.TrimSpace(key)}
	}
	if strings.TrimSpace(sas) != "" {
		return SASTokenAuth{Token: strings.TrimSpace(sas)}
	}
	if strings.TrimSpace(token) != "" {
		return BearerAuth{Token: strings.TrimSpace(token)}
	}
	return nil
}

// Config configures the Azure Blob adapter.
type Config struct {
	Account    string
	Container  string
	BaseURL    string // default https://<account>.blob.core.windows.net (override for Azurite/tests)
	Auth       objstorerest.Auth
	HTTPClient *http.Client
	MaxRetries int
	UserAgent  string // optional custom user agent; defaults to "productforge-azurestore/1"
}

// Store is the Azure Blob Storage ObjectStore adapter.
type Store struct {
	client    *objstorerest.Client
	account   string
	container string
	baseURL   string
}

// New constructs an Azure Blob ObjectStore adapter (fail-closed on missing container).
func New(cfg Config) (*Store, error) {
	container := strings.TrimSpace(cfg.Container)
	if container == "" {
		return nil, errors.New("azurestore: container is required")
	}

	base := strings.TrimRight(strings.TrimSpace(cfg.BaseURL), "/")
	if base == "" {
		account := strings.TrimSpace(cfg.Account)
		if account == "" {
			return nil, errors.New("azurestore: account is required when BaseURL is not set")
		}
		base = fmt.Sprintf("https://%s.blob.core.windows.net", account)
	}

	ua := strings.TrimSpace(cfg.UserAgent)
	if ua == "" {
		ua = "productforge-azurestore/1"
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
		client:    cl,
		account:   strings.TrimSpace(cfg.Account),
		container: container,
		baseURL:   base,
	}, nil
}

// Capabilities declares truthfully that optional capabilities are not supported.
func (s *Store) Capabilities() datastore.Capabilities {
	return datastore.Capabilities{}
}

func (s *Store) blobURL(key string) string {
	key = strings.TrimPrefix(key, "/")
	parts := strings.Split(key, "/")
	for i, p := range parts {
		parts[i] = url.PathEscape(p)
	}
	return fmt.Sprintf("%s/%s/%s", s.baseURL, url.PathEscape(s.container), strings.Join(parts, "/"))
}

func (s *Store) containerURL() string {
	return fmt.Sprintf("%s/%s", s.baseURL, url.PathEscape(s.container))
}

// Put uploads a block blob with SHA256 checksum in user metadata.
// Unsupported optional capabilities (immutability, retention, CMK) fail-closed.
func (s *Store) Put(ctx context.Context, key string, r io.Reader, size int64, opts datastore.PutOptions) (datastore.ObjectInfo, error) {
	if strings.TrimSpace(key) == "" {
		return datastore.ObjectInfo{}, errors.New("azurestore: empty key")
	}
	if opts.Immutable {
		return datastore.ObjectInfo{}, &datastore.UnsupportedError{Provider: "azure", Capability: "immutability"}
	}
	if opts.Retention > 0 || opts.RetentionMode != "" {
		return datastore.ObjectInfo{}, &datastore.UnsupportedError{Provider: "azure", Capability: "retention"}
	}
	if opts.ServerSideEncryption != "" {
		return datastore.ObjectInfo{}, &datastore.UnsupportedError{Provider: "azure", Capability: "server-side-encryption"}
	}

	var payload []byte
	if size >= 0 {
		buf := make([]byte, size)
		n, err := io.ReadFull(r, buf)
		if err != nil && err != io.EOF && err != io.ErrUnexpectedEOF {
			return datastore.ObjectInfo{}, fmt.Errorf("azurestore: read payload: %w", err)
		}
		if int64(n) != size {
			return datastore.ObjectInfo{}, fmt.Errorf("azurestore: size mismatch: declared %d, read %d", size, n)
		}
		// Verify no trailing bytes
		var extra [1]byte
		if extraN, _ := r.Read(extra[:]); extraN > 0 {
			return datastore.ObjectInfo{}, fmt.Errorf("azurestore: size mismatch: declared %d, read more than declared", size)
		}
		payload = buf
	} else {
		var err error
		payload, err = io.ReadAll(r)
		if err != nil {
			return datastore.ObjectInfo{}, fmt.Errorf("azurestore: read payload: %w", err)
		}
	}

	ct := opts.ContentType
	if ct == "" {
		ct = "application/octet-stream"
	}
	sum := objstorerest.SHA256Hex(payload)
	if opts.Checksum != "" && opts.Checksum != sum {
		return datastore.ObjectInfo{}, fmt.Errorf("azurestore: checksum mismatch: declared %s, computed %s", opts.Checksum, sum)
	}

	headers := map[string]string{
		"x-ms-blob-type":        "BlockBlob",
		"Content-Type":          ct,
		"Content-Length":        strconv.Itoa(len(payload)),
		"x-ms-meta-pf_checksum": sum,
	}

	u := s.blobURL(key)
	resp, err := s.client.Do(ctx, http.MethodPut, u, bytes.NewReader(payload), func() (io.Reader, error) {
		return bytes.NewReader(payload), nil
	}, headers)
	if err != nil {
		return datastore.ObjectInfo{}, err
	}
	defer resp.Body.Close()

	if err := s.client.EnsureOK(resp); err != nil {
		return datastore.ObjectInfo{}, err
	}

	return datastore.ObjectInfo{
		Key:         key,
		Size:        int64(len(payload)),
		Checksum:    sum,
		ContentType: ct,
		Version:     resp.Header.Get("x-ms-version-id"),
	}, nil
}

// Get streams an object over HTTP directly without buffering into memory, honoring streaming contracts.
func (s *Store) Get(ctx context.Context, key, version string) (io.ReadCloser, datastore.ObjectInfo, error) {
	if strings.TrimSpace(key) == "" {
		return nil, datastore.ObjectInfo{}, errors.New("azurestore: empty key")
	}

	u := s.blobURL(key)
	if version != "" {
		u += "?versionid=" + url.QueryEscape(version)
	}

	resp, err := s.client.Do(ctx, http.MethodGet, u, nil, nil, nil)
	if err != nil {
		return nil, datastore.ObjectInfo{}, err
	}

	if err := s.client.EnsureOK(resp); err != nil {
		_ = resp.Body.Close()
		return nil, datastore.ObjectInfo{}, err
	}

	size, _ := strconv.ParseInt(resp.Header.Get("Content-Length"), 10, 64)
	cs := s.extractChecksum(resp.Header)

	info := datastore.ObjectInfo{
		Key:         key,
		Checksum:    cs,
		Size:        size,
		ContentType: resp.Header.Get("Content-Type"),
		Version:     resp.Header.Get("x-ms-version-id"),
	}
	return resp.Body, info, nil
}

// Head returns metadata for an object.
func (s *Store) Head(ctx context.Context, key string) (datastore.ObjectInfo, error) {
	if strings.TrimSpace(key) == "" {
		return datastore.ObjectInfo{}, errors.New("azurestore: empty key")
	}

	resp, err := s.client.Do(ctx, http.MethodHead, s.blobURL(key), nil, nil, nil)
	if err != nil {
		return datastore.ObjectInfo{}, err
	}
	defer resp.Body.Close()

	if err := s.client.EnsureOK(resp); err != nil {
		return datastore.ObjectInfo{}, err
	}

	size, _ := strconv.ParseInt(resp.Header.Get("Content-Length"), 10, 64)
	cs := s.extractChecksum(resp.Header)

	return datastore.ObjectInfo{
		Key:         key,
		Size:        size,
		ContentType: resp.Header.Get("Content-Type"),
		Checksum:    cs,
		Version:     resp.Header.Get("x-ms-version-id"),
	}, nil
}

// extractChecksum resolves the SHA256 checksum from headers.
// Primary SSOT: x-ms-meta-pf_checksum. Fallbacks support legacy interop: pf-checksum, checksum, ETag.
func (s *Store) extractChecksum(h http.Header) string {
	if cs := h.Get("x-ms-meta-pf_checksum"); cs != "" {
		return cs
	}
	if cs := h.Get("x-ms-meta-pf-checksum"); cs != "" {
		return cs
	}
	if cs := h.Get("x-ms-meta-checksum"); cs != "" {
		return cs
	}
	return strings.Trim(h.Get("ETag"), "\"")
}

// Delete permanently removes a blob. Deleting a non-existent blob is idempotent.
func (s *Store) Delete(ctx context.Context, key, version string) error {
	if strings.TrimSpace(key) == "" {
		return errors.New("azurestore: empty key")
	}

	u := s.blobURL(key)
	if version != "" {
		u += "?versionid=" + url.QueryEscape(version)
	}

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

// ListPage returns a page of blobs matching prefix with bounded memory.
func (s *Store) ListPage(ctx context.Context, prefix, marker string, limit int) ([]datastore.ObjectInfo, string, error) {
	q := url.Values{}
	q.Set("restype", "container")
	q.Set("comp", "list")
	q.Set("include", "metadata")
	if prefix != "" {
		q.Set("prefix", prefix)
	}
	if marker != "" {
		q.Set("marker", marker)
	}
	if limit > 0 {
		q.Set("maxresults", strconv.Itoa(limit))
	}

	u := s.containerURL() + "?" + q.Encode()
	resp, err := s.client.Do(ctx, http.MethodGet, u, nil, nil, nil)
	if err != nil {
		return nil, "", err
	}
	defer resp.Body.Close()

	if err := s.client.EnsureOK(resp); err != nil {
		return nil, "", err
	}

	var er azureEnumerationResults
	if err := xml.NewDecoder(io.LimitReader(resp.Body, maxListBytes)).Decode(&er); err != nil {
		return nil, "", fmt.Errorf("azurestore: decode container list XML: %w", err)
	}

	items := make([]datastore.ObjectInfo, 0, len(er.Blobs.Blob))
	for _, b := range er.Blobs.Blob {
		cs := b.Metadata.Checksum
		if cs == "" {
			cs = b.Metadata.DashChecksum
		}
		if cs == "" {
			cs = b.Metadata.AltChecksum
		}
		if cs == "" {
			cs = strings.Trim(b.Properties.Etag, "\"")
		}

		items = append(items, datastore.ObjectInfo{
			Key:         b.Name,
			Size:        b.Properties.ContentLength,
			ContentType: b.Properties.ContentType,
			Checksum:    cs,
		})
	}

	return items, er.NextMarker, nil
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

// SignedURL is not supported by this adapter (declared via Capabilities).
func (s *Store) SignedURL(_ context.Context, _, _ string, _ time.Duration) (string, error) {
	return "", &datastore.UnsupportedError{Provider: "azure", Capability: "signed-urls"}
}

// ---- XML wire models for container list ----

type azureEnumerationResults struct {
	XMLName    xml.Name   `xml:"EnumerationResults"`
	Blobs      azureBlobs `xml:"Blobs"`
	NextMarker string     `xml:"NextMarker"`
}

type azureBlobs struct {
	Blob []azureBlobItem `xml:"Blob"`
}

type azureBlobItem struct {
	Name       string              `xml:"Name"`
	Properties azureBlobProperties `xml:"Properties"`
	Metadata   azureBlobMetadata   `xml:"Metadata"`
}

type azureBlobProperties struct {
	ContentLength int64  `xml:"Content-Length"`
	ContentType   string `xml:"Content-Type"`
	Etag          string `xml:"Etag"`
	BlobType      string `xml:"BlobType"`
}

type azureBlobMetadata struct {
	Checksum     string `xml:"pf_checksum"`
	DashChecksum string `xml:"pf-checksum"`
	AltChecksum  string `xml:"checksum"`
}
