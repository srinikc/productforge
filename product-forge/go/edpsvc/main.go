// Command edpsvc is the EDP data-plane service (ADR-0008): the Go API surface for the Enterprise Data
// Plane. First capability: migrations admin (status/up/down) + schema-check, admin-authz only. It reuses
// the go/store DAL and go/migrate runner; it integrates with other services over HTTP only.
//
// Env:
//
//	PF_DB_DSN         PostgreSQL DSN (owner role)
//	PF_ADMIN_TOKEN    required bearer token for /admin/* (admin capability)
//	PF_EDP_ADDR       listen address (default 127.0.0.1:8030)
//	PF_MIGRATIONS_DIR migrations directory (default: nearest 'migrations' up from cwd)
package main

import (
	"bytes"
	"context"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"time"

	"productforge/artifacts"
	"productforge/datastore"
	"productforge/edpdata"
	"productforge/edpsvc/internal/limits"
	"productforge/migrate"
	"productforge/objpolicy"
	"productforge/objstore"
	"productforge/s3store"
	"productforge/store"
)

type server struct {
	dsn     string
	admin   string
	migDir  string
	obj     datastore.ObjectStore
	cfg     limits.Config
	st      *store.PgStore
	quota   *limits.Quota
	metrics *limits.Metrics
	role    *limits.RoleGuard
}

// buildObjectStore selects the object-store adapter (EDP-13 local / EDP-14 S3) by PF_OBJECT_BACKEND.
func buildObjectStore() (datastore.ObjectStore, error) {
	if strings.EqualFold(os.Getenv("PF_OBJECT_BACKEND"), "s3") {
		return s3store.New(context.Background(), s3store.Config{
			Endpoint:  os.Getenv("PF_S3_ENDPOINT"),
			AccessKey: os.Getenv("PF_S3_ACCESS_KEY"),
			SecretKey: os.Getenv("PF_S3_SECRET_KEY"),
			Bucket:    os.Getenv("PF_S3_BUCKET"),
			Region:    os.Getenv("PF_S3_REGION"),
			UseSSL:    os.Getenv("PF_S3_USE_SSL") == "1",
			Ensure:    os.Getenv("PF_S3_ENSURE") == "1",
		})
	}
	return objstore.NewLocalStore(envOr("PF_OBJECT_ROOT", "data/local/objects"), 0)
}

func main() {
	cfg, err := limits.Load(os.Getenv)
	if err != nil {
		log.Fatalf("config: %v", err)
	}
	if err := limits.ValidateProfile(cfg, os.Getenv); err != nil {
		log.Fatalf("profile: %v", err)
	}
	dsn := os.Getenv("PF_DB_DSN")
	if dsn == "" {
		log.Fatal("PF_DB_DSN is required")
	}
	admin := os.Getenv("PF_ADMIN_TOKEN")
	if admin == "" {
		log.Fatal("PF_ADMIN_TOKEN is required")
	}
	st, err := store.OpenWithPool(context.Background(), dsn, store.PoolOptions{
		MaxConns:          cfg.Pool.MaxConns,
		MinConns:          cfg.Pool.MinConns,
		MaxConnLifetime:   cfg.Pool.MaxConnLifetime,
		MaxConnIdleTime:   cfg.Pool.MaxConnIdleTime,
		HealthCheckPeriod: cfg.Pool.HealthCheckPeriod,
		ConnectTimeout:    cfg.Pool.ConnectTimeout,
	})
	if err != nil {
		log.Fatalf("database: %v", err)
	}
	guard := limits.NewRoleGuard()
	role, err := limits.CheckDBRole(context.Background(), st, cfg.AllowSuperuserDSN)
	if err != nil {
		st.Close()
		log.Fatalf("runtime DB role: %v", err)
	}
	guard.Set(role)
	if role.Superuser || role.BypassRLS {
		log.Printf("WARNING runtime DB role %q is superuser/BYPASSRLS (explicitly allowed)", role.Name)
	}
	m := limits.NewMetrics()
	q := limits.NewQuota(cfg, nil, m)
	s := &server{dsn: dsn, admin: admin, migDir: envOr("PF_MIGRATIONS_DIR", findMigrations()),
		cfg: cfg, st: st, quota: q, metrics: m, role: guard}
	obj, err := buildObjectStore()
	if err != nil {
		st.Close()
		log.Fatalf("object store: %v", err)
	}
	s.obj = obj
	recheckCtx, stopRecheck := context.WithCancel(context.Background())
	defer stopRecheck()
	go guard.RecheckLoop(recheckCtx, st, cfg.AllowSuperuserDSN, cfg.RoleRecheckInterval, func(err error) {
		log.Printf("WARNING runtime DB role recheck failed: %v", err)
		m.Inc("edp_role_check_failures_total")
	})
	// AC: surface coverage non-fatally at startup (a stale/low rotation must not stop the service).
	s.checkAuditCoverage()
	handler := limits.Chain(limits.EnvelopeFallback(s.buildMux()), cfg, q, m, guard.OK)
	addr := envOr("PF_EDP_ADDR", "127.0.0.1:8030")
	srv := &http.Server{
		Addr:              addr,
		Handler:           handler,
		ReadHeaderTimeout: cfg.ReadHeaderTimeout,
		ReadTimeout:       cfg.ReadTimeout,
		WriteTimeout:      cfg.WriteTimeout,
		IdleTimeout:       cfg.IdleTimeout,
		MaxHeaderBytes:    int(cfg.MaxHeaderBytes),
	}
	sigCtx, stopSig := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stopSig()
	go func() {
		log.Printf("edpsvc listening on %s (migrations=%s, profile=%s)", addr, s.migDir, cfg.Profile)
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Fatalf("edpsvc: %v", err)
		}
	}()
	<-sigCtx.Done()
	stopRecheck()
	drain := cfg.WriteTimeout
	if drain < 30*time.Second {
		drain = 30 * time.Second
	}
	shutCtx, cancel := context.WithTimeout(context.Background(), drain)
	defer cancel()
	if err := srv.Shutdown(shutCtx); err != nil {
		log.Printf("edpsvc shutdown: %v; force-closing the listener", err)
		_ = srv.Close()
	}
	st.Close()
}

func (s *server) buildMux() *http.ServeMux {
	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
	})
	mux.HandleFunc("/ready", s.ready)
	mux.HandleFunc("/metrics", s.adminOnly(s.metricsHandler))
	mux.HandleFunc("/admin/migrations/status", s.adminOnly(s.migrationsStatus))
	mux.HandleFunc("/admin/migrations/up", s.adminOnly(s.migrationsUp))
	mux.HandleFunc("/admin/migrations/down", s.adminOnly(s.migrationsDown))
	mux.HandleFunc("/admin/schema-check", s.adminOnly(s.schemaCheck))
	mux.HandleFunc("/admin/object-store/capabilities", s.adminOnly(s.objectStoreCapabilities))
	mux.HandleFunc("/admin/object-store/conform", s.adminOnly(s.objectStoreConform))
	mux.HandleFunc("/admin/limits", s.adminOnly(s.adminLimits))
	mux.HandleFunc("/artifacts", s.adminOnly(s.artifactUpload))
	mux.HandleFunc("/artifacts/", s.adminOnly(s.artifactRoute))
	mux.HandleFunc("/audit", s.adminOnly(s.auditAppend))
	mux.HandleFunc("/admin/audit-coverage", s.adminOnly(s.auditCoverage))
	mux.HandleFunc("/admin/objects/url", s.adminOnly(s.objectURL))
	mux.HandleFunc("/jobs", s.adminOnly(s.jobSubmit))
	mux.HandleFunc("/jobs/claim", s.adminOnly(s.jobClaim))
	mux.HandleFunc("/jobs/action", s.adminOnly(s.jobAction))
	mux.HandleFunc("/memory", s.adminOnly(s.memoryHandle))
	mux.HandleFunc("/memory/", s.adminOnly(s.memoryByID))
	mux.HandleFunc("/backlog", s.adminOnly(s.backlogHandle))
	mux.HandleFunc("/backlog/", s.adminOnly(s.backlogByID))
	return mux
}

// coverageStatus mirrors audit_partition_coverage for the startup probe and the admin endpoint.
type coverageStatus struct {
	MonthsAhead       int
	LeadMonths        int
	LastRotationHours float64
	Stale             bool
}

func (c coverageStatus) Low() bool { return c.MonthsAhead < c.LeadMonths }

// rotationMaxAge reads the stale threshold once (env), defaulting to 48h.
func rotationMaxAge() float64 {
	if v := os.Getenv("PF_AUDIT_ROTATION_MAX_AGE_HOURS"); v != "" {
		if n, err := strconv.ParseFloat(v, 64); err == nil && n > 0 {
			return n
		}
	}
	return 48
}

// readCoverage uses the store port (no second pool / provider import in the service layer).
func (s *server) readCoverage(ctx context.Context, maxAge float64) (coverageStatus, error) {
	var st coverageStatus
	_, err := s.withStore(ctx, func(pg *store.PgStore) (any, error) {
		return nil, pg.WithTx(ctx, func(tx datastore.Tx) error {
			rows, err := tx.Query(ctx, `SELECT months_ahead, lead_months, last_rotation_hours
				FROM audit_coverage_status()`)
			if err != nil {
				return err
			}
			defer rows.Close()
			if !rows.Next() {
				return errors.New("audit coverage: no row")
			}
			if err := rows.Scan(&st.MonthsAhead, &st.LeadMonths, &st.LastRotationHours); err != nil {
				return err
			}
			st.Stale = maxAge > 0 && (st.LastRotationHours < 0 || st.LastRotationHours > maxAge)
			return rows.Err()
		})
	})
	return st, err
}

// checkAuditCoverage emits the AC metrics once on startup; every failure is logged, never fatal.
func (s *server) checkAuditCoverage() {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	st, err := s.readCoverage(ctx, rotationMaxAge())
	if err != nil {
		log.Printf("audit coverage: %v (non-fatal)", err)
		return
	}
	metrics := map[string]int64{}
	if st.Low() {
		metrics["audit_partition_low_coverage_total"] = 1
	}
	stale := 0.0
	if st.Stale {
		stale = 1
	}
	b, _ := json.Marshal(map[string]any{
		"metrics": metrics,
		"gauges": map[string]float64{
			"audit_partition_months_ahead": float64(st.MonthsAhead),
			"audit_rotation_stale":         stale,
		},
	})
	fmt.Fprintln(os.Stderr, string(b))
	if st.Low() {
		log.Printf("WARNING audit coverage low: months_ahead=%d lead=%d", st.MonthsAhead, st.LeadMonths)
	}
	if st.Stale {
		log.Printf("WARNING audit rotation stale: last_rotation_hours=%.1f", st.LastRotationHours)
	}
}

func (s *server) auditCoverage(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 10*time.Second)
	defer cancel()
	st, err := s.readCoverage(ctx, rotationMaxAge())
	if err != nil {
		s.fail(w, r, http.StatusServiceUnavailable, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"months_ahead": st.MonthsAhead, "lead_months": st.LeadMonths, "low": st.Low(),
		"last_rotation_hours": st.LastRotationHours, "stale": st.Stale,
	})
}

// objectURL mints a signed URL through the single objpolicy boundary (admin API; tenant from the request).
func (s *server) objectURL(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		s.bad(w, r, http.StatusMethodNotAllowed, "use GET")
		return
	}
	q := r.URL.Query()
	tenant, key := q.Get("tenant"), q.Get("key")
	if tenant == "" || key == "" {
		s.bad(w, r, http.StatusBadRequest, "tenant and key are required")
		return
	}
	ttl := 5 * time.Minute
	if v := q.Get("ttl_seconds"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			ttl = time.Duration(n) * time.Second
		}
	}
	method := q.Get("method")
	if method == "" {
		method = http.MethodGet
	}
	ctx := objpolicy.WithTenant(r.Context(), tenant)
	u, err := objpolicy.Mint(ctx, s.obj, key, method, ttl)
	if err != nil {
		s.fail(w, r, http.StatusBadRequest, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"url": u})
}

func envOr(k, d string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return d
}

func findMigrations() string {
	d, err := os.Getwd()
	if err != nil {
		return "migrations"
	}
	for {
		cand := filepath.Join(d, "migrations")
		if st, e := os.Stat(cand); e == nil && st.IsDir() {
			return cand
		}
		parent := filepath.Dir(d)
		if parent == d {
			return "migrations"
		}
		d = parent
	}
}

func (s *server) adminOnly(fn http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		auth := r.Header.Get("Authorization")
		token := ""
		if strings.HasPrefix(auth, "Bearer ") {
			token = strings.TrimSpace(strings.TrimPrefix(auth, "Bearer "))
		}
		if subtle.ConstantTimeCompare([]byte(token), []byte(s.admin)) != 1 {
			limits.WriteError(w, r, http.StatusUnauthorized, "admin authorization required")
			return
		}
		fn(w, r)
	}
}

func (s *server) withStore(ctx context.Context, fn func(*store.PgStore) (any, error)) (any, error) {
	return fn(s.st)
}

func (s *server) migrationsStatus(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := s.dbCtx(r)
	defer cancel()
	out, err := s.withStore(ctx, func(st *store.PgStore) (any, error) {
		all, err := migrate.LoadDir(s.migDir)
		if err != nil {
			return nil, err
		}
		if err := migrate.EnsureTable(ctx, st); err != nil {
			return nil, err
		}
		applied, err := migrate.Applied(ctx, st)
		if err != nil {
			return nil, err
		}
		rows := make([]map[string]any, 0, len(all))
		for _, m := range all {
			rows = append(rows, map[string]any{"version": m.Version, "name": m.Name, "applied": applied[m.Version]})
		}
		return map[string]any{"migrations": rows}, nil
	})
	if err != nil {
		s.fail(w, r, http.StatusInternalServerError, err)
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (s *server) migrationsUp(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := s.migrationCtx(r)
	defer cancel()
	out, err := s.withStore(ctx, func(st *store.PgStore) (any, error) {
		all, err := migrate.LoadDir(s.migDir)
		if err != nil {
			return nil, err
		}
		if err := migrate.EnsureTable(ctx, st); err != nil {
			return nil, err
		}
		n, err := migrate.Up(ctx, st, all)
		if err != nil {
			return nil, err
		}
		return map[string]any{"applied": n}, nil
	})
	if err != nil {
		s.fail(w, r, http.StatusInternalServerError, err)
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (s *server) migrationsDown(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := s.migrationCtx(r)
	defer cancel()
	out, err := s.withStore(ctx, func(st *store.PgStore) (any, error) {
		all, err := migrate.LoadDir(s.migDir)
		if err != nil {
			return nil, err
		}
		if err := migrate.EnsureTable(ctx, st); err != nil {
			return nil, err
		}
		if err := migrate.Down(ctx, st, all); err != nil {
			return nil, err
		}
		return map[string]string{"result": "rolled back one migration"}, nil
	})
	if err != nil {
		s.fail(w, r, http.StatusInternalServerError, err)
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (s *server) schemaCheck(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := s.dbCtx(r)
	defer cancel()
	out, err := s.withStore(ctx, func(st *store.PgStore) (any, error) {
		expected, err := store.ExpectedFromDir(s.migDir)
		if err != nil {
			return nil, err
		}
		tables, indexes, err := store.LiveSchema(ctx, st)
		if err != nil {
			return nil, err
		}
		missingTables := store.Missing(expected.Tables, tables)
		missingIndexes := store.Missing(expected.Indexes, indexes)
		return map[string]any{
			"ok":              len(missingTables) == 0 && len(missingIndexes) == 0,
			"missing_tables":  missingTables,
			"missing_indexes": missingIndexes,
			"expected_tables": len(expected.Tables), "expected_indexes": len(expected.Indexes),
			"live_tables": len(tables), "live_indexes": len(indexes),
		}, nil
	})
	if err != nil {
		s.fail(w, r, http.StatusInternalServerError, err)
		return
	}
	code := http.StatusOK
	if m, ok := out.(map[string]any); ok && m["ok"] == false {
		code = http.StatusConflict
	}
	writeJSON(w, code, out)
}

func (s *server) objectStoreCapabilities(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, s.obj.Capabilities())
}

func (s *server) objectStoreConform(w http.ResponseWriter, r *http.Request) {
	errs := datastore.ConformObjectStore(r.Context(), s.obj)
	msgs := make([]string, 0, len(errs))
	for _, e := range errs {
		msgs = append(msgs, e.Error())
	}
	code := http.StatusOK
	if len(msgs) > 0 {
		code = http.StatusConflict
	}
	writeJSON(w, code, map[string]any{"ok": len(msgs) == 0, "errors": msgs})
}

var errTenant = errors.New("tenant query parameter is required")

func (s *server) artifactUpload(w http.ResponseWriter, r *http.Request) {
	if err := r.ParseMultipartForm(s.cfg.MaxUploadBytes); err != nil {
		s.fail(w, r, http.StatusBadRequest, err)
		return
	}
	tenant := r.FormValue("tenant")
	if tenant == "" {
		s.fail(w, r, http.StatusBadRequest, errTenant)
		return
	}
	f, hdr, err := r.FormFile("file")
	if err != nil {
		s.bad(w, r, http.StatusBadRequest, "file part required")
		return
	}
	defer f.Close()
	data, err := io.ReadAll(io.LimitReader(f, s.cfg.MaxUploadBytes+1))
	if err != nil {
		s.fail(w, r, http.StatusInternalServerError, err)
		return
	}
	if int64(len(data)) > s.cfg.MaxUploadBytes {
		s.bad(w, r, http.StatusRequestEntityTooLarge, "upload exceeds the configured limit")
		return
	}
	sum := sha256.Sum256(data)
	checksum := hex.EncodeToString(sum[:])
	if _, err := s.obj.Put(r.Context(), checksum, bytes.NewReader(data), int64(len(data)),
		datastore.PutOptions{ContentType: hdr.Header.Get("Content-Type")}); err != nil {
		s.fail(w, r, http.StatusInternalServerError, err)
		return
	}
	ctx, cancel := s.dbCtx(r)
	defer cancel()
	svc := artifacts.New(store.BindTenant(s.st, tenant), s.obj)
	a, err := svc.Register(ctx, datastore.Artifact{
		ID: r.FormValue("id"), TenantID: tenant, Project: r.FormValue("project"), Run: r.FormValue("run"),
		Stage: r.FormValue("stage"), Type: r.FormValue("type"), Checksum: checksum,
		Size: int64(len(data)), Version: checksum,
	})
	if err != nil {
		s.fail(w, r, http.StatusInternalServerError, err)
		return
	}
	writeJSON(w, http.StatusOK, a)
}

func (s *server) artifactRoute(w http.ResponseWriter, r *http.Request) {
	rest := strings.TrimPrefix(r.URL.Path, "/artifacts/")
	if strings.HasSuffix(rest, "/content") {
		s.artifactContent(w, r, strings.TrimSuffix(rest, "/content"))
		return
	}
	s.artifactGet(w, r, rest)
}

func (s *server) artifactSvc(r *http.Request) (*artifacts.Service, error) {
	tenant := r.URL.Query().Get("tenant")
	if tenant == "" {
		return nil, errTenant
	}
	return artifacts.New(store.BindTenant(s.st, tenant), s.obj), nil
}

func (s *server) artifactGet(w http.ResponseWriter, r *http.Request, id string) {
	svc, err := s.artifactSvc(r)
	if err != nil {
		s.fail(w, r, http.StatusBadRequest, err)
		return
	}
	a, err := svc.Get(r.Context(), id)
	if err != nil {
		s.bad(w, r, http.StatusNotFound, "artifact not found")
		return
	}
	writeJSON(w, http.StatusOK, a)
}

func (s *server) artifactContent(w http.ResponseWriter, r *http.Request, id string) {
	svc, err := s.artifactSvc(r)
	if err != nil {
		s.fail(w, r, http.StatusBadRequest, err)
		return
	}
	rc, err := svc.FetchContent(r.Context(), id)
	if err != nil {
		s.bad(w, r, http.StatusNotFound, "artifact not found")
		return
	}
	defer rc.Close()
	w.Header().Set("Content-Type", "application/octet-stream")
	_, _ = io.Copy(w, rc)
}

func (s *server) tenantStore(tenant string) (*store.PgStore, error) {
	return s.st, nil
}

func (s *server) auditAppend(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := s.dbCtx(r)
	defer cancel()
	var b struct {
		Tenant, Actor, Action, Resource, Outcome, CorrelationID string
	}
	if err := json.NewDecoder(r.Body).Decode(&b); err != nil {
		s.fail(w, r, http.StatusBadRequest, err)
		return
	}
	if b.Tenant == "" || b.Action == "" {
		s.bad(w, r, http.StatusBadRequest, "tenant and action are required")
		return
	}
	st, err := s.tenantStore(b.Tenant)
	if err != nil {
		s.fail(w, r, http.StatusInternalServerError, err)
		return
	}
	err = edpdata.NewAudit(store.BindTenant(st, b.Tenant)).Append(ctx, datastore.AuditEvent{
		TenantID: b.Tenant, Actor: b.Actor, Action: b.Action, Resource: b.Resource,
		Outcome: b.Outcome, CorrelationID: b.CorrelationID, At: time.Now(),
	})
	if err != nil {
		s.fail(w, r, http.StatusInternalServerError, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func (s *server) jobSubmit(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := s.dbCtx(r)
	defer cancel()
	var b struct {
		Tenant, ID, Kind, IdempotencyKey string
		Priority                         int
	}
	if err := json.NewDecoder(r.Body).Decode(&b); err != nil {
		s.fail(w, r, http.StatusBadRequest, err)
		return
	}
	if b.Tenant == "" || b.ID == "" {
		s.bad(w, r, http.StatusBadRequest, "tenant and id are required")
		return
	}
	st, err := s.tenantStore(b.Tenant)
	if err != nil {
		s.fail(w, r, http.StatusInternalServerError, err)
		return
	}
	j, err := edpdata.NewJobs(store.BindTenant(st, b.Tenant)).Submit(ctx, datastore.Job{
		ID: b.ID, TenantID: b.Tenant, Kind: b.Kind, Priority: b.Priority, IdempotencyKey: b.IdempotencyKey})
	if err != nil {
		s.fail(w, r, http.StatusInternalServerError, err)
		return
	}
	writeJSON(w, http.StatusOK, j)
}

func (s *server) jobClaim(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := s.dbCtx(r)
	defer cancel()
	var b struct {
		Tenant, Worker string
		TTLSeconds     int
	}
	if err := json.NewDecoder(r.Body).Decode(&b); err != nil {
		s.fail(w, r, http.StatusBadRequest, err)
		return
	}
	if b.Tenant == "" || b.Worker == "" {
		s.bad(w, r, http.StatusBadRequest, "tenant and worker are required")
		return
	}
	if b.TTLSeconds <= 0 {
		b.TTLSeconds = 60
	}
	st, err := s.tenantStore(b.Tenant)
	if err != nil {
		s.fail(w, r, http.StatusInternalServerError, err)
		return
	}
	j, ok, err := edpdata.NewJobs(store.BindTenant(st, b.Tenant)).Claim(ctx, b.Worker, time.Duration(b.TTLSeconds)*time.Second)
	if err != nil {
		s.fail(w, r, http.StatusInternalServerError, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"claimed": ok, "job": j})
}

func (s *server) jobAction(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := s.dbCtx(r)
	defer cancel()
	var b struct {
		Tenant, ID, Lease, Action, Reason string
	}
	if err := json.NewDecoder(r.Body).Decode(&b); err != nil {
		s.fail(w, r, http.StatusBadRequest, err)
		return
	}
	if b.Tenant == "" || b.ID == "" {
		s.bad(w, r, http.StatusBadRequest, "tenant and id are required")
		return
	}
	st, err := s.tenantStore(b.Tenant)
	if err != nil {
		s.fail(w, r, http.StatusInternalServerError, err)
		return
	}
	jobs := edpdata.NewJobs(store.BindTenant(st, b.Tenant))
	switch b.Action {
	case "complete":
		err = jobs.Complete(ctx, b.ID, b.Lease)
	case "fail":
		err = jobs.Fail(ctx, b.ID, b.Lease, b.Reason)
	case "release":
		err = jobs.Release(ctx, b.ID, b.Lease)
	case "heartbeat":
		err = jobs.Heartbeat(ctx, b.ID, b.Lease)
	default:
		s.bad(w, r, http.StatusBadRequest, "action must be complete|fail|release|heartbeat")
		return
	}
	if err != nil {
		s.fail(w, r, http.StatusInternalServerError, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func (s *server) memoryHandle(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := s.dbCtx(r)
	defer cancel()
	q := r.URL.Query()
	tenant := q.Get("tenant")
	st, err := s.tenantStore(tenant)
	if err != nil {
		s.fail(w, r, http.StatusInternalServerError, err)
		return
	}
	mem := edpdata.NewMemory(store.BindTenant(st, tenant))
	// The ACL principal is server-side (this admin API has one authenticated principal). Client-supplied
	// `owner`/`user` are never trusted.
	principal := envOr("PF_MEMORY_PRINCIPAL", "admin")
	switch r.Method {
	case http.MethodPost:
		var b struct {
			ID, Tenant, Project, Kind, ObjectRef, ACLScope string
			Content, Source, Owner                         string
			Embedding                                      []float32
		}
		if err := json.NewDecoder(r.Body).Decode(&b); err != nil {
			s.fail(w, r, http.StatusBadRequest, err)
			return
		}
		if b.ID == "" || b.Tenant == "" {
			s.bad(w, r, http.StatusBadRequest, "id and tenant are required")
			return
		}
		if b.Owner != "" && b.Owner != principal {
			s.bad(w, r, http.StatusForbidden, "owner is derived from the authenticated principal")
			return
		}
		e, err := mem.Put(ctx, datastore.MemoryEntry{ID: b.ID, TenantID: b.Tenant, Project: b.Project,
			Kind: b.Kind, ObjectRef: b.ObjectRef, ACLScope: b.ACLScope, Content: b.Content, Source: b.Source,
			Owner: principal, Embedding: b.Embedding})
		if err != nil {
			s.fail(w, r, http.StatusInternalServerError, err)
			return
		}
		writeJSON(w, http.StatusOK, e)
	case http.MethodGet:
		k := 20
		if v := q.Get("k"); v != "" {
			if n, convErr := strconv.Atoi(v); convErr == nil && n > 0 {
				k = n
			}
		}
		var kinds []string
		kv := strings.TrimSpace(q.Get("kinds"))
		if kv == "" {
			kv = strings.TrimSpace(q.Get("types"))
		}
		if kv != "" {
			for _, part := range strings.Split(kv, ",") {
				if p := strings.TrimSpace(part); p != "" {
					kinds = append(kinds, p)
				}
			}
		}
		// Backward compatible: `kind` used to be the free-text query.
		text := q.Get("q")
		if text == "" {
			text = q.Get("kind")
		}
		src, acl := q.Get("source"), ""
		if src == "private" || src == "project" || src == "tenant" || src == "shared" {
			acl, src = src, "" // legacy: `source` used to filter acl_scope
		}
		hits, err := mem.Search(ctx, text, datastore.MemoryScope{
			TenantID: tenant, Project: q.Get("project"), Source: src, ACL: acl,
			User: principal, Kinds: kinds}, k)
		if err != nil {
			s.fail(w, r, http.StatusInternalServerError, err)
			return
		}
		writeJSON(w, http.StatusOK, map[string]any{"hits": hits})
	default:
		s.bad(w, r, http.StatusMethodNotAllowed, "use GET or POST")
	}
}

func (s *server) memoryByID(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := s.dbCtx(r)
	defer cancel()
	id := strings.TrimPrefix(r.URL.Path, "/memory/")
	tenant := r.URL.Query().Get("tenant")
	st, err := s.tenantStore(tenant)
	if err != nil {
		s.fail(w, r, http.StatusInternalServerError, err)
		return
	}
	mem := edpdata.NewMemory(store.BindTenant(st, tenant))
	principal := envOr("PF_MEMORY_PRINCIPAL", "admin")
	visible := func(e datastore.MemoryEntry) bool { return e.ACLScope != "private" || e.Owner == principal }
	e, err := mem.Get(ctx, id)
	if err != nil || !visible(e) {
		s.bad(w, r, http.StatusNotFound, "not found")
		return
	}
	if r.Method == http.MethodDelete {
		if err := mem.Delete(ctx, id); err != nil {
			s.fail(w, r, http.StatusNotFound, err)
			return
		}
		writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
		return
	}
	writeJSON(w, http.StatusOK, e)
}

func (s *server) backlogHandle(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := s.dbCtx(r)
	defer cancel()
	q := r.URL.Query()
	tenant := q.Get("tenant")
	st, err := s.tenantStore(tenant)
	if err != nil {
		s.fail(w, r, http.StatusInternalServerError, err)
		return
	}
	bl := edpdata.NewBacklog(store.BindTenant(st, tenant))
	switch r.Method {
	case http.MethodPost:
		var b struct {
			ID, Tenant, Type, Status, Title, Body string
			Data                                  json.RawMessage
		}
		if err := json.NewDecoder(r.Body).Decode(&b); err != nil {
			s.fail(w, r, http.StatusBadRequest, err)
			return
		}
		if b.ID == "" || b.Tenant == "" {
			s.bad(w, r, http.StatusBadRequest, "id and tenant are required")
			return
		}
		it, err := bl.Put(ctx, edpdata.BacklogItem{ID: b.ID, TenantID: b.Tenant, Type: b.Type,
			Status: b.Status, Title: b.Title, Body: b.Body, Data: b.Data})
		if err != nil {
			s.fail(w, r, http.StatusInternalServerError, err)
			return
		}
		writeJSON(w, http.StatusOK, it)
	case http.MethodGet:
		limit := 50
		if v := q.Get("limit"); v != "" {
			if n, e := strconv.Atoi(v); e == nil && n > 0 {
				limit = n
			}
		}
		items, err := bl.List(ctx, q.Get("status"), limit)
		if err != nil {
			s.fail(w, r, http.StatusInternalServerError, err)
			return
		}
		writeJSON(w, http.StatusOK, map[string]any{"items": items})
	default:
		s.bad(w, r, http.StatusMethodNotAllowed, "use GET or POST")
	}
}

func (s *server) backlogByID(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := s.dbCtx(r)
	defer cancel()
	id := strings.TrimPrefix(r.URL.Path, "/backlog/")
	tenant := r.URL.Query().Get("tenant")
	st, err := s.tenantStore(tenant)
	if err != nil {
		s.fail(w, r, http.StatusInternalServerError, err)
		return
	}
	bl := edpdata.NewBacklog(store.BindTenant(st, tenant))
	if r.Method == http.MethodDelete {
		if err := bl.Delete(ctx, id); err != nil {
			s.fail(w, r, http.StatusNotFound, err)
			return
		}
		writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
		return
	}
	it, err := bl.Get(ctx, id)
	if err != nil {
		s.fail(w, r, http.StatusNotFound, err)
		return
	}
	writeJSON(w, http.StatusOK, it)
}

func (s *server) dbCtx(r *http.Request) (context.Context, context.CancelFunc) {
	return context.WithTimeout(r.Context(), s.cfg.DBTimeout)
}

// migrationCtx bounds DDL with the (longer) migration timeout, not the per-query DB timeout.
func (s *server) migrationCtx(r *http.Request) (context.Context, context.CancelFunc) {
	return context.WithTimeout(r.Context(), s.cfg.MigrationTimeout)
}

func (s *server) bad(w http.ResponseWriter, r *http.Request, status int, msg string) {
	limits.WriteError(w, r, status, msg)
}

func (s *server) fail(w http.ResponseWriter, r *http.Request, status int, err error) {
	if err == nil {
		s.bad(w, r, status, "request failed")
		return
	}
	var mbe *http.MaxBytesError
	if errors.As(err, &mbe) {
		limits.WriteError(w, r, http.StatusRequestEntityTooLarge, "request body exceeds the configured limit")
		return
	}
	if errors.Is(err, context.DeadlineExceeded) || errors.Is(err, context.Canceled) {
		limits.WriteHandlerError(w, r, err)
		return
	}
	if status >= http.StatusInternalServerError {
		log.Printf("edpsvc: %s %s: %s", r.Method, r.URL.Path, limits.Redact(err.Error()))
		limits.WriteError(w, r, status, "internal error")
		return
	}
	limits.WriteError(w, r, status, err.Error())
}

func (s *server) ready(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), s.cfg.DBTimeout)
	defer cancel()
	if err := s.st.Ping(ctx); err != nil {
		limits.WriteError(w, r, http.StatusServiceUnavailable, "database unavailable")
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"status": "ready"})
}

func (s *server) metricsHandler(w http.ResponseWriter, r *http.Request) {
	for k, v := range s.poolStats() {
		s.metrics.Set("edp_db_pool_"+k, int(v))
	}
	s.metrics.Set("edp_quota_tenant_buckets", s.quota.TenantBuckets())
	w.Header().Set("Content-Type", "text/plain; version=0.0.4")
	s.metrics.Write(w)
}

func (s *server) poolStats() map[string]int32 {
	if s.st == nil {
		return map[string]int32{}
	}
	return s.st.Stats()
}

func (s *server) adminLimits(w http.ResponseWriter, r *http.Request) {
	role := s.role.Role()
	writeJSON(w, http.StatusOK, map[string]any{
		"profile": s.cfg.Profile,
		"enforce": s.cfg.Enforce,
		"timeouts": map[string]string{
			"request": s.cfg.RequestTimeout.String(), "db": s.cfg.DBTimeout.String(),
			"upload": s.cfg.UploadTimeout.String(), "read": s.cfg.ReadTimeout.String(),
			"write": s.cfg.WriteTimeout.String(), "idle": s.cfg.IdleTimeout.String(),
		},
		"limits": map[string]any{
			"max_body_bytes": s.cfg.MaxBodyBytes, "max_upload_bytes": s.cfg.MaxUploadBytes,
			"tenant_rpm": s.cfg.TenantRPM, "global_rpm": s.cfg.GlobalRPM,
			"tenant_concurrency": s.cfg.TenantConcurrency, "global_concurrency": s.cfg.GlobalConcurrency,
			"max_tenant_buckets": s.cfg.MaxTenantBuckets,
		},
		"pool":           s.poolStats(),
		"tenant_buckets": s.quota.TenantBuckets(),
		"role": map[string]any{"name": role.Name, "superuser": role.Superuser,
			"bypassrls": role.BypassRLS, "ok": s.role.OK(), "last_check_unix": s.role.LastCheck()},
	})
}

func writeJSON(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("X-EDP-Service", "edpsvc")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(v)
}
