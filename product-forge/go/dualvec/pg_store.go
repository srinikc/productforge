package dualvec

import (
	"context"

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
	return p.inner.Put(ctx, e)
}

// Get delegates to the inner PostgreSQL memory store.
func (p *PgMemoryStore) Get(ctx context.Context, id string) (datastore.MemoryEntry, error) {
	return p.inner.Get(ctx, id)
}

// Search delegates to the inner PostgreSQL memory store.
func (p *PgMemoryStore) Search(ctx context.Context, q string, scope datastore.MemoryScope, k int) ([]datastore.MemoryEntry, error) {
	return p.inner.Search(ctx, q, scope, k)
}

// Delete delegates to the inner PostgreSQL memory store.
func (p *PgMemoryStore) Delete(ctx context.Context, id string) error {
	return p.inner.Delete(ctx, id)
}
