package objpolicy

import (
	"context"
	"errors"
	"io"
	"testing"
	"time"

	"productforge/datastore"
)

type stubStore struct{ signed bool }

func (s stubStore) Put(context.Context, string, io.Reader, int64, datastore.PutOptions) (datastore.ObjectInfo, error) {
	return datastore.ObjectInfo{}, errors.New("not used")
}
func (s stubStore) Get(context.Context, string, string) (io.ReadCloser, datastore.ObjectInfo, error) {
	return nil, datastore.ObjectInfo{}, errors.New("not used")
}
func (s stubStore) Head(context.Context, string) (datastore.ObjectInfo, error) {
	return datastore.ObjectInfo{}, errors.New("not used")
}
func (s stubStore) Delete(context.Context, string, string) error { return errors.New("not used") }
func (s stubStore) List(context.Context, string) ([]datastore.ObjectInfo, error) {
	return nil, errors.New("not used")
}
func (s stubStore) SignedURL(_ context.Context, key, method string, ttl time.Duration) (string, error) {
	return "https://signed/" + key + "?m=" + method + "&ttl=" + ttl.String(), nil
}
func (s stubStore) Capabilities() datastore.Capabilities {
	return datastore.Capabilities{SignedURLs: s.signed}
}

func TestMintAllowsValidRequest(t *testing.T) {
	u, err := Mint(context.Background(), stubStore{signed: true}, "tenant-a", "tenant-a/x/y", "get", 0)
	if err != nil || u == "" {
		t.Fatalf("mint: %v %q", err, u)
	}
}

func TestMintRejectsOutOfScopeKey(t *testing.T) {
	if _, err := Mint(context.Background(), stubStore{signed: true}, "tenant-a", "tenant-b/x", "GET", time.Minute); !errors.Is(err, ErrTenantKey) {
		t.Fatalf("want ErrTenantKey, got %v", err)
	}
}

func TestMintRejectsMethodAndTTL(t *testing.T) {
	if _, err := Mint(context.Background(), stubStore{signed: true}, "t", "t/x", "POST", time.Minute); !errors.Is(err, ErrMethod) {
		t.Fatalf("want ErrMethod, got %v", err)
	}
	if _, err := Mint(context.Background(), stubStore{signed: true}, "t", "t/x", "GET", time.Second); !errors.Is(err, ErrTTL) {
		t.Fatalf("want ErrTTL low, got %v", err)
	}
	if _, err := Mint(context.Background(), stubStore{signed: true}, "t", "t/x", "GET", time.Hour); !errors.Is(err, ErrTTL) {
		t.Fatalf("want ErrTTL high, got %v", err)
	}
}

func TestMintRejectsProviderWithoutSignedURLs(t *testing.T) {
	if _, err := Mint(context.Background(), stubStore{signed: false}, "t", "t/x", "GET", time.Minute); !errors.Is(err, ErrUnsupported) {
		t.Fatalf("want ErrUnsupported, got %v", err)
	}
}
