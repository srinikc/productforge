// Package artifacts implements the datastore.ArtifactService port (EDP-15 / BI-PF-1307): artifact metadata
// lives in the relational store, the bytes live in the object store. It composes the two provider-neutral
// ports only (no provider-specific code). The object key is the content address (checksum).
//
// The caller establishes the tenant context (RLS) around these calls; for PostgreSQL that is store.WithTenant.
package artifacts

import (
	"context"
	"errors"
	"io"

	"productforge/datastore"
)

// ErrNotFound is returned when an artifact does not exist (or is soft-deleted).
var ErrNotFound = errors.New("artifacts: not found")

// Service is the relational+object ArtifactService implementation.
type Service struct {
	db datastore.RelationalStore
	os datastore.ObjectStore
}

// New composes the metadata store (db) and the byte store (object store).
func New(db datastore.RelationalStore, os datastore.ObjectStore) *Service {
	return &Service{db: db, os: os}
}

func ctOr(t string) string {
	if t == "" {
		return "application/octet-stream"
	}
	return t
}

// Register persists metadata for an artifact whose bytes are already in the object store (keyed by checksum).
// The logical revision is assigned monotonically per (tenant, name).
func (s *Service) Register(ctx context.Context, a datastore.Artifact) (datastore.Artifact, error) {
	if a.ID == "" || a.TenantID == "" || a.Checksum == "" {
		return datastore.Artifact{}, errors.New("artifacts: id, tenant_id and checksum are required")
	}
	name := a.Type
	err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
		if _, err := tx.Exec(ctx,
			`INSERT INTO stored_objects (tenant_id, checksum, size, content_type) VALUES ($1, $2, $3, $4)
			 ON CONFLICT (tenant_id, checksum) DO NOTHING`,
			a.TenantID, a.Checksum, a.Size, ctOr(a.Type)); err != nil {
			return err
		}
		_, err := tx.Exec(ctx,
			`INSERT INTO artifacts
			   (id, tenant_id, project_id, run_id, stage, artifact_type, name, revision,
			    object_version, checksum, content_type, size)
			 VALUES ($1, $2, NULLIF($3,''), NULLIF($4,''), $5, $6, $6,
			   (SELECT COALESCE(MAX(revision), -1) + 1 FROM artifacts WHERE tenant_id = $2 AND name = $6),
			   $7, $8, $9, $10)`,
			a.ID, a.TenantID, a.Project, a.Run, a.Stage, name, a.Version, a.Checksum, ctOr(a.Type), a.Size)
		return err
	})
	if err != nil {
		return datastore.Artifact{}, err
	}
	return s.Get(ctx, a.ID)
}

// Get returns artifact metadata (excluding soft-deleted).
func (s *Service) Get(ctx context.Context, id string) (datastore.Artifact, error) {
	var a datastore.Artifact
	var found bool
	err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
		rows, err := tx.Query(ctx,
			`SELECT id, tenant_id, COALESCE(project_id, ''), COALESCE(run_id, ''), stage, artifact_type,
			        object_version, checksum, size
			 FROM artifacts WHERE id = $1 AND deleted_at IS NULL`, id)
		if err != nil {
			return err
		}
		defer rows.Close()
		if rows.Next() {
			if err := rows.Scan(&a.ID, &a.TenantID, &a.Project, &a.Run, &a.Stage, &a.Type,
				&a.Version, &a.Checksum, &a.Size); err != nil {
				return err
			}
			found = true
		}
		return rows.Err()
	})
	if err != nil {
		return datastore.Artifact{}, err
	}
	if !found {
		return datastore.Artifact{}, ErrNotFound
	}
	return a, nil
}

// FetchContent streams the artifact's bytes from the object store (keyed by content address).
func (s *Service) FetchContent(ctx context.Context, id string) (io.ReadCloser, error) {
	a, err := s.Get(ctx, id)
	if err != nil {
		return nil, err
	}
	rc, _, err := s.os.Get(ctx, a.Checksum, a.Version)
	return rc, err
}

// Verify confirms the stored bytes match the recorded checksum.
func (s *Service) Verify(ctx context.Context, id string) (bool, error) {
	a, err := s.Get(ctx, id)
	if err != nil {
		return false, err
	}
	info, err := s.os.Head(ctx, a.Checksum)
	if err != nil {
		return false, err
	}
	return info.Checksum == a.Checksum, nil
}

// Delete soft-deletes an artifact (tombstone; retention/expiry is EDP-16).
func (s *Service) Delete(ctx context.Context, id string) error {
	var affected int64
	err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
		n, err := tx.Exec(ctx, `UPDATE artifacts SET deleted_at = now() WHERE id = $1 AND deleted_at IS NULL`, id)
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
