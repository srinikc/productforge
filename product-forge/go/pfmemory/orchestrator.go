package pfmemory

import (
	"context"
	"errors"
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"

	"productforge/datastore"
	"productforge/memory"
)

var (
	ErrInvalidScope            = errors.New("pfmemory: invalid scope")
	ErrValidation              = errors.New("pfmemory: validation failed")
	ErrNotFound                = errors.New("pfmemory: not found")
	ErrScopedReadUnsupported   = errors.New("pfmemory: scoped read unsupported")
	ErrScopedDeleteUnsupported = errors.New("pfmemory: scoped delete unsupported")
	ErrLimitExceeded           = errors.New("pfmemory: limit exceeded")
)

const (
	defaultMaxSearchK = 20
	maxSearchK        = 100
	maxOperationTime  = 5 * time.Second
)

// Scope is the server-resolved authority for a memory operation.
type Scope struct {
	TenantID  string
	ProjectID string
	Principal string
	Role      string
}

func (s Scope) valid() bool {
	return strings.TrimSpace(s.TenantID) != "" &&
		strings.TrimSpace(s.ProjectID) != "" &&
		strings.TrimSpace(s.Principal) != ""
}

// ScopedGetter is implemented by storage adapters that can filter a read in storage.
type ScopedGetter interface {
	GetScoped(ctx context.Context, id string, scope datastore.MemoryScope) (datastore.MemoryEntry, error)
}

// ScopedDeleter is implemented by storage adapters that can filter a delete in storage.
type ScopedDeleter interface {
	DeleteScoped(ctx context.Context, id string, scope datastore.MemoryScope) error
}

// SearchRequest is the caller-facing search input. Tenant/project/principal never come from here.
type SearchRequest struct {
	Text   string
	K      int
	Source string
	ACL    string
	Kinds  []string
}

// Orchestrator is the single governed gateway for memory operations.
type AuditEvent struct {
	Op        string
	TenantID  string
	ProjectID string
	Actor     string
	RecordID  string
	Outcome   string
	Reason    string
}

type Auditor interface {
	Audit(AuditEvent)
}

type Orchestrator struct {
	repo    datastore.MemoryRepository
	obs     Observer
	auditor Auditor
	maxK    int
	timeout time.Duration
}

type Option func(*Orchestrator)

func WithLimits(k int, timeout time.Duration) Option {
	return func(o *Orchestrator) {
		if k > 0 {
			o.maxK = k
		}
		if timeout > 0 {
			o.timeout = timeout
		}
	}
}

func WithObserver(obs Observer) Option {
	return func(o *Orchestrator) {
		if obs != nil {
			o.obs = obs
		}
	}
}

func WithAuditor(a Auditor) Option {
	return func(o *Orchestrator) { o.auditor = a }
}

func LoadLimitsFromEnv() (int, time.Duration, error) {
	k := defaultMaxSearchK
	if raw := strings.TrimSpace(os.Getenv("PF_MEMORY_MAX_SEARCH_K")); raw != "" {
		v, err := strconv.Atoi(raw)
		if err != nil {
			return 0, 0, fmt.Errorf("pfmemory: invalid PF_MEMORY_MAX_SEARCH_K: %w", err)
		}
		k = v
	}
	timeout := maxOperationTime
	if raw := strings.TrimSpace(os.Getenv("PF_MEMORY_OP_TIMEOUT")); raw != "" {
		v, err := time.ParseDuration(raw)
		if err != nil {
			return 0, 0, fmt.Errorf("pfmemory: invalid PF_MEMORY_OP_TIMEOUT: %w", err)
		}
		timeout = v
	}
	if k < 1 || k > maxSearchK {
		return 0, 0, fmt.Errorf("pfmemory: max search k must be 1..%d", maxSearchK)
	}
	if timeout <= 0 || timeout > maxOperationTime {
		return 0, 0, fmt.Errorf("pfmemory: timeout must be positive and <= %s", maxOperationTime)
	}
	return k, timeout, nil
}

func New(repo datastore.MemoryRepository, opts ...Option) (*Orchestrator, error) {
	if repo == nil {
		return nil, errors.New("pfmemory: nil repository")
	}
	o := &Orchestrator{repo: repo, obs: noopObserver{}, maxK: defaultMaxSearchK, timeout: maxOperationTime}
	for _, opt := range opts {
		opt(o)
	}
	if o.maxK < 1 || o.maxK > maxSearchK {
		return nil, fmt.Errorf("pfmemory: max search k must be 1..%d", maxSearchK)
	}
	if o.timeout <= 0 || o.timeout > maxOperationTime {
		return nil, fmt.Errorf("pfmemory: timeout must be positive and <= %s", maxOperationTime)
	}
	return o, nil
}

func (o *Orchestrator) Put(ctx context.Context, scope Scope, entry datastore.MemoryEntry) (datastore.MemoryEntry, error) {
	start := time.Now()
	res, err := o.put(ctx, scope, entry)
	o.observe("put", start, err)
	o.auditOutcome("write", scope, res.ID, err)
	return res, err
}

func (o *Orchestrator) put(ctx context.Context, scope Scope, entry datastore.MemoryEntry) (datastore.MemoryEntry, error) {
	if !scope.valid() {
		return datastore.MemoryEntry{}, o.deny("scope", ErrInvalidScope)
	}
	if entry.TenantID != "" && entry.TenantID != scope.TenantID {
		return datastore.MemoryEntry{}, o.deny("tenant", ErrInvalidScope)
	}
	if entry.Project != "" && entry.Project != scope.ProjectID {
		return datastore.MemoryEntry{}, o.deny("project", ErrInvalidScope)
	}
	ctx, cancel := o.context(ctx)
	defer cancel()

	entry.TenantID = scope.TenantID
	entry.Project = scope.ProjectID
	entry.Owner = scope.Principal
	if entry.ACLScope == "" {
		entry.ACLScope = "project"
	}
	rec := canonicalRecord(scope, entry)
	if err := rec.Validate(); err != nil {
		return datastore.MemoryEntry{}, o.deny("validation", fmt.Errorf("%w: %v", ErrValidation, err))
	}
	res, err := o.repo.Put(ctx, entry)
	if err != nil {
		return datastore.MemoryEntry{}, err
	}
	return res, nil
}

func (o *Orchestrator) Get(ctx context.Context, scope Scope, id string) (datastore.MemoryEntry, error) {
	start := time.Now()
	res, err := o.get(ctx, scope, id)
	o.observe("get", start, err)
	o.auditOutcome("read", scope, id, err)
	return res, err
}

func (o *Orchestrator) get(ctx context.Context, scope Scope, id string) (datastore.MemoryEntry, error) {
	if !scope.valid() {
		return datastore.MemoryEntry{}, o.deny("scope", ErrInvalidScope)
	}
	getter, ok := o.repo.(ScopedGetter)
	if !ok {
		return datastore.MemoryEntry{}, o.deny("scoped_read", ErrScopedReadUnsupported)
	}
	ctx, cancel := o.context(ctx)
	defer cancel()
	entry, err := getter.GetScoped(ctx, id, scopeForRepo(scope, "", "", nil))
	if errors.Is(err, datastore.ErrNotFound) {
		o.obs.Denied("not_found")
		return datastore.MemoryEntry{}, ErrNotFound
	}
	if err != nil {
		return datastore.MemoryEntry{}, err
	}
	if !visible(entry, scope) {
		return datastore.MemoryEntry{}, o.deny("acl", ErrNotFound)
	}
	return entry, nil
}

func (o *Orchestrator) Search(ctx context.Context, scope Scope, req SearchRequest) ([]datastore.MemoryEntry, error) {
	start := time.Now()
	res, err := o.search(ctx, scope, req)
	o.observe("search", start, err)
	o.auditOutcome("search", scope, "", err)
	return res, err
}

func (o *Orchestrator) search(ctx context.Context, scope Scope, req SearchRequest) ([]datastore.MemoryEntry, error) {
	if !scope.valid() {
		return nil, o.deny("scope", ErrInvalidScope)
	}
	if req.K == 0 {
		req.K = o.maxK
	}
	if req.K < 1 || req.K > o.maxK || req.K > maxSearchK {
		return nil, o.deny("limit", ErrLimitExceeded)
	}
	ctx, cancel := o.context(ctx)
	defer cancel()
	hits, err := o.repo.Search(ctx, req.Text, scopeForRepo(scope, req.Source, req.ACL, req.Kinds), req.K)
	if err != nil {
		return nil, o.mapStoreError(err)
	}
	out := make([]datastore.MemoryEntry, 0, len(hits))
	for _, hit := range hits {
		if hit.Project == "" {
			o.obs.FilteredProjectless()
			continue
		}
		if !visible(hit, scope) {
			o.obs.Denied("search_filter")
			continue
		}
		out = append(out, hit)
	}
	return out, nil
}

func (o *Orchestrator) Delete(ctx context.Context, scope Scope, id string) error {
	start := time.Now()
	err := o.delete(ctx, scope, id)
	o.observe("delete", start, err)
	o.auditOutcome("delete", scope, id, err)
	return err
}

func (o *Orchestrator) delete(ctx context.Context, scope Scope, id string) error {
	if !scope.valid() {
		return o.deny("scope", ErrInvalidScope)
	}
	deleter, ok := o.repo.(ScopedDeleter)
	if !ok {
		return o.deny("scoped_delete", ErrScopedDeleteUnsupported)
	}
	ctx, cancel := o.context(ctx)
	defer cancel()
	if _, err := o.get(ctx, scope, id); err != nil {
		return err
	}
	if err := deleter.DeleteScoped(ctx, id, scopeForRepo(scope, "", "", nil)); errors.Is(err, datastore.ErrNotFound) {
		o.obs.Denied("not_found")
		return ErrNotFound
	} else if err != nil {
		return err
	}
	return nil
}

func (o *Orchestrator) Validate(_ context.Context, scope Scope, entry datastore.MemoryEntry) error {
	if !scope.valid() {
		return ErrInvalidScope
	}
	if entry.TenantID != "" && entry.TenantID != scope.TenantID {
		return ErrInvalidScope
	}
	if entry.Project != "" && entry.Project != scope.ProjectID {
		return ErrInvalidScope
	}
	entry.TenantID = scope.TenantID
	entry.Project = scope.ProjectID
	return canonicalRecord(scope, entry).Validate()
}

func canonicalRecord(scope Scope, entry datastore.MemoryEntry) *memory.MemoryRecord {
	now := time.Now().UTC()
	rec := &memory.MemoryRecord{
		ID:         entry.ID,
		TenantID:   scope.TenantID,
		ProjectID:  scope.ProjectID,
		Kind:       memory.MemoryKind(entry.Kind),
		Scope:      entry.ACLScope,
		Content:    entry.Content,
		Confidence: 1,
		ValidFrom:  now,
		Embedding:  entry.Embedding,
		Provenance: memory.ProvenanceInfo{CreatedBy: scope.Principal, CreatedAt: now},
		Evidence:   memory.MemoryEvidence{Source: entry.Source, RecordedBy: scope.Principal},
	}
	if rec.Content == "" && strings.TrimSpace(entry.ObjectRef) != "" {
		rec.PayloadRef = entry.ObjectRef
	}
	return rec
}

func scopeForRepo(scope Scope, source, acl string, kinds []string) datastore.MemoryScope {
	return datastore.MemoryScope{
		TenantID: scope.TenantID,
		Project:  scope.ProjectID,
		Source:   source,
		ACL:      acl,
		User:     scope.Principal,
		Kinds:    kinds,
	}
}

func visible(entry datastore.MemoryEntry, scope Scope) bool {
	if entry.TenantID != scope.TenantID || entry.Project != scope.ProjectID {
		return false
	}
	if entry.ACLScope == "private" && entry.Owner != scope.Principal {
		return false
	}
	return true
}

func (o *Orchestrator) context(ctx context.Context) (context.Context, context.CancelFunc) {
	return context.WithTimeout(ctx, o.timeout)
}

func (o *Orchestrator) mapStoreError(err error) error {
	if errors.Is(err, datastore.ErrNotFound) {
		return ErrNotFound
	}
	return err
}

func (o *Orchestrator) deny(reason string, err error) error {
	o.obs.Denied(reason)
	return err
}

func (o *Orchestrator) auditOutcome(op string, scope Scope, recordID string, err error) {
	if err == nil {
		o.audit(op, scope, recordID, "allow", "")
		return
	}
	reason := "error"
	if errors.Is(err, ErrNotFound) {
		reason = "not_found"
	} else if errors.Is(err, ErrInvalidScope) {
		reason = "invalid_scope"
	} else if errors.Is(err, ErrValidation) {
		reason = "validation"
	} else if errors.Is(err, ErrLimitExceeded) {
		reason = "limit"
	}
	o.audit(op, scope, recordID, "deny", reason)
}

func (o *Orchestrator) audit(op string, scope Scope, recordID string, outcome string, reason string) {
	if o.auditor == nil {
		return
	}
	o.auditor.Audit(AuditEvent{Op: op, TenantID: scope.TenantID, ProjectID: scope.ProjectID, Actor: scope.Principal, RecordID: recordID, Outcome: outcome, Reason: reason})
}

func (o *Orchestrator) observe(op string, start time.Time, err error) {
	result := "ok"
	if err != nil {
		result = "error"
		if errors.Is(err, ErrNotFound) || errors.Is(err, ErrInvalidScope) || errors.Is(err, ErrLimitExceeded) {
			result = "denied"
		}
	}
	o.obs.Observe(op, result, time.Since(start))
}
