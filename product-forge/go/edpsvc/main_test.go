package main

import (
	"context"
	"crypto/x509"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgconn"

	"productforge/datastore"
	"productforge/edpdata"
	"productforge/edpsvc/internal/auth"
	"productforge/edpsvc/internal/cache"
	"productforge/edpsvc/internal/limits"
	"productforge/store"
)

type fakeBacklog struct {
	authErr    error
	reserveErr error
	timeout    time.Duration
}

func (f fakeBacklog) Authority(context.Context) (edpdata.Authority, error) {
	return edpdata.Authority{}, f.authErr
}
func (f fakeBacklog) Reserve(context.Context, string, string, string, int) (edpdata.IDBlock, error) {
	return edpdata.IDBlock{}, f.reserveErr
}
func (f fakeBacklog) StatementTimeout() time.Duration { return f.timeout }

func testServer(t *testing.T) *server {
	t.Helper()
	cfg := limits.DefaultConfig()
	m := limits.NewMetrics()
	guard := limits.NewRoleGuard()
	guard.Set(limits.Role{Name: "pf_app"})
	return &server{admin: "test-token", cfg: cfg, quota: limits.NewQuota(cfg, nil, m),
		metrics: m, role: guard, cacheStore: cache.New()}
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
	mreq := httptest.NewRequest(http.MethodGet, "/metrics", nil)
	mreq.Header.Set("Authorization", "Bearer test-token")
	h.ServeHTTP(rr, mreq)
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

func TestAuthorityReasonCodesAreBounded(t *testing.T) {
	allowed := map[string]bool{"timeout": true, "canceled": true, "migration_missing": true, "row_missing": true, "db_unavailable": true, "internal_error": true}
	for _, tc := range []struct {
		err  error
		want string
	}{
		{context.DeadlineExceeded, "timeout"},
		{context.Canceled, "canceled"},
		{edpdata.ErrAuthoritySchema, "migration_missing"},
		{edpdata.ErrAuthorityRow, "row_missing"},
		{&net.OpError{Op: "dial", Net: "tcp", Err: errors.New("refused")}, "db_unavailable"},
		{&pgconn.PgError{Code: "57014"}, "timeout"},
		{fmt.Errorf("wrapped: %w", &pgconn.PgError{Code: "57014"}), "timeout"},
		{fmt.Errorf("outer: %w", fmt.Errorf("inner: %w", &pgconn.PgError{Code: "57014"})), "timeout"},
		{&pgconn.PgError{Code: "28P01"}, "db_unavailable"},
		{fmt.Errorf("tls handshake failed"), "db_unavailable"},
		{x509.UnknownAuthorityError{}, "db_unavailable"},
		{x509.HostnameError{Certificate: &x509.Certificate{}, Host: "db"}, "db_unavailable"},
		{fmt.Errorf("wrapped: %w", x509.UnknownAuthorityError{}), "db_unavailable"},
		{x509.CertificateInvalidError{Cert: &x509.Certificate{}}, "db_unavailable"},
		{fmt.Errorf("prefix x509: legacy string"), "db_unavailable"},
		{fmt.Errorf("x509: leading string"), "db_unavailable"},
		{fmt.Errorf("(x509: wrapped)"), "db_unavailable"},
		{fmt.Errorf("[x509: wrapped]"), "db_unavailable"},
		{fmt.Errorf("- x509: wrapped"), "db_unavailable"},
		{fmt.Errorf("result/x509: wrapped"), "db_unavailable"},
		{fmt.Errorf("result=x509: wrapped"), "db_unavailable"},
		{fmt.Errorf("X509: uppercase"), "db_unavailable"},
		{fmt.Errorf("not_x509: marker"), "internal_error"},
		{fmt.Errorf("not.x509: marker"), "internal_error"},
		{fmt.Errorf("not-x509: marker"), "internal_error"},
		{fmt.Errorf("notx509: marker"), "internal_error"},
		{fmt.Errorf("x509: statement timeout 57014"), "timeout"},
		{fmt.Errorf("certificate rotation pending"), "internal_error"},
		{fmt.Errorf("x509"), "internal_error"},
		{fmt.Errorf("no pg_hba.conf entry"), "db_unavailable"},
		{fmt.Errorf("unexpected failure"), "internal_error"},
	} {
		got := authorityReasonCode(tc.err)
		if got != tc.want || !allowed[got] {
			t.Fatalf("authorityReasonCode(%v)=%q want %q", tc.err, got, tc.want)
		}
	}
}

func TestAuthorityFailureMetricUsesBoundedReasons(t *testing.T) {
	s := testServer(t)
	s.backlogFactory = func(string, bool) backlogStore { return fakeBacklog{authErr: errors.New("boom")} }
	rr := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/admin/backlog/authority?tenant=x", nil)
	req.Header.Set("Authorization", "Bearer test-token")
	s.buildMux().ServeHTTP(rr, req)
	if rr.Code != http.StatusServiceUnavailable {
		t.Fatalf("want 503, got %d %q", rr.Code, rr.Body.String())
	}
	var metrics strings.Builder
	s.metrics.Write(&metrics)
	if !strings.Contains(metrics.String(), `edp_backlog_authority_errors_total{reason="internal_error"} 1
`) ||
		!strings.Contains(metrics.String(), "edp_backlog_authority_last_request_ok 0") {
		t.Fatalf("authority failure metrics missing: %s", metrics.String())
	}
	s.backlogFactory = func(string, bool) backlogStore { return fakeBacklog{} }
	rr = httptest.NewRecorder()
	req = httptest.NewRequest(http.MethodGet, "/admin/backlog/authority?tenant=x", nil)
	req.Header.Set("Authorization", "Bearer test-token")
	s.buildMux().ServeHTTP(rr, req)
	if rr.Code != http.StatusOK {
		t.Fatalf("want recovery 200, got %d %q", rr.Code, rr.Body.String())
	}
	metrics.Reset()
	s.metrics.Write(&metrics)
	if !strings.Contains(metrics.String(), "edp_backlog_authority_last_request_ok 1") {
		t.Fatalf("authority gauge did not recover: %s", metrics.String())
	}
	labels := 0
	for _, line := range strings.Split(metrics.String(), "\n") {
		if i := strings.Index(line, `edp_backlog_authority_errors_total{reason="`); i == 0 {
			labels++
			reason := strings.Split(strings.TrimPrefix(line, `edp_backlog_authority_errors_total{reason="`), `"`)[0]
			if !authorityReasonBounded(reason) {
				t.Fatalf("unbounded authority reason label %q", reason)
			}
		}
	}
	if labels == 0 {
		t.Fatalf("authority failure metric was not emitted: %s", metrics.String())
	}
}

func TestAuthorityTimeoutComesFromConfig(t *testing.T) {
	cfg, err := limits.Load(func(k string) string {
		if k == "PF_EDP_DB_TIMEOUT" {
			return "2345ms"
		}
		return ""
	})
	if err != nil {
		t.Fatal(err)
	}
	s := testServer(t)
	s.cfg.DBTimeout = cfg.DBTimeout
	b := s.authorityBacklog("config-test")
	if cfg.DBTimeout != 2345*time.Millisecond || b.StatementTimeout() != cfg.DBTimeout {
		t.Fatalf("cfg.DBTimeout=%s store.timeout=%s", cfg.DBTimeout, b.StatementTimeout())
	}
	if got := s.reserveBacklog().StatementTimeout(); got != cfg.DBTimeout {
		t.Fatalf("reserve timeout=%s want %s", got, cfg.DBTimeout)
	}
}

func TestAuthorityResponseEchoesReservationID(t *testing.T) {
	got := reservationResponse("res-1", edpdata.IDBlock{Start: 10, End: 12})
	if got["reservation_id"] != "res-1" || got["start"] != int64(10) || got["end"] != int64(12) {
		t.Fatalf("unexpected response: %#v", got)
	}
}

func TestBacklogAuthorityRequiresAdminToken(t *testing.T) {
	s := testServer(t)
	rr := httptest.NewRecorder()
	s.buildMux().ServeHTTP(rr, httptest.NewRequest(http.MethodGet,
		"/admin/backlog/authority?tenant=product_forge", nil))
	if rr.Code != http.StatusUnauthorized {
		t.Fatalf("want 401, got %d %q", rr.Code, rr.Body.String())
	}
	var env limits.ErrorEnvelope
	if err := json.Unmarshal(rr.Body.Bytes(), &env); err != nil || env.Error.Code != "UNAUTHENTICATED" {
		t.Fatalf("envelope %q err=%v", rr.Body.String(), err)
	}
}

func TestBacklogAuthorityStatusPrecedence(t *testing.T) {
	s := testServer(t)
	h := s.buildMux()
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, httptest.NewRequest(http.MethodPost, "/admin/backlog/authority?tenant=x", nil))
	if rr.Code != http.StatusUnauthorized {
		t.Fatalf("POST without bearer: want 401, got %d", rr.Code)
	}
	rr = httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/admin/backlog/authority?tenant=x", nil)
	req.Header.Set("Authorization", "Bearer test-token")
	h.ServeHTTP(rr, req)
	if rr.Code != http.StatusMethodNotAllowed {
		t.Fatalf("POST with bearer: want 405, got %d %q", rr.Code, rr.Body.String())
	}
}

func TestBacklogAuthorityRequiresTenant(t *testing.T) {
	s := testServer(t)
	rr := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/admin/backlog/authority", nil)
	req.Header.Set("Authorization", "Bearer test-token")
	s.buildMux().ServeHTTP(rr, req)
	if rr.Code != http.StatusBadRequest {
		t.Fatalf("want 400, got %d %q", rr.Code, rr.Body.String())
	}
}

func TestBacklogAuthorityAuthBeforeMethodThroughChain(t *testing.T) {
	s := testServer(t)
	h := limits.Chain(s.buildMux(), s.cfg, s.quota, s.metrics, s.role.OK, s.authorize)
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, httptest.NewRequest(http.MethodPost, "/admin/backlog/authority?tenant=x", nil))
	if rr.Code != http.StatusUnauthorized {
		t.Fatalf("POST without bearer through chain: want 401, got %d", rr.Code)
	}
	rr = httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/admin/backlog/authority?tenant=x", nil)
	req.Header.Set("Authorization", "Bearer test-token")
	h.ServeHTTP(rr, req)
	if rr.Code != http.StatusMethodNotAllowed {
		t.Fatalf("POST with bearer through chain: want 405, got %d %q", rr.Code, rr.Body.String())
	}
}

func TestBacklogAuthorityWithDB(t *testing.T) {
	dsn := os.Getenv("PF_RUNTIME_DSN")
	if dsn == "" {
		t.Skip("set PF_RUNTIME_DSN to run the backlog authority DB test")
	}
	st, err := store.Open(context.Background(), dsn)
	if err != nil {
		t.Fatal(err)
	}
	defer st.Close()
	tenant := fmt.Sprintf("authority-it-%d", time.Now().UnixNano())
	bl := edpdata.NewBacklog(store.BindTenant(st, tenant))
	itemID := "BL-" + tenant
	if _, err := bl.Put(context.Background(), edpdata.BacklogItem{ID: itemID, TenantID: tenant, Title: "authority test"}); err != nil {
		t.Fatal(err)
	}
	defer func() { _ = bl.Delete(context.Background(), itemID) }()
	otherTenant := tenant + "-other"
	otherBl := edpdata.NewBacklog(store.BindTenant(st, otherTenant))
	otherID := "BL-" + otherTenant
	if _, err := otherBl.Put(context.Background(), edpdata.BacklogItem{ID: otherID, TenantID: otherTenant, Title: "other tenant"}); err != nil {
		t.Fatal(err)
	}
	defer func() { _ = otherBl.Delete(context.Background(), otherID) }()

	s := testServer(t)
	s.st = st
	rr := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/admin/backlog/authority?tenant="+tenant, nil)
	req.Header.Set("Authorization", "Bearer test-token")
	s.buildMux().ServeHTTP(rr, req)
	if rr.Code != http.StatusOK {
		t.Fatalf("want 200, got %d %q", rr.Code, rr.Body.String())
	}
	var body struct {
		Authority        string `json:"authority"`
		NextID           int64  `json:"next_id"`
		ReservationScope string `json:"reservation_scope"`
		ReservationCount int64  `json:"reservation_count"`
		Tenant           string `json:"tenant"`
		ItemScope        string `json:"item_scope"`
		ItemCount        int64  `json:"item_count"`
	}
	if err := json.Unmarshal(rr.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	if body.Authority != "global" || body.ReservationScope != "global" || body.ItemScope != "tenant" ||
		body.Tenant != tenant || body.NextID <= 0 || body.ItemCount != 1 {
		t.Fatalf("unexpected authority body: %+v", body)
	}
}

func TestBacklogReserveEchoesIDWithDB(t *testing.T) {
	dsn := os.Getenv("PF_RUNTIME_DSN")
	if dsn == "" {
		t.Skip("set PF_RUNTIME_DSN to run the reservation echo DB test")
	}
	st, err := store.Open(context.Background(), dsn)
	if err != nil {
		t.Fatal(err)
	}
	defer st.Close()
	s := testServer(t)
	s.st = st
	rid := fmt.Sprintf("res-echo-%d", time.Now().UnixNano())
	body := fmt.Sprintf(`{"scope":"product_forge","project":"","reservation_id":%q,"size":2}`, rid)
	rr := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/backlog/ids:reserve", strings.NewReader(body))
	req.Header.Set("Authorization", "Bearer test-token")
	s.buildMux().ServeHTTP(rr, req)
	if rr.Code != http.StatusOK {
		t.Fatalf("want 200, got %d %q", rr.Code, rr.Body.String())
	}
	var got map[string]any
	if err := json.Unmarshal(rr.Body.Bytes(), &got); err != nil {
		t.Fatal(err)
	}
	if got["reservation_id"] != rid || got["start"] == nil || got["end"] == nil {
		t.Fatalf("unexpected reservation response: %#v", got)
	}
	if hasTenantKey(got) {
		t.Fatalf("reservation response leaked tenant data: %#v", got)
	}
}

func hasTenantKey(v any) bool {
	switch x := v.(type) {
	case map[string]any:
		for k, child := range x {
			if strings.Contains(strings.ToLower(k), "tenant") || hasTenantKey(child) {
				return true
			}
		}
	case []any:
		for _, child := range x {
			if hasTenantKey(child) {
				return true
			}
		}
	}
	return false
}

func TestReservationExhaustedFailsClosedWithAlarm(t *testing.T) {
	s := testServer(t)
	s.backlogFactory = func(tenant string, reserve bool) backlogStore {
		if tenant != "" || !reserve {
			t.Fatalf("reserve seam called with tenant=%q reserve=%v", tenant, reserve)
		}
		return fakeBacklog{reserveErr: edpdata.ErrReservationExhausted}
	}
	rr := httptest.NewRecorder()
	body := `{"scope":"product_forge","project":"","reservation_id":"res-x","size":2}`
	req := httptest.NewRequest(http.MethodPost, "/backlog/ids:reserve", strings.NewReader(body))
	req.Header.Set("Authorization", "Bearer test-token")
	s.buildMux().ServeHTTP(rr, req)
	if rr.Code != http.StatusConflict || !strings.Contains(rr.Body.String(), "backlog id space exhausted") {
		t.Fatalf("want fixed 409, got %d %q", rr.Code, rr.Body.String())
	}
	var metrics strings.Builder
	s.metrics.Write(&metrics)
	if !strings.Contains(metrics.String(), "edp_backlog_reservation_exhausted_total 1") {
		t.Fatalf("exhaustion alarm metric missing: %s", metrics.String())
	}
	rules, err := os.ReadFile("../../ops/prometheus/backlog-authority.rules.yml")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(rules), "alert: ProductForgeBacklogIDSpaceExhausted") ||
		!strings.Contains(string(rules), "expr: increase(edp_backlog_reservation_exhausted_total[10m]) > 0") {
		t.Fatal("exhaustion metric is not wired to the expected alert rule")
	}
}

func TestBacklogAuthorityFailsClosed(t *testing.T) {
	dsn := os.Getenv("PF_RUNTIME_DSN")
	if dsn == "" {
		t.Skip("set PF_RUNTIME_DSN to run the closed-pool authority test")
	}
	st, err := store.Open(context.Background(), dsn)
	if err != nil {
		t.Fatal(err)
	}
	st.Close()
	s := testServer(t)
	s.st = st
	rr := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/admin/backlog/authority?tenant=product_forge", nil)
	req.Header.Set("Authorization", "Bearer test-token")
	s.buildMux().ServeHTTP(rr, req)
	if rr.Code != http.StatusServiceUnavailable {
		t.Fatalf("want 503, got %d %q", rr.Code, rr.Body.String())
	}
	if !strings.Contains(rr.Body.String(), "backlog authority unavailable") {
		t.Fatalf("want fixed 503 message, got %q", rr.Body.String())
	}
	var metrics strings.Builder
	s.metrics.Write(&metrics)
	if !strings.Contains(metrics.String(), `edp_backlog_authority_errors_total{reason="db_unavailable"} 1`) {
		t.Fatalf("authority failure metric missing: %s", metrics.String())
	}
}

func TestBacklogTenantErrorMapping(t *testing.T) {
	s := testServer(t)
	cases := []struct {
		err  error
		code int
	}{
		{edpdata.ErrTenantMismatch, http.StatusForbidden},
		{edpdata.ErrTenantContext, http.StatusServiceUnavailable},
	}
	for _, c := range cases {
		rr := httptest.NewRecorder()
		if !s.backlogTenantError(rr, httptest.NewRequest(http.MethodGet, "/backlog?tenant=x", nil), c.err) {
			t.Fatalf("not handled: %v", c.err)
		}
		if rr.Code != c.code {
			t.Fatalf("%v: got %d want %d", c.err, rr.Code, c.code)
		}
	}
}

func TestTenantAuth_EndToEnd(t *testing.T) {
	adminToken := "adm-token-32-chars-long-secret"
	gwSecret := "gw-secret-32-chars-long-hmac-key"
	tenantTokens := "tok_alpha=tenant_a;tok_beta=tenant_b"

	authenticator := auth.NewAuthenticator(adminToken, tenantTokens, gwSecret, "")
	cfg := limits.DefaultConfig()
	q := limits.NewQuota(cfg, nil, limits.NewMetrics())
	m := limits.NewMetrics()
	roleGuard := limits.NewRoleGuard()
	roleGuard.Set(limits.Role{Name: "pf_app"})

	s := &server{
		admin:         adminToken,
		authenticator: authenticator,
		cfg:           cfg,
		quota:         q,
		metrics:       m,
		role:          roleGuard,
		cacheStore:    cache.New(),
	}

	handler := limits.Chain(limits.EnvelopeFallback(s.buildMux()), cfg, q, m, roleGuard.OK, s.authorize)

	// 1. Unauthenticated request -> 401
	reqUnauth := httptest.NewRequest(http.MethodGet, "/admin/limits", nil)
	rrUnauth := httptest.NewRecorder()
	handler.ServeHTTP(rrUnauth, reqUnauth)
	if rrUnauth.Code != http.StatusUnauthorized {
		t.Fatalf("unauth want 401, got %d", rrUnauth.Code)
	}

	// 2. Admin token on admin route -> 200
	reqAdmin := httptest.NewRequest(http.MethodGet, "/admin/limits", nil)
	reqAdmin.Header.Set("Authorization", "Bearer "+adminToken)
	rrAdmin := httptest.NewRecorder()
	handler.ServeHTTP(rrAdmin, reqAdmin)
	if rrAdmin.Code != http.StatusOK {
		t.Fatalf("admin want 200, got %d", rrAdmin.Code)
	}

	// 3. Tenant token attempting admin route -> 401/403
	reqTenantAdmin := httptest.NewRequest(http.MethodGet, "/admin/limits", nil)
	reqTenantAdmin.Header.Set("Authorization", "Bearer tok_alpha")
	rrTenantAdmin := httptest.NewRecorder()
	handler.ServeHTTP(rrTenantAdmin, reqTenantAdmin)
	if rrTenantAdmin.Code != http.StatusUnauthorized {
		t.Fatalf("tenant token on admin route want 401, got %d", rrTenantAdmin.Code)
	}

	// 4. Valid Gateway Signed Claim
	claims := auth.GatewayClaims{
		Tenant:    "tenant_a",
		Principal: "user_a",
		ExpiresAt: time.Now().Unix() + 3600,
		IssuedAt:  time.Now().Unix() - 10,
	}
	gwToken, err := auth.SignGatewayClaim(claims, []byte(gwSecret))
	if err != nil {
		t.Fatalf("SignGatewayClaim failed: %v", err)
	}

	// 5. Cross-tenant mismatch (authenticated as tenant_a, requests tenant_b via query or header) -> 403
	reqCrossQuery := httptest.NewRequest(http.MethodGet, "/backlog?tenant=tenant_b", nil)
	reqCrossQuery.Header.Set("Authorization", "Bearer "+gwToken)
	rrCrossQuery := httptest.NewRecorder()
	handler.ServeHTTP(rrCrossQuery, reqCrossQuery)
	if rrCrossQuery.Code != http.StatusForbidden {
		t.Fatalf("cross-tenant query want 403, got %d", rrCrossQuery.Code)
	}

	reqCrossHeader := httptest.NewRequest(http.MethodGet, "/backlog", nil)
	reqCrossHeader.Header.Set("Authorization", "Bearer "+gwToken)
	reqCrossHeader.Header.Set("X-Tenant-Id", "tenant_b")
	rrCrossHeader := httptest.NewRecorder()
	handler.ServeHTTP(rrCrossHeader, reqCrossHeader)
	if rrCrossHeader.Code != http.StatusForbidden {
		t.Fatalf("cross-tenant header want 403, got %d", rrCrossHeader.Code)
	}

	// 6. Forged gateway claim -> 401
	forgedToken, _ := auth.SignGatewayClaim(claims, []byte("wrong-signing-secret-attacker-key"))
	reqForged := httptest.NewRequest(http.MethodGet, "/backlog", nil)
	reqForged.Header.Set("Authorization", "Bearer "+forgedToken)
	rrForged := httptest.NewRecorder()
	handler.ServeHTTP(rrForged, reqForged)
	if rrForged.Code != http.StatusUnauthorized {
		t.Fatalf("forged token want 401, got %d", rrForged.Code)
	}

	// 7. Expired gateway claim -> 401
	expiredClaims := auth.GatewayClaims{
		Tenant:    "tenant_a",
		ExpiresAt: time.Now().Unix() - 100,
	}
	expiredToken, _ := auth.SignGatewayClaim(expiredClaims, []byte(gwSecret))
	reqExpired := httptest.NewRequest(http.MethodGet, "/backlog", nil)
	reqExpired.Header.Set("Authorization", "Bearer "+expiredToken)
	rrExpired := httptest.NewRecorder()
	handler.ServeHTTP(rrExpired, reqExpired)
	if rrExpired.Code != http.StatusUnauthorized {
		t.Fatalf("expired token want 401, got %d", rrExpired.Code)
	}
}

func TestBuildObjectStore_GCS(t *testing.T) {
	origBackend := os.Getenv("PF_OBJECT_BACKEND")
	origBucket := os.Getenv("PF_GCS_BUCKET")
	origToken := os.Getenv("PF_GCS_TOKEN")
	origBaseURL := os.Getenv("PF_GCS_BASE_URL")
	origCredsJSON := os.Getenv("PF_GCS_CREDENTIALS_JSON")
	defer func() {
		os.Setenv("PF_OBJECT_BACKEND", origBackend)
		os.Setenv("PF_GCS_BUCKET", origBucket)
		os.Setenv("PF_GCS_TOKEN", origToken)
		os.Setenv("PF_GCS_BASE_URL", origBaseURL)
		os.Setenv("PF_GCS_CREDENTIALS_JSON", origCredsJSON)
	}()

	// Case 1: PF_OBJECT_BACKEND=gcs without bucket -> fail closed
	os.Setenv("PF_OBJECT_BACKEND", "gcs")
	os.Unsetenv("PF_GCS_BUCKET")
	st, err := buildObjectStore()
	if err == nil || st != nil {
		t.Fatalf("expected error on missing PF_GCS_BUCKET, got st=%v err=%v", st, err)
	}

	// Case 2: PF_OBJECT_BACKEND=gcs with bucket and token -> success
	os.Setenv("PF_GCS_BUCKET", "test-bucket")
	os.Setenv("PF_GCS_TOKEN", "test-bearer-token")
	os.Setenv("PF_GCS_BASE_URL", "https://storage.googleapis.com")
	st, err = buildObjectStore()
	if err != nil || st == nil {
		t.Fatalf("expected store on valid gcs config, got st=%v err=%v", st, err)
	}

	// Case 3: PF_OBJECT_BACKEND=gcs with credentials JSON -> success
	os.Unsetenv("PF_GCS_TOKEN")
	os.Setenv("PF_GCS_CREDENTIALS_JSON", `{"access_token": "json-derived-token"}`)
	st, err = buildObjectStore()
	if err != nil || st == nil {
		t.Fatalf("expected store on gcs credentials JSON, got st=%v err=%v", st, err)
	}

	// Case 3b: PF_OBJECT_BACKEND=gcs with credentials file -> success
	os.Unsetenv("PF_GCS_CREDENTIALS_JSON")
	tmpFile := filepath.Join(t.TempDir(), "gcs-creds.json")
	if err := os.WriteFile(tmpFile, []byte(`{"access_token": "file-token"}`), 0600); err != nil {
		t.Fatal(err)
	}
	os.Setenv("PF_GCS_CREDENTIALS_FILE", tmpFile)
	defer os.Unsetenv("PF_GCS_CREDENTIALS_FILE")
	st, err = buildObjectStore()
	if err != nil || st == nil {
		t.Fatalf("expected store on gcs credentials file, got st=%v err=%v", st, err)
	}

	// Case 4: Default or local backend -> local store
	os.Unsetenv("PF_GCS_CREDENTIALS_FILE")
	os.Setenv("PF_OBJECT_BACKEND", "local")
	st, err = buildObjectStore()
	if err != nil || st == nil {
		t.Fatalf("expected local store, got st=%v err=%v", st, err)
	}
}

func TestBuildObjectStore_Azure(t *testing.T) {
	origBackend := os.Getenv("PF_OBJECT_BACKEND")
	origContainer := os.Getenv("PF_AZURE_CONTAINER")
	origAccount := os.Getenv("PF_AZURE_ACCOUNT")
	origKey := os.Getenv("PF_AZURE_KEY")
	origSAS := os.Getenv("PF_AZURE_SAS_TOKEN")
	origToken := os.Getenv("PF_AZURE_TOKEN")
	origBaseURL := os.Getenv("PF_AZURE_BASE_URL")
	defer func() {
		os.Setenv("PF_OBJECT_BACKEND", origBackend)
		os.Setenv("PF_AZURE_CONTAINER", origContainer)
		os.Setenv("PF_AZURE_ACCOUNT", origAccount)
		os.Setenv("PF_AZURE_KEY", origKey)
		os.Setenv("PF_AZURE_SAS_TOKEN", origSAS)
		os.Setenv("PF_AZURE_TOKEN", origToken)
		os.Setenv("PF_AZURE_BASE_URL", origBaseURL)
	}()

	// Case 1: PF_OBJECT_BACKEND=azure without container -> fail closed
	os.Setenv("PF_OBJECT_BACKEND", "azure")
	os.Unsetenv("PF_AZURE_CONTAINER")
	st, err := buildObjectStore()
	if err == nil || st != nil {
		t.Fatalf("expected error on missing PF_AZURE_CONTAINER, got st=%v err=%v", st, err)
	}

	// Case 2: PF_OBJECT_BACKEND=azure with container and shared key -> success
	os.Setenv("PF_AZURE_CONTAINER", "testcontainer")
	os.Setenv("PF_AZURE_ACCOUNT", "testaccount")
	os.Setenv("PF_AZURE_KEY", "dGVzdGtleQ==")
	st, err = buildObjectStore()
	if err != nil || st == nil {
		t.Fatalf("expected store on azure SharedKey config, got st=%v err=%v", st, err)
	}

	// Case 3: PF_OBJECT_BACKEND=azblob alias with SAS token -> success
	os.Setenv("PF_OBJECT_BACKEND", "azblob")
	os.Unsetenv("PF_AZURE_KEY")
	os.Setenv("PF_AZURE_SAS_TOKEN", "sv=2020-10-02&sig=mock")
	st, err = buildObjectStore()
	if err != nil || st == nil {
		t.Fatalf("expected store on azblob alias with SAS, got st=%v err=%v", st, err)
	}

	// Case 4: PF_OBJECT_BACKEND=azure with Bearer token -> success
	os.Setenv("PF_OBJECT_BACKEND", "azure")
	os.Unsetenv("PF_AZURE_SAS_TOKEN")
	os.Setenv("PF_AZURE_TOKEN", "mock-ad-token")
	st, err = buildObjectStore()
	if err != nil || st == nil {
		t.Fatalf("expected store on azure Bearer token, got st=%v err=%v", st, err)
	}

	// Case 5: PF_OBJECT_BACKEND=azure with BaseURL (emulator) -> success
	os.Unsetenv("PF_AZURE_TOKEN")
	os.Setenv("PF_AZURE_BASE_URL", "http://127.0.0.1:10000/devstoreaccount1")
	st, err = buildObjectStore()
	if err != nil || st == nil {
		t.Fatalf("expected store on azure emulator BaseURL, got st=%v err=%v", st, err)
	}
}

func TestBuildObjectStore_GDrive(t *testing.T) {
	origBackend := os.Getenv("PF_OBJECT_BACKEND")
	origFolder := os.Getenv("PF_GDRIVE_ROOT_FOLDER_ID")
	origToken := os.Getenv("PF_GDRIVE_TOKEN")
	origBaseURL := os.Getenv("PF_GDRIVE_BASE_URL")
	origUploadURL := os.Getenv("PF_GDRIVE_UPLOAD_BASE_URL")
	defer func() {
		os.Setenv("PF_OBJECT_BACKEND", origBackend)
		os.Setenv("PF_GDRIVE_ROOT_FOLDER_ID", origFolder)
		os.Setenv("PF_GDRIVE_TOKEN", origToken)
		os.Setenv("PF_GDRIVE_BASE_URL", origBaseURL)
		os.Setenv("PF_GDRIVE_UPLOAD_BASE_URL", origUploadURL)
	}()

	// Case 1: PF_OBJECT_BACKEND=gdrive without root folder -> fail closed
	os.Setenv("PF_OBJECT_BACKEND", "gdrive")
	os.Unsetenv("PF_GDRIVE_ROOT_FOLDER_ID")
	st, err := buildObjectStore()
	if err == nil || st != nil {
		t.Fatalf("expected error on missing PF_GDRIVE_ROOT_FOLDER_ID, got st=%v err=%v", st, err)
	}

	// Case 2: PF_OBJECT_BACKEND=gdrive with root folder and token -> success
	os.Setenv("PF_GDRIVE_ROOT_FOLDER_ID", "0B-root-folder-12345")
	os.Setenv("PF_GDRIVE_TOKEN", "ya29.test-bearer-token")
	st, err = buildObjectStore()
	if err != nil || st == nil {
		t.Fatalf("expected store on gdrive token config, got st=%v err=%v", st, err)
	}

	// Case 3: PF_OBJECT_BACKEND=googledrive alias with custom BaseURL and UploadBaseURL -> success
	os.Setenv("PF_OBJECT_BACKEND", "googledrive")
	os.Setenv("PF_GDRIVE_BASE_URL", "http://127.0.0.1:8090")
	os.Setenv("PF_GDRIVE_UPLOAD_BASE_URL", "http://127.0.0.1:8090")
	st, err = buildObjectStore()
	if err != nil || st == nil {
		t.Fatalf("expected store on googledrive alias with custom URLs, got st=%v err=%v", st, err)
	}
}

func TestServer_Memory_DualVec_Sqlite(t *testing.T) {
	dbPath := filepath.Join(t.TempDir(), "test_mem.db")
	origDSN := os.Getenv("PF_MEMORY_DSN")
	defer os.Setenv("PF_MEMORY_DSN", origDSN)
	os.Setenv("PF_MEMORY_DSN", dbPath)

	s := &server{
		admin: "admin",
		cfg:   limits.Config{DBTimeout: 5 * time.Second},
	}
	defer func() {
		if c, ok := s.memRepo.(io.Closer); ok && c != nil {
			_ = c.Close()
		}
	}()

	// POST /memory
	body := `{"id":"11111111-1111-4111-8111-111111111111","tenant":"test-tenant","project":"proj-1","kind":"semantic","content":"dualvec test content"}`
	req := httptest.NewRequest(http.MethodPost, "/memory", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	s.memoryHandle(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("POST /memory failed: code=%d body=%s", w.Code, w.Body.String())
	}

	// GET /memory?tenant=test-tenant&project=proj-1&q=dualvec
	reqGet := httptest.NewRequest(http.MethodGet, "/memory?tenant=test-tenant&project=proj-1&q=dualvec", nil)
	wGet := httptest.NewRecorder()
	s.memoryHandle(wGet, reqGet)

	if wGet.Code != http.StatusOK {
		t.Fatalf("GET /memory failed: code=%d body=%s", wGet.Code, wGet.Body.String())
	}

	var res struct {
		Hits []datastore.MemoryEntry `json:"hits"`
	}
	if err := json.NewDecoder(wGet.Body).Decode(&res); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}
	if len(res.Hits) != 1 || res.Hits[0].ID != "11111111-1111-4111-8111-111111111111" {
		t.Fatalf("unexpected hits: %+v", res.Hits)
	}

	// GET /memory/11111111-1111-4111-8111-111111111111?tenant=test-tenant&project=proj-1
	reqByID := httptest.NewRequest(http.MethodGet, "/memory/11111111-1111-4111-8111-111111111111?tenant=test-tenant&project=proj-1", nil)
	wByID := httptest.NewRecorder()
	s.memoryByID(wByID, reqByID)
	if wByID.Code != http.StatusOK {
		t.Fatalf("GET /memory/11111111-1111-4111-8111-111111111111 failed: code=%d body=%s", wByID.Code, wByID.Body.String())
	}

	reqOtherTenant := httptest.NewRequest(http.MethodGet, "/memory/11111111-1111-4111-8111-111111111111?tenant=other&project=proj-1", nil)
	wOtherTenant := httptest.NewRecorder()
	s.memoryByID(wOtherTenant, reqOtherTenant)
	if wOtherTenant.Code != http.StatusNotFound {
		t.Fatalf("cross-tenant get must be 404, got %d body=%s", wOtherTenant.Code, wOtherTenant.Body.String())
	}

	reqOtherProject := httptest.NewRequest(http.MethodGet, "/memory/11111111-1111-4111-8111-111111111111?tenant=test-tenant&project=proj-2", nil)
	wOtherProject := httptest.NewRecorder()
	s.memoryByID(wOtherProject, reqOtherProject)
	if wOtherProject.Code != http.StatusNotFound {
		t.Fatalf("cross-project get must be 404, got %d body=%s", wOtherProject.Code, wOtherProject.Body.String())
	}

	// DELETE /memory/11111111-1111-4111-8111-111111111111?tenant=test-tenant&project=proj-1
	reqDel := httptest.NewRequest(http.MethodDelete, "/memory/11111111-1111-4111-8111-111111111111?tenant=test-tenant&project=proj-1", nil)
	wDel := httptest.NewRecorder()
	s.memoryByID(wDel, reqDel)
	if wDel.Code != http.StatusOK {
		t.Fatalf("DELETE /memory/11111111-1111-4111-8111-111111111111 failed: code=%d body=%s", wDel.Code, wDel.Body.String())
	}
}

func TestNoDirectMemoryRepositoryCalls(t *testing.T) {
	b, err := os.ReadFile("main.go")
	if err != nil {
		t.Fatal(err)
	}
	src := string(b)
	for _, bad := range []string{"mem.Put(", "mem.Get(", "mem.Search(", "mem.Delete("} {
		if strings.Contains(src, bad) {
			t.Fatalf("direct memory repository call found: %s", bad)
		}
	}
}

func TestMemoryHandlersUseOrchestrator(t *testing.T) {
	TestServer_Memory_DualVec_Sqlite(t)
}
