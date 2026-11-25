// Package intakeingest ingests the file-backed intake-raw/builds stores into the EDP artifact substrate
// (BI-PF-1475 / EDP-24 gap).
//
// The bytes are written to the object store under a tenant-prefixed, content-addressed key; the metadata is
// written to the relational system of record (stored_objects + artifacts) inside one RLS-bound transaction.
// The artifact id is deterministic over (tenant, bucket, logical name, checksum), so re-ingesting unchanged
// bytes is a no-op while changed bytes create a new immutable object plus the next artifact revision.
package intakeingest

import (
	"bytes"
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"path"
	"regexp"
	"sort"
	"strings"
	"time"

	"productforge/datastore"
)

// Schema is the pinned report contract; ops automation may rely on it.
const Schema = "pf.intake-ingest/1"

// NewRunID returns a UUIDv4 run id (pinned in the pf.intake-ingest/1 contract).
func NewRunID() (string, error) {
	var b [16]byte
	if _, err := rand.Read(b[:]); err != nil {
		return "", fmt.Errorf("intakeingest: cannot generate run id: %w", err)
	}
	b[6] = (b[6] & 0x0f) | 0x40
	b[8] = (b[8] & 0x3f) | 0x80
	return fmt.Sprintf("%x-%x-%x-%x-%x", b[0:4], b[4:6], b[6:8], b[8:10], b[10:16]), nil
}

const (
	BucketIntake = "intake"
	BucketBuilds = "builds"
	// DefaultMaxBytes caps one file (and one verify re-hash) at 256 MiB.
	DefaultMaxBytes int64 = 256 << 20
)

// Status is the per-file outcome in the report.
type Status string

const (
	// Planned means a dry run validated the file but mutated nothing.
	Planned Status = "planned"
	// Written means the object and metadata were created.
	Written Status = "written"
	// SkippedUnchanged means the same artifact id already existed (or verify passed).
	SkippedUnchanged Status = "skipped-unchanged"
	// Drift means the source, metadata and object disagree.
	Drift Status = "drift"
	// Failed means the file could not be read, stored or verified.
	Failed Status = "failed"
)

var (
	ErrTooLarge  = errors.New("intakeingest: file exceeds max-bytes")
	ErrBadBucket = errors.New("intakeingest: bucket must be intake or builds")
	ErrNoTenant  = errors.New("intakeingest: tenant is required")
	ErrNoName    = errors.New("intakeingest: name is required")
	// ErrBadTenant rejects a tenant id that could escape the tenant/ object prefix (path traversal).
	ErrBadTenant = errors.New("intakeingest: tenant id must match [A-Za-z0-9][A-Za-z0-9._-]*")
)

var tenantRE = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._-]*$`)

// FileResult is one file's outcome. It is also emitted as one structured log line.
type FileResult struct {
	Store      string `json:"store"`
	Bucket     string `json:"bucket"`
	Name       string `json:"name"`
	Status     Status `json:"status"`
	ArtifactID string `json:"artifact_id,omitempty"`
	Revision   int64  `json:"revision"`
	Checksum   string `json:"checksum,omitempty"`
	Bytes      int64  `json:"bytes"`
	DurationMS int64  `json:"duration_ms"`
	Error      string `json:"error,omitempty"`
}

// Report is the pinned pf.intake-ingest/1 run report.
type Report struct {
	Schema        string         `json:"schema"`
	RunID         string         `json:"run_id"`
	Mode          string         `json:"mode"`
	Tenant        string         `json:"tenant"`
	DryRun        bool           `json:"dry_run"`
	StartedAt     time.Time      `json:"started_at"`
	DurationMS    int64          `json:"duration_ms"`
	Files         []FileResult   `json:"files"`
	Counts        map[string]int `json:"counts"`
	OrphanObjects []string       `json:"orphan_objects,omitempty"`
}

// NewReport returns an empty report with the pinned schema and zeroed counts.
func NewReport(runID, mode, tenant string, dryRun bool) Report {
	return Report{Schema: Schema, RunID: runID, Mode: mode, Tenant: tenant, DryRun: dryRun,
		StartedAt: time.Now().UTC(), Files: []FileResult{}, Counts: map[string]int{
			string(Planned): 0, string(Written): 0, string(SkippedUnchanged): 0,
			string(Drift): 0, string(Failed): 0}}
}

// Add appends a result and updates the counts.
func (r *Report) Add(f FileResult) {
	r.Files = append(r.Files, f)
	r.Counts[string(f.Status)]++
}

// OK reports whether the run has no drift and no failures.
func (r *Report) OK() bool { return r.Counts[string(Drift)] == 0 && r.Counts[string(Failed)] == 0 }

// HasFailure reports whether any file failed (exit 2) vs drifted (exit 1).
func (r *Report) HasFailure() bool { return r.Counts[string(Failed)] > 0 }

// ExitCode maps a report to the CLI contract: 2 failed, 1 drift, 0 clean.
func ExitCode(r Report) int {
	if r.HasFailure() {
		return 2
	}
	if !r.OK() {
		return 1
	}
	return 0
}

// Service ingests files over the provider-neutral datastore ports.
type Service struct {
	db       datastore.RelationalStore
	objects  datastore.ObjectStore
	maxBytes int64
}

// New composes an RLS-bound relational store with the object store.
func New(db datastore.RelationalStore, objects datastore.ObjectStore, maxBytes int64) *Service {
	if maxBytes <= 0 {
		maxBytes = DefaultMaxBytes
	}
	return &Service{db: db, objects: objects, maxBytes: maxBytes}
}

// MaxBytes reports the effective per-file cap.
func (s *Service) MaxBytes() int64 { return s.maxBytes }

// ObjectKey is the tenant-prefixed, content-addressed object key.
func ObjectKey(tenant, bucket, checksum string) string {
	return "tenant/" + tenant + "/" + bucket + "/" + checksum
}

// ArtifactID is deterministic over (tenant, bucket, logical name, checksum). Unchanged input therefore maps
// to the same row; changed bytes map to a new row (and the next revision). The 128-bit truncation keeps the
// id readable; uniqueness is also enforced by (tenant, name, revision), so a truncation collision would be a
// conflict error rather than silent data loss.
func ArtifactID(tenant, bucket, name, checksum string) string {
	sum := sha256.Sum256([]byte(tenant + "|" + bucket + "|" + name + "|" + checksum))
	return hex.EncodeToString(sum[:])[:32]
}

// Checksum returns the lowercase hex sha256 of b.
func Checksum(b []byte) string {
	sum := sha256.Sum256(b)
	return hex.EncodeToString(sum[:])
}

func artifactType(bucket string) string {
	if bucket == BucketBuilds {
		return "build"
	}
	return "intake-raw"
}

// ContentTypeFor keeps per-store MIME fidelity when the caller does not override it.
func ContentTypeFor(name, override string) string {
	if strings.TrimSpace(override) != "" && override != "application/octet-stream" {
		return override
	}
	ext := ""
	if i := strings.LastIndex(name, "."); i >= 0 {
		ext = strings.ToLower(name[i+1:])
	}
	switch ext {
	case "json":
		return "application/json"
	case "jsonl", "ndjson":
		return "application/x-ndjson"
	case "md", "markdown":
		return "text/markdown"
	case "txt", "log":
		return "text/plain"
	case "yaml", "yml":
		return "application/yaml"
	default:
		return "application/octet-stream"
	}
}

func validate(tenant, bucket, name string) error {
	if strings.TrimSpace(tenant) == "" {
		return ErrNoTenant
	}
	if !tenantRE.MatchString(tenant) {
		return ErrBadTenant
	}
	if bucket != BucketIntake && bucket != BucketBuilds {
		return ErrBadBucket
	}
	if strings.TrimSpace(name) == "" {
		return ErrNoName
	}
	return nil
}

func (s *Service) read(r io.Reader) ([]byte, error) {
	if r == nil {
		return nil, errors.New("intakeingest: nil reader")
	}
	b, err := io.ReadAll(io.LimitReader(r, s.maxBytes+1))
	if err != nil {
		return nil, err
	}
	if int64(len(b)) > s.maxBytes {
		return nil, ErrTooLarge
	}
	return b, nil
}

// Ingest writes one file. With dryRun it only hashes the input (no object or metadata writes).
func (s *Service) Ingest(ctx context.Context, tenant, bucket, name string, r io.Reader,
	contentType string, dryRun bool) (FileResult, error) {
	start := time.Now()
	res := FileResult{Store: path.Base(name), Bucket: bucket, Name: name}
	finish := func(err error) (FileResult, error) {
		res.DurationMS = time.Since(start).Milliseconds()
		if err != nil {
			res.Status = Failed
			res.Error = err.Error()
		}
		return res, err
	}
	if err := validate(tenant, bucket, name); err != nil {
		return finish(err)
	}
	body, err := s.read(r)
	if err != nil {
		return finish(err)
	}
	res.Bytes = int64(len(body))
	res.Checksum = Checksum(body)
	res.ArtifactID = ArtifactID(tenant, bucket, name, res.Checksum)
	if dryRun {
		res.Status = Planned
		return finish(nil)
	}

	found, rev, storedSum, err := s.byID(ctx, tenant, res.ArtifactID)
	if err != nil {
		return finish(err)
	}
	if found {
		res.Revision = rev
		if storedSum != res.Checksum {
			res.Status = Drift
			res.Error = "artifact id exists with a different checksum"
			return finish(nil)
		}
		res.Status = SkippedUnchanged
		return finish(nil)
	}

	ct := ContentTypeFor(name, contentType)
	if _, err := s.objects.Put(ctx, ObjectKey(tenant, bucket, res.Checksum), bytes.NewReader(body),
		int64(len(body)), datastore.PutOptions{ContentType: ct, Immutable: true}); err != nil {
		return finish(err)
	}
	rev, err = s.register(ctx, tenant, bucket, name, res.ArtifactID, res.Checksum, res.Bytes, ct)
	if err != nil {
		// The immutable object is content-addressed and safe to reuse on retry.
		return finish(err)
	}
	res.Revision = rev
	res.Status = Written
	return finish(nil)
}

// Verify checks the current source against the latest stored revision and the object store.
func (s *Service) Verify(ctx context.Context, tenant, bucket, name string, r io.Reader) (FileResult, error) {
	start := time.Now()
	res := FileResult{Store: path.Base(name), Bucket: bucket, Name: name}
	finish := func(err error) (FileResult, error) {
		res.DurationMS = time.Since(start).Milliseconds()
		if err != nil {
			res.Status = Failed
			res.Error = err.Error()
		}
		return res, err
	}
	if err := validate(tenant, bucket, name); err != nil {
		return finish(err)
	}
	body, err := s.read(r)
	if err != nil {
		return finish(err)
	}
	res.Bytes = int64(len(body))
	res.Checksum = Checksum(body)

	found, storedID, rev, storedSum, err := s.latest(ctx, tenant, bucket+"/"+name)
	if err != nil {
		return finish(err)
	}
	if !found {
		return finish(errors.New("no artifact metadata for the source name"))
	}
	res.Revision = rev
	res.ArtifactID = storedID
	if storedSum != res.Checksum {
		res.Status = Drift
		res.Error = "source checksum differs from the latest stored revision"
		return finish(nil)
	}
	objSum, err := s.objectChecksum(ctx, ObjectKey(tenant, bucket, res.Checksum))
	if err != nil {
		if errors.Is(err, ErrTooLarge) {
			return finish(fmt.Errorf("intakeingest: stored object exceeds max-bytes, cannot verify: %w", err))
		}
		return finish(err)
	}
	if objSum != res.Checksum {
		res.Status = Drift
		res.Error = "object-store checksum differs from the artifact checksum"
		return finish(nil)
	}
	res.Status = SkippedUnchanged
	return finish(nil)
}

// Orphans lists objects under the tenant+bucket prefix with no stored_objects row.
func (s *Service) Orphans(ctx context.Context, tenant, bucket string) ([]string, error) {
	if tenant == "" {
		return nil, ErrNoTenant
	}
	if bucket != BucketIntake && bucket != BucketBuilds {
		return nil, ErrBadBucket
	}
	infos, err := s.objects.List(ctx, ObjectKey(tenant, bucket, ""))
	if err != nil {
		return nil, err
	}
	known := map[string]bool{}
	if err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
		rows, err := tx.Query(ctx,
			`SELECT checksum FROM artifacts WHERE tenant_id=$1 AND name LIKE $2 AND deleted_at IS NULL`,
			tenant, bucket+"/%")
		if err != nil {
			return err
		}
		defer rows.Close()
		for rows.Next() {
			var sum string
			if err := rows.Scan(&sum); err != nil {
				return err
			}
			known[sum] = true
		}
		return rows.Err()
	}); err != nil {
		return nil, err
	}
	var out []string
	for _, info := range infos {
		sum := info.Key[strings.LastIndex(info.Key, "/")+1:]
		if !known[sum] {
			out = append(out, info.Key)
		}
	}
	sort.Strings(out)
	return out, nil
}

func (s *Service) byID(ctx context.Context, tenant, id string) (bool, int64, string, error) {
	var rev int64
	var sum string
	found := false
	err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
		rows, err := tx.Query(ctx,
			`SELECT revision, checksum FROM artifacts WHERE id=$1 AND tenant_id=$2 AND deleted_at IS NULL`,
			id, tenant)
		if err != nil {
			return err
		}
		defer rows.Close()
		if rows.Next() {
			if err := rows.Scan(&rev, &sum); err != nil {
				return err
			}
			found = true
		}
		return rows.Err()
	})
	return found, rev, sum, err
}

func (s *Service) latest(ctx context.Context, tenant, logicalName string) (bool, string, int64, string, error) {
	var id string
	var rev int64
	var sum string
	found := false
	err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
		rows, err := tx.Query(ctx,
			`SELECT id, revision, checksum FROM artifacts
			 WHERE tenant_id=$1 AND name=$2 AND deleted_at IS NULL
			 ORDER BY revision DESC LIMIT 1`, tenant, logicalName)
		if err != nil {
			return err
		}
		defer rows.Close()
		if rows.Next() {
			if err := rows.Scan(&id, &rev, &sum); err != nil {
				return err
			}
			found = true
		}
		return rows.Err()
	})
	return found, id, rev, sum, err
}

func (s *Service) objectChecksum(ctx context.Context, key string) (string, error) {
	info, err := s.objects.Head(ctx, key)
	if err == nil && info.Checksum != "" {
		return info.Checksum, nil
	}
	rc, _, gerr := s.objects.Get(ctx, key, "")
	if gerr != nil {
		if err != nil {
			return "", fmt.Errorf("head: %v; get: %w", err, gerr)
		}
		return "", gerr
	}
	defer rc.Close()
	b, rerr := s.read(rc)
	if rerr != nil {
		return "", rerr
	}
	return Checksum(b), nil
}

// register inserts stored_objects + artifacts in one transaction. The revision is allocated under the
// unique (tenant, name, revision) index and the whole transaction is retried on a concurrent conflict, so
// two writers can never duplicate a revision.
func (s *Service) register(ctx context.Context, tenant, bucket, name, id, sum string,
	size int64, contentType string) (int64, error) {
	logicalName := bucket + "/" + name
	var rev int64
	var lastErr error
	for attempt := 0; attempt < 10; attempt++ {
		err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
			if _, err := tx.Exec(ctx,
				`INSERT INTO stored_objects (tenant_id, checksum, size, content_type)
				 VALUES ($1,$2,$3,$4) ON CONFLICT (tenant_id, checksum) DO NOTHING`,
				tenant, sum, size, contentType); err != nil {
				return err
			}
			var next int64
			rows, err := tx.Query(ctx,
				`SELECT COALESCE(MAX(revision), -1) + 1 FROM artifacts WHERE tenant_id=$1 AND name=$2`,
				tenant, logicalName)
			if err != nil {
				return err
			}
			if rows.Next() {
				if err := rows.Scan(&next); err != nil {
					rows.Close()
					return err
				}
			}
			if err := rows.Err(); err != nil {
				rows.Close()
				return err
			}
			rows.Close()
			n, err := tx.Exec(ctx,
				`INSERT INTO artifacts
				   (id, tenant_id, stage, artifact_type, name, revision, object_version, checksum, content_type, size)
				 VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
				 ON CONFLICT (id) DO NOTHING`,
				id, tenant, bucket, artifactType(bucket), logicalName, next, sum, sum, contentType, size)
			if err != nil {
				return err
			}
			if n == 1 {
				rev = next
				return nil
			}
			rows, err = tx.Query(ctx, `SELECT revision FROM artifacts WHERE id=$1`, id)
			if err != nil {
				return err
			}
			defer rows.Close()
			if rows.Next() {
				if err := rows.Scan(&rev); err != nil {
					return err
				}
			}
			return rows.Err()
		})
		if err == nil {
			return rev, nil
		}
		if !isUniqueViolation(err) {
			return 0, err
		}
		lastErr = err
		select {
		case <-ctx.Done():
			return 0, ctx.Err()
		case <-time.After(time.Duration(attempt+1) * 10 * time.Millisecond):
		}
	}
	return 0, fmt.Errorf("intakeingest: revision allocation conflict after retries: %w", lastErr)
}

func isUniqueViolation(err error) bool {
	var sqlErr interface{ SQLState() string }
	return errors.As(err, &sqlErr) && sqlErr.SQLState() == "23505"
}
