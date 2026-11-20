package eventtransport

import (
	"os"
	"strings"
)

// ResolveHMACKey resolves a subscription auth_ref ("env:NAME") or the env default.
func ResolveHMACKey(authRef string) (string, bool) {
	ref := strings.TrimSpace(authRef)
	if strings.HasPrefix(ref, "env:") {
		v := os.Getenv(strings.TrimPrefix(ref, "env:"))
		return v, v != ""
	}
	if ref != "" {
		return ref, true
	}
	v := os.Getenv("PF_WEBHOOK_HMAC_KEY")
	return v, v != ""
}
