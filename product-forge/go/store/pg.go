// Package store is Product Forge's canonical data-access layer (DAL) over the PostgreSQL system of record
// (EDP-17 / BI-PF-1309). It implements the provider-neutral “datastore.RelationalStore“ with a pooled pgx
// client and provides typed repositories with optimistic-concurrency updates (the per-row “version“ column).
//
// Domain logic depends on this layer, never on pgx directly (ADR-0006 / EDP-07).
package store

import (
	"context"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"productforge/datastore"
)

// PgStore is the PostgreSQL implementation of datastore.RelationalStore, backed by a pgx connection pool.
type PgStore struct{ pool *pgxpool.Pool }

// Open creates a pooled store for dsn and verifies connectivity. Close it when done.
func Open(ctx context.Context, dsn string) (*PgStore, error) {
	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		return nil, err
	}
	if err := pool.Ping(ctx); err != nil {
		pool.Close()
		return nil, err
	}
	return &PgStore{pool: pool}, nil
}

// Close releases the pool.
func (s *PgStore) Close() { s.pool.Close() }

// Ping verifies connectivity.
func (s *PgStore) Ping(ctx context.Context) error { return s.pool.Ping(ctx) }

// Capabilities reports the real provider features (transactions + conditional writes via the version column).
func (s *PgStore) Capabilities() datastore.Capabilities {
	return datastore.Capabilities{Transactions: true, ConditionalWrites: true}
}

// WithTx runs fn inside a transaction: commit on success, roll back on error/panic.
func (s *PgStore) WithTx(ctx context.Context, fn func(datastore.Tx) error) (err error) {
	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return err
	}
	defer func() {
		if err != nil {
			_ = tx.Rollback(ctx)
		}
	}()
	if err = fn(&pgTx{tx: tx}); err != nil {
		return err
	}
	return tx.Commit(ctx)
}

type pgTx struct{ tx pgx.Tx }

func (t *pgTx) Exec(ctx context.Context, sql string, args ...any) (int64, error) {
	ct, err := t.tx.Exec(ctx, sql, args...)
	if err != nil {
		return 0, err
	}
	return ct.RowsAffected(), nil
}

func (t *pgTx) Query(ctx context.Context, sql string, args ...any) (datastore.Rows, error) {
	rows, err := t.tx.Query(ctx, sql, args...)
	if err != nil {
		return nil, err
	}
	return &pgRows{rows: rows}, nil
}

func (t *pgTx) Commit(ctx context.Context) error   { return t.tx.Commit(ctx) }
func (t *pgTx) Rollback(ctx context.Context) error { return t.tx.Rollback(ctx) }

type pgRows struct{ rows pgx.Rows }

func (r *pgRows) Next() bool             { return r.rows.Next() }
func (r *pgRows) Scan(dest ...any) error { return r.rows.Scan(dest...) }
func (r *pgRows) Err() error             { return r.rows.Err() }
func (r *pgRows) Close() error           { r.rows.Close(); return nil }
