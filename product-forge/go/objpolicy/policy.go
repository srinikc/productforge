// Package objpolicy is the single privilege boundary for minting signed object URLs (EDP-16).
//
// The tenant comes from the AUTHENTICATED request context (WithTenant, set by the API auth middleware), never
// from the caller. Mint validates method/TTL/tenant scope first, then the provider capability. Denials are
// counted and logged with structured fields; providers without signed URLs fail closed.
package objpolicy

import (
	"context"
	"errors"
	"fmt"
	"log"
	"path"
	"sort"
	"strings"
	"sync"
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
	ErrTenantScope = errors.New("objpolicy: key is outside the authenticated tenant scope")
	ErrTenantCtx   = errors.New("objpolicy: authenticated tenant missing from context")
	ErrUnsupported = datastore.ErrUnsupported
)

var allowedMethods = map[string]bool{"GET": true, "PUT": true, "HEAD": true, "DELETE": true}

// AllowedMethods returns the allowlist (sorted); it cannot be mutated.
func AllowedMethods() []string {
	out := make([]string, 0, len(allowedMethods))
	for m := range allowedMethods {
		out = append(out, m)
	}
	sort.Strings(out)
	return out
}

// ---- authenticated tenant context ----

type tenantKey struct{}

// WithTenant attaches the authenticated tenant (set by the API auth middleware).
func WithTenant(ctx context.Context, tenant string) context.Context {
	return context.WithValue(ctx, tenantKey{}, strings.TrimSpace(tenant))
}

// TenantFrom returns the authenticated tenant, if present.
func TenantFrom(ctx context.Context) (string, bool) {
	v, ok := ctx.Value(tenantKey{}).(string)
	return v, ok && v != ""
}

// ---- denial counters (structured, dependency-free) ----

var stats struct {
	sync.Mutex
	byReason map[string]int
}

func init() { stats.byReason = map[string]int{} }

func deny(reason string) {
	stats.Lock()
	stats.byReason[reason]++
	stats.Unlock()
	log.Printf("objpolicy: deny reason=%s", reason)
}

// Stats returns a copy of denial counts by reason.
func Stats() map[string]int {
	stats.Lock()
	defer stats.Unlock()
	out := make(map[string]int, len(stats.byReason))
	for k, v := range stats.byReason {
		out[k] = v
	}
	return out
}

// ResetStats clears the counters (tests / process restart).
func ResetStats() {
	stats.Lock()
	stats.byReason = map[string]int{}
	stats.Unlock()
}

// Mint issues a signed URL for key within the authenticated tenant.
func Mint(ctx context.Context, store datastore.ObjectStore, key, method string, ttl time.Duration) (string, error) {
	tenant, ok := TenantFrom(ctx)
	if !ok {
		deny("TENANT_CONTEXT")
		return "", ErrTenantCtx
	}
	m := strings.ToUpper(strings.TrimSpace(method))
	if !allowedMethods[m] {
		deny("METHOD")
		return "", fmt.Errorf("%w: %q", ErrMethod, method)
	}
	if ttl == 0 {
		ttl = DefaultTTL
	}
	if ttl < MinTTL || ttl > MaxTTL {
		deny("TTL")
		return "", fmt.Errorf("%w: %s (min %s, max %s)", ErrTTL, ttl, MinTTL, MaxTTL)
	}
	prefix, k := cleanPath(tenant), cleanPath(key)
	if prefix == "" || !strings.HasPrefix(k, prefix+"/") {
		deny("TENANT_SCOPE")
		return "", fmt.Errorf("%w: %q not under %q", ErrTenantScope, key, tenant)
	}
	if !store.Capabilities().SignedURLs {
		deny("UNSUPPORTED")
		return "", &datastore.UnsupportedError{Provider: fmt.Sprintf("%T", store), Capability: "signed-url"}
	}
	return store.SignedURL(ctx, k, m, ttl)
}

// cleanPath normalizes a key/prefix and refuses traversal (".." / absolute escapes).
func cleanPath(p string) string {
	c := path.Clean("/" + strings.TrimSpace(p))
	if c == "/" || c == "/.." || strings.HasPrefix(c, "/../") || strings.Contains(c, "/../") {
		return ""
	}
	return strings.TrimPrefix(c, "/")
}
