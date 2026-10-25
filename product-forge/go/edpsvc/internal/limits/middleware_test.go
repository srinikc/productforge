package limits

import (
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func testChain(cfg Config, q *Quota, m *Metrics, roleOK func() bool, h http.Handler) http.Handler {
	return Chain(h, cfg, q, m, roleOK)
}

func okHandler() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(http.StatusOK) })
}

func TestRequestIDPropagation(t *testing.T) {
	h := testChain(DefaultConfig(), nil, NewMetrics(), nil, okHandler())
	rr := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	req.Header.Set("X-Request-ID", "client-id")
	h.ServeHTTP(rr, req)
	if rr.Header().Get("X-Request-ID") != "client-id" {
		t.Fatalf("want propagated id, got %q", rr.Header().Get("X-Request-ID"))
	}
	rr = httptest.NewRecorder()
	req = httptest.NewRequest(http.MethodGet, "/health", nil)
	req.Header.Set("X-Request-ID", "bad id|")
	h.ServeHTTP(rr, req)
	if id := rr.Header().Get("X-Request-ID"); id == "bad id|" || id == "" {
		t.Fatalf("invalid id must be replaced, got %q", id)
	}
}

func TestBodyLimitContentLength(t *testing.T) {
	cfg := DefaultConfig()
	cfg.MaxBodyBytes = 10
	h := testChain(cfg, nil, NewMetrics(), nil, okHandler())
	rr := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/x", strings.NewReader(strings.Repeat("x", 100)))
	req.ContentLength = 100
	h.ServeHTTP(rr, req)
	if rr.Code != http.StatusRequestEntityTooLarge {
		t.Fatalf("want 413, got %d", rr.Code)
	}
}

func TestBodyLimitChunkedRead(t *testing.T) {
	cfg := DefaultConfig()
	cfg.MaxBodyBytes = 10
	h := testChain(cfg, nil, NewMetrics(), nil, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if _, err := io.Copy(io.Discard, r.Body); err != nil {
			WriteHandlerError(w, r, err)
			return
		}
		w.WriteHeader(http.StatusOK)
	}))
	rr := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/x", strings.NewReader(strings.Repeat("x", 100)))
	req.ContentLength = -1
	h.ServeHTTP(rr, req)
	if rr.Code != http.StatusRequestEntityTooLarge {
		t.Fatalf("want 413, got %d", rr.Code)
	}
}

func TestTimeoutWrites504(t *testing.T) {
	cfg := DefaultConfig()
	cfg.RequestTimeout = 20 * time.Millisecond
	h := testChain(cfg, nil, NewMetrics(), nil, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		select {
		case <-r.Context().Done():
			WriteHandlerError(w, r, r.Context().Err())
		case <-time.After(time.Second):
			w.WriteHeader(http.StatusOK)
		}
	}))
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, httptest.NewRequest(http.MethodGet, "/x", nil))
	if rr.Code != http.StatusGatewayTimeout {
		t.Fatalf("want 504, got %d", rr.Code)
	}
}

func TestQuota429AndHealthExempt(t *testing.T) {
	cfg := DefaultConfig()
	cfg.TenantRPM = 1
	m := NewMetrics()
	q := NewQuota(cfg, func() time.Time { return time.Unix(1, 0) }, m)
	h := testChain(cfg, q, m, nil, okHandler())

	rr := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/x", nil)
	req.Header.Set("X-Tenant-Id", "t1")
	h.ServeHTTP(rr, req)
	if rr.Code != http.StatusOK {
		t.Fatalf("first want 200, got %d", rr.Code)
	}
	rr = httptest.NewRecorder()
	req = httptest.NewRequest(http.MethodGet, "/x", nil)
	req.Header.Set("X-Tenant-Id", "t1")
	h.ServeHTTP(rr, req)
	if rr.Code != http.StatusTooManyRequests || rr.Header().Get("Retry-After") == "" {
		t.Fatalf("want 429+Retry-After, got %d %q", rr.Code, rr.Header().Get("Retry-After"))
	}
	rr = httptest.NewRecorder()
	req = httptest.NewRequest(http.MethodGet, "/health", nil)
	req.Header.Set("X-Tenant-Id", "t1")
	h.ServeHTTP(rr, req)
	if rr.Code != http.StatusOK {
		t.Fatalf("health must be exempt, got %d", rr.Code)
	}
}

func TestTenantHeaderQueryMismatch(t *testing.T) {
	cfg := DefaultConfig()
	h := testChain(cfg, NewQuota(cfg, nil, NewMetrics()), NewMetrics(), nil, okHandler())
	rr := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/x?tenant=b", nil)
	req.Header.Set("X-Tenant-Id", "a")
	h.ServeHTTP(rr, req)
	if rr.Code != http.StatusBadRequest {
		t.Fatalf("want 400 mismatch, got %d", rr.Code)
	}
}

func TestPanicIs500AndReleasesSlot(t *testing.T) {
	cfg := DefaultConfig()
	cfg.GlobalConcurrency = 1
	cfg.TenantConcurrency = 1
	count := 0
	h := testChain(cfg, NewQuota(cfg, nil, NewMetrics()), NewMetrics(), nil,
		http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			count++
			if count == 1 {
				panic("boom")
			}
			w.WriteHeader(http.StatusOK)
		}))
	rr := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/x", nil)
	req.Header.Set("X-Tenant-Id", "t")
	h.ServeHTTP(rr, req)
	if rr.Code != http.StatusInternalServerError {
		t.Fatalf("want 500, got %d", rr.Code)
	}
	rr = httptest.NewRecorder()
	req = httptest.NewRequest(http.MethodGet, "/x", nil)
	req.Header.Set("X-Tenant-Id", "t")
	h.ServeHTTP(rr, req)
	if rr.Code != http.StatusOK {
		t.Fatalf("slot must be released after panic, got %d", rr.Code)
	}
}

func TestRoleGate503(t *testing.T) {
	cfg := DefaultConfig()
	h := testChain(cfg, nil, NewMetrics(), func() bool { return false }, okHandler())
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, httptest.NewRequest(http.MethodGet, "/x", nil))
	if rr.Code != http.StatusServiceUnavailable {
		t.Fatalf("want 503, got %d", rr.Code)
	}
	rr = httptest.NewRecorder()
	h.ServeHTTP(rr, httptest.NewRequest(http.MethodGet, "/health", nil))
	if rr.Code != http.StatusOK {
		t.Fatalf("health must bypass the role gate, got %d", rr.Code)
	}
}

func TestMetricsFromChain(t *testing.T) {
	m := NewMetrics()
	h := testChain(DefaultConfig(), nil, m, nil, okHandler())
	h.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest(http.MethodGet, "/x", nil))
	var b strings.Builder
	m.Write(&b)
	out := b.String()
	if !strings.Contains(out, `edp_http_requests_total{class="json",status="200"}`) {
		t.Fatalf("missing request counter:\n%s", out)
	}
	if !strings.Contains(out, "edp_http_request_duration_seconds_count") {
		t.Fatalf("missing histogram:\n%s", out)
	}
}

func TestEnforceKillSwitchDisablesLimits(t *testing.T) {
	cfg := DefaultConfig()
	cfg.Enforce = false
	cfg.MaxBodyBytes = 1
	cfg.RequestTimeout = time.Millisecond
	h := testChain(cfg, NewQuota(cfg, nil, NewMetrics()), NewMetrics(), nil,
		http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			time.Sleep(5 * time.Millisecond)
			_, _ = io.Copy(io.Discard, r.Body)
			w.WriteHeader(http.StatusOK)
		}))
	rr := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/x", strings.NewReader(strings.Repeat("x", 100)))
	req.ContentLength = 100
	h.ServeHTTP(rr, req)
	if rr.Code != http.StatusOK {
		t.Fatalf("kill switch must disable body/timeout/quota, got %d", rr.Code)
	}
}

func TestEnvelopeFallback404And405(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /ok", func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(http.StatusOK) })
	h := Chain(EnvelopeFallback(mux), DefaultConfig(), nil, NewMetrics(), nil)
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, httptest.NewRequest(http.MethodGet, "/nope", nil))
	if rr.Code != http.StatusNotFound || !strings.Contains(rr.Body.String(), `"code":"NOT_FOUND"`) {
		t.Fatalf("404 not enveloped: %d %s", rr.Code, rr.Body.String())
	}
	rr = httptest.NewRecorder()
	h.ServeHTTP(rr, httptest.NewRequest(http.MethodPost, "/ok", nil))
	if rr.Code != http.StatusMethodNotAllowed || !strings.Contains(rr.Body.String(), `"code":"METHOD_NOT_ALLOWED"`) {
		t.Fatalf("405 not enveloped: %d %s", rr.Code, rr.Body.String())
	}
}

func TestQuotaAttributesJSONBodyTenant(t *testing.T) {
	cfg := DefaultConfig()
	cfg.TenantRPM = 1
	q := NewQuota(cfg, func() time.Time { return time.Unix(1, 0) }, NewMetrics())
	h := testChain(cfg, q, NewMetrics(), nil, okHandler())
	do := func() int {
		rr := httptest.NewRecorder()
		req := httptest.NewRequest(http.MethodPost, "/x", strings.NewReader(`{"tenant":"t1","action":"a"}`))
		req.Header.Set("Content-Type", "application/json")
		h.ServeHTTP(rr, req)
		return rr.Code
	}
	if code := do(); code != http.StatusOK {
		t.Fatalf("first want 200, got %d", code)
	}
	if code := do(); code != http.StatusTooManyRequests {
		t.Fatalf("second want 429 from the body tenant, got %d", code)
	}
}

func TestAuthMiddlewareReturns401(t *testing.T) {
	cfg := DefaultConfig()
	auth := func(w http.ResponseWriter, r *http.Request) bool {
		WriteError(w, r, http.StatusUnauthorized, "no token")
		return false
	}
	h := Chain(okHandler(), cfg, NewQuota(cfg, nil, NewMetrics()), NewMetrics(), nil, auth)
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, httptest.NewRequest(http.MethodGet, "/admin/limits", nil))
	if rr.Code != http.StatusUnauthorized {
		t.Fatalf("want 401 before quota, got %d", rr.Code)
	}
}

func TestUnauthenticated401ConsumesGlobalQuota(t *testing.T) {
	cfg := DefaultConfig()
	cfg.GlobalRPM = 1
	cfg.TenantRPM = 100
	auth := func(w http.ResponseWriter, r *http.Request) bool {
		WriteError(w, r, http.StatusUnauthorized, "no token")
		return false
	}
	h := Chain(okHandler(), cfg, NewQuota(cfg, func() time.Time { return time.Unix(1, 0) }, NewMetrics()),
		NewMetrics(), nil, auth)
	if rr := httptest.NewRecorder(); func() int { h.ServeHTTP(rr, httptest.NewRequest(http.MethodGet, "/admin/x", nil)); return rr.Code }() != http.StatusUnauthorized {
		t.Fatalf("first want 401")
	}
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, httptest.NewRequest(http.MethodGet, "/admin/x", nil))
	if rr.Code != http.StatusTooManyRequests {
		t.Fatalf("second want 429 from the pre-auth global bucket, got %d", rr.Code)
	}
}
