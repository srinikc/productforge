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
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"productforge/artifacts"
	"productforge/datastore"
	"productforge/edpdata"
	"productforge/migrate"
	"productforge/objstore"
	"productforge/s3store"
	"productforge/store"
)

type server struct {
	dsn    string
	admin  string
	migDir string
	obj    datastore.ObjectStore
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
	s := &server{dsn: os.Getenv("PF_DB_DSN"), admin: os.Getenv("PF_ADMIN_TOKEN"),
		migDir: envOr("PF_MIGRATIONS_DIR", findMigrations())}
	if s.dsn == "" {
		log.Fatal("PF_DB_DSN is required")
	}
	if s.admin == "" {
		log.Fatal("PF_ADMIN_TOKEN is required")
	}
	obj, err := buildObjectStore()
	if err != nil {
		log.Fatalf("object store: %v", err)
	}
	s.obj = obj
	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
	})
	mux.HandleFunc("/admin/migrations/status", s.adminOnly(s.migrationsStatus))
	mux.HandleFunc("/admin/migrations/up", s.adminOnly(s.migrationsUp))
	mux.HandleFunc("/admin/migrations/down", s.adminOnly(s.migrationsDown))
	mux.HandleFunc("/admin/schema-check", s.adminOnly(s.schemaCheck))
	mux.HandleFunc("/admin/object-store/capabilities", s.adminOnly(s.objectStoreCapabilities))
	mux.HandleFunc("/admin/object-store/conform", s.adminOnly(s.objectStoreConform))
	mux.HandleFunc("/artifacts", s.adminOnly(s.artifactUpload))
	mux.HandleFunc("/artifacts/", s.adminOnly(s.artifactRoute))
	mux.HandleFunc("/audit", s.adminOnly(s.auditAppend))
	mux.HandleFunc("/admin/audit-coverage", s.adminOnly(s.auditCoverage))
	mux.HandleFunc("/jobs", s.adminOnly(s.jobSubmit))
	mux.HandleFunc("/jobs/claim", s.adminOnly(s.jobClaim))
	mux.HandleFunc("/jobs/action", s.adminOnly(s.jobAction))
	mux.HandleFunc("/memory", s.adminOnly(s.memoryHandle))
	mux.HandleFunc("/memory/", s.adminOnly(s.memoryByID))
	mux.HandleFunc("/backlog", s.adminOnly(s.backlogHandle))
	mux.HandleFunc("/backlog/", s.adminOnly(s.backlogByID))
	// AC: surface coverage non-fatally at startup (a stale/low rotation must not stop the service).
	s.checkAuditCoverage()
	addr := envOr("PF_EDP_ADDR", "127.0.0.1:8030")
	log.Printf("edpsvc listening on %s (migrations=%s)", addr, s.migDir)
	log.Fatal(http.ListenAndServe(addr, mux))
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
		writeJSON(w, http.StatusServiceUnavailable, map[string]string{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"months_ahead": st.MonthsAhead, "lead_months": st.LeadMonths, "low": st.Low(),
		"last_rotation_hours": st.LastRotationHours, "stale": st.Stale,
	})
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
		if !strings.HasPrefix(auth, "Bearer ") || strings.TrimSpace(strings.TrimPrefix(auth, "Bearer ")) != s.admin {
			writeJSON(w, http.StatusUnauthorized, map[string]string{"error": "admin authorization required"})
			return
		}
		fn(w, r)
	}
}

func (s *server) withStore(ctx context.Context, fn func(*store.PgStore) (any, error)) (any, error) {
	st, err := store.Open(ctx, s.dsn)
	if err != nil {
		return nil, err
	}
	defer st.Close()
	return fn(st)
}

func (s *server) migrationsStatus(w http.ResponseWriter, r *http.Request) {
	ctx := context.Background()
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
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (s *server) migrationsUp(w http.ResponseWriter, r *http.Request) {
	ctx := context.Background()
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
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (s *server) migrationsDown(w http.ResponseWriter, r *http.Request) {
	ctx := context.Background()
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
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (s *server) schemaCheck(w http.ResponseWriter, r *http.Request) {
	ctx := context.Background()
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
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
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
	errs := datastore.ConformObjectStore(context.Background(), s.obj)
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
	if err := r.ParseMultipartForm(64 << 20); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "multipart body required"})
		return
	}
	tenant := r.FormValue("tenant")
	if tenant == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": errTenant.Error()})
		return
	}
	f, hdr, err := r.FormFile("file")
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "file part required"})
		return
	}
	defer f.Close()
	data, err := io.ReadAll(io.LimitReader(f, 64<<20))
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}
	ctx := context.Background()
	sum := sha256.Sum256(data)
	checksum := hex.EncodeToString(sum[:])
	if _, err := s.obj.Put(ctx, checksum, bytes.NewReader(data), int64(len(data)),
		datastore.PutOptions{ContentType: hdr.Header.Get("Content-Type")}); err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}
	st, err := store.Open(ctx, s.dsn)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}
	defer st.Close()
	svc := artifacts.New(store.BindTenant(st, tenant), s.obj)
	a, err := svc.Register(ctx, datastore.Artifact{
		ID: r.FormValue("id"), TenantID: tenant, Project: r.FormValue("project"), Run: r.FormValue("run"),
		Stage: r.FormValue("stage"), Type: r.FormValue("type"), Checksum: checksum,
		Size: int64(len(data)), Version: checksum,
	})
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
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

func (s *server) artifactSvc(r *http.Request) (*artifacts.Service, func(), error) {
	tenant := r.URL.Query().Get("tenant")
	if tenant == "" {
		return nil, nil, errTenant
	}
	st, err := store.Open(context.Background(), s.dsn)
	if err != nil {
		return nil, nil, err
	}
	return artifacts.New(store.BindTenant(st, tenant), s.obj), st.Close, nil
}

func (s *server) artifactGet(w http.ResponseWriter, r *http.Request, id string) {
	svc, closeFn, err := s.artifactSvc(r)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}
	defer closeFn()
	a, err := svc.Get(r.Context(), id)
	if err != nil {
		writeJSON(w, http.StatusNotFound, map[string]string{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, a)
}

func (s *server) artifactContent(w http.ResponseWriter, r *http.Request, id string) {
	svc, closeFn, err := s.artifactSvc(r)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}
	defer closeFn()
	rc, err := svc.FetchContent(r.Context(), id)
	if err != nil {
		writeJSON(w, http.StatusNotFound, map[string]string{"error": err.Error()})
		return
	}
	defer rc.Close()
	w.Header().Set("Content-Type", "application/octet-stream")
	_, _ = io.Copy(w, rc)
}

func (s *server) tenantStore(tenant string) (*store.PgStore, error) {
	st, err := store.Open(context.Background(), s.dsn)
	return st, err
}

func (s *server) auditAppend(w http.ResponseWriter, r *http.Request) {
	var b struct {
		Tenant, Actor, Action, Resource, Outcome, CorrelationID string
	}
	if err := json.NewDecoder(r.Body).Decode(&b); err != nil || b.Tenant == "" || b.Action == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "tenant and action are required"})
		return
	}
	st, err := s.tenantStore(b.Tenant)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}
	defer st.Close()
	err = edpdata.NewAudit(store.BindTenant(st, b.Tenant)).Append(r.Context(), datastore.AuditEvent{
		TenantID: b.Tenant, Actor: b.Actor, Action: b.Action, Resource: b.Resource,
		Outcome: b.Outcome, CorrelationID: b.CorrelationID, At: time.Now(),
	})
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func (s *server) jobSubmit(w http.ResponseWriter, r *http.Request) {
	var b struct {
		Tenant, ID, Kind, IdempotencyKey string
		Priority                         int
	}
	if err := json.NewDecoder(r.Body).Decode(&b); err != nil || b.Tenant == "" || b.ID == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "tenant and id are required"})
		return
	}
	st, err := s.tenantStore(b.Tenant)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}
	defer st.Close()
	j, err := edpdata.NewJobs(store.BindTenant(st, b.Tenant)).Submit(r.Context(), datastore.Job{
		ID: b.ID, TenantID: b.Tenant, Kind: b.Kind, Priority: b.Priority, IdempotencyKey: b.IdempotencyKey})
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, j)
}

func (s *server) jobClaim(w http.ResponseWriter, r *http.Request) {
	var b struct {
		Tenant, Worker string
		TTLSeconds     int
	}
	if err := json.NewDecoder(r.Body).Decode(&b); err != nil || b.Tenant == "" || b.Worker == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "tenant and worker are required"})
		return
	}
	if b.TTLSeconds <= 0 {
		b.TTLSeconds = 60
	}
	st, err := s.tenantStore(b.Tenant)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}
	defer st.Close()
	j, ok, err := edpdata.NewJobs(store.BindTenant(st, b.Tenant)).Claim(r.Context(), b.Worker, time.Duration(b.TTLSeconds)*time.Second)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"claimed": ok, "job": j})
}

func (s *server) jobAction(w http.ResponseWriter, r *http.Request) {
	var b struct {
		Tenant, ID, Lease, Action, Reason string
	}
	if err := json.NewDecoder(r.Body).Decode(&b); err != nil || b.Tenant == "" || b.ID == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "tenant and id are required"})
		return
	}
	st, err := s.tenantStore(b.Tenant)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}
	defer st.Close()
	jobs := edpdata.NewJobs(store.BindTenant(st, b.Tenant))
	switch b.Action {
	case "complete":
		err = jobs.Complete(r.Context(), b.ID, b.Lease)
	case "fail":
		err = jobs.Fail(r.Context(), b.ID, b.Lease, b.Reason)
	case "release":
		err = jobs.Release(r.Context(), b.ID, b.Lease)
	case "heartbeat":
		err = jobs.Heartbeat(r.Context(), b.ID, b.Lease)
	default:
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "action must be complete|fail|release|heartbeat"})
		return
	}
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func (s *server) memoryHandle(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	tenant := q.Get("tenant")
	st, err := s.tenantStore(tenant)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}
	defer st.Close()
	mem := edpdata.NewMemory(store.BindTenant(st, tenant))
	switch r.Method {
	case http.MethodPost:
		var b struct {
			ID, Tenant, Project, Kind, ObjectRef, ACLScope string
			Content, Source, Owner                         string
			Embedding                                      []float32
		}
		if err := json.NewDecoder(r.Body).Decode(&b); err != nil || b.ID == "" || b.Tenant == "" {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "id and tenant are required"})
			return
		}
		e, err := mem.Put(r.Context(), datastore.MemoryEntry{ID: b.ID, TenantID: b.Tenant, Project: b.Project,
			Kind: b.Kind, ObjectRef: b.ObjectRef, ACLScope: b.ACLScope, Content: b.Content, Source: b.Source,
			Owner: b.Owner, Embedding: b.Embedding})
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
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
		if v := strings.TrimSpace(q.Get("types")); v != "" {
			for _, part := range strings.Split(v, ",") {
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
		hits, err := mem.Search(r.Context(), text, datastore.MemoryScope{
			TenantID: tenant, Project: q.Get("project"), Source: q.Get("source"),
			User: q.Get("user"), Kinds: kinds}, k)
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
			return
		}
		writeJSON(w, http.StatusOK, map[string]any{"hits": hits})
	default:
		writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "use GET or POST"})
	}
}

func (s *server) memoryByID(w http.ResponseWriter, r *http.Request) {
	id := strings.TrimPrefix(r.URL.Path, "/memory/")
	tenant := r.URL.Query().Get("tenant")
	st, err := s.tenantStore(tenant)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}
	defer st.Close()
	mem := edpdata.NewMemory(store.BindTenant(st, tenant))
	if r.Method == http.MethodDelete {
		if err := mem.Delete(r.Context(), id); err != nil {
			writeJSON(w, http.StatusNotFound, map[string]string{"error": err.Error()})
			return
		}
		writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
		return
	}
	e, err := mem.Get(r.Context(), id)
	if err != nil {
		writeJSON(w, http.StatusNotFound, map[string]string{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, e)
}

func (s *server) backlogHandle(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	tenant := q.Get("tenant")
	st, err := s.tenantStore(tenant)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}
	defer st.Close()
	bl := edpdata.NewBacklog(store.BindTenant(st, tenant))
	switch r.Method {
	case http.MethodPost:
		var b struct {
			ID, Tenant, Type, Status, Title, Body string
			Data                                  json.RawMessage
		}
		if err := json.NewDecoder(r.Body).Decode(&b); err != nil || b.ID == "" || b.Tenant == "" {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "id and tenant are required"})
			return
		}
		it, err := bl.Put(r.Context(), edpdata.BacklogItem{ID: b.ID, TenantID: b.Tenant, Type: b.Type,
			Status: b.Status, Title: b.Title, Body: b.Body, Data: b.Data})
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
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
		items, err := bl.List(r.Context(), q.Get("status"), limit)
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
			return
		}
		writeJSON(w, http.StatusOK, map[string]any{"items": items})
	default:
		writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "use GET or POST"})
	}
}

func (s *server) backlogByID(w http.ResponseWriter, r *http.Request) {
	id := strings.TrimPrefix(r.URL.Path, "/backlog/")
	tenant := r.URL.Query().Get("tenant")
	st, err := s.tenantStore(tenant)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}
	defer st.Close()
	bl := edpdata.NewBacklog(store.BindTenant(st, tenant))
	if r.Method == http.MethodDelete {
		if err := bl.Delete(r.Context(), id); err != nil {
			writeJSON(w, http.StatusNotFound, map[string]string{"error": err.Error()})
			return
		}
		writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
		return
	}
	it, err := bl.Get(r.Context(), id)
	if err != nil {
		writeJSON(w, http.StatusNotFound, map[string]string{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, it)
}

func writeJSON(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("X-EDP-Service", "edpsvc")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(v)
}
