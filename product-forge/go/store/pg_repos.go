package store

import (
	"context"
	"errors"

	"productforge/datastore"
)

// NewPostgres returns the repository ports backed by PostgreSQL (the EDP-17 adapter). A different backend
// (another SQL DB, or a document store like MongoDB) is added later by implementing the same ports.
func NewPostgres(db datastore.RelationalStore) *Repositories {
	return &Repositories{
		Tenants:  &pgTenantRepo{db: db},
		Projects: &pgProjectRepo{db: db},
	}
}

// ---- PostgreSQL TenantRepository ----

type pgTenantRepo struct{ db datastore.RelationalStore }

func (r *pgTenantRepo) Create(ctx context.Context, t Tenant) (Tenant, error) {
	if t.ID == "" || t.Slug == "" || t.Name == "" {
		return Tenant{}, errors.New("store: tenant id, slug and name are required")
	}
	if t.Status == "" {
		t.Status = "active"
	}
	err := r.db.WithTx(ctx, func(tx datastore.Tx) error {
		_, err := tx.Exec(ctx,
			`INSERT INTO tenants (id, slug, name, region, status, version) VALUES ($1, $2, $3, $4, $5, 0)`,
			t.ID, t.Slug, t.Name, t.Region, t.Status)
		return err
	})
	if err != nil {
		return Tenant{}, err
	}
	t.Version = 0
	return t, nil
}

func (r *pgTenantRepo) Get(ctx context.Context, id string) (Tenant, error) {
	var t Tenant
	var found bool
	err := r.db.WithTx(ctx, func(tx datastore.Tx) error {
		rows, err := tx.Query(ctx,
			`SELECT id, slug, name, region, status, version FROM tenants WHERE id = $1`, id)
		if err != nil {
			return err
		}
		defer rows.Close()
		if rows.Next() {
			if err := rows.Scan(&t.ID, &t.Slug, &t.Name, &t.Region, &t.Status, &t.Version); err != nil {
				return err
			}
			found = true
		}
		return rows.Err()
	})
	if err != nil {
		return Tenant{}, err
	}
	if !found {
		return Tenant{}, ErrNotFound
	}
	return t, nil
}

func (r *pgTenantRepo) Update(ctx context.Context, id string, expected int64, name, status string) (Tenant, error) {
	newVersion := expected + 1
	var affected int64
	err := r.db.WithTx(ctx, func(tx datastore.Tx) error {
		n, err := tx.Exec(ctx,
			`UPDATE tenants SET name = $1, status = $2, version = $3, updated_at = now()
			 WHERE id = $4 AND version = $5`,
			name, status, newVersion, id, expected)
		affected = n
		return err
	})
	if err != nil {
		return Tenant{}, err
	}
	if affected == 0 {
		return Tenant{}, ErrVersionConflict
	}
	return r.Get(ctx, id)
}

func (r *pgTenantRepo) Delete(ctx context.Context, id string) error {
	var affected int64
	err := r.db.WithTx(ctx, func(tx datastore.Tx) error {
		n, err := tx.Exec(ctx, `DELETE FROM tenants WHERE id = $1`, id)
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

// ---- PostgreSQL ProjectRepository ----

type pgProjectRepo struct{ db datastore.RelationalStore }

func (r *pgProjectRepo) Create(ctx context.Context, p Project) (Project, error) {
	if p.ID == "" || p.TenantID == "" || p.Slug == "" || p.Name == "" {
		return Project{}, errors.New("store: project id, tenant_id, slug and name are required")
	}
	if p.Status == "" {
		p.Status = "active"
	}
	err := r.db.WithTx(ctx, func(tx datastore.Tx) error {
		_, err := tx.Exec(ctx,
			`INSERT INTO projects (id, tenant_id, slug, name, status, version) VALUES ($1, $2, $3, $4, $5, 0)`,
			p.ID, p.TenantID, p.Slug, p.Name, p.Status)
		return err
	})
	if err != nil {
		return Project{}, err
	}
	p.Version = 0
	return p, nil
}

func (r *pgProjectRepo) ListByTenant(ctx context.Context, tenantID string) ([]Project, error) {
	var out []Project
	err := r.db.WithTx(ctx, func(tx datastore.Tx) error {
		rows, err := tx.Query(ctx,
			`SELECT id, tenant_id, slug, name, status, version FROM projects
			 WHERE tenant_id = $1 ORDER BY slug`, tenantID)
		if err != nil {
			return err
		}
		defer rows.Close()
		for rows.Next() {
			var p Project
			if err := rows.Scan(&p.ID, &p.TenantID, &p.Slug, &p.Name, &p.Status, &p.Version); err != nil {
				return err
			}
			out = append(out, p)
		}
		return rows.Err()
	})
	return out, err
}
