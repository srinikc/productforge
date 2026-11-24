# Memory Orchestrator Design - BI-PF-1567

- Item: BI-PF-1567
- Epic: BI-PF-1565 Unified Agent Memory Platform
- Scope: Go-only governed gateway for existing memory operations
- Runtime surface: existing `edpsvc` `/memory` routes
- Status: Gate 0 design candidate

## 1. RECONCILIATION

### PRIOR DECISIONS
- BI-PF-1565 defines one unified memory platform; BI-PF-1566 delivered the canonical `MemoryRecord` contract.
- New shipped or security-sensitive logic is Go. `core/memory_orchestrator.py` is prohibited.
- PostgreSQL remains the system of record for memory metadata; runtime roles must remain NOSUPERUSER/NOBYPASSRLS and RLS stays FORCEd.
- `/memory` already exists as the EDP memory surface; this item governs it rather than creating a second public API.
- Consolidation belongs to BI-PF-1569; governance/lifecycle belongs to BI-PF-1570.

### EXISTING PATH
- Canonical validation: `go/memory/record.go:67` (`MemoryKind`), `go/memory/record.go:180` (`MemoryRecord.Validate`), `go/memory/record.go:419` (`MapLegacyType`).
- Repository contract: `go/datastore/datastore.go:187` (`MemoryEntry`), `go/datastore/datastore.go:201` (`MemoryRepository`), `go/datastore/datastore.go:209` (`MemoryScope`).
- HTTP routes: `go/edpsvc/main.go:334` (`/memory`), `go/edpsvc/main.go:335` (`/memory/`).
- Handler wiring: `go/edpsvc/main.go:1145` (`resolveMemory`), `go/edpsvc/main.go:1166` (`memoryHandle`), `go/edpsvc/main.go:1249` (`memoryByID`).
- SQLite fallback: `go/dualvec/sqlite_store.go:230` (`Get` by ID), `go/dualvec/sqlite_store.go:256` (`Delete` by ID), `go/dualvec/sqlite_store.go:281` (`Search`).
- The existing fallback Get/Delete paths do not compare tenant/project/ACL before returning or deleting. That is the defect this item closes.

### ASSUMPTIONS
- The authenticated principal and tenant are resolved by the server boundary; callers never supply authoritative tenant identity.
- `datastore.MemoryRepository` remains the storage adapter for both PostgreSQL and SQLite test mode.
- Existing `/memory` response shapes must remain compatible for allowed operations.
- Memory writes after this item require a non-empty project. Legacy project-empty rows will not be returned by governed reads.

### DIVERGENCES
- D-1: strict project isolation. Existing SQLite Search includes `project_id IS NULL` rows; this gateway excludes them. This is required by AC-2 and needs Gate 1 HIL approval. Migration/backfill ownership is BI-PF-1570; `memory_filtered_projectless_total` makes filtered legacy rows observable.
- D-2: `Consolidate` is removed from this item and deferred to BI-PF-1569 to keep one end-to-end capability per item.
- D-3: no new public API. Existing `/memory` remains the only surface.

### OPEN QUESTIONS
- None for this item. D-1 is an explicit Gate 1 approval item.

## 2. Runtime contract

| Field | Value |
|---|---|
| Trigger | HTTP memory operations on `edpsvc` and internal Go callers using the gateway |
| Production entrypoint | `go/pfmemory/orchestrator.go:Orchestrator` |
| Call sites | `go/edpsvc/main.go:memoryHandle`, `go/edpsvc/main.go:memoryByID` |
| Adapter | `datastore.MemoryRepository` backed by `dualvec` PostgreSQL or SQLite |
| Inputs | Authenticated `Scope` + operation payload |
| Outputs | Scoped memory record, search hits, delete acknowledgement, or non-leaky `ErrNotFound` |
| Auth | Tenant, project, principal, ACLScope, owner |
| Timeout | 5 seconds per operation unless caller context expires sooner |
| Failure behavior | Fail closed; denial and cross-boundary access return `ErrNotFound` |
| Observable result | Bounded metrics, structured audit, latency log |

`Scope` is server-resolved:

```go
type Scope struct {
    TenantID  string
    ProjectID string
    Principal string
    Role      string
}
```

Tenant/project/principal are required. Empty values fail closed before any repository call.

## 3. Operations

### Put
1. Require non-empty `Scope.TenantID`, `Scope.ProjectID`, `Scope.Principal`.
2. Reject payload tenant/project that differs from `Scope`.
3. Build a canonical `memory.MemoryRecord`, setting `TenantID`, `ProjectID`, `Provenance.CreatedBy`, and `Evidence.RecordedBy` from `Scope`; never trust caller-supplied authority fields.
4. Run `MemoryRecord.Validate()`.
5. Map only validated fields to `datastore.MemoryEntry`; set `Owner` from `Scope.Principal`.
6. Call `MemoryRepository.Put`.
7. Emit audit and metrics.

### Get
1. Require a complete `Scope`.
2. Call `MemoryRepository.Get`.
3. Return `ErrNotFound` unless the entry matches tenant, project, and ACL visibility.
4. Project-empty legacy rows are denied under D-1.
5. Emit audit and metrics; never reveal whether a denied record exists.

### Search
1. Require a complete `Scope`.
2. Build `datastore.MemoryScope` from server state only.
3. Apply `TenantID`, `ProjectID`, `User`, `ACL`, and `Kinds`.
4. Bound `k` to 1..100; default 20, maximum 100.
5. Revalidate every returned hit for tenant, project, `ACLScope`, and owner. Drop any mismatched hit before returning it and increment `memory_denied_total{reason=search_filter}`. A repository that returns an out-of-scope hit is a defect, never a partial success.
6. Emit audit and metrics for filtered hits and returned count.

### Delete
1. Require a complete `Scope`.
2. Fetch the entry with `Get`.
3. Apply the full tenant/project/ACL/owner check before any mutation.
4. Only after authorization passes, call `Delete` by the verified record ID.
5. Return `ErrNotFound` for missing, forbidden, cross-tenant, or cross-project targets.
6. Emit audit and metrics.

Delete is read-verify-delete, never delete-then-authorize. The TOCTOU window is bounded because record ID, tenant, project, and owner are immutable for an existing record and cross-tenant ID reuse is denied by the repository Put path.

### Validate
Expose canonical validation for internal callers. Validation is the only operation that does not require repository access, but it still requires a complete `Scope`.

## 4. Bypass prevention (AC-1)

The only production callers of `datastore.MemoryRepository` memory methods are the two `edpsvc` handlers, and both use `pfmemory.Orchestrator`. This is enforced by a static Go test:

- `go/pfmemory/bypass_test.go:TestNoDirectMemoryRepositoryCalls` scans `go/edpsvc` for direct `MemoryRepository.Put/Get/Search/Delete` calls outside the orchestrator wiring.
- The test fails if a new direct call site appears.
- `go/edpsvc/main_test.go:TestMemoryHandlersUseOrchestrator` proves the handlers route through the orchestrator.
- Other modules are out of scope for the runtime path and cannot claim memory access without adding a new, reviewed call site.

## 5. ACL matrix

| ACLScope | Tenant | Project | Principal rule | Read | Delete |
|---|---|---|---|---|---|
| `private` | equal | equal | entry owner equals principal | allow | allow |
| `project` | equal | equal | any authenticated project member | allow | allow |
| `tenant` | equal | equal | any authenticated tenant member in the project | allow | allow |
| `shared` | equal | equal | any authenticated tenant member in the project | allow | allow |
| empty/legacy | equal | equal | treated as `project` | allow | allow |
| any | unequal | any | none | deny | deny |
| any | equal | unequal | none | deny | deny |
| private | equal | equal | owner mismatch | deny | deny |

Admin/operator roles do not bypass tenant or project boundaries in this item. Cross-boundary denial is always non-leaky.

## 5. Tenant and RLS

- PostgreSQL access continues through the existing tenant-bound transaction adapter.
- The orchestrator verifies tenant/project after every single-record read, even when RLS is expected to enforce it.
- Search filters by tenant and project before returning and post-filters results.
- A required role-posture test asserts `current_user` is not superuser and does not have BYPASSRLS. CI must provide `PF_TEST_MEMORY_DSN`; in CI (`CI=true`) a missing DSN fails the test instead of skipping it.
- SQLite conformance tests prove the gateway closes the repository fallback gap.
- No SQL is constructed from caller-supplied tenant or project values.

## 6. Failure taxonomy

| Condition | Internal error | External behavior | Metric reason |
|---|---|---|---|
| Missing/empty Scope | `ErrInvalidScope` | denied, no repository call | `scope` |
| Canonical validation failure | wrapped `memory` validation error | bad request at boundary | `validation` |
| Cross-tenant access | `ErrNotFound` | 404-equivalent | `tenant` |
| Cross-project access | `ErrNotFound` | 404-equivalent | `project` |
| ACL/private denial | `ErrNotFound` | 404-equivalent | `acl` |
| Repository unavailable | wrapped store error | 503-equivalent, fail closed | `store` |
| Limit exceeded | `ErrLimitExceeded` | bad request | `limit` |

## 7. Concurrency and idempotency

- `Put` is idempotent by canonical record ID for the same tenant/project/owner.
- Reusing an ID across tenants/projects/owners is denied by the repository and by the gateway.
- The gateway is stateless and safe for concurrent use.
- Concurrent tests run cross-tenant and cross-project reads, writes, searches, and deletes against the same store.

## 8. Performance and capacity

- Search is bounded to 100 results; default is 20.
- Operation timeout is 5 seconds or the caller deadline, whichever is earlier.
- Canonical content is capped at 1 MiB and embeddings at 3072 dimensions by `go/memory`.
- No unbounded scans, consolidation batches, or background jobs are introduced.
- No new indexes or schema changes are required.

| Config | Default | Valid | Invalid behavior |
|---|---|---|---|
| `PF_MEMORY_MAX_SEARCH_K` | 100 | 1..100 | fail startup/use with `ErrInvalidScope`-style configuration error |
| `PF_MEMORY_OP_TIMEOUT` | 5s | positive duration, <= 30s | fail startup/use |
| `PF_TEST_MEMORY_DSN` | empty locally | PostgreSQL DSN in CI | CI fails if missing when `CI=true` |

The authenticated principal is not configuration. It is server-resolved per request.

## 9. Observability and audit

Metrics use a small injected observer so the gateway does not depend on an HTTP framework:

- `memory_ops_total{op,result}`
- `memory_denied_total{reason}`
- `memory_op_duration_seconds{op,result}`
- `memory_filtered_projectless_total`

These metrics reuse the existing `edpsvc` metrics registry through an adapter. The gateway does not create a second registry or redefine existing edpsvc families.

Audit events:

- `memory.write`
- `memory.read`
- `memory.search`
- `memory.delete`
- `memory.denied`

Audit fields are tenant, project, actor, operation, record ID when safe, outcome, reason code, and timestamp. Content, embeddings, secrets, and unrestricted tenant identifiers are never logged. Audit metadata follows the existing EDP audit retention policy; this item adds no separate personal-data store. A safe record ID is retained only when it is not a secret and is needed for traceability.

## 10. Quotas and limits

- One record per Put; no bulk writes.
- Search `k` is capped at 100.
- Delete is single-record only; no bulk delete.
- Consolidation is out of scope.
- No dry-run mode is added because the only destructive operation is single-record delete and it is ACL-checked and non-leaky.

## 11. Rollback and recovery

- No schema migration is introduced.
- Rollback restores the previous `edpsvc` binary or reverts the orchestrator wiring commit.
- Existing memory rows remain unchanged in the store.
- Data recovery uses the existing EDP backup/restore path; this item adds no new backup artifact.
- Because there is no bulk mutation, rollback does not require a compensating data script.

## 12. Deployment and rollout

1. Build `go/pfmemory`, `go/edpsvc`, and dependent modules.
2. Run pfmemory unit and concurrency tests.
3. Run edpsvc memory integration tests with SQLite and, where configured, PostgreSQL.
4. Deploy `edpsvc` with the gateway wiring.
5. Verify `/memory` allowed operations and cross-boundary denial metrics.
6. Roll back by reverting the deployment if `memory_denied_total{reason=tenant|project|acl}` exceeds 1% of memory operations over 5 minutes, or memory 5xx errors exceed 5% over 5 minutes, for two consecutive evaluation windows.

## 13. Ownership

- `go/pfmemory`: gateway policy, scope enforcement, ACL decisions, metrics/audit facade.
- `go/memory`: canonical record contract and validation.
- `go/datastore`: repository interface and storage contract.
- `go/dualvec`: concrete repository implementation.
- `go/edpsvc`: HTTP surface, authenticated principal/tenant resolution, wiring.

## 14. Test matrix

| AC | Test suite | Command | Proof |
|---|---|---|---|
| AC-1 | All operations routed through orchestrator | `go test ./...` in `go/pfmemory` and `go/edpsvc` | Handler integration test observes orchestrator calls and validation failures |
| AC-2 | Tenant/project/ACL negative suites | `go test ./...` in `go/pfmemory` | Cross-tenant and cross-project read/write/search/delete return `ErrNotFound` |
| AC-3 | Four negative leakage suites under concurrency | `go test -race ./...` in `go/pfmemory` | `TestCrossTenantReadWriteSearch`, `TestCrossProjectReadWriteSearch`, `TestACLPrivateDenial`, and `TestConcurrentBoundaryLoad` pass with `-race` |

Additional suites:

- canonical validation rejection;
- search limit bounds;
- idempotent Put;
- non-leaky Get/Delete;
- metrics/audit observer;
- PostgreSQL role posture;
- edpsvc HTTP compatibility.

## 15. Failing proof plan

`TestCrossTenantReadWriteSearch` and `TestCrossProjectReadWriteSearch` must fail against the current direct-repository path:

- Get and Delete use ID only in the SQLite fallback.
- Search can return project-empty rows for a different project.
- Put accepts the caller-supplied tenant without comparing it to the authenticated Scope.

The same tests must pass after the `edpsvc` handlers use `pfmemory.Orchestrator`.

## 16. Acceptance evidence

| AC | Design evidence | Implementation evidence | Candidate SHA |
|---|---|---|---|
| AC-1 | this design + handler call sites | `go test ./...` in `go/edpsvc` | design baseline `a536d6d1` |
| AC-2 | this design + datastore contract | `go test ./...` in `go/pfmemory` | design baseline `a536d6d1` |
| AC-3 | this design + negative matrix | `go test -race ./...` in `go/pfmemory` | design baseline `a536d6d1` |

Implementation candidate SHA and command output are stamped at Gate 2. The design baseline SHA is not runtime proof.

## 17. Stop conditions

- A request needs a new public memory API.
- A request needs consolidation or lifecycle governance.
- A change relaxes project isolation or allows caller-supplied tenant authority.
- A change requires a schema migration.
- A review finds more than one end-to-end capability in scope.

## 18. Gate timing ledger

| Gate | Target | Actual | Notes |
|---|---|---|---|
| Gate 0 design/reconciliation | 15-20m | in progress | started 2026-11-24T05:38:57Z |
| Gate 1.5 design review | 10-15m | pending | fresh Mimo review required |
| Gate 1 HIL approval | 5-10m | pending | explicit human decision |
| Implementation/tests | 30-45m | pending | not started |
| Gate 2.5/Gate 2 | 15-20m | pending | not started |
| Delivery/sync | 10m | pending | not started |
