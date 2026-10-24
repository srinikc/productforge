package intakeingest

import (
	"context"
	"errors"
	"fmt"

	"productforge/datastore"
)

// RolePosture is the current database role's privilege posture.
type RolePosture struct {
	Name      string
	Superuser bool
	BypassRLS bool
}

// RuntimeRole reads current_user's superuser/bypassrls flags. A role that bypasses RLS makes the tenant
// isolation guarantee advisory, so ingestion refuses it by default.
func RuntimeRole(ctx context.Context, db datastore.RelationalStore) (RolePosture, error) {
	var p RolePosture
	err := db.WithTx(ctx, func(tx datastore.Tx) error {
		rows, err := tx.Query(ctx,
			`SELECT current_user, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user`)
		if err != nil {
			return err
		}
		defer rows.Close()
		if rows.Next() {
			return rows.Scan(&p.Name, &p.Superuser, &p.BypassRLS)
		}
		return rows.Err()
	})
	if err != nil {
		return RolePosture{}, err
	}
	if p.Name == "" {
		return RolePosture{}, errors.New("intakeingest: cannot determine current_user")
	}
	return p, nil
}

// EnsureRuntimeRole fails closed on a superuser/BYPASSRLS role unless allowBypass is explicit. Callers must
// also gate allowBypass on a non-CI environment; the CLI enforces that so CI can never take the escape hatch.
func EnsureRuntimeRole(ctx context.Context, db datastore.RelationalStore, allowBypass bool) (RolePosture, error) {
	p, err := RuntimeRole(ctx, db)
	if err != nil {
		return p, err
	}
	if p.Superuser || p.BypassRLS {
		if !allowBypass {
			return p, fmt.Errorf("intakeingest: refusing to run as %q (rolsuper=%v rolbypassrls=%v): "+
				"row-level security would be bypassed; use a non-BYPASSRLS role", p.Name, p.Superuser, p.BypassRLS)
		}
		return p, nil
	}
	return p, nil
}
