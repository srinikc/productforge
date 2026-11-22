package dualvec

import (
	"context"
	"time"

	"productforge/datastore"
	"productforge/edpdata"
)

// PgMemoryStore implements datastore.MemoryRepository over PostgreSQL with pgvector.
type PgMemoryStore struct {
	inner *edpdata.MemoryStore
}

// NewPgMemoryStore wraps an existing RelationalStore into a PgMemoryStore.
func NewPgMemoryStore(db datastore.RelationalStore) *PgMemoryStore {
	return &PgMemoryStore{inner: edpdata.NewMemory(db)}
}

// Put delegates to the inner PostgreSQL memory store.
func (p *PgMemoryStore) Put(ctx context.Context, e datastore.MemoryEntry) (datastore.MemoryEntry, error) {
	start := time.Now()
	entry, err := p.inner.Put(ctx, e)
	currentObserver.Observe(EnginePostgres, "Put", e.TenantID, e.Project, time.Since(start), err)
	return entry, err
}

// Get delegates to the inner PostgreSQL memory store.
func (p *PgMemoryStore) Get(ctx context.Context, id string) (datastore.MemoryEntry, error) {
	start := time.Now()
	entry, err := p.inner.Get(ctx, id)
	currentObserver.Observe(EnginePostgres, "Get", entry.TenantID, entry.Project, time.Since(start), err)
	return entry, err
}

// Search delegates to the inner PostgreSQL memory store.
func (p *PgMemoryStore) Search(ctx context.Context, q string, scope datastore.MemoryScope, k int) ([]datastore.MemoryEntry, error) {
	start := time.Now()
	entries, err := p.inner.Search(ctx, q, scope, k)
	currentObserver.Observe(EnginePostgres, "Search", scope.TenantID, scope.Project, time.Since(start), err)
	return entries, err
}

// Delete delegates to the inner PostgreSQL memory store.
func (p *PgMemoryStore) Delete(ctx context.Context, id string) error {
	start := time.Now()
	err := p.inner.Delete(ctx, id)
	currentObserver.Observe(EnginePostgres, "Delete", "", "", time.Since(start), err)
	return err
}
