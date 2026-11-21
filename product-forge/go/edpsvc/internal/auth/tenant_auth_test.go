package auth

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestTenantAuth_Admin(t *testing.T) {
	auth := NewAuthenticator("admin-secret-token", "", "", "")

	req := httptest.NewRequest(http.MethodGet, "/backlog", nil)
	req.Header.Set("Authorization", "Bearer admin-secret-token")

	p, err := auth.Authenticate(req)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !p.IsAdmin {
		t.Errorf("expected IsAdmin to be true")
	}
	if p.ID != "admin" {
		t.Errorf("expected ID 'admin', got %q", p.ID)
	}
	if p.Tenant != "" {
		t.Errorf("expected empty Tenant for admin, got %q", p.Tenant)
	}
}

func TestTenantAuth_StaticTenantTokens(t *testing.T) {
	raw := `{"token_alpha": "tenant_a", "token_beta": "tenant_b"}`
	auth := NewAuthenticator("admin-tok", raw, "", "")

	// Test tenant_a
	reqA := httptest.NewRequest(http.MethodGet, "/backlog", nil)
	reqA.Header.Set("Authorization", "Bearer token_alpha")
	pA, err := auth.Authenticate(reqA)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if pA.IsAdmin {
		t.Errorf("expected non-admin")
	}
	if pA.Tenant != "tenant_a" {
		t.Errorf("expected tenant 'tenant_a', got %q", pA.Tenant)
	}

	// Test tenant_b
	reqB := httptest.NewRequest(http.MethodGet, "/backlog", nil)
	reqB.Header.Set("Authorization", "Bearer token_beta")
	pB, err := auth.Authenticate(reqB)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if pB.Tenant != "tenant_b" {
		t.Errorf("expected tenant 'tenant_b', got %q", pB.Tenant)
	}

	// Semicolon formatted string
	rawKV := "tok1=t1;tok2=t2"
	authKV := NewAuthenticator("", rawKV, "", "")
	reqKV := httptest.NewRequest(http.MethodGet, "/backlog", nil)
	reqKV.Header.Set("Authorization", "Bearer tok2")
	pKV, err := authKV.Authenticate(reqKV)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if pKV.Tenant != "t2" {
		t.Errorf("expected tenant 't2', got %q", pKV.Tenant)
	}
}

func TestGatewayClaims_Valid(t *testing.T) {
	secret := []byte("trusted-gateway-hmac-secret-32-bytes")
	auth := NewAuthenticator("admin-tok", "", string(secret), "")

	now := time.Now().Unix()
	claims := GatewayClaims{
		Tenant:    "acme_corp",
		Principal: "user_42",
		Subject:   "user_42",
		ExpiresAt: now + 3600,
		IssuedAt:  now - 10,
		Issuer:    "trusted-gateway",
	}

	token, err := SignGatewayClaim(claims, secret)
	if err != nil {
		t.Fatalf("SignGatewayClaim error: %v", err)
	}

	// Test as Bearer token
	req := httptest.NewRequest(http.MethodGet, "/backlog", nil)
	req.Header.Set("Authorization", "Bearer "+token)

	p, err := auth.Authenticate(req)
	if err != nil {
		t.Fatalf("Authenticate error: %v", err)
	}
	if p.Tenant != "acme_corp" {
		t.Errorf("expected tenant 'acme_corp', got %q", p.Tenant)
	}
	if p.ID != "user_42" {
		t.Errorf("expected principal ID 'user_42', got %q", p.ID)
	}

	// Test via X-Tenant-Claim header
	reqHdr := httptest.NewRequest(http.MethodGet, "/backlog", nil)
	reqHdr.Header.Set("X-Tenant-Claim", token)
	pHdr, err := auth.Authenticate(reqHdr)
	if err != nil {
		t.Fatalf("Authenticate header error: %v", err)
	}
	if pHdr.Tenant != "acme_corp" {
		t.Errorf("expected tenant 'acme_corp', got %q", pHdr.Tenant)
	}
}

func TestGatewayClaims_ForgedAndTampered(t *testing.T) {
	secret := []byte("trusted-gateway-hmac-secret-32-bytes")
	wrongSecret := []byte("attacker-forged-secret-32-bytes-long")
	auth := NewAuthenticator("", "", string(secret), "")

	now := time.Now().Unix()
	claims := GatewayClaims{
		Tenant:    "acme_corp",
		ExpiresAt: now + 3600,
	}

	// Signed with wrong secret
	forgedToken, err := SignGatewayClaim(claims, wrongSecret)
	if err != nil {
		t.Fatalf("SignGatewayClaim error: %v", err)
	}

	req := httptest.NewRequest(http.MethodGet, "/backlog", nil)
	req.Header.Set("Authorization", "Bearer "+forgedToken)

	_, err = auth.Authenticate(req)
	if err == nil {
		t.Fatalf("expected error for forged signature, got nil")
	}

	// Tampered payload
	token, _ := SignGatewayClaim(claims, secret)
	tamperedToken := token[:len(token)-5] + "XXXXX"
	reqTampered := httptest.NewRequest(http.MethodGet, "/backlog", nil)
	reqTampered.Header.Set("Authorization", "Bearer "+tamperedToken)
	_, err = auth.Authenticate(reqTampered)
	if err == nil {
		t.Fatalf("expected error for tampered token, got nil")
	}
}

func TestGatewayClaims_Expired(t *testing.T) {
	secret := []byte("trusted-gateway-hmac-secret-32-bytes")
	auth := NewAuthenticator("", "", string(secret), "")

	past := time.Now().Unix() - 60
	claims := GatewayClaims{
		Tenant:    "acme_corp",
		ExpiresAt: past,
	}

	expiredToken, err := SignGatewayClaim(claims, secret)
	if err != nil {
		t.Fatalf("SignGatewayClaim error: %v", err)
	}

	req := httptest.NewRequest(http.MethodGet, "/backlog", nil)
	req.Header.Set("Authorization", "Bearer "+expiredToken)

	_, err = auth.Authenticate(req)
	if err != ErrExpiredCredential {
		t.Fatalf("expected ErrExpiredCredential, got %v", err)
	}
}

func TestGatewayClaims_ClockSkewAndPremature(t *testing.T) {
	secret := []byte("trusted-gateway-hmac-secret-32-bytes")
	auth := NewAuthenticator("", "", string(secret), "")

	now := time.Now().Unix()

	// 1. Within 30s clock skew should be accepted
	claimsAllowed := GatewayClaims{
		Tenant:    "tenant_skew",
		ExpiresAt: now + 300,
		IssuedAt:  now + 20, // 20s in future, allowed (<30s)
	}
	tokenAllowed, _ := SignGatewayClaim(claimsAllowed, secret)
	req1 := httptest.NewRequest(http.MethodGet, "/backlog", nil)
	req1.Header.Set("Authorization", "Bearer "+tokenAllowed)
	p, err := auth.Authenticate(req1)
	if err != nil {
		t.Fatalf("expected 20s future skew to be allowed, got error: %v", err)
	}
	if p.Tenant != "tenant_skew" {
		t.Errorf("expected tenant_skew, got %q", p.Tenant)
	}

	// 2. Far in future (> 30s) rejected
	claimsFuture := GatewayClaims{
		Tenant:    "tenant_skew",
		ExpiresAt: now + 300,
		IssuedAt:  now + 120, // 2 minutes in future
	}
	tokenFuture, _ := SignGatewayClaim(claimsFuture, secret)
	req2 := httptest.NewRequest(http.MethodGet, "/backlog", nil)
	req2.Header.Set("Authorization", "Bearer "+tokenFuture)
	_, err = auth.Authenticate(req2)
	if err != ErrPrematureCredential {
		t.Fatalf("expected ErrPrematureCredential, got %v", err)
	}
}

func TestGatewayClaims_SecretRotation(t *testing.T) {
	primarySecret := []byte("new-primary-secret-32-bytes-long")
	oldSecret := []byte("old-retiring-secret-32-bytes-long")

	auth := NewAuthenticator("", "", string(primarySecret), string(oldSecret))

	now := time.Now().Unix()
	claims := GatewayClaims{
		Tenant:    "acme_corp",
		ExpiresAt: now + 3600,
	}

	// Token signed with old secret should succeed
	oldToken, err := SignGatewayClaim(claims, oldSecret)
	if err != nil {
		t.Fatalf("SignGatewayClaim error: %v", err)
	}
	reqOld := httptest.NewRequest(http.MethodGet, "/backlog", nil)
	reqOld.Header.Set("Authorization", "Bearer "+oldToken)
	pOld, err := auth.Authenticate(reqOld)
	if err != nil {
		t.Fatalf("expected old secret token to authenticate during rotation, got: %v", err)
	}
	if pOld.Tenant != "acme_corp" {
		t.Errorf("expected acme_corp, got %q", pOld.Tenant)
	}

	// Token signed with new primary secret should also succeed
	newToken, err := SignGatewayClaim(claims, primarySecret)
	if err != nil {
		t.Fatalf("SignGatewayClaim error: %v", err)
	}
	reqNew := httptest.NewRequest(http.MethodGet, "/backlog", nil)
	reqNew.Header.Set("Authorization", "Bearer "+newToken)
	pNew, err := auth.Authenticate(reqNew)
	if err != nil {
		t.Fatalf("expected new secret token to authenticate, got: %v", err)
	}
	if pNew.Tenant != "acme_corp" {
		t.Errorf("expected acme_corp, got %q", pNew.Tenant)
	}
}

func TestContextHelpers(t *testing.T) {
	ctx := context.Background()
	if _, ok := PrincipalFrom(ctx); ok {
		t.Errorf("expected no principal on empty context")
	}
	if _, ok := TenantFrom(ctx); ok {
		t.Errorf("expected no tenant on empty context")
	}

	p := &Principal{ID: "usr_1", Tenant: "t_alpha"}
	ctxWithP := WithPrincipal(ctx, p)

	retrievedP, ok := PrincipalFrom(ctxWithP)
	if !ok || retrievedP.ID != "usr_1" {
		t.Errorf("failed to retrieve principal")
	}

	tenant, ok := TenantFrom(ctxWithP)
	if !ok || tenant != "t_alpha" {
		t.Errorf("expected tenant 't_alpha', got %q", tenant)
	}
}
