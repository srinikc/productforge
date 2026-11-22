package gdrivestore_test

import (
	"bytes"
	"context"
	"crypto/md5"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
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
	"time"

	"productforge/datastore"
	"productforge/gdrivestore"
)

type mockFile struct {
	id            string
	name          string
	parentID      string
	mimeType      string
	data          []byte
	properties    map[string]string
	appProperties map[string]string
	md5Checksum   string
	sha256Hex     string
	createdTime   string
	modifiedTime  string
	trashed       bool
}

type mockGDriveServer struct {
	mu           sync.RWMutex
	rootFolderID string
	files        map[string]*mockFile
	fileSeq      int64
	uploadErr    bool
}

func newMockGDriveServer(rootFolderID string) *mockGDriveServer {
	return &mockGDriveServer{
		rootFolderID: rootFolderID,
		files:        make(map[string]*mockFile),
	}
}

func (m *mockGDriveServer) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	m.mu.Lock()
	defer m.mu.Unlock()

	path := r.URL.Path

	// Multipart upload endpoint
	if path == "/upload/drive/v3/files" && r.Method == http.MethodPost {
		if m.uploadErr {
			http.Error(w, `{"error":{"message":"simulated upload failure"}}`, http.StatusInternalServerError)
			return
		}

		ct := r.Header.Get("Content-Type")
		mediaType, params, err := mime.ParseMediaType(ct)
		if err != nil || !strings.HasPrefix(mediaType, "multipart/") {
			http.Error(w, "invalid multipart content type", http.StatusBadRequest)
			return
		}

		mr := multipart.NewReader(r.Body, params["boundary"])

		// Part 1: Metadata
		part1, err := mr.NextPart()
		if err != nil {
			http.Error(w, "missing metadata part", http.StatusBadRequest)
			return
		}
		var meta struct {
			Name          string            `json:"name"`
			Parents       []string          `json:"parents"`
			MimeType      string            `json:"mimeType"`
			Properties    map[string]string `json:"properties"`
			AppProperties map[string]string `json:"appProperties"`
		}
		if err := json.NewDecoder(part1).Decode(&meta); err != nil {
			http.Error(w, "invalid metadata json", http.StatusBadRequest)
			return
		}

		// Part 2: Media
		part2, err := mr.NextPart()
		if err != nil {
			http.Error(w, "missing media part", http.StatusBadRequest)
			return
		}
		data, err := io.ReadAll(part2)
		if err != nil {
			http.Error(w, "read media failed", http.StatusInternalServerError)
			return
		}

		m.fileSeq++
		id := fmt.Sprintf("id-%d-%d", time.Now().UnixNano(), m.fileSeq)

		m5 := md5.Sum(data)
		s256 := sha256.Sum256(data)
		nowStr := time.Now().UTC().Format(time.RFC3339Nano)

		parent := ""
		if len(meta.Parents) > 0 {
			parent = meta.Parents[0]
		}

		f := &mockFile{
			id:            id,
			name:          meta.Name,
			parentID:      parent,
			mimeType:      meta.MimeType,
			data:          data,
			properties:    meta.Properties,
			appProperties: meta.AppProperties,
			md5Checksum:   hex.EncodeToString(m5[:]),
			sha256Hex:     hex.EncodeToString(s256[:]),
			createdTime:   nowStr,
			modifiedTime:  nowStr,
			trashed:       false,
		}
		m.files[id] = f

		w.Header().Set("Content-Type", "application/json; charset=UTF-8")
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(map[string]any{
			"id":            f.id,
			"name":          f.name,
			"size":          strconv.Itoa(len(f.data)),
			"mimeType":      f.mimeType,
			"properties":    f.properties,
			"appProperties": f.appProperties,
			"md5Checksum":   f.md5Checksum,
			"version":       f.id,
			"createdTime":   f.createdTime,
			"modifiedTime":  f.modifiedTime,
			"trashed":       f.trashed,
		})
		return
	}

	// Files collection endpoint (list / query)
	if path == "/drive/v3/files" && r.Method == http.MethodGet {
		q := r.URL.Query().Get("q")
		pageToken := r.URL.Query().Get("pageToken")
		pageSizeStr := r.URL.Query().Get("pageSize")
		pageSize := 100
		if ps, err := strconv.Atoi(pageSizeStr); err == nil && ps > 0 {
			pageSize = ps
		}

		// Filter files
		var matched []*mockFile
		for _, f := range m.files {
			if f.trashed {
				continue
			}
			if f.parentID != m.rootFolderID {
				continue
			}
			if strings.Contains(q, "name = '") {
				// Extract target name from query
				start := strings.Index(q, "name = '") + len("name = '")
				end := strings.Index(q[start:], "'")
				if end >= 0 {
					targetName := q[start : start+end]
					targetName = strings.ReplaceAll(targetName, "\\'", "'")
					targetName = strings.ReplaceAll(targetName, "\\\\", "\\")
					if f.name != targetName {
						continue
					}
				}
			}
			matched = append(matched, f)
		}

		sort.Slice(matched, func(i, j int) bool {
			return matched[i].id < matched[j].id
		})

		startIdx := 0
		if pageToken != "" {
			for i, f := range matched {
				if f.id == pageToken {
					startIdx = i
					break
				}
			}
		}

		endIdx := startIdx + pageSize
		var nextPageToken string
		if endIdx < len(matched) {
			nextPageToken = matched[endIdx].id
		} else {
			endIdx = len(matched)
		}

		pageItems := matched[startIdx:endIdx]
		var fileItems []map[string]any
		for _, f := range pageItems {
			fileItems = append(fileItems, map[string]any{
				"id":            f.id,
				"name":          f.name,
				"size":          strconv.Itoa(len(f.data)),
				"mimeType":      f.mimeType,
				"properties":    f.properties,
				"appProperties": f.appProperties,
				"md5Checksum":   f.md5Checksum,
				"version":       f.id,
				"createdTime":   f.createdTime,
				"modifiedTime":  f.modifiedTime,
				"trashed":       f.trashed,
			})
		}

		w.Header().Set("Content-Type", "application/json; charset=UTF-8")
		_ = json.NewEncoder(w).Encode(map[string]any{
			"nextPageToken": nextPageToken,
			"files":         fileItems,
		})
		return
	}

	// Single file operations: /drive/v3/files/{id}
	if strings.HasPrefix(path, "/drive/v3/files/") {
		fileID := strings.TrimPrefix(path, "/drive/v3/files/")
		f, ok := m.files[fileID]

		if r.Method == http.MethodGet {
			if !ok {
				http.Error(w, `{"error":{"message":"not found"}}`, http.StatusNotFound)
				return
			}
			if r.URL.Query().Get("alt") == "media" {
				if f.trashed {
					http.Error(w, `{"error":{"message":"file is in trash"}}`, http.StatusNotFound)
					return
				}
				w.Header().Set("Content-Type", f.mimeType)
				w.Header().Set("Content-Length", strconv.Itoa(len(f.data)))
				w.WriteHeader(http.StatusOK)
				_, _ = w.Write(f.data)
				return
			}

			// Metadata get
			w.Header().Set("Content-Type", "application/json; charset=UTF-8")
			_ = json.NewEncoder(w).Encode(map[string]any{
				"id":            f.id,
				"name":          f.name,
				"size":          strconv.Itoa(len(f.data)),
				"mimeType":      f.mimeType,
				"properties":    f.properties,
				"appProperties": f.appProperties,
				"md5Checksum":   f.md5Checksum,
				"version":       f.id,
				"createdTime":   f.createdTime,
				"modifiedTime":  f.modifiedTime,
				"trashed":       f.trashed,
			})
			return
		}

		if r.Method == http.MethodPatch {
			if !ok {
				http.Error(w, `{"error":{"message":"not found"}}`, http.StatusNotFound)
				return
			}
			var patchData map[string]any
			if err := json.NewDecoder(r.Body).Decode(&patchData); err != nil {
				http.Error(w, "bad json", http.StatusBadRequest)
				return
			}
			if t, hasT := patchData["trashed"].(bool); hasT {
				f.trashed = t
			}
			w.Header().Set("Content-Type", "application/json; charset=UTF-8")
			_ = json.NewEncoder(w).Encode(map[string]any{
				"id":      f.id,
				"name":    f.name,
				"trashed": f.trashed,
			})
			return
		}

		if r.Method == http.MethodDelete {
			if !ok {
				http.Error(w, `{"error":{"message":"not found"}}`, http.StatusNotFound)
				return
			}
			delete(m.files, fileID)
			w.WriteHeader(http.StatusNoContent)
			return
		}
	}

	http.NotFound(w, r)
}

func TestGDriveStore_Conformance(t *testing.T) {
	rootFolder := "0B-root-folder-12345"
	mock := newMockGDriveServer(rootFolder)
	srv := httptest.NewServer(mock)
	defer srv.Close()

	store, err := gdrivestore.New(gdrivestore.Config{
		RootFolderID:  rootFolder,
		BaseURL:       srv.URL,
		UploadBaseURL: srv.URL,
		Auth:          gdrivestore.BearerAuth{Token: "test-token-xyz"},
	})
	if err != nil {
		t.Fatalf("New() failed: %v", err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()

	failures := datastore.ConformObjectStore(ctx, store)
	for _, f := range failures {
		t.Errorf("conformance failure: %v", f)
	}
}

func TestGDriveStore_CapabilitiesHonesty(t *testing.T) {
	store, err := gdrivestore.New(gdrivestore.Config{
		RootFolderID: "dummy-folder",
		BaseURL:      "http://localhost:9999",
	})
	if err != nil {
		t.Fatalf("New() failed: %v", err)
	}

	caps := store.Capabilities()
	if caps.SignedURLs || caps.Transactions || caps.ObjectLock || caps.ObjectVersioning || caps.MultipartUpload || caps.CustomerManagedKeys {
		t.Errorf("expected all-false capabilities, got %+v", caps)
	}

	ctx := context.Background()
	_, err = store.SignedURL(ctx, "test/key", "GET", time.Minute)
	if !errors.Is(err, datastore.ErrUnsupported) {
		t.Errorf("expected ErrUnsupported for SignedURL, got %v", err)
	}

	// Test fail-closed on unsupported Put options
	_, err = store.Put(ctx, "k", strings.NewReader("val"), 3, datastore.PutOptions{Immutable: true})
	if !errors.Is(err, datastore.ErrUnsupported) {
		t.Errorf("expected ErrUnsupported for Immutable=true, got %v", err)
	}

	_, err = store.Put(ctx, "k", strings.NewReader("val"), 3, datastore.PutOptions{Retention: time.Hour})
	if !errors.Is(err, datastore.ErrUnsupported) {
		t.Errorf("expected ErrUnsupported for Retention, got %v", err)
	}

	_, err = store.Put(ctx, "k", strings.NewReader("val"), 3, datastore.PutOptions{ServerSideEncryption: "aws:kms"})
	if !errors.Is(err, datastore.ErrUnsupported) {
		t.Errorf("expected ErrUnsupported for ServerSideEncryption, got %v", err)
	}
}

func TestGDriveStore_WriteThenDeleteCollisionSafety(t *testing.T) {
	rootFolder := "safety-folder-xyz"
	mock := newMockGDriveServer(rootFolder)
	srv := httptest.NewServer(mock)
	defer srv.Close()

	store, err := gdrivestore.New(gdrivestore.Config{
		RootFolderID:  rootFolder,
		BaseURL:       srv.URL,
		UploadBaseURL: srv.URL,
	})
	if err != nil {
		t.Fatalf("New() failed: %v", err)
	}

	ctx := context.Background()
	key := "docs/architecture/spec.pdf"
	v1Content := []byte("version 1 payload data")

	// 1. Initial write (v1)
	info1, err := store.Put(ctx, key, bytes.NewReader(v1Content), int64(len(v1Content)), datastore.PutOptions{ContentType: "application/pdf"})
	if err != nil {
		t.Fatalf("Put v1 failed: %v", err)
	}

	mock.mu.Lock()
	v1File := mock.files[info1.Version]
	if v1File == nil || v1File.trashed {
		mock.mu.Unlock()
		t.Fatalf("v1 file missing or trashed")
	}
	mock.mu.Unlock()

	// 2. Simulated upload failure on replacement write (v2)
	mock.uploadErr = true
	v2Content := []byte("version 2 payload with new changes")
	_, err = store.Put(ctx, key, bytes.NewReader(v2Content), int64(len(v2Content)), datastore.PutOptions{})
	if err == nil {
		t.Fatalf("expected Put v2 to fail on simulated upload error")
	}

	// Verify v1 file is completely intact and NOT trashed (Zero Data Loss guarantee)
	mock.mu.Lock()
	if v1File.trashed {
		mock.mu.Unlock()
		t.Fatalf("Write-Then-Delete violation: v1 file was trashed even though v2 upload failed!")
	}
	mock.mu.Unlock()

	head1, err := store.Head(ctx, key)
	if err != nil {
		t.Fatalf("Head after failed v2 upload failed: %v", err)
	}
	if head1.Version != info1.Version {
		t.Fatalf("Head returned wrong version: expected %s, got %s", info1.Version, head1.Version)
	}

	// 3. Successful replacement write (v2)
	mock.uploadErr = false
	info2, err := store.Put(ctx, key, bytes.NewReader(v2Content), int64(len(v2Content)), datastore.PutOptions{})
	if err != nil {
		t.Fatalf("Put v2 failed: %v", err)
	}
	if info2.Version == info1.Version {
		t.Fatalf("Put v2 should have a distinct file ID")
	}

	// Verify v1 is now retired to trash, and v2 is active
	mock.mu.Lock()
	if !v1File.trashed {
		mock.mu.Unlock()
		t.Fatalf("expected v1 file to be retired to trash after successful v2 upload")
	}
	v2File := mock.files[info2.Version]
	if v2File == nil || v2File.trashed {
		mock.mu.Unlock()
		t.Fatalf("v2 file missing or trashed")
	}
	mock.mu.Unlock()

	// Verify Get returns v2 content
	rc, gi, err := store.Get(ctx, key, "")
	if err != nil {
		t.Fatalf("Get after replacement failed: %v", err)
	}
	gotData, _ := io.ReadAll(rc)
	_ = rc.Close()
	if !bytes.Equal(gotData, v2Content) {
		t.Errorf("Get returned unexpected content")
	}
	if gi.Checksum != info2.Checksum {
		t.Errorf("Get returned checksum %s, expected %s", gi.Checksum, info2.Checksum)
	}
}

func TestGDriveStore_SizeAndChecksumValidation(t *testing.T) {
	rootFolder := "check-folder-123"
	mock := newMockGDriveServer(rootFolder)
	srv := httptest.NewServer(mock)
	defer srv.Close()

	store, err := gdrivestore.New(gdrivestore.Config{
		RootFolderID:  rootFolder,
		BaseURL:       srv.URL,
		UploadBaseURL: srv.URL,
	})
	if err != nil {
		t.Fatalf("New() failed: %v", err)
	}

	ctx := context.Background()

	// Short read
	_, err = store.Put(ctx, "k1", bytes.NewReader([]byte("short")), 10, datastore.PutOptions{})
	if err == nil || !strings.Contains(err.Error(), "size mismatch") {
		t.Errorf("expected size mismatch for short read, got %v", err)
	}

	// Long read
	_, err = store.Put(ctx, "k2", bytes.NewReader([]byte("longer than five")), 5, datastore.PutOptions{})
	if err == nil || !strings.Contains(err.Error(), "size mismatch") {
		t.Errorf("expected size mismatch for long read, got %v", err)
	}

	// Declared checksum mismatch
	_, err = store.Put(ctx, "k3", bytes.NewReader([]byte("data")), 4, datastore.PutOptions{
		Checksum: "deadbeefcafebabe",
	})
	if err == nil || !strings.Contains(err.Error(), "checksum mismatch") {
		t.Errorf("expected checksum mismatch error, got %v", err)
	}
}

func TestGDriveStore_AuthBearer(t *testing.T) {
	rootFolder := "auth-folder"
	var receivedAuth string
	var authMu sync.Mutex

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		authMu.Lock()
		receivedAuth = r.Header.Get("Authorization")
		authMu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{
			"files": []any{},
		})
	}))
	defer srv.Close()

	token := "ya29.secret-access-token-999"
	store, err := gdrivestore.New(gdrivestore.Config{
		RootFolderID: rootFolder,
		BaseURL:      srv.URL,
		Auth:         gdrivestore.AuthFromToken(token),
	})
	if err != nil {
		t.Fatalf("New() failed: %v", err)
	}

	ctx := context.Background()
	_, _ = store.List(ctx, "some-prefix")

	authMu.Lock()
	defer authMu.Unlock()
	expectedAuth := "Bearer " + token
	if receivedAuth != expectedAuth {
		t.Errorf("expected Authorization header %q, got %q", expectedAuth, receivedAuth)
	}
}
