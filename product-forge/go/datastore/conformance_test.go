package datastore

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"strings"
	"sync"
	"testing"
	"time"
)

// fakeObjectStore is an in-memory ObjectStore that MUST pass the conformance suite.
type fakeObjectStore struct {
	mu sync.Mutex
	m  map[string][]byte
}

func newFakeObjectStore() *fakeObjectStore { return &fakeObjectStore{m: map[string][]byte{}} }

func (f *fakeObjectStore) Put(_ context.Context, key string, r io.Reader, _ int64, opts PutOptions) (ObjectInfo, error) {
	b, _ := io.ReadAll(r)
	f.mu.Lock()
	f.m[key] = b
	f.mu.Unlock()
	return ObjectInfo{Key: key, Size: int64(len(b)), Checksum: fmt.Sprintf("sha256:%d", len(b)), ContentType: opts.ContentType}, nil
}

func (f *fakeObjectStore) Get(_ context.Context, key, _ string) (io.ReadCloser, ObjectInfo, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	b, ok := f.m[key]
	if !ok {
		return nil, ObjectInfo{}, fmt.Errorf("not found: %s", key)
	}
	return io.NopCloser(bytes.NewReader(b)), ObjectInfo{Key: key, Size: int64(len(b)), Checksum: fmt.Sprintf("sha256:%d", len(b))}, nil
}

func (f *fakeObjectStore) Head(_ context.Context, key string) (ObjectInfo, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	b, ok := f.m[key]
	if !ok {
		return ObjectInfo{}, fmt.Errorf("not found: %s", key)
	}
	return ObjectInfo{Key: key, Size: int64(len(b)), Checksum: fmt.Sprintf("sha256:%d", len(b))}, nil
}

func (f *fakeObjectStore) Delete(_ context.Context, key, _ string) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	delete(f.m, key)
	return nil
}

func (f *fakeObjectStore) List(_ context.Context, prefix string) ([]ObjectInfo, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	var out []ObjectInfo
	for k, v := range f.m {
		if strings.HasPrefix(k, prefix) {
			out = append(out, ObjectInfo{Key: k, Size: int64(len(v))})
		}
	}
	return out, nil
}

func (f *fakeObjectStore) SignedURL(_ context.Context, key, _ string, _ time.Duration) (string, error) {
	return "https://signed.invalid/" + key, nil
}

func (f *fakeObjectStore) Capabilities() Capabilities { return Capabilities{SignedURLs: true} }

// brokenObjectStore always returns an empty checksum, so conformance must FAIL.
type brokenObjectStore struct{ *fakeObjectStore }

func (b *brokenObjectStore) Put(ctx context.Context, key string, r io.Reader, size int64, o PutOptions) (ObjectInfo, error) {
	info, err := b.fakeObjectStore.Put(ctx, key, r, size, o)
	info.Checksum = ""
	return info, err
}

func TestConformObjectStore_Pass(t *testing.T) {
	if errs := ConformObjectStore(context.Background(), newFakeObjectStore()); len(errs) != 0 {
		t.Fatalf("fake adapter must conform, got: %v", errs)
	}
}

func TestConformObjectStore_Fails(t *testing.T) {
	b := &brokenObjectStore{newFakeObjectStore()}
	if errs := ConformObjectStore(context.Background(), b); len(errs) == 0 {
		t.Fatal("conformance suite must FAIL on a broken adapter (checksum)")
	}
}
