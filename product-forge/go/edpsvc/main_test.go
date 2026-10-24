package main

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"

	"productforge/edpsvc/internal/limits"
	"productforge/store"
)

func testServer(t *testing.T) *server {
	t.Helper()
	cfg := limits.DefaultConfig()
	m := limits.NewMetrics()
	guard := limits.NewRoleGuard()
	guard.Set(limits.Role{Name: "pf_app"})
	return &server{admin: "test-token", cfg: cfg, quota: limits.NewQuota(cfg, nil, m),
		metrics: m, role: guard}
}

func TestHealthAndMetrics(t *testing.T) {
	s := testServer(t)
	h := s.buildMux()
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, httptest.NewRequest(http.MethodGet, "/health", nil))
	if rr.Code != http.StatusOK {
		t.Fatalf("health %d", rr.Code)
	}
	s.metrics.Inc("edp_test_total")
	rr = httptest.NewRecorder()
	h.ServeHTTP(rr, httptest.NewRequest(http.MethodGet, "/metrics", nil))
	if rr.Code != http.StatusOK || !strings.Contains(rr.Body.String(), "edp_") {
		t.Fatalf("metrics %d %q", rr.Code, rr.Body.String())
	}
}

func TestAdminAuthUsesStructuredEnvelope(t *testing.T) {
	s := testServer(t)
	h := s.buildMux()
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, httptest.NewRequest(http.MethodGet, "/admin/limits", nil))
	if rr.Code != http.StatusUnauthorized {
		t.Fatalf("want 401, got %d", rr.Code)
	}
	var env limits.ErrorEnvelope
	if err := json.Unmarshal(rr.Body.Bytes(), &env); err != nil || env.Error.Code != "UNAUTHENTICATED" {
		t.Fatalf("envelope %q err=%v", rr.Body.String(), err)
	}
	rr = httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/admin/limits", nil)
	req.Header.Set("Authorization", "Bearer test-token")
	h.ServeHTTP(rr, req)
	if rr.Code != http.StatusOK {
		t.Fatalf("admin/limits %d %q", rr.Code, rr.Body.String())
	}
	if !strings.Contains(rr.Body.String(), "\"max_body_bytes\"") {
		t.Fatalf("limits body: %s", rr.Body.String())
	}
}

func TestMuxQuotaViaChain(t *testing.T) {
	s := testServer(t)
	s.cfg.TenantRPM = 1
	s.quota = limits.NewQuota(s.cfg, func() time.Time { return time.Unix(1, 0) }, s.metrics)
	h := limits.Chain(s.buildMux(), s.cfg, s.quota, s.metrics, s.role.OK)
	do := func() *httptest.ResponseRecorder {
		rr := httptest.NewRecorder()
		req := httptest.NewRequest(http.MethodGet, "/admin/limits", nil)
		req.Header.Set("Authorization", "Bearer test-token")
		req.Header.Set("X-Tenant-Id", "t1")
		h.ServeHTTP(rr, req)
		return rr
	}
	if rr := do(); rr.Code != http.StatusOK {
		t.Fatalf("first %d", rr.Code)
	}
	if rr := do(); rr.Code != http.StatusTooManyRequests || rr.Header().Get("Retry-After") == "" {
		t.Fatalf("second want 429+Retry-After, got %d", rr.Code)
	}
}

func TestReadyWithDB(t *testing.T) {
	dsn := os.Getenv("PF_RUNTIME_DSN")
	if dsn == "" {
		t.Skip("set PF_RUNTIME_DSN to run the ready probe")
	}
	st, err := store.Open(context.Background(), dsn)
	if err != nil {
		t.Fatal(err)
	}
	defer st.Close()
	s := testServer(t)
	s.st = st
	rr := httptest.NewRecorder()
	s.buildMux().ServeHTTP(rr, httptest.NewRequest(http.MethodGet, "/ready", nil))
	if rr.Code != http.StatusOK {
		t.Fatalf("ready %d %q", rr.Code, rr.Body.String())
	}
}

func TestChunkedOversizeReturns413(t *testing.T) {
	s := testServer(t)
	s.cfg.MaxBodyBytes = 10
	h := limits.Chain(s.buildMux(), s.cfg, s.quota, s.metrics, s.role.OK)
	rr := httptest.NewRecorder()
	body := `{"tenant":"t","action":"a","pad":"` + strings.Repeat("x", 200) + `"}`
	req := httptest.NewRequest(http.MethodPost, "/audit", strings.NewReader(body))
	req.ContentLength = -1 // chunked
	req.Header.Set("Authorization", "Bearer test-token")
	h.ServeHTTP(rr, req)
	if rr.Code != http.StatusRequestEntityTooLarge {
		t.Fatalf("want 413, got %d %q", rr.Code, rr.Body.String())
	}
	if !strings.Contains(rr.Body.String(), `"code":"PAYLOAD_TOO_LARGE"`) {
		t.Fatalf("want PAYLOAD_TOO_LARGE envelope, got %s", rr.Body.String())
	}
}

func TestMuxLevelTimeoutReturns504(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/slow", func(w http.ResponseWriter, r *http.Request) {
		<-r.Context().Done()
		limits.WriteHandlerError(w, r, r.Context().Err())
	})
	cfg := limits.DefaultConfig()
	cfg.RequestTimeout = 20 * time.Millisecond
	h := limits.Chain(mux, cfg, nil, limits.NewMetrics(), nil)
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, httptest.NewRequest(http.MethodGet, "/slow", nil))
	if rr.Code != http.StatusGatewayTimeout {
		t.Fatalf("want 504, got %d", rr.Code)
	}
}
