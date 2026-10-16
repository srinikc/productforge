# Store Status, Concurrency, RAG, Intake & Generated Products

Companion to `docs/EDP-SAAS-PERSISTENCE-AND-DEPLOYMENT.md`. Owner: EDP (`BI-PF-1292`).
Answers: *what is in the DB vs files, why, how concurrency is handled, and where RAG / intake /
generated-product data live.*

## 1. Store status matrix (file | view | table · migrated?)

| Category (examples) | Home | Migrated? |
|---|---|---|
| **Authored config** — skills, prompts, instructions, **guardrails**, **LLM models** list/tier, **capabilities**, compliance register, context/log policies, budget policy, queue/portfolio config | **file** (git) | n/a (stays file) |
| **Derived projections** — QA results/manifest (qir, qa-manifest), go/no-go, readiness, run/project status, model-gate, BOM, spec-review | **DB view** | view exists; data computed |
| **Runtime domain data** — backlog/issues, runs/stages/attempts, jobs/queues, audit, memory, artifacts metadata, control_state, state/checkpoints, tool_settings, products, providers, registries, traceability, problems, insights, decomposition, allocations, ledger | **DB table** | **only backlog (676)**; others empty |
| **Not built** — **users/identity**, **portfolio** (sqlite), intake raw, generated-product data | table planned / object store | ❌ |

## 2. Why some things STAY files (and how concurrency is handled)
- Authored config is **published, reviewed, versioned, deploy-time** — **not** tenant/runtime data. Git gives
  review + rollback + diff, which a DB row cannot.
- **Concurrency for files = git**: changes land via **reviewed PRs** (one writer per PR); a conflict is a
  **merge review**, not a runtime race. Config changes are rare (not hot-path), so no runtime contention.
- **Runtime backlog files** are protected by a **file lock + the API single writer**; the DB cutover
  (`BI-PF-1399`) replaces this with DB transactions.
- **Rule of thumb:** *tenant/runtime data → DB (transactions + RLS); authored/reviewed knowledge → files (git).*

## 3. Concurrency model (DB)
- **Transactions** + **optimistic versioning** (`version`/`revision`) — stale write → conflict.
- **Row-level security** per tenant (RLS) — no cross-tenant access.
- **Jobs:** `FOR UPDATE SKIP LOCKED` lease-based claim (multiple workers, no double-claim).
- **Pooling:** bounded `PoolOptions`; `SET LOCAL app.tenant_id` per tx (pooled-safe).

## 4. RAG handling
- **Bytes** (documents) → **object store** (local/S3) keyed by sha256.
- **Chunks + embeddings + metadata** → **PostgreSQL** (metadata now; **pgvector** for vectors — EDP-21).
- **Retrieval** → the **`SearchProvider`** port (PG FTS first, pgvector; external vector DB only if measured).
- Never files for RAG — it needs indexed, ACL-filtered, concurrent retrieval.

## 5. Intake items
- An **intake item is work** → becomes a **backlog item** (`backlog_items`, tenant/project-scoped) — DB.
- **Raw intake attachments** (pdf/docx/…) → **object store** + an `intake` metadata store (table).
- Currently intake writes files; moves to DB/object store with the cutover.

## 6. Generated products — their data
- Generated products are **project-scope**: their **metadata** (projects, runs, stages, artifacts,
  evidence, QA, traceability) → **DB tables**; **artifacts/bytes** → **object store**.
- So a product's generated data points live in the **same standard** (DB + object store), tenant/RLS-scoped —
  not bespoke files.

## 7. Bottom line
- **Backlog data = migrated (676)**; **everything else = file (config, by design) or empty table (not migrated)**.
- Remaining data migration = **EDP-18 domains** (portfolio/forge/project/pipeline) + **per-store migration**
  (incl. SQLite, intake, generated-product data). Tracked, not assumed done.
