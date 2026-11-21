package azurestore_test

import (
	"bytes"
	"context"
	"encoding/xml"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"sort"
	"strings"
	"sync"
	"testing"
	"time"

	"productforge/azurestore"
	"productforge/datastore"
)

type mockBlob struct {
	data        []byte
	contentType string
	checksum    string
	versionID   string
}

type mockAzureServer struct {
	mu        sync.RWMutex
	container string
	blobs     map[string]mockBlob
}

func newMockAzureServer(container string) *mockAzureServer {
	return &mockAzureServer{
		container: container,
		blobs:     make(map[string]mockBlob),
	}
}

func (m *mockAzureServer) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	m.mu.Lock()
	defer m.mu.Unlock()

	path := strings.TrimPrefix(r.URL.Path, "/")
	parts := strings.SplitN(path, "/", 2)
	if len(parts) == 0 || parts[0] != m.container {
		http.Error(w, "container not found", http.StatusNotFound)
		return
	}

	// Container-level operations
	if len(parts) == 1 || parts[1] == "" {
		if r.Method == http.MethodGet && r.URL.Query().Get("comp") == "list" {
			prefix := r.URL.Query().Get("prefix")
			marker := r.URL.Query().Get("marker")

			var keys []string
			for k := range m.blobs {
				if strings.HasPrefix(k, prefix) {
					keys = append(keys, k)
				}
			}
			sort.Strings(keys)

			type xmlBlob struct {
				Name       string `xml:"Name"`
				Properties struct {
					ContentLength int64  `xml:"Content-Length"`
					ContentType   string `xml:"Content-Type"`
				} `xml:"Properties"`
				Metadata struct {
					Checksum string `xml:"pf_checksum"`
				} `xml:"Metadata"`
			}
			type xmlResults struct {
				XMLName    xml.Name  `xml:"EnumerationResults"`
				Blobs      []xmlBlob `xml:"Blobs>Blob"`
				NextMarker string    `xml:"NextMarker"`
			}

			var res xmlResults
			startIdx := 0
			if marker != "" {
				for i, k := range keys {
					if k == marker {
						startIdx = i + 1
						break
					}
				}
			}

			for i := startIdx; i < len(keys); i++ {
				k := keys[i]
				b := m.blobs[k]
				xb := xmlBlob{Name: k}
				xb.Properties.ContentLength = int64(len(b.data))
				xb.Properties.ContentType = b.contentType
				xb.Metadata.Checksum = b.checksum
				res.Blobs = append(res.Blobs, xb)
			}

			w.Header().Set("Content-Type", "application/xml")
			_ = xml.NewEncoder(w).Encode(res)
			return
		}
		http.Error(w, "unknown container operation", http.StatusBadRequest)
		return
	}

	blobKey := parts[1]

	switch r.Method {
	case http.MethodPut:
		b, err := io.ReadAll(r.Body)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		cs := r.Header.Get("x-ms-meta-pf_checksum")
		ct := r.Header.Get("Content-Type")
		vID := fmt.Sprintf("v-%d", time.Now().UnixNano())
		m.blobs[blobKey] = mockBlob{
			data:        b,
			contentType: ct,
			checksum:    cs,
			versionID:   vID,
		}
		w.Header().Set("x-ms-version-id", vID)
		w.WriteHeader(http.StatusCreated)

	case http.MethodGet:
		b, ok := m.blobs[blobKey]
		if !ok {
			http.Error(w, "blob not found", http.StatusNotFound)
			return
		}
		w.Header().Set("Content-Type", b.contentType)
		w.Header().Set("x-ms-meta-pf_checksum", b.checksum)
		w.Header().Set("x-ms-version-id", b.versionID)
		w.Header().Set("Content-Length", fmt.Sprintf("%d", len(b.data)))
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write(b.data)

	case http.MethodHead:
		b, ok := m.blobs[blobKey]
		if !ok {
			http.Error(w, "blob not found", http.StatusNotFound)
			return
		}
		w.Header().Set("Content-Type", b.contentType)
		w.Header().Set("x-ms-meta-pf_checksum", b.checksum)
		w.Header().Set("x-ms-version-id", b.versionID)
		w.Header().Set("Content-Length", fmt.Sprintf("%d", len(b.data)))
		w.WriteHeader(http.StatusOK)

	case http.MethodDelete:
		delete(m.blobs, blobKey)
		w.WriteHeader(http.StatusAccepted)

	default:
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
	}
}

func TestAzureStore_Conformance(t *testing.T) {
	mock := newMockAzureServer("testcontainer")
	ts := httptest.NewServer(mock)
	defer ts.Close()

	store, err := azurestore.New(azurestore.Config{
		Account:   "devstoreaccount1",
		Container: "testcontainer",
		BaseURL:   ts.URL,
	})
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}

	ctx := context.Background()
	failures := datastore.ConformObjectStore(ctx, store)
	if len(failures) > 0 {
		for _, f := range failures {
			t.Errorf("conformance failure: %v", f)
		}
	}
}

func TestAzureStore_CapabilitiesHonesty(t *testing.T) {
	mock := newMockAzureServer("capscontainer")
	ts := httptest.NewServer(mock)
	defer ts.Close()

	store, err := azurestore.New(azurestore.Config{
		Account:   "devstoreaccount1",
		Container: "capscontainer",
		BaseURL:   ts.URL,
	})
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}

	caps := store.Capabilities()
	if caps.Transactions || caps.ObjectVersioning || caps.ObjectLock ||
		caps.ConditionalWrites || caps.SignedURLs || caps.MultipartUpload || caps.CustomerManagedKeys {
		t.Fatalf("expected all capabilities to be false, got %+v", caps)
	}

	ctx := context.Background()
	_, err = store.SignedURL(ctx, "key", "GET", time.Minute)
	if err == nil {
		t.Fatal("expected error on SignedURL")
	}
	var unsupp *datastore.UnsupportedError
	if !errors.As(err, &unsupp) {
		t.Fatalf("expected UnsupportedError, got %T: %v", err, err)
	}

	// Fail-closed checks on PutOptions
	body := []byte("hello")
	_, err = store.Put(ctx, "key", bytes.NewReader(body), int64(len(body)), datastore.PutOptions{Immutable: true})
	if err == nil || !errors.As(err, &unsupp) {
		t.Fatalf("expected UnsupportedError for Immutable, got %v", err)
	}

	_, err = store.Put(ctx, "key", bytes.NewReader(body), int64(len(body)), datastore.PutOptions{Retention: time.Hour})
	if err == nil || !errors.As(err, &unsupp) {
		t.Fatalf("expected UnsupportedError for Retention, got %v", err)
	}

	_, err = store.Put(ctx, "key", bytes.NewReader(body), int64(len(body)), datastore.PutOptions{ServerSideEncryption: "azure:kms"})
	if err == nil || !errors.As(err, &unsupp) {
		t.Fatalf("expected UnsupportedError for ServerSideEncryption, got %v", err)
	}
}

func TestAzureStore_SizeAndChecksumValidation(t *testing.T) {
	mock := newMockAzureServer("validcontainer")
	ts := httptest.NewServer(mock)
	defer ts.Close()

	store, err := azurestore.New(azurestore.Config{
		Account:   "devstoreaccount1",
		Container: "validcontainer",
		BaseURL:   ts.URL,
	})
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}

	ctx := context.Background()

	// Short read
	_, err = store.Put(ctx, "short", bytes.NewReader([]byte("123")), 10, datastore.PutOptions{})
	if err == nil || !strings.Contains(err.Error(), "size mismatch") {
		t.Fatalf("expected size mismatch on short read, got: %v", err)
	}

	// Long read
	_, err = store.Put(ctx, "long", bytes.NewReader([]byte("1234567890EXTRA")), 10, datastore.PutOptions{})
	if err == nil || !strings.Contains(err.Error(), "size mismatch") {
		t.Fatalf("expected size mismatch on long read, got: %v", err)
	}

	// Checksum mismatch
	_, err = store.Put(ctx, "badsum", bytes.NewReader([]byte("content")), 7, datastore.PutOptions{Checksum: "0000000000000000000000000000000000000000000000000000000000000000"})
	if err == nil || !strings.Contains(err.Error(), "checksum mismatch") {
		t.Fatalf("expected checksum mismatch error, got: %v", err)
	}
}

func TestAzureStore_AuthMechanisms(t *testing.T) {
	var capturedAuth, capturedDate, capturedVer string
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		capturedAuth = r.Header.Get("Authorization")
		capturedDate = r.Header.Get("x-ms-date")
		capturedVer = r.Header.Get("x-ms-version")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("ok"))
	}))
	defer ts.Close()

	ctx := context.Background()

	// 1. SharedKeyAuth
	keyBase64 := "dGVzdGtleQ==" // "testkey" base64
	skAuth := azurestore.SharedKeyAuth{Account: "myaccount", Key: keyBase64}
	store1, err := azurestore.New(azurestore.Config{
		Account:   "myaccount",
		Container: "c1",
		BaseURL:   ts.URL,
		Auth:      skAuth,
	})
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	_, _, _ = store1.Get(ctx, "probe", "")
	if !strings.HasPrefix(capturedAuth, "SharedKey myaccount:") {
		t.Fatalf("expected SharedKey auth header, got %q", capturedAuth)
	}
	if capturedDate == "" || capturedVer != "2020-10-02" {
		t.Fatalf("expected valid date and version, got date=%q ver=%q", capturedDate, capturedVer)
	}

	// 2. BearerAuth
	bearerAuth := azurestore.BearerAuth{Token: "secrettoken123"}
	store2, err := azurestore.New(azurestore.Config{
		Account:   "myaccount",
		Container: "c2",
		BaseURL:   ts.URL,
		Auth:      bearerAuth,
	})
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	_, _, _ = store2.Get(ctx, "probe", "")
	if capturedAuth != "Bearer secrettoken123" {
		t.Fatalf("expected Bearer token, got %q", capturedAuth)
	}

	// 3. SASTokenAuth
	sasAuth := azurestore.SASTokenAuth{Token: "sv=2020-10-02&sig=test"}
	store3, err := azurestore.New(azurestore.Config{
		Account:   "myaccount",
		Container: "c3",
		BaseURL:   ts.URL,
		Auth:      sasAuth,
	})
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	_, _, _ = store3.Get(ctx, "probe", "")
	if capturedVer != "2020-10-02" {
		t.Fatalf("expected version 2020-10-02, got %q", capturedVer)
	}
}
