package store

import (
	"context"
	"errors"
	"testing"

	"productforge/datastore"
)

// fakeStore lets us exercise the DAL's control flow (e.g. the optimistic-conflict branch) without a DB.
type fakeStore struct{ affected int64 }

func (s *fakeStore) Ping(context.Context) error { return nil }
func (s *fakeStore) Capabilities() datastore.Capabilities {
	return datastore.Capabilities{Transactions: true}
}
func (s *fakeStore) WithTx(_ context.Context, fn func(datastore.Tx) error) error {
	return fn(&fakeTx{affected: s.affected})
}

type fakeTx struct{ affected int64 }

func (t *fakeTx) Exec(context.Context, string, ...any) (int64, error) { return t.affected, nil }
func (t *fakeTx) Query(context.Context, string, ...any) (datastore.Rows, error) {
	return emptyRows{}, nil
}
func (t *fakeTx) Commit(context.Context) error   { return nil }
func (t *fakeTx) Rollback(context.Context) error { return nil }

type emptyRows struct{}

func (emptyRows) Next() bool        { return false }
func (emptyRows) Scan(...any) error { return nil }
func (emptyRows) Err() error        { return nil }
func (emptyRows) Close() error      { return nil }

func TestUpdateTenantVersionConflictOnZeroAffected(t *testing.T) {
	repos := NewPostgres(&fakeStore{affected: 0})
	if _, err := repos.Tenants.Update(context.Background(), "t1", 1, "x", "active"); !errors.Is(err, ErrVersionConflict) {
		t.Fatalf("want ErrVersionConflict, got %v", err)
	}
}

func TestCreateValidatesRequiredFields(t *testing.T) {
	repos := NewPostgres(&fakeStore{})
	if _, err := repos.Tenants.Create(context.Background(), Tenant{}); err == nil {
		t.Fatal("want validation error for missing id/slug/name")
	}
	if _, err := repos.Projects.Create(context.Background(), Project{ID: "p"}); err == nil {
		t.Fatal("want validation error for missing tenant_id/slug/name")
	}
}
