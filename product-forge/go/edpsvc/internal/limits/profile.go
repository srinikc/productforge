package limits

import (
	"context"
	"fmt"
	"sync/atomic"
	"time"

	"productforge/datastore"
)

// Role is the runtime database role posture.
type Role struct {
	Name      string
	Superuser bool
	BypassRLS bool
}

// Violation reports whether the role bypasses row-level security and is not explicitly allowed.
func (r Role) Violation(allowSuperuser bool) bool {
	return (r.Superuser || r.BypassRLS) && !allowSuperuser
}

// CheckDBRole reads current_user's superuser/bypassrls flags and fails closed on a bypass role.
func CheckDBRole(ctx context.Context, db datastore.RelationalStore, allowSuperuser bool) (Role, error) {
	var r Role
	if db == nil {
		return r, fmt.Errorf("limits: no database handle for the runtime role check")
	}
	if err := db.WithTx(ctx, func(tx datastore.Tx) error {
		rows, err := tx.Query(ctx,
			`SELECT current_user, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user`)
		if err != nil {
			return err
		}
		defer rows.Close()
		if rows.Next() {
			return rows.Scan(&r.Name, &r.Superuser, &r.BypassRLS)
		}
		return rows.Err()
	}); err != nil {
		return r, err
	}
	if r.Name == "" {
		return r, fmt.Errorf("limits: cannot determine current_user for the runtime role check")
	}
	if r.Violation(allowSuperuser) {
		return r, fmt.Errorf("runtime DB role %q is superuser/BYPASSRLS; use pf_app/pf_runtime so RLS is enforced",
			r.Name)
	}
	return r, nil
}

// RoleGuard holds the last role posture; a failed recheck makes every non-health request 503 (fail closed).
type RoleGuard struct {
	ok     atomic.Bool
	name   atomic.Value // string
	super  atomic.Bool
	bypass atomic.Bool
	last   atomic.Int64 // unix seconds of the last successful check
}

// NewRoleGuard returns a guard in the closed (not-yet-verified) state.
func NewRoleGuard() *RoleGuard {
	g := &RoleGuard{}
	g.name.Store("")
	return g
}

// Set records a successful check.
func (g *RoleGuard) Set(r Role) {
	g.name.Store(r.Name)
	g.super.Store(r.Superuser)
	g.bypass.Store(r.BypassRLS)
	g.ok.Store(true)
	g.last.Store(time.Now().Unix())
}

// Fail closes the guard after a failed/violating recheck.
func (g *RoleGuard) Fail() { g.ok.Store(false) }

// OK reports whether the last check passed.
func (g *RoleGuard) OK() bool { return g.ok.Load() }

// Role returns the last observed role.
func (g *RoleGuard) Role() Role {
	name, _ := g.name.Load().(string)
	return Role{Name: name, Superuser: g.super.Load(), BypassRLS: g.bypass.Load()}
}

// LastCheck returns the unix second of the last successful check (0 = never).
func (g *RoleGuard) LastCheck() int64 { return g.last.Load() }

// RecheckLoop revalidates the role every interval until stop is closed. A violation/failure closes the guard
// and invokes onViolation (logging/metrics), so a role grant after boot cannot silently bypass RLS.
func (g *RoleGuard) RecheckLoop(ctx context.Context, db datastore.RelationalStore, allowSuperuser bool,
	every time.Duration, onViolation func(error)) {
	if every <= 0 {
		return
	}
	t := time.NewTicker(every)
	defer t.Stop()
	failures := 0
	for {
		select {
		case <-ctx.Done():
			return
		case <-t.C:
			checkCtx, cancel := context.WithTimeout(ctx, 10*time.Second)
			r, err := CheckDBRole(checkCtx, db, allowSuperuser)
			cancel()
			if err != nil {
				failures++
				if failures >= 2 {
					g.Fail()
				}
				if onViolation != nil {
					onViolation(err)
				}
				continue
			}
			failures = 0
			g.Set(r)
		}
	}
}
