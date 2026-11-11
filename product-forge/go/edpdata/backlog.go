package edpdata

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"time"

	"productforge/datastore"
)

// BacklogItem is a backlog work item's persisted form. `Data` holds the FULL item JSON (lossless) so the DB
// is a complete copy of the file item - no field is dropped. BI-PF-1399 owns the cutover.
type BacklogItem struct {
	ID        string
	TenantID  string
	Scope     string // product_forge | project (direct discriminator; BI-PF-1421)
	ProjectID string // project slug for project-scope items; '' for product_forge (soft ref, no FK)
	Type      string
	Status    string
	Title     string
	Body      string
	Data      json.RawMessage // full item JSON (jsonb)
	Revision  int64
}

// ErrAuthorityUnavailable means the backlog authority schema/row is missing or unreadable.
var (
	ErrAuthorityUnavailable = errors.New("edpdata: backlog authority unavailable")
	ErrAuthoritySchema      = fmt.Errorf("%w: schema", ErrAuthorityUnavailable)
	ErrAuthorityRow         = fmt.Errorf("%w: allocation row", ErrAuthorityUnavailable)
	ErrTenantConflict       = errors.New("edpdata: backlog id belongs to another tenant")
	ErrTenantContext        = errors.New("edpdata: tenant context missing")
	ErrTenantMismatch       = errors.New("edpdata: tenant context mismatch")
	ErrReservationInvalid   = errors.New("edpdata: invalid reservation request")
	ErrReservationConflict  = errors.New("edpdata: reservation id already has a different block")
	ErrReservationExhausted = errors.New("edpdata: id space exhausted")
)

// MaxReservationSize bounds one admin reservation so it cannot consume the ID space.
const MaxReservationSize = 1_000_000

// BacklogStore is a Postgres repository over backlog_items (tenant-scoped; RLS enforced by the caller).
type BacklogStore struct {
	db      datastore.RelationalStore
	timeout time.Duration
}

const defaultStatementTimeout = 5 * time.Second

// NewBacklog returns a BacklogStore over db.
func NewBacklog(db datastore.RelationalStore) *BacklogStore {
	return &BacklogStore{db: db, timeout: defaultStatementTimeout}
}

// WithTimeout applies the service DB timeout to transaction-local statement timeouts.
func (s *BacklogStore) WithTimeout(d time.Duration) *BacklogStore {
	if d > 0 {
		s.timeout = d
	}
	return s
}

// StatementTimeout reports the transaction-local timeout currently configured for the store.
func (s *BacklogStore) StatementTimeout() time.Duration { return s.timeout }

func (s *BacklogStore) setStatementTimeout(ctx context.Context, tx datastore.Tx) error {
	ms := s.timeout.Milliseconds()
	if ms <= 0 {
		ms = defaultStatementTimeout.Milliseconds()
	}
	_, err := tx.Exec(ctx, "SELECT set_config('statement_timeout', $1, true)", fmt.Sprintf("%dms", ms))
	return err
}

// Authority is the readiness snapshot read by the admin backlog-authority endpoint.
// NextID and ReservationCount are global; ItemCount is scoped to the bound tenant.
type Authority struct {
	NextID           int64
	ReservationCount int64
	ItemCount        int64
}

// Authority reads the global allocation row and the tenant-scoped item count in one transaction.
// Missing 0016/0018 schema, a missing global row, or a query error fails closed.
func (s *BacklogStore) Authority(ctx context.Context) (Authority, error) {
	var out Authority
	err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
		// Bound server-side work independently of the caller's context.
		if err := s.setStatementTimeout(ctx, tx); err != nil {
			return err
		}
		rows, err := tx.Query(ctx, `SELECT
			COALESCE(to_regclass('public.backlog_id_allocations')::text, ''),
			COALESCE(to_regclass('public.backlog_id_reservations')::text, ''),
			COALESCE(to_regclass('public.backlog_items')::text, ''),
			EXISTS (SELECT 1 FROM information_schema.columns
			        WHERE table_schema='public' AND table_name='backlog_id_allocations'
			          AND column_name='reservation_count'),
			COALESCE(current_setting('app.tenant_id', true), ''),
			EXISTS (SELECT 1 FROM pg_class c
			        JOIN pg_policies p ON p.tablename=c.relname AND p.schemaname='public'
			        WHERE c.relname='backlog_items' AND c.relrowsecurity AND c.relforcerowsecurity
			          AND p.policyname='tenant_isolation'),
			EXISTS (SELECT 1 FROM schema_migrations WHERE version IN (16,18,19,20,21,23) HAVING count(*)=6)`)
		if err != nil {
			return err
		}
		var alloc, reservations, items, tenantContext string
		var counter, rlsPolicy, migrationsOK bool
		if rows.Next() {
			if err := rows.Scan(&alloc, &reservations, &items, &counter, &tenantContext, &rlsPolicy, &migrationsOK); err != nil {
				rows.Close()
				return err
			}
		}
		if err := rows.Err(); err != nil {
			rows.Close()
			return err
		}
		rows.Close()
		if alloc == "" || reservations == "" || items == "" || !counter || tenantContext == "" || !rlsPolicy || !migrationsOK {
			return ErrAuthoritySchema
		}

		rows, err = tx.Query(ctx, `SELECT next_id, reservation_count
			FROM backlog_id_allocations WHERE authority='global'`)
		if err != nil {
			return err
		}
		found := rows.Next()
		if found {
			if err := rows.Scan(&out.NextID, &out.ReservationCount); err != nil {
				rows.Close()
				return err
			}
		}
		if err := rows.Err(); err != nil {
			rows.Close()
			return err
		}
		rows.Close()
		if !found {
			return ErrAuthorityRow
		}
		if out.NextID <= 0 || out.ReservationCount < 0 {
			return ErrAuthorityRow
		}

		rows, err = tx.Query(ctx, `SELECT count(*) FROM backlog_items WHERE tenant_id = current_setting('app.tenant_id', true)`)
		if err != nil {
			return err
		}
		if rows.Next() {
			if err := rows.Scan(&out.ItemCount); err != nil {
				rows.Close()
				return err
			}
		}
		if err := rows.Err(); err != nil {
			rows.Close()
			return err
		}
		rows.Close()
		return nil
	})
	if err != nil {
		return Authority{}, err
	}
	return out, nil
}

func orEmpty(raw json.RawMessage) string {
	if len(raw) == 0 {
		return "{}"
	}
	return string(raw)
}

// Put upserts a backlog item (idempotent on id; material changes bump revision). `Data` is stored verbatim.
func requireTenant(ctx context.Context, tx datastore.Tx) (string, error) {
	rows, err := tx.Query(ctx, `SELECT COALESCE(current_setting('app.tenant_id', true), '')`)
	if err != nil {
		return "", err
	}
	var tenant string
	if rows.Next() {
		if err := rows.Scan(&tenant); err != nil {
			rows.Close()
			return "", err
		}
	}
	if err := rows.Close(); err != nil {
		return "", err
	}
	if tenant == "" {
		return "", ErrTenantContext
	}
	return tenant, nil
}

func (s *BacklogStore) Put(ctx context.Context, it BacklogItem) (BacklogItem, error) {
	if it.ID == "" || it.TenantID == "" {
		return BacklogItem{}, errors.New("edpdata: backlog id and tenant_id are required")
	}
	if it.Type == "" {
		it.Type = "feature"
	}
	if it.Status == "" {
		it.Status = "new"
	}
	if it.Scope == "" {
		it.Scope = "product_forge"
	}
	data := orEmpty(it.Data)
	err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
		bound, err := requireTenant(ctx, tx)
		if err != nil {
			return err
		}
		if bound != it.TenantID {
			return ErrTenantMismatch
		}
		n, err := tx.Exec(ctx,
			`INSERT INTO backlog_items (id, tenant_id, scope, project_id, type, status, title, body, data, revision)
			 VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10)
			 ON CONFLICT (tenant_id, id) DO UPDATE SET
			   scope=EXCLUDED.scope, project_id=EXCLUDED.project_id,
			   type=EXCLUDED.type, status=EXCLUDED.status,
			   title=EXCLUDED.title, body=EXCLUDED.body, data=EXCLUDED.data,
			   revision=backlog_items.revision + 1, updated_at=now()
			 WHERE backlog_items.tenant_id = EXCLUDED.tenant_id`,
			it.ID, it.TenantID, it.Scope, it.ProjectID, it.Type, it.Status, it.Title, it.Body, data, it.Revision)
		if err != nil {
			return err
		}
		if n == 0 {
			return ErrTenantConflict
		}
		return nil
	})
	if err != nil {
		return BacklogItem{}, err
	}
	return s.Get(ctx, it.ID)
}

// IDBlock is a DB-reserved contiguous ID range.
type IDBlock struct {
	Start int64
	End   int64
}

// Reserve allocates a contiguous block from the DB authority. The reservation_id makes timeout retries
// idempotent: a retry returns the same block instead of allocating a second one.
func (s *BacklogStore) Reserve(ctx context.Context, scope, projectID, reservationID string, size int) (IDBlock, error) {
	if reservationID == "" || size <= 0 || size > MaxReservationSize {
		return IDBlock{}, ErrReservationInvalid
	}
	if scope == "" {
		scope = "product_forge"
	}
	var out IDBlock
	err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
		if err := s.setStatementTimeout(ctx, tx); err != nil {
			return err
		}
		// Hold the allocation row first so concurrent retries serialize before the idempotency check.
		rows, err := tx.Query(ctx,
			`SELECT next_id FROM backlog_id_allocations WHERE authority='global' FOR UPDATE`)
		if err != nil {
			return err
		}
		var next int64
		if rows.Next() {
			err = rows.Scan(&next)
		} else {
			err = ErrAuthorityRow
		}
		if closeErr := rows.Close(); err == nil {
			err = closeErr
		}
		if err != nil {
			return err
		}
		if next <= 0 || next > math.MaxInt64-int64(size) {
			return ErrReservationExhausted
		}

		rows, err = tx.Query(ctx,
			`SELECT start_id, end_id, scope, project_id FROM backlog_id_reservations WHERE reservation_id=$1`, reservationID)
		if err != nil {
			return err
		}
		if rows.Next() {
			var gotScope, gotProject string
			if err := rows.Scan(&out.Start, &out.End, &gotScope, &gotProject); err != nil {
				rows.Close()
				return err
			}
			if err := rows.Err(); err != nil {
				rows.Close()
				return err
			}
			rows.Close()
			if out.End-out.Start+1 != int64(size) || gotScope != scope || gotProject != projectID {
				return ErrReservationConflict
			}
			return nil
		}
		if err := rows.Err(); err != nil {
			rows.Close()
			return err
		}
		rows.Close()

		out.Start = next
		out.End = next + int64(size) - 1
		if _, err := tx.Exec(ctx,
			`UPDATE backlog_id_allocations SET next_id=$1 WHERE authority='global'`,
			out.End+1); err != nil {
			return err
		}
		_, err = tx.Exec(ctx,
			`INSERT INTO backlog_id_reservations(reservation_id, scope, project_id, start_id, end_id)
			 VALUES ($1,$2,$3,$4,$5)`, reservationID, scope, projectID, out.Start, out.End)
		return err
	})
	if err != nil {
		return IDBlock{}, err
	}
	return out, nil
}

// Get reads a backlog item (including its full Data).
func (s *BacklogStore) Get(ctx context.Context, id string) (BacklogItem, error) {
	var it BacklogItem
	var found bool
	err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
		bound, err := requireTenant(ctx, tx)
		if err != nil {
			return err
		}
		rows, err := tx.Query(ctx,
			`SELECT id, tenant_id, scope, COALESCE(project_id, ''), type, status, title, body, data, revision FROM backlog_items WHERE id=$1 AND tenant_id=$2`, id, bound)
		if err != nil {
			return err
		}
		defer rows.Close()
		if rows.Next() {
			if err := rows.Scan(&it.ID, &it.TenantID, &it.Scope, &it.ProjectID, &it.Type, &it.Status, &it.Title, &it.Body, &it.Data, &it.Revision); err != nil {
				return err
			}
			found = true
		}
		return rows.Err()
	})
	if err != nil {
		return BacklogItem{}, err
	}
	if !found {
		return BacklogItem{}, ErrNotFound
	}
	return it, nil
}

// List returns items, optionally filtered by status.
func (s *BacklogStore) List(ctx context.Context, status string, limit int) ([]BacklogItem, error) {
	if limit <= 0 {
		limit = 50
	}
	var out []BacklogItem
	err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
		bound, err := requireTenant(ctx, tx)
		if err != nil {
			return err
		}
		rows, err := tx.Query(ctx,
			`SELECT id, tenant_id, scope, COALESCE(project_id, ''), type, status, title, body, data, revision FROM backlog_items
			 WHERE tenant_id=$3 AND ($1 = '' OR status = $1) ORDER BY created_at DESC LIMIT $2`, status, limit, bound)
		if err != nil {
			return err
		}
		defer rows.Close()
		for rows.Next() {
			var it BacklogItem
			if err := rows.Scan(&it.ID, &it.TenantID, &it.Scope, &it.ProjectID, &it.Type, &it.Status, &it.Title, &it.Body, &it.Data, &it.Revision); err != nil {
				return err
			}
			out = append(out, it)
		}
		return rows.Err()
	})
	return out, err
}

// Delete removes a backlog item.
func (s *BacklogStore) Delete(ctx context.Context, id string) error {
	var affected int64
	err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
		bound, err := requireTenant(ctx, tx)
		if err != nil {
			return err
		}
		n, err := tx.Exec(ctx, `DELETE FROM backlog_items WHERE id=$1 AND tenant_id=$2`, id, bound)
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
