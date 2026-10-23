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
	"log"
	"path"
	"sort"
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

// allowedMethods is the fixed, unexported allowlist.
var allowedMethods = map[string]bool{"GET": true, "PUT": true, "HEAD": true, "DELETE": true}

// AllowedMethods returns the allowlist (sorted) for documentation/tests; it cannot be mutated.
func AllowedMethods() []string {
	out := make([]string, 0, len(allowedMethods))
	for m := range allowedMethods {
		out = append(out, m)
	}
	sort.Strings(out)
	return out
}

// Mint issues a signed URL for key within tenantPrefix. tenantPrefix comes from the authenticated tenant
// context (never from a caller-supplied value) and the key must live under it.
func Mint(ctx context.Context, store datastore.ObjectStore, tenantPrefix, key, method string, ttl time.Duration) (string, error) {
	if !store.Capabilities().SignedURLs {
		log.Printf("objpolicy: deny reason=UNSUPPORTED method=%s", method)
		return "", fmt.Errorf("%w: provider has no signed URLs", ErrUnsupported)
	}
	m := strings.ToUpper(strings.TrimSpace(method))
	if !allowedMethods[m] {
		log.Printf("objpolicy: deny reason=METHOD method=%q", method)
		return "", fmt.Errorf("%w: %q", ErrMethod, method)
	}
	if ttl == 0 {
		ttl = DefaultTTL
	}
	if ttl < MinTTL || ttl > MaxTTL {
		log.Printf("objpolicy: deny reason=TTL ttl=%s", ttl)
		return "", fmt.Errorf("%w: %s (min %s, max %s)", ErrTTL, ttl, MinTTL, MaxTTL)
	}
	prefix, k := cleanPath(tenantPrefix), cleanPath(key)
	if prefix == "" || !(k == prefix || strings.HasPrefix(k, prefix+"/")) {
		log.Printf("objpolicy: deny reason=TENANT_KEY key=%q prefix=%q", key, tenantPrefix)
		return "", fmt.Errorf("%w: %q not under %q", ErrTenantKey, key, tenantPrefix)
	}
	return store.SignedURL(ctx, k, m, ttl)
}

// cleanPath normalizes a key/prefix and refuses traversal (".." / absolute escapes).
func cleanPath(p string) string {
	c := path.Clean("/" + strings.TrimSpace(p))
	if c == "/" || strings.Contains(c, "..") {
		return ""
	}
	return strings.TrimPrefix(c, "/")
}
