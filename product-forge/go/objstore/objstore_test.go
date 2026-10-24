package objstore

import (
	"bytes"
	"context"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"productforge/datastore"
)

func TestConformObjectStore(t *testing.T) {
	s, err := NewLocalStore(t.TempDir(), 0)
	if err != nil {
		t.Fatal(err)
	}
	if errs := datastore.ConformObjectStore(context.Background(), s); len(errs) != 0 {
		t.Fatalf("conformance failed: %v", errs)
	}
}

func TestPutGetChecksum(t *testing.T) {
	ctx := context.Background()
	s, _ := NewLocalStore(t.TempDir(), 0)
	body := []byte("hello world")
	info, err := s.Put(ctx, "a/b/obj.txt", bytes.NewReader(body), int64(len(body)),
		datastore.PutOptions{ContentType: "text/plain"})
	if err != nil {
		t.Fatal(err)
	}
	if info.Checksum == "" || info.Size != int64(len(body)) {
		t.Fatalf("bad info: %+v", info)
	}
	rc, gi, err := s.Get(ctx, "a/b/obj.txt", "")
	if err != nil {
		t.Fatal(err)
	}
	defer rc.Close()
	got := make([]byte, len(body))
	if _, err := rc.Read(got); err != nil && err.Error() != "EOF" {
		t.Fatal(err)
	}
	if !bytes.Equal(got, body) || gi.Checksum != info.Checksum {
		t.Fatalf("round-trip mismatch")
	}
}

func TestBadKeysRejected(t *testing.T) {
	ctx := context.Background()
	s, _ := NewLocalStore(t.TempDir(), 0)
	for _, k := range []string{"", "../evil", "a/../../evil", "/abs"} {
		if _, err := s.Put(ctx, k, strings.NewReader("x"), 1, datastore.PutOptions{}); !errors.Is(err, ErrBadKey) {
			t.Errorf("key %q: want ErrBadKey, got %v", k, err)
		}
	}
}

func TestSizeLimit(t *testing.T) {
	s, _ := NewLocalStore(t.TempDir(), 4)
	if _, err := s.Put(context.Background(), "k", strings.NewReader("toolong"), 7, datastore.PutOptions{}); !errors.Is(err, ErrTooLarge) {
		t.Fatalf("want ErrTooLarge, got %v", err)
	}
}

func TestSymlinkEscapeRejected(t *testing.T) {
	root := t.TempDir()
	outside := t.TempDir()
	if err := os.Symlink(outside, filepath.Join(root, "link")); err != nil {
		t.Skip("symlink not permitted on this platform")
	}
	s, _ := NewLocalStore(root, 0)
	if _, err := s.Put(context.Background(), "link/x", strings.NewReader("x"), 1, datastore.PutOptions{}); !errors.Is(err, ErrBadKey) {
		t.Fatalf("want ErrBadKey for symlink escape, got %v", err)
	}
}

func TestSignedURLUnsupported(t *testing.T) {
	s, _ := NewLocalStore(t.TempDir(), 0)
	if _, err := s.SignedURL(context.Background(), "k", "GET", 0); !errors.Is(err, ErrNotSupported) {
		t.Fatalf("want ErrNotSupported, got %v", err)
	}
}

func TestPutRetentionFailsClosed(t *testing.T) {
	st, err := NewLocalStore(t.TempDir(), 0)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := st.Put(context.Background(), "k", bytes.NewReader([]byte("x")), 1,
		datastore.PutOptions{Retention: time.Hour, Immutable: true}); err == nil {
		t.Fatal("local store must refuse retention")
	}
}

func TestLifecycleUnsupported(t *testing.T) {
	st, err := NewLocalStore(t.TempDir(), 0)
	if err != nil {
		t.Fatal(err)
	}
	if _, ok := datastore.Lifecycle(st); ok {
		t.Fatal("local store must not advertise lifecycle capability")
	}
	if err := st.ApplyLifecycle(context.Background(), "k", "", datastore.LifecyclePolicy{Mode: "GOVERNANCE"}); !errors.Is(err, datastore.ErrUnsupported) {
		t.Fatalf("ApplyLifecycle: want ErrUnsupported, got %v", err)
	}
	if _, err := st.ObjectLifecycle(context.Background(), "k", ""); !errors.Is(err, datastore.ErrUnsupported) {
		t.Fatalf("ObjectLifecycle: want ErrUnsupported, got %v", err)
	}
}

func TestImmutableRejectsDifferentContent(t *testing.T) {
	st, err := NewLocalStore(t.TempDir(), 0)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := st.Put(context.Background(), "k", bytes.NewReader([]byte("a")), 1, datastore.PutOptions{Immutable: true}); err != nil {
		t.Fatal(err)
	}
	if _, err := st.Put(context.Background(), "k", bytes.NewReader([]byte("b")), 1, datastore.PutOptions{Immutable: true}); !errors.Is(err, datastore.ErrImmutable) {
		t.Fatalf("want ErrImmutable, got %v", err)
	}
}
