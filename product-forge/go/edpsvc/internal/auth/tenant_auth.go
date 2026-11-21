package auth

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"net/http"
	"strings"
	"time"
)

var (
	ErrUnauthenticated     = errors.New("unauthenticated: missing credential")
	ErrInvalidCredential   = errors.New("unauthenticated: invalid credential")
	ErrExpiredCredential   = errors.New("unauthenticated: expired credential")
	ErrPrematureCredential = errors.New("unauthenticated: credential not yet valid")
	ErrInvalidClaims       = errors.New("unauthenticated: invalid tenant claim")
)

type ctxKey string

const principalCtxKey ctxKey = "edp-principal"

// Principal represents the authenticated caller identity and tenant scope.
type Principal struct {
	ID        string    `json:"id"`
	Tenant    string    `json:"tenant"`
	IsAdmin   bool      `json:"is_admin"`
	ExpiresAt time.Time `json:"expires_at,omitempty"`
}

// WithPrincipal attaches an authenticated Principal to the context.
func WithPrincipal(ctx context.Context, p *Principal) context.Context {
	return context.WithValue(ctx, principalCtxKey, p)
}

// PrincipalFrom retrieves the authenticated Principal from the context.
func PrincipalFrom(ctx context.Context) (*Principal, bool) {
	if ctx == nil {
		return nil, false
	}
	p, ok := ctx.Value(principalCtxKey).(*Principal)
	return p, ok && p != nil
}

// TenantFrom retrieves the authenticated tenant ID from the context.
func TenantFrom(ctx context.Context) (string, bool) {
	p, ok := PrincipalFrom(ctx)
	if !ok || p == nil || p.Tenant == "" {
		return "", false
	}
	return p.Tenant, true
}

// GatewayClaims represents claims inside a signed trusted-gateway token.
type GatewayClaims struct {
	Tenant    string `json:"tenant"`
	Subject   string `json:"sub,omitempty"`
	Principal string `json:"principal,omitempty"`
	ExpiresAt int64  `json:"exp,omitempty"`
	IssuedAt  int64  `json:"iat,omitempty"`
	Issuer    string `json:"iss,omitempty"`
}

// Authenticator verifies inbound credentials across admin, tenant tokens, and trusted gateway claims.
type Authenticator struct {
	adminHash         [32]byte
	hasAdmin          bool
	tenantTokenHashes map[[32]byte]string
	gatewaySecret     []byte
	gatewaySecretOld  []byte
}

// NewAuthenticator constructs an Authenticator with admin token, tenant token mapping, and gateway secrets.
func NewAuthenticator(adminToken string, tenantTokensRaw string, gatewaySecret, gatewaySecretOld string) *Authenticator {
	a := &Authenticator{
		tenantTokenHashes: make(map[[32]byte]string),
	}
	if strings.TrimSpace(adminToken) != "" {
		a.adminHash = sha256.Sum256([]byte(strings.TrimSpace(adminToken)))
		a.hasAdmin = true
	}
	if strings.TrimSpace(gatewaySecret) != "" {
		a.gatewaySecret = []byte(strings.TrimSpace(gatewaySecret))
	}
	if strings.TrimSpace(gatewaySecretOld) != "" {
		a.gatewaySecretOld = []byte(strings.TrimSpace(gatewaySecretOld))
	}
	a.parseTenantTokens(tenantTokensRaw)
	return a
}

func (a *Authenticator) parseTenantTokens(raw string) {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return
	}
	// Try parsing as JSON map: {"token1": "tenant1", "hash1": "tenant2"}
	if strings.HasPrefix(raw, "{") {
		var m map[string]string
		if err := json.Unmarshal([]byte(raw), &m); err == nil {
			for tok, tenant := range m {
				t := strings.TrimSpace(tenant)
				if t == "" {
					continue
				}
				tok = strings.TrimSpace(tok)
				// If 64 hex chars, assume it might already be a sha256 hex digest
				if len(tok) == 64 {
					if h, err := hex.DecodeString(tok); err == nil && len(h) == 32 {
						var hArr [32]byte
						copy(hArr[:], h)
						a.tenantTokenHashes[hArr] = t
					}
				}
				// Also index the raw token hash
				a.tenantTokenHashes[sha256.Sum256([]byte(tok))] = t
			}
			return
		}
	}
	// Fall back to semicolon/comma separated key-value pairs: token1=tenant1;token2=tenant2
	items := strings.FieldsFunc(raw, func(r rune) bool { return r == ';' || r == ',' })
	for _, it := range items {
		it = strings.TrimSpace(it)
		if it == "" {
			continue
		}
		parts := strings.SplitN(it, "=", 2)
		if len(parts) == 2 {
			tok := strings.TrimSpace(parts[0])
			tenant := strings.TrimSpace(parts[1])
			if tok != "" && tenant != "" {
				a.tenantTokenHashes[sha256.Sum256([]byte(tok))] = tenant
			}
		}
	}
}

// Authenticate extracts credentials from request and returns an authenticated Principal.
func (a *Authenticator) Authenticate(r *http.Request) (*Principal, error) {
	token := ""
	authHeader := r.Header.Get("Authorization")
	if strings.HasPrefix(authHeader, "Bearer ") {
		token = strings.TrimSpace(strings.TrimPrefix(authHeader, "Bearer "))
	} else if claimHdr := r.Header.Get("X-Tenant-Claim"); strings.TrimSpace(claimHdr) != "" {
		token = strings.TrimSpace(claimHdr)
	}

	if token == "" {
		return nil, ErrUnauthenticated
	}

	th := sha256.Sum256([]byte(token))

	// 1. Check admin token
	if a.hasAdmin && subtle.ConstantTimeCompare(th[:], a.adminHash[:]) == 1 {
		return &Principal{
			ID:      "admin",
			Tenant:  "",
			IsAdmin: true,
		}, nil
	}

	// 2. Check static tenant tokens
	if tenant, ok := a.tenantTokenHashes[th]; ok && tenant != "" {
		return &Principal{
			ID:      "token:" + tenant,
			Tenant:  tenant,
			IsAdmin: false,
		}, nil
	}

	// 3. Check trusted gateway signed claim (JWT format)
	if strings.Count(token, ".") == 2 && (len(a.gatewaySecret) > 0 || len(a.gatewaySecretOld) > 0) {
		p, err := a.verifyGatewayClaim(token)
		if err == nil {
			return p, nil
		}
		return nil, err
	}

	return nil, ErrInvalidCredential
}

func (a *Authenticator) verifyGatewayClaim(token string) (*Principal, error) {
	parts := strings.Split(token, ".")
	if len(parts) != 3 {
		return nil, ErrInvalidCredential
	}
	headerB64, payloadB64, sigB64 := parts[0], parts[1], parts[2]

	sig, err := decodeBase64URL(sigB64)
	if err != nil {
		return nil, ErrInvalidCredential
	}

	signedContent := headerB64 + "." + payloadB64
	valid := false

	if len(a.gatewaySecret) > 0 {
		h := hmac.New(sha256.New, a.gatewaySecret)
		h.Write([]byte(signedContent))
		expected := h.Sum(nil)
		if subtle.ConstantTimeCompare(sig, expected) == 1 {
			valid = true
		}
	}
	if !valid && len(a.gatewaySecretOld) > 0 {
		h := hmac.New(sha256.New, a.gatewaySecretOld)
		h.Write([]byte(signedContent))
		expected := h.Sum(nil)
		if subtle.ConstantTimeCompare(sig, expected) == 1 {
			valid = true
		}
	}
	if !valid {
		return nil, ErrInvalidCredential
	}

	payloadJSON, err := decodeBase64URL(payloadB64)
	if err != nil {
		return nil, ErrInvalidCredential
	}

	var claims GatewayClaims
	if err := json.Unmarshal(payloadJSON, &claims); err != nil {
		return nil, ErrInvalidCredential
	}

	claims.Tenant = strings.TrimSpace(claims.Tenant)
	if claims.Tenant == "" {
		return nil, ErrInvalidClaims
	}

	now := time.Now().Unix()
	// Check expiration: exp must be in the future
	if claims.ExpiresAt > 0 && now > claims.ExpiresAt {
		return nil, ErrExpiredCredential
	}
	// Check clock skew tolerance: allow up to 30 seconds into the future for issued_at
	if claims.IssuedAt > 0 && now < claims.IssuedAt-30 {
		return nil, ErrPrematureCredential
	}

	principalID := strings.TrimSpace(claims.Principal)
	if principalID == "" {
		principalID = strings.TrimSpace(claims.Subject)
	}
	if principalID == "" {
		principalID = "gateway:" + claims.Tenant
	}

	var expTime time.Time
	if claims.ExpiresAt > 0 {
		expTime = time.Unix(claims.ExpiresAt, 0)
	}

	return &Principal{
		ID:        principalID,
		Tenant:    claims.Tenant,
		IsAdmin:   false,
		ExpiresAt: expTime,
	}, nil
}

func decodeBase64URL(s string) ([]byte, error) {
	// RFC 7515 Section 2 specifies Base64url encoding without padding.
	if b, err := base64.RawURLEncoding.DecodeString(s); err == nil {
		return b, nil
	}
	// Fallback to padded Base64url if caller supplied padding.
	return base64.URLEncoding.DecodeString(s)
}

// SignGatewayClaim generates a signed JWT-formatted claim token for trusted gateway clients.
func SignGatewayClaim(claims GatewayClaims, secret []byte) (string, error) {
	headerJSON := []byte(`{"alg":"HS256","typ":"JWT"}`)
	headerB64 := base64.RawURLEncoding.EncodeToString(headerJSON)

	payloadJSON, err := json.Marshal(claims)
	if err != nil {
		return "", err
	}
	payloadB64 := base64.RawURLEncoding.EncodeToString(payloadJSON)

	signedContent := headerB64 + "." + payloadB64
	h := hmac.New(sha256.New, secret)
	h.Write([]byte(signedContent))
	sig := h.Sum(nil)
	sigB64 := base64.RawURLEncoding.EncodeToString(sig)

	return signedContent + "." + sigB64, nil
}
