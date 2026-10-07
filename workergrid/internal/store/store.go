// Package store is the WorkerGrid coordination store (SQLite) - the Go port of
// workergrid/store.py (BI-PF-0412). Owns workers + leases; producer-agnostic;
// single writer (this process). Schema and JSON shapes are pinned by the
// cross-impl contract suite (test_workergrid_service_contract.py).
//
// Claim atomicity: the Python spike uses BEGIN IMMEDIATE; here a store-wide
// mutex plus a single-connection database serializes check-then-claim the same
// way (the coordinator is one process; a second process on the same file is
// not a supported topology).
package store

import (
	"context"
	"database/sql"
	"fmt"
	"strings"
	"sync"
	"time"

	_ "modernc.org/sqlite"
)

const schema = `
CREATE TABLE IF NOT EXISTS workers (
  worker_id TEXT PRIMARY KEY,
  runtime TEXT,
  capabilities TEXT,
  role TEXT,
  status TEXT,
  registered_at REAL,
  last_heartbeat REAL,
  current_assignment TEXT
);
CREATE TABLE IF NOT EXISTS leases (
  item_id TEXT PRIMARY KEY,
  worker_id TEXT,
  runtime TEXT,
  assignment_id TEXT,
  expires_at REAL,
  created_at REAL
);`

// Worker mirrors a workers row (capabilities stays a CSV string, like Python).
type Worker struct {
	WorkerID          string  `json:"worker_id"`
	Runtime           string  `json:"runtime"`
	Capabilities      string  `json:"capabilities"`
	Role              string  `json:"role"`
	Status            string  `json:"status"`
	RegisteredAt      float64 `json:"registered_at"`
	LastHeartbeat     float64 `json:"last_heartbeat"`
	CurrentAssignment string  `json:"current_assignment"`
}

// Store coordinates workers and leases over a SQLite file.
type Store struct {
	db    *sql.DB
	mu    sync.Mutex
	ttl   func() int
	ctxbg context.Context
}

// Open creates/opens state/workergrid.db under stateDir and ensures the schema.
func Open(stateDir string, ttl func() int) (*Store, error) {
	dsn := stateDir + "/workergrid.db"
	db, err := sql.Open("sqlite", dsn)
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(1)
	if _, err := db.Exec(schema); err != nil {
		db.Close()
		return nil, err
	}
	if ttl == nil {
		ttl = func() int { return 3600 }
	}
	return &Store{db: db, ttl: ttl, ctxbg: context.Background()}, nil
}

func (s *Store) Close() error { return s.db.Close() }

func now() float64 { return float64(time.Now().UnixNano()) / 1e9 }

// ── workers ─────────────────────────────────────────────────────────────────

// Register upserts a worker (conflict -> refresh runtime/caps/role, ONLINE,
// new heartbeat; registered_at keeps its original value - Python parity).
func (s *Store) Register(workerID, runtime string, capabilities []string, role string) (*Worker, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	wid := strings.TrimSpace(workerID)
	if wid == "" {
		rt := runtime
		if rt == "" {
			rt = "worker"
		}
		wid = fmt.Sprintf("WRK-%s-%d", rt, int(now())%100000000)
	}
	caps := strings.Join(capabilities, ",")
	_, err := s.db.Exec(`
INSERT INTO workers(worker_id,runtime,capabilities,role,status,registered_at,last_heartbeat,current_assignment)
VALUES(?,?,?,?,?,?,?,'')
ON CONFLICT(worker_id) DO UPDATE SET runtime=excluded.runtime,
 capabilities=excluded.capabilities, role=excluded.role, status='ONLINE',
 last_heartbeat=excluded.last_heartbeat`,
		wid, runtime, caps, role, "ONLINE", now(), now())
	if err != nil {
		return nil, err
	}
	return s.getLocked(wid)
}

// Get returns a worker or nil (not found).
func (s *Store) Get(workerID string) (*Worker, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.getLocked(workerID)
}

func (s *Store) getLocked(workerID string) (*Worker, error) {
	row := s.db.QueryRow(`SELECT worker_id,runtime,capabilities,role,status,
 registered_at,last_heartbeat,current_assignment FROM workers WHERE worker_id=?`, workerID)
	var w Worker
	if err := row.Scan(&w.WorkerID, &w.Runtime, &w.Capabilities, &w.Role, &w.Status,
		&w.RegisteredAt, &w.LastHeartbeat, &w.CurrentAssignment); err != nil {
		if err == sql.ErrNoRows {
			return nil, nil
		}
		return nil, err
	}
	return &w, nil
}

// ListWorkers returns all workers ordered by registered_at.
func (s *Store) ListWorkers() ([]Worker, error) {
	rows, err := s.db.Query(`SELECT worker_id,runtime,capabilities,role,status,
 registered_at,last_heartbeat,current_assignment FROM workers ORDER BY registered_at`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	return scanWorkers(rows)
}

// Heartbeat refreshes liveness; empty status/current keep previous values
// (Python: `status or w["status"]`). Unknown worker -> ok=false + reason.
func (s *Store) Heartbeat(workerID, status, current string) (map[string]any, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	w, err := s.getLocked(workerID)
	if err != nil {
		return nil, err
	}
	if w == nil {
		return map[string]any{"ok": false, "reason": "unknown worker"}, nil
	}
	newStatus, newCurrent := w.Status, w.CurrentAssignment
	if status != "" {
		newStatus = status
	}
	if current != "" {
		newCurrent = current
	}
	_, err = s.db.Exec(`UPDATE workers SET last_heartbeat=?, status=?, current_assignment=? WHERE worker_id=?`,
		now(), newStatus, newCurrent, workerID)
	if err != nil {
		return nil, err
	}
	return map[string]any{"ok": true, "worker_id": workerID}, nil
}

// Unregister removes the worker and any of its leases.
func (s *Store) Unregister(workerID string) (map[string]any, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	res, err := s.db.Exec(`DELETE FROM workers WHERE worker_id=?`, workerID)
	if err != nil {
		return nil, err
	}
	n, _ := res.RowsAffected()
	if _, err := s.db.Exec(`DELETE FROM leases WHERE worker_id=?`, workerID); err != nil {
		return nil, err
	}
	return map[string]any{"removed": n > 0, "worker_id": workerID}, nil
}

// ── leases ──────────────────────────────────────────────────────────────────

// Claim atomically takes the lease for itemID (assignment ASG-<item>) and marks
// the worker BUSY. A live lease held by anyone -> claimed=false + reason.
func (s *Store) Claim(itemID, workerID, runtime string) (map[string]any, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	secs := s.ttl()
	t := now()
	var holder, expires any
	err := s.db.QueryRow(`SELECT worker_id, expires_at FROM leases WHERE item_id=?`, itemID).
		Scan(&holder, &expires)
	if err != nil && err != sql.ErrNoRows {
		return nil, err
	}
	if err == nil {
		if e, ok := expires.(float64); ok && e > t {
			return map[string]any{
				"claimed": false,
				"reason":  fmt.Sprintf("already leased by %v", holder),
			}, nil
		}
	}
	asg := "ASG-" + itemID
	tx, err := s.db.Begin()
	if err != nil {
		return nil, err
	}
	_, err = tx.Exec(`INSERT INTO leases(item_id,worker_id,runtime,assignment_id,expires_at,created_at)
 VALUES(?,?,?,?,?,?) ON CONFLICT(item_id) DO UPDATE SET worker_id=excluded.worker_id,
 runtime=excluded.runtime, assignment_id=excluded.assignment_id,
 expires_at=excluded.expires_at, created_at=excluded.created_at`,
		itemID, workerID, runtime, asg, t+float64(secs), t)
	if err == nil {
		_, err = tx.Exec(`UPDATE workers SET status='BUSY', current_assignment=? WHERE worker_id=?`,
			itemID, workerID)
	}
	if err != nil {
		_ = tx.Rollback()
		return nil, err
	}
	if err := tx.Commit(); err != nil {
		return nil, err
	}
	return map[string]any{
		"claimed":       true,
		"item_id":       itemID,
		"worker_id":     workerID,
		"assignment_id": asg,
		"expires_at":    t + float64(secs),
	}, nil
}

// Renew extends a lease; unknown item -> renewed=false.
func (s *Store) Renew(itemID string) (map[string]any, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	res, err := s.db.Exec(`UPDATE leases SET expires_at=? WHERE item_id=?`, now()+float64(s.ttl()), itemID)
	if err != nil {
		return nil, err
	}
	n, _ := res.RowsAffected()
	return map[string]any{"renewed": n > 0, "item_id": itemID}, nil
}

// Release drops the lease and frees its worker (IDLE); always released=true
// (Python parity - releasing an unknown lease is a no-op success).
func (s *Store) Release(itemID string) (map[string]any, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	var holder any
	err := s.db.QueryRow(`SELECT worker_id FROM leases WHERE item_id=?`, itemID).Scan(&holder)
	if err != nil && err != sql.ErrNoRows {
		return nil, err
	}
	if _, err := s.db.Exec(`DELETE FROM leases WHERE item_id=?`, itemID); err != nil {
		return nil, err
	}
	if err == nil && holder != nil {
		if _, err := s.db.Exec(`UPDATE workers SET status='IDLE', current_assignment='' WHERE worker_id=?`,
			holder); err != nil {
			return nil, err
		}
	}
	return map[string]any{"released": true, "item_id": itemID}, nil
}

// ListLeases returns all leases ordered by created_at.
func (s *Store) ListLeases() ([]map[string]any, error) {
	rows, err := s.db.Query(`SELECT item_id,worker_id,runtime,assignment_id,expires_at,created_at
 FROM leases ORDER BY created_at`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []map[string]any{}
	for rows.Next() {
		var itemID, w, rt, asg string
		var expires, created float64
		if err := rows.Scan(&itemID, &w, &rt, &asg, &expires, &created); err != nil {
			return nil, err
		}
		out = append(out, map[string]any{
			"item_id": itemID, "worker_id": w, "runtime": rt,
			"assignment_id": asg, "expires_at": expires, "created_at": created,
		})
	}
	return out, rows.Err()
}

// RecoverExpired frees expired leases and their workers; returns the result
// dict {"recovered": [...], "count": n} (Python parity).
func (s *Store) RecoverExpired() (map[string]any, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	t := now()
	rows, err := s.db.Query(`SELECT item_id, worker_id FROM leases WHERE expires_at < ?`, t)
	if err != nil {
		return nil, err
	}
	recovered := []string{}
	holders := []any{}
	for rows.Next() {
		var itemID, w string
		if err := rows.Scan(&itemID, &w); err != nil {
			rows.Close()
			return nil, err
		}
		recovered = append(recovered, itemID)
		holders = append(holders, w)
	}
	if err := rows.Err(); err != nil {
		rows.Close()
		return nil, err
	}
	rows.Close()
	for _, h := range holders {
		if _, err := s.db.Exec(`UPDATE workers SET status='IDLE', current_assignment='' WHERE worker_id=?`,
			h); err != nil {
			return nil, err
		}
	}
	if _, err := s.db.Exec(`DELETE FROM leases WHERE expires_at < ?`, t); err != nil {
		return nil, err
	}
	return map[string]any{"recovered": recovered, "count": len(recovered)}, nil
}

// Count returns (workers, leases) for GET /status.
func (s *Store) Count() (int, int, error) {
	var w, l int
	if err := s.db.QueryRow(`SELECT COUNT(*) FROM workers`).Scan(&w); err != nil {
		return 0, 0, err
	}
	if err := s.db.QueryRow(`SELECT COUNT(*) FROM leases`).Scan(&l); err != nil {
		return 0, 0, err
	}
	return w, l, nil
}

func scanWorkers(rows *sql.Rows) ([]Worker, error) {
	out := []Worker{}
	for rows.Next() {
		var w Worker
		if err := rows.Scan(&w.WorkerID, &w.Runtime, &w.Capabilities, &w.Role, &w.Status,
			&w.RegisteredAt, &w.LastHeartbeat, &w.CurrentAssignment); err != nil {
			return nil, err
		}
		out = append(out, w)
	}
	return out, rows.Err()
}
