// Package store is Product Forge's canonical data-access layer (EDP-17 / BI-PF-1309).
//
// It exposes **domain-facing repository ports** (ports-and-adapters): the domain depends on the
// interfaces (TenantRepository, ProjectRepository, …), and each database is an adapter behind them. The
// PostgreSQL adapter (pgx, SQL) ships now; another SQL DB, or a document DB like MongoDB, can be added
// later by implementing the SAME interfaces — no domain code changes (ADR-0006 portability).
package store

import (
	"context"
	"errors"
)

// ErrVersionConflict is returned when an optimistic-concurrency update's expected version is stale.
var ErrVersionConflict = errors.New("store: optimistic version conflict")

// ErrNotFound is returned when a row does not exist.
var ErrNotFound = errors.New("store: not found")

// ---- entity types (DB-agnostic) ----

// Tenant is a tenant (identity/tenancy).
type Tenant struct {
	ID      string
	Slug    string
	Name    string
	Region  string
	Status  string
	Version int64
}

// Project is a tenant-scoped project.
type Project struct {
	ID       string
	TenantID string
	Slug     string
	Name     string
	Status   string
	Version  int64
}

// ---- ports (domain depends on these; DB specifics live in adapters) ----

// TenantRepository is the port for tenant persistence. Any backend implements it.
type TenantRepository interface {
	Create(ctx context.Context, t Tenant) (Tenant, error)
	Get(ctx context.Context, id string) (Tenant, error)
	// Update applies a change under optimistic concurrency (expected version); stale -> ErrVersionConflict.
	Update(ctx context.Context, id string, expected int64, name, status string) (Tenant, error)
	Delete(ctx context.Context, id string) error
}

// ProjectRepository is the port for project persistence.
type ProjectRepository interface {
	Create(ctx context.Context, p Project) (Project, error)
	ListByTenant(ctx context.Context, tenantID string) ([]Project, error)
}

// Repositories aggregates the ports the domain consumes. Swap the adapter, keep the call sites.
type Repositories struct {
	Tenants  TenantRepository
	Projects ProjectRepository
}
