# Product Forge — Enterprise Database & Storage Architecture
## Performance- and security-centric design, repository reconciliation, and phased implementation roadmap

**Repository reviewed:** `srinikc/productforge`  
**Target branch:** `develop`  
**Branch head observed during review:** `c246cf9c204e3596a412df0f813520abc0fc531f`  
**Review date:** 2026-10-13  
**Status:** Architecture and implementation plan; not a claim that the proposed controls are already implemented.

> **Decision:** Build the enterprise architecture into contracts, ownership, tenant boundaries, performance budgets, migration paths, and tests from the start. Operate the smallest deployment that meets the current workload and risk. Do not introduce costly distributed infrastructure before measurements justify it.

---

## 1. Executive summary

Product Forge already has meaningful building blocks: a PostgreSQL design guideline, store ownership registry, artifact scanning/cataloguing, content-addressed artifact publishing, single-writer JSON store facades, a fail-closed API authentication boundary, credential references rather than raw provider keys in configuration, and a PostgreSQL-backed WorkerGrid coordination test. The main architectural gap is not simply “files versus database.” It is the absence of one consistently enforced, provider-neutral data plane that combines:

1. **Authoritative metadata and transactions** — identity, tenant ownership, lifecycle state, relationships, permissions, artifact references, run state, quotas, and audit event metadata.
2. **Bulk/object content** — generated files, documents, binaries, images, archives, datasets, large checkpoints, and immutable build artifacts.
3. **Operational coordination** — jobs, leases, retries, outbox events, cache, and rate/concurrency limits.
4. **Security and performance controls** — tenant context, least privilege, authorization on every path, quotas, connection pools, indexes, timeouts, bounded payloads, concurrency controls, encryption, backups, and tested recovery.
5. **A migration strategy** — existing local JSON/SQLite/filesystem stores remain supported through adapters while new writes are routed through canonical interfaces; data is migrated only after inventory, parity checks, and rollback are proven.

**Recommended initial stack:** PostgreSQL as the relational system of record; PostgreSQL full-text search and `pgvector` where needed; local filesystem object adapter for development; an S3-compatible object-store adapter for deployment; PostgreSQL-backed jobs/outbox initially; optional Valkey/Redis cache only after profiling; Docker Compose for the first deployment. Each provider is replaceable through explicit contracts and conformance tests.

**Do not do:** rewrite every store at once, put binary files in PostgreSQL by default, add Kafka/Kubernetes/multiple databases prematurely, assume tenant IDs supplied by clients prove authorization, or treat a successful backup command as proof of recoverability.

---

## 2. Repository evidence and what it means

This is a **targeted architecture review** of relevant files on `develop`, not a full line-by-line audit of all repository paths. Reconfirm the branch head and inspect call sites, schema migrations, deployment manifests, tests, and runtime wiring before implementation.

| Existing component | Observed purpose/design | Recommendation |
|---|---|---|
| `product-forge/docs/guidelines/database/postgresql.md` | PostgreSQL naming, keys, FKs, indexes, timestamps, JSONB, RLS and query-plan guidance | **KEEP + strengthen.** Add tenant-safe RLS patterns, role separation, migration rules, pooling, query budgets, secure defaults, online schema-change guidance, and performance tests. Validate the examples against actual production roles and schemas. |
| `product-forge/config/store-registry.json` | Maps files to owner, concern, scope, and visibility; documents single-writer and derived-file rules | **KEEP + evolve.** Make it a versioned data ownership catalogue with sensitivity, tenant scope, authoritative/derived status, backend, retention, recovery tier, and migration status. Add automated enforcement and coverage checks. |
| `product-forge/core/artifact_store.py` | Scans project artifact directories and derives metadata such as path, type, hash, size and timestamps | **KEEP as a compatibility/read adapter; refactor behind `ArtifactService`.** Avoid scanning whole directories on every request at scale. Use DB metadata/indexes for list/search and object storage for bytes. |
| `product-forge/core/artifact_registry.py` | Local content-addressed/checksummed registry; pluggable external publishing via configured backends/commands | **KEEP the concept; harden the contract.** Separate immutable artifact publication from mutable working files. Validate paths, use full SHA-256, atomic upload/commit semantics, integrity verification, retention, authorization, and safe credential handling. |
| `product-forge/api/routers/artifacts.py` | Authenticated endpoints resolve project paths and scan/read artifacts from filesystem | **MODIFY early.** Authorize tenant/project access before lookup; query metadata through `ArtifactService`; stream bytes through a bounded download path; never trust a project or object ID as authorization. Preserve the current route as an API compatibility adapter. |
| `product-forge/core/forge_store.py` | JSON plan/state with atomic file replacement | **KEEP temporarily as `JsonForgeStore` adapter.** Move authoritative multi-user and concurrent state to PostgreSQL after writer/call-site inventory. |
| `product-forge/core/project_store.py` | Single-writer facade for `project.json`, lock-file coordination and atomic write | **KEEP as a legacy facade during migration.** A lock file is not a distributed transaction or robust multi-host lock. Replace cross-process/cross-host coordination with DB transactions/optimistic versioning when shared deployment is enabled. |
| `product-forge/core/pipeline_store.py` | Compatibility projection: `project.json` + `pipeline-state.json` → derived `pipeline.json` | **KEEP the projection approach.** Make PostgreSQL the source for shared authoritative run state; regenerate compatibility files as projections until readers are migrated. |
| `product-forge/core/agent_memory.py` | Eight memory categories persisted in JSON files | **KEEP the memory domain model; change persistence behind a `MemoryRepository`.** Store searchable metadata and relationships in PostgreSQL; keep large source/evidence payloads in object storage. Apply tenant/source ACL filters before retrieval. |
| `product-forge/core/state_checkpoint.py` | Durable local files copied and committed through a PR to `develop` | **KEEP only for development/repository-governed durable project state.** Never use Git/PRs as the production database or customer-runtime checkpoint transport. Separate product source/control documents from execution checkpoints and customer content. |
| `product-forge/core/orchestrator/storage.py` | JSON audit log and file-backed caches with atomic writes | **SPLIT responsibilities.** Durable audit events → append-only DB/event interface; ephemeral caches → cache adapter; large execution evidence → object store; local file implementation remains a dev adapter. Review legacy `LLMCache` separately from the input cache and prevent sensitive prompt/output retention by policy. |
| `product-forge/core/orchestrator/checkpoint.py` | Writes status/context/summary Markdown files | **KEEP as human-readable projections.** Persist checkpoint identity, state, version, and artifact references in DB; store large snapshots in object storage; write summaries asynchronously and with size limits. |
| `product-forge/data/control-plane/control-plane.db`, `product-forge/data/portfolio/portfolio.db` | SQLite database files are present in repository tree | **INVESTIGATE before migration.** Determine whether they are fixtures, active data, examples, or accidentally committed runtime state. Never inspect/migrate binary DBs by filename alone. Record schemas, owners, write paths, retention, and source-of-truth status. Do not blindly commit live customer data. |
| `product-forge/test-framework/tests/pipeline/test_workergrid_pg_store.py` and `workergrid/` | PostgreSQL E2E coordination test exists, gated by `WORKERGRID_PG_DSN`; tests independent coordinators sharing leases | **REUSE.** Expand it into database adapter conformance and failure/recovery tests. Verify the Go store schema and transaction semantics from the actual implementation before wiring other domains to it. |
| `product-forge/api/auth.py` | Fail-closed Bearer token auth unless explicit dev-only anonymous flag; tenant routes expect `X-Tenant-Id` | **KEEP as an important foundation, not the complete SaaS auth model.** Verify token validation/rotation, roles’ trust source, tenant membership resolution, per-resource authorization, audit, and that caller-provided tenant headers cannot select an unauthorized tenant. |
| `product-forge/core/credentials.py` | Provider keys resolved from environment and local `.env` files; config stores env references | **KEEP + harden.** Production secrets should come from a `SecretStore`/platform secret manager; prohibit secrets in DB metadata, logs, artifacts, Git, error messages, and exports. `.env` is for local development only. |
| `product-forge/core/paths.py` | Centralized root/path helpers and project-name validation | **KEEP + reuse.** Continue canonical path resolution; add symlink/path containment checks for filesystem-backed object operations and tests for traversal, encoding, and race conditions. |

### Important repository interpretation

- There are multiple file-backed stores with useful ownership boundaries. This is a migration asset: preserve their domain APIs and swap persistence implementations behind interfaces.
- `store-registry.json` is a useful starting catalogue but is not itself proof that every store is correctly classified or all writes are enforced.
- The PostgreSQL guideline and WorkerGrid test indicate existing PostgreSQL readiness, but do not prove that every Product Forge domain is PostgreSQL-backed or tenant-safe.
- The API artifact route’s filesystem lookup is acceptable for local development but is not the scalable listing/indexing model for multi-tenant production.
- A content-addressed artifact registry is valuable for reproducibility and deduplication; it must not be treated as a complete metadata database or tenant authorization boundary.

---

## 3. Target architecture

```text
Clients / UI / CLI / API / WorkerGrid
              |
     Authentication + Authorization
     Verified tenant context + quotas
              |
        Domain services
  (projects, runs, artifacts, memory,
   plans, audit, billing/usage, policy)
              |
     Canonical Data Access Layer
  ┌───────────┼──────────────┬──────────────┐
  |           |              |              |
Relational  Object         Job/Outbox     Cache
Store       Store          Store          (optional)
  |           |              |              |
PostgreSQL  Local dev /    PostgreSQL     Valkey/Redis
+ FTS       S3-compatible  initially      only if needed
+ pgvector  / cloud blob
              |
       Search / vector adapter
       PostgreSQL first; external
       engine only after measured need

Cross-cutting: migrations, tenant policy, encryption, audit,
quotas, observability, backups, restore drills, conformance tests.
```


### 3.6 Country/region data residency and sovereignty — first-class architecture capability

**Yes: this requires an explicit architecture capability, not merely a cloud-region dropdown.** Product Forge must support region-local deployment cells, policy-driven placement, and enforced controls over every data copy and processing path. However, do not encode the incorrect assumption that every country requires every category of data to stay inside its borders. Requirements differ by country, data category, sector, customer contract, public-sector procurement rules, and transfer mechanism. Legal/compliance owners must approve the policy for each launch market.

#### Terminology and policy model

- **Data residency:** where primary data, replicas, backups and derived copies are physically stored.
- **Data sovereignty/jurisdiction:** which laws and authorities can apply to data, providers, operators, keys and access; physical location alone does not settle this.
- **Cross-border transfer:** data being made available to, accessed from, or processed in another jurisdiction; depending on law, remote support, telemetry, LLM prompts, logs and subprocessors may count even if the database remains local.
- **Localization mandate:** a specific law/regulator/contract requires particular data to be stored or processed in a named territory, sometimes exclusively. Do not infer this from a general privacy law.

Create a versioned **Residency & Transfer Policy Registry** with at least:

- `policy_id`, jurisdiction/country/region, policy version/effective date, approver and review date;
- data classes and processing purposes covered; legal basis/transfer mechanism and applicable sector/customer obligations;
- allowed primary regions, allowed replica/backup regions, allowed support-access countries, allowed subprocessors and approved model providers;
- rules for database rows, object payloads, logs/traces, audit, backups, caches, search indexes/embeddings, queue messages, analytics, crash dumps and exports;
- encryption/key ownership requirements, retention/deletion rules, evidence requirements and exception expiry;
- a fail-closed decision for unknown classifications, unsupported regions or missing approvals.

This registry is operational policy input, not legal advice or a substitute for country-specific counsel. Store the policy version and placement decision with tenant provisioning and material processing events so the decision can be audited later.

#### Target topology: global routing plane + region-local data plane cells

```text
Global entry / control plane (minimal metadata only)
  - opaque tenant ID, selected region, plan/entitlements, policy version
  - no customer content; keep personal metadata out unless approved
                 | signed routing decision
                 v
        Region resolver + policy enforcement
                 |
      +----------+----------------------------+
      | Region Cell: e.g. IN / EU / UK / US   |
      | API + workers + PostgreSQL            |
      | object storage + jobs/outbox          |
      | search/vector + cache (if enabled)    |
      | audit/logs + KMS + backups            |
      +---------------------------------------+
                 |
       approved in-region model/provider calls
       or explicit transfer-gateway decision
```

A region cell is a deployable, bounded unit with its own data stores, credentials, encryption keys, backups and operational policy. Start with one cell and one region for zero-cost development. Add cells only for a contracted market or a validated need. Keep deployment artifacts and provider adapters portable; do not make cross-region replication the default.

#### Placement and enforcement rules

1. Resolve tenant region from authenticated tenant configuration and approved policy—not from an untrusted request header. Region is assigned before data creation and cannot be changed by a normal API call. Region migration is a controlled export/import workflow with explicit authorization, transfer review, checksums, audit and rollback.
2. Enforce region at provisioning and runtime: DB endpoint, object bucket/container, queue, cache, vector index, logs, backup target, KMS key and worker pool must match the tenant's allowed-region policy. Reject mismatches before accepting writes.
3. Default to **no cross-region copies or access**. Enable a transfer only when policy explicitly permits it and required legal/contractual safeguards and approvals are recorded. This applies to replicas, disaster recovery, support access, observability, analytics, embeddings, prompt/context sent to model providers and subprocessors.
4. Keep tenant data and processing in the assigned cell. For strict residency customers, use region-local control-plane metadata too, or provide a customer-operated/single-region deployment; the global plane should retain only minimal opaque routing metadata where legally approved.
5. Use region-local encryption/KMS keys and credentials. Document provider parent-company/jurisdiction, operator access, key administration, subprocessors and lawful-access handling for sovereignty-sensitive customers. Customer-managed keys and customer-operated deployment can be enterprise options.
6. Data egress is denied by default for storage, workers and model gateways. Egress rules are allowlisted by purpose, destination, data class, tenant policy and region. Apply DLP/redaction/minimization before permitted outbound processing.
7. Tag all derived data with source tenant, source region, data class and policy version. A cache hit, search result, vector result, log event or export must not bypass residency or tenant ACLs. Invalidate/delete derived copies when source access is revoked or retention expires.
8. Backups, PITR/WAL archives, object versions, snapshots, replicas, dead-letter queues, incident exports and disaster-recovery copies inherit the same residency restrictions unless a reviewed policy explicitly allows otherwise. Restore drills must verify region and key policy as well as data integrity.
9. Make support/admin access region-aware and auditable. “Stored in country” is not enough if support staff or central services can retrieve it from an unapproved jurisdiction. Use just-in-time access, approval, reason, expiry and immutable audit evidence.
10. Provide customer-visible residency metadata: assigned region, data categories stored there, subprocessors/processing locations, backup location, transfer status, retention and export/deletion options. Do not claim a compliance certification merely because a cloud region is selected.

#### Initial launch profiles: India and United States (v1)

**Product decision:** for the first commercial release, offer an India cell and a US cell. Default an Indian tenant to the India cell and a US tenant to the US cell as a conservative product commitment, even when a general privacy law does not itself require blanket in-country hosting. Treat the selected home region as a provisioning-time tenant property. This is a product baseline, not a claim that every customer or data category is legally required to stay there.

##### India profile (`IN-v1`)

- **Default placement:** application/API workers, PostgreSQL primary and replicas, object store, queues, cache/vector index, audit logs, security logs, backups/PITR, encryption keys and restore workers remain in India unless a documented, approved policy explicitly allows otherwise.
- **DPDP framework:** the Digital Personal Data Protection Act, 2023 and DPDP Rules, 2025 create personal-data processing, security, rights and transfer obligations, but should not be represented as a blanket rule that all personal data must always be stored only in India. Section 16 permits government-imposed restrictions on transfers; other laws and sector rules can impose stricter requirements. The DPDP Rules were notified on 14 November 2025 with phased commencement dates, so maintain a dated legal-obligations register and verify the provisions in force at launch and on each review. See the official [DPDP Rules notification](https://www.meity.gov.in/static/uploads/2025/11/53450e6e5dc0bfa85ebd78686cadad39.pdf) and [MeitY DPDP Rules page](https://www.meity.gov.in/documents/act-and-policies/digital-personal-data-protection-rules-2025-gDOxUjMtQWa?pageTitle=Digit).
- **CERT-In logging:** design the India operations profile to retain required ICT-system logs securely for a rolling 180 days within Indian jurisdiction, and support the applicable incident-reporting and point-of-contact process. Confirm the exact applicability and current directions for the deployed entity and service. Reference: [CERT-In Directions under section 70B](https://www.cert-in.org.in/PDF/CERT-In_Directions_70B_28.04.2022.pdf).
- **Payments and regulated finance:** if PF or a generated product is used by an RBI-regulated payment system operator or is part of a regulated payments service, assess RBI’s payment-data storage direction and the regulated customer’s obligations. Do not assume every ordinary SaaS tenant is a payment system operator. Reference: [RBI Storage of Payment System Data circular](https://rbi.org.in/Scripts/NotificationUser.aspx?Id=11244) and [RBI FAQ](https://systemhealth.rbi.org.in/Scripts/FAQDisplay.aspx_Id%3D130%281%29.html).
- **Implementation consequence:** make India-local security logs and backups explicit in the provider capability checks; do not send raw log payloads, prompts, artifacts or support bundles to a foreign-region observability/model service by default. Redacted metadata may leave India only when the tenant's policy and applicable obligations permit it.

##### United States profile (`US-v1`)

- **Default placement:** place US tenants' customer content, database, object data, backups, logs, keys and routine processing in an approved US region by default. This is the Product Forge product promise for US-hosted tenants, not a statement that US law generally mandates localization for all private-sector data.
- **No blanket localization assumption:** the United States does not have a single general rule requiring all commercial personal data to remain in the US. Obligations vary by state, sector, contract, data type and customer (for example, healthcare, financial services, children, government, defense and public-sector contracts). The policy engine must represent the actual customer/sector obligations rather than infer them from `country=US` alone.
- **Sensitive-data access restrictions:** assess the US Department of Justice Data Security Program for transactions involving covered bulk sensitive personal data or US government-related data, including restrictions related to countries of concern and covered persons. It is not a generalized US data-localization mandate; it is a distinct access/transaction risk that must be evaluated where relevant. Reference: [US DOJ Data Security Program](https://www.justice.gov/nsd/data-security) and [DOJ implementation announcement](https://www.justice.gov/archives/opa/pr/justice-department-implements-critical-national-security-program-protect-americans-sensitive).
- **Government/regulated contracts:** require a separate customer compliance profile when a contract or regime requires US-only storage, backup, support access, or authorized personnel/provider controls. Examples include applicable federal/defense requirements and IRS federal tax information rules; these are not automatically satisfied by choosing a US cloud region. References: [DFARS US storage clause](https://www.acquisition.gov/dfars/239.7602-2-required-storage-data-within-united-states-or-outlying-areas) and [IRS cloud computing requirements](https://www.irs.gov/privacy-disclosure/cloud-computing-environment).
- **Implementation consequence:** default US tenant data-plane resources to US regions, but make support-personnel location, provider/subprocessor jurisdiction, key administration, model processing, government-contract conditions and data-export controls independently configurable and auditable.

##### Shared India/US controls and profile differences

| Control | India profile | US profile |
|---|---|---|
| Tenant content, DB, object storage | India by default | US by default |
| Primary and recovery backups | India by default; verify applicable legal/contract requirements | US by default; stricter customer contracts can limit regions/access further |
| Security logs | India-local retention/operations, including applicable CERT-In requirements | US-local by product default; retention and access rules per customer/sector/contract |
| Model/API providers | Deny cross-border prompt/content egress by default; allow only approved processing destinations | Deny non-US processing by default for US-region tenants unless policy allows it |
| Support and incident exports | India-local access by default; approved JIT exceptions only | US-local access by default for US-only contracts; approved JIT exceptions only |
| Cross-region DR | Disabled by default; policy approval plus documented recovery trade-off | Disabled by default; policy approval plus documented recovery trade-off |
| Legal profile | DPDP/IT/CERT-In plus applicable sector/customer rules | Applicable federal/state/sector/customer rules, DOJ Data Security Program where relevant |

These profiles are intentionally conservative defaults. A legal/compliance review must map the tenant's actual data categories, controller/processor roles, sector, contracts, transfer mechanisms, retention, breach duties and current effective dates before a compliance claim or regulated deployment.

##### Required technical implementation for v1

1. Define `JurisdictionProfile` and `ResidencyPolicy` as versioned configuration with effective dates, source links, reviewer/approver, data classes, allowed regions, permitted support locations, provider/subprocessor allowlists, retention and transfer rules.
2. Define a `RegionCell` inventory with explicit capability attestations for DB, object storage, backups/PITR, logs, keys/KMS, queues, cache/vector, worker pools and model gateways. Provisioning fails closed if any required service lacks an approved region.
3. Add `tenant.home_region`, `tenant.jurisdiction_profile_id`, `tenant.residency_policy_version`, and immutable provisioning/audit events. Never select region solely from `X-Tenant-Id`, `X-Region`, URL parameters or user-editable project configuration.
4. Require each provider adapter to expose its effective region, backup/replication behavior, support/access model and subprocessor metadata. If a provider cannot attest to a required property, it is not eligible for that tenant profile.
5. Make the global control plane either (a) store only opaque tenant ID + home-cell routing + minimal entitlement metadata, with an approved transfer assessment, or (b) deploy it inside each region for strict/local-only customers. Do not put tenant content, raw prompts, object names containing personal data, or detailed audit payloads in a global plane by default.
6. Route all operations through the tenant's home cell. Cross-cell reads, writes, replication, support access, exports and model calls require an explicit policy decision, an auditable purpose, an approved destination and (where required) customer/legal approval. No silent failover to another country.
7. Build separate `IN-v1` and `US-v1` policy tests, including wrong-region DB/object/backup/KMS configuration, foreign-region telemetry, model prompt egress, support access, backup restore and attempted tenant region changes. Run these tests in CI and deployment preflight.
8. Publish a tenant-facing residency statement that identifies primary region, backup region, key-management model, relevant subprocessors/model providers, permitted support access and any approved transfers. Update it when configuration changes.

##### Rollout sequence

- **Phase 0 — policy and inventory:** identify all data flows and stores; classify content, metadata, logs, prompts, memory, backups and generated-product runtime data; define India/US launch profiles and legal-review owners.
- **Phase 1 — fail-closed contracts:** add region/profile fields and policy decisions to provisioning; add adapter capability checks and test doubles; block unsupported/cross-region placements before tenant activation.
- **Phase 2 — India cell:** deploy and validate all required components in India, including 180-day India-local logging where applicable; run restore and egress tests before accepting real customer data.
- **Phase 3 — US cell:** deploy an independent US data plane and validate US-region backups/logging/keys/support/model restrictions; add customer-specific overlays for regulated or government contracts.
- **Phase 4 — evidence and operations:** generate a per-tenant residency report, data-flow map, provider/subprocessor inventory, region-specific restore evidence and exception register. Revalidate policies on a schedule and after law/provider/contract changes.
- **Phase 5 — additional jurisdictions:** add a new jurisdiction by supplying an approved policy profile, provider capability mapping, region cell and tests—not by changing core domain logic.

#### Product Forge vs generated products

Product Forge needs two distinct policy planes:

- **PF platform data:** product specifications, source code, run state, generated artifacts, agent memory, prompts, credentials references, telemetry and audit. Apply the tenant's policy to each class, including model calls and support diagnostics.
- **Generated product runtime data:** each generated product must have its own data-residency manifest and deployable regional data plane. PF should generate the configuration/IaC and evidence, but must not route runtime customer data through PF by default. If PF-hosted control/telemetry is enabled, it must be explicitly classified and region-aware.

Add a machine-readable residency section to the Product Manifest/EAP, for example: `data_classes`, `home_region`, `allowed_regions`, `replication_policy`, `backup_regions`, `kms_policy`, `allowed_subprocessors`, `model_processing_regions`, `egress_policy`, `retention_policy`, `transfer_approval_ref` and `evidence_requirements`. Validate it in build, deployment and runtime gates. This is a policy contract, not a claim that the manifest alone makes a deployment compliant.

### 3.1 Relational system of record — PostgreSQL

Use PostgreSQL for records that need transactions, constraints, queries, relationships, multi-user concurrency, and reliable state transitions:

- Tenant, membership, roles/permissions, plans, entitlements, quotas and usage counters.
- Product Forge projects, products, configurations, run/pipeline/stage state, ownership and lifecycle.
- Artifact metadata, object references, checksums, versions, retention/expiry, classifications and access policy.
- Memory metadata, provenance, source references, ACL scope, validation state and embeddings when using `pgvector`.
- Job records, leases/attempts where appropriate, idempotency keys, outbox events and deduplication records.
- Audit event metadata, policy decisions, schema versions, provider configurations (never raw secrets).

Use foreign keys, unique constraints, check constraints and transaction boundaries for correctness. Use UUIDs for externally exposed identifiers where appropriate; UUIDs are not authorization. Avoid storing arbitrary unbounded documents and binary blobs in hot relational rows. JSONB is for evolving, bounded metadata—not a replacement for normalized ownership, relationships, or queryable state.

### 3.2 Object/blob storage — actual bytes

Use an `ObjectStore` interface for generated code archives, media, documents, uploaded source bundles, large reports, datasets, immutable artifacts, long-running execution evidence and large checkpoint snapshots.

- **Development:** filesystem adapter outside the source-controlled tree, with path containment and explicit data-root configuration.
- **Initial hosted deployment:** an S3-compatible backend or cloud object storage with private buckets, least-privilege credentials, lifecycle policies, versioning where required, and optional object lock/immutability for evidence needing it.
- **Enterprise:** provider-managed object storage, customer-owned storage, tenant-specific buckets/accounts/keys when isolation requirements justify it, and documented residency/retention controls.

The database stores an object record and opaque provider reference; it does not store provider-specific bucket URLs as the only identity. Generate signed download/upload URLs only after authorization, constrain them to a specific object/method, use short expirations, and avoid exposing storage credentials. Keep object content private by default. Do not use predictable object paths as access control.

### 3.3 Search and vector retrieval

Start with PostgreSQL full-text search and `pgvector` only for use cases that need them. Keep metadata and ACL filtering in the canonical query path. Consider a dedicated search/vector engine only after benchmarks show a need for independent scaling, specialized ranking, or latency targets that PostgreSQL cannot meet. Never allow vector similarity to bypass tenant, project, source, or document permissions.

### 3.4 Jobs, events and cache

- Begin with PostgreSQL job rows plus transactional outbox where practical; use `FOR UPDATE SKIP LOCKED`/leases with bounded transactions and idempotent handlers where appropriate.
- Keep WorkerGrid’s PostgreSQL coordination store for its defined coordination responsibilities; do not create a second competing job truth without explicit ownership.
- Introduce a broker only when throughput, fan-out, backpressure, or independent worker scaling proves the need. Redis/Valkey is optional cache/ephemeral coordination, not the durable system of record.
- Every tenant-scoped job must carry a verified tenant scope and be re-authorized by the consumer. Messages are not proof of authorization.
- Cache keys must include tenant plus all authorization/result-varying dimensions. Authorize before serving protected cache hits. Apply per-tenant and global queue/concurrency/rate limits.

### 3.5 Product Forge vs products generated by Product Forge

Product Forge is the control plane for generating and governing products. A generated product owns its own runtime database, object store, tenant model, keys, retention and backup policy. Product Forge may retain product manifests, deployment metadata, run/build evidence and customer-authorized operational metadata, but must not become the default storage location for all generated-product runtime/customer data. Provide generated products with their own storage/provider configuration and migrations.

---

## 4. Performance-first design rules

Performance must be testable from the first database migration, not deferred until scale.

### 4.1 Data and query design

1. Define primary access patterns before schema/index choices: tenant + project + run; artifact list by project/stage/type/time; job claim by status/priority/availability; memory retrieval by tenant/project/source/permission.
2. Put `tenant_id` and other scope columns into the appropriate composite indexes and uniqueness constraints. Index actual query patterns—not every column. Use partial indexes for hot subsets where justified.
3. Require a query review for hot paths and use `EXPLAIN (ANALYZE, BUFFERS)` on representative data volumes. Avoid N+1 queries, repeated directory scans, unbounded JSON parsing, and loading entire artifacts into API memory.
4. Use cursor/keyset pagination for large or changing result sets; enforce maximum page size, result bytes, and query duration. Avoid deep `OFFSET` pagination on high-volume tables.
5. Use bulk insert/upsert for batches; keep transactions short; never hold DB transactions open during LLM calls, object transfers, or long-running agent execution.
6. Use connection pooling from the beginning. Bound pool size per process and calculate the total across API instances, workers, migrations, and admin jobs. Configure acquisition/query/statement/lock timeouts. Do not scale by opening an unbounded connection per request.
7. Keep large payloads out of hot rows. Store object bytes externally; persist hashes, size, MIME/type, encoding, owner, scope, object version and retention metadata in PostgreSQL.
8. Make all write paths idempotent where retries are possible. Use idempotency keys and unique constraints for run creation, artifact registration, job scheduling and event delivery.
9. Define cache policy explicitly. Caching is a performance feature, not a correctness mechanism. Cache invalidation, versioning, tenant scope and sensitive-content policy must be testable.
10. Use asynchronous projections for status Markdown, indexes and derived reports. Mark projections as derived and rebuildable; never let a stale projection become the only source of truth.

### 4.2 Artifact throughput

- Do not scan all files to answer every list request. Register metadata on upload/commit and query an indexed artifact table.
- Stream downloads/uploads; support multipart/resumable upload when large artifacts require it.
- Hash while streaming; verify checksum and byte count; avoid repeated full reads solely to compute metadata.
- Use immutable artifact versions and content-addressed keys when useful. Keep tenant authorization at the metadata/object access layer even when content is deduplicated.
- Use asynchronous object lifecycle and deletion workflows; deletion must reconcile DB records, object versions, replicas and backups according to retention rules.
- Set maximum upload size, decompressed archive size, file count, nesting depth, and content-processing time. Treat archives and uploaded paths as untrusted input.

### 4.3 Capacity and service objectives

Establish measurable baselines before claiming enterprise scale. Initial suggested targets are placeholders to be confirmed with workload tests:

- Metadata API: p95 under 250 ms for common indexed reads at the agreed test load, excluding external LLM calls and object transfer.
- Artifact metadata list: p95 under 300 ms at agreed row count, with pagination and no full filesystem scan.
- API and worker DB pools: no sustained pool-acquisition timeouts; bounded connection counts.
- Queue/job age, retries, dead-letter count, object latency/error rate, DB saturation and tenant throttling are observable.
- Every service has explicit request/body/time/concurrency limits and returns bounded errors.

Do not accept these targets without defining hardware, data volume, concurrency, region, payload sizes, cache state, and percentile methodology. Benchmark on representative data and retain results in CI/release evidence.

---

## 5. Security-first design rules

### 5.1 Tenant context and authorization

- Resolve identity from a validated credential/session and resolve tenant membership/entitlements server-side. `X-Tenant-Id` is a selector, not proof of membership.
- Enforce tenant/project/resource authorization in a shared service boundary on every route, worker task, artifact read, memory retrieval, cache hit and export.
- Use explicit roles/scopes and least privilege. Separate tenant request roles from migrations, operators, backup jobs and cross-tenant support tooling.
- For shared-table PostgreSQL, apply RLS to tenant-owned tables as defense in depth, with both `USING` and `WITH CHECK` policies and default-deny behavior. The runtime role must not be superuser, table owner where it can bypass policies, or `BYPASSRLS`. Evaluate `FORCE ROW LEVEL SECURITY` where appropriate.
- Set tenant context transaction-locally for pooled connections and prove it is cleared between requests. Never rely on a session-level tenant setting that can leak across a reused connection.
- Keep tenant scope explicit in SQL predicates and indexes even with RLS; test both correctness and policy overhead. Index the columns used by RLS predicates.
- Provide a separately authorized, auditable cross-tenant administrative path; ordinary tenant operations must never silently become unscoped.

### 5.2 Storage and file access

- Authorize the exact object and operation before reading it or issuing a signed URL. Use private buckets and least-privilege object credentials.
- Prevent path traversal, symlink escape, path normalization bypasses, arbitrary file reads and overwrite races in the local adapter. Resolve paths against a trusted root and verify containment after resolution.
- Validate content type and size; never trust file extensions. Scan uploaded content where risk warrants it. Process archives in a sandbox with CPU/memory/time/file-count limits.
- Encrypt network traffic with TLS. Use provider-managed encryption at rest by default; support customer-managed keys or tenant-specific keys for enterprise tiers where needed. Document key rotation, access, revocation and recovery.
- Keep secrets out of JSON config, database rows, source control, artifacts, logs and API responses. Local `.env` files are development-only. Use a secret manager in hosted production and customer-provided secret integrations for on-prem/air-gapped deployments.
- Define data classification, retention, deletion, export, legal hold and backup retention. Tenant deletion must include object versions and documented backup expiry—not only deleting current DB rows.

### 5.3 API, identity, audit and supply chain

- Keep `API_ALLOW_ANON=1` and other bypass flags disabled in production; fail startup if a production profile enables development authentication or uses missing/default credentials.
- Verify token audience, issuer, expiry, revocation/rotation model and scopes if JWT/OIDC is adopted; do not trust arbitrary role headers from clients.
- Add rate limits and quotas per tenant, user, endpoint, API key and globally; apply to expensive model calls, file upload/download, search and job submission.
- Audit authentication failures, authorization denials, tenant switches, exports, object reads/writes/deletes, policy changes, key actions, migrations, backup/restore and admin access. Logs must be tamper-evident enough for the chosen tier and avoid secrets, raw prompts, tokens and sensitive artifact contents.
- Use parameterized SQL; validate identifiers before constructing paths/queries; constrain outbound network access and provider callbacks; protect against SSRF in URL-fetching and integration features.
- Pin dependencies, scan packages/images, generate an SBOM, sign release artifacts where supported, protect CI secrets, and apply schema migrations through reviewed versioned changes.

### 5.4 RLS and PostgreSQL version maintenance

RLS is not a substitute for application authorization. Test it as a separate security boundary. Track supported PostgreSQL versions and apply security updates promptly; include security advisories and fixed minor versions in release maintenance. Verify migration and role-change behavior against the exact PostgreSQL version in use.

---


### 5.5 Data residency, sovereignty and cross-border processing

- Treat residency as a tenant-level, data-class-aware policy enforced by architecture. Do not assume that a provider's “region” setting governs logs, backups, support access, telemetry, queues, model calls, crash dumps or subprocessors.
- Create a **Region/Residency Policy Enforcement Point** shared by provisioning, storage adapters, database routing, object access, job dispatch, model gateway, observability export, backup, support and deletion workflows. No individual module should invent its own region-selection rules.
- A tenant's region and allowed transfer policy must be immutable to ordinary users; changes require an audited migration plan and explicit approval. Missing or ambiguous policy means deny cross-region processing and avoid accepting sensitive data until resolved.
- Keep a data-flow register that maps each data class to collection, primary store, replicas, backup/archive, processing services, model providers, subprocessors, support roles, retention and deletion path. Generate a deploy-time report and test it against the policy registry.
- Separate **where stored** from **where accessed** and **where processed**. For example, an EU database with a non-EU log exporter or an external model API may still create a transfer/compliance issue. Apply the same review to embeddings and prompts because they can contain or reveal source data.
- Require providers to document region availability and service-specific data locations, including backup/PITR, support, control-plane metadata, subprocessors and key management. Do not assume every provider service is available in every region or that an account-level region pinning setting covers all services.
- For country/sector launch, legal/compliance must produce an approved jurisdiction profile with applicable laws, regulator rules, contract terms, permitted transfers, data-subject rights, breach reporting, retention and evidence. Product Forge supplies technical enforcement and evidence; legal owners decide whether a profile is sufficient.
- Run automated policy tests: allowed local write succeeds; forbidden region endpoint/bucket/provider is rejected; backup/restore remains in allowed locations; cross-region logs/metrics and support access are blocked; tenant region cannot be changed through headers; region migration leaves no unintended residual copies.

**Important legal distinction:** not every privacy regime imposes blanket in-country storage. For example, EU GDPR generally regulates international transfers through adequacy and other safeguards rather than requiring all EU personal data to remain in the EU; India's DPDP framework allows transfers subject to government restrictions while sector-specific rules can impose stronger localization; China's PIPL includes domestic-storage requirements for specified operators/processing categories and controls on exports; Saudi Arabia's PDPL transfer regulation sets conditions and safeguards for transfers outside the Kingdom. These examples are not exhaustive and rules change. Confirm the current law and sector obligations for every target market with qualified counsel.

## 6. Canonical data contracts and logical schema

Create these logical interfaces first; implementations can initially be local or PostgreSQL-backed.

### 6.1 Interfaces

- `RelationalStore`: transactions, migrations, scoped queries, optimistic concurrency, health checks.
- `ObjectStore`: put/get/head/delete/list-prefix, streaming, checksum, version, metadata, signed URL, lifecycle and optional conditional writes.
- `ArtifactService`: register immutable artifact, query metadata, fetch authorized content, validate hash, promote/revoke/delete by policy.
- `MemoryRepository`: tenant/project/source-scoped CRUD and retrieval metadata; payload reference can point to object storage.
- `JobStore`: submit, claim, renew lease, heartbeat, retry, cancel, complete, dead-letter; idempotent transitions.
- `OutboxStore`: transactional event record, delivery status, retry and deduplication.
- `CacheStore` (optional): get/set/delete, TTL, namespace and tenant scope.
- `SecretStore`: resolve secret by reference; never return secrets in ordinary configuration APIs.
- `AuditStore`: append structured event, tenant/scope, actor, action, resource, outcome, correlation ID and timestamp.
- `BackupProvider`: backup policy, restore point, verification and restore-drill status.
- `SearchProvider` / `VectorProvider`: search and embedding operations with mandatory scope filters.

Every interface must have contract tests shared by local and cloud implementations. Declare optional capabilities explicitly; do not pretend all providers support object versioning, retention lock, conditional writes, customer-managed keys, transactions or signed URLs identically.

### 6.2 Initial logical tables

These are conceptual starting entities, not a final migration script. Inspect existing schemas and IDs before implementation.

- `tenants`, `tenant_memberships`, `roles`/`permissions` or equivalent identity-provider mappings.
- `projects` / `products` with `tenant_id`, owner, lifecycle, config version and timestamps.
- `runs`, `run_stages`, `run_attempts` with tenant/project scope, state, idempotency key, lease/retry fields, version and timestamps.
- `artifacts` with `artifact_id`, tenant/project/run/stage references, type, visibility/classification, object reference, checksum, byte size, MIME type, version, retention, created-by and timestamps.
- `stored_objects` with provider, opaque key/reference, object version, hash, size, content type, encryption/key reference, status, retention and tenant scope. Never store secret credentials here.
- `memory_entries` with tenant/project/source scope, type, bounded metadata, provenance, ACL scope, object reference if payload is large, and optional embedding.
- `jobs`, `job_attempts`, `leases`, `outbox_events`, `idempotency_records`.
- `audit_events`, `usage_events`, `tenant_quotas` and `schema_migrations`/migration bookkeeping as appropriate.

**Key rules:**

- Tenant-owned tables have a clear enforceable ownership model. Add tenant scope to unique constraints where identity is tenant-local (e.g. `(tenant_id, external_key)`).
- Where practical, use composite foreign keys to prevent cross-tenant references, or enforce equivalent constraints in the service layer plus tests.
- Avoid storing secrets or full file content in metadata tables.
- Keep event payloads bounded and versioned. Store large event evidence as object references.
- Use UTC `TIMESTAMPTZ`; use soft deletion only where a documented retention/legal requirement needs it, and define how it affects indexes and access.
- Define deletion/retention and tenant export semantics before storing production customer data.

---

## 7. Provider/deployment choices and cost posture

Architecture is provider-neutral; cost and operational responsibility vary by provider and plan. Recheck live pricing and terms before deployment. Free tiers are best-effort and do not imply an SLA, durable backup, or guaranteed capacity.

| Stage | DB / storage deployment | Cost posture | Suitable use |
|---|---|---|---|
| **Stage 0 — local development** | Docker Compose PostgreSQL; local filesystem object adapter outside Git; local migrations and backups | Target ₹0 incremental cloud spend | Development, tests, prototypes. Not production multi-tenant hosting. |
| **Stage 1 — demo / low-volume pilot** | Eligible free VM or free DB where available; PostgreSQL on a controlled VM or a limited free hosted DB; low-cost S3-compatible/cloud object storage; quotas and alerts | Aim for ₹0–₹500/month only if provider limits fit | Non-critical pilots with explicit backup/export and downtime expectations. Do not promise production SLA. |
| **Stage 2 — first paying customers** | Managed PostgreSQL or a properly operated VM DB; private object storage; independent backups; monitoring; TLS; restore drills | Usage-based budget tied to customer revenue and risk | Production workloads with clear RPO/RTO and support obligations. Prefer managed DB if it reduces operational risk enough to justify cost. |
| **Stage 3 — enterprise** | HA managed PostgreSQL or tested self-managed HA; PITR; read replicas when measured; tenant isolation tiers; object lifecycle/versioning; customer-managed keys where required; separate worker pools | Paid, workload and contract dependent | Enterprise SLA, stronger isolation, compliance and recovery. Add dedicated DB/storage for specific tenants when requirements justify it. |

### Deployment operating models

- **Self-hosted:** lowest direct cost and maximum control, but the team owns patching, monitoring, disk growth, backup verification, restore, network controls, HA and on-call response.
- **Managed cloud services:** higher direct bill, lower operational burden for backups/patching/HA, but still requires secure configuration, access control, restore testing, quotas and cost monitoring.
- **Customer-operated/on-prem/air-gapped:** support configurable endpoints, certificates, customer keys and storage backends. Do not hard-code a public cloud dependency into domain services.
- **Hybrid:** app/worker on a VM with managed DB and object storage can be a pragmatic first production step.

A ₹0–₹500 monthly target is appropriate for development and constrained experiments, not a promise of enterprise availability. Architecture should support scale now; infrastructure should scale only when measured load, revenue, contractual requirements or risk demand it.

---

## 8. Phased execution order

Phases are gates, not calendar promises. Do not start broad data migration before Phase 0/1 inventory, tests and rollback design are complete.

### Phase 0 — Baseline, threat model, data inventory
**Priority: P0 | Blocking prerequisite**

1. Pin the exact `develop` commit used for implementation and create a storage/data architecture ADR.
2. Inventory every file-backed, SQLite, PostgreSQL, cache, artifact and checkpoint store; identify all readers/writers, ownership, scope, sensitivity, data volume, write frequency, concurrency and retention.
3. Inspect the two SQLite files and identify whether they are active runtime data, test fixtures, examples or accidentally committed data. Do not migrate or delete based on filename alone.
4. Extend `store-registry.json` fields: authoritative vs derived, data classification, tenant scope, backend, owner, write path, retention, backup tier, migration status, and rebuild procedure.
5. Build a threat model covering cross-tenant IDOR, path traversal, token/role spoofing, object URL leakage, prompt/source leakage, noisy neighbors, compromised workers, backup exposure, tenant deletion, cross-region access, data egress, provider jurisdiction and residency-policy bypass.
6. Inventory data flows beyond primary databases: object versions, WAL/PITR, replicas, caches, queues, vector/embedding indexes, telemetry, logs, traces, crash dumps, model/API calls, support access, exports and subprocessors. Record physical region and access/processing jurisdiction where knowable.
7. Define initial launch-market legal profiles with counsel/compliance; classify requirements as mandatory law/regulator, contractual/customer, or recommended practice. Do not assume blanket localization.
8. Capture baseline performance: artifact list/read, project load/save, run state transitions, memory retrieval, job claim/lease, DB connection count, CPU/RAM/disk, and concurrent users/runs.

**Exit gate:** every store and data flow has an owner, source-of-truth decision, data classification, region/transfer disposition, migration disposition and test plan. No unexplained active writer or unclassified cross-region flow remains for a critical data path.

### Phase 1 — Contracts, migrations, security defaults
**Priority: P0**

1. Define provider-neutral interfaces (`RelationalStore`, `ObjectStore`, `ArtifactService`, `JobStore`, `AuditStore`, `MemoryRepository`, `SecretStore`, optional `CacheStore`).
2. Add versioned DB migrations and a schema ownership policy; never create production schema implicitly during API startup.
3. Establish separate DB roles: migration/owner role, restricted application runtime role, read-only/analytics role where needed, and backup/maintenance role. Runtime role must not be superuser or `BYPASSRLS`.
4. Add tenant context middleware/service context. Derive authorized tenant membership from identity; do not trust `X-Tenant-Id` alone.
5. Implement tenant-aware query helper/repository rules and RLS for tenant-owned tables. Use transaction-local context with pooled connections; add negative tests proving context cannot bleed across reused connections.
6. Define timeouts, pool sizing, request limits, upload limits, statement/lock timeouts, per-tenant/global quotas, structured errors and safe logging.
7. Add secret provider interface; production profile rejects development auth, anonymous bypass and insecure defaults.
8. Define `ResidencyPolicy` / `RegionResolver` contracts and a versioned policy registry. Resolve region from authenticated tenant provisioning, validate provider capabilities/regions, and fail closed for unsupported or unapproved placement.
9. Add policy-aware egress controls and region tags to object, DB, job, cache, vector, observability, backup and model-provider contracts. Add a data-flow inventory/report that can be checked at deploy time.
10. Add a generated-product residency manifest field to Product Manifest/EAP and make it a build/deploy gate; do not route generated product runtime data through PF by default.

**Exit gate:** contract tests pass for local adapters; tenant-isolation and residency-policy tests fail closed; migration/rollback path is exercised on disposable data; no new persistence code bypasses the interface or region policy without a reviewed exception.

### Phase 2 — Object store and artifact path modernization
**Priority: P0**

1. Implement local filesystem `ObjectStore` first, with root containment, symlink defenses, atomic writes, checksum, size limits and deterministic test fixtures.
2. Implement one S3-compatible adapter and conformance tests; keep provider-specific configuration in the adapter, not domain services.
3. Introduce `stored_objects` and `artifacts` metadata with tenant/project/run scope, content hash, object version, size, type, classification and retention.
4. Refactor `artifact_store.py` into a compatibility adapter over `ArtifactService`; keep scan/import tooling for one-time discovery/reconciliation, not request-time listing.
5. Refactor `artifact_registry.py` to publish immutable content, verify checksums and return stable object references. Make publication retry-safe and idempotent.
6. Refactor `/artifacts` endpoints to query metadata and stream authorized content. Validate project access before metadata or object lookup; never return unrestricted local paths.
7. Add lifecycle rules, multipart/resumable transfers if needed, and explicit delete/revoke behavior across DB/object store/versions/backups.
8. Make object-store region, backup/replication locations, key region, retention and provider identity explicit capabilities/metadata. Reject cross-region bucket configuration for a tenant whose policy prohibits it.
9. Add conformance tests for wrong-region writes, signed URLs, replication, object versions, deletion, lifecycle expiry and restore location.

**Exit gate:** list performance no longer scales linearly with directory tree size; cross-tenant artifact tests pass; object corruption, missing object, retry, timeout, partial upload and deletion reconciliation are tested.

### Phase 3 — PostgreSQL control plane and critical state
**Priority: P0/P1**

1. Implement tenant, project/product, run/stage, artifact metadata, quota/usage and audit schemas in migrations after comparing current models and SQLite schemas.
2. Add indexes based on measured query plans and common tenant-scoped access paths. Ensure all tenant filters have correct supporting indexes.
3. Add connection pooling, bounded pool budgets across API/worker processes, timeouts, health checks and graceful shutdown.
4. Introduce transactions and optimistic version checks for state updates. Keep long agent/model execution outside DB transactions.
5. Move only shared, concurrent, authoritative state first. Retain JSON as compatibility projections for legacy readers and regenerate them from DB truth.
6. Add migration/import tooling with dry-run, checksums/counts, idempotency, conflict report, dual-read verification where safe, rollback snapshot and cutover flag.
7. Reconcile `forge_store.py`, `project_store.py`, `pipeline_store.py`, `control-plane.db` and `portfolio.db` only after ownership and schema investigation. Do not maintain two writers to the same truth.
8. Implement region-aware tenant provisioning and routing. Validate the DB cluster/endpoint, database backups/PITR, and any read replica against the assigned residency policy before tenant activation.
9. Ensure tenant, project and artifact records carry region/policy metadata where required, while avoiding unnecessary personal data in global control-plane tables.

**Exit gate:** no dual-write ambiguity; migrations are repeatable; counts/hashes and critical invariants match; rollback is demonstrated; load tests meet agreed latency/concurrency targets.

### Phase 4 — Run state, WorkerGrid, durable jobs and audit
**Priority: P1**

1. Decide the boundary between Product Forge pipeline run state and WorkerGrid coordination/leases. Document one owner for each fact.
2. Use durable job/lease records, idempotency keys, bounded retries, heartbeat/lease expiry and dead-letter/terminal failure state.
3. Use a transactional outbox for DB changes that must trigger asynchronous work; consumers are idempotent and reauthorize tenant scope.
4. Move authoritative agent execution audit events to `AuditStore`; keep summaries and status Markdown as derived views. Set retention and sensitive-data redaction policies.
5. Store large checkpoint snapshots/evidence in object storage; DB stores state, versions and references. Retain compact Markdown summaries as rebuildable convenience projections.
6. Split `core/orchestrator/storage.py` into audit, cache and object/evidence responsibilities. Review the legacy LLM output cache independently and enforce the configured sensitive-data retention policy.

**Exit gate:** kill/restart workers during each transition; prove no duplicate billing/state mutation, no lost accepted job, safe lease recovery, and complete audit correlation across API/run/stage/worker.

### Phase 5 — Memory and retrieval persistence
**Priority: P1**

1. Add `MemoryRepository` behind the existing eight memory types; preserve domain semantics.
2. Store structured memory/provenance/ACL metadata in PostgreSQL; store large raw evidence externally with checksum and stable object reference.
3. Add PostgreSQL full-text search first; add `pgvector` only for embedding-based cases with explicit tenant/project/source ACL filters.
4. Define retention, confidence/validation, deletion, provenance, source refresh and derived embedding invalidation.
5. Add retrieval tests for cross-tenant leakage, stale embeddings, source revocation, poisoned content and top-k/latency limits.

**Exit gate:** memory retrieval cannot return unauthorized source content; indexing/rebuild is repeatable; query latency and payload limits are measured.

### Phase 6 — Performance, resilience, backup and recovery
**Priority: P1**

1. Create representative load fixtures and benchmarks for p50/p95/p99 latency, throughput, error rate, pool wait, lock wait, DB CPU/I/O, object throughput, queue age and tenant fairness.
2. Use `EXPLAIN (ANALYZE, BUFFERS)` against representative data; tune indexes/query shapes only from evidence. Track slow-query fingerprints without logging sensitive parameters.
3. Test graceful degradation: DB unavailable, object store unavailable, full disk, provider throttling, cache unavailable, queue backlog, slow query and expired credentials.
4. Define RPO/RTO by deployment tier. Back up PostgreSQL and objects with consistent identity/version references; encrypt backups; isolate backup credentials and locations.
5. Implement restore drills for full service and single-tenant export/restore. Verify DB metadata ↔ object checksums/references after restore. A successful backup is not proof until restoration succeeds.
6. For managed PostgreSQL, validate PITR/retention/region behavior against provider guarantees. For self-managed PostgreSQL, operate base backups + WAL archiving/PITR with documented monitoring and restore runbooks.
7. Add schema-compatible rolling deployments, migration locks, backward-compatible expand/contract migrations and rollback gates.
8. Add region-specific restore drills and verify backups, WAL/PITR, object replicas, encryption keys and restore workers remain within permitted jurisdictions.
9. Test incident response, export and deletion with region-local evidence; ensure logs/metrics/traces and alert payloads do not leak restricted content to a central region.

**Exit gate:** restore drills meet target RPO/RTO; recovery integrity checks pass; performance regression thresholds are in CI/release gates; failure modes have runbooks.

### Phase 7 — Scale-out and enterprise isolation tiers
**Priority: P2, only when measured or contracted**

1. Scale API and workers horizontally; use bounded worker pools, per-tenant concurrency, backpressure and queue-age limits.
2. Add read replicas only for measured read pressure and with explicit stale-read semantics. Keep writes on the primary and do not use replicas for authorization decisions requiring immediate consistency.
3. Partition large event/usage/audit tables only when data volume and query patterns justify it. Plan retention and index maintenance before partitioning.
4. Add dedicated DB/schema/bucket/key/worker pool for tenants requiring stronger isolation, noisy-neighbor protection, residency or contractual commitments. For strict residency, deploy a complete region cell (including logs, backups, keys, queues, support workflow and approved model processing), not just a regional database.
5. Add additional country/region cells only when legal/contractual requirements or validated commercial demand justify the operational cost; keep each cell independently deployable and observable.
6. Add dedicated search/vector service or broker only when load tests demonstrate the current PostgreSQL-backed approach misses targets.
7. Add multi-region active/passive or active/active only with explicit consistency, failover, data residency and recovery design; do not equate multi-region with automatic correctness. Cross-region DR is opt-in per policy, never a default.
8. Provide a region migration workflow: preflight legal/policy check, freeze or consistent snapshot, export encryption, controlled transfer, import and checksum verification, cutover, rollback window, old-copy expiry proof and audit evidence.

**Exit gate:** architecture change is justified by measured saturation or contractual requirements; migration/rollback and tenant-isolation evidence is approved.

---

## 9. Migration and compatibility rules

- **No big-bang rewrite.** Preserve current domain functions while changing persistence behind facades/adapters.
- **One source of truth per concern.** During transition, define a single writer. If dual-write is temporarily unavoidable, add an outbox/reconciliation process and a sunset date; never silently accept divergent truths.
- **Read old, write new only after parity.** Start with inventory/import; compare IDs, counts, hashes and relationships; run shadow reads; switch writes; keep rollback path; then remove old writes after a release window.
- **Derived files stay derived.** `pipeline.json`, status Markdown, indexes and reports can remain as compatibility projections. They must be rebuildable from canonical state and marked with source version/time.
- **Keep Git for code and reviewed configuration, not live customer state.** Durable Product Forge source/config can remain under version control; high-churn execution state and customer artifacts belong in DB/object storage.
- **Provider portability means tested contracts, not a lowest-common-denominator abstraction.** Expose capabilities such as versioning, retention lock, conditional writes, KMS, signed URLs and multipart transfer explicitly.
- **Schema migrations are versioned and reviewed.** Avoid auto-migration on application startup in production; separate schema owner credentials from runtime credentials.

---

## 10. Required test matrix and release gates

| Area | Minimum tests / evidence |
|---|---|
| Tenant isolation | Cross-tenant read/write/list/delete denial for projects, artifacts, memory, jobs, search, cache, exports and signed URLs; forged tenant header; tenant switch; pooled-connection context reuse; RLS bypass-role checks |
| Object security | Traversal and symlink escape; malicious archive; content-type spoof; oversized payload; expired signed URL; wrong method; unauthorized object reference; checksum mismatch; object-version deletion and restore |
| DB correctness | FK/unique/check constraints; concurrent updates; optimistic conflict; transaction rollback; idempotent retries; migration rerun; old/new schema compatibility |
| Performance | Representative data volumes; p50/p95/p99; query plan; pool saturation; pagination; artifact listing without tree scan; memory retrieval; tenant fairness; queue backlog |
| Durability | Process kill during write/upload; partial upload; object missing; DB failover/restart; worker crash/lease expiry; outbox retry; disk full; backup restore and checksum reconciliation |
| Secrets/audit | No secrets in logs/API/DB dumps; rotation/revocation; unauthorized admin path; audit event completeness; redaction and retention checks |
| Operations | Health/readiness; migration lock; restore runbook; quota alerts; storage growth; cost alerts; patch/version inventory; SBOM and dependency scan |

Release gates:

- No P0 cross-tenant leakage, arbitrary file access, secret exposure, data loss, or unaudited privilege escalation.
- No production deployment with anonymous auth, development token fallback, superuser DB runtime role, public object bucket, or missing backup/restore runbook.
- No migration cutover until data parity and rollback have been demonstrated.
- No “enterprise scale” claim until workload targets and recovery objectives have reproducible evidence.

---

## 11. Observability, quotas and cost protection

Record structured, low-sensitivity metrics with correlation IDs:

- API request rate/latency/error by route and tenant tier (avoid sensitive high-cardinality labels where costly).
- PostgreSQL connection use, pool wait, query duration, locks, deadlocks, slow-query fingerprints, table/index growth, replication lag and backup/PITR status.
- Object operations, bytes, latency, error, orphaned objects, checksum mismatch, upload duration and lifecycle deletion lag.
- Job queue depth/age, lease expiries, retry count, dead-letter count, per-tenant concurrency and execution time.
- Memory/search latency, candidate counts, filter selectivity and index freshness.
- Cost/usage counters for DB, storage, requests, egress, LLM calls and worker compute.

Apply tenant and global budgets for storage bytes, object count, upload size, API requests, job concurrency, active runs, memory/search cost and external model spend. Quotas must be enforced server-side and fail predictably. Add alerts for approaching quota, runaway retries, unexpected storage growth and free-tier limit exhaustion. Keep a graceful degradation plan when optional cache/search/broker services are unavailable.

---

## 12. Decisions to lock now vs defer

### Lock now

- Residency is a first-class, versioned policy enforced across storage, processing, support, telemetry, backups and model calls; it is not a deployment-only setting.
- No cross-region replication/egress by default. Any exception requires an approved policy, safeguards, expiry/review and audit evidence.
- Each generated product carries an explicit residency/processing manifest and owns its runtime data plane.

- PostgreSQL is the relational system of record for shared/concurrent authoritative state.
- Object storage is the default home for large/binary content and immutable artifacts.
- DB rows hold metadata, relationships, permissions, lifecycle and opaque object references.
- All persistence is accessed through domain-specific interfaces and provider adapters.
- Tenant authorization, quotas, audit, retention, migration versioning, performance tests and restore tests are foundational requirements.
- Generated products own their own runtime data plane; Product Forge does not become the default runtime database for those products.
- Local adapters remain supported for zero-cost development; production provider configuration is externalized.

### Defer until evidence requires it

- Dedicated Redis/Valkey, Kafka/RabbitMQ, external vector database, external search engine, database sharding, read replicas, Kubernetes, multi-region active/active and per-tenant dedicated infrastructure.
- Automatic migration of every JSON file or SQLite DB before ownership and write-path analysis.
- Moving all source-controlled Product Forge plans and governance files into PostgreSQL if their Git review/versioning semantics remain valuable.

---

## 13. Implementation checklist

- [ ] Pin branch and commit for the implementation PR.
- [ ] Complete store inventory and classify all existing data stores.
- [ ] Review the two SQLite files’ schemas and all readers/writers.
- [ ] Update `store-registry.json` schema and add automated registry completeness checks.
- [ ] Add architecture ADRs, threat model, country/sector launch profiles and data-flow inventory.
- [ ] Define `ResidencyPolicy`/`RegionResolver`, versioned policy registry and deploy-time data-flow report.
- [ ] Enforce region-aware routing for databases, object storage, queues, caches, vectors, logs/traces, backups, KMS, support and model providers.
- [ ] Add generated-product residency manifest and build/deploy policy gates.
- [ ] Add negative tests for forbidden cross-region access, backups, telemetry, model calls and region changes.
- [ ] Define adapter contracts and conformance test suite.
- [ ] Add migration framework, roles, tenant context, RLS and negative tests.
- [ ] Add local and S3-compatible object adapters.
- [ ] Refactor artifact API to metadata DB + authorized streaming object access.
- [ ] Add canonical relational schema and migration/import/rollback tooling.
- [ ] Migrate critical run/job state with one-writer ownership and compatibility projections.
- [ ] Add memory repository and scoped retrieval.
- [ ] Add benchmarks, SLOs, observability, quotas and load tests.
- [ ] Add backup, restore, object-integrity and tenant-recovery drills.
- [ ] Add enterprise isolation tier only when requirements or measured contention justify it.

---

## 14. Reference material

- PostgreSQL Row Security Policies: https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- PostgreSQL performance tips and `EXPLAIN`: https://www.postgresql.org/docs/current/performance-tips.html
- PostgreSQL backup and restore: https://www.postgresql.org/docs/current/backup.html
- PostgreSQL continuous archiving / PITR: https://www.postgresql.org/docs/current/continuous-archiving.html
- PostgreSQL TLS connections: https://www.postgresql.org/docs/current/ssl-tcp.html
- European Commission — International transfers under GDPR: https://commission.europa.eu/law/law-topic/data-protection/international-dimension-data-protection/rules-international-data-transfers_en
- Government of India / PIB — DPDP Rules 2025 and sector-specific localization context (press release, 1 April 2026): https://www.pib.gov.in/PressReleasePage.aspx?PRID=2247773&lang=1&reg=1
- Government of India / PIB — DPDP Act and Rules overview: https://www.pib.gov.in/PressReleasePage.aspx?PRID=2190014&lang=2&reg=3
- MeitY — Official DPDP Rules, 2025 Gazette notification and phased commencement: https://www.meity.gov.in/static/uploads/2025/11/53450e6e5dc0bfa85ebd78686cadad39.pdf
- CERT-In — Directions under section 70B, including applicable 180-day log retention within Indian jurisdiction: https://www.cert-in.org.in/PDF/CERT-In_Directions_70B_28.04.2022.pdf
- RBI — Storage of Payment System Data circular: https://rbi.org.in/Scripts/NotificationUser.aspx?Id=11244
- US Department of Justice — Data Security Program: https://www.justice.gov/nsd/data-security
- US DFARS — Required storage of certain government data within the United States or outlying areas: https://www.acquisition.gov/dfars/239.7602-2-required-storage-data-within-united-states-or-outlying-areas
- IRS — Cloud computing environment and federal tax information requirements: https://www.irs.gov/privacy-disclosure/cloud-computing-environment
- China PIPL, English text (NPC source): https://en.npc.gov.cn.cdurl.cn/2021-12/29/c_694559_2.htm
- Saudi SDAIA — Regulation on Personal Data Transfer Outside the Kingdom: https://dgp.sdaia.gov.sa/wps/portal/pdp/knowledgecenter/details/RegulationonPersonalDataTransferOutsidetheKingdom/
- OWASP Multi-Tenant Security Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Multi_Tenant_Security_Cheat_Sheet.html
- PostgreSQL RLS performance guidance (Supabase docs): https://supabase.com/docs/guides/database/postgres/row-level-security#rls-performance-recommendations

Use these as engineering references, not as a substitute for checking the actual Product Forge schema, deployment, provider plan, threat model and workload.

---

## Final recommendation

**Modernize the existing design by evolution, not wholesale replacement.** Keep the useful single-writer and derived-projection concepts; centralize persistence behind provider-neutral contracts; move hot, concurrent authoritative state to PostgreSQL; move large bytes to object storage; and make tenant authorization, pooling, quotas, observability, backup/restore, residency policy and performance evidence part of the initial gates. Start with local Docker and adapters to preserve the zero-cost development path, but ensure the same contracts can target managed services, customer-owned storage, country/region cells and enterprise isolation tiers without rewriting domain logic. Residency is a policy-enforced end-to-end data-flow property—not merely the location of the primary database. Validate each launch market with qualified legal/compliance review.

---

## 15. Backlog decomposition & execution plan (authoritative work breakdown)

This section is the **authoritative work breakdown** for the roadmap above. The doc is the design authority; the backlog is the work authority. Every item below cites this doc via `source_ref` and links `source_doc`.

**Epic:** `BI-PF-1292` — *EPIC: Enterprise Data Plane (DB & Storage) — PostgreSQL system of record + object store + tenant isolation + data residency* (scope `product_forge`, origin `review`).

### 15.1 Locked decisions (2026-10-13)

| ID | Decision |
|---|---|
| **L1** | **Language rule = Go.** New shipped/sensitive data-plane logic is Go; existing Python stays (compiled). Every item must pass `scripts/dev/language_rule_review.py` (BI-PF-0387/0388 baseline). |
| **L2** | **WorkerGrid is the single job/lease truth.** PF pipeline run-state is separate but is **not** a second queue (`core/job_manager.py` + `worker…`). |
| **L3** | `config/store-registry.json` becomes the **versioned data-ownership catalogue** + automated coverage gate. |
| **L4** | **Residency is a versioned, fail-closed policy engine.** IN-v1/US-v1 legal profiles are counsel-owned inputs, never encoded legal conclusions. |

### 15.2 Items (phase → id → dependency)

| Phase | ID | Item | Priority | Depends on |
|---|---|---|---|---|
| 0 | BI-PF-1293 | EDP-01: Storage/data architecture ADR + pin develop commit | P0 | — |
| 0 | BI-PF-1294 | EDP-02: Store & data-flow inventory + extend store-registry.json + completeness gate | P0 | 1293 |
| 0 | BI-PF-1295 | EDP-03: Investigate & disposition committed SQLite DBs | P0 | 1293 |
| 0 | BI-PF-1296 | EDP-04: Data-plane threat model + data-flow register | P0 | 1293 |
| 0 | BI-PF-1297 | EDP-05: Residency & Transfer Policy Registry + IN-v1/US-v1 profiles | P0 | 1296 |
| 0 | BI-PF-1298 | EDP-06: Baseline performance capture | P0 | 1294 |
| 1 | BI-PF-1299 | EDP-07: Provider-neutral storage interfaces (11) + conformance harness (Go) | P0 | 1293 |
| 1 | BI-PF-1300 | EDP-08: Versioned migration framework + DB roles + schema-ownership policy | P0 | 1293 |
| 1 | BI-PF-1301 | EDP-09: Tenant context + server-side membership/role verification + RLS + negative tests | P0 | 1296 |
| 1 | BI-PF-1302 | EDP-10: Limits, pool budgets, quotas; prod rejects dev/anon auth | P0 | 1300 |
| 1 | BI-PF-1303 | EDP-11: ResidencyPolicy/RegionResolver + RegionCell attestation + fail-closed provisioning | P0 | 1297 |
| 1 | BI-PF-1304 | EDP-12: Generated-product residency manifest + build/deploy gate | P1 | 1303 |
| 2 | BI-PF-1305 | EDP-13: Local filesystem ObjectStore adapter | P0 | 1299 |
| 2 | BI-PF-1306 | EDP-14: S3-compatible ObjectStore adapter + conformance | P0 | 1305 |
| 2 | BI-PF-1307 | EDP-15: stored_objects + artifacts metadata; ArtifactService; /artifacts authz+streaming | P0 | 1305, 1301 |
| 2 | BI-PF-1308 | EDP-16: Object lifecycle, signed-URL policy, delete/replica/backup reconciliation | P1 | 1307 |
| 3 | BI-PF-1309 | EDP-17: Canonical PostgreSQL schema + indexes + pooling + optimistic versioning | P0 | 1300, 1301 |
| 3 | BI-PF-1310 | EDP-18: Migration/import tooling (parity, rollback, cutover); JSON → projections | P0 | 1309, 1307 |
| 4 | BI-PF-1311 | EDP-19: Durable JobStore/OutboxStore + leases; one-owner boundary vs WorkerGrid | P1 | 1309 |
| 4 | BI-PF-1312 | EDP-20: Append-only AuditStore; split orchestrator/storage; checkpoints → object store | P1 | 1309, 1307 |
| 5 | BI-PF-1313 | EDP-21: MemoryRepository behind the 8 types; PG metadata + object payloads; FTS→pgvector | P1 | 1309, 1307 |
| 6 | BI-PF-1314 | EDP-22: Benchmarks/SLOs + EXPLAIN tuning + observability + degradation | P1 | 1310, 1311, 1312, 1313 |
| 6 | BI-PF-1315 | EDP-23: Backup/PITR + restore drills + DB↔object integrity + region-aware restore | P1 | 1310 |
| 7 | BI-PF-1317 | EDP-24: Scale-out & enterprise isolation tiers **[EVIDENCE-GATED]** | P2 | 1314, 1315 |

### 15.3 Execution waves (dependency-gated)

1. **Wave 0 — Baseline:** 1293 → (1294, 1295, 1296) → 1297, 1298.
2. **Wave 1 — Contracts & security defaults:** 1299, 1300, 1301 → 1302, 1303 → 1304.
3. **Wave 2 — Object store & artifacts:** 1305 → 1306, 1307 → 1308.
4. **Wave 3 — PostgreSQL control plane:** 1309 → 1310.
5. **Wave 4 — Jobs/outbox & audit:** 1311, 1312.
6. **Wave 5 — Memory:** 1313.
7. **Wave 6 — Performance & recovery:** 1314, 1315.
8. **Wave 7 — Scale/isolation (gated):** 1317.

### 15.4 Cross-links with existing work

- **Folded/linked:** `BI-PF-0391` (EPIC B: Scale & Editions) and its child `BI-PF-0402` (B3: persistence adapters) — superseded/absorbed by this epic; retained as historical context.
- **Cross-linked (related, not duplicated):** `BI-PF-1202` (Security/Privacy/Compliance — residency, privacy, audit), `BI-PF-0332` (API-5 hardening: limits, tenant-isolation), `BI-PF-0414` (WorkerGrid pluggable SQLite/PostgreSQL store — completed; reused as the coordination truth, L2), `BI-PF-0387`/`BI-PF-0388` (locked Go-first baseline / ADR — governs L1).

### 15.5 Release gates (from §10, restated)

- No P0 cross-tenant leakage, arbitrary file access, secret exposure, data loss, or unaudited privilege escalation.
- No production deploy with anonymous auth, dev token fallback, superuser DB runtime role, public object bucket, or missing restore runbook.
- No migration cutover until data parity and rollback are demonstrated.
- No "enterprise scale" claim until workload targets and recovery objectives have reproducible evidence.
