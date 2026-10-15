package store

import (
	"context"
	"errors"

	"productforge/datastore"
)

// ErrNoTenant is returned when a tenant-scoped operation is attempted without a tenant id.
var ErrNoTenant = errors.New("store: tenant id required")

// WithTenant runs fn in a transaction with the RLS tenant context set. set_config(..., true) is
// transaction-local, so pooled connections never leak tenant context between requests. The database role
// must be non-owner (pf_runtime) for RLS to apply; pf_admin bypasses via BYPASSRLS.
func WithTenant(ctx context.Context, db datastore.RelationalStore, tenantID string, fn func(datastore.Tx) error) error {
	if tenantID == "" {
		return ErrNoTenant
	}
	return db.WithTx(ctx, func(tx datastore.Tx) error {
		if _, err := tx.Exec(ctx, "SELECT set_config('app.tenant_id', $1, true)", tenantID); err != nil {
			return err
		}
		return fn(tx)
	})
}

// VerifyMembership is the server-side authorization check: the active role for principal in tenantID.
// Callers must never trust a client-supplied tenant id without this check.
func VerifyMembership(ctx context.Context, db datastore.RelationalStore, tenantID, principal string) (string, bool, error) {
	if tenantID == "" || principal == "" {
		return "", false, ErrNoTenant
	}
	var role string
	var found bool
	err := db.WithTx(ctx, func(tx datastore.Tx) error {
		rows, err := tx.Query(ctx,
			`SELECT role FROM memberships WHERE tenant_id = $1 AND principal = $2 AND status = 'active'`,
			tenantID, principal)
		if err != nil {
			return err
		}
		defer rows.Close()
		if rows.Next() {
			if err := rows.Scan(&role); err != nil {
				return err
			}
			found = true
		}
		return rows.Err()
	})
	return role, found, err
}
