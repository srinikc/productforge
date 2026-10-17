// Package edpdata implements the EDP data-plane service ports over the relational system of record:
// AuditStore (append-only), JobStore (lease-based) and OutboxStore (transactional outbox).
// It composes the provider-neutral datastore ports only; callers establish the tenant/RLS context.
package edpdata

import (
	"context"
	"errors"
	"regexp"
	"time"

	"productforge/datastore"
)

var (
	emailPII = regexp.MustCompile(`[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}`)
	secretPII = regexp.MustCompile(`(?i)\b(bearer|token|secret|password)\b\s*[:=]?\s*[A-Za-z0-9._\-]{6,}`)
)

// redact masks PII/sensitive values at INGEST (evidence must never be mutated afterwards). BI-PF-1312.
func redact(s string) string {
	s = emailPII.ReplaceAllString(s, "[redacted-email]")
	return secretPII.ReplaceAllString(s, "[redacted-secret]")
}

// ErrNotFound is returned when a row does not exist.
var ErrNotFound = errors.New("edpdata: not found")

// ---- AuditStore (append-only) ----

// AuditStore persists append-only audit events.
type AuditStore struct{ db datastore.RelationalStore }

// NewAudit returns an AuditStore over db.
func NewAudit(db datastore.RelationalStore) *AuditStore { return &AuditStore{db: db} }

// Append writes one audit event with INGEST-TIME redaction (PII masked before write). The table denies
// UPDATE/DELETE (append-only trigger) - evidence is immutable once written.
func (s *AuditStore) Append(ctx context.Context, e datastore.AuditEvent) error {
	return s.db.WithTx(ctx, func(tx datastore.Tx) error {
		_, err := tx.Exec(ctx,
			`INSERT INTO audit (tenant_id, actor, action, resource, outcome, correlation_id, at)
			 VALUES ($1,$2,$3,$4,$5,$6,$7)`,
			e.TenantID, redact(e.Actor), redact(e.Action), redact(e.Resource), redact(e.Outcome),
			redact(e.CorrelationID), e.At)
		return err
	})
}

// ---- JobStore (lease-based) ----

// JobStore persists durable jobs with leases.
type JobStore struct{ db datastore.RelationalStore }

// NewJobs returns a JobStore over db.
func NewJobs(db datastore.RelationalStore) *JobStore { return &JobStore{db: db} }

// Submit creates a job (idempotent on idempotency_key per tenant).
func (s *JobStore) Submit(ctx context.Context, j datastore.Job) (datastore.Job, error) {
	if j.ID == "" || j.TenantID == "" {
		return datastore.Job{}, errors.New("edpdata: job id and tenant_id are required")
	}
	if j.Status == "" {
		j.Status = "pending"
	}
	err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
		_, err := tx.Exec(ctx,
			`INSERT INTO jobs (id, tenant_id, kind, status, priority, attempt, idempotency_key)
			 VALUES ($1,$2,$3,$4,$5,$6,$7)
			 ON CONFLICT (id) DO NOTHING`,
			j.ID, j.TenantID, j.Kind, j.Status, j.Priority, j.Attempt, j.IdempotencyKey)
		return err
	})
	if err != nil {
		return datastore.Job{}, err
	}
	return s.Get(ctx, j.ID)
}

// Get reads a job by id.
func (s *JobStore) Get(ctx context.Context, id string) (datastore.Job, error) {
	var j datastore.Job
	var found bool
	err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
		rows, err := tx.Query(ctx,
			`SELECT id, tenant_id, kind, status, priority, attempt, lease_id, expires_at, idempotency_key
			 FROM jobs WHERE id = $1`, id)
		if err != nil {
			return err
		}
		defer rows.Close()
		if rows.Next() {
			var exp *time.Time
			if err := rows.Scan(&j.ID, &j.TenantID, &j.Kind, &j.Status, &j.Priority, &j.Attempt,
				&j.LeaseID, &exp, &j.IdempotencyKey); err != nil {
				return err
			}
			if exp != nil {
				j.ExpiresAt = *exp
			}
			found = true
		}
		return rows.Err()
	})
	if err != nil {
		return datastore.Job{}, err
	}
	if !found {
		return datastore.Job{}, ErrNotFound
	}
	return j, nil
}

// Claim leases the next available job (FIFO by priority/age) to worker for ttl; ok=false when none.
func (s *JobStore) Claim(ctx context.Context, worker string, ttl time.Duration) (datastore.Job, bool, error) {
	var j datastore.Job
	var ok bool
	err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
		rows, err := tx.Query(ctx,
			`UPDATE jobs SET status='leased', lease_id=$1, expires_at=now()+$2::interval,
			        attempt = attempt + 1, updated_at=now()
			 WHERE id = (SELECT id FROM jobs
			             WHERE status='pending' OR (status='leased' AND expires_at < now())
			             ORDER BY priority DESC, created_at
			             FOR UPDATE SKIP LOCKED LIMIT 1)
			 RETURNING id, tenant_id, kind, status, priority, attempt, lease_id, idempotency_key`,
			worker, ttl.String())
		if err != nil {
			return err
		}
		defer rows.Close()
		if rows.Next() {
			if err := rows.Scan(&j.ID, &j.TenantID, &j.Kind, &j.Status, &j.Priority, &j.Attempt,
				&j.LeaseID, &j.IdempotencyKey); err != nil {
				return err
			}
			ok = true
		}
		return rows.Err()
	})
	return j, ok, err
}

func (s *JobStore) finish(ctx context.Context, id, lease, newStatus string) error {
	var affected int64
	err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
		n, err := tx.Exec(ctx,
			`UPDATE jobs SET status=$1, lease_id='', expires_at=NULL, updated_at=now()
			 WHERE id=$2 AND lease_id=$3`, newStatus, id, lease)
		affected = n
		return err
	})
	if err != nil {
		return err
	}
	if affected == 0 {
		return ErrNotFound
	}
	return nil
}

// Complete marks a leased job done.
func (s *JobStore) Complete(ctx context.Context, id, lease string) error {
	return s.finish(ctx, id, lease, "completed")
}

// Fail marks a leased job failed.
func (s *JobStore) Fail(ctx context.Context, id, lease, reason string) error {
	return s.finish(ctx, id, lease, "failed")
}

// Release returns a leased job to pending.
func (s *JobStore) Release(ctx context.Context, id, lease string) error {
	return s.finish(ctx, id, lease, "pending")
}

// Heartbeat extends a lease.
func (s *JobStore) Heartbeat(ctx context.Context, id, lease string) error {
	var affected int64
	err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
		n, err := tx.Exec(ctx,
			`UPDATE jobs SET expires_at=now() + interval '1 minute', updated_at=now()
			 WHERE id=$1 AND lease_id=$2`, id, lease)
		affected = n
		return err
	})
	if err != nil {
		return err
	}
	if affected == 0 {
		return ErrNotFound
	}
	return nil
}
