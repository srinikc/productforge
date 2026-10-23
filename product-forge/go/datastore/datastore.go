// Package datastore defines Product Forge's provider-neutral storage interfaces (EDP-07 / BI-PF-1299).
//
// The canonical access layer from ADR-0006: domain logic depends ONLY on these interfaces, never on a
// concrete provider (Postgres, S3, Redis, a secret manager, ...). Each interface has a shared conformance
// suite so a local adapter and a cloud adapter can be swapped without changing domain code. Providers must
// declare optional capabilities explicitly (Capabilities) - no lowest-common-denominator assumptions.
//
// Go-first per ADR-0001 (new shipped/sensitive logic -> Go). Reference adapter to reuse: workergrid/internal/store.
package datastore

import (
	"context"
	"errors"
	"io"
	"time"
)

// Capabilities declares optional provider features. Never assume a provider supports them; adapters report
// their real capabilities and callers degrade explicitly (ADR-0006 "provider portability = tested contracts").
type Capabilities struct {
	Transactions        bool
	ObjectVersioning    bool
	ObjectLock          bool
	ConditionalWrites   bool
	SignedURLs          bool
	MultipartUpload     bool
	CustomerManagedKeys bool
}

// ---- Relational system of record (PostgreSQL) ----

type RelationalStore interface {
	Ping(ctx context.Context) error
	// WithTx runs fn inside a transaction; it MUST roll back on error and commit on success.
	WithTx(ctx context.Context, fn func(Tx) error) error
	Capabilities() Capabilities
}

type Tx interface {
	Exec(ctx context.Context, sql string, args ...any) (rowsAffected int64, err error)
	Query(ctx context.Context, sql string, args ...any) (Rows, error)
	Commit(ctx context.Context) error
	Rollback(ctx context.Context) error
}

type Rows interface {
	Next() bool
	Scan(dest ...any) error
	Err() error
	Close() error
}

// ---- Object store (bytes) ----

type PutOptions struct {
	ContentType string
	Checksum    string
	Immutable   bool
	Retention   time.Duration
	// ServerSideEncryption requests provider-managed encryption (e.g. "aws:kms"); adapters that cannot
	// honour it MUST reject the write rather than silently store plaintext.
	ServerSideEncryption string
}

type ObjectInfo struct {
	Key         string
	Version     string
	Checksum    string
	ContentType string
	Size        int64
}

// LifecyclePolicy is the requested object-lock state. Mode is GOVERNANCE or COMPLIANCE; COMPLIANCE cannot
// be shortened or removed once applied (one-way door - callers must opt in explicitly).
type LifecyclePolicy struct {
	Mode        string // GOVERNANCE | COMPLIANCE
	RetainUntil time.Time
	LegalHold   bool
}

// LifecycleState is the effective object-lock state reported by a provider.
type LifecycleState struct {
	Mode        string
	RetainUntil time.Time
	LegalHold   bool
}

// ErrUnsupported is returned by adapters that cannot honour a requested capability (fail closed).
var ErrUnsupported = errors.New("datastore: capability unsupported")

// LifecycleCapable is an OPTIONAL capability: providers that support object lock/retention implement it.
// Look it up with Lifecycle(store) instead of asserting it unconditionally.
type LifecycleCapable interface {
	ApplyLifecycle(ctx context.Context, key string, policy LifecyclePolicy) error
	ObjectLifecycle(ctx context.Context, key string) (LifecycleState, error)
}

// Lifecycle returns the provider's lifecycle capability, if any.
func Lifecycle(store ObjectStore) (LifecycleCapable, bool) {
	lc, ok := store.(LifecycleCapable)
	return lc, ok
}

type ObjectStore interface {
	Put(ctx context.Context, key string, r io.Reader, size int64, opts PutOptions) (ObjectInfo, error)
	Get(ctx context.Context, key, version string) (io.ReadCloser, ObjectInfo, error)
	Head(ctx context.Context, key string) (ObjectInfo, error)
	Delete(ctx context.Context, key, version string) error
	List(ctx context.Context, prefix string) ([]ObjectInfo, error)
	// SignedURL issues an authorized, short-lived, method-scoped URL (only when authorized).
	SignedURL(ctx context.Context, key, method string, ttl time.Duration) (string, error)
	Capabilities() Capabilities
}

// ---- Immutable artifacts (metadata in the SoR, bytes in the object store) ----

type ArtifactService interface {
	Register(ctx context.Context, a Artifact) (Artifact, error)
	Get(ctx context.Context, id string) (Artifact, error)
	FetchContent(ctx context.Context, id string) (io.ReadCloser, error)
	Verify(ctx context.Context, id string) (bool, error)
	Delete(ctx context.Context, id string) error
}

type Artifact struct {
	ID        string
	TenantID  string
	Project   string
	Run       string
	Stage     string
	Type      string
	ObjectRef string // opaque ObjectStore reference; never a provider URL
	Checksum  string
	Size      int64
	Version   string
}

// ---- Memory (metadata + provenance; large payloads referenced in the object store) ----

type MemoryEntry struct {
	ID        string
	TenantID  string
	Project   string
	Kind      string
	ObjectRef string
	ACLScope  string
	Content   string
	Source    string
	Owner     string
	Score     float32
	Embedding []float32
}

type MemoryRepository interface {
	Put(ctx context.Context, e MemoryEntry) (MemoryEntry, error)
	Get(ctx context.Context, id string) (MemoryEntry, error)
	// Search MUST apply tenant/project/source ACL filters BEFORE returning (never bypass authz).
	Search(ctx context.Context, q string, scope MemoryScope, k int) ([]MemoryEntry, error)
	Delete(ctx context.Context, id string) error
}

type MemoryScope struct {
	TenantID string
	Project  string
	Source   string
	ACL      string    // optional acl_scope filter (legacy `source` values are mapped by the API)
	User     string    // caller principal: private entries are visible only to their owner
	Kinds    []string  // optional memory-type filter (all eight types when empty)
	Vector   []float32 // optional query embedding; used only when pgvector is available
}

// ---- Durable jobs / leases (ONE job truth; reuse workergrid/internal/store as reference) ----

type JobStore interface {
	Submit(ctx context.Context, j Job) (Job, error)
	Claim(ctx context.Context, worker string, ttl time.Duration) (Job, bool, error)
	Heartbeat(ctx context.Context, id, lease string) error
	Complete(ctx context.Context, id, lease string) error
	Fail(ctx context.Context, id, lease, reason string) error
	Release(ctx context.Context, id, lease string) error
}

type Job struct {
	ID             string
	TenantID       string
	Kind           string
	Status         string
	Priority       int
	Attempt        int
	LeaseID        string
	ExpiresAt      time.Time
	IdempotencyKey string
}

// ---- Transactional outbox (at-least-once async effects) ----

type OutboxStore interface {
	Append(ctx context.Context, e Event) error // MUST be in the same Tx as the state change
	ClaimBatch(ctx context.Context, n int) ([]Event, error)
	MarkDelivered(ctx context.Context, id string) error
	MarkFailed(ctx context.Context, id, reason string) error
}

type Event struct {
	ID       string
	TenantID string
	Type     string
	Payload  []byte
	At       time.Time
}

// ---- Cache (optional; never a correctness mechanism) ----

type CacheStore interface {
	Get(ctx context.Context, key string) ([]byte, bool, error)
	Set(ctx context.Context, key string, val []byte, ttl time.Duration) error
	Delete(ctx context.Context, key string) error
}

// ---- Secrets (resolve by reference; never return secrets in config APIs) ----

type SecretStore interface {
	Resolve(ctx context.Context, ref string) (string, error)
}

// ---- Audit (append-only, tamper-evident) ----

type AuditStore interface {
	Append(ctx context.Context, e AuditEvent) error
}

type AuditEvent struct {
	TenantID      string
	Actor         string
	Action        string
	Resource      string
	Outcome       string
	CorrelationID string
	At            time.Time
}

// ---- Backup / recovery ----

type BackupProvider interface {
	Backup(ctx context.Context, label string) (BackupRef, error)
	Restore(ctx context.Context, ref BackupRef) error
	Verify(ctx context.Context, ref BackupRef) (bool, error)
}

type BackupRef struct {
	ID        string
	Region    string
	CreatedAt time.Time
}

// ---- Search / vector (scope filters mandatory; PG FTS first, external only if measured) ----

type SearchProvider interface {
	Index(ctx context.Context, doc SearchDoc) error
	Query(ctx context.Context, q string, scope MemoryScope, k int) ([]SearchDoc, error)
}

type SearchDoc struct {
	ID     string
	Scope  MemoryScope
	Text   string
	Vector []float32
}
