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

func ctxFor(tenant string) context.Context {
	return WithTenant(context.Background(), tenant)
}

func TestMintAllowsValidRequest(t *testing.T) {
	ResetStats()
	u, err := Mint(ctxFor("tenant-a"), stubStore{signed: true}, "tenant-a/x/y", "get", 0)
	if err != nil || u == "" {
		t.Fatalf("mint: %v %q", err, u)
	}
}

func TestMintRejectsOutOfScopeKey(t *testing.T) {
	ResetStats()
	if _, err := Mint(ctxFor("tenant-a"), stubStore{signed: true}, "tenant-b/x", "GET", time.Minute); !errors.Is(err, ErrTenantScope) {
		t.Fatalf("want ErrTenantScope, got %v", err)
	}
	if _, err := Mint(ctxFor("tenant-a"), stubStore{signed: true}, "tenant-a", "GET", time.Minute); !errors.Is(err, ErrTenantScope) {
		t.Fatalf("tenant root must be rejected, got %v", err)
	}
	if Stats()["TENANT_SCOPE"] != 2 {
		t.Fatalf("denial counter = %v", Stats())
	}
}

func TestMintRequiresAuthenticatedTenant(t *testing.T) {
	ResetStats()
	if _, err := Mint(context.Background(), stubStore{signed: true}, "tenant-a/x", "GET", time.Minute); !errors.Is(err, ErrTenantCtx) {
		t.Fatalf("want ErrTenantCtx, got %v", err)
	}
}

func TestMintRejectsMethodAndTTL(t *testing.T) {
	ResetStats()
	if _, err := Mint(ctxFor("t"), stubStore{signed: true}, "t/x", "POST", time.Minute); !errors.Is(err, ErrMethod) {
		t.Fatalf("want ErrMethod, got %v", err)
	}
	if _, err := Mint(ctxFor("t"), stubStore{signed: true}, "t/x", "GET", time.Second); !errors.Is(err, ErrTTL) {
		t.Fatalf("want ErrTTL low, got %v", err)
	}
	if _, err := Mint(ctxFor("t"), stubStore{signed: true}, "t/x", "GET", time.Hour); !errors.Is(err, ErrTTL) {
		t.Fatalf("want ErrTTL high, got %v", err)
	}
	if Stats()["METHOD"] != 1 || Stats()["TTL"] != 2 {
		t.Fatalf("denial counters = %v", Stats())
	}
}

func TestMintRejectsProviderWithoutSignedURLs(t *testing.T) {
	ResetStats()
	if _, err := Mint(ctxFor("t"), stubStore{signed: false}, "t/x", "GET", time.Minute); !errors.Is(err, ErrUnsupported) {
		t.Fatalf("want ErrUnsupported, got %v", err)
	}
}

func TestMintRejectsTraversal(t *testing.T) {
	ResetStats()
	if _, err := Mint(ctxFor("tenant-a"), stubStore{signed: true}, "tenant-a/../tenant-b/x", "GET", time.Minute); !errors.Is(err, ErrTenantScope) {
		t.Fatalf("want ErrTenantScope for traversal, got %v", err)
	}
}
