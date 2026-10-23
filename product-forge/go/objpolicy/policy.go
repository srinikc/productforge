// Package objpolicy is the single privilege boundary for minting signed object URLs (EDP-16).
//
// Callers never talk to provider credentials directly: Mint validates the method allowlist, the TTL bounds
// and the tenant key prefix, then delegates to the provider's SignedURL capability. Providers without signed
// URLs fail closed with datastore.ErrUnsupported.
package objpolicy

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"

	"productforge/datastore"
)

const (
	MinTTL     = 30 * time.Second
	MaxTTL     = 15 * time.Minute
	DefaultTTL = 5 * time.Minute
)

var (
	ErrTTL         = errors.New("objpolicy: ttl outside the allowed bounds")
	ErrMethod      = errors.New("objpolicy: method not allowed")
	ErrTenantKey   = errors.New("objpolicy: key is outside the tenant prefix")
	ErrUnsupported = datastore.ErrUnsupported
)

// AllowedMethods is the fixed method allowlist.
var AllowedMethods = map[string]bool{"GET": true, "PUT": true, "HEAD": true, "DELETE": true}

// Mint issues a signed URL for key within tenantPrefix. tenantPrefix comes from the authenticated tenant
// context (never from a caller-supplied value) and the key must live under it.
func Mint(ctx context.Context, store datastore.ObjectStore, tenantPrefix, key, method string, ttl time.Duration) (string, error) {
	if !store.Capabilities().SignedURLs {
		return "", fmt.Errorf("%w: provider has no signed URLs", ErrUnsupported)
	}
	m := strings.ToUpper(strings.TrimSpace(method))
	if !AllowedMethods[m] {
		return "", fmt.Errorf("%w: %q", ErrMethod, method)
	}
	if ttl == 0 {
		ttl = DefaultTTL
	}
	if ttl < MinTTL || ttl > MaxTTL {
		return "", fmt.Errorf("%w: %s (min %s, max %s)", ErrTTL, ttl, MinTTL, MaxTTL)
	}
	prefix := strings.Trim(tenantPrefix, "/")
	k := strings.Trim(key, "/")
	if prefix == "" || !(k == prefix || strings.HasPrefix(k, prefix+"/")) {
		return "", fmt.Errorf("%w: %q not under %q", ErrTenantKey, key, tenantPrefix)
	}
	return store.SignedURL(ctx, key, m, ttl)
}
