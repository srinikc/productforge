package gcsstore

import (
	"context"
	"encoding/json"
	"io"
	"mime"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"sort"
	"strconv"
	"strings"
	"sync"
	"testing"

	"productforge/datastore"
)

// mockGCS is an in-memory GCS JSON/Media API (upload multipart, metadata, media, delete, list-by-prefix).
type mockGCS struct {
	mu       sync.Mutex
	objs     map[string]mockObj
	gen      int
	pageSize int
}

type mockObj struct {
	data       []byte
	ct         string
	generation string
	meta       map[string]string
}

func newMockGCS() *httptest.Server {
	srv, _ := newMockGCSSized(0)
	return srv
}

func newMockGCSSized(pageSize int) (*httptest.Server, *mockGCS) {
	m := &mockGCS{objs: map[string]mockObj{}, pageSize: pageSize}
	mux := http.NewServeMux()
	mux.HandleFunc("/upload/storage/v1/b/", m.upload)
	mux.HandleFunc("/storage/v1/b/", m.objects)
	return httptest.NewServer(mux), m
}

func (m *mockGCS) upload(w http.ResponseWriter, r *http.Request) {
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
