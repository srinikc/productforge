package gcsstore

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"mime"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"os"
	"sort"
	"strconv"
	"strings"
	"sync"
	"testing"
	"time"

	"productforge/datastore"
	"productforge/objstorerest"
)

// mockGCS is an in-memory GCS JSON/Media API (upload multipart/resumable, metadata, media, delete, list-by-prefix).
type mockGCS struct {
	mu       sync.Mutex
	objs     map[string]mockObj
	sessions map[string]*mockSession
	gen      int
	pageSize int
}

type mockObj struct {
	data       []byte
	ct         string
	generation string
	meta       map[string]string
}

type mockSession struct {
	name string
	ct   string
	meta map[string]string
	data []byte
}

func newMockGCS() *httptest.Server {
	srv, _ := newMockGCSSized(0)
	return srv
}

func newMockGCSSized(pageSize int) (*httptest.Server, *mockGCS) {
	m := &mockGCS{
		objs:     map[string]mockObj{},
		sessions: map[string]*mockSession{},
		pageSize: pageSize,
	}
	mux := http.NewServeMux()
	mux.HandleFunc("/upload/storage/v1/b/", m.upload)
	mux.HandleFunc("/storage/v1/b/", m.objects)
	return httptest.NewServer(mux), m
}

func (m *mockGCS) upload(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodPost && r.URL.Query().Get("uploadType") == "resumable" {
		var meta struct {
			Name        string            `json:"name"`
			ContentType string            `json:"contentType"`
			Metadata    map[string]string `json:"metadata"`
		}
		if err := json.NewDecoder(r.Body).Decode(&meta); err != nil {
			http.Error(w, "bad resumable meta", http.StatusBadRequest)
			return
		}
		m.mu.Lock()
		m.gen++
		sID := strconv.Itoa(m.gen)
		m.sessions[sID] = &mockSession{
			name: meta.Name,
			ct:   meta.ContentType,
			meta: meta.Metadata,
		}
		m.mu.Unlock()
		w.Header().Set("Location", r.URL.Path+"?uploadType=resumable&upload_id="+sID)
		w.WriteHeader(http.StatusOK)
		return
	}

	if r.Method == http.MethodPut && r.URL.Query().Get("upload_id") != "" {
		sID := r.URL.Query().Get("upload_id")
		m.mu.Lock()
		sess, ok := m.sessions[sID]
		m.mu.Unlock()
		if !ok {
			http.Error(w, "session not found", http.StatusNotFound)
			return
		}
		chunk, err := io.ReadAll(r.Body)
		if err != nil {
			http.Error(w, "read chunk error", http.StatusBadRequest)
			return
		}
		sess.data = append(sess.data, chunk...)

		cr := r.Header.Get("Content-Range") // bytes start-end/total
		isFinal := false
		if cr != "" {
			parts := strings.Split(cr, "/")
			if len(parts) == 2 && parts[1] != "*" {
				if total, err := strconv.Atoi(parts[1]); err == nil && len(sess.data) >= total {
					isFinal = true
				}
			}
		}

		if isFinal {
			m.mu.Lock()
			m.gen++
			gen := strconv.Itoa(m.gen)
			m.objs[sess.name] = mockObj{data: sess.data, ct: sess.ct, generation: gen, meta: sess.meta}
			delete(m.sessions, sID)
			m.mu.Unlock()
			writeObjJSON(w, sess.name, sess.ct, gen, sess.meta, len(sess.data))
		} else {
			w.Header().Set("Range", fmt.Sprintf("bytes=0-%d", len(sess.data)-1))
			w.WriteHeader(308) // Resume Incomplete
		}
		return
	}

	if r.Method != http.MethodPost {
		http.Error(w, "method", http.StatusMethodNotAllowed)
		return
	}
	_, params, err := mime.ParseMediaType(r.Header.Get("Content-Type"))
	if err != nil {
		http.Error(w, "bad content-type", http.StatusBadRequest)
		return
	}
	mr := multipart.NewReader(r.Body, params["boundary"])
	p1, err := mr.NextPart()
	if err != nil {
		http.Error(w, "part1", http.StatusBadRequest)
		return
	}
	metaBytes, _ := io.ReadAll(p1)
	var meta struct {
		Name        string            `json:"name"`
		ContentType string            `json:"contentType"`
		Metadata    map[string]string `json:"metadata"`
	}
	if err := json.Unmarshal(metaBytes, &meta); err != nil {
		http.Error(w, "meta", http.StatusBadRequest)
		return
	}
	p2, err := mr.NextPart()
	if err != nil {
		http.Error(w, "part2", http.StatusBadRequest)
		return
	}
	data, _ := io.ReadAll(p2)
	m.mu.Lock()
	m.gen++
	gen := strconv.Itoa(m.gen)
	m.objs[meta.Name] = mockObj{data: data, ct: meta.ContentType, generation: gen, meta: meta.Metadata}
	m.mu.Unlock()
	writeObjJSON(w, meta.Name, meta.ContentType, gen, meta.Metadata, len(data))
}

func (m *mockGCS) objects(w http.ResponseWriter, r *http.Request) {
	p := strings.TrimPrefix(r.URL.Path, "/storage/v1/b/") // "<bucket>/o[/<key>]"
	idx := strings.Index(p, "/o")
	if idx < 0 {
		http.Error(w, "bad path", http.StatusBadRequest)
		return
	}
	rest := strings.TrimPrefix(p[idx+2:], "/")
	if rest == "" {
		m.list(w, r)
		return
	}
	key := rest
	switch r.Method {
	case http.MethodGet:
		m.mu.Lock()
		o, ok := m.objs[key]
		m.mu.Unlock()
		if !ok {
			http.Error(w, "not found", http.StatusNotFound)
			return
		}
		if r.URL.Query().Get("alt") == "media" {
			w.Header().Set("Content-Type", o.ct)
			_, _ = w.Write(o.data)
			return
		}
		writeObjJSON(w, key, o.ct, o.generation, o.meta, len(o.data))
	case http.MethodPatch:
		var req struct {
			Metadata map[string]string `json:"metadata"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, "bad patch body", http.StatusBadRequest)
			return
		}
		m.mu.Lock()
		o, ok := m.objs[key]
		if !ok {
			m.mu.Unlock()
			http.Error(w, "not found", http.StatusNotFound)
			return
		}
		if o.meta == nil {
			o.meta = map[string]string{}
		}
		for k, v := range req.Metadata {
			o.meta[k] = v
		}
		m.objs[key] = o
		m.mu.Unlock()
		writeObjJSON(w, key, o.ct, o.generation, o.meta, len(o.data))
	case http.MethodDelete:
		m.mu.Lock()
		_, ok := m.objs[key]
		delete(m.objs, key)
		m.mu.Unlock()
		if !ok {
			http.Error(w, "not found", http.StatusNotFound)
			return
		}
		w.WriteHeader(http.StatusNoContent)
	default:
		http.Error(w, "method", http.StatusMethodNotAllowed)
	}
}

func (m *mockGCS) list(w http.ResponseWriter, r *http.Request) {
	prefix := r.URL.Query().Get("prefix")
	pageSize := m.pageSize
	if pageSize <= 0 {
		pageSize = 1000
	}
	start := 0
	if tok := r.URL.Query().Get("pageToken"); tok != "" {
		start, _ = strconv.Atoi(tok)
	}
	m.mu.Lock()
	defer m.mu.Unlock()
	names := make([]string, 0, len(m.objs))
	for name := range m.objs {
		if prefix != "" && !strings.HasPrefix(name, prefix) {
			continue
		}
		names = append(names, name)
	}
	sort.Strings(names)
	if start > len(names) {
		start = len(names)
	}
	end := start + pageSize
	if end > len(names) {
		end = len(names)
	}
	items := []map[string]any{}
	for _, name := range names[start:end] {
		o := m.objs[name]
		items = append(items, map[string]any{
			"name": name, "size": strconv.Itoa(len(o.data)), "contentType": o.ct,
			"generation": o.generation, "metadata": o.meta,
		})
	}
	next := ""
	if end < len(names) {
		next = strconv.Itoa(end)
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]any{"items": items, "nextPageToken": next})
}

func writeObjJSON(w http.ResponseWriter, name, ct, gen string, meta map[string]string, size int) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]any{
		"name": name, "size": strconv.Itoa(size), "contentType": ct, "generation": gen, "metadata": meta,
	})
}

func TestGCSStoreConformance(t *testing.T) {
	srv := newMockGCS()
	defer srv.Close()
	st, err := New(Config{Bucket: "b", BaseURL: srv.URL, HTTPClient: srv.Client()})
	if err != nil {
		t.Fatal(err)
	}
	if errs := datastore.ConformObjectStore(context.Background(), st); len(errs) > 0 {
		t.Fatalf("conformance failures: %v", errs)
	}
}

func TestGCSListPaginates(t *testing.T) {
	srv, _ := newMockGCSSized(1) // force 1 item per page
	defer srv.Close()
	st, _ := New(Config{Bucket: "b", BaseURL: srv.URL, HTTPClient: srv.Client()})
	ctx := context.Background()
	for _, k := range []string{"p/a", "p/b", "p/c"} {
		if _, err := st.Put(ctx, k, strings.NewReader("x"), 1, datastore.PutOptions{ContentType: "text/plain"}); err != nil {
			t.Fatal(err)
		}
	}
	items, err := st.List(ctx, "p/")
	if err != nil {
		t.Fatal(err)
	}
	if len(items) != 3 {
		t.Fatalf("pagination truncated: got %d, want 3 (nextPageToken not followed)", len(items))
	}
}

func TestGCSPutHeadChecksumAndPrefixList(t *testing.T) {
	srv := newMockGCS()
	defer srv.Close()
	st, _ := New(Config{Bucket: "b", BaseURL: srv.URL, HTTPClient: srv.Client()})
	ctx := context.Background()
	body := []byte("hello gcs")
	if _, err := st.Put(ctx, "proj/a.txt", strings.NewReader(string(body)), int64(len(body)), datastore.PutOptions{ContentType: "text/plain"}); err != nil {
		t.Fatal(err)
	}
	h, err := st.Head(ctx, "proj/a.txt")
	if err != nil || h.Checksum == "" || h.Size != int64(len(body)) {
		t.Fatalf("head: %+v err=%v", h, err)
	}
	items, err := st.List(ctx, "proj/")
	if err != nil || len(items) != 1 || items[0].Key != "proj/a.txt" {
		t.Fatalf("list: %v err=%v", items, err)
	}
	if other, _ := st.List(ctx, "nope/"); len(other) != 0 {
		t.Fatalf("prefix filter leaked: %v", other)
	}
}

func TestResumableUpload(t *testing.T) {
	srv := newMockGCS()
	defer srv.Close()
	st, err := New(Config{Bucket: "b", BaseURL: srv.URL, HTTPClient: srv.Client()})
	if err != nil {
		t.Fatal(err)
	}
	ctx := context.Background()

	// 11 MB payload (> 5 MB ResumableThreshold)
	payloadSize := int64(11 * 1024 * 1024)
	payload := make([]byte, payloadSize)
	for i := range payload {
		payload[i] = byte(i % 251)
	}
	expectedChecksum := objstorerest.SHA256Hex(payload)

	key := "large/dataset.bin"
	info, err := st.Put(ctx, key, bytes.NewReader(payload), payloadSize, datastore.PutOptions{
		ContentType: "application/octet-stream",
	})
	if err != nil {
		t.Fatalf("resumable Put failed: %v", err)
	}
	if info.Size != payloadSize {
		t.Fatalf("Put size mismatch: got %d, want %d", info.Size, payloadSize)
	}
	if info.Checksum != expectedChecksum {
		t.Fatalf("Put checksum mismatch: got %s, want %s", info.Checksum, expectedChecksum)
	}

	// Verify Head
	h, err := st.Head(ctx, key)
	if err != nil {
		t.Fatalf("Head failed: %v", err)
	}
	if h.Size != payloadSize || h.Checksum != expectedChecksum {
		t.Fatalf("Head mismatch: size=%d want=%d, checksum=%s want=%s", h.Size, payloadSize, h.Checksum, expectedChecksum)
	}

	// Verify Get
	rc, gInfo, err := st.Get(ctx, key, "")
	if err != nil {
		t.Fatalf("Get failed: %v", err)
	}
	defer rc.Close()
	downloaded, err := io.ReadAll(rc)
	if err != nil {
		t.Fatalf("read downloaded object: %v", err)
	}
	if int64(len(downloaded)) != payloadSize {
		t.Fatalf("Get downloaded length mismatch: got %d, want %d", len(downloaded), payloadSize)
	}
	if gInfo.Checksum != expectedChecksum {
		t.Fatalf("Get checksum mismatch: got %s, want %s", gInfo.Checksum, expectedChecksum)
	}
}

func TestResumableUpload_SizeMismatch(t *testing.T) {
	srv := newMockGCS()
	defer srv.Close()
	st, err := New(Config{Bucket: "b", BaseURL: srv.URL, HTTPClient: srv.Client()})
	if err != nil {
		t.Fatal(err)
	}
	ctx := context.Background()

	// Declare 11 MB, but provide only 6 MB
	declaredSize := int64(11 * 1024 * 1024)
	actualSize := int64(6 * 1024 * 1024)
	payload := make([]byte, actualSize)
	for i := range payload {
		payload[i] = byte(i % 199)
	}

	key := "invalid/truncated.bin"
	_, err = st.Put(ctx, key, bytes.NewReader(payload), declaredSize, datastore.PutOptions{
		ContentType: "application/octet-stream",
	})
	if err == nil {
		t.Fatalf("expected error on declared size mismatch, got nil")
	}
	if !strings.Contains(err.Error(), "size mismatch") {
		t.Fatalf("expected size mismatch error, got: %v", err)
	}

	// Object must NOT exist in store
	_, err = st.Head(ctx, key)
	if err == nil {
		t.Fatalf("object should not exist after failed upload")
	}
}

type memoryTrackingReader struct {
	r         io.Reader
	totalRead int64
	maxChunk  int
}

func (m *memoryTrackingReader) Read(p []byte) (int, error) {
	n, err := m.r.Read(p)
	m.totalRead += int64(n)
	if n > m.maxChunk {
		m.maxChunk = n
	}
	return n, err
}

func TestResumableUpload_ProofOfMemoryBoundedness(t *testing.T) {
	srv := newMockGCS()
	defer srv.Close()
	st, err := New(Config{Bucket: "b", BaseURL: srv.URL, HTTPClient: srv.Client()})
	if err != nil {
		t.Fatal(err)
	}
	ctx := context.Background()

	// 10 MB payload
	payloadSize := int64(10 * 1024 * 1024)
	payload := make([]byte, payloadSize)
	tr := &memoryTrackingReader{r: bytes.NewReader(payload)}

	key := "large/bounded.bin"
	info, err := st.Put(ctx, key, tr, payloadSize, datastore.PutOptions{
		ContentType: "application/octet-stream",
	})
	if err != nil {
		t.Fatalf("Put failed: %v", err)
	}
	if info.Size != payloadSize {
		t.Fatalf("size mismatch: got %d, want %d", info.Size, payloadSize)
	}
	// Verify that buffer chunk reads were bounded by ChunkSize (5 MB)
	if int64(tr.maxChunk) > ChunkSize {
		t.Fatalf("chunk read exceeded buffer chunk size: %d > %d", tr.maxChunk, ChunkSize)
	}
}

func TestGCSStore_RealProviderQualification(t *testing.T) {
	bucket := os.Getenv("PF_GCS_QUALIFICATION_BUCKET")
	if bucket == "" {
		t.Skip("skipping real-provider qualification: PF_GCS_QUALIFICATION_BUCKET not set (see docs/GCS-ADAPTER-QUALIFICATION.md)")
	}
	tok := os.Getenv("PF_GCS_TOKEN")
	var auth objstorerest.Auth
	if tok != "" {
		auth = TokenAuth{Token: tok}
	} else if credsFile := os.Getenv("PF_GCS_CREDENTIALS_FILE"); credsFile != "" {
		if data, err := os.ReadFile(credsFile); err == nil {
			auth = AuthFromCredentials(data)
		}
	}
	baseURL := os.Getenv("PF_GCS_BASE_URL")
	st, err := New(Config{
		Bucket:  bucket,
		BaseURL: baseURL,
		Auth:    auth,
	})
	if err != nil {
		t.Fatalf("failed to init real-provider GCS store: %v", err)
	}

	ctx := context.Background()
	// 1. Conformance suite
	if errs := datastore.ConformObjectStore(ctx, st); len(errs) > 0 {
		t.Fatalf("real-provider conformance failed: %v", errs)
	}

	// 2. Large streaming resumable upload qualification (> 5 MB)
	largeSize := int64(6 * 1024 * 1024) // 6 MB
	largePayload := make([]byte, largeSize)
	for i := range largePayload {
		largePayload[i] = byte(i % 251)
	}
	key := fmt.Sprintf("qualification-run/%d-large.bin", time.Now().UnixNano())
	defer func() {
		_ = st.Delete(ctx, key, "")
	}()

	info, err := st.Put(ctx, key, bytes.NewReader(largePayload), largeSize, datastore.PutOptions{
		ContentType: "application/octet-stream",
	})
	if err != nil {
		t.Fatalf("real-provider resumable put failed: %v", err)
	}
	if info.Size != largeSize {
		t.Fatalf("size mismatch: got %d, want %d", info.Size, largeSize)
	}
	expectedChecksum := objstorerest.SHA256Hex(largePayload)
	if info.Checksum != expectedChecksum {
		t.Fatalf("checksum mismatch: got %s, want %s", info.Checksum, expectedChecksum)
	}

	// Verify Head
	h, err := st.Head(ctx, key)
	if err != nil {
		t.Fatalf("real-provider head failed: %v", err)
	}
	if h.Checksum != expectedChecksum || h.Size != largeSize {
		t.Fatalf("real-provider head mismatch: %+v", h)
	}
}
