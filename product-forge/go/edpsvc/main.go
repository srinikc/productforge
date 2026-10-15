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
	"context"
	"encoding/json"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strings"

	"productforge/datastore"
	"productforge/migrate"
	"productforge/objstore"
	"productforge/store"
)

type server struct {
	dsn    string
	admin  string
	migDir string
	obj    *objstore.LocalStore
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
	objRoot := envOr("PF_OBJECT_ROOT", "data/local/objects")
	obj, err := objstore.NewLocalStore(objRoot, 0)
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
	addr := envOr("PF_EDP_ADDR", "127.0.0.1:8030")
	log.Printf("edpsvc listening on %s (migrations=%s)", addr, s.migDir)
	log.Fatal(http.ListenAndServe(addr, mux))
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

func writeJSON(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("X-EDP-Service", "edpsvc")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(v)
}
