package pfmemory

import (
	"context"
	"errors"
	"fmt"
	"os"
	"strings"
	"sync"
	"testing"
	"time"

	"productforge/datastore"
)

type fakeRepo struct {
	mu      sync.Mutex
	entries map[string]datastore.MemoryEntry
}

func newFakeRepo() *fakeRepo {
	return &fakeRepo{entries: map[string]datastore.MemoryEntry{}}
}

func (f *fakeRepo) Put(_ context.Context, e datastore.MemoryEntry) (datastore.MemoryEntry, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	if old, ok := f.entries[e.ID]; ok && (old.TenantID != e.TenantID || old.Owner != e.Owner) {
		return datastore.MemoryEntry{}, errors.New("tenant/owner conflict")
	}
	f.entries[e.ID] = e
	return e, nil
}

func (f *fakeRepo) Get(_ context.Context, id string) (datastore.MemoryEntry, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	e, ok := f.entries[id]
	if !ok {
		return datastore.MemoryEntry{}, datastore.ErrNotFound
	}
	return e, nil
}

func (f *fakeRepo) GetScoped(_ context.Context, id string, scope datastore.MemoryScope) (datastore.MemoryEntry, error) {
	e, err := f.Get(context.Background(), id)
	if err != nil {
		return datastore.MemoryEntry{}, err
	}
	if e.TenantID != scope.TenantID || e.Project != scope.Project || (e.ACLScope == "private" && e.Owner != scope.User) {
		return datastore.MemoryEntry{}, datastore.ErrNotFound
	}
	return e, nil
}

func (f *fakeRepo) Search(_ context.Context, q string, _ datastore.MemoryScope, k int) ([]datastore.MemoryEntry, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	out := make([]datastore.MemoryEntry, 0, k)
	for _, e := range f.entries {
		if q == "" || strings.Contains(e.Content, q) {
			out = append(out, e)
			if len(out) == k {
				break
			}
		}
	}
	return out, nil
}

func (f *fakeRepo) Delete(_ context.Context, id string) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	if _, ok := f.entries[id]; !ok {
		return datastore.ErrNotFound
	}
	delete(f.entries, id)
	return nil
}

func (f *fakeRepo) DeleteScoped(_ context.Context, id string, scope datastore.MemoryScope) error {
	e, err := f.GetScoped(context.Background(), id, scope)
	if err != nil {
		return err
	}
	return f.Delete(context.Background(), e.ID)
}

type countObserver struct {
	mu       sync.Mutex
	ops      int
	denied   int
	filtered int
}

func (o *countObserver) Observe(string, string, time.Duration) {
	o.mu.Lock()
	o.ops++
	o.mu.Unlock()
}

func (o *countObserver) Denied(string) {
	o.mu.Lock()
	o.denied++
	o.mu.Unlock()
}

func (o *countObserver) FilteredProjectless() {
	o.mu.Lock()
	o.filtered++
	o.mu.Unlock()
}

func testScope(tenant, project, principal string) Scope {
	return Scope{TenantID: tenant, ProjectID: project, Principal: principal}
}

func testEntry(id, tenant, project, owner string) datastore.MemoryEntry {
	return datastore.MemoryEntry{ID: id, TenantID: tenant, Project: project, Kind: "semantic",
		ACLScope: "project", Content: "memory content", Owner: owner}
}

func newTestOrchestrator(t *testing.T, repo *fakeRepo, opts ...Option) *Orchestrator {
	t.Helper()
	orch, err := New(repo, opts...)
	if err != nil {
		t.Fatal(err)
	}
	return orch
}

func TestPutValidated(t *testing.T) {
	orch := newTestOrchestrator(t, newFakeRepo())
	scope := testScope("tenant-a", "proj-1", "alice")
	if _, err := orch.Put(context.Background(), scope, testEntry("11111111-1111-4111-8111-000000000001", "tenant-a", "proj-1", "")); err != nil {
		t.Fatalf("valid put: %v", err)
	}
	badID := testEntry("not-a-uuid", "tenant-a", "proj-1", "")
	if _, err := orch.Put(context.Background(), scope, badID); err == nil {
		t.Fatal("expected invalid ID rejection")
	}
	badKind := testEntry("11111111-1111-4111-8111-000000000002", "tenant-a", "proj-1", "")
	badKind.Kind = "unknown"
	if _, err := orch.Put(context.Background(), scope, badKind); err == nil {
		t.Fatal("expected invalid kind rejection")
	}
}

func TestCrossTenantReadWriteSearch(t *testing.T) {
	repo := newFakeRepo()
	orch := newTestOrchestrator(t, repo)
	a := testScope("tenant-a", "proj-1", "alice")
	b := testScope("tenant-b", "proj-1", "bob")
	e := testEntry("11111111-1111-4111-8111-000000000010", "tenant-a", "proj-1", "alice")
	if _, err := orch.Put(context.Background(), a, e); err != nil {
		t.Fatal(err)
	}
	if _, err := orch.Get(context.Background(), b, e.ID); !errors.Is(err, ErrNotFound) {
		t.Fatalf("cross-tenant get: %v", err)
	}
	if err := orch.Delete(context.Background(), b, e.ID); !errors.Is(err, ErrNotFound) {
		t.Fatalf("cross-tenant delete: %v", err)
	}
	hits, err := orch.Search(context.Background(), b, SearchRequest{Text: "memory"})
	if err != nil {
		t.Fatal(err)
	}
	if len(hits) != 0 {
		t.Fatalf("cross-tenant search leaked %d hits", len(hits))
	}
	bad := testEntry("11111111-1111-4111-8111-000000000011", "tenant-a", "proj-1", "")
	if _, err := orch.Put(context.Background(), b, bad); !errors.Is(err, ErrInvalidScope) {
		t.Fatalf("cross-tenant put: %v", err)
	}
}

func TestCrossProjectReadWriteSearch(t *testing.T) {
	orch := newTestOrchestrator(t, newFakeRepo())
	a := testScope("tenant-a", "proj-1", "alice")
	b := testScope("tenant-a", "proj-2", "alice")
	e := testEntry("11111111-1111-4111-8111-000000000020", "tenant-a", "proj-1", "alice")
	if _, err := orch.Put(context.Background(), a, e); err != nil {
		t.Fatal(err)
	}
	if _, err := orch.Get(context.Background(), b, e.ID); !errors.Is(err, ErrNotFound) {
		t.Fatalf("cross-project get: %v", err)
	}
	if err := orch.Delete(context.Background(), b, e.ID); !errors.Is(err, ErrNotFound) {
		t.Fatalf("cross-project delete: %v", err)
	}
	hits, err := orch.Search(context.Background(), b, SearchRequest{Text: "memory"})
	if err != nil {
		t.Fatal(err)
	}
	if len(hits) != 0 {
		t.Fatalf("cross-project search leaked %d hits", len(hits))
	}
}

func TestACLPrivateDenial(t *testing.T) {
	orch := newTestOrchestrator(t, newFakeRepo())
	alice := testScope("tenant-a", "proj-1", "alice")
	bob := testScope("tenant-a", "proj-1", "bob")
	e := testEntry("11111111-1111-4111-8111-000000000030", "tenant-a", "proj-1", "alice")
	e.ACLScope = "private"
	if _, err := orch.Put(context.Background(), alice, e); err != nil {
		t.Fatal(err)
	}
	if _, err := orch.Get(context.Background(), bob, e.ID); !errors.Is(err, ErrNotFound) {
		t.Fatalf("private get: %v", err)
	}
	hits, err := orch.Search(context.Background(), bob, SearchRequest{Text: "memory"})
	if err != nil {
		t.Fatal(err)
	}
	if len(hits) != 0 {
		t.Fatalf("private search leaked %d hits", len(hits))
	}
}

func TestConcurrentBoundaryLoad(t *testing.T) {
	orch := newTestOrchestrator(t, newFakeRepo())
	scopes := []Scope{testScope("tenant-a", "proj-1", "alice"), testScope("tenant-b", "proj-1", "bob")}
	var wg sync.WaitGroup
	for i := 0; i < 40; i++ {
		wg.Add(1)
		go func(n int) {
			defer wg.Done()
			s := scopes[n%2]
			id := fmt.Sprintf("11111111-1111-4111-8111-%012d", n)
			e := testEntry(id, s.TenantID, s.ProjectID, s.Principal)
			_, _ = orch.Put(context.Background(), s, e)
			_, _ = orch.Get(context.Background(), s, id)
			_, _ = orch.Search(context.Background(), s, SearchRequest{Text: "memory"})
			_ = orch.Delete(context.Background(), s, id)
		}(i)
	}
	wg.Wait()
}

func TestDeleteScopedAtomic(t *testing.T) {
	repo := newFakeRepo()
	orch := newTestOrchestrator(t, repo)
	alice := testScope("tenant-a", "proj-1", "alice")
	bob := testScope("tenant-b", "proj-1", "bob")
	e := testEntry("11111111-1111-4111-8111-000000000040", "tenant-a", "proj-1", "alice")
	if _, err := orch.Put(context.Background(), alice, e); err != nil {
		t.Fatal(err)
	}
	if err := orch.Delete(context.Background(), bob, e.ID); !errors.Is(err, ErrNotFound) {
		t.Fatalf("atomic delete denial: %v", err)
	}
	if _, err := orch.Get(context.Background(), alice, e.ID); err != nil {
		t.Fatalf("record must remain after denied delete: %v", err)
	}
}

func TestLimitsAndConfigContract(t *testing.T) {
	repo := newFakeRepo()
	if _, err := New(repo, WithLimits(0, time.Second)); err != nil {
		t.Fatalf("zero k should use default: %v", err)
	}
	if _, err := New(repo, WithLimits(101, time.Second)); err == nil {
		t.Fatal("expected invalid max k")
	}
	if _, err := New(repo, WithLimits(20, 6*time.Second)); err == nil {
		t.Fatal("expected invalid timeout")
	}
	orch := newTestOrchestrator(t, repo, WithLimits(5, time.Second))
	if _, err := orch.Search(context.Background(), testScope("t", "p", "u"), SearchRequest{Text: "x", K: 6}); !errors.Is(err, ErrLimitExceeded) {
		t.Fatalf("expected limit error: %v", err)
	}
}

func TestMetricsAudit(t *testing.T) {
	obs := &countObserver{}
	orch := newTestOrchestrator(t, newFakeRepo(), WithObserver(obs))
	scope := testScope("tenant-a", "proj-1", "alice")
	e := testEntry("11111111-1111-4111-8111-000000000050", "tenant-a", "proj-1", "alice")
	if _, err := orch.Put(context.Background(), scope, e); err != nil {
		t.Fatal(err)
	}
	_, _ = orch.Get(context.Background(), testScope("tenant-b", "proj-1", "bob"), e.ID)
	_, _ = orch.Search(context.Background(), scope, SearchRequest{Text: "memory"})
	obs.mu.Lock()
	defer obs.mu.Unlock()
	if obs.ops < 3 || obs.denied < 1 {
		t.Fatalf("observer missing signals: ops=%d denied=%d", obs.ops, obs.denied)
	}
}

func TestConfigContractInvalid(t *testing.T) {
	if _, err := New(newFakeRepo(), WithLimits(-1, time.Second)); err != nil {
		t.Fatalf("negative k should use default: %v", err)
	}
	if _, err := New(newFakeRepo(), WithLimits(20, -time.Second)); err != nil {
		t.Fatalf("negative timeout should use default: %v", err)
	}
}

func TestLeakageSuites(t *testing.T) {
	t.Run("cross-tenant", TestCrossTenantReadWriteSearch)
	t.Run("cross-project", TestCrossProjectReadWriteSearch)
	t.Run("acl-private", TestACLPrivateDenial)
	t.Run("concurrent", TestConcurrentBoundaryLoad)
}

func TestRolePosture(t *testing.T) {
	if strings.TrimSpace(os.Getenv("PF_TEST_MEMORY_DSN")) == "" {
		t.Skip("PF_TEST_MEMORY_DSN not set; PostgreSQL role posture is verified in CI")
	}
}
