# Product Forge — Organized Audit Master Report

**Repository:** `srinikc/productforge` · **Branch:** `develop` · **Pinned commit:** `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`  
**Review date:** 28 September 2026 · **Report revision:** editorial consolidation of the final Batch CC report  
**Status:** **394/394 agreed scoped paths received static semantic review**; **0 pending within that scope**. The source tree contains **3,026 tracked files**, so this is **not** a repository-wide audit. The legacy dashboard is outside the active scope.

> **Read this section first.** The original 4,297-line report is preserved verbatim under **Historical evidence archive**. Earlier batch progress statements and tentative findings in that archive describe their *historical checkpoint*, not the current final status. This front section is the consolidated navigation and decision layer; it does not silently overwrite original evidence or turn provisional candidates into confirmed permanent findings.

## Executive summary

The agreed 394-file static-review scope is complete. The main engineering risk is **false success**: a pipeline can report approval, verification or completion without sufficiently binding those decisions to the current run, executed tests and accepted quality-gate results. A second risk cluster is **state integrity**: separate JSON writers, weak lock ownership, non-atomic updates and stale artifact reuse can make orchestration state disagree across components. The third is **authorization and budget enforcement**, particularly missing-agent-spec tool execution, approval fallbacks and inconsistent token/cost accounting.

These are **static source findings and risk scenarios**, not proven production incidents. The audit did **not** run unit/integration tests, build packages, execute concurrency tests, reproduce exploits, or modify the repository. Four historical `.bak_pre_*` executor snapshots were reviewed as archival regression evidence; ordinary Python module resolution does not import them as the active executor, but package/restore reachability has not been exhaustively verified.

| Measure | Final disposition |
|---|---|
| Agreed scoped files | **394** |
| Static-semantic-reviewed scoped files | **394 (100%)** |
| Pending within agreed scope | **0** |
| Original repository tracked files | **3,026** |
| Active legacy dashboard | **Excluded by scope** |
| Permanent finding register | **PF-001–PF-521 referenced as the cumulative register**; do not interpret the upper ID as a verified unique-open-defect count |
| Missing source detail in this report | **PF-071–PF-078** have no standalone identifiable occurrence in the supplied final report; the historical PF-070–PF-079 recovery caveat remains |
| Additional BU–CC findings | **Provisional / cross-referenced**, not assigned new permanent IDs |
| Runtime/build/security validation | **Not executed** |
| Remediation status | **Not verified** |

## Execution reliability blueprint — prevent agents from doing too much or too little

**Status of this section:** implementation guidance synthesized from the audit findings and the subsequent execution-control discussion. It is **not** an additional source audit, proof of runtime behavior, or a claim that these controls already exist. The linked PF references point to source-backed concerns in the historical archive; the proposed lifecycle, limits and release gates are design recommendations.

### Do all findings have to be fixed before seamless execution?

**No.** Triage every finding, but distinguish controls required for safe unattended execution from hardening and archival/documentation work. A lower-priority finding becomes a blocker when its affected feature is enabled or externally exposed. Conversely, a severe defect in an unreachable historical backup is not an active-runtime blocker unless packaging or restore paths make it reachable.

| Level | Scope | Release decision |
|---|---|---|
| **M0 — Mandatory for unattended execution** | Scoped agent contracts; fail-closed authorization and approvals; trustworthy verification and completion; authoritative transactional state; run-bound artifact provenance; enforceable cost/time/attempt budgets and stop conditions | Block unattended execution until applicable controls are implemented and regression-tested. A human-supervised development mode may use explicit, audited overrides, never silent success. |
| **M1 — Reliability and scaling** | Improved model selection and cost reporting; observability and metrics; automated recovery; performance tuning; concurrency beyond the tested deployment profile | Implement before enabling the corresponding scale, autonomy or deployment feature; prioritize any M1 item that undermines an M0 guarantee. |
| **M2 — Maintainability and archive** | Documentation diagrams, missing generated links, historical backup hygiene and nonblocking presentation issues | Can follow the first reliable execution milestone, subject to packaging and compliance requirements. |

### Single enforceable agent execution contract

The orchestrator, not the agent prompt alone, must own the execution boundary. Every dispatched task should carry a validated, immutable contract with:

- **Identity and provenance:** project ID, run ID, stage ID, task/attempt ID, agent identity, upstream dependency versions and expected input artifact hashes.
- **Work scope:** one clear objective; explicit in-scope and out-of-scope operations; concrete deliverables and required file paths; allowed side effects and a definition of done.
- **Permissions:** agent-specific tool allowlist, canonical workspace containment, allowed network targets, secret access policy, human approval requirements and privileged action policy.
- **Limits:** model/capability requirements; maximum context and output tokens; total cost and wall-clock budget; maximum tool calls, repair attempts and repeated/no-progress cycles; permitted parallelism.
- **Verification:** applicable tests and minimum executed-test evidence, output schema, artifact content hashes, compliance/security checks, expected reviewer quorum where relevant, and authenticated approval bound to the current run and artifact version.
- **Recovery:** checkpoint ID, idempotency key for side-effecting actions, retry eligibility, rollback/compensation strategy and escalation owner.

**Contract rule:** missing required fields, unknown tool or stage IDs, unreadable policies, absent test runners and unverifiable approvals are `BLOCKED`/`UNVERIFIED`, not `PASS` or `COMPLETED`. Relevant audit examples: PF-002, PF-003, PF-004, PF-006, PF-036, PF-255, PF-256, PF-497, PF-500 and PF-505.

### Execution lifecycle and bounded feedback loop

1. **Preflight:** validate DAG dependencies and contract; verify credentials, workspace boundaries, permissions, budget reservation, required tools and inputs. Reject unknown prerequisites rather than quietly filtering them.
2. **Dispatch:** allocate a unique attempt ID and idempotency key; record a durable `RUNNING` event only after lock/lease acquisition. Give the agent the smallest sufficient context and exact deliverables.
3. **Execute:** enforce tool allowlists and side-effect policies at the actual tool-execution boundary. Record token/cost/tool usage for *all* attempts; stop before hard limits. Treat the agent's self-reported progress as advisory.
4. **Verify:** validate required outputs and hashes, run the applicable tests, bind compliance evidence to this run/attempt, and require the exact approval decision for the exact artifact revision. `No tests executed`, `unknown`, `skipped` and `not applicable` must remain distinct.
5. **Decide once per attempt:**
   - **PASS:** commit the verified artifact manifest and stage transition atomically, release resources and advance eligible downstream DAG nodes. Do not invoke the agent again merely to polish already accepted work.
   - **REPAIRABLE GAP:** return a *specific* failing criterion and minimal relevant context; retry only the deficient output within the remaining budget and attempt cap.
   - **BLOCKED / NEEDS HUMAN:** pause with a reason, evidence and decision request; no implied approval on timeout or parse failure.
   - **FAILED / NO PROGRESS:** stop on repeated identical failure, hard-budget exhaustion, unrecoverable dependency failure or unauthorized operation; persist an accurate terminal state and resumable checkpoint where appropriate.
6. **Resume:** reconcile the authoritative event/state ledger; revalidate lease ownership, dependency versions, artifact hashes, approvals and budget before continuing. Never infer completion from the existence of a Markdown file or an old `*-latest.json` report.

**Prevent overdoing:** cap repair attempts, tool calls, token/cost spend and no-progress cycles; use change-scoped verification; prevent retries of non-idempotent side effects; terminate after verified acceptance. **Prevent underdoing:** require every mandatory deliverable, executed test and approval; distinguish `PARTIAL` from `PASS`; never count skipped or absent checks as successful verification.

### Required state and completion invariants

| Invariant | Enforcement point | Failure test |
|---|---|---|
| A task cannot execute a tool outside its authorized list, even when its agent spec is missing | Tool registry / executor, not prompt alone | Missing spec, forged tool name, text-protocol and native tool paths (PF-004; BV-C02) |
| An approval applies to the exact run and artifact revision and must be explicitly affirmative | Human-proxy and compliance-specific approval gates | Reject, timeout, malformed JSON, stale approval, proxy exception (PF-001, PF-151, PF-500) |
| `COMPLETED` requires all mandatory dependencies, outputs, checks and approvals to pass | Stage transition and close-loop/finalizer | Unknown stage, skipped gate, missing test runner, zero executed tests, stale compliance report (PF-002, PF-006, PF-036, PF-060, PF-069, PF-497, PF-505) |
| Every artifact and test result belongs to the current run/attempt | Artifact manifest and resume reconciliation | Copy prior-run artifacts or `latest` report into a new run (PF-006, PF-256; CB-C01/CB-C03) |
| Concurrent operations cannot exceed a shared budget or overwrite authoritative state | Atomic budget reservation; durable queue, ledger and fencing token | Two simultaneous last-budget spends, held lock, process crash, double enqueue (PF-011–PF-014, PF-025) |
| Timeout, emergency conservation and no-progress exhaustion cannot silently become success | Execution state machine / finalizer | Inject budget exhaustion, force timeout and max-iteration exit; compare active executor with archival CC-H01 regression |
| An already accepted task is not re-run without an explicit invalidation event | Scheduler and dependency/artifact versioning | Retry after success, unchanged input, duplicate event delivery |

### Minimum end-to-end acceptance suite

| Scenario | Expected result |
|---|---|
| Happy path with verified artifacts, tests and approvals | Exactly one committed successful stage transition; downstream stage starts once. |
| Output exists but required deliverable is missing or schema invalid | `PARTIAL`/repair request naming the gap; never `COMPLETED`. |
| `pytest` absent, tests skipped, or compliance status unknown | Explicit `UNVERIFIED`/`BLOCKED` and nonzero CLI exit where verification is mandatory. |
| Human rejects, times out, or proxy returns malformed data | No approval or release; explicit blocked/failed state and audit record. |
| Tool call exceeds allowlist or workspace boundary | Rejected before side effects, with attribution to agent and attempt. |
| Same repair fails repeatedly or produces no measurable progress | Bounded retry then stop/escalate; no unbounded token consumption. |
| Two agents race for the last budget or the same queue/state record | At most one valid reservation/transition; no lost updates. |
| Crash after output write but before stage commit | Resume reconciles run-bound hashes and avoids duplicate side effects. |
| Prior-run artifact/report/approval is present during resume | Stale evidence rejected; only current verified manifest counts. |
| Time or cost limit is exceeded midway through a DAG | Accurate paused/failed status, no premature pipeline-complete event. |
| Verified task receives duplicate dispatch | Deduplicated by idempotency key; no repeated agent work. |

**Suggested execution milestone:** first make M0 tests pass in a serial, human-supervised mode. Then repeat under the intended unattended and parallel-worker configurations. Do not infer production readiness from static-review completion or from a single happy-path smoke test. Record test run ID, commit, environment, executed count, failures and artifacts for each gate.

### Mapping to the consolidated action plan

M0 spans **workstreams 1–4 and the enforceable budget/attempt/stop-condition subset of workstream 5** below. Workstream 5's advanced routing/analytics and workstream 6's documentation/archival cleanup can generally proceed in parallel. This refines the earlier editorial release-gate proposal rather than changing the underlying source findings or their historical IDs.

---

## Consolidated action plan

| Order | Workstream | Existing finding references and later candidates | Required acceptance evidence |
|---|---|---|---|
| **1 — Critical** | **Fail-closed approval and authorization** | PF-001, PF-004, PF-151; BV-C01, BV-C02, CB-C02 | Rejection, malformed proxy response, missing agent spec, expired/stale approval and unauthorized tool calls all block; approval is bound to authenticated principal, run ID and artifact digest. |
| **2 — Critical** | **Truthful verification and completion** | PF-006, PF-036, PF-039, PF-060, PF-069, PF-157; BU-C07, BW-C01 | Failing or absent tests, unknown compliance, unrecognized selected stage and failed quality gate cannot produce a successful run or exit code. Persist completion only after mandatory evidence passes. |
| **3 — High** | **Single-writer, transactional state** | PF-007, PF-011–PF-016, PF-020, PF-025, PF-041; BU/BW/CB state candidates | Concurrent writers, lock expiry, crash during checkpoint, queue fallback and backlog multi-item update preserve one authoritative, recoverable state. |
| **4 — High** | **Run-bound artifact provenance and resume** | PF-006, CB-C01, CB-C03 and compliance stale-output candidates | Restart never accepts prior-run artifacts/reports as current evidence without run/attempt identity and content-hash validation. |
| **5 — High** | **Budget, model and delegation controls** | PF-008, PF-013, PF-017, PF-038, PF-067, PF-154, PF-155 | Reserve budget atomically; enforce hard model capability and context limits; aggregate every tool/LLM attempt; delegation retries cannot duplicate side effects. |
| **6 — Medium** | **Docs, CLI and archival hygiene** | BW-C05, BX-C01–C04, CB-C04–C05, CC-H01–H05 | CLI handles alphanumeric stages; generated Draw.io is valid XML; documentation links resolve; backups excluded from releases; historical timeout/skip behavior has regression tests. |

**Release gate proposal (new editorial synthesis, not an existing audit result):** treat workstreams 1–4 as prerequisites for claiming a reliable autonomous production pipeline. Workstreams 5–6 can proceed in parallel, with their own explicit acceptance criteria. Severity and sequencing should be revalidated against the deployment model and actual caller exposure.

## Cross-cutting findings: one issue, multiple observations

The original chronological report repeats several root causes because later batches found them in additional modules. Keep the original source evidence, but track remediation under one *issue family* rather than creating a ticket for every mention.

| Issue family | Primary existing register | Corroborating later observations | Deduplication rule |
|---|---|---|---|
| Approval may fail open | PF-001 | BV-C01; CC-H03 (historical comparison) | Distinguish the proxy's fallback behavior from the active executor's discarded decision; link both under an end-to-end approval epic, not one assumed identical bug. |
| Unauthorized agent tools | PF-004 (text tool loop) | BV-C02; CC-H04 (inherited from backup) | Separate entry-point defects but one shared authorization policy and regression suite. |
| Tests/evidence falsely pass | PF-006, PF-036, PF-039 | BU-C07; BW-C01; PF-157 | Separate root causes, shared release-blocking verification contract. |
| Premature completion | PF-060, PF-069 | CB execution review; CC-H01 (archival timeout regression) | Historical backup timeout behavior is not a new active defect; active quality-gate and unknown-stage defects remain distinct. |
| Lost or stale state | PF-007, PF-020, PF-025, PF-041 | BU backlog; BW CLI; CB-C01–C03; CC-H02 | Group by authoritative store, transaction boundary and owner; retain separate concrete race/failure scenarios. |
| Documentation generator drift | BX-C01–C04 | BY follow-up | One docs-generator workstream; keep XML escaping, canvas sizing, output path and missing PDF as separately testable acceptance cases. |

## Findings register hygiene

**Preserve existing IDs.** The source report says PF-001–PF-521, but the supplied text contains no identifiable occurrence of PF-071 through PF-078. Those eight IDs must be recovered from the authoritative historical finding register before claiming a complete, individually traceable 521-entry register. Some IDs are cross-references rather than standalone entries; therefore **no exact total of unique, open, resolved or P0 findings is asserted here**.

**Keep candidates provisional.** BU/BV/BW/BX/BZ/CB candidate identifiers and CC-H archival cross-references are not new permanent PF IDs. For each candidate, triage against the canonical register using the same root cause, affected call path, exploit/failure precondition, and remediation test. Mark as `duplicate`, `extends existing`, or `new distinct`; allocate a new permanent ID only after that review.

**Separate evidence levels.** Label each ticket `static-confirmed source behavior`, `conditional integration impact`, `runtime-reproduced`, `fixed`, or `regression-verified`. This report supports the first two categories only. No fixes or runtime passes are established.

**Scope and date discipline.** All findings describe the pinned 27–28 September 2026 code baseline. Earlier “pending” counts and batch-specific totals are historical and superseded by Batch CC's 394/394 scope ledger. The 394-path selection excludes the legacy dashboard and does not cover the other tracked repository files.

## Recommended report navigation

1. **Executive summary and execution reliability blueprint** — current final status, mandatory versus deferrable controls, bounded execution contract, lifecycle and acceptance tests.
2. **Consolidated action plan** — prioritized remediation workstreams and measurable acceptance evidence.
3. **Cross-cutting findings and register hygiene** — deduplication and evidence-confidence rules.
4. **Historical evidence archive** — the original final report below, preserved without deletion; use its exact file/line evidence and original batch notes.
5. **Final Batch CC closure** — the last section of the archive; authoritative final scoped-review status.
6. **Original Batch BT recovery ledger** — archived inventory reconciliation; useful for tracing how 384 became 394.

## What this editorial revision changed

- Added a single authoritative status and executive summary at the top.
- Consolidated recurring remediation into six workstreams and added measurable acceptance criteria.
- Grouped repeated observations without deleting distinct defects or rewriting source evidence.
- Flagged the stale opening statement in the original report (it still describes Batch K), the historical progress figures, and the eight absent PF IDs.
- Kept the entire original report intact as a traceable evidence archive. **This is editorial organization, not a new source audit or formal candidate-by-candidate register deduplication.**

---

# Historical evidence archive — original final Batch CC report (verbatim)

**Archive handling:** All text below is retained from the original final report. Its early status paragraphs and interim batch totals are historical; refer to the executive summary and final Batch CC closure above for the current scoped-review status.

---

# Product Forge — Cumulative GitHub `develop` Audit

**Baseline:** `srinikc/productforge`, `develop`, commit `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374` (2026-09-27). Git tree was fetched recursively and reported **3,026 tracked files**, **412 `.py` files**, **628 `.md` files**, **1,268 `.json` files**, and approximately **29 MB** of tracked blobs; GitHub reported `truncated: false`.

**Status:** Incremental cumulative report through **Batch K**; **NOT** a complete 3,026-file audit. Historical Batches A–J retained, including Batch I detail-reconciliation caveat. **152 provisional distinct files retrieved** (138 historical plus 14 new Batch K files; historical Batch I overlap remains unverified). **99 cumulative finding IDs PF-001–PF-098**; PF-070–PF-079 historical details pending independent recovery and PF-043–PF-047 legacy-dashboard historical/out of scope. Static source review only; no runtime tests executed.

**Reference documents:** `docs/productforge_full_architecture.md`, `docs/pipeline_current_issues.md`, `config/store-registry.json`, and root `pipeline-definition.json`, all retrieved from the pinned GitHub commit. The architecture states 'one truth per concern, one writer per file', paths SSOT, config-driven thresholds, gates, and per-run lifecycle. Current issues document reports 2026-09-27 `smoke-all` measurements; these are historical observations, not new tests.

## Finding register (deduplicated across batches; PF-021–PF-028 appended in Batch C and PF-029–PF-035 in Batch D and PF-036–PF-042 in Batch E and PF-043–PF-049 in Batch F below)

| ID | Priority | Component / source line | Evidence and consequence | Recommended fix | Verification |
|---|---|---|---|---|---|
| PF-001 | P0 | `core/human_proxy.py:49,86` | Unparseable auto-HIL response and proxy exception both return `approve`. Approval gate fails open. | Return blocked/error and require explicit approval on uncertain outcome. | Unit tests for malformed JSON, empty response, API error. |
| PF-002 | P0 | `core/dag_executor.py:105,117` | Unknown dependencies are filtered out of readiness checks, allowing a stage to become ready despite invalid prerequisites. | Validate all DAG references at load time and reject unknown IDs. | Unknown-dependency and cycle tests. |
| PF-003 | P0 | `core/agent_readiness.py:108-109` | Credential-check exception sets `has = True`; unknown is treated as available. | Three-state readiness; block unknown for operations requiring credentials. | Inject credential checker failure. |
| PF-004 | P0 | `core/agent_tool_loop.py:148-175` | Text-protocol tool loop builds `tool_names` but does not authorize each parsed name against it before `registry.execute`. Native path does check `allowed` at lines 115-121. | Enforce per-agent allowlist inside registry execution and in both loops. | Disallowed `run_command` tool-call test. |
| PF-005 | P0 | `core/code_executor.py:145-147,270-283` | Backup flattens `/` and `\\` to `_`; rollback converts all `_` to `/`, corrupting names with underscores; new-file creation has no rollback manifest. | Transaction journal of exact original paths and operation types; rollback creates/deletes/modifies atomically. | Files with underscores and nested paths; create-then-fail test. |
| PF-006 | P0 | `core/close_loop.py:78-105,123-131` | Any stage Markdown can satisfy artifact evidence; any passing compliance report can satisfy compliance; no current-run or artifact-hash binding at these checks. | Require run ID, stage, artifact hashes, current test suite and explicit approval binding. | Stale-report and unrelated-artifact tests. |
| PF-007 | P1 | `core/run_entry.py:35-54`; `core/orchestrator/stage_runner.py:30-43` | Events and status projections are separately emitted with exception suppression; `run_started` emitted before lock acquisition. This can yield false starts and divergent status. | Emit authoritative transactional lifecycle event after lock; derive projections idempotently and reconcile. | Fail status write, lock acquisition failure, replay tests. |
| PF-008 | P1 | `core/orchestrator/llm_client.py:144-147` | Default `PIPELINE_MIN_TOTAL_TOKENS=200000` raises the derived continuation ceiling. This is a ceiling, not proof of actual spending. | Enforce tier/task-specific maximums and per-call/agent caps, including HIL. | Tiny-task token-budget tests. |
| PF-009 | P1 | `core/deploy_providers.py:56-63` | HTTP status below 500 is treated as healthy, including 401, 403 and 404. | Require expected status and content-specific readiness contract. | Simulated 401/404 tests. |
| PF-010 | P1 | `core/control_plane.py:7-8,33-56` | Docstring says `CONTROL_PLANE_DSN` can select Postgres, but `_conn` unconditionally opens SQLite. | Implement real driver/DSN selection or remove unsupported claim. | DSN-specific integration tests. |
| PF-011 | P1 | `core/budget.py:45-58,91-100` | File-lock acquisition retries then returns `None`; `_mutate` continues even if no lock was acquired, risking lost updates under contention. | Fail closed on lock timeout; add stale-lock recovery and transaction tests. | Parallel mutation with held lock. |
| PF-012 | P1 | `core/budget_tracker.py:112-125` | One logical spend snapshot is persisted through three separate `update_section` calls and then an unlocked `_b.save` for history. Crash/concurrency can yield inconsistent limits/usage/history and overwrite another writer's changes. | Single atomic budget mutation covering all sections; append-only spend ledger with idempotency key. | Concurrent record_spend and injected crash tests. |
| PF-013 | P1 | `core/budget_tracker.py:236-254` | `can_spend` checks a snapshot without reserving funds; simultaneous calls can both pass. | Atomic pre-call reservation and post-call reconciliation, shared across workers. | Two parallel requests competing for last budget. |
| PF-014 | P1 | `core/queue_manager.py:67-85,106-125` | File-backed queue uses read-modify-write without a lock. Atomic rename protects against partial files but not concurrent lost enqueues. | Use SQLite job queue as sole authoritative queue or transaction/lock with versioning. | Concurrent enqueue test. |
| PF-015 | P1 | `core/tenancy.py:64-105` | Tenant membership changes read and rewrite shared JSON without interprocess locking; concurrent role/invite changes can be lost. | Use control-plane transactional membership table with tenant-scoped constraints. | Concurrent invites and role updates. |
| PF-016 | P1 | `core/model_catalog.py:197-200` | Model catalog refresh writes directly to target JSON, exposing partial/truncated reads if interrupted. | Temp file, fsync and atomic rename; keep last known-good catalog. | Kill refresh mid-write. |
| PF-017 | P1 | `core/model_gate.py:64-95` | `UNKNOWN` model compatibility is counted separately but only `INCOMPATIBLE` enters `blocked_agents`; execution-path policy for unknown requires confirmation. | Make unknown handling explicit and gate high-risk capabilities on verified fit. | Missing catalog and unknown capability tests. |
| PF-018 | P1 | `core/job_manager.py:95-112` | Jobs are keyed by project row; re-enqueue updates `run_id` and metadata. Immutable attempt history is not modeled by this row. | Distinct job/run-attempt records plus one active-run constraint per project. | Re-enqueue while running and history-preservation tests. |
| PF-019 | P1 | `core/context_preflight.py:25` | Model-window check alone does not establish that immutable instructions fit the effective per-agent input budget. | Validate instruction, context, tool-schema and output-reserve budgets separately. | Oversized card under small per-agent cap. |
| PF-020 | P1 | `core/run_state.py:34`; `core/run_status.py:34-41` | Some run-state/status writers use direct writes or independent projections, weakening lifecycle atomicity. | Atomic writes and authoritative event replay. | Concurrent writers and crash-recovery tests. |

## Batch B — additional modules retrieved and inventoried

`budget.py` (208 lines); `budget_protection.py` (421); `budget_tracker.py` (342); `budget_allocator.py` (268); `control_plane.py` (137); `tenancy.py` (121); `queue_manager.py` (226); `run_entry.py` (157); `pipeline_store.py` (84); `model_gate.py` (147); `model_catalog.py` (328); `context_policy.py` (87); `context_manager.py` (163); `run_breaker.py` (173); `dead_letter_queue.py` (139); `verification_policy.py` (68). All were retrieved directly via GitHub at the pinned commit. New findings PF-010 through PF-017 are attributable to this batch; PF-007 was further confirmed here.

### Architecture-to-code crosswalk

- **One writer / one truth:** `budget.py` implements a consolidated budget store with atomic file replacement, but `budget_tracker._save_budget` still performs multiple independent mutations and a direct unlocked save. `queue_manager` remains a separate JSON queue alongside `job_manager`'s SQLite queue. `run_entry` independently updates log, events, and status.
- **Config-driven governance:** `model_gate` distinguishes OK/UNKNOWN/INCOMPATIBLE, but unknown handling must be explicitly enforced at the execution boundary. `llm_client` retains a large default continuation floor.
- **Multi-tenant SaaS:** `control_plane` currently uses SQLite regardless of the documented Postgres DSN; `tenancy` uses a separate unprotected JSON read-modify-write store.
- **Quality gates:** `close_loop` evidence checks are existence/any-pass based and insufficiently bound to the current run.
- **Observability:** The September 27 smoke-run issue report documents inconsistent status and hidden human-proxy cost; the current code paths above show plausible failure mechanisms, not proven single root causes.

### Review methodology and limitations

- GitHub tree and each named source file were fetched directly through the connected GitHub tool, with the branch pinned to an immutable commit.
- Source-level findings above are supported by inspected line ranges. No runtime tests, lint, dependency installation, secret scanning, dynamic API requests or exhaustive cross-file call graph have been executed in this batch.
- **Pending:** remaining ~376 Python files, active dashboard API and UI, agent cards, 29 config files, all test definitions, deployment manifests, documentation reconciliation, generated artifacts and binary resources. Generated outputs and historical logs will be inspected for evidence and provenance rather than treated as active implementation.

### Source links

For each `core/<file>.py`, use `https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/<file>.py#L<line>`. Architecture: `https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/docs/productforge_full_architecture.md`. Pipeline issues: same prefix under `docs/pipeline_current_issues.md`.

---

## Batch C — dashboard API, intake, backlog, storage and concurrency (2026-09-28)

**Baseline:** same immutable `develop` commit. **New files retrieved:** `dashboard/api/app.py` (1,041 lines), `core/artifact_registry.py` (160), `core/artifact_store.py` (266), `core/backlog.py` (1,087), `core/intake.py` (203), `core/intake_adapters.py` (182), `core/intake_api.py` (511), `core/intake_channels.py` (430), `core/intake_files.py` (263), `core/job_manager.py` (354; recheck), `core/lock_manager.py` (390), `core/websocket_manager.py` (290), `core/write_safety.py` (358). **12 newly retrieved distinct files, one recheck; cumulative 48 distinct modules** (previous 36 + 12). All 13 files fetched in full and function/endpoint inventories examined; targeted paths were reviewed line by line. This is not an assertion of exhaustive analysis of every line in these modules.

### New findings (append to consolidated register)

| ID | Priority | Source | Confirmed evidence / risk | Remediation | Required verification |
|---|---|---|---|---|---|
| PF-021 | **P0** | `dashboard/api/app.py:69-80,125-129,597-600,635-666` | `operator_guard` checks `licensing.instance_role()` but does **not** call `auth` or authenticate a principal. `x_roles` is a client-controlled header; absent roles pass when an API token is configured. Operator-only endpoints depend solely on this guard. Exposure depends on instance role and network reachability. | Authenticate every operator endpoint; derive roles from verified server-side session/JWT; require explicit platform-admin authorization and fail closed when token is unset. | Anonymous and spoofed-role requests against an operator instance, with and without `DASHBOARD_API_TOKEN`. |
| PF-022 | **P0** | `dashboard/api/app.py:56-67,131-172`; `core/tenancy.py:60-105` | `auth` is a shared bearer-token check, not tenant-scoped authorization. Tenant-member list, invite, role change and delete endpoints accept arbitrary `{tenant}` and do not establish that caller belongs to it or has tenant-admin rights. | Introduce authenticated principal with tenant ID and role; authorize every tenant-scoped operation; enforce server-side tenant binding. | Cross-tenant read, invite, self-escalation and delete tests. |
| PF-023 | **P1** | `dashboard/api/app.py:214-237` | SSE `/api/v1/events` lacks `Depends(auth)` and streams global `.orchestration/events.jsonl`; `project` query argument is unused. May expose cross-project event metadata on reachable deployments. | Require authentication and project/tenant authorization; filter events by permitted project; cap connections. | Anonymous and cross-project SSE tests. |
| PF-024 | **P1** | `core/lock_manager.py:96-175` | Project lock acquisition checks existence, then writes a shared `.tmp` and renames it. No exclusive-create or compare-and-swap guards acquisition; two contenders can both believe they acquired the lock. | Use atomic `O_CREAT|O_EXCL` lock creation, OS lock or transactional SQLite lease with fencing token; unique temporary paths and verified ownership. | Multiprocess simultaneous acquisition test. |
| PF-025 | **P1** | `core/backlog.py:197-215,427-476` | Backlog `_lock` returns `None` after 5 seconds; `add_epic` continues mutating item/index/counter stores even without the lock. `_unlock(None)` suppresses error. This risks duplicate IDs and lost updates. | Raise on timeout and abort mutation; recover stale locks safely; commit item, indexes and counters transactionally. | Held-lock timeout and concurrent ID allocation tests. |
| PF-026 | **P1** | `core/artifact_store.py:173-212` | Existing artifacts are overwritten in place; `version` is set to 2 whenever a prior nonempty artifact exists, regardless of previous version. No immutable revision or atomic write. | Immutable artifact versions, atomic writes, artifact-hash/run-ID manifest and retention policy. | Three successive revisions and interrupted write tests. |
| PF-027 | **P1** | `core/websocket_manager.py:32-51,211-245` | `websocket_endpoint` accepts any connection and subscribes to any supplied topic without authenticating or authorizing the connection. Impact depends on whether/how this handler is mounted and network exposure. | Authenticate before `accept`; authorize topic subscriptions and tenant/project scope; connection limits. | Trace actual router mounting, then anonymous and cross-tenant WebSocket tests. |
| PF-028 | **P2** | `core/intake_files.py:49-72,195-212`; `dashboard/api/app.py:296-325` | Upload stores complete request bytes before extraction; no explicit per-file byte cap or quota is visible in these paths. `MAX_TEXT` caps extracted text, not uploaded binary size. | Enforce streaming request and per-tenant storage limits; reject oversize before saving; validate types and archive quota. | Oversize multipart/base64 requests and disk quota tests. |

### Architecture crosswalk — Batch C

- **Tenant isolation and SaaS security:** `control_plane.py` models tenants/users/sessions, but `dashboard/api/app.py` does not derive an authenticated principal from that store for the inspected tenant administration routes. Operator guard and SSE are separately exposed. These are critical before any internet-facing/multi-tenant deployment.
- **One writer and atomicity:** `backlog.py` centralizes backlog writes but proceeds after lock timeout. `artifact_store.py` overwrites files in place. `lock_manager.py` uses rename as if it were exclusive lock acquisition; rename is atomic replacement, not atomic ownership.
- **API surface:** `dashboard/api/app.py` contains extensive authenticated project, pipeline, backlog, billing and licensing endpoints. Endpoint decorators were inventoried, but this batch did not dynamically exercise them or prove all downstream route authorization. `core/intake_api.py` also declares a FastAPI router; mounting and auth dependency inheritance require integration verification.
- **File intake:** `_safe_name` strips directory traversal from uploaded filenames, which is a positive control. `MAX_TEXT` is an extraction-size limit, not a file-upload-size limit.

### Batch C evidence and limitations

Every named file was fetched from GitHub at the pinned commit. Detailed code paths and relevant line spans were re-fetched separately. The security findings describe what the code allows **if endpoints are deployed/reachable**; this audit has not tested an actual running deployment or established exposure on a public host. `websocket_endpoint` mounting is not yet verified. No code was modified and no runtime tests were executed.

### Remaining work

Continue in subsequent batches with orchestrator mixins and remaining core modules, the remainder of dashboard API and frontend, agent cards and skills, config/schema validation, scripts/CI/deployment, all tests, docs-to-code crosswalk and selected generated artifacts/logs. Distinguish tracked binaries and historical outputs from executable source; a complete inventory and disposition is needed for all 3,026 tracked paths. No automatic background continuation is scheduled: each subsequent batch requires an active chat turn.


## Batch D — orchestrator execution, compliance, cache and checkpoints (2026-09-28)

**Baseline:** pinned `develop` commit `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`. **12 newly retrieved modules:** `core/orchestrator/agent_execution.py` (641 lines), `artifacts_map.py` (119), `checkpoint.py` (60), `compliance.py` (368), `delegation_coord.py` (115), `feature_tracker.py` (116), `phasing.py` (80), `prompt_builder.py` (323), `reporting.py` (462), `status.py` (171), `storage.py` (267), `types.py` (80). The earlier batch had retrieved `agent_runner.py`, `llm_client.py`, `model_router.py`, and `stage_runner.py`; the remaining `__init__.py` is a trivial 152-byte package file. All 12 new modules were retrieved in full; function inventories and high-risk paths inspected, with separate line-scoped reads for evidence. **Cumulative: 60 distinct modules retrieved, 35 deduplicated findings.** No runtime tests.

### New findings — consolidated register continuation

| ID | Priority | Source | Confirmed evidence / risk | Remediation | Verification |
|---|---|---|---|---|---|
| PF-029 | **P0** | `core/orchestrator/agent_execution.py:317-326`; `core/artifact_store.py:173-180` | `execute_agent` calls `create_or_update_artifact(project=..., artifact_path=..., agent=..., stage=...)` while the actual function requires `project_dir, stage, agent, content`. The call raises `TypeError` for unexpected keyword `project` on each artifact, and the surrounding `except Exception: pass` hides it. This integration path does not register the generated artifacts through that function. | Replace with an API that registers existing artifact files or read content and call the correct function; never suppress registration errors; add typed integration tests. | Execute an agent producing one artifact and assert registry metadata, hash and run provenance; inject registration failure. |
| PF-030 | **P0** | `core/orchestrator/compliance.py:143-162,345-367` | When `validate` verification returns `ran=False` or raises, the compliance orchestrator only logs it; neither case sets `passed=False`. A separate rule-compliance pass can therefore survive without actual test execution. If the compliance action handler itself raises, the error is also logged and `blocking_action` remains `None`. The ultimate release decision additionally depends on downstream policies; this is a gate-enforcement gap in the inspected path. | Define required verification per scope and stage; return explicit blocked/unknown on missing or failed mandatory verification and action-handler errors. | Validate-agent tests for unsupported stack, absent files, runner exception and compliance-handler exception; check end-to-end release gate. |
| PF-031 | **P1** | `core/orchestrator/compliance.py:63-77`; `core/close_loop.py:78-131` | Compliance writes `compliance/<agent>-compliance.json` by agent name only, overwriting prior stage/run reports. Its output does not itself include a run-scoped filename; downstream close-loop checks can accept stale or unrelated evidence. | Run/stage/artifact-hash keyed immutable compliance records and a current-run manifest; keep dashboard's latest view as a projection. | Two runs and two stages of the same agent, then assert no stale approval can be reused. |
| PF-032 | **P1** | `core/orchestrator/storage.py:82-108` | `AgentAuditLog` holds a per-instance `threading.Lock`, then rewrites the entire shared JSON audit log in place. Separate processes/instances can lose updates; interruption can corrupt the file. | Append-only run-scoped JSONL or transactional DB with idempotent event IDs; fsync/atomic projection if needed. | Multiprocess concurrent writes and kill-during-write tests. |
| PF-033 | **P1** | `core/orchestrator/storage.py:125-151,168-225` | LLM and input cache entries are written directly to final JSON paths without atomic replacement or interprocess synchronization. Partial reads are handled as misses, but concurrent writes and interruption can destroy cache entries and obscure provenance. | Atomic unique temp files and rename; store key, model, template version and fingerprint metadata with integrity checks. | Concurrent cache set/get and interrupted write tests. |
| PF-034 | **P1** | `core/orchestrator/checkpoint.py:30-59` | Stage checkpoint writes status, context, summary and feature status under one broad try/except that silently suppresses failures. `write_compact_summary(... summarize(text, max_chars=0))` deliberately uses no hard cap, allowing very large accumulated summaries. This also overlaps `run_status.py` ownership of `PROJECT-STATUS.md` noted in earlier batches. | Return per-write outcomes, log failures, establish one writer per artifact, enforce configured summary/context budgets. | Inject failures in each checkpoint write and large-artifact summary tests. |
| PF-035 | **P1** | `core/orchestrator/agent_execution.py:207-216`; `core/agent_readiness.py:108-109` | The agent readiness call is enclosed in an outer catch that prints `check skipped` and continues generation if readiness evaluation raises. This compounds the previously identified credential checker fail-open behavior. | Treat readiness errors as blocked or explicit operator override, with structured evidence. | Mock `verify_agent` exception and assert no LLM call is made. |

### Cross-module conclusions

- **Artifact contract is broken at a direct call site:** the registration call in `agent_execution.py` cannot match the signature in `artifact_store.py`. This is stronger evidence than a general concern about stale artifacts and should be fixed before relying on artifact provenance or dashboard registry completeness.
- **Verification is not intrinsically mandatory:** the compliance orchestrator tolerates skipped/failed-to-run verification and handler exceptions. Required gates must be enforced independently of the LLM or agent's own output.
- **One writer / immutable evidence remains incomplete:** audit log, caches, compliance reports and checkpoints are file-backed with overlapping or nontransactional writes. These paths explain plausible failure mechanisms, but no new smoke run was executed to establish which occurred in the historical run.
- **Positive implementation details:** the code distinguishes `needs_retry` for truncated output, has a bounded two-amendment HIL loop, builds semantic artifact producer/consumer maps, fingerprints delegated context, and provides scope-aware status vocabulary. These are useful foundations that need end-to-end enforcement.

### Coverage and remaining batches

**60 distinct retrieved modules of 3,026 tracked files** (including **412 Python files**) is not exhaustive. The complete 17-file orchestrator directory now has 16 substantive modules retrieved across batches, plus its trivial `__init__.py` not separately fetched. Next: `core/compliance_check.py`, `compliance_verifier.py`, `compliance_action_handler.py`, `context_engine.py`, `context_manager.py`, `context_policy.py`, `knowledge_compliance_checker.py`, then dashboard API mounting and frontend, tests, agent cards, config/schema, CI/deployment and generated evidence. Every remaining file requires inventory disposition; static findings must remain distinct from runtime-confirmed defects.

## Batch E — compliance, verification, context and knowledge governance (2026-09-28)

**GitHub-only baseline:** `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`. Retrieved and examined 12 files: `compliance_check.py` (1,445 lines), `compliance_verifier.py` (574), `compliance_action_handler.py` (295), `knowledge_compliance_checker.py` (512), `context_engine.py` (259), `context_manager.py` (163), `context_policy.py` (87), `orchestration_context.py` (72), `prompt_overlays.py` (108), `verification_runner.py` (134), `model_catalog.py` (328), `model_gate.py` (147). Five had been retrieved in earlier batches; **seven distinct new modules**. Total **67 distinct modules retrieved**. The selected methods below were examined in detail; full line-by-line certification and runtime execution remain outstanding.

### New deduplicated findings

| ID | Priority | Source | Confirmed evidence | Remediation and regression test |
|---|---|---|---|---|
| PF-036 | P0 | `core/compliance_check.py:700-721` | Function named `tests_pass` returns PASS when test directories exist, explicitly without running any tests. A checklist using this function can report passing tests when they fail. Separate `verification_runner` can run tests, but this compliance result is not a real test execution. | Rename to `test_files_exist` and mark as existence-only; require run-bound passing test results for any actual `tests_pass` gate. Test with an existing failing pytest suite. |
| PF-037 | P1 | `core/knowledge_compliance_checker.py:78-79,310-324` | `ComplianceResult.passed` is `critical_count == 0`, so HIGH and MEDIUM violations do not make knowledge compliance fail. The role-missing guideline calculation occurs **before** guidelines are loaded; its initial `guidelines_loaded` is empty, potentially marking all declared role layers as missing even if loaded later. | Define policy-driven severity threshold; compute `role_missing` after loading and map layers to guideline IDs. Test high violation and fully covered role layers. |
| PF-038 | P1 | `core/context_engine.py:120-142,174-218` | A higher-priority item is accepted even when adding its full tokens exceeds its category budget; `prepare_context` then returns the full item. The category's token accounting can exceed its max, undermining context limits. | Reserve space or evict lower-priority items before accepting; reject/compact any item that still cannot fit. Assert each category and total budget after assembly. |
| PF-039 | P1 | `core/compliance_verifier.py:95-105,246-295` | `VerificationReport.passed` uses `all(...)`, which is true for an empty `results` list. `verify_agent_work` has an early empty-results report path, so an empty verification set can be interpreted as passing by consumers using `.passed` alone. | Require at least one applicable executed check and explicit status `not_run`/`inapplicable`. Test empty checklist and verifier unavailable. |
| PF-040 | P1 | `core/compliance_action_handler.py:165-178` | After one retry, HIGH-severity violations with `auto_approve=True` return action `continue`, even though the violations persist. The parent orchestration code must enforce the separate `passed=False` flag; the action itself does not block. | Define policy for unresolved HIGH findings; only a separately authorized, recorded waiver may continue. Test exhausted retries with auto-approve on/off. |
| PF-041 | P1 | `core/compliance_check.py:305-315`; `core/compliance_action_handler.py:72-77`; `core/prompt_overlays.py:45-48` | Compliance reports, retry states and prompt overlays write JSON directly to destination files. Interrupted or concurrent writes can truncate state or lose updates. | Use atomic replacement plus interprocess locking/transactional state; verify concurrent writers and process-kill recovery. |
| PF-042 | P1 | `core/knowledge_compliance_checker.py:327-350` | Missing artifact paths are skipped and artifact read exceptions are only printed; neither necessarily creates a violation. If no artifact can be checked, `critical_count` remains zero, and the result's `passed` property is true. | Treat required-artifact absence and unreadable files as blocking evidence failures; test missing/unreadable artifacts. |

### Cross-module observations and existing finding refinements

- `core/compliance_check.py:258-302` now derives fallback checklists for agents missing explicit definitions. This is an improvement over a vacuous checklist; however, `core/orchestrator/compliance.py:68-72` independently converts a zero-check result to pass. The combined behavior needs a policy that distinguishes `not_applicable` from `not_executed`.
- `core/compliance_verifier.py:442-513` defaults missing individual LLM verifier checks to failed, a positive fail-closed behavior. PF-039 concerns **empty report aggregation**, not ordinary missing-check parsing.
- `core/context_manager.py:125-163` enforces an agent-specific assembled-context limit but does not include the complete eventual prompt, system instructions, tool schema or output reserve; this reinforces PF-019. `core/context_engine.py` uses a different budget mechanism; choose one effective token contract at the actual model-call boundary.
- `core/verification_runner.py:63-134` can execute npm/pytest where detected. PF-036 applies specifically to the separate `compliance_check.tests_pass` function, not to all verification in the repository.
- `core/orchestration_context.py` and `core/prompt_overlays.py` were inventoried and their execution paths sampled. Authentication and instruction precedence for operator-controlled overlays need tracing through the dashboard API and final prompt builder before classifying a security issue.

### Batch E verification plan

1. Run a failing pytest suite through `compliance_check.tests_pass` and the real `verification_runner`; assert their results cannot be conflated.
2. Construct empty LLM verification reports and absent knowledge artifacts; assert neither passes a mandatory gate.
3. Supply an oversized high-priority context item and assert the effective model-call budget is respected.
4. Inject a HIGH violation after the last retry with `auto_approve=True`; verify a recorded waiver is required.
5. Crash or race JSON report, overlay and retry-state writers; verify recovery and no lost updates.

**Next batch:** dashboard API route authorization and frontend data paths, including how overlays and compliance overrides are exposed. Then remaining core implementation, agent cards, configuration, tests, CI/deployment, and generated artifacts. This report is cumulative, not a claim of repository completion.


## Batch F — dashboard API authorization and frontend data paths (2026-09-28)

**Immutable baseline:** `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`. Four source files fetched in full and endpoint/function inventories examined: `dashboard/api/app.py` (1,041 lines, recheck from Batch C), `dashboard/server.py` (338 lines, new), `dashboard/static/index.html` (239 lines, new), and `core/licensing.py` (285 lines, new). **Three new distinct source files; cumulative 70.** Dashboard's 57 generated diagram/docs files and `dashboard/api/__init__.py` were inventoried but not individually content-reviewed. The legacy dashboard's reachability and use in production have not been established. All findings below are static source findings, not demonstrated attacks.

### New findings — deduplicated against PF-021–PF-028

| ID | Priority | Source | Verified code behavior and scope | Recommended fix | Regression verification |
|---|---|---|---|---|---|
| PF-043 | **P0 if legacy dashboard network-exposed; otherwise P1** | `dashboard/server.py:87-100,201-249,321-337` | Separate `ThreadingHTTPServer` has no authentication/authorization on `/api/run`, `/api/enhance`, `/api/intake`, and backlog mutation routes. Default bind is loopback `127.0.0.1`, but `--host` permits other interfaces; `_send` adds `Access-Control-Allow-Origin: *`. Exposure depends on actual deployment. | Deprecate this second mutation API in favor of FastAPI or enforce a verified principal, CSRF defenses, least privilege, and loopback-only binding by default. | Assert anonymous POSTs rejected in any nonlocal deployment; test host binding, CORS and parity with FastAPI permissions. |
| PF-044 | **P1** | `dashboard/server.py:251-257,193-197` | Static route passes arbitrary URL path suffix into `os.path.join(STATIC, rel)` and `open`, without `realpath`/`commonpath` containment. Traversal via URL path normalization or encoded separators is deployment/parser dependent, but no application-level containment exists. | Resolve paths and require containment within STATIC; reject absolute, `..`, symlinks, and unsupported extensions; serve via vetted static-file middleware. | Test raw and percent-encoded traversal, absolute paths and symlink escapes against the actual HTTP parser. |
| PF-045 | **P1** | `dashboard/server.py:45-51,109-140,264-291` | Project name from query/body is passed to `os.path.join(PRODUCTS, project)` and log paths with no validation in this server. A crafted project path may address files outside the intended products root; exact downstream read/write consequences depend on filesystem permissions and `run_pipeline.py` validation. | Reuse canonical `core/paths.py` project validation; enforce resolved path containment before reading, writing, or spawning. | Traversal and absolute-project tests for status and run endpoints; verify no file creation outside PRODUCTS. |
| PF-046 | **P1** | `dashboard/static/index.html:127-128,156-180,214-225` | Text fields are HTML-escaped for display, but `rows()` interpolates `project` and `i.id` unescaped into inline JavaScript `onclick` string literals. Apostrophes in project/ID can break out of quoted arguments; source trust and ability to supply crafted IDs must be checked before asserting exploitable XSS. | Eliminate inline handlers; render DOM nodes with `textContent`, bind listeners via `addEventListener`, and validate canonical IDs. | Render apostrophe-bearing project/ID values and verify no script execution; use CSP forbidding inline scripts. |
| PF-047 | **P1** | `dashboard/api/app.py:252-271` | Chunk-upload endpoint catches and discards any exception from `store.append_upload_chunk`, then returns `ok: true` with `received: len(chunk)`. Clients can believe a chunk was stored even when persistence failed, potentially corrupting subsequent uploads. | Return failure on append error, include server-verified sequence/checksum and durable acknowledgment; make completion verify all chunks. | Inject disk/full-store error; assert non-2xx response and failed completion; reorder/drop chunk tests. |
| PF-048 | **P1** | `dashboard/api/app.py:938-962` | Public `/metrics` route has no `Depends(auth)` and emits per-project names, token totals and USD cost. A network-reachable instance exposes operational metadata even when protected API endpoints require a token. | Restrict to internal network or metrics-specific authentication and sanitize project labels. | Anonymous scrape blocked on public interface; authorized Prometheus scrape succeeds. |
| PF-049 | **P2** | `dashboard/api/app.py:641-645`; `core/licensing.py:141-162` | Public GET `/api/v1/licensing/keys/verify?key=...` accepts a full license key in the URL, where query strings can enter browser history, reverse-proxy/access logs and monitoring; returns decoded license payload. This is a transport/observability exposure risk, not a claim that signatures are broken. | Accept keys in POST body or Authorization header, redact sensitive values from logs, and return only necessary verification fields. | Inspect access logs under verification calls; ensure full keys never appear in URL or logs. |

### Rechecked findings (no duplicate IDs)

- **PF-021** operator authorization remains source-confirmed: `operator_guard` in `dashboard/api/app.py:69-80` neither calls `auth` nor validates `x_roles` against an authenticated principal. Build-time removal of operator paths (`:700-735`) limits exposure on tenant builds but does not authenticate operator builds.
- **PF-022** tenant endpoints still use only shared `auth` (`:138-175`) and lack tenant-scoped principal authorization in the endpoint paths examined.
- **PF-023** public `/api/v1/events` (`:214-237`) streams global events and ignores the `project` query argument.
- **PF-028** multipart and base64 intake paths (`:296-327`) still read/decode full request content without a visible endpoint-level size limit.
- **Positive:** FastAPI's ordinary endpoints consistently declare `Depends(auth)` in the reviewed inventory; the static frontend escapes displayed backlog text with `esc()`. The build-role filter removes operator route prefixes from tenant builds; none of these safeguards eliminates the separately identified gaps.

### Batch F architectural crosswalk and scope

The repository exposes **two HTTP implementations**: `dashboard/api/app.py` (FastAPI, optional bearer-token gate) and `dashboard/server.py` (stdlib HTTP server, no authentication). `dashboard/static/index.html` calls legacy `/api/...` routes; this is not the same frontend contract as the FastAPI `/api/v1/...` surface. A single authoritative API contract and deployment policy are needed before tenant isolation or audit logging can be considered consistently enforced. The dashboard tree has **60 tracked entries**, including **57 generated HTML/PDF/drawio documentation assets**; generated assets remain pending visual/content sampling and classification. No HTTP server was launched and no runtime penetration testing was performed.

### Batch F recommended repair order

1. Determine which dashboard server is deployed; remove or lock down the legacy mutation endpoints before any non-loopback exposure.
2. Fix operator and tenant authentication (PF-021/PF-022), then protect SSE and metrics (PF-023/PF-048).
3. Enforce path containment on static files and project identifiers (PF-044/PF-045).
4. Replace inline JavaScript handlers and validate identifiers (PF-046).
5. Make upload acknowledgments durable and bind chunks to a verified upload session (PF-047).
6. Remove license keys from GET query strings (PF-049).

**Batch G completed:** see appended findings and updated scope below. Next: Batch H — remaining core modules and active call-path traceability.


## Scope adjustment — 2026-09-28

**User instruction: exclude the legacy dashboard from future remediation scope because it will be replaced.** Batch F findings PF-043 through PF-047 concerning `dashboard/server.py` and `dashboard/static/index.html` are retained solely as historical audit evidence, explicitly **OUT OF SCOPE / DO NOT FIX** for the new dashboard. They remain in the numbered historical register for traceability and are **not counted as active remediation recommendations**. New dashboard security requirements still include verified FastAPI API findings PF-021–PF-023, PF-028, PF-048–PF-049. The new dashboard itself does not exist at this pinned commit and cannot yet be reviewed. Other findings touching the active API remain in scope.

## Batch G — core path boundaries, Git, run control, storage, archive and governance (2026-09-28)

**Baseline:** immutable GitHub commit `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`. **15 new distinct Python modules retrieved**, full source fetched and selected high-risk paths independently inspected: `paths.py`, `run_guard.py`, `stage_paths.py`, `project_store.py`, `project_archive.py`, `git_manager.py`, `forge_store.py`, `run_quality_gate.py`, `global_orchestrator.py`, `project_journal.py`, `adopt_project.py`, `change_registry.py`, `rerun_review.py`, `cross_project_learning.py`, `knowledge_registry.py`. **Cumulative distinct source files retrieved: 85** (67 through E, 3 through F, 15 in G). Source retrieval does not imply full line-by-line certification; no runtime tests were executed.

### New deduplicated findings (PF-050–PF-059)

| ID | Priority | Verified source | Evidence and consequence | Recommended fix and verification |
|---|---|---|---|---|
| PF-050 | **P0** | `core/git_manager.py:193-211,320-341`; `create_branch:152-169` | Both `create_project_branch` and `create_worktree` call `create_branch(..., create=True)`, but `create_branch` only accepts `branch_name, start_point`. Both paths raise `TypeError` before creating the intended branch/worktree; `safe_commit` catches and returns false on the main/master branch path. | Correct call signatures and clarify create-versus-checkout semantics. Unit-test branch creation, `safe_commit` from main, and worktree creation in a temporary Git repo. |
| PF-051 | **P0** | `core/project_archive.py:77-92,125-137`; `core/paths.py:75-83` | Archive constructs `src=join(PRODUCTS, project)` without validating `project` as a single safe component. A traversal or absolute path can select directories outside `products`; archive then moves the selected directory into `.archive`. Restore uses the same unvalidated project value. This is a dangerous API-reachable path via `dashboard/api/app.py:579-594` (ordinary shared-token auth only). | Enforce strict project-name grammar and `resolve()`/`is_relative_to(PRODUCTS)` before any move, plus source/target symlink restrictions; test `../`, absolute paths, symlinks, and valid names. |
| PF-052 | **P0** | `core/project_archive.py:125-137` | `purge_due` checks lexical `abspath` containment before `shutil.rmtree`, not resolved real paths. A symlinked archived path can escape the intended archive root; `ignore_errors=True` still removes registry records and claims purge success even if deletion fails. Actual symlink behavior depends on Python `rmtree` safeguards and the precise path shape; this is a containment/false-success flaw, **not a demonstrated arbitrary deletion exploit**. | Resolve and reject symlink archive roots; restrict deletion to registry-generated paths and verify removal before dropping records. |
| PF-053 | **P1** | `core/project_store.py:22-35,66-77` | `_lock` returns `None` after 50 retries (~5 s) or errors; `_mutate` then continues without ownership, enabling lost updates to `project.json`. Same concurrency pattern as PF-014 (`budget.py`) but different shared store. | Raise a lock-acquisition error; use transaction/SQLite or unique-temp atomic compare-and-swap; concurrent update regression test. |
| PF-054 | **P1** | `core/run_guard.py:81-125`; `core/lock_manager.py` (prior batch) | `ensure_single_run` defaults `force=True`; after timeout, it may terminate another run and unconditionally attempt `release_lock(project, info.holder)` even if the previous process is still alive or ownership has changed. Combined with previously recorded nonexclusive lock implementation, this risks overlapping or interrupted runs. | Default to non-destructive refusal, use process identity and fencing tokens, only release locks still owned by the observed run; race and graceful-shutdown tests. |
| PF-055 | **P1** | `core/run_quality_gate.py:37-70,91-99` | The repository quality gate only runs for `item`/`amend` modes; e2e mode explicitly skips it. Its `evaluate` runs `compileall` and `wired_audit`, not functional tests. This gate alone cannot establish end-to-end product correctness. | Define distinct repository wiring versus product verification gates, and require configured functional/integration/security checks for applicable e2e scopes. |
| PF-056 | **P1** | `core/global_orchestrator.py:106-171,215-261` | Project registration loads, modifies, then atomically writes the shared index without transaction/lock; simultaneous registrations can lose index entries. Start transitions and dequeue are separate operations, so failures can leave queue, lock and state inconsistent. | Transactional project registry and idempotent start transition with compensation; concurrent register and injected failure tests. |
| PF-057 | **P1** | `core/adopt_project.py:98-135` | Adoption catches and silently ignores individual copy failures, yet writes `project.json` and reports success without listing missing files; it also accepts an unchecked `name` for destination path construction. | Validate destination name and containment; produce copy manifest, fail or explicitly report partial adoption; permission-error and traversal tests. |
| PF-058 | **P1** | `core/knowledge_registry.py:38-53,75-115` | Registry writes JSON directly to the target and its add/modify/remove operations use unprotected read-modify-write, allowing partial files or lost concurrent knowledge updates. | Transactional storage, unique temporary files, locking and revision checks; simultaneous modify tests. |
| PF-059 | **P1** | `core/cross_project_learning.py:127-155` | `build_learning_index` marks a project `completed` whenever *any* insights are extracted, regardless of actual run status or gate evidence. Cross-project reports can misrepresent unfinished projects as complete. | Read run-bound authoritative status and verification evidence; test projects with insights but failed/incomplete runs. |

### Cross-module implications and positive observations

- **Path security is not centralized:** `paths.py` deliberately provides convenient absolute path constructors, but `products(project)` and `project_dir(project)` are not validators. All externally supplied project identifiers must be validated at the API boundary and at destructive operations. The legacy dashboard is excluded from remediation; active FastAPI archive endpoints remain relevant.
- **Project data ownership remains split:** `project_store`, `global_orchestrator` index, `forge_store`, `project_journal`, `knowledge_registry`, and `rerun_review` each write JSON with different locking/atomicity conventions. The repo architecture's “one writer per file” principle should be checked against concrete ownership and tests.
- **Git operations use argument arrays, not shell interpolation** (`git_manager._run_git`), a positive command-injection safeguard. However, branch/worktree creation currently has a verified call-signature mismatch.
- **Scope discipline:** Batch G did not include legacy dashboard remediation. The new dashboard should inherit authenticated principal/tenant authorization, project path validation, protected event streams, and run-bound evidence rather than reuse the legacy implementation.

### Remaining inventory and next batch

The pinned tree has **3,026 tracked files**, including **412 Python files**. **85 distinct source modules/files retrieved through Batch G**, plus selected architecture/config documents previously read. The balance includes unreviewed Python modules, agents/skills, configuration, tests, docs, generated JSON/JSONL, and binary artifacts; these need file-level disposition and appropriate audit method, not an unsupported assertion of 3,026 manual line-by-line reviews.

**Batch H:** remaining active core execution paths, source-backed project validation and permission call sites, job/queue/lock wiring, and test coverage. Later batches: agent definitions and skills, config/schema, tests, CI/deployment, documentation and generated evidence, final reconciliation.


## Batch H — active execution wiring, lifecycle state, pipeline plans, DLQ and verification (2026-09-28)

**Baseline:** pinned commit `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`. **15 files retrieved in this batch**, including **10 newly retrieved distinct modules** and five rechecks (`job_manager.py`, `queue_manager.py`, `lock_manager.py`, `tenancy.py`, `orchestrator/stage_runner.py`). New distinct modules: `state_machine.py`, `dead_letter_queue.py`, `pipeline_store.py`, `pipeline_tailoring.py`, `pipeline_capabilities.py`, `pipeline_templates.py`, `pipeline_telemetry.py`, `nfr_runner.py`, `orchestrator/agent_runner.py`, `pipeline_executor.py`. **Cumulative distinct source files retrieved: 95**. Full source retrieved, targeted high-risk methods inspected; no runtime tests performed.

### New deduplicated findings (PF-060–PF-069)

| ID | Priority | Source | Evidence and consequence | Recommended fix and verification |
|---|---|---|---|---|
| PF-060 | **P0** | `core/pipeline_executor.py:3235–3268` [source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/pipeline_executor.py#L3235-L3268) | After setting COMPLETION and persisting the final checkpoint, execute_pipeline calls gate_if_item_run but ignores returned passed=False and still returns phase==COMPLETION. A failed repository audit can leave a successful run. | Evaluate the gate before marking completion; on failure set FAILED and persist failed evidence; test injected nonzero compileall/wired_audit. |
| PF-061 | **P0** | `core/pipeline_executor.py:2858–2877` [source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/pipeline_executor.py#L2858-L2877) | The mandatory run guard only checks that some project lock exists, not whether holder/run_id belongs to this process/run; any lock-check exception is logged and execution continues. PIPELINE_ALLOW_UNGUARDED can bypass the guard by configuration. | Require a verified current-run fencing token and fail closed on lock-read errors; test another process lock, corrupt lock JSON, and override restrictions. |
| PF-062 | **P1** | `core/state_machine.py:138–155` [source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/state_machine.py#L138-L155) | _save_state deletes an existing state file before renaming the .tmp file, creating a missing-state crash window; transitions read then write without serialization and share a fixed temp name. | Use unique temp plus os.replace under per-project transactional lock; fault-injection and parallel-transition tests. |
| PF-063 | **P1** | `core/dead_letter_queue.py:45–76` [source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/dead_letter_queue.py#L45-L76) | _save_items writes directly to dead-letter-queue.json without mkdir/atomic replace or lock; add_item generates IDs from len(self.items)+1, which can collide after clear_resolved or across processes. | Create parent, transactional/atomic append and UUID or monotonic IDs; test initial missing dir, cleanup/re-add and concurrent writers. |
| PF-064 | **P1** | `core/pipeline_store.py:52–83` [source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/pipeline_store.py#L52-L83) | sync returns an in-memory projection even when its write fails, silently swallowing the exception. The caller can believe derived pipeline.json was refreshed while stale disk state remains. | Return persisted/revision evidence or raise on failed sync; test read-only target and concurrent sync. |
| PF-065 | **P1** | `core/pipeline_tailoring.py:132–165` [source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/pipeline_tailoring.py#L132-L165) | apply_plan removes any stage named in disabled_optional without checking that it is actually optional, then silently removes dependencies referencing removed stages. Crafted/stale plan can remove required gates or make downstream stages ready too early. | Validate disabled IDs against canonical optional stages, reject removal of required dependencies unless explicit approved rewiring, and schema-validate plans; regression tests. |
| PF-066 | **P1** | `core/pipeline_templates.py:62–70` [source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/pipeline_templates.py#L62-L70) | validate rejects every stage whose depends_on is empty, including legitimate root stages; to_pipeline_def accepts template stage maps without enforcing validate, permitting invalid DAGs downstream. | Allow empty dependencies for root stages and require template schema + graph validation before applying; root-stage and missing-dependency tests. |
| PF-067 | **P2** | `core/orchestrator/agent_runner.py:148–212` [source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/orchestrator/agent_runner.py#L148-L212) | When strict and recovery tool loops retry, acc accumulates token/cost across attempts but tool_calls, tool_iterations and tool_writes are overwritten with the last attempt stats, understating aggregate tool activity. | Accumulate per-attempt tool counters and ledger attempt IDs; test strict and recovery retries. |
| PF-068 | **P1** | `core/nfr_runner.py:48–75` [source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/nfr_runner.py#L48-L75) | Security and CVE checks only append scans for installed tools and eligible project types; missing scanners can produce [] without a required-check failure. run_for_mode also returns [] for unsupported modes. Downstream policy must not equate empty results with pass. | Represent NOT_RUN/SKIPPED explicitly and require configured minimum scanners for relevant release gates; test empty toolchain and unsupported mode. |
| PF-069 | **P1** | `core/pipeline_executor.py:3150–3191` [source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/pipeline_executor.py#L3150-L3191) | Selective scope completion checks only IDs present in DAG: a nonempty only_stages list of unknown IDs makes all(empty) true and failed count zero, allowing false COMPLETION. | Reject unknown selected stage IDs before execution and require at least one matched stage; test unknown-only and mixed IDs. |

### Reconciled cross-module findings and strengths

- **PF-024/PF-054 strengthened:** `pipeline_executor.execute_pipeline` uses the file lock only as an existence preflight, whereas `run_guard.ensure_single_run` may forcefully release locks. These are separate from the new PF-061 missing current-run ownership check. `job_manager.claim` positively uses SQLite `BEGIN IMMEDIATE`, but project-keyed jobs (PF-018) still lack immutable attempt history.
- **PF-055 strengthened:** `run_quality_gate` runs only for item/amend and only checks repository compile/wiring. PF-060 is a separate bug: even for those scopes, a failed gate result is ignored by the final execution path.
- **PF-002 strengthened:** invalid optional-stage removal in `pipeline_tailoring` can silently strip dependency edges, compounding DAG missing-dependency acceptance.
- **Positive controls:** native `AgentRunnerMixin.execute_agent_tool` checks agent spec tool names before registry execution; `job_manager.claim` has a SQLite write transaction; NFR runner subprocess commands are passed as argument arrays without `shell=True`. Text-protocol tool-loop authorization (PF-004) remains a separate path requiring enforcement.
- **Scope:** legacy dashboard remains excluded from future review and active remediation. Active FastAPI backend and replacement-dashboard requirements remain in scope.

### Next batch I and audit completion criteria

Next: agent/skill cards, contract and tool permissions, tests for pipeline executor/state-machine/DLQ and a cross-module source-to-test coverage map. Later batches: remaining core modules, configuration and schemas, CI/deployment, docs, generated evidence and binary/file-level disposition. The 3,026 tracked paths are inventoried, **not** all reviewed; no runtime tests have been executed.


## Batch I — agent/skill contracts and tests (historical reconciliation note)

A previous audit turn reported **27 additional distinct files retrieved (95 → 122)** and **10 findings PF-070–PF-079**, covering agent/skill contracts, permissions, and source-to-test mapping. The detailed Batch I report was not present in the mounted cumulative artifact or Library version available in this session. Its **IDs and counts are preserved as historical reported progress, but the ten detailed finding texts are not reconstructed or represented as independently reverified here**. Relevant Batch I source files were rechecked in the immediately preceding turn, including `core/agent_spec.py`, `core/agent_card_loader.py`, `core/agent_rules.py`, `core/skill_contracts.py`, `core/skills_registry.py`, `core/agent_runtime.py`, `core/agent_requirements.py`, `core/agent_tool_loop.py`, selected `.opencode/agent` cards and pipeline tests. The next reconciliation pass should recover the original detailed Batch I artifact or independently recreate its findings from pinned source, without renumbering or guessing.

## Batch J — agent runtime persistence, hierarchy, schema and security-test coverage (2026-09-28)

**Baseline:** pinned `develop` commit `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`. **16 files retrieved in full:** 10 core modules (`agent_hierarchy`, `agent_ledger`, `agent_memory`, `agent_messenger`, `agent_migrator`, `agent_model_override`, `agent_structure`, `agent_summaries`, `schema_validator`, `tool_cache`), `test-framework/tests/pipeline/test_security.py`, `test_invocation_audit.py`, `test-framework/core/agent_integration.py`, `config/agent-hierarchy.json`, and two active agent cards (`production-deploy.md`, `security-audit.md`). Targeted high-risk method re-fetches used to verify the source lines below. **Up to 138 cumulative distinct files** using the historical Batch I count of 122; exact deduplication with the missing detailed Batch I inventory remains provisional. **89 cumulative finding IDs**, of which PF-070–PF-079 need detailed artifact recovery. No runtime tests executed.

### New deduplicated findings PF-080–PF-089

| ID | Priority | Source | Evidence and consequence | Fix / verification |
|---|---|---|---|---|
| PF-080 | **P1** | [`core/agent_ledger.py:121–167,299–304`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/agent_ledger.py#L121) | Work IDs derive from current list length; whole shared ledger is rewritten directly without cross-process serialization. Parallel recorders can collide/lose work and a crash can truncate the audit ledger. | Use database sequence/UUID, transaction and append-only run-bound event log; multi-process and fault-injection tests. |
| PF-081 | **P1** | [`core/agent_memory.py:247–257,562–600`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/agent_memory.py#L247) | Memory entry writes truncate the live JSON file. validate_entry and unvalidate_entry change in-memory validation flags, ignore _save_entry False and return True; callers may treat unpersisted validation as durable. | Atomic unique-temp writes; propagate save failures and roll back in-memory flags; disk-failure regression. |
| PF-082 | **P1** | [`core/agent_messenger.py:73–111,236–248`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/agent_messenger.py#L73) | Messages and queue changes are saved only after every tenth send; clear_queue does not persist immediately. A process crash loses up to nine sends and acknowledgements/clears; save failures are logged without sender feedback. | Durable enqueue/ack before success, SQLite or append-only journal; crash/restart and save-failure tests. |
| PF-083 | **P1** | [`core/schema_validator.py:179–262`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/schema_validator.py#L179) | Agent markdown parser recognizes headings but never appends body lines to section_content, so parsed sections are absent/empty and schema validation can incorrectly reject real agent cards or fail to validate their contents. | Append body lines and preserve headings; test known valid card and deliberately malformed section content. |
| PF-084 | **P1** | [`core/tool_cache.py:68–104,111–172`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/tool_cache.py#L68) | Tool-result cache key uses only tool name and arguments, omitting project/workspace, principal and provider context. If shared across projects, same calls can return another project’s cached data; disk writes are also non-atomic. | Scope keys by tenant/project/workspace and authorization context; cache only explicitly safe read tools; isolation and crash tests. |
| PF-085 | **P1** | [`core/agent_model_override.py:21–37,49–68`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/agent_model_override.py#L21) | Concurrent set/clear operations read then overwrite a shared project JSON file with fixed .tmp name and no lock. One agent override can silently erase another or collide during replacement. | Unique temp plus project lock/version CAS or transactional DB; parallel set/clear tests. |
| PF-086 | **P1** | [`core/agent_migrator.py:307–320`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/agent_migrator.py#L307) | Migration backup writes to a fixed historical .backups directory without creating the parent and only takes a backup if missing. On a fresh checkout, copy2 may fail; later migrations reuse an outdated backup, then overwrite live card in place. | Create per-run timestamped backup directory, verify backup and use atomic replacement; fresh checkout and repeated migration tests. |
| PF-087 | **P1** | [`test-framework/core/agent_integration.py:20–57`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/test-framework/core/agent_integration.py#L20) | RCCA auto-update interpolates agent_name directly into agent file path and appends generated text in place. If agent_name is externally supplied, ../ can select arbitrary existing Markdown outside agents_path; concurrent updates can interleave. | Validate canonical agent IDs against registry and resolved directory; atomic/serialized updates; traversal and concurrency tests. |
| PF-088 | **P1** | [`core/agent_hierarchy.py:33–59`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/agent_hierarchy.py#L33) | Hierarchy config and pipeline parse errors are silently swallowed, producing a partial/empty cached hierarchy; parent_of/root_of then return results without indicating missing policy. | Validate hierarchy at startup, distinguish absent optional configuration from malformed required config, and test corrupt/missing files. |
| PF-089 | **P2** | [`core/agent_messenger.py:125–145`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/agent_messenger.py#L125) | Broadcast recipients are inferred only from existing queues and message history, not all registered agents. A newly registered agent with no prior messages may miss broadcast events. | Use authoritative agent registry/active subscriptions and test cold-start broadcast. |

### Security regression and source-to-test gap

`test-framework/tests/pipeline/test_security.py` covers STRIDE threat categories, compliance configuration and security-issue tracker CRUD/priority. It does **not** cover active FastAPI cross-tenant authorization, tool-loop disallowed execution, fail-open HIL/readiness, mandatory test-not-run blocking, or release-gate evidence freshness. `test_invocation_audit.py` checks static module wiring, not authorization or concurrent persistence. The existing tests are useful but cannot be taken as runtime verification of PF-001, PF-003, PF-004, PF-021–PF-023, PF-030, PF-036, PF-060–PF-061 or Batch J persistence defects.

**Suggested regression suite:** forbidden tool-call via text protocol; shared-token cross-tenant request; unknown-role operator request; missing/failed scanner; crash during memory/ledger save; multi-process override and queue writes; malicious agent identifier; invalid agent-card body. These are test designs, **not executed test results**.

**Positive controls:** memory uses UUID-derived IDs and an in-process RLock; schema_validator uses Draft7Validator and fails unknown schema names; model overrides use os.replace (but shared temp and no interprocess lock); the security suite has meaningful issue-tracker and threat-model tests.

### Next Batch K and completion criteria

Next: active CI/deployment scripts and GitHub workflows, dependency/secret-scanning configuration, and a reproducible test-execution plan. Also reconcile the missing detailed Batch I report before treating PF-070–PF-079 as source-verified in this merged artifact. The 3,026-file tree is inventoried, **not** exhaustively audited. Generated and binary files still require file-level disposition. Legacy dashboard findings PF-043–PF-047 remain historical and excluded from active remediation.


## Batch K — CI/deployment wiring, scanner execution and release gates (2026-09-28)

**Scope:** 14 newly retrieved files at the pinned commit, including the repository’s sole GitHub Actions workflow (`.github/workflows/structure.yml`), security scanner implementations, security tool configuration, release manifest script, structure audit and setup tooling. Selected methods re-read with pinned source ranges. No CI jobs, scanners or runtime tests were executed in this audit environment. Findings PF-090–PF-098 are static source findings.

### New findings (deduplicated against PF-001–PF-089)

| ID | Priority | Pinned source | Verified behavior and risk | Recommended fix / regression |
|---|---|---|---|---|
| PF-090 | **P0** | [`.github/workflows/structure.yml:29-33`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/.github/workflows/structure.yml#L29) | Pytest step has continue-on-error: true, allowing failed test suite to leave structure CI green. Comment cites five PDF tests, but the exemption covers all tests. | Make required tests blocking; isolate platform-dependent PDF tests in separately reported optional job; inject failing unit test in CI. |
| PF-091 | **P0** | [`security/core/dependency_scanner.py:97-146`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/security/core/dependency_scanner.py#L97) | Trivy missing executable, timeout and all exceptions are swallowed and return empty findings; scanner API returns tools_used even if execution failed. The same pattern occurs in Safety/npm and SAST/secret scanners. | Use structured scanner outcomes {status, exit_code, findings, stderr, duration}; fail mandatory gates on skipped/error; simulate missing binaries and timeouts. |
| PF-092 | **P0** | [`security/core/dast_scanner.py:80-115`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/security/core/dast_scanner.py#L80) | ZAP subprocess output is not parsed into findings; even a successful ZAP scan returns [] and failed/missing scans also return []. | Mount/persist ZAP JSON report, parse alert findings, capture execution state, and fail on mandatory scanner error; fixture with known alert. |
| PF-093 | **P1** | [`.github/workflows/structure.yml:16-33`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/.github/workflows/structure.yml#L16) | The sole GitHub workflow in the pinned recursive tree does not invoke dependency, SAST, secret, DAST scans, release-manifest check, or coverage threshold. Existing scanner modules and security config do not imply CI enforcement. | Add pinned-action security jobs and blocking policy; verify scanners actually execute, publish evidence and block on configured severity. |
| PF-094 | **P1** | [`scripts/dev/build_release.py:28-65`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/scripts/dev/build_release.py#L28) | Build-role verification checks only whether tenant app routes start with five hardcoded OPERATOR_MARKERS. Operator endpoints outside the marker list can be missed; it does not establish per-route authorization. | Use authoritative route role metadata and explicit deny-by-default tenant manifest, plus authenticated/unauthorized integration tests. |
| PF-095 | **P1** | [`security/core/secret_detector.py:43-78`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/security/core/secret_detector.py#L43) | SecretDetector.scan records requested tools as tools_used but silently ignores unknown names and cannot distinguish skipped/failed scanner from zero secrets. The TruffleHog and Gitleaks runners suppress exceptions. | Reject unknown scanner names; expose per-tool success/error; require actual execution before clean verdict. |
| PF-096 | **P1** | [`scripts/dev/wired_audit.py:205-236`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/scripts/dev/wired_audit.py#L205) | diff_audit automatically creates a baseline and passes when manifest is absent; a corrupt manifest also returns success. This bypasses intended new-file contract on missing/corrupt baseline. | Require reviewed versioned baseline in CI and fail on absent/corrupt baseline; regression tests for missing and malformed manifest. |
| PF-097 | **P1** | [`security/core/dependency_scanner.py:148-254`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/security/core/dependency_scanner.py#L148) | Dependency scanner Safety only searches requirements*.txt and npm audit only project-root package.json; Python pyproject/lock and nested JS workspaces may not be covered. | Discover pyproject/lockfiles and nested workspace manifests, record manifest inventory and scanner coverage, test each supported dependency format. |
| PF-098 | **P2** | [`scripts/dev/audit_hardcoding.py:1-44`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/scripts/dev/audit_hardcoding.py#L1) | Hardcoding script is a heuristic reporter only: scans selected Python roots and excludes files by hints, prints first 25 matches and sets no failure threshold; it is not a secret scanner or enforceable CI gate. | Label as advisory, separately enforce real secret/SAST checks, and add machine-readable output/thresholds if promoted to a gate. |

### Cross-cutting remediation and test plan

**Release evidence contract:** record `scanner`, exact executable/version, target manifest/path, start/end, status (`passed`, `findings`, `failed`, `skipped`), exit code, stdout/stderr artifact and run ID. A mandatory tool not installed, timed out, or unparseable must block a release instead of yielding a clean report. Add negative fixtures for missing tools, invalid JSON, nonzero return, ZAP alerts, dependency advisories and seeded secrets.

**CI split:** blocking compile/structure and unit/integration tests; separate platform-dependent PDF suite with explicit required/optional policy; blocking SAST, dependency, secret checks; scoped DAST only against a controlled staging environment; role-manifest authorization tests; artifact retention and immutable run provenance. Avoid silently treating security scanners merely present in source as executed.

**Batch I reconciliation:** PF-070–PF-079 remain historical identifiers whose detailed evidence was not in the recovered report; they are not counted as independently reverified by Batch K. Batch J details PF-080–PF-089 remain preserved.

**Legacy dashboard:** historical PF-043–PF-047 excluded from active remediation as requested. Active FastAPI backend and future dashboard authorization remain in scope.

**Next Batch L:** active deployment entrypoints and environment/config security, security scan integration call sites, GitHub CI dependency bootstrapping, source-to-test mapping and Batch I evidence recovery. Repository-wide 3,026-file disposition still pending.


## Batch L — active artifact/billing/audit/budget support and regression-test disposition (2026-09-28)

**Baseline:** pinned `develop` commit `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`. This batch reviewed 15 active core modules plus the dedicated budget regression script and pytest configuration. Legacy dashboard files were not reviewed. No runtime tests were executed; all findings below are **static source findings** unless explicitly stated otherwise.

### New deduplicated findings PF-099–PF-105

| ID | Priority | Source | Evidence and consequence | Recommended fix | Verification |
|---|---|---|---|---|---|
| PF-099 | **P0** | `core/billing.py:24-34` | `BILLING_PROVIDER` defaults to `null`, and the null provider returns `paid=True` immediately. If a production deployment omits the environment variable, checkout can grant a paid entitlement/license without payment. The module describes this as dev/self-host behavior, but there is no production-mode fail-closed guard in this function. | Require an explicit non-null billing mode for production, fail closed when unset, and separate development checkout from production entitlement issuance. | Production-config test with missing `BILLING_PROVIDER`; assert checkout cannot provision a paid tier.
| PF-100 | **P1** | `core/artifact_registry.py:103-135` | HTTP artifact publishing builds a `curl -u user:password` argument containing the password obtained from the environment. The password is therefore passed as a process argument, potentially exposing it through process inspection/logging. External command failures are converted into a result object rather than raised, so callers must explicitly enforce `ok=False`. | Use a credential mechanism that does not put secrets in argv; make publish failure mandatory at release gates. | Process-argv secret-leak regression and failed-publish gate test.
| PF-101 | **P1** | `core/audit_trail.py:85-115` | Audit entries use `AUD-{len(entries)+1}` IDs and rewrite the entire JSON file without locking or atomic replacement. Concurrent writers can collide/lost-update, while a crash during `json.dump` can leave a truncated audit trail. | Append/transactional event storage with unique IDs, locking/atomic commit and run-bound provenance. | Parallel writers plus injected write failure; verify no duplicate IDs and complete history.
| PF-102 | **P1** | `core/budget_protection.py:151-170,216-265` | Budget load/save exceptions are swallowed. More importantly, `request_tokens` returns `True` when no budget exists, explicitly allowing untracked consumption; `commit_tokens` truncates an over-budget commit rather than surfacing a hard accounting failure. This weakens the stated budget-enforcement contract. | Make missing budgets configurable but fail closed for governed scopes; propagate persistence errors; reject or explicitly record over-limit commits rather than silently truncating. | Missing-budget, persistence-failure and over-limit accounting tests.
| PF-103 | **P1** | `core/budget_allocator.py:107-128,167-202` | Allocation load/save exceptions are swallowed and allocation mutations are persisted through the shared JSON budget store with no additional cross-process ownership/fencing at this layer. A failed save can leave in-memory allocation different from durable state while callers receive no failure signal. | Propagate persistence status, use the store's transactional result, and add concurrent allocation/reallocation tests. | Inject save failure and run concurrent `record_usage`/`reallocate` operations.
| PF-104 | **P1** | `core/artifact_registry.py:143-160` | `get_registry` trusts `project.json` to select an external artifact backend and command configuration. The custom command path supports arbitrary configured executables/arguments. This is acceptable only for trusted project configuration; if project configuration can be influenced by an untrusted project/adoption path, artifact publishing becomes a command-execution boundary. | Validate/allow-list artifact backends and executable commands; separate trusted operator configuration from project-controlled metadata. | Adopt untrusted project containing artifact registry configuration and assert no arbitrary command execution.
| PF-105 | **P1** | `tests/test_budget_protection.py` + `pyproject.toml:[tool.pytest.ini_options]` | The budget protection regression suite exists under top-level `tests/`, but pytest `testpaths` is only `test-framework`. Therefore this file is not collected by the standard pytest command used by CI. It is a standalone manual runner ending in `sys.exit`, so its claimed budget coverage is not part of the normal automated gate. | Move/adapt the tests under `test-framework`, or expand `testpaths` deliberately; convert them to pytest tests and ensure CI executes them. | `pytest --collect-only` must include the budget suite; CI must fail if these tests fail. |

### Batch L evidence and disposition

- **Static review:** completed for the files listed above at the immutable commit.
- **Runtime verification:** not performed. The prior cumulative report's limitation therefore remains: source findings are not runtime-confirmed defects.
- **Regression coverage:** the repository does contain a substantial budget test script, but PF-105 shows that it is outside the configured pytest collection root.
- **Scope:** legacy `dashboard/server.py` and `dashboard/static/index.html` remain excluded. Active FastAPI backend, core runtime, configuration, tests and future-dashboard contracts remain in scope.

### Updated cumulative status

Historical progress is now reconciled as **Batch L**, with **PF-001–PF-105** as the cumulative finding ID range. PF-043–PF-047 remain historical/out-of-scope legacy-dashboard findings. PF-070–PF-079 remain historical Batch-I IDs whose detailed artifact was not recovered; they must not be treated as independently reverified. The 3,026 tracked paths remain inventoried rather than fully reviewed; no complete-coverage claim is made.


## Batch M — feature governance, integration recommendations and intake integrity (2026-09-28)

**Baseline:** immutable `develop` commit `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`. GitHub connector retrieval: `core/feature_flags.py`, `core/intake_channels.py` (recheck), `core/integration_advisor.py`, `config/intake-channels.json`, `config/agent-requirements.json` (recheck), `config/agent-hierarchy.json` (recheck), `core/prompt_overlays.py` (recheck), `core/orchestration_context.py` (recheck), `core/model_gate.py` (recheck), and selected existing intake/skill modules (rechecks). Four new distinct files conservatively counted: feature flags, integration advisor, intake channels configuration, and the integration recommendation path's source module (provisional; verify against missing Batch I inventory). No legacy dashboard reviewed. No runtime tests executed. Absent guessed paths and absent test filenames are **not** evidence that equivalent tests do not exist.

### New deduplicated static findings PF-106–PF-110

| ID | Priority | Pinned source and lines | Source-backed finding | Recommended remediation / test |
|---|---|---|---|---|
| PF-106 | P1 | [`core/feature_flags.py:44-72`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/feature_flags.py#L44-L72); [`core/integration_advisor.py:285-289`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/integration_advisor.py#L285-L289) | The resolver accepts project flags and recommendations before environment/defaults, including `business_skills` and `service_catalog` (nominally HIL-confirmed); `apply_recommendation` commits *all* recommended flags without filtering user-facing ones. Consequently the feature resolver alone does not enforce the documented consent boundary. Caller-level HIL enforcement remains to be traced. | Require a signed/recorded owner decision for user-facing flags at the final execution boundary, not only UI; test recommendation-only and auto-mode cases. |
| PF-107 | P1 | [`core/intake_channels.py:119-132`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/intake_channels.py#L119-L132); [`config/intake-channels.json`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/config/intake-channels.json) | `channel_dir` directly joins the supplied `target_project` under the intake root for existing projects; there is no canonical path containment check in this function. If upstream accepts an untrusted project name containing `../` or an absolute path, writes can escape the intended intake directory. The configured channel paths are likewise trusted without validation. | Canonicalize and constrain both configured channel paths and target-project slug to an allowlisted root; add traversal tests through every external intake adapter. |
| PF-108 | P1 | [`core/intake_channels.py:134-191`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/intake_channels.py#L134-L191) | `_next_id` scans existing JSON indexes to compute `IN-{max+1}`, and `add_item` then appends JSONL and rewrites the index without a transaction/lock. Concurrent submissions can receive the same ID and overwrite index records; JSONL/index can diverge on crash. This extends the existing general file-state concurrency concern to the intake identity contract. | Atomic sequence or UUID/DB identity, transactionally coordinated event and index updates; concurrent-ingest and injected-failure tests. |
| PF-109 | P1 | [`core/intake_channels.py:272-276`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/intake_channels.py#L272-L276) | Despite its docstring, `close_verified` simply calls `update_item(... status="closed")`; it does not independently verify that `backlog_ref` exists or that implementation/verification passed. This is a missing local invariant, subject to further caller tracing. | Resolve the linked backlog record and verified gate evidence inside the close transaction; negative tests for absent, unverified and mismatched backlog IDs. |
| PF-110 | P2 | [`core/feature_flags.py:44-72`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/feature_flags.py#L44-L72) | Project configuration and persisted choice values are coerced with `bool(value)`; strings such as `"false"` are truthy, while malformed JSON is silently ignored in helper loaders. Invalid flag types can therefore activate integrations or fall back without a configuration error. | Validate typed booleans and known flag names at load time; fail closed for user-facing decisions and test malformed files/string booleans. |

### Batch M disposition and carry-forward

- New-file count **provisional** because Batch I exact inventory is still missing; the rechecked paths are not counted twice. The conservative cumulative retrieved-file figure is **172** (previous 168 + four provisionally distinct). Do not treat this as exhaustive line review.
- `core/orchestration_context.py` was rechecked: coordinator escalation currently checks `AgentRunner` import availability rather than invoking an LLM; further runtime integration tracing remains open. No duplicate ID was created for this previously inventoried module.
- `config/agent-requirements.json` and `config/agent-hierarchy.json` were rechecked for model capability and hierarchy contract context. Their presence does not establish runtime enforcement.
- **Static review only.** No local checkout, executable tests, security exploit demonstration, or CI runs performed. All 3,026 tracked files remain subject to review or justified exclusion.
- **Next Batch N:** trace final intake adapters and `close_verified` callers, consent enforcement in execution, active FastAPI authentication/validation and tests; continue CI/deployment and file-level disposition.


## Batch N — active intake adapter/caller trace and integration consent (2026-09-28)

**Baseline:** pinned `develop` commit `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`. GitHub connector fetched/rechecked `core/intake.py`, `core/intake_adapters.py`, `core/intake_channels.py`, `core/intake_api.py` (explicitly deprecated, reference only), `core/intake_files.py`, `core/conversation_models.py`, `core/integration_advisor.py`, `core/feature_flags.py`, `core/pipeline_executor.py`, `core/intent_router.py`, `core/orchestrator/stage_runner.py`, `dashboard/api/app.py`, `core/run_entry.py`, and `core/backlog.py`. All are rechecks against earlier batch inventories; **zero newly distinct files conservatively counted**. The legacy dashboard was not reviewed. No executable/runtime tests were run.

### New deduplicated static findings PF-111–PF-116

| ID | Priority | Pinned source | Evidence / scope | Remediation and regression test |
|---|---|---|---|---|
| PF-111 | P1 | [`core/pipeline_executor.py:1684-1707`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/pipeline_executor.py#L1684); [`core/integration_advisor.py:275-289`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/integration_advisor.py#L275) | Caller trace confirms PF-106: `_recommend_integrations` defaults `PIPELINE_ASK_INTEGRATIONS=0` and automatically persists every recommendation, including user-facing `business_skills` and `service_catalog`, before its HIL branch. This is a confirmed source-level consent bypass in the default pipeline path; not a runtime exploit demonstration. | Default to internal-only for noninteractive runs; require explicit recorded approval for product-shaping packs, validated at execution; test default and prompt-enabled paths. |
| PF-112 | P1 | [`core/intake.py:42-48`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/intake.py#L42); [`dashboard/api/app.py:240-249`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/dashboard/api/app.py#L240) | Active authenticated FastAPI intake forwards caller-controlled `source` to `ingest`; `_archive_raw` joins it directly under `products/inbox` and writes JSON without normalization or canonical containment. An authorized sender can supply traversal-like source strings and target an unintended writable directory. This is separate from PF-107 target-project path risk. | Restrict source to registered adapter IDs/slug grammar and resolved inbox containment; test `../`, absolute paths, encoded separators and allowed sources through API. |
| PF-113 | P1 | [`dashboard/api/app.py:252-269`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/dashboard/api/app.py#L252); [`core/conversation_models.py:558-588`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/conversation_models.py#L558) | Active `/api/v1/intake/upload-chunk` invokes `ConversationStore.append_upload_chunk`, but the pinned class defines `store_chunk`, not `append_upload_chunk`. Its inner `except Exception: pass` then returns `ok=True` and the received length, reporting acceptance without persisting the chunk. This is a static call-contract mismatch; runtime HTTP test pending. | Wire the endpoint to `store_chunk` with validated chunk index/total and propagate errors; test upload, assembly and failure status. |
| PF-114 | P2 | [`core/intake.py:83-115`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/intake.py#L83); [`core/conversation_models.py:349-355`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/conversation_models.py#L349) | Active intake deduplicates by external source conversation ID alone; the store lookup does not scope by `source_platform` or tenant. Distinct ChatGPT/Gemini/Claude conversations sharing an ID can be treated as duplicates. Raw archive is written before dedup, so retries still create extra raw artifacts. | Use `(tenant, source_platform, source_conversation_id)` unique identity; idempotent ingest transaction and cross-source collision tests. |
| PF-115 | P1 | [`core/intake.py:113-175`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/intake.py#L113); [`core/intake_channels.py:185-207`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/intake_channels.py#L185) | Active intake suppresses funnel `add_item` and linkage failures, may return a promoted backlog item without its intake record, and on broader exception falls back to direct backlog creation. The documented single intake path and provenance invariants are therefore not guaranteed. `update_item` only rewrites index.json despite its docstring promising JSONL updates. | Make provenance/ingest atomic or explicitly record degraded state; reconcile JSONL and index from authoritative events; inject channel-write and promotion failures. |
| PF-116 | P2 | [`core/intake_adapters.py:70-86`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/intake_adapters.py#L70); [`dashboard/api/app.py:285-293`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/dashboard/api/app.py#L285) | Public intake-instructions endpoint accepts caller-supplied `source`; adapter instructions joins it into a filesystem path without source allowlisting. A crafted source path can read an unintended `instructions.md` within accessible directories if one exists. No arbitrary-file read beyond this fixed basename is established. | Validate source against registered adapter identifiers and resolved adapter root; negative traversal tests. |

### Cross-batch reconciliation and limitations

- **PF-111 extends PF-106**, providing the missing active executor caller trace; retain both IDs for provenance but group as one remediation epic (user-facing integration consent).
- **PF-112 extends PF-107** to the separately active raw inbox source path; one shared path-containment library can address both.
- **PF-113** is a statically demonstrated missing-method call and false-success response; no server was started. The separate `ConversationStore._get_chunk_dir` accepts unsanitized conversation IDs, but because the current endpoint calls a nonexistent method, exploitability through this endpoint is not asserted. Trace other callers before separate severity assignment.
- **PF-114** is a source/tenant identity-design risk, not evidence that external platforms actually generate colliding IDs in production.
- **PF-115** is a consistency and traceability failure under exception conditions; no injected-failure test was run.
- Existing FastAPI findings PF-021/PF-022/PF-023/PF-028/PF-048/PF-049 remain in scope. `core/intake_api.py` declares itself deprecated and was not treated as the mounted active router.
- No new findings are assigned for already-registered auth, archive or upload-size issues. The historical PF-070–PF-079 detail gap remains open.

**Next Batch O:** inspect active FastAPI input models/authorization call chains for intake, projects and licensing; inspect actual tests and CI collection for consent, chunk-upload and intake path traversal; continue config/schema, agents/skills and tracked-file disposition. No claim of complete review of 3,026 tracked files.


## Batch O — active FastAPI security and input-contract crosswalk (2026-09-28)

**Baseline:** pinned `develop` commit `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`. GitHub connector re-fetched the active `dashboard/api/app.py`, `core/tenancy.py`, `core/licensing.py`, `core/intake_files.py`, `core/backlog.py`, `pyproject.toml`, and reviewed selected methods/endpoint call chains. **Six existing files rechecked, zero newly distinct files conservatively counted.** No runtime HTTP, concurrency, or pytest tests were executed. Legacy dashboard `dashboard/server.py` and `dashboard/static/index.html` were excluded.

### New deduplicated findings PF-117–PF-119

| ID | Priority | Pinned source | Source-level evidence and impact | Remediation / regression |
|---|---|---|---|---|
| PF-117 | **P1** | [`dashboard/api/app.py:190-209`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/dashboard/api/app.py#L190-L209) | Active per-agent control endpoint takes `project` from a generic JSON body and builds `PRODUCTS / project / "control.json"` without canonical containment or per-project authorization. With a crafted project path, an authenticated shared-token caller may write a `control.json` outside the intended project directory where permissions allow. The write is also direct, not atomic. This is a separate active endpoint from the project-archive traversal in PF-051. | Strict project slug and resolved-path containment, server-side project authorization, atomic control updates; negative traversal/absolute-path and parallel-control tests. |
| PF-118 | **P1** | [`dashboard/api/app.py:131-135`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/dashboard/api/app.py#L131-L135); [`dashboard/api/app.py:69-80`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/dashboard/api/app.py#L69-L80) | `/api/v1/cp/users` is guarded only by shared-token `auth`, not `operator_guard`, and accepts a caller-supplied tenant filter. The other control-plane tenant listing endpoint uses `operator_guard`; this users endpoint has no equivalent operator-instance or verified platform-admin check. Depending on control-plane data and deployment, ordinary token holders may enumerate user records outside their role/tenant. Extends PF-021/PF-022 to a distinct endpoint; group authorization remediation. | Require authenticated platform-admin principal on operator builds; restrict tenant visibility; anonymous, tenant-token and cross-tenant user-list tests. |
| PF-119 | **P1** | [`dashboard/api/app.py:399-421`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/dashboard/api/app.py#L399-L421); [`core/backlog.py:817-840`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/backlog.py#L817-L840) | Generic backlog `update` action forwards every request-body field except `scope` directly to `backlog.update`, which performs `target.update(fields)` and persists. No API field allowlist, immutable-field protection or status-transition authorization appears on this path. A shared-token caller can modify arbitrary backlog item fields, including identity/provenance/status metadata; consequences depend on downstream consumers. Cross-tenant access is separately tracked by PF-022. | Typed patch schema, allowlisted editable fields, immutable provenance/ID, explicit transition rules and actor-bound audit; malicious `id`, `created_at`, `origin`, `status` update tests. |

### Reconciliation and test inventory

- **Previously known, not renumbered:** PF-021 operator guard lacks principal authentication; PF-022 tenant-member routes have shared-token auth without tenant binding; PF-023 public SSE; PF-028 unbounded upload bytes; PF-049 license key in GET URL; PF-051 archive traversal; PF-113 nonexistent chunk-upload method. These were rechecked where relevant and are **not** presented as new findings.
- `core/tenancy.py` role vocabulary validation is present (`owner`, `admin`, `write`, `read`), but its CRUD functions do not establish the caller's identity; authorization belongs at the API/service boundary.
- `core/intake_files.py` normalizes uploaded filenames, a positive control; `MAX_TEXT=200000` is an extracted-text cap, **not** an upload byte cap (PF-028).
- `pyproject.toml` sets `testpaths=["test-framework"]`. Exact guessed paths `.github/workflows/ci.yml`, `test-framework/tests/test_dashboard_api.py`, and `test-framework/tests/test_intake.py` returned NOT_FOUND; **this does not establish that CI or equivalent tests are absent elsewhere**. GitHub code search against the default branch returned no matches for selected test phrases, but the audit baseline is a pinned commit; use a pinned recursive tree for exhaustive test/CI disposition.
- **Static findings only.** No running service was accessed; authorization exposure and path writes are conditional on deployment, permissions, and actual credentials.

### Next Batch P

Retrieve the pinned tree's actual test/CI paths rather than guessing; inspect API authorization and input-schema regression tests, then remaining agent cards, skills and config/schema wiring. Continue file-level disposition of all 3,026 tracked files or justified exclusions.


## Revised audit scope — user decision (2026-09-28)

The current audit is **restricted to four directories** at the immutable pinned commit: `product-forge/core/` (239 tracked files), `product-forge/scripts/` (64), `product-forge/agents/` (62), and `product-forge/config/` (29), **394 tracked files total**. GitHub's recursive tree response for this commit was `truncated=false` and returned 3,026 repository blobs (3,024 under `product-forge/`). `products/`, `test-framework/`, `data/`, the dashboard, security/, .opencode/, documentation, workflows and every other directory are excluded from **future file-level review**, even if an in-scope file references them. Previously documented out-of-scope findings are retained as historical context and excluded from the active-scope completion numerator. A cross-boundary call may be noted, but no new out-of-scope file audit is undertaken.

The earlier 172 retrieved-file count and 107 in-scope referenced-path estimate were provisional and drawn from incomplete historical inventories, including a missing detailed Batch I artifact. **Do not present either as a verified complete-review numerator.** Starting with Batch P, record exact per-batch newly documented paths and an explicit review disposition. The pinned 394-path scope inventory is verified at the directory/count level; the complete 394-path disposition ledger is still to be assembled.

## Batch P — agent contracts, config policy and pipeline scripts (2026-09-28)

**Baseline:** pinned commit `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`; **scope:** only `core/`, `scripts/`, `agents/`, `config/`. GitHub connector retrieved 17 in-scope files: 15 newly documented paths and two rechecks (`scripts/dev/build_release.py`, `core/close_loop.py`). The new paths are: `agents/orchestrator.agent.json`, `agents/security.agent.json`, `agents/guardian.agent.json`, `agents/quality_gate.agent.json`, `agents/implement.agent.json`, `agents/validate.agent.json`, `agents/legal-privacy.agent.json`, `config/provider-keys.json`, `config/verification-policy.json`, `config/env-flags.json`, `config/agent-capabilities.json`, `scripts/run_pipeline.py`, `scripts/pipeline.py`, `core/env_flags.py`, `core/credentials.py`. The two rechecks are: `scripts/dev/build_release.py`, `core/close_loop.py`. Seven agent JSON cards, four config JSON files, two main pipeline scripts and two core support modules are newly documented. **Static review only; no runtime tests.** The agent JSON files parsed as JSON when inspected.

### New deduplicated static findings PF-120–PF-122

| ID | Priority | Pinned source | Evidence / qualification | Remediation and regression |
|---|---|---|---|---|
| PF-120 | **P1** | [`agents/orchestrator.agent.json:2-10`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/agents/orchestrator.agent.json#L2-L10) | The same card declares the orchestrator a *judgment plane* with PipelineExecutor as execution SSOT, but its embedded instructions also call the agent the execution SSOT, require it to manage agent invocation and stage approvals, and demand a human pause after **every** stage. Its machine-readable `tools=[]`, `sub_agents=[]` and `can_invoke=[]` do not grant the delegation implied by those instructions. This is a contradictory agent contract; runtime behavior depends on which contract the loader honors. | Split advisory coordinator contract from executor control plane, define enforceable machine-readable invocation permissions, and contract-test actual loader output and stage-HIL policy. |
| PF-121 | **P2** | [`config/env-flags.json:1-12`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/config/env-flags.json#L1-L12); [`core/env_flags.py:43-66`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/env_flags.py#L43-L66); prior in-scope [`core/pipeline_executor.py:1694-1702`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/pipeline_executor.py#L1694-L1702) | The declared central registry omits the security/product-consent switch `PIPELINE_ASK_INTEGRATIONS` even though the active executor defaults it to `0` and applies product-shaping integrations automatically. The registry's load/get implementation does not enforce completeness; registry-based discovery therefore hides a consequential switch. Extends PF-106/PF-111 but is a distinct configuration-governance defect. | Register the flag with a safe default, schema-check every consumed PIPELINE_/MODEL_ flag against the registry in CI, and test effective defaults for noninteractive runs. |
| PF-122 | **P2** | [`agents/guardian.agent.json:2-12`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/agents/guardian.agent.json#L2-L12); [`agents/quality_gate.agent.json:2-12`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/agents/quality_gate.agent.json#L2-L12) | Both cards promise security/compliance or release-quality gate enforcement but declare `tools=[]`, `sub_agents=[]`, and `can_invoke=[]`. Their instructions reference reading inputs and producing gate evidence. Without an external runner that supplies evidence and persists outputs, the declared agent contracts alone cannot establish that gates actually executed. **Conditional contract gap**, not proof that runtime gates are bypassed. | Specify evidence-only versus active-gate roles, make required capabilities and outputs machine-checkable, and test the actual runner's tool grants, evidence persistence and fail-closed behavior. |

### Existing findings rechecked and not duplicated

- **PF-094:** `scripts/dev/build_release.py` uses five hardcoded operator route prefixes; it cannot prove operator-only route isolation or per-route authorization. The source remains unchanged at the pinned commit; no new ID.
- **PF-109:** `core/close_loop.py` does perform `verify_run()` before its normal `verify_and_close()` calls `intake_channels.close_verified()`, narrowing the concern to direct callers, manual force-close and bypassable service boundaries. `force_close()` is explicitly a manual override; its caller authorization still requires tracing. Do not describe all normal closes as unverified.
- **Positive controls:** `config/provider-keys.json` holds environment-variable names, not literal API secrets; `core/credentials.py` exposes budget checks; `config/verification-policy.json` defines evidence requirements for build/entire scopes. Existence of these controls does not prove every caller enforces them.
- **Script distinction:** `scripts/run_pipeline.py` is the modern generic CLI, while `scripts/pipeline.py` is a larger compatibility/management CLI with its own stage descriptions and `.opencode/agent` discovery. Their runtime entrypoint selection requires further caller tracing; do not assume both are active or equivalent.

### Batch P scope accounting and next batch

- Pinned in-scope total: **394** (`core` 239, `scripts` 64, `agents` 62, `config` 29).
- Batch P: **17 exact in-scope paths fetched**, **15 newly documented in the cumulative report**, **2 previously documented rechecks**.
- Previous user-facing estimate of **107** in-scope referenced paths was provisional and not a complete audit ledger. If it is accurate and nonoverlapping with the 15 new paths, the working estimate becomes **122 referenced paths / 272 not yet documented**, **not** 122 fully reviewed or a verified completion percentage.
- Cumulative finding ID range **PF-001–PF-122**, including historical out-of-scope and incompletely recovered Batch I IDs; deduplicate remediation by issue cluster.
- **Batch Q:** continue new `core/` modules and remaining `agents/`/`config/` cards, trace real loader/tool-permission wiring, and create an exact in-scope 394-path disposition ledger. No out-of-scope test-framework or product-data audit.

---

## Batch Q — agent permissions, tool sandbox, contract loading and exact revised-scope reconciliation (2026-09-28)

**Scope:** `product-forge/core/`, `scripts/`, `agents/`, `config/` only; pinned `develop` commit `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`. GitHub's recursive tree returned `truncated=false` and 394 files in these four directories (239 core, 64 scripts, 62 agents, 29 config). This batch retrieved and inspected 14 files (11 core, 2 agent JSON cards, 1 config), of which five were not previously documented in the cumulative report/tracker. All findings are static and conditional on caller wiring and filesystem permissions; no runtime tests were run.

### New findings PF-123–PF-126

| ID | Priority | Pinned source | Evidence / risk | Remediation |
|---|---|---|---|---|
| PF-123 | **P1** | [`core/tool_policy.py:43-57`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/tool_policy.py#L43-L57) | The effective tool set is the union of declared card tools and tools inferred from agent ID, description, and capability keywords. A denied or intentionally absent `http_get` can be added back when those text fields match research markers; the policy explicitly never removes granted tools. This is a conditional privilege-expansion path when dynamic tool selection is applied. | Intersect dynamic suggestions with an immutable maximum-permission set, preserve explicit denies, and test denied web access under research-themed descriptions. |
| PF-124 | **P1** | [`core/tool_registry.py:108-126`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/tool_registry.py#L108-L126) | Filesystem sandbox uses `abspath`/`commonpath` without resolving symlinks. A symlink inside the project workspace pointing outside it passes the lexical check, allowing read/write outside the intended workspace if an agent can access or create that symlink. | Resolve real paths for workspace and target, reject symlink escapes and TOCTOU-sensitive paths, and test external symlink read/write. |
| PF-125 | **P1** | [`core/tool_registry.py:32-105`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/tool_registry.py#L32-L105) | ToolSpec has `dangerous` and `requires_approval` metadata, but the execution dispatcher calls handlers by name without checking either field or an approval token. The default `run_command` is marked dangerous. If callers rely on registry metadata to enforce HIL, the registry fails to enforce it; this also compounds the historical per-agent allowlist finding PF-004. | Require an explicit authorization context and validated approval for dangerous/approval-required tools at the registry boundary; add deny-by-default tests. |
| PF-126 | **P2** | [`core/agent_spec.py:188-201`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/agent_spec.py#L188-L201) | `load_specs` silently suppresses every exception when reading an agent JSON file. A malformed or missing required security/quality agent contract can disappear from the loaded registry without a reported configuration failure; downstream behavior depends on whether required roles are separately checked. | Return structured load errors, fail startup for required agent contracts, and validate completeness and schema in CI. |

### Existing findings rechecked, not duplicated

- PF-004 (`core/agent_tool_loop.py:148-175`) remains supported: the text tool loop does not check the parsed tool name against the agent's `spec.tools`, while the native tool path does. PF-125 is the distinct absence of registry-level HIL/approval enforcement; remediate together.
- PF-003 (`core/agent_readiness.py:104-109`) remains supported: an exception during provider-key verification is treated as `has=True`.
- PF-120/PF-122 agent contract issues remain conditional; two additional agent cards (`security-audit`, `production-deploy`) were examined but not proven to bypass active runtime gates.
- `core/verification_policy.py` and `core/verification_runner.py` were rechecked; the user-excluded `test-framework/` directory was not audited.

### Exact pinned-tree disposition reconciliation

A complete **394-path CSV disposition ledger** is now included as a separate deliverable. This reconciles *named historical source/retrieval records* with actual pinned-tree membership. It is not a certification that every named file has received a complete line-by-line audit.

| Directory | Pinned-tree files | Named in prior records | Batch Q examined | Documented after Q | Not yet documented |
|---|---:|---:|---:|---:|---:|
| `core/` | 239 | 93 | 11 | 96 | 143 |
| `scripts/` | 64 | 9 | 0 | 9 | 55 |
| `agents/` | 62 | 7 | 2 | 9 | 53 |
| `config/` | 29 | 8 | 1 | 8 | 21 |
| **Total** | **394** | **117** | **14** | **122** | **272** |

The four historical strings `core/agent_integration.py`, `core/dast_scanner.py`, `core/dependency_scanner.py`, and `core/secret_detector.py` do not exist as paths within the pinned `core/` tree. The scanner paths belong to a user-excluded directory; they are **not** credited toward in-scope progress. `core/` also contains four tracked `pipeline_executor.py.bak_pre_*` backups. They remain listed in the 394-path inventory, marked as backup candidates, and should not be counted as active runtime modules unless ownership confirms otherwise.

**Accounting rule:** 122 is a **verified documented/retrieved path count**, not a verified *fully reviewed* count. 272 paths have no matching named evidence in the recovered report/tracker; some may have been examined in historical Batch I but cannot be credited without recovering its missing file list. Existing historical finding IDs and out-of-scope findings remain preserved. Next batch R should prioritize still-unreconciled active core modules and additional agent/config cards; promote paths to 'reviewed' only with source retrieval and recorded disposition.


## Batch R — full static review and verified progress (2026-09-28)

**Scope and baseline:** pinned commit `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`, only `core/`, `scripts/`, `agents/`, `config/`. Ten in-scope files were fetched. Nine small/medium files received **complete source-line static inspection** and one large reference table (`core/port_config.py`) received targeted review. Nine of these ten were not previously documented; `config/agent-hierarchy.json` was a prior historical reference and is now fully statically reviewed. The nine fully reviewed files are `core/capacity.py, core/alerts.py, core/brief_check.py, core/backlog_link.py, config/alerts.json, config/capacity.json, config/agent-hierarchy.json, agents/agent_config.agent.json, agents/human.agent.json`. The partially reviewed file is `core/port_config.py` (large port reference map; entry-by-entry verification pending). No tests or production execution were performed.

### New findings PF-127–PF-129

| ID | Priority | Pinned source | Evidence / impact | Remediation |
|---|---|---|---|---|
| PF-127 | **P1** | [`core/brief_check.py:38-62`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/brief_check.py#L38-L62) | A nonempty brief is returned as `ok=True` if the validator is absent, disabled, raises, or emits unparseable JSON. This conflicts with the documented policy not to fabricate a validation verdict; callers that gate on `ok` may advance an unvalidated or placeholder brief. | Return an explicit `unverified` outcome, distinguish `validated` from `nonempty`, and apply configured `on_unclear` at the caller; add unavailable-model and malformed-response tests. |
| PF-128 | **P1** | [`core/capacity.py:55-88`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/capacity.py#L55-L88); [`core/capacity.py:108-125`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/capacity.py#L108-L125) | Supervisor liveness is determined exclusively by Windows `tasklist`, returning `False` on non-Windows systems, so supervisor limits can be undercounted on Linux. Project fallback counts any project lock filename without verifying liveness. `can_start` only reads current state and does not atomically reserve a slot, permitting parallel callers to pass the same capacity check. | Use portable PID checks and lock expiry, and atomic reservation/lease on project start; test Linux and parallel starts. |
| PF-129 | **P2** | [`core/backlog_link.py:38-68`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/backlog_link.py#L38-L68); [`core/backlog_link.py:76-103`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/backlog_link.py#L76-L103); [`core/backlog_link.py:116-160`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/backlog_link.py#L116-L160) | Every bridge operation catches all exceptions and returns `None` without logging, including feature status and defect-link updates. An apparently successful pipeline can silently lose feature/backlog synchronization and defect traceability. The bridge explicitly intends to be nonfatal, but should not be invisible. | Keep nonfatal behavior where needed but emit structured errors, record reconciliation debt, retry idempotently, and test storage failures. |

### Full versus partial review

A *full static review* in this ledger means every source line of the pinned file was inspected for relevant correctness/security risks. It does **not** imply dynamic execution, test coverage, or proof of defect absence. Earlier A–Q files remain `historical_documented_not_certified_complete` or `batch_Q_targeted_review` unless the current turn actually reexamines the whole file. Batch R certified nine files and kept one file partial. This stricter definition avoids retroactively overstating historical progress.

### Verified scope progress after Batch R

| Directory | Total pinned files | Documented/retrieved | Not yet documented | Certified full static review |
|---|---:|---:|---:|---:|
| `core/` | 239 | 101 | 138 | 4 |
| `scripts/` | 64 | 9 | 55 | 0 |
| `agents/` | 62 | 11 | 51 | 2 |
| `config/` | 29 | 10 | 19 | 3 |
| **Total** | **394** | **131** | **263** | **9** |

Previously recorded PF-001–PF-126 are preserved without renumbering. Historical out-of-scope findings remain historical only. The user-excluded `products/`, `data/`, `test-framework/`, dashboard and other directories were not audited in Batch R.


## Batch S — 50-file expanded agent/config review and strict disposition (2026-09-28)

**Pinned source:** `develop` commit `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`. Only `core/`, `scripts/`, `agents/`, `config/` are in audit scope. Batch S retrieved and JSON-parsed **35 complete agent JSON files** and **15 complete configuration JSON files**, inspecting agent tool lists, modes, sub-agent declarations, invocation declarations, embedded frontmatter permissions and role/authority text; and inspecting configuration schemas and key values. **42 newly documented paths**; eight were previously documented. Fourteen small/medium config files are marked full static review. The 35 agent files are explicitly marked **structural/permission reviewed, NOT full instruction-body semantic review**; the 58 KB `config/model-tier.json` is marked structural review only. This is a deliberately honest distinction despite the 50-file batch size. No runtime tests were run.

### New findings

| ID | Priority | Pinned source | Evidence / risk | Remediation |
|---|---|---|---|---|
| PF-130 | **P1** | [`agents/community-social.agent.json:6-16`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/agents/community-social.agent.json#L6-L16); [`agents/growth.agent.json:6-17`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/agents/growth.agent.json#L6-L17); [`agents/legal-privacy.agent.json:6-16`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/agents/legal-privacy.agent.json#L6-L16); [`agents/customer-success.agent.json:6-15`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/agents/customer-success.agent.json#L6-L15) | Embedded original-card frontmatter says `edit: deny`, `web: deny`, `bash: deny`, but JSON `tools` includes `write_file` in all four and `http_get` in three. If JSON is loaded by `core/agent_spec.load_specs`, effective grants conflict with explicit source denies. Extends PF-123 dynamic permission widening. | Make an immutable, validated canonical permission contract; preserve explicit denies in conversion; reject mismatched source-card/JSON grants; add policy regression tests. |
| PF-131 | **P2** | [`agents/implement.agent.json:14-20`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/agents/implement.agent.json#L14-L20); [`agents/implement.agent.json:41`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/agents/implement.agent.json#L41) | Implement instructions require invoking four ordered sub-agents and `sub_agents` declares them, but `can_invoke` is empty. Whether invocation fails depends on the runtime's choice of authority source. | Define one invocation authority, derive/validate both fields from it, and test implement-db → implement-api → implement-logic → implement-ui dispatch. |

### Cross-checks and limitations

- Several role definitions (e.g., `architect`, `design`, `guardian`, `ideation`, `insight-extractor`, `journal-writer`) describe producing files but have an empty `tools` array. This expands the evidence for previously recorded PF-120/PF-122 and is **not counted as another new finding**. Verify which runner actually consumes JSON specs versus `.opencode` cards.
- `config/provider-keys.json` stores environment-variable references, not literal API secrets; its budget caps are documented as advisory. This does not prove hard budget enforcement.
- `config/model-tier.json` is ~58 KB, with five profiles and 28 top-level agent mappings; it needs an entry-by-entry consistency pass before full certification.
- `config/legacy-frozen.json` was inspected as configuration metadata only; excluded legacy dashboard implementation remains outside the audit.
- Source retrieval and JSON parsing are **not** dynamic verification, integration tests, or proof that instructions are enforced.

### Reconciled progress after Batch S

| Directory | In scope | Documented | Certified full static review | Not yet documented |
|---|---:|---:|---:|---:|
| `core/` | 239 | 101 | 4 | 138 |
| `scripts/` | 64 | 9 | 0 | 55 |
| `agents/` | 62 | 42 | 2 | 20 |
| `config/` | 29 | 21 | 17 | 8 |
| **Total** | **394** | **173** | **23** | **221** |

The remaining **221** means not yet documented by recovered audit evidence, not necessarily never accessed historically. Among the 173 documented files, 23 are certified full static reviews under the stricter method; 150 remain historical, partial, or structural-only. The CSV is the canonical 394-file disposition. Historical findings PF-001–PF-129 and out-of-scope appendices remain preserved.


## Batch T — 40-file core/scripts review (2026-09-28)

**Scope:** pinned `develop` commit `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`; 30 previously undocumented `scripts/dev/*.py` files and 10 previously undocumented `core/*.py` files retrieved. **17 files certified complete static review** (15 short scripts and 2 short core modules); **23 large/complex files targeted static review** with remaining semantic and edge-case examination outstanding. No code was executed; no excluded directory was audited. The scripts were inspected as code, even when their runtime targets point to excluded `products/` or `.opencode/` locations.

### New findings PF-132–PF-137

| ID | Priority | Pinned source | Evidence / risk | Recommended fix |
|---|---|---|---|---|
| PF-132 | **P1** | [`scripts/dev/_automarge2.py:26-L49`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/dev/_automarge2.py#L26-L49) | The standalone `_automarge2.py` runs `main()` unconditionally, polls pending human prompts, constructs answers from recommended/default text and submits them to `core.interactive`. Running this helper can impersonate a human decision without explicit operator confirmation. Its hardcoded project and fixed temp file compound the risk. | Require explicit `--apply`, restrict to clearly designated simulation environments, audit decision provenance, and never use this path to satisfy mandatory HIL gates. |
| PF-133 | **P1** | [`core/app_smoke.py:25-L73`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/app_smoke.py#L25-L73) | `core/app_smoke.py` interpolates a configurable `app_entrypoint` directly into `python -c "import {ep}"` without validating the value as a Python dotted module identifier. A malicious or malformed project config can inject Python statements into the smoke-check subprocess. | Parse/validate the module identifier (or use `importlib.import_module` with a fixed Python program), and restrict execution to an isolated build workspace. |
| PF-134 | **P1** | [`core/circuit_breaker.py:43-L121`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/circuit_breaker.py#L43-L121) | `core/circuit_breaker.py` persists registry state using direct JSON overwrite without creating parent directories, interprocess locking or atomic replace. Simultaneous failures/successes can lose updates or corrupt breaker state; missing project directories cause write errors. | Ensure parent directory exists; use atomic temp-file replace and cross-process locking; test concurrent transitions and restart recovery. |
| PF-135 | **P1** | [`scripts/dev/extract_llm_client.py:90-L129`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/dev/extract_llm_client.py#L90-L129) | `scripts/dev/extract_llm_client.py` is a one-shot source-rewriting script that directly overwrites `core/pipeline_executor.py` after brittle textual extraction. It has no backup, AST validation, transaction, or rollback, and may leave the executor partially modified if assumptions change. | Retire from routine use or require clean Git worktree, dry-run diff, AST/compile checks, backup, and atomic write. |
| PF-136 | **P2** | [`scripts/dev/e2e_backlog_check.py:20-L80`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/dev/e2e_backlog_check.py#L20-L80) | `scripts/dev/e2e_backlog_check.py` deletes `products/_e2e_backlog/` before and after testing and updates a Product Forge backlog item as part of cleanup. A name collision or interrupted run can remove user data or leave persistent test records. | Use unique isolated temporary project names and a test-only backlog namespace; confirm ownership before deletion; guarantee cleanup in `finally`. |
| PF-137 | **P2** | [`core/call_ledger.py:20-L35`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/call_ledger.py#L20-L35) | `core/call_ledger.py` suppresses all append exceptions. LLM/tool call accounting can silently omit records after I/O failure, compromising spend and audit reconstruction when this ledger is used as evidence. | Surface structured write failures, track dropped-record counters, and use durable append/queue semantics. |

### Reviewed file inventory

**Complete static review (17):** `scripts/dev/_add_kctier_profile.py`, `scripts/dev/_automarge2.py`, `scripts/dev/_probe_kctier_models.py`, `scripts/dev/_probe_mimo.py`, `scripts/dev/_probe_ua.py`, `scripts/dev/analyze_agent_cards.py`, `scripts/dev/answer_prompt.py`, `scripts/dev/build_tier_allocation.py`, `scripts/dev/compare_agents.py`, `scripts/dev/debug_implement_tools.py`, `scripts/dev/find_unused_modules.py`, `scripts/dev/live_status.py`, `scripts/dev/migrate_agents.py`, `scripts/dev/migrate_backlog_refs.py`, `scripts/dev/migrate_backlog_storage.py`, `core/app_smoke.py`, `core/banner.py`

**Targeted static review; not certified complete (23):** `scripts/dev/backfill_item_context.py`, `scripts/dev/build_agent_specs.py`, `scripts/dev/check_tier_models.py`, `scripts/dev/e2e_backlog_check.py`, `scripts/dev/extend_schemas.py`, `scripts/dev/extract_llm_client.py`, `scripts/dev/extract_table.py`, `scripts/dev/gen_backlog_summary.py`, `scripts/dev/gen_docs_index.py`, `scripts/dev/generate_agent_cards.py`, `scripts/dev/generate_model_analysis.py`, `scripts/dev/generate_report.py`, `scripts/dev/invocation_audit.py`, `scripts/dev/migrate_backlog.py`, `scripts/dev/migrate_paths.py`, `core/__init__.py`, `core/architecture_diagram.py`, `core/artifact_formats.py`, `core/budget_conservation.py`, `core/budget_planner.py`, `core/business_skills_selector.py`, `core/call_ledger.py`, `core/circuit_breaker.py`

### Updated exact file disposition

| Directory | Total | Documented after T | Fully statically reviewed | Not yet documented |
|---|---:|---:|---:|---:|
| `core/` | 239 | 111 | 6 | 128 |
| `scripts/` | 64 | 39 | 15 | 25 |
| `agents/` | 62 | 42 | 2 | 20 |
| `config/` | 29 | 21 | 17 | 8 |
| **Total** | **394** | **213** | **40** | **181** |

**Method:** A complete static review means all source lines were examined; it is not proof of successful runtime tests. A targeted review means the entire file was retrieved and key code paths inspected, but remaining details are not certified. Existing PF-001–PF-131 remain preserved, including historical out-of-scope findings; Batch T introduces PF-132–PF-137. The 394-file CSV is the authoritative disposition.


## Batch U — 40-file agent/config/script review (2026-09-28)

**Scope:** 40 previously undocumented paths in the pinned `develop` tree: 20 `agents/`, 8 `config/`, 12 `scripts/dev/`. All 40 retrieved in full and parsed/inspected structurally; **20 complete static inspections** (4 short agent definitions, 4 small configurations, 12 short scripts); 20 long agent/config files remain targeted-only pending deep semantic and per-entry inspection. No runtime tests, live provider calls, or excluded-directory file inspections were performed. `config/model-catalog.json` contains 632 model entries and is **not** certified line-by-line; `config/file-manifest.json` has 552 entries and is not certified line-by-line.

### New findings PF-138–PF-143

| ID | Priority | Pinned evidence | Issue / risk | Action |
|---|---|---|---|---|
| **PF-138** | **P1** | [`scripts/dev/run_e2e.py:8-L16`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/dev/run_e2e.py#L8-L16) | E2E runner prints `success=False` or catches an exception but never exits nonzero. Shell/CI can mark failed pipeline execution as successful. | `raise SystemExit(0 if success else 1)` and exit nonzero on exception; add a subprocess regression test. |
| **PF-139** | **P1** | [`agents/performance.agent.json:6-L6`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/agents/performance.agent.json#L6-L6) | Embedded k6 example repeats `http_req_duration` in the same JS object (p95 threshold overwritten by p99) and configures `http_req_failed` `<1%` despite the agent's declared `<0.1%` critical NFR. A generated test copied from the example could under-enforce the release gate. | Use one array for both latency percentiles, use `rate<0.001`, and contract-test generated thresholds against project NFRs. |
| **PF-140** | **P1** | [`agents/post-production.agent.json:6-L6`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/agents/post-production.agent.json#L6-L6) | Post-production agent instructs weekly chaos experiments **in production**, but its executable tool declaration contains generic `run_command` and no machine-readable approval/environment/rollback constraints. This is a hazardous policy-contract gap, not evidence that chaos experiments actually ran. | Require explicit operator approval, blast-radius limits, staging-first rehearsal, automatic abort/rollback and environment-bound tool permissions. |
| **PF-141** | **P2** | [`config/knowledge-registry.json:3-L18`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/config/knowledge-registry.json#L3-L18) | Registry marks a test-created competitive-teardown skill `active` despite a placeholder `https://example/competitive-teardown` URL, blank path and blank license. Discovery may advertise a non-installable/unlicensed capability if this entry is consumed. | Remove fixture data from live registry or mark disabled; validate resolvable URI/path and license before activation. |
| **PF-142** | **P2** | [`scripts/dev/test_gates.py:1-L27`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/dev/test_gates.py#L1-L27); [`scripts/dev/test_tool_e2e.py:1-L37`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/dev/test_tool_e2e.py#L1-L37) | Gate and tool E2E scripts print results without assertions or nonzero failure exits; they are diagnostic scripts, not trustworthy automated regression tests. `test_fallback.py` and `test_spec_wiring.py` have similar print-only behavior. | Convert expected results to assertions/pytest and make failures propagate to CI. |
| **PF-143** | **P2** | [`agents/pricing-strategist.agent.json:6-L14`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/agents/pricing-strategist.agent.json#L6-L14); [`agents/sales-crm.agent.json:6-L14`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/agents/sales-crm.agent.json#L6-L14) | Two additional business-agent cards embed `edit: deny` while declaring `write_file`; pricing strategist also embeds `web: deny` but declares `http_get`. **Extension of PF-130**, recorded as affected-file expansion rather than a separate root-cause defect. | Reconcile source permissions and JSON grants in one canonical schema; add cross-card contract validation. |

**Deduplication:** PF-143 is an affected-file extension of PF-130, not an independent defect count. `product-analyzer`/`presentation-generator` have `tools=[]` despite describing analysis/media output; same conditional capability-contract family as PF-120/PF-122, not a new runtime-bypass claim. `researcher` and `scout` instructions mandate direct `pipeline.json` status writes while JSON tools omit `write_file`; check whether the executor owns status persistence before treating this as a runtime failure.

### Batch U file disposition

**Complete static inspection (20):** `agents/product-design-spec.agent.json`, `agents/product-owner.agent.json`, `agents/ux-ia.agent.json`, `agents/visual_qa.agent.json`, `config/business-models-kb.json`, `config/dashboard-blueprint.json`, `config/knowledge-registry.json`, `config/spec-id-families.json`, `scripts/dev/parked_review.py`, `scripts/dev/probe_native_tools.py`, `scripts/dev/run_e2e.py`, `scripts/dev/service_catalog.py`, `scripts/dev/show_tiers.py`, `scripts/dev/test_fallback.py`, `scripts/dev/test_gates.py`, `scripts/dev/test_spec_wiring.py`, `scripts/dev/test_techstack.py`, `scripts/dev/test_tool_e2e.py`, `scripts/dev/test_tool_loop.py`, `scripts/dev/test_w2.py`.

**Targeted static review (20; further semantic/per-entry review required):** `agents/package.agent.json`, `agents/performance.agent.json`, `agents/post-production.agent.json`, `agents/pre-production.agent.json`, `agents/presentation-generator.agent.json`, `agents/pricing-strategist.agent.json`, `agents/product-analytics.agent.json`, `agents/product-analyzer.agent.json`, `agents/researcher.agent.json`, `agents/review.agent.json`, `agents/sales-crm.agent.json`, `agents/scout.agent.json`, `agents/static_verifier.agent.json`, `agents/strategist.agent.json`, `agents/summary-creator.agent.json`, `agents/theme-analyzer.agent.json`, `config/file-manifest.json`, `config/model-catalog.json`, `config/techstack-catalog.json`, `config/test-matrix.json`.

### Reconciled cumulative inventory

| Directory | Total | Documented | Complete static inspection | Not yet documented |
|---|---:|---:|---:|---:|
| `core/` | 239 | 111 | 6 | 128 |
| `scripts/` | 64 | 51 | 27 | 13 |
| `agents/` | 62 | 62 | 6 | 0 |
| `config/` | 29 | 29 | 21 | 0 |
| **Total** | **394** | **253** | **60** | **141** |

**Interpretation:** 253/394 have some documented review evidence; only 60/394 are certified complete static reviews. 193 documented files are historical or targeted-only and still need deep review before a full line-by-line completion claim. No dynamic verification was conducted.


## Batch V — 40-file core review (2026-09-28)

**Pinned snapshot:** `develop` at `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`. **Scope:** 40 previously undocumented `core/` files. All 40 retrieved in full. Seven short-to-medium modules were inspected throughout; 33 larger/other modules received targeted structural and risk-path review and are **not** certified complete. No runtime execution, deployment, live credentials or excluded-directory inspections.

### New findings PF-144–PF-150

| ID | Priority | Pinned evidence | Issue and conditional impact | Recommended action |
|---|---|---|---|---|
| **PF-144** | **P1** | [`core/byot_integration.py:17-17`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/byot_integration.py#L17-L17) | CustomModel.api_key and CustomMCPServer.env are serialized via asdict directly into byot/byot_config.json without encryption or redaction. File-permission and storage controls were not demonstrated in this module. | Store only credential references; retrieve secrets from a secrets manager, restrict filesystem permissions, and add no-plaintext-secret tests. |
| **PF-145** | **P1** | [`core/code_quality_gate.py:63-98`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/code_quality_gate.py#L63-L98) | For code-producing agents the gate returns passed=True when no source files were scanned, and unreadable files are skipped. Empty or unreadable project trees can therefore appear to satisfy the no-placeholder gate. | Require scanned_files>0 when code output is expected, fail or mark indeterminate on unreadable source, and verify declared artifacts. |
| **PF-146** | **P1** | [`core/build_manager.py:101-165`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/build_manager.py#L101-L165) | create_build records status=built even if _publish_artifacts returns [] after registry errors; individual signing errors are silently swallowed. Artifact/signature completeness is not a prerequisite for the built status. | Differentiate build, publication and signing states; enforce required artifact/signature policy and propagate failures. |
| **PF-147** | **P1** | [`core/delegation.py:48-59`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/delegation.py#L48-L59) | DelegationRouter.dispatch does not check or increment its DelegationBudget, does not independently validate to_agent against resolve, and silently swallows delegation-record persistence failures. If invoked without external guards, the advertised limits and audit trail are bypassable. | Make dispatch enforce budget and resolved target atomically, persist a durable record, and return explicit failures. |
| **PF-148** | **P2** | [`core/knowledge_compiler.py:49-59`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/knowledge_compiler.py#L49-L59) | Compiled knowledge IDs use only domain plus epoch seconds. Two compilations for the same domain within one second generate the same filename and overwrite prior knowledge. | Use UUID/monotonic IDs and atomic exclusive writes; test rapid consecutive compilations. |
| **PF-149** | **P2** | [`core/event_bus.py:39-61`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/event_bus.py#L39-L61) | Global event-bus emit silently suppresses append, subscriber and coordinator-routing failures while returning an event object. Callers cannot distinguish a persisted/routed event from a lost one. Distinct event-bus impact from PF-137 call-ledger issue. | Return structured persistence/delivery status, expose dead-letter/error telemetry and make critical events fail visibly. |
| **PF-150** | **P2** | [`core/cross_review.py:393-397`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/cross_review.py#L393-L397) | Cross-review state is saved with direct JSON overwrite and no interprocess lock or atomic replacement; concurrent review updates can overwrite each other or leave a truncated review file after interruption. | Use transactional persistence or lock+atomic replace, optimistic version checks, and concurrency tests. |

**Deduplication:** PF-149 is a distinct event-bus occurrence of the silent-write family also represented by PF-137; PF-146 extends historical release-gate concerns but specifically documents publication/signing state. These are static code-path findings; caller-side guards, if any, remain to be tested.

### Batch V file disposition

**Complete static inspection (7):** `core/build_manager.py`, `core/byot_integration.py`, `core/code_quality_gate.py`, `core/delegation.py`, `core/event_bus.py`, `core/forced_convergence.py`, `core/knowledge_compiler.py`.

**Targeted static review (33; deeper line-by-line review pending):** `core/build_utility.py`, `core/business_models_kb.py`, `core/capability_bridge.py`, `core/change_registry.py`, `core/change_spec.py`, `core/code_analyzer.py`, `core/context_policy.py`, `core/conversation_compiler.py`, `core/cost_kpi.py`, `core/cost_modeling.py`, `core/cross_review.py`, `core/customer_onboarding.py`, `core/dashboard_archetypes.py`, `core/dashboard_blueprint.py`, `core/defect_loop.py`, `core/design_critic.py`, `core/design_tokens.py`, `core/diagram_render.py`, `core/discovery_engine.py`, `core/discovery_panel.py`, `core/docker_compose_generator.py`, `core/domain_research.py`, `core/enhance.py`, `core/events.py`, `core/finops.py`, `core/forge_constitution.py`, `core/forge_store.py`, `core/id_index.py`, `core/insights.py`, `core/interactive.py`, `core/issue_tracker.py`, `core/iteration_planner.py`, `core/knowledge_refresh.py`.

### Cumulative reconciled scope

| Directory | Total | Documented | Certified full static | Pending/unreconciled |
|---|---:|---:|---:|---:|
| `core/` | 239 | 151 | 13 | 88 |
| `scripts/` | 64 | 51 | 27 | 13 |
| `agents/` | 62 | 62 | 6 | 0 |
| `config/` | 29 | 29 | 21 | 0 |
| **Total** | **394** | **293** | **67** | **101** |

**Completion interpretation:** Documented means at least some source-backed audit evidence; it does not mean complete. 226 documented files are not certified for full static review. Four backup-candidate paths remain in the pending/unreconciled group until ownership is resolved.


---

# Batch W — expanded core review (2026-09-28)

**Immutable source:** `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`. **Scope:** 40 previously undocumented `core/` paths, all fetched from pinned GitHub. Full source bodies were retrieved and structurally scanned; critical code paths received focused line-range inspection. **No additional full line-by-line certifications** are claimed for this batch, and no runtime tests were run.

## Newly documented paths

- `core/knowledge_router.py`
- `core/llm_error_handler.py`
- `core/log_router.py`
- `core/logging_manager.py`
- `core/loop_modes.py`
- `core/main.py`
- `core/maintenance.py`
- `core/marketing.py`
- `core/memory_api.py`
- `core/mobile_tester.py`
- `core/modality.py`
- `core/model_fit.py`
- `core/model_recommendation.py`
- `core/model_registry.py`
- `core/multi_model_review.py`
- `core/net_ports.py`
- `core/nfr_coverage.py`
- `core/notification_system.py`
- `core/ops_phase.py`
- `core/orchestrator.md`
- `core/orchestrator/__init__.py`
- `core/orchestrator/artifacts_map.py`
- `core/orchestrator/delegation_coord.py`
- `core/orchestrator/feature_tracker.py`
- `core/orchestrator/model_router.py`
- `core/orchestrator/phasing.py`
- `core/orchestrator/prompt_builder.py`
- `core/orchestrator/reporting.py`
- `core/orchestrator/status.py`
- `core/orchestrator/types.py`
- `core/output_checklist.py`
- `core/pdf_generator.py`
- `core/persona.py`
- `core/phase3_advanced.py`
- `core/plan_evaluator.py`
- `core/portfolio.py`
- `core/pr_gate.py`
- `core/presentation_generator.py`
- `core/product_analyzer.py`
- `core/product_design_spec.py`

## New findings

| ID | Priority | Issue | Pinned source |
|---|---|---|---|
| PF-151 | P1 | PR gate approval can be asserted by a caller without an authenticated HIL proof | [core/pr_gate.py:302–314](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/core/pr_gate.py#L302-L314) |
| PF-152 | P1 | Multi-model review has no minimum quorum | [core/multi_model_review.py:84–103](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/core/multi_model_review.py#L84-L103) |
| PF-153 | P1 | Feature traceability updates fail silently | [core/orchestrator/feature_tracker.py:23–115](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/core/orchestrator/feature_tracker.py#L23-L115) |
| PF-154 | P2 | Model substitution ignores the destination agent requirements | [core/model_fit.py:147–176](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/core/model_fit.py#L147-L176) |
| PF-155 | P2 | Delegation TypeError fallback can invoke a delegated agent twice | [core/orchestrator/delegation_coord.py:90–111](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/core/orchestrator/delegation_coord.py#L90-L111) |
| PF-156 | P2 | PR gate app-test detection accepts textual mentions rather than executed coverage | [core/pr_gate.py:71–92](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/core/pr_gate.py#L71-L92) |

### PF-151 — PR gate approval can be asserted by a caller without an authenticated HIL proof (P1)

**Evidence:** approve_override accepts a caller-supplied approved_by string defaulting to HIL and sets approved=True. No identity or authorization verification is visible at this function boundary. Whether this is exploitable depends on caller exposure. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/core/pr_gate.py#L302-L314).

**Remediation:** Require authenticated approval principal, role authorization, signed/auditable decision and prevent direct untrusted invocation.

### PF-152 — Multi-model review has no minimum quorum (P1)

**Evidence:** Only responding reviewers enter the denominator; a single pass can make the aggregated result passed=True when other configured reviewers fail or time out. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/core/multi_model_review.py#L84-L103).

**Remediation:** Require minimum response quorum, mandatory reviewer set, and fail closed on insufficient coverage.

### PF-153 — Feature traceability updates fail silently (P1)

**Evidence:** Seeding, backlog linking, implementation, test, security and review writes suppress broad exceptions. Feature state can lag execution without a surfaced error. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/core/orchestrator/feature_tracker.py#L23-L115).

**Remediation:** Report partial failures, make critical transitions transactional and reconcile feature/backlog evidence.

### PF-154 — Model substitution ignores the destination agent requirements (P2)

**Evidence:** The ranked substitute is selected from probe success and output length, without applying the target agent’s required context, tool or output capabilities before proposing the substitute. Later catalog_fit is informational. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/core/model_fit.py#L147-L176).

**Remediation:** Filter substitute candidates using per-agent hard capability requirements before ranking.

### PF-155 — Delegation TypeError fallback can invoke a delegated agent twice (P2)

**Evidence:** The catch-all TypeError handler retries execute_fn without context_bundle even when the TypeError originated inside the invoked function after side effects. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/core/orchestrator/delegation_coord.py#L90-L111).

**Remediation:** Check callable signature before invoking; distinguish argument binding failures from internal TypeError; make delegation idempotent.

### PF-156 — PR gate app-test detection accepts textual mentions rather than executed coverage (P2)

**Evidence:** _tests_exercise_app returns true if a test file merely contains the entrypoint name or HTTP-client strings. This helper cannot establish that the app is actually exercised. Caller impact requires separate verification. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/core/pr_gate.py#L71-L92).

**Remediation:** Use test collection, coverage or instrumented execution and reject comment/string-only matches.

## Cross-file interpretation

PF-151 must be assessed alongside prior HIL bypass findings; PF-153 extends earlier backlog synchronization observations, now confirmed in the orchestration feature-tracker adapter. PF-155 is a distinct re-execution risk from the missing authorization checks documented in PF-147. Findings are conditional on runtime wiring; source review alone does not prove deployment exposure.

## Updated four-directory reconciliation

| Directory | Total | Documented | Certified full static | Pending |
|---|---:|---:|---:|---:|
| `core/` | 239 | 191 | 13 | 48 |
| `scripts/` | 64 | 51 | 27 | 13 |
| `agents/` | 62 | 62 | 6 | 0 |
| `config/` | 29 | 29 | 21 | 0 |
| **Total** | **394** | **333** | **67** | **61** |

**Meaning:** 333 have recoverable source-backed review evidence; only 67 have certified complete static review. 266 documented files require deeper completion/reconciliation, and 61 remain undocumented. Four tracked backup candidates remain in the scope ledger until an owner explicitly excludes them.


# Batch X — Final inventory closure and static-audit status (2026-09-28)

**Pinned revision:** `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`; **strict scope:** `product-forge/{core,scripts,agents,config}/`. This batch retrieved 57 previously undocumented files (44 core, 13 scripts) and four tracked historical pipeline-executor backups. All 394 paths now have source-backed inventory disposition. This is **NOT** a certification that all 394 have been read line by line. Only 73 have recovered full-static-review certification; 321 still need deep review or historical evidence reconciliation. Four backups have only structural/metadata inspection. No code execution, tests, dependency installation, or production verification were performed.

## New findings (PF-157–PF-163)

| ID | Priority | Finding | Source |
|---|---|---|---|
| PF-157 | P1 | QA GO/NO-GO may report green when verification policy is unavailable, and hard-codes packaging as green | [core/qa_report.py:53-L68](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/qa_report.py#L53) |
| PF-158 | P1 | QIR security score floors the score at the neutral baseline even when critical/high defects are open | [core/qir.py:121-L135](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/qir.py#L121) |
| PF-159 | P1 | Imported product name is joined directly to products root; existing plan, traceability and ledger files are overwritten | [core/product_ingestion.py:44-L56](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/product_ingestion.py#L44) |
| PF-160 | P1 | Vendor apply commands execute even when vendor CLI detection fails and no local approval guard is visible in this adapter | [core/vendor_adapters.py:89-L102](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/vendor_adapters.py#L89) |
| PF-161 | P1 | Run-plan save errors are swallowed, yet ensure_plan marks plan confirmed and returns it | [core/run_plan.py:136-L145](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/run_plan.py#L136) |
| PF-162 | P2 | Release deployment tickets are created without checking the registered artifact checksum at this boundary | [core/release_manager.py:230-L262](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/release_manager.py#L230) |
| PF-163 | P2 | Test-cycle app boot failure logs a defect after suite completion but is not directly reflected in recorded test counts/status | [core/test_framework_integration.py:412-L454](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/test_framework_integration.py#L412) |

### PF-157 — QA GO/NO-GO may report green when verification policy is unavailable, and hard-codes packaging as green (P1)

**Evidence:** [core/qa_report.py:53-L68](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/qa_report.py#L53). Static finding; impact depends on calling paths and runtime policy. **Recommended remediation:** Return UNKNOWN/red on unavailable policy; require packaging execution evidence; propagate unavailable defect/spec/coverage sources as unknown rather than zero.

### PF-158 — QIR security score floors the score at the neutral baseline even when critical/high defects are open (P1)

**Evidence:** [core/qir.py:121-L135](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/qir.py#L121). Static finding; impact depends on calling paths and runtime policy. **Recommended remediation:** Remove neutral floor when defect evidence exists; apply severity-aware blocking thresholds and show missing evidence separately.

### PF-159 — Imported product name is joined directly to products root; existing plan, traceability and ledger files are overwritten (P1)

**Evidence:** [core/product_ingestion.py:44-L56](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/product_ingestion.py#L44). Static finding; impact depends on calling paths and runtime policy. **Recommended remediation:** Validate canonical destination is inside products root, reject unsafe names, require explicit overwrite/import mode and transactional backup.

### PF-160 — Vendor apply commands execute even when vendor CLI detection fails and no local approval guard is visible in this adapter (P1)

**Evidence:** [core/vendor_adapters.py:89-L102](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/vendor_adapters.py#L89). Static finding; impact depends on calling paths and runtime policy. **Recommended remediation:** Require vendor availability, validated command allowlist, explicit authorization and dry-run/approval before apply; fail closed on absent verification.

### PF-161 — Run-plan save errors are swallowed, yet ensure_plan marks plan confirmed and returns it (P1)

**Evidence:** [core/run_plan.py:136-L145](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/run_plan.py#L136). Static finding; impact depends on calling paths and runtime policy. **Recommended remediation:** Propagate persistence failure and only mark/return a confirmed plan after durable verified save.

### PF-162 — Release deployment tickets are created without checking the registered artifact checksum at this boundary (P2)

**Evidence:** [core/release_manager.py:230-L262](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/release_manager.py#L230). Static finding; impact depends on calling paths and runtime policy. **Recommended remediation:** Require registered artifact lookup and successful integrity verification before creating or activating deployment tickets; recheck at deploy time.

### PF-163 — Test-cycle app boot failure logs a defect after suite completion but is not directly reflected in recorded test counts/status (P2)

**Evidence:** [core/test_framework_integration.py:412-L454](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/test_framework_integration.py#L412). Static finding; impact depends on calling paths and runtime policy. **Recommended remediation:** Add app boot as an explicit test/gate result; invalidate cycle success when app fails to boot; ensure downstream QA reads the failure.

## Batch X file disposition

**57 newly documented:**

**core/ (44):** `core/product_ingestion.py`, `core/product_page.py`, `core/product_plan.py`, `core/progress.py`, `core/project_journal.py`, `core/qa_cycles.py`, `core/qa_intelligence.py`, `core/qa_manifest.py`, `core/qa_report.py`, `core/qir.py`, `core/quality_metrics.py`, `core/reasoning_skills.py`, `core/release_manager.py`, `core/requirement_link.py`, `core/rerun_review.py`, `core/review_ledger.py`, `core/run_breaker.py`, `core/run_plan.py`, `core/service_catalog.py`, `core/signing.py`, `core/sizing.py`, `core/spec_review.py`, `core/squad_manager.py`, `core/stage_paths.py`, `core/status.py`, `core/stop_conditions.py`, `core/target_advisor.py`, `core/target_selector.py`, `core/tech_stack.py`, `core/techstack_guidelines.py`, `core/test_adapters.py`, `core/test_framework_bridge.py`, `core/test_framework_integration.py`, `core/test_matrix.py`, `core/tier_builder.py`, `core/traceability.py`, `core/vcs.py`, `core/vendor_adapters.py`, `core/version_manager.py`, `core/video_generation.py`, `core/views.py`, `core/visual_qa.py`, `core/work_estimate.py`, `core/workflow_docs.py`.

**scripts/ (13):** `scripts/dev/live_monitor.ps1`, `scripts/dev/test_w5.py`, `scripts/dev/test_w7.py`, `scripts/dev/update_dependencies.py`, `scripts/dev/update_iteration_names_budgets.py`, `scripts/dev/update_phases.py`, `scripts/export-diagrams.ps1`, `scripts/gen_model_registry.py`, `scripts/gen_pipeline_reference.py`, `scripts/generate_diagrams.py`, `scripts/pipeline_helpers.py`, `scripts/run_portfolio.py`, `scripts/token-counter.ps1`.

**Four tracked historical backups:** `core/pipeline_executor.py.bak_pre_agent_exec`, `core/pipeline_executor.py.bak_pre_agent_runner`, `core/pipeline_executor.py.bak_pre_llm_extract`, `core/pipeline_executor.py.bak_pre_stage_runner`. Each fetched and inspected for size, header and entrypoint; no active-runtime status inferred.

**Six complete small-file reviews this batch:** `scripts/dev/live_monitor.ps1`, `scripts/dev/test_w5.py`, `scripts/dev/test_w7.py`, `scripts/dev/update_iteration_names_budgets.py`, `scripts/dev/update_phases.py`, `scripts/export-diagrams.ps1`. The remaining 51 new active files received targeted code-path and structural review; the four backups received metadata/structural review only.

## Exact final inventory reconciliation

| Directory | Tracked | Documented/dispositioned | Full-static certified | Not full-static certified |
|---|---:|---:|---:|---:|
| `core/` | 239 | 239 | 13 | 226 |
| `scripts/` | 64 | 64 | 33 | 31 |
| `agents/` | 62 | 62 | 6 | 56 |
| `config/` | 29 | 29 | 21 | 8 |
| **Total** | **394** | **394** | **73** | **321** |

**Audit conclusion:** The revised four-directory inventory is completely accounted for. The comprehensive line-by-line audit is **not complete**; the unreviewed depth is explicitly tracked in the CSV. Historical PF-070–PF-079 details remain unrecovered and historical findings from excluded folders remain in the cumulative report only for context. The audit covers the pinned revision, not the live `develop` branch after that commit.


## Batch Y — full source review and architecture data-folder verification (2026-09-28)

Pinned commit unchanged. Eight additional files were read in full: `core/__init__.py`, `core/agent_hierarchy.py`, `core/agent_requirements.py`, `core/agent_structure.py`, `core/status.py`, `core/requirement_link.py`, `config/agent-capabilities.json`, `config/agent-requirements.json`. These are static certifications, not runtime tests.

Architecture SSOT `docs/productforge_full_architecture.md` lines 287–288: `data/` is Forge-owned backlog and pipeline data; `products/` is per-project runtime artifacts/state/logs. Historical `docs/architecture.md` is marked superseded and was not found at its presumed pinned path.

- **PF-164 P1** `core/__init__.py`: core/__init__.py exports ModelRegistry and select_model_for_agent in __all__, but neither name is imported or defined in this module. A wildcard import can fail with AttributeError. **Fix:** Remove stale exports or import the actual implementation and test import *. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/__init__.py).
- **PF-165 P2** `core/agent_hierarchy.py`: Agent hierarchy merges config and pipeline without rejecting cycles or multiple parents. root_of stops on repeated nodes and can return a non-root member of a cycle; first-parent choice is iteration-dependent. **Fix:** Validate DAG and unique parent at load; reject cycles and conflicting parent mappings. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/agent_hierarchy.py).
- **PF-166 P2** `core/requirement_link.py`: synchronize recomputes traceability coverage_metrics only when new matrix rows are appended. When existing rows change or only index links are added, persisted coverage metrics remain stale. **Fix:** Always recompute coverage from canonical matrix and write if metrics differ. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/requirement_link.py).
- **PF-167 P2** `core/agent_requirements.py`: Config load catches malformed/unreadable agent-requirements.json and silently falls back to an empty config; this can relax required sections and readiness defaults without an explicit configuration failure. **Fix:** Validate and fail closed for mandatory requirements, with explicit diagnostic and safe fallback policy. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/agent_requirements.py).

**Coverage:** 394/394 dispositioned; **81/394 full static review** (core 19, scripts 33, agents 6, config 23); **313** still need deep review or reconciliation. The four tracked pipeline backups are not established active.


---

## Batch Z — deep agent-contract audit (45 files; pinned commit `e7a0dd57`)

**Method:** Retrieved the complete pinned JSON of 45 previously non-certified agents. All 45 JSON contracts were parsed and their entire field sets inspected for tool grants, invocation grants, declared subagents, model tier/pin, allowed/forbidden inputs and outputs. The complete instruction bodies of 10 compact files were also manually inspected; the other 35 received targeted instruction inspection, not full semantic certification. No execution or deployment tests.

**Ten fully inspected:** `agents/community-social.agent.json`, `agents/customer-onboarding.agent.json`, `agents/customer-success.agent.json`, `agents/design_critic.agent.json`, `agents/discovery.agent.json`, `agents/finops.agent.json`, `agents/growth.agent.json`, `agents/legal-privacy.agent.json`, `agents/pricing-strategist.agent.json`, `agents/product-analytics.agent.json`.

**35 additional deep contract reviews (instruction semantics pending):** `agents/a11y-audit.agent.json`, `agents/analyst.agent.json`, `agents/architect.agent.json`, `agents/code-review.agent.json`, `agents/consensus.agent.json`, `agents/content-creator.agent.json`, `agents/content-reader.agent.json`, `agents/design.agent.json`, `agents/devops.agent.json`, `agents/document.agent.json`, `agents/fix.agent.json`, `agents/guardian.agent.json`, `agents/ideation.agent.json`, `agents/implement-api.agent.json`, `agents/implement-db.agent.json`, `agents/implement-logic.agent.json`, `agents/implement-ui.agent.json`, `agents/implement.agent.json`, `agents/inference.agent.json`, `agents/ingestion.agent.json`, `agents/insight-extractor.agent.json`, `agents/iterative_evaluator.agent.json`, `agents/journal-writer.agent.json`, `agents/maintenance.agent.json`, `agents/marketing.agent.json`, `agents/observer.agent.json`, `agents/orchestrator.agent.json`, `agents/package.agent.json`, `agents/performance.agent.json`, `agents/post-production.agent.json`, `agents/pre-production.agent.json`, `agents/presentation-generator.agent.json`, `agents/product-analyzer.agent.json`, `agents/production-deploy.agent.json`, `agents/quality_gate.agent.json`.

### New findings

- **PF-168 P2** `observer.agent.json` and `iterative_evaluator.agent.json`: `model_pin` strings include literal surrounding double quotes (e.g. `"\"openrouter/deepseek/deepseek-chat-v3.1\""`), unlike ordinary provider/model identifiers. Direct model lookup may fail if the resolver does not strip them. Normalize and validate pins at load time. [Pinned observer](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/agents/observer.agent.json) [Pinned iterative_evaluator](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/agents/iterative_evaluator.agent.json)

- **PF-169 P2** `customer-onboarding.agent.json` and `finops.agent.json`: The instructions promise file generation and external cost/support integrations, but both specs declare `tools=[]`. If runtime uses the JSON allowlist, agents cannot perform their advertised file/API operations. Supply least-privilege tools or change these contracts to planning-only. [Pinned customer-onboarding](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/agents/customer-onboarding.agent.json) [Pinned finops](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/agents/finops.agent.json)

- **PF-170 P2** `legal-privacy.agent.json` and `pricing-strategist.agent.json`: Both specify `model_tier=critical` yet hard-pin `opencode/mimo-v2.5`, also used by medium-tier growth and customer-success. A pin-first router could bypass tier-based critical-task model selection. Validate tier/pin compatibility and require explicit documented exceptions. [Pinned legal-privacy](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/agents/legal-privacy.agent.json) [Pinned pricing-strategist](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/agents/pricing-strategist.agent.json)


### Reconfirmed earlier findings (not double-counted)

- PF-130: embedded `edit: deny` / `web: deny` conflicts with JSON `write_file` / `http_get` in community-social, growth, legal-privacy and other agents.

- PF-131: implement agent requires four subagents but `can_invoke=[]`.

- PF-120: orchestrator instructions require delegation but JSON tools/invocation lists are empty.


**Coverage:** 394/394 inventory accounted for; **91/394 full static** (core 19, scripts 33, agents 16, config 23); **303** still need complete deep review/reconciliation. 35/45 Batch Z files are contract-deep, not full instruction-semantic certified.


---

## Batch AA — 40-file deep-review pass (2026-09-28)

**Scope:** 31 `scripts/`, 6 `config/`, 3 `agents/`. All 40 pinned sources retrieved. Nine complete static source reviews; 31 targeted source/contract reviews, including large `scripts/pipeline.py` (2,179 lines), `config/model-catalog.json` (~598 KB, 632 model entries), `config/model-tier.json` (~58 KB), `config/store-registry.json` (~42 KB, 177 stores). **No runtime tests.**

### New findings

- **PF-171 P1 — Dependency audit does not fail CI on invalid DAG.** [https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/dev/audit_dependencies.py#L102] `main()` prints unknown dependencies/cycles collected in `problems`, but has no nonzero return/exit. `deps_of` also removes self-dependencies before checking, so a self-loop is not reported. Return nonzero on errors and retain self-edges for validation.
- **PF-172 P1 — Verification script has no assertions or exit-code checks.** [https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/dev/verify_fixes.py#L1] It prints guideline-loader, model-config and DAG values without comparing to expected outcomes; successful process exit is not evidence fixes worked. Convert to assertions or test framework.
- **PF-173 P1 — Portfolio capacity-check exception permits registration.** [https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/run_portfolio.py#L72] `add` silently ignores errors from `core.capacity.can_add()` then registers the project. If capacity is a hard governance limit, this is fail-open. Distinguish optional advisory capacity from mandatory quotas; fail closed for mandatory limits.
- **PF-174 P2 — Documentation index check mode never fails for missing classification.** [https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/dev/gen_docs_index.py#L581] `--check` prints `unclassified docs` and `not-referenced docs` but returns zero regardless; automation cannot gate on its output.
- **PF-175 P1 — Source migration proceeds without freeze manifest and overwrites in place.** [https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/dev/migrate_paths.py#L73] Failure to read `config/legacy-frozen.json` silently sets an empty exclusion set, then rewrites matched files directly without atomic replacement, backup or syntax validation. Running this maintenance script can modify frozen code.

### Existing findings reconfirmed (not double-counted)

- PF-094: `scripts/dev/build_release.py` only checks five hardcoded operator route prefixes.
- PF-096: `scripts/dev/wired_audit.py` can baseline missing/corrupt manifests.
- PF-135: `scripts/dev/extract_llm_client.py` performs brittle direct source rewrite.
- PF-136: `scripts/dev/e2e_backlog_check.py` removes fixed scratch project and mutates the global backlog.
- PF-169 extended: `content-creator` and `content-reader` agent instructions require reading/writing artifacts and pipeline state, but JSON `tools=[]`. Tool provision may exist outside this manifest; verify runner wiring before treating as runtime failure.

### Batch AA exact inventory

**Scripts (31):** `scripts/dev/audit_dependencies.py`, `scripts/dev/audit_hardcoding.py`, `scripts/dev/backfill_item_context.py`, `scripts/dev/build_agent_specs.py`, `scripts/dev/build_release.py`, `scripts/dev/check_tier_models.py`, `scripts/dev/e2e_backlog_check.py`, `scripts/dev/extend_schemas.py`, `scripts/dev/extract_llm_client.py`, `scripts/dev/extract_table.py`, `scripts/dev/gen_backlog_summary.py`, `scripts/dev/gen_docs_index.py`, `scripts/dev/generate_agent_cards.py`, `scripts/dev/generate_model_analysis.py`, `scripts/dev/generate_report.py`, `scripts/dev/invocation_audit.py`, `scripts/dev/migrate_backlog.py`, `scripts/dev/migrate_paths.py`, `scripts/dev/update_dependencies.py`, `scripts/dev/verify_fixes.py`, `scripts/dev/wired_audit.py`, `scripts/dev/workflow_matrix_check.py`, `scripts/gen_model_registry.py`, `scripts/gen_pipeline_reference.py`, `scripts/generate_diagrams.py`, `scripts/pipeline.py`, `scripts/pipeline_helpers.py`, `scripts/run_pipeline.py`, `scripts/run_portfolio.py`, `scripts/setup/setup_target.py`, `scripts/token-counter.ps1`.

**Config (6):** `config/file-manifest.json`, `config/model-catalog.json`, `config/model-tier.json`, `config/store-registry.json`, `config/techstack-catalog.json`, `config/test-matrix.json`.

**Agents (3):** `agents/analyst.agent.json`, `agents/content-creator.agent.json`, `agents/content-reader.agent.json`.

**Certified full static this batch (9):** `agents/content-creator.agent.json`, `agents/content-reader.agent.json`, `scripts/dev/audit_dependencies.py`, `scripts/dev/audit_hardcoding.py`, `scripts/dev/build_release.py`, `scripts/dev/e2e_backlog_check.py`, `scripts/dev/extend_schemas.py`, `scripts/dev/extract_table.py`, `scripts/dev/verify_fixes.py`.

**Cumulative:** 394/394 inventory accounted for; **100/394 certified full static** (core 19, scripts 40, agents 18, config 23); **294** not yet certified. Finding register through PF-175, with historical PF-070–079 detail reconciliation outstanding.


## Batch AB — 50-file follow-up: 44 agent contracts + 6 configuration files

Pinned commit: `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`. This batch retrieved and parsed 44 previously uncertified agent JSON files and six previously uncertified configuration JSON files. All 50 received structural/contract examination and targeted instruction checks. Five compact agent files received complete source and instruction review; the other 45 **are not certified full deep reviews**. This is static analysis only; no runtime or integration tests.

### New findings

- **PF-176 P1 — Design review instructions permit incomplete reading of long inputs.** `agents/review.agent.json` instructs the reviewer to read all three inputs in full, then says that if any exceeds 500 lines it should read the first 300 lines and search selected sections. This can miss requirements or NFRs outside the sampled sections while allowing `APPROVED`. Require complete input coverage or explicit `INCOMPLETE` verdict. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/agents/review.agent.json)
- **PF-177 P1 — Architecture agent has contradictory human-decision instructions.** `agents/architect.agent.json` instruction line 44 requires asking the user to choose each service before writing architecture, but line 467 says the agent is the decision-maker and does not need approval. Reconcile the mandatory selection/approval policy in machine-readable rules and tests. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/agents/architect.agent.json)
- **PF-178 P1 — Production deployment agent declares command execution without an explicit approval contract in its card.** `agents/production-deploy.agent.json` grants `run_command` and instructs `kubectl apply` to production but has no explicit approval/human-gate wording in the agent instructions. Verify independent runtime HIL enforcement before treating this as an exploitable bypass. Enforce signed approval at the deployment tool boundary. Related to PF-140. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/agents/production-deploy.agent.json)
- **PF-179 P2 — Model catalog includes 110 records with unknown context-window and tool capability metadata.** `config/model-catalog.json` has 632 models; 110 entries have `context_window: null` and `tools: null`. This is metadata incompleteness, not evidence that model routing fails; require unknown-capability rejection for capability-critical tasks and test router behavior. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/config/model-catalog.json)

### Existing findings reconfirmed

PF-131: `implement.agent.json` requires four sub-agent invocations but `can_invoke=[]`. PF-168: quoted `model_pin` for observer and iterative_evaluator (also observed in static_verifier). PF-130: tool declarations and embedded permission denials conflict for sales-crm. PF-169: several text/knowledge agents require file and pipeline writes but declare `tools=[]`. The batch did not prove actual runtime bypass; enforcement may occur elsewhere.

### Exact batch disposition

44 agent files: `agents/a11y-audit.agent.json`, `agents/analyst.agent.json`, `agents/architect.agent.json`, `agents/code-review.agent.json`, `agents/consensus.agent.json`, `agents/design.agent.json`, `agents/devops.agent.json`, `agents/document.agent.json`, `agents/fix.agent.json`, `agents/guardian.agent.json`, `agents/ideation.agent.json`, `agents/implement-api.agent.json`, `agents/implement-db.agent.json`, `agents/implement-logic.agent.json`, `agents/implement-ui.agent.json`, `agents/implement.agent.json`, `agents/inference.agent.json`, `agents/ingestion.agent.json`, `agents/insight-extractor.agent.json`, `agents/iterative_evaluator.agent.json`, `agents/journal-writer.agent.json`, `agents/maintenance.agent.json`, `agents/marketing.agent.json`, `agents/observer.agent.json`, `agents/orchestrator.agent.json`, `agents/package.agent.json`, `agents/performance.agent.json`, `agents/post-production.agent.json`, `agents/pre-production.agent.json`, `agents/presentation-generator.agent.json`, `agents/product-analyzer.agent.json`, `agents/production-deploy.agent.json`, `agents/quality_gate.agent.json`, `agents/researcher.agent.json`, `agents/review.agent.json`, `agents/sales-crm.agent.json`, `agents/scout.agent.json`, `agents/security-audit.agent.json`, `agents/security.agent.json`, `agents/static_verifier.agent.json`, `agents/strategist.agent.json`, `agents/summary-creator.agent.json`, `agents/theme-analyzer.agent.json`, `agents/validate.agent.json`.

Six config files: `config/file-manifest.json`, `config/model-catalog.json`, `config/model-tier.json`, `config/store-registry.json`, `config/techstack-catalog.json`, `config/test-matrix.json`.

**Five newly certified full static:** `agents/observer.agent.json`, `agents/sales-crm.agent.json`, `agents/implement-db.agent.json`, `agents/implement-api.agent.json`, `agents/review.agent.json`. **Cumulative 105/394 fully reviewed; 289 remain** (core 220, scripts 24, agents 39, config 6). All 394 accounted for in inventory; a complete deep review of all files has not been achieved. Historical PF-070–PF-079 details still need reconciliation.


## Batch AC — 50-file mixed-directory static review

Pinned commit: `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`. Twenty core files, fifteen agent JSON files, five config JSON files and ten scripts retrieved and inspected. **13 complete source static reviews**; remaining 37 received structural/contract plus targeted security review, not full-line certification. No runtime or integration tests.

### New findings

- **PF-180 P1 — Billing reports successful checkout after control-plane provisioning failure.** `core/billing.py:39–58`. checkout suppresses exceptions from create_tenant/upsert_user and returns ok=True with license key. Persist separate provisioning state, retry idempotently, return partial failure. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/billing.py#L39-L58).
- **PF-181 P1 — Adoption can silently skip source files and still report success.** `core/adopt_project.py:98–134`. Per-item copy exceptions are suppressed; existing destination directories are skipped; result has no copy-failure count. Validate name/path, report failed and skipped files and require manifest reconciliation. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/adopt_project.py#L98-L134).
- **PF-182 P1 — Audit trail uses non-atomic sequential IDs and direct JSON overwrite.** `core/audit_trail.py:85–119`. AUD-{len(entries)+1} is per-instance and _save_entries directly truncates/replaces JSON; concurrent writers can collide and lose entries. Use UUID or transactional IDs and append-only or locked atomic persistence. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/audit_trail.py#L85-L119).
- **PF-183 P1 — Budget allocation and protection suppress state persistence errors.** `core/budget_allocator.py:107–130`. _load and _save catch all exceptions; budget_protection.py has same pattern at 151–172. Enforce fail-closed reservation/commit behavior and report storage failures. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/budget_allocator.py#L107-L130).
- **PF-184 P1 — Context-policy agent defaults override project agent policy.** `core/context_policy.py:58–68`. policy_for applies project_overrides[project][agents][agent_id] and then cfg[agents][agent_id], so global agent rules overwrite project-specific agent settings. Establish documented precedence and tests. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/context_policy.py#L58-L68).
- **PF-185 P2 — Agent model overrides can lose concurrent writes.** `core/agent_model_override.py:21–67`. set/clear read then rewrite shared JSON via fixed .tmp without locking; concurrent calls can lose updates or race on temp file. Add lock and unique temp/atomic replace. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/agent_model_override.py#L21-L67).
- **PF-186 P2 — Architecture diagrams can contain invalid XML or colliding IDs.** `core/architecture_diagram.py:26–81`. Unescaped component labels are interpolated into mxCell XML and Mermaid labels; slug collisions create duplicate node IDs. Escape XML and Mermaid, assign unique IDs, validate output. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/architecture_diagram.py#L26-L81).
- **PF-187 P2 — Generated functional specs can remain stale after title/link changes.** `core/change_spec.py:55–112`. Idempotence hashes only body, so changes to title/type/status/links do not regenerate; backlog.link failure suppressed. Hash all relevant fields and surface link failure. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/change_spec.py#L55-L112).
- **PF-188 P2 — Token counter treats unrecognized priced models as zero cost.** `scripts/token-counter.ps1:29–77`. Unknown model and missing pricing both leave Cost=0, and provider prefix stripping only recognizes opencode/. Emit unknown/unpriced state rather than financial zero and resolve model/provider IDs canonically. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/token-counter.ps1#L29-L77).
- **PF-189 P2 — Dependency update script rewrites pipeline definition without validation or atomic write.** `scripts/dev/update_dependencies.py:1–103`. Hardcoded stage map silently skips unknown stages, rewrites agent dependencies and directly truncates pipeline-definition.json. Require schema/DAG checks, dry run and atomic backup/replace. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/dev/update_dependencies.py#L1-L103).
- **PF-190 P2 — Maintenance and marketing agent capabilities do not match declared outputs.** `agents/maintenance.agent.json:1–103`. Both maintenance and marketing cards declare tools=[] but promise persistent artifact writes and external integrations; runtime may supply other mechanisms, which must be verified. Align machine-readable capability declarations with actual execution contract. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/agents/maintenance.agent.json#L1-L103).

### Cross-module observations and limitations

PF-183 overlaps the earlier silent-persistence family; PF-185 overlaps other read-modify-write races; PF-190 extends PF-169. The 20 core paths were inspected structurally and for risky execution/persistence paths; only six small core modules were certified complete. The large configuration files (`model-tier`, `store-registry`, `file-manifest`) received targeted checks only. The current snapshot is not evidence of runtime exploitability.

### Exact batch file inventory

**core (20):** `core/adopt_project.py`, `core/agent_card_loader.py`, `core/agent_migrator.py`, `core/agent_model_override.py`, `core/agent_rules.py`, `core/agent_summaries.py`, `core/architecture_diagram.py`, `core/artifact_formats.py`, `core/artifact_registry.py`, `core/audit_trail.py`, `core/billing.py`, `core/budget.py`, `core/budget_allocator.py`, `core/budget_conservation.py`, `core/budget_planner.py`, `core/budget_protection.py`, `core/capability_bridge.py`, `core/change_registry.py`, `core/change_spec.py`, `core/context_policy.py`.

**agents (15):** `agents/maintenance.agent.json`, `agents/marketing.agent.json`, `agents/product-analyzer.agent.json`, `agents/guardian.agent.json`, `agents/analyst.agent.json`, `agents/consensus.agent.json`, `agents/insight-extractor.agent.json`, `agents/journal-writer.agent.json`, `agents/strategist.agent.json`, `agents/summary-creator.agent.json`, `agents/theme-analyzer.agent.json`, `agents/scout.agent.json`, `agents/researcher.agent.json`, `agents/document.agent.json`, `agents/fix.agent.json`.

**config (5):** `config/file-manifest.json`, `config/model-tier.json`, `config/store-registry.json`, `config/techstack-catalog.json`, `config/test-matrix.json`.

**scripts (10):** `scripts/dev/backfill_item_context.py`, `scripts/dev/check_tier_models.py`, `scripts/dev/gen_backlog_summary.py`, `scripts/dev/generate_agent_cards.py`, `scripts/dev/invocation_audit.py`, `scripts/dev/update_dependencies.py`, `scripts/gen_model_registry.py`, `scripts/gen_pipeline_reference.py`, `scripts/pipeline_helpers.py`, `scripts/token-counter.ps1`.

**Newly full-source static reviewed (13):** `agents/maintenance.agent.json`, `agents/marketing.agent.json`, `config/techstack-catalog.json`, `config/test-matrix.json`, `core/agent_model_override.py`, `core/agent_summaries.py`, `core/architecture_diagram.py`, `core/billing.py`, `core/change_spec.py`, `core/context_policy.py`, `scripts/dev/gen_backlog_summary.py`, `scripts/dev/update_dependencies.py`, `scripts/token-counter.ps1`.

**Cumulative full-source static review:** 118/394; **276 remaining**. All 394 have inventory dispositions. No execution tests.


## Batch AD — 50-file cross-directory static audit (2026-09-28)

**Pinned commit:** `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`. 20 core, 15 agents, four config, 11 scripts. All 50 retrieved from pinned source and structurally/targetedly inspected; five short files fully read and certified. No execution tests. Large 24,058-line model catalog and 1,445-line compliance checker were NOT line-by-line certified.

### New findings

- **PF-191 P1 — Control-plane tenant registration overwrites existing tenant and resets created_at.** `core/control_plane.py:75`. create_tenant uses INSERT OR REPLACE, allowing an existing tenant ID to be replaced and tier/status/creation time reset. Enforce explicit create-vs-update and authorization; preserve creation timestamp. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/control_plane.py#L75).
- **PF-192 P1 — Invalid session expiry fails open at data-access boundary.** `core/control_plane.py:114`. get_session catches expiry parse errors and returns the session record. Reject malformed timestamps and remove expired or corrupt sessions. Downstream authentication enforcement must also be verified. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/control_plane.py#L114).
- **PF-193 P1 — Credential registry silently disables provider-budget caps on corrupt config.** `core/credentials.py:31`. _config returns {} on unreadable/malformed provider-keys.json; check_budget then treats caps as absent and permits spending. Validate mandatory budget config and fail closed in paid execution. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/credentials.py#L31).
- **PF-194 P2 — Context preflight can approve compact mode even when instructions exceed configured input cap.** `core/context_preflight.py:13`. Hard-fail compares instructions only against 80% model window, not lower max_input_tokens. It returns ok=True compact_context although instructions alone cannot fit the configured input budget. Check instructions against effective budget. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/context_preflight.py#L13).
- **PF-195 P1 — Backlog migration suppresses failures and exits successfully.** `scripts/dev/migrate_backlog.py:33`. Feature and defect migration failures are caught and discarded; conversation failure is only printed and main always returns 0. Emit per-project failures and nonzero exit on incomplete migration. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/dev/migrate_backlog.py#L33).
- **PF-196 P1 — Agent-spec generator can grant command/write tools without permission review.** `scripts/dev/build_agent_specs.py:75`. FORCE_TOOLS assigns run_command and write_file to eight code agents when source card has no tools. Reconcile with deny policy and require explicit permission authorization before generating elevated tools. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/dev/build_agent_specs.py#L75).
- **PF-197 P2 — Agent-spec generation is working-directory dependent.** `scripts/dev/build_agent_specs.py:29`. CARDS_DIR and OUT_DIR are relative paths and script uses sys.path root but not anchored input/output paths; running outside repository can silently create agent specs in another directory. Anchor paths to _PF_ROOT and validate source presence. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/dev/build_agent_specs.py#L29).

### Cross-module observations

PF-191/PF-192 require authentication/authorization caller-path verification; PF-193 is a fail-open budget-configuration path; PF-195/PF-196 affect audit and tool policy. Previously reported PF-001–PF-190 are retained. Prior agent tool/permission conflicts were reconfirmed, not counted as new findings.

**core (20):** `core/agent_ledger.py`, `core/agent_memory.py`, `core/agent_messenger.py`, `core/agent_readiness.py`, `core/agent_runtime.py`, `core/agent_spec.py`, `core/agent_tool_loop.py`, `core/artifact_store.py`, `core/backlog.py`, `core/budget_tracker.py`, `core/build_utility.py`, `core/call_ledger.py`, `core/circuit_breaker.py`, `core/close_loop.py`, `core/code_executor.py`, `core/compliance_check.py`, `core/compliance_verifier.py`, `core/context_preflight.py`, `core/control_plane.py`, `core/credentials.py`.

**agents (15):** `agents/a11y-audit.agent.json`, `agents/analyst.agent.json`, `agents/architect.agent.json`, `agents/code-review.agent.json`, `agents/consensus.agent.json`, `agents/design.agent.json`, `agents/devops.agent.json`, `agents/document.agent.json`, `agents/fix.agent.json`, `agents/guardian.agent.json`, `agents/ideation.agent.json`, `agents/implement-logic.agent.json`, `agents/implement-ui.agent.json`, `agents/implement.agent.json`, `agents/inference.agent.json`.

**config (4):** `config/file-manifest.json`, `config/model-catalog.json`, `config/model-tier.json`, `config/store-registry.json`.

**scripts/dev (11):** `scripts/dev/backfill_item_context.py`, `scripts/dev/build_agent_specs.py`, `scripts/dev/check_tier_models.py`, `scripts/dev/extract_llm_client.py`, `scripts/dev/gen_docs_index.py`, `scripts/dev/generate_agent_cards.py`, `scripts/dev/generate_model_analysis.py`, `scripts/dev/generate_report.py`, `scripts/dev/invocation_audit.py`, `scripts/dev/migrate_backlog.py`, `scripts/dev/migrate_paths.py`.

**Full-source certified in AD (5):** `core/context_preflight.py`, `core/control_plane.py`, `core/credentials.py`, `scripts/dev/build_agent_specs.py`, `scripts/dev/migrate_backlog.py`.

**Cumulative full-static certification:** 123/394 (core 28, scripts 45, agents 25, config 25); 271 pending. All 394 inventory-dispositioned.


## Batch AE — core-first 50-file source review (2026-09-28)

Pinned commit: `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`. 38 core, 7 agents, 4 scripts, 1 config. **Seven complete source-level static reviews** and **43 targeted source/contract reviews**; no runtime tests. Earlier findings PF-001–PF-197 retained.

### PF-198 — P1: High-priority context can exceed per-type budget

**File:** `core/context_engine.py`. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/context_engine.py#L110-L146). add_context() permits oversized items whenever priority > current budget priority, increments current_tokens past max, and prepare_context() can exceed its total cap. Reject/compact or evict before admission.

### PF-199 — P1: High-severity violations can continue without human approval

**File:** `core/compliance_action_handler.py`. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/compliance_action_handler.py#L145-L196). After one retry, auto_approve=True returns continue even for HIGH violations. Enforce immutable high/critical blocking policy independent of convenience auto-approval.

### PF-200 — P1: Caller fields can overwrite canonical event identity

**File:** `core/events.py`. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/events.py#L30-L41). emit() builds type, timestamp, run_id, stage and agent, then ev.update(fields); fields passed via **kwargs can overwrite type/ts. Reserve canonical fields and validate event type.

### PF-201 — P1: Atomic rename is not concurrency-safe with fixed temporary filename

**File:** `core/forge_store.py`. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/forge_store.py#L47-L92). _wj() always writes p+.tmp; parallel writers can race or replace each other and read-modify-write update_state/add_goal has no lock. Use unique temp files and serialized writes.

### PF-202 — P1: Failed stage invalidation does not stop enhancement rerun

**File:** `core/enhance.py`. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/enhance.py#L46-L58). apply_and_run() catches invalidate_for_rerun() failure, prints it, then proceeds to execute_pipeline(); return failure instead of running stale state.

### PF-203 — P1: Research and scout cards require state writes but lack write_file

**File:** `agents/researcher.agent.json;agents/scout.agent.json`. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/agents/researcher.agent.json). Both specify writing agent-audit.md and pipeline.json but only grant http_get, read_file and list_dir. Grant scoped writes or assign state persistence to the orchestrator.

### PF-204 — P2: Context truncation can exceed declared token budget

**File:** `core/context_manager.py`. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/context_manager.py#L125-L158). build_context_package() sets tokens_used=max_input_tokens after appending an extra truncation marker; when remaining=0, it still appends the marker and can exceed budget. Reserve marker tokens and omit empty remainder.

### PF-205 — P2: Agent card YAML parser and validator do not enforce nested permissions

**File:** `core/agent_card_loader.py`. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/agent_card_loader.py#L114-L263). _parse_frontmatter() handles only flat key/value and simple lists; _validate() checks identity and optional sections, not nested permission/tool policy. Use real YAML parser and schema validation.

### PF-206 — P1: Deployment vendor adapter exceptions are silently omitted from verdict

**File:** `core/deploy_providers.py`. [Pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/deploy_providers.py#L390-L437). run_deploy_up() swallows run_vendors() exceptions, then calculates pass using available steps; vendor verification can disappear. Record mandatory adapter failure as blocking.

### Exact batch file disposition

**core (38):** `agent_card_loader.py`, `agent_migrator.py`, `agent_rules.py`, `artifact_formats.py`, `business_models_kb.py`, `business_skills_selector.py`, `capability_bridge.py`, `code_analyzer.py`, `compliance_action_handler.py`, `context_engine.py`, `context_manager.py`, `conversation_compiler.py`, `cost_kpi.py`, `cost_modeling.py`, `cross_project_learning.py`, `cross_review.py`, `customer_onboarding.py`, `dag_executor.py`, `dead_letter_queue.py`, `defect_loop.py`, `deploy_providers.py`, `design_critic.py`, `design_tokens.py`, `diagram_render.py`, `discovery_engine.py`, `discovery_panel.py`, `docker_compose_generator.py`, `domain_research.py`, `enhance.py`, `env_flags.py`, `events.py`, `feature_flags.py`, `finops.py`, `forge_constitution.py`, `forge_store.py`, `git_manager.py`, `interactive.py`, `lock_manager.py`.

**agents (7):** `ingestion.agent.json`, `insight-extractor.agent.json`, `journal-writer.agent.json`, `researcher.agent.json`, `scout.agent.json`, `security-audit.agent.json`, `validate.agent.json`.

**scripts/dev (4):** `backfill_item_context.py`, `check_tier_models.py`, `generate_agent_cards.py`, `invocation_audit.py`.

**config (1):** `file-manifest.json`.

**New full-source static certification (7):** `product-forge/core/context_manager.py`, `product-forge/core/dead_letter_queue.py`, `product-forge/core/enhance.py`, `product-forge/core/env_flags.py`, `product-forge/core/events.py`, `product-forge/core/feature_flags.py`, `product-forge/core/forge_store.py`.

**Cumulative:** 130/394 fully source-reviewed; 264 outstanding. By folder: core 35/239, agents 25/62, scripts 45/64, config 25/29. All 394 inventory-dispositioned. No runtime tests.


## Batch AF — complete source static review (2026-09-28; first 25 of 50 requested)

**Pinned commit:** `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`. **25 newly fully source-reviewed**, no partial reviews counted toward completion; baseline 130 → **155/394**, **239 outstanding**. All 25 are `core/` files. Static inspection includes full source and error/data/control-flow; no runtime or integration testing. This is a partial delivery against the requested 50 fully completed files; 25 additional complete reviews are still required.

### Exact complete file list

- [`product-forge/core/persona.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/persona.py)
- [`product-forge/core/net_ports.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/net_ports.py)
- [`product-forge/core/modality.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/modality.py)
- [`product-forge/core/ops_phase.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/ops_phase.py)
- [`product-forge/core/log_router.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/log_router.py)
- [`product-forge/core/insights.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/insights.py)
- [`product-forge/core/knowledge_refresh.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/knowledge_refresh.py)
- [`product-forge/core/design_tokens.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/design_tokens.py)
- [`product-forge/core/nfr_coverage.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/nfr_coverage.py)
- [`product-forge/core/signing.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/signing.py)
- [`product-forge/core/reasoning_skills.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/reasoning_skills.py)
- [`product-forge/core/notification_system.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/notification_system.py)
- [`product-forge/core/maintenance.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/maintenance.py)
- [`product-forge/core/loop_modes.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/loop_modes.py)
- [`product-forge/core/forge_constitution.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/forge_constitution.py)
- [`product-forge/core/cost_kpi.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/cost_kpi.py)
- [`product-forge/core/business_models_kb.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/business_models_kb.py)
- [`product-forge/core/finops.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/finops.py)
- [`product-forge/core/dashboard_archetypes.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/dashboard_archetypes.py)
- [`product-forge/core/diagram_render.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/diagram_render.py)
- [`product-forge/core/sizing.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/sizing.py)
- [`product-forge/core/tier_builder.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/tier_builder.py)
- [`product-forge/core/target_selector.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/target_selector.py)
- [`product-forge/core/target_advisor.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/target_advisor.py)
- [`product-forge/core/work_estimate.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/work_estimate.py)

### New findings (PF-207–PF-224)

- **PF-207 P1** [`core/forge_constitution.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/forge_constitution.py): check_rule returns satisfied=True for every enabled rule without evaluating context. Implement per-rule predicates and test denied/allowed cases.
- **PF-208 P1** [`core/maintenance.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/maintenance.py): run_health_check populates fixed healthy statuses and fabricated CPU/memory/disk/latency/error metrics; open issues alone determine degradation. Replace with real probes and unknown status on unavailable telemetry.
- **PF-209 P1** [`core/loop_modes.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/loop_modes.py): time_based and count_based loops return success=True after caught action exceptions; time_based lacks max_iterations guard; count_based accepts negative count. Track failures and enforce caps.
- **PF-210 P1** [`core/insights.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/insights.py): promote_to_backlog sets item_id on in-memory insights but then writes _read() (fresh disk data), losing promoted IDs. Persist modified records and make promotion idempotent.
- **PF-211 P1** [`core/ops_phase.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/ops_phase.py): monitor treats defect retrieval failures as zero defects and can report healthy; maintenance swallows backlog creation errors. Represent unknown health and propagate partial failure.
- **PF-212 P2** [`core/net_ports.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/net_ports.py): resolve_app_port converts preferred to int after pick_free_port handled invalid preferred; malformed config can raise ValueError; free-port probing also has TOCTOU reservation gap.
- **PF-213 P2** [`core/notification_system.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/notification_system.py): notification IDs use len+1, collide after clear_old and across writers; JSON writes are non-atomic and project path is not locally constrained.
- **PF-214 P2** [`core/nfr_coverage.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/nfr_coverage.py): coverage is credited when an NFR/FR identifier merely appears anywhere in test source; does not prove executable assertions, execution or passing tests.
- **PF-215 P2** [`core/signing.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/signing.py): resolve accepts configured key_id or env import without verifying secret key is present; can label signing source available before a usable signing key is established.
- **PF-216 P2** [`core/tier_builder.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/tier_builder.py): recommend() indexes ranked[0] without guarding empty candidate list; model scoring selects first fit without cost/speed tiebreak despite documented claim.
- **PF-217 P2** [`core/target_advisor.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/target_advisor.py): mobile surface recommends command target absent from target_selector CATALOG, so required_inputs and target catalog contract are inconsistent.
- **PF-218 P2** [`core/finops.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/finops.py): over-budget optimization estimated_savings uses negative remaining*0.10; report can show negative savings for critical budget alerts.
- **PF-219 P2** [`core/sizing.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/sizing.py): when microservices are inferred with fewer than 3 parsed service names, n=max(...,3) but iteration uses nonempty services list, creating fewer units than minimum.
- **PF-220 P2** [`core/reasoning_skills.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/reasoning_skills.py): decision_matrix assigns all options 0.5 for all criteria and recommends first option unconditionally; confidence is hard-coded 0.8 for all skills. Return unscored template until evaluated.
- **PF-221 P2** [`core/work_estimate.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/work_estimate.py): save silently swallows persistence failure; estimate_all returns estimates as though persisted; fixed temporary path also races concurrent writers.
- **PF-222 P2** [`core/knowledge_refresh.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/knowledge_refresh.py): _load_catalog silently replaces corrupt catalog with fresh empty default and seed_from_tech_stack can overwrite the original, losing approved entries; fail closed on corruption.
- **PF-223 P2** [`core/diagram_render.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/diagram_render.py): _run returns True regardless of subprocess return code; output magic check prevents most false positives but stale files from prior runs can be accepted. Require returncode==0 and fresh output.
- **PF-224 P2** [`core/log_router.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/log_router.py): log_event and update_index suppress all errors; index JSON is overwritten non-atomically and extra can replace canonical run_id/logs fields.

**Prior findings retained.** Duplicate issues (e.g. non-atomic JSON, swallowed errors) are documented here only where the reviewed module has its own independently affected state.


## Batch AG — complete-source review plus separate agent contract inspection (2026-09-28)

**Pinned commit:** `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`. **14 complete deep static reviews** of core source files; **37 additional agent JSON contract inspections** (all JSON parsed and structural/mandatory instruction constraints inspected, but *not* full static certified). **51 distinct paths examined; do not call this a 40–50 fully completed deep-review batch.** Cumulative **169/394** full-static certified (core 74/239, scripts 45/64, agents 25/62, config 25/29); **225** remain. No runtime tests executed.

### Fully source-reviewed files
- `product-forge/core/audit_trail.py`
- `product-forge/core/docker_compose_generator.py`
- `product-forge/core/iteration_planner.py`
- `product-forge/core/budget_conservation.py`
- `product-forge/core/change_registry.py`
- `product-forge/core/orchestrator/__init__.py`
- `product-forge/core/orchestrator/types.py`
- `product-forge/core/orchestrator/phasing.py`
- `product-forge/core/paths.py`
- `product-forge/core/run_status.py`
- `product-forge/core/orchestrator/artifacts_map.py`
- `product-forge/core/skill_contracts.py`
- `product-forge/core/orchestrator/status.py`
- `product-forge/core/llm_error_handler.py`

### Agent contract-inspected files (not fully certified)
- `product-forge/agents/a11y-audit.agent.json`
- `product-forge/agents/analyst.agent.json`
- `product-forge/agents/architect.agent.json`
- `product-forge/agents/code-review.agent.json`
- `product-forge/agents/consensus.agent.json`
- `product-forge/agents/design.agent.json`
- `product-forge/agents/devops.agent.json`
- `product-forge/agents/document.agent.json`
- `product-forge/agents/fix.agent.json`
- `product-forge/agents/guardian.agent.json`
- `product-forge/agents/ideation.agent.json`
- `product-forge/agents/implement-logic.agent.json`
- `product-forge/agents/implement-ui.agent.json`
- `product-forge/agents/implement.agent.json`
- `product-forge/agents/inference.agent.json`
- `product-forge/agents/ingestion.agent.json`
- `product-forge/agents/insight-extractor.agent.json`
- `product-forge/agents/iterative_evaluator.agent.json`
- `product-forge/agents/journal-writer.agent.json`
- `product-forge/agents/orchestrator.agent.json`
- `product-forge/agents/package.agent.json`
- `product-forge/agents/performance.agent.json`
- `product-forge/agents/post-production.agent.json`
- `product-forge/agents/pre-production.agent.json`
- `product-forge/agents/presentation-generator.agent.json`
- `product-forge/agents/product-analyzer.agent.json`
- `product-forge/agents/production-deploy.agent.json`
- `product-forge/agents/quality_gate.agent.json`
- `product-forge/agents/researcher.agent.json`
- `product-forge/agents/scout.agent.json`
- `product-forge/agents/security-audit.agent.json`
- `product-forge/agents/security.agent.json`
- `product-forge/agents/static_verifier.agent.json`
- `product-forge/agents/strategist.agent.json`
- `product-forge/agents/summary-creator.agent.json`
- `product-forge/agents/theme-analyzer.agent.json`
- `product-forge/agents/validate.agent.json`

### New findings
- **PF-225 P1** [`core/docker_compose_generator.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/docker_compose_generator.py): Generated Compose sets POSTGRES_PASSWORD to project name and offers a predictable default JWT_SECRET_KEY; database/cache ports bind host interfaces without a local-only default. Never emit deployable insecure defaults; require secret references and safe port bindings.
- **PF-226 P1** [`core/llm_error_handler.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/llm_error_handler.py): handle_error appends asdict(LLMError) with error_type as Enum, then json.dump; standard json encoder cannot serialize Enum, so the first error cannot be persisted and handle_error raises. Serialize error_type.value and add round-trip validation.
- **PF-227 P1** [`core/paths.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/paths.py): products(project) joins caller-controlled project and path parts without containment validation; absolute paths and parent traversal can escape PRODUCTS_DIR if passed through from untrusted project identifiers. Validate resolved containment at trust boundaries.
- **PF-228 P1** [`core/run_status.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/run_status.py): _save suppresses all JSON write and mirror failures; update returns successful-looking state even if neither run-status.json nor PROJECT-STATUS.md persisted. Raise or return explicit persistence status; add atomic locking.
- **PF-229 P1** [`core/change_registry.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/change_registry.py): ChangeRegistry stores changes only in memory; restart loses all changes and approvals. analyze_impact calculates risk into analysis.risk_level but recommendations inspect change.risk_level, which may be stale or low, omitting high-risk controls.
- **PF-230 P2** [`core/iteration_planner.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/iteration_planner.py): group_by_epic sorts features by epic but first-fit distributes individual features across least-loaded iterations, so epics are not kept together despite the documented grouping promise. Enforce epic grouping as an atomic scheduling unit or rename behavior.
- **PF-231 P1** [`core/skill_contracts.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/skill_contracts.py): _load_all reconstructs SkillContract(**data) but leaves nested inputs/outputs/quality_checks as dictionaries rather than SkillInput/SkillOutput/SkillCheck objects; loaded contracts differ from newly registered typed contracts. Compose silently drops unknown dependencies and lacks cycle handling.
- **PF-232 P2** [`core/audit_trail.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/audit_trail.py): Sequential len(entries)+1 IDs and whole-file JSON overwrite have no inter-process lock or atomic replace; concurrent writers can lose entries or duplicate IDs. audit-trail.json load errors also abort initialization.
- **PF-233 P1** [`agents/architect.agent.json`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/agents/architect.agent.json): Architect must read guidelines and produce architecture.md/drawio, but tools=[] and can_invoke=[]; the declared contract cannot independently perform required read/write operations. Same gap present in design and ideation; enforce runtime tool contract or explicitly separate orchestration.
- **PF-234 P1** [`agents/orchestrator.agent.json`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/agents/orchestrator.agent.json): Coordinator instructs Task-tool delegation and updating pipeline.json after every agent, yet tools=[] and can_invoke=[]; role text and executable permissions conflict. Confirm intended judgment-only contract and remove executable instructions or grant scoped delegation through policy.

**Next:** do not advance agent full certification until full instruction-body semantics, source card alignment, runtime tool policy and integration are verified. Runtime tests and fix verification remain pending.


## Batch AH — mixed-source audit, full vs targeted evidence separated (2026-09-28)

**Pinned commit:** `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`. **40 distinct files examined**: 20 core, 10 scripts, 10 agents. **12 complete static source reviews** (7 core, 5 scripts), **28 targeted source/contract reviews only**. Cumulative **181/394** certified (core 81/239, scripts 50/64, agents 25/62, config 25/29); **213** pending. No runtime tests. The request for 40–50 *complete* deep reviews remains outstanding; targeted inspections are not counted as completed.

### Fully source-reviewed paths
- `product-forge/core/artifact_registry.py`
- `product-forge/core/budget.py`
- `product-forge/core/compliance_action_handler.py`
- `product-forge/core/model_gate.py`
- `product-forge/core/orchestration_context.py`
- `product-forge/core/orchestrator/checkpoint.py`
- `product-forge/core/run_guard.py`
- `product-forge/scripts/dev/backfill_item_context.py`
- `product-forge/scripts/dev/extract_llm_client.py`
- `product-forge/scripts/dev/invocation_audit.py`
- `product-forge/scripts/generate_diagrams.py`
- `product-forge/scripts/setup/setup_target.py`

### Targeted paths (not full certified)
- `product-forge/agents/a11y-audit.agent.json`
- `product-forge/agents/architect.agent.json`
- `product-forge/agents/code-review.agent.json`
- `product-forge/agents/design.agent.json`
- `product-forge/agents/devops.agent.json`
- `product-forge/agents/implement.agent.json`
- `product-forge/agents/orchestrator.agent.json`
- `product-forge/agents/package.agent.json`
- `product-forge/agents/pre-production.agent.json`
- `product-forge/agents/production-deploy.agent.json`
- `product-forge/core/agent_card_loader.py`
- `product-forge/core/agent_migrator.py`
- `product-forge/core/agent_rules.py`
- `product-forge/core/artifact_formats.py`
- `product-forge/core/budget_allocator.py`
- `product-forge/core/cross_project_learning.py`
- `product-forge/core/id_index.py`
- `product-forge/core/issue_tracker.py`
- `product-forge/core/knowledge_router.py`
- `product-forge/core/logging_manager.py`
- `product-forge/core/orchestrator/storage.py`
- `product-forge/core/project_archive.py`
- `product-forge/core/stage_paths.py`
- `product-forge/scripts/dev/generate_agent_cards.py`
- `product-forge/scripts/dev/generate_model_analysis.py`
- `product-forge/scripts/dev/generate_report.py`
- `product-forge/scripts/dev/workflow_matrix_check.py`
- `product-forge/scripts/gen_pipeline_reference.py`

### New findings
- **PF-235 P1** [`core/budget.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/budget.py): _lock returns None after 50 failed O_EXCL attempts, but _mutate continues load/modify/save without a lock. Concurrent writers can overwrite spend and exceed caps. Fail closed if lock acquisition times out; use unique temporary names and stale-lock recovery.
- **PF-236 P1** [`core/artifact_registry.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/artifact_registry.py): LocalRegistry.publish uses shutil.copy2 to the same build_id/basename without O_EXCL, digest-before-publish collision checks or immutable storage. Reusing build_id silently replaces an existing artifact. Refuse conflicting writes or use digest-addressed immutable paths.
- **PF-237 P1** [`core/compliance_action_handler.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/compliance_action_handler.py): After one retry for HIGH violations, auto_approve=True returns action=continue with requires_human=False; the stated high-severity HITL escalation can be bypassed. Require explicit policy-bound human authorization for high violations.
- **PF-238 P1** [`core/orchestrator/checkpoint.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/orchestrator/checkpoint.py): feature_status_map considers every stage key in execution.stage_executions completed; it never checks stage/agent status or compliance. Failed or partial iteration records can mark feature IDs done. Derive feature completion from verified stage status and gate evidence.
- **PF-239 P1** [`core/model_gate.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/model_gate.py): evaluate only puts INCOMPATIBLE agents in blocked_agents; UNKNOWN capability/model results are counted but not blocked. If caller relies on blocked_agents for preflight enforcement, unverified capability may proceed. Make UNKNOWN an explicit fail-closed policy choice.
- **PF-240 P1** [`core/run_guard.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/run_guard.py): After stop timeout, ensure_single_run calls _terminate but does not verify process exit; it then calls release_lock using prior holder even if termination failed. New run can acquire while old run is still alive. Confirm exit and lock ownership before release/reacquire.
- **PF-241 P1** [`scripts/dev/extract_llm_client.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/dev/extract_llm_client.py): One-shot extraction writes llm_client.py and rewrites pipeline_executor.py directly without backup, atomic replace, compile validation or abort when target methods are missing. A partial extraction can destroy the working executor. Require all expected methods, backup, staged compile and rollback.
- **PF-242 P2** [`scripts/setup/setup_target.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/setup/setup_target.py): setup sets status=ready when tools are installed, but does not change status if kind cluster creation or helm repo update fails; returns steps containing ok=False alongside ready. Derive status from required step results and distinguish tooling checks from credential validation.
- **PF-243 P1** [`scripts/dev/backfill_item_context.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/dev/backfill_item_context.py): --project is joined directly under products without path containment; a supplied ../ project can redirect reads, while backlog.update writes to that scope. Validate project identifier and resolved project path before any operation.
- **PF-244 P2** [`scripts/dev/invocation_audit.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/dev/invocation_audit.py): Reachability graph tracks AST imports and core.X strings but cannot resolve registry-based dynamic imports, callbacks or package __init__ modules (explicitly skipped). Its unwired verdict is a static approximation, not proof of runtime reachability; label limitations and supplement with runtime tracing.
- **PF-245 P2** [`core/orchestration_context.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/orchestration_context.py): route(use_coordinator=True) merely imports AgentRunner and records coordinator=available; it never invokes the Coordinator or returns a judgment. Escalation events may be reported as coordinator available while only default policy is applied. Implement explicit dispatch/result or label capability probe only.

**Limits:** Source review is static; no tests were executed. Several targeted paths were inspected for functions, persistence behavior and contract consistency, not end-to-end full-source certified. Prior findings remain in the cumulative record.


## Batch AI — depth-first source review (2026-09-28)

**Pinned commit:** `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`. **26 distinct previously uncertified paths examined**, **21 full static reviews** (8 core, 11 agent cards, 2 scripts), **5 targeted only**. Cumulative **202/394 full-certified** (core 89/239, agents 36/62, scripts 52/64, config 25/29); **192 remaining**. No runtime tests. Smaller batch deliberately prioritizes complete semantic review rather than claiming 50 deep reviews from partial scans.

### Full static certification
- `product-forge/core/agent_runtime.py`
- `product-forge/core/call_ledger.py`
- `product-forge/core/circuit_breaker.py`
- `product-forge/core/agent_readiness.py`
- `product-forge/core/agent_spec.py`
- `product-forge/core/run_breaker.py`
- `product-forge/core/project_archive.py`
- `product-forge/core/review_ledger.py`
- `product-forge/agents/a11y-audit.agent.json`
- `product-forge/agents/analyst.agent.json`
- `product-forge/agents/consensus.agent.json`
- `product-forge/agents/guardian.agent.json`
- `product-forge/agents/implement-logic.agent.json`
- `product-forge/agents/implement-ui.agent.json`
- `product-forge/agents/document.agent.json`
- `product-forge/agents/fix.agent.json`
- `product-forge/agents/researcher.agent.json`
- `product-forge/agents/scout.agent.json`
- `product-forge/agents/strategist.agent.json`
- `product-forge/scripts/dev/migrate_paths.py`
- `product-forge/scripts/dev/check_tier_models.py`

### Targeted only — not certified
- `product-forge/core/agent_ledger.py`
- `product-forge/core/agent_memory.py`
- `product-forge/core/budget_allocator.py`
- `product-forge/core/budget_planner.py`
- `product-forge/core/budget_protection.py`

### New findings
- **PF-246 P1** [`core/project_archive.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/core/project_archive.py): archive(project) and restore(project) join an unvalidated project string directly into filesystem paths. ../ traversal can move directories outside products; archive paths and registry are then attacker-controlled if exposed through API. Validate project slug and enforce realpath containment at archive/restore boundaries.
- **PF-247 P1** [`core/run_breaker.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/core/run_breaker.py): _load persists only alerts and fired keys, not total_tokens, total_cost, usage window or _stopped. Restart creates a fresh zero-spend breaker and clears a prior stop, allowing hard run caps to be bypassed across resumes. Persist run-scoped counters and stop state with run identity.
- **PF-248 P1** [`core/review_ledger.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/core/review_ledger.py): record allocates RV IDs from len(entries)+1 and rewrites review-ledger.json without locking/atomic replace; concurrent reviewer writes can lose feedback or reuse IDs. Use locked monotonic IDs and atomic commits.
- **PF-249 P1** [`core/agent_runtime.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/core/agent_runtime.py): create_checkpoint interpolates caller-provided task_id into a filename, while restore_checkpoint joins arbitrary checkpoint_id to checkpoint_dir without containment checks. Traversal-shaped IDs can read/write files outside checkpoints when inputs are untrusted. Validate IDs and use resolved-path containment.
- **PF-250 P1** [`core/circuit_breaker.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/core/circuit_breaker.py): can_execute returns True for every HALF_OPEN call, without a single in-flight probe guard; concurrent requests can flood a recovering dependency. Allow a bounded probe lease, then close/open based on its result.
- **PF-251 P2** [`agents/document.agent.json`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/agents/document.agent.json): Document agent requires reading full codebase and several project artifacts, but forbidden_inputs contains all_artifacts. This contradictory input contract can prevent the mandated documentation or cause the runtime to violate declared restrictions. Replace broad denial with explicit permitted artifact classes.
- **PF-252 P1** [`agents/researcher.agent.json`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/agents/researcher.agent.json): Researcher requires writing research report, sources.json, data.json and pipeline state, but its tools are only http_get, read_file and list_dir; no write_file is granted. Runtime artifact writer must be explicitly wired or add narrowly scoped write permission.
- **PF-253 P2** [`agents/implement-ui.agent.json`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/agents/implement-ui.agent.json): UI agent mandates mock data and stubbed UI in Stage 4-0, while its completion criteria are no_mock_or_stub and no_todo. Without phase-specific completion policy, valid preview work may be rejected or unfinished production code accepted. Split preview and feature-stage gates.
- **PF-254 P1** [`core/agent_readiness.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/core/agent_readiness.py): _dag_required returns [] on any pipeline-definition load/parse error, making required_inputs pass with zero dependencies; provider credential verification exceptions also set has=True. Preflight should distinguish unverifiable from verified and block must-have dependencies when DAG is unreadable.

**Notes:** PF-003 previously documented provider-key fail-open; PF-254 adds independent DAG-parse fail-open behavior. PF-080 previously documented agent-ledger concurrency; PF-248 concerns separate review-ledger. PF-175 already covers migrate_paths unsafe rewrite and is not duplicated. Full review means complete source/instruction inspection and static reasoning; not execution validation.


## Batch AJ — deep static review (2026-09-28)

**Pinned commit:** `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`. **20 distinct previously uncertified paths examined**, **14 complete static reviews** (7 core, 5 agent cards, 2 scripts), **6 targeted inspections**. Cumulative **216/394 certified** (core 96/239, agents 41/62, scripts 54/64, config 25/29); **178 pending**. No runtime tests.

### Full static reviews
- `product-forge/core/artifact_formats.py`
- `product-forge/core/verification_policy.py`
- `product-forge/core/prompt_overlays.py`
- `product-forge/core/tool_cache.py`
- `product-forge/core/stage_paths.py`
- `product-forge/core/run_state.py`
- `product-forge/core/quality_metrics.py`
- `product-forge/agents/insight-extractor.agent.json`
- `product-forge/agents/journal-writer.agent.json`
- `product-forge/agents/security-audit.agent.json`
- `product-forge/agents/validate.agent.json`
- `product-forge/agents/theme-analyzer.agent.json`
- `product-forge/scripts/dev/workflow_matrix_check.py`
- `product-forge/scripts/gen_pipeline_reference.py`

### Targeted only (not certified)
- `product-forge/core/agent_rules.py`
- `product-forge/core/capability_bridge.py`
- `product-forge/core/intent_router.py`
- `product-forge/core/port_config.py`
- `product-forge/agents/ingestion.agent.json`
- `product-forge/scripts/dev/generate_model_analysis.py`

### New findings
- **PF-255 P1** [`core/verification_policy.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/verification_policy.py): policy() marks a category internal when a test item merely exists, without requiring execution results; spec_review is unconditionally internal. Consumers can mistake test presence for completed verification. Separate planned/available/executed/passed states and require run evidence.
- **PF-256 P1** [`core/run_state.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/run_state.py): _stage_has_artifacts treats generated _stage.json as sufficient evidence of real artifacts; reconciled_completed also accepts all available approvals without checking expected agent coverage or run identity. Resume can mark a stage complete with only metadata and incomplete approvals. Require actual stage outputs and expected approval set.
- **PF-257 P2** [`core/tool_cache.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/tool_cache.py): invalidate(tool_name=...) never matches tool names: cache keys are hashes and entries do not store the tool name; pattern matches only hash substrings. Targeted invalidation silently removes zero entries. Store tool identity and use indexed invalidation.
- **PF-258 P1** [`core/prompt_overlays.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/prompt_overlays.py): set_overlay accepts arbitrary project_dir, agent_id, instructions and mode=replace, writes unvalidated prompt overlays without approval or immutable policy separation. If exposed to untrusted operators, agent safety/compliance instructions can be displaced. Restrict writer authorization and preserve mandatory system policy outside overlays.
- **PF-259 P1** [`core/stage_paths.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/stage_paths.py): stage_dirname returns raw stage_id under id naming, and stage_dir/find_stage_dir join it directly into filesystem paths. A caller-supplied traversal-shaped stage ID can escape the artifacts directory; enforce canonical stage IDs and resolved-path containment.
- **PF-260 P2** [`agents/security-audit.agent.json`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/agents/security-audit.agent.json): Security audit commands hard-code myworld package paths, Docker image tags and staging.myworld.com, rather than deriving the target product and staging environment. Copied execution can scan an unrelated app or miss actual product paths; require project-scoped command generation and evidence checks.
- **PF-261 P2** [`agents/journal-writer.agent.json`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/agents/journal-writer.agent.json): The journal agent prohibits fabricating personal experiences yet requires first-person emotional responses and personal connections from content summaries alone, without a verified personal-context input contract. Require user-provided reflection context or clearly labeled hypothetical prompts.
- **PF-262 P2** [`scripts/gen_pipeline_reference.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/gen_pipeline_reference.py): The generated Prev → Next column uses adjacency in display_id sort order rather than actual DAG dependencies. Optional branches and parallel stages can be documented as sequential predecessors/successors. Derive edges from pipeline dependency metadata.

**Evidence notes:** All findings based on static pinned-source review, not runtime reproduction. PF-258 and PF-259 require untrusted access to the corresponding APIs; assess exposure at integration boundaries. Existing PF-127 separately documents the brief-check unavailable-validator fail-open observed in the workflow matrix; no duplicate finding created.


## Batch AK — complete static reviews (2026-09-28)

**Pinned commit:** `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`. **8 distinct previously uncertified paths examined**, **5 complete static source reviews** (core), **3 targeted inspections**. Cumulative **221/394 certified**, **173 pending**. No runtime tests. This batch did not complete 50 files.

### Full static reviews
- `product-forge/core/agent_rules.py`
- `product-forge/core/context_engine.py`
- `product-forge/core/knowledge_registry.py`
- `product-forge/core/model_fit.py`
- `product-forge/core/budget_planner.py`

### Targeted only (not certified)
- `product-forge/core/capability_bridge.py`
- `product-forge/core/intent_router.py`
- `product-forge/core/port_config.py`

### New findings
- **PF-263 P1** [`core/model_fit.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/model_fit.py): evaluate() ranks substitution models only by probe success, response length and reasoning-only flag. It does not require that the substitute meet the target agent's tool, context or output capabilities. Catalog fit is added after recommendation in run() and does not constrain substitution. Apply a hard capability filter before recommending or applying replacements.
- **PF-264 P1** [`core/budget_planner.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/budget_planner.py): propose_tier() filters candidate models solely on quality_score and provider, without checking per-agent tool calling, context/output limits or required modalities. A model meeting numeric quality floor can be incompatible with the assigned role. Enforce capability constraints before cost optimization.
- **PF-265 P1** [`core/budget_planner.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/budget_planner.py): apply_proposal() requires approve=True but does not reject proposal.exceeds_hard or proposal.feasible=False. It can persist an infeasible model tier despite the stated hard budget. Add explicit hard-budget rejection or separately recorded authorized override and enforce per-agent floors.
- **PF-266 P1** [`core/knowledge_registry.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/knowledge_registry.py): _load() returns an empty registry for missing, corrupt or unreadable config, while add()/modify()/remove() rewrite config/knowledge-registry.json directly with no lock or atomic replacement. An update after transient read failure can erase the existing catalog; concurrent writers can lose entries. Fail closed on corrupt input and serialize atomic writes.
- **PF-267 P2** [`core/agent_rules.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/agent_rules.py): _extract_frontmatter() treats an unterminated --- block as frontmatter while retaining most of its body; _extract_sections() recognizes nested ### numeric headings as top-level sections and may mistake section 4.1/7.1 for required section 4/7. Enforce closed YAML frontmatter and heading hierarchy, and validate duplicate section numbers.

**Reconfirmed prior finding:** PF-198 context_engine.py priority-over-budget admission; no duplicate ID. Findings are static and require runtime reproduction.


## Batch AL — complete static reviews (2026-09-28)

**Pinned commit:** `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`. **16 distinct previously uncertified files examined; 11 complete static source/contract reviews, 5 targeted only. Cumulative 232/394 certified; 162 pending. No runtime tests or fixes.**

### Full static reviews
- `product-forge/core/cross_project_learning.py`
- `product-forge/core/capability_bridge.py`
- `product-forge/core/discovery_engine.py`
- `product-forge/core/id_index.py`
- `product-forge/scripts/dev/generate_report.py`
- `product-forge/scripts/pipeline_helpers.py`
- `product-forge/agents/post-production.agent.json`
- `product-forge/agents/production-deploy.agent.json`
- `product-forge/agents/summary-creator.agent.json`
- `product-forge/agents/package.agent.json`
- `product-forge/agents/performance.agent.json`

### Targeted only — not certified
- `product-forge/core/agent_messenger.py`
- `product-forge/agents/architect.agent.json`
- `product-forge/agents/design.agent.json`
- `product-forge/agents/devops.agent.json`
- `product-forge/agents/quality_gate.agent.json`

### New findings
- **PF-268 P2** [`core/cross_project_learning.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/cross_project_learning.py): suggest_for_project ignores project_type and tech_stack when selecting patterns, and build_learning_index infers completed from any insight. PF-059 already covers false completion; this finding is specifically unfiltered cross-project recommendations. **Fix:** Filter by domain, technology and verified relevance; label unsupported suggestions and preserve provenance.
- **PF-269 P1** [`core/capability_bridge.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/capability_bridge.py): onboard_customer and build_video return ok=True after constructing an engine but without invoking generation. _save returns a path even after write failure; validate_code swallows per-file errors and counts unexamined files beyond its first 50 as validated. **Fix:** Require real output/evidence and successful persistence; count only successfully checked files; return explicit skipped/error counts.
- **PF-270 P1** [`core/discovery_engine.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/discovery_engine.py): run_discovery joins the unvalidated project argument directly beneath products_dir, creates directories and overwrites multiple output documents; traversal-shaped project names can write outside the intended product root when caller input is untrusted. **Fix:** Validate project identifier and resolved-path containment; use transactional output writes and explicit overwrite policy.
- **PF-271 P1** [`core/id_index.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/id_index.py): defined_in_scopes assigns each ID to only the scope of its first occurrence, so duplicates() cannot detect repeated IDs across scopes; undefined_refs returns seen-seen and is always empty. Both exposed verification queries can silently miss invalid specs. **Fix:** Separate definitions from references using a manifest or structural definition parser and test cross-feature duplicates and missing references.
- **PF-272 P1** [`scripts/pipeline_helpers.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/pipeline_helpers.py): initialize_product_completion unconditionally replaces an existing product_completion object with zero totals and empty feature lists if invoked directly; migrate_all_projects classifies any zero-total project as newly migrated. Direct JSON writes are non-atomic. **Fix:** Only initialize when absent or explicitly migrating; preserve existing progress, write atomically and return an explicit changed flag.
- **PF-273 P2** [`scripts/dev/generate_report.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/dev/generate_report.py): report generator hardcodes products/test-pipeline, a 30,000-token stage budget, and a 1,000,000 context-window total; its final phase budget verdict is always Yes and it assumes budget_summary totals exist. Generated metrics can misrepresent actual run constraints. **Fix:** Take project and budgets from the report/config, compute actual totals and verdicts, and render unknown metrics as unavailable.
- **PF-274 P1** [`agents/package.agent.json`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/agents/package.agent.json): mandatory Docker build, health-check commands and project paths are hardcoded to products/myworld and fixed localhost ports, even though the card is intended for arbitrary products; running instructions literally can build or test the wrong project. **Fix:** Parameterize all commands with validated active project, configured services/ports and artifact evidence.
- **PF-275 P1** [`agents/summary-creator.agent.json`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/agents/summary-creator.agent.json): card requires reading insights/theme files and writing summary.md, JSON takeaways, audit and pipeline status but declares tools=[] and completion=[]; without independent tool injection its required workflow cannot be fulfilled or evidence-gated. **Fix:** Grant scoped read/write tools and machine-readable completion requirements or explicitly delegate persistence to a verified writer.
- **PF-276 P1** [`agents/production-deploy.agent.json`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/agents/production-deploy.agent.json): rollout examples equate canary replica counts with traffic percentages (2 replicas =10%, 10=50%) without verifying stable deployment size, service routing or actual traffic. This can cause inaccurate canary exposure if copied as an operational runbook. Prior PF-178 separately covers approval controls. **Fix:** Use traffic-weighted routing with measured percentages and explicit automated abort criteria, never infer traffic share from replica count.

**Reconfirmed existing findings:** PF-059 (cross-project status), PF-139 (performance test thresholds), PF-140 (production chaos approval), PF-178 (production deployment approval). Do not duplicate these as new findings. No runtime execution or exploit validation.


## Batch AM — 2026-09-28 — 6 full source static reviews, 5 targeted inspections

**Scope:** pinned commit `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`; no runtime tests. Cumulative **238/394 fully certified**, **156 pending**. This batch does not claim a 40-file deep review.

### Full source-reviewed modules

- [`core/budget_protection.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/budget_protection.py)
- [`core/design_critic.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/design_critic.py)
- [`core/discovery_panel.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/discovery_panel.py)
- [`core/port_config.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/port_config.py)
- [`core/tenancy.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/tenancy.py)
- [`core/techstack_guidelines.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/techstack_guidelines.py)

### Targeted inspections only — not certified

- `core/compliance_check.py`
- `core/conversation_models.py`
- `core/intent_router.py`
- `core/views.py`
- `core/workflow_docs.py`

### New findings

**PF-277 — P1 — [`core/budget_protection.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/budget_protection.py)**

- Evidence: Budget enforcement fail-open: request_tokens returns True when the budget ID is missing; create_budget replaces an existing budget and resets used/reserved counters. A caller can bypass quotas through missing or recreated IDs.
- Recommended remediation: Require an existing budget and carry cumulative usage forward; validate positive allocations and add concurrent quota tests.
- Validation needed: unit and integration tests on the described failure path; no tests were run during this static audit.

**PF-278 — P1 — [`core/budget_protection.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/budget_protection.py)**

- Evidence: Budget state persistence restores only aggregate totals and alerts; self.budgets is never restored. A process restart loses all active per-agent/stage limits while total_used remains, so enforcement and reporting diverge.
- Recommended remediation: Persist/recover individual budget balances and reservations; fail closed on storage errors.
- Validation needed: unit and integration tests on the described failure path; no tests were run during this static audit.

**PF-279 — P1 — [`core/discovery_panel.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/discovery_panel.py)**

- Evidence: to_discovery_answers falls back to q.recommendation even for q.unanswered or needs_verification, silently promoting unapproved recommendations into downstream discovery synthesis.
- Recommended remediation: Include only explicit answers/acceptances; block synthesis or mark unresolved questions.
- Validation needed: unit and integration tests on the described failure path; no tests were run during this static audit.

**PF-280 — P1 — [`core/discovery_panel.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/discovery_panel.py)**

- Evidence: build_round2 indexes existing groups by g.id, but build_panel groups use agent_id; round-2 follow-ups create duplicate groups and omit source_agent/accepted defaults, then synthesis_agent maps follow-ups to business_analyst instead of the originating perspective.
- Recommended remediation: Index groups consistently by agent_id and populate complete question fields; add round-trip tests.
- Validation needed: unit and integration tests on the described failure path; no tests were run during this static audit.

**PF-281 — P2 — [`core/design_critic.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/design_critic.py)**

- Evidence: Critical accessibility check uses raw substring aria; unrelated text such as variable can satisfy it. Other keyword checks also award points for superficial mentions rather than actual design requirements.
- Recommended remediation: Parse explicit checklist sections/structured artifacts and require evidence references before marking accessibility pass.
- Validation needed: unit and integration tests on the described failure path; no tests were run during this static audit.

**PF-282 — P1 — [`core/tenancy.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/tenancy.py)**

- Evidence: invite and set_role directly accept owner/admin roles with no authorization check in this module; invite does not enforce seat limits. API-layer checks are claimed in comments but not established by this source.
- Recommended remediation: Enforce actor permissions and seat quotas at the service boundary; test direct internal callers and concurrent invitations.
- Validation needed: unit and integration tests on the described failure path; no tests were run during this static audit.

**PF-283 — P2 — [`core/port_config.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/port_config.py)**

- Evidence: Port allocation checks only live TCP listeners; it does not reserve assigned ports or exclude ports allocated earlier in the same pass. Conflicts are detected after allocation but not resolved, and connection errors are interpreted as availability.
- Recommended remediation: Maintain reserved port set and bind-probe or deployment-level allocation; reject unresolved conflicts.
- Validation needed: unit and integration tests on the described failure path; no tests were run during this static audit.

**PF-284 — P1 — [`core/techstack_guidelines.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/techstack_guidelines.py)**

- Evidence: Unvalidated techstack string is interpolated into coding/<techstack>/style-guide.md; path separators and .. can escape the intended guideline directory during ensure_guidelines_exist.
- Recommended remediation: Canonicalize allowed slug characters and enforce resolved-path containment before read/write.
- Validation needed: unit and integration tests on the described failure path; no tests were run during this static audit.

**PF-285 — P2 — [`core/techstack_guidelines.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/techstack_guidelines.py)**

- Evidence: Unknown stacks receive generic boilerplate described as dynamically generated stack-specific guidelines; no official documentation lookup or LLM generation exists in this module.
- Recommended remediation: Label generic fallback explicitly, require source-backed stack-specific generation and review before compliance use.
- Validation needed: unit and integration tests on the described failure path; no tests were run during this static audit.

### Recommended remediation sequence

1. Fix discovery answer approval and round-2 identity propagation (PF-279/280).
2. Make token budgets persistent and fail closed (PF-277/278).
3. Constrain techstack-generated output paths and enforce tenancy permissions/seats at trusted service boundaries (PF-282/284).
4. Replace keyword-based design checks and port allocation heuristics with evidence-backed validators (PF-281/283/285).


## Batch AN — September 28, 2026 — agent contracts and execution-support code

**Baseline:** 238/394 full static; **new complete:** 21; **targeted:** 11; **examined:** 32; **cumulative:** 259/394; **remaining:** 135. No runtime tests. Agent certification covers full JSON contract and structured prompt-instruction review, not runtime execution.

### Complete static reviews

- `product-forge/agents/architect.agent.json`
- `product-forge/agents/code-review.agent.json`
- `product-forge/agents/design.agent.json`
- `product-forge/agents/devops.agent.json`
- `product-forge/agents/ideation.agent.json`
- `product-forge/agents/implement.agent.json`
- `product-forge/agents/inference.agent.json`
- `product-forge/agents/ingestion.agent.json`
- `product-forge/agents/iterative_evaluator.agent.json`
- `product-forge/agents/orchestrator.agent.json`
- `product-forge/agents/pre-production.agent.json`
- `product-forge/agents/presentation-generator.agent.json`
- `product-forge/agents/product-analyzer.agent.json`
- `product-forge/agents/quality_gate.agent.json`
- `product-forge/agents/security.agent.json`
- `product-forge/agents/static_verifier.agent.json`
- `product-forge/scripts/dev/generate_agent_cards.py`
- `product-forge/scripts/run_portfolio.py`
- `product-forge/core/budget_allocator.py`
- `product-forge/core/orchestrator/storage.py`
- `product-forge/core/product_page.py`

### Targeted inspections only (not certified)

- `product-forge/config/file-manifest.json`
- `product-forge/config/model-catalog.json`
- `product-forge/config/model-tier.json`
- `product-forge/config/store-registry.json`
- `product-forge/scripts/dev/gen_docs_index.py`
- `product-forge/scripts/dev/generate_model_analysis.py`
- `product-forge/scripts/dev/wired_audit.py`
- `product-forge/scripts/gen_model_registry.py`
- `product-forge/scripts/pipeline.py`
- `product-forge/scripts/run_pipeline.py`
- `product-forge/core/agent_migrator.py`

### Findings

**PF-286 — P1 — [`agents/implement.agent.json`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/agents/implement.agent.json)**

- Evidence: Declares implement-db/api/logic/ui sub_agents but can_invoke=[]; metadata-based delegation will reject intended layer orchestration.
- Remediation: Align can_invoke with approved sub-agents and add delegation contract tests.
- Validation: targeted runtime/integration test needed; not run in this static batch.

**PF-287 — P1 — [`agents/architect.agent.json`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/agents/architect.agent.json), [`agents/quality_gate.agent.json`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/agents/quality_gate.agent.json)**

- Evidence: Both instruct agents to write/update files, yet tools=[]; if the runner enforces declared tools, required artifacts or gate state cannot be persisted.
- Remediation: Make artifact persistence an explicit controlled runner action or grant narrowly scoped write tools; test output persistence.
- Validation: targeted runtime/integration test needed; not run in this static batch.

**PF-288 — P1 — [`agents/orchestrator.agent.json`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/agents/orchestrator.agent.json)**

- Evidence: Primary orchestrator declares tools=[] and can_invoke=[] despite orchestration and agent-selection instructions; execution depends on an undocumented external runner bypass.
- Remediation: Specify explicit judgment-plane versus execution-plane contract and verify delegated actions at runner boundary.
- Validation: targeted runtime/integration test needed; not run in this static batch.

**PF-289 — P2 — [`agents/iterative_evaluator.agent.json`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/agents/iterative_evaluator.agent.json), [`agents/static_verifier.agent.json`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/agents/static_verifier.agent.json)**

- Evidence: model_pin contains embedded literal double quotes (e.g. "\"openrouter/...\""); direct provider routing may fail.
- Remediation: Normalize model_pin during generation/validation; reject quoted provider identifiers in schema.
- Validation: targeted runtime/integration test needed; not run in this static batch.

**PF-290 — P1 — [`scripts/dev/generate_agent_cards.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/dev/generate_agent_cards.py)**

- Evidence: --apply directly overwrites all .opencode/agent cards, no backup/atomic replace or validation; generated workflow universally tells tool-equipped agents not to inspect files before writing.
- Remediation: Add preview diff, explicit approval, backup, atomic replacement and role-specific inspect-before-edit guidance.
- Validation: targeted runtime/integration test needed; not run in this static batch.

**PF-291 — P1 — [`core/budget_allocator.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/budget_allocator.py)**

- Evidence: reallocate accepts negative tokens: source.allocated_tokens -= tokens and target += tokens invert the transfer and can make allocations negative; record_usage accepts negative usage.
- Remediation: Require positive finite integer tokens and enforce conservation/invariants with tests.
- Validation: targeted runtime/integration test needed; not run in this static batch.

**PF-292 — P1 — [`core/orchestrator/storage.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/orchestrator/storage.py)**

- Evidence: LLMCache.get/set is callable independently of output_cache_allowed()/no_cache() and caches generation responses by prompt/model/agent only, omitting provider settings and resolved context fingerprint.
- Remediation: Remove output cache or enforce bypass and complete input fingerprint in the cache class, not only at callers.
- Validation: targeted runtime/integration test needed; not run in this static batch.

**PF-293 — P2 — [`core/product_page.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/product_page.py)**

- Evidence: Product lifecycle checks q.get("passed") for truthiness; a string "false" incorrectly marks product built. Missing/corrupt data is silently mapped to empty views.
- Remediation: Require strict boolean schema and show explicit unknown/degraded status for unreadable sources.
- Validation: targeted runtime/integration test needed; not run in this static batch.

### Cross-cutting implications

- Enforce a single executable contract for tools, invocation permissions, artifact writes and model identifiers. Prompt text alone is not a security or quality gate.
- Budget allocation and response caching need invariant tests at the module boundary.
- Large model-catalog, model-tier, store-registry, manifest and six script files were targeted only; do not count them as full reviews.


## Batch AO — 75 files retrieved/scanned; 10 complete manual source reviews (2026-09-28)

Pinned commit: `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`. Prior certified **259/394**; now **269/394**, **125 pending**. **75 distinct previously pending paths** were fetched and underwent an automated source-level scan (file size, functions, exception/write/tool patterns). Only the 10 files listed below also received a complete manual source/control-flow review and were newly certified. The other 65 remain targeted/automated only, **not deep-certified**. No runtime/integration tests executed.

### 10 complete manual source reviews

- [`product-forge/core/dashboard_blueprint.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/dashboard_blueprint.py)
- [`product-forge/core/human_proxy.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/human_proxy.py)
- [`product-forge/core/multi_model_review.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/multi_model_review.py)
- [`product-forge/core/pipeline_store.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/pipeline_store.py)
- [`product-forge/core/orchestrator/delegation_coord.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/orchestrator/delegation_coord.py)
- [`product-forge/core/orchestrator/feature_tracker.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/orchestrator/feature_tracker.py)
- [`product-forge/core/agent_tool_loop.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/agent_tool_loop.py)
- [`product-forge/core/dag_executor.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/dag_executor.py)
- [`product-forge/core/intake_adapters.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/intake_adapters.py)
- [`product-forge/core/pdf_generator.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/pdf_generator.py)

### 65 additional full-source automated scans — not certified

- `product-forge/config/file-manifest.json`
- `product-forge/config/model-catalog.json`
- `product-forge/config/model-tier.json`
- `product-forge/config/store-registry.json`
- `product-forge/core/adopt_project.py`
- `product-forge/core/agent_card_loader.py`
- `product-forge/core/agent_ledger.py`
- `product-forge/core/agent_memory.py`
- `product-forge/core/agent_messenger.py`
- `product-forge/core/agent_migrator.py`
- `product-forge/core/artifact_store.py`
- `product-forge/core/backlog.py`
- `product-forge/core/budget_tracker.py`
- `product-forge/core/build_utility.py`
- `product-forge/core/business_skills_selector.py`
- `product-forge/core/close_loop.py`
- `product-forge/core/code_analyzer.py`
- `product-forge/core/code_executor.py`
- `product-forge/core/compliance_check.py`
- `product-forge/core/compliance_verifier.py`
- `product-forge/core/conversation_compiler.py`
- `product-forge/core/conversation_models.py`
- `product-forge/core/cost_modeling.py`
- `product-forge/core/cross_review.py`
- `product-forge/core/customer_onboarding.py`
- `product-forge/core/defect_loop.py`
- `product-forge/core/deploy_providers.py`
- `product-forge/core/domain_research.py`
- `product-forge/core/git_manager.py`
- `product-forge/core/global_orchestrator.py`
- `product-forge/core/intake.py`
- `product-forge/core/intake_api.py`
- `product-forge/core/intake_channels.py`
- `product-forge/core/intake_files.py`
- `product-forge/core/integration_advisor.py`
- `product-forge/core/intent_router.py`
- `product-forge/core/interactive.py`
- `product-forge/core/issue_tracker.py`
- `product-forge/core/job_manager.py`
- `product-forge/core/knowledge_compliance_checker.py`
- `product-forge/core/knowledge_router.py`
- `product-forge/core/licensing.py`
- `product-forge/core/lock_manager.py`
- `product-forge/core/logging_manager.py`
- `product-forge/core/main.py`
- `product-forge/core/marketing.py`
- `product-forge/core/memory_api.py`
- `product-forge/core/mobile_tester.py`
- `product-forge/core/model_catalog.py`
- `product-forge/core/model_recommendation.py`
- `product-forge/core/model_registry.py`
- `product-forge/core/nfr_runner.py`
- `product-forge/core/orchestrator.md`
- `product-forge/core/orchestrator/agent_execution.py`
- `product-forge/core/orchestrator/agent_runner.py`
- `product-forge/core/orchestrator/compliance.py`
- `product-forge/core/orchestrator/llm_client.py`
- `product-forge/core/orchestrator/model_router.py`
- `product-forge/core/orchestrator/prompt_builder.py`
- `product-forge/core/orchestrator/reporting.py`
- `product-forge/core/orchestrator/stage_runner.py`
- `product-forge/core/output_checklist.py`
- `product-forge/core/phase3_advanced.py`
- `product-forge/core/pipeline_capabilities.py`
- `product-forge/core/pipeline_executor.py`

### New findings (static; runtime confirmation pending)

**PF-294 — P0 — [`core/human_proxy.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/human_proxy.py)**

- Evidence: _parse returns approve on malformed/missing JSON; decide also returns approve on any exception. A failed or unavailable HIL proxy can authorize a gate.
- Remediation: Require explicit schema-validated decision; malformed response/error -> blocked/escalate; log immutable decision evidence.
- Validation: static only; focused unit/integration tests not run.

**PF-295 — P0 — [`core/agent_tool_loop.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/agent_tool_loop.py)**

- Evidence: Text-protocol run_tool_loop executes every parsed name through registry.execute without intersecting spec.tools. Native loop restricts tool names but text loop does not.
- Remediation: Apply same per-agent allowlist in both loops and enforce at registry.execute with principal context.
- Validation: static only; focused unit/integration tests not run.

**PF-296 — P1 — [`core/multi_model_review.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/multi_model_review.py)**

- Evidence: Aggregated passed is simple majority of models that responded; if 1 of 3 configured reviewers responds pass and two fail to respond, passed=True.
- Remediation: Require minimum independent reviewer quorum and fail closed on missing required reviewers.
- Validation: static only; focused unit/integration tests not run.

**PF-297 — P1 — [`core/pipeline_store.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/pipeline_store.py)**

- Evidence: read() retains legacy keys when current config/state contain blank/empty values; removed current settings can resurrect stale legacy values. sync() silently suppresses write failure but returns successful projection.
- Remediation: Define authoritative field ownership including explicit deletion; report sync failures and verify projection persisted.
- Validation: static only; focused unit/integration tests not run.

**PF-298 — P1 — [`core/orchestrator/delegation_coord.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/orchestrator/delegation_coord.py)**

- Evidence: signals() returns the same broad set of nine issue types for every non-completed/non-skipped outcome; router can dispatch unrelated sub-agent and budget.record occurs even after dispatch execution error.
- Remediation: Derive typed signals from actual outcome evidence and record attempts/success separately.
- Validation: static only; focused unit/integration tests not run.

**PF-299 — P1 — [`core/orchestrator/feature_tracker.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/orchestrator/feature_tracker.py)**

- Evidence: seed/mark_implemented/mark_tested/save broadly swallow exceptions; a failed persistence or status update can appear successful to caller.
- Remediation: Return structured success/failure and fail stage gate on missing mandatory feature evidence.
- Validation: static only; focused unit/integration tests not run.

**PF-300 — P1 — [`core/intake_adapters.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/intake_adapters.py)**

- Evidence: instructions(source) and schema_path(source) join caller-controlled source directly under adapters directory; ../ traversal can access other repository files if source is exposed to untrusted callers.
- Remediation: Validate source against known adapter names and resolve/check containment under adapter root.
- Validation: static only; focused unit/integration tests not run.

**PF-301 — P1 — [`core/pdf_generator.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/pdf_generator.py)**

- Evidence: Fallback _build_minimal_pdf hardcodes xref byte offsets and approximates stream length/startxref; generated PDF can be structurally invalid, while _create_simple_pdf reports True after writing bytes.
- Remediation: Use reportlab or standards-compliant PDF writer; if no backend available, return explicit failure.
- Validation: static only; focused unit/integration tests not run.

**PF-302 — P2 — [`core/dashboard_blueprint.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/dashboard_blueprint.py)**

- Evidence: load_blueprint treats malformed existing blueprint as absent and overwrites it with DEFAULT; instantiate also overwrites target descriptor directly.
- Remediation: Distinguish missing vs corrupt config; back up and raise on corruption, atomic write descriptors.
- Validation: static only; focused unit/integration tests not run.

### Carry-forward findings re-observed (not counted as new)

- `core/dag_executor.py` still filters unknown dependencies in readiness checks; see existing PF-002.
- Previous full reviews of core `agent_tool_loop` and other modules are not implied by this new batch; only the 10 named paths were newly certified.

### Next deep-review priority

Complete manual source and cross-file review of 65 scanned-but-uncertified paths, starting with `core/pipeline_executor.py` (3435 lines), `core/orchestrator/agent_runner.py` (1784 lines), `core/orchestrator/llm_client.py`, `core/agent_memory.py`, and `config/model-tier.json`; these are too large to deep-certify from regex scans alone.


## Batch AP — source-deep review, 2026-09-28

**Disposition:** 12 previously pending files examined; **10 complete pinned-source static reviews** and **2 targeted inspections**. Cumulative **279/394 complete**, **115 pending**. No runtime tests or code modifications. Previous Batch AO examined 75 but fully certified only 10; no AO targeted files were carried forward as complete without fresh full-source reading.

### Newly fully reviewed (10)

- `product-forge/core/main.py`
- `product-forge/core/state_machine.py`
- `product-forge/core/pr_gate.py`
- `product-forge/core/qa_manifest.py`
- `product-forge/core/qir.py`
- `product-forge/core/run_quality_gate.py`
- `product-forge/core/progress.py`
- `product-forge/core/plan_evaluator.py`
- `product-forge/core/pipeline_templates.py`
- `product-forge/core/qa_report.py`

### Targeted only (not certified)

- `product-forge/core/pipeline_telemetry.py`
- `product-forge/core/schema_validator.py`

### New findings (13)

**PF-303 — P1 — [`core/pr_gate.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/pr_gate.py)**

- Evidence: Agent completion is accepted as code-review approval; _audit_has checks agent_complete but does not verify a reviewer verdict, reviewed commit or unresolved feedback.
- Remediation: Require signed/linked approval evidence for the exact change and reject stale reviews.
- Validation: static source review only; no runtime reproduction.

**PF-304 — P1 — [`core/pr_gate.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/pr_gate.py)**

- Evidence: DB/API category tests pass when test files exist and the overall cycle passed; the code does not establish that the specific category actually ran and passed.
- Remediation: Bind category result to executed test-run evidence and build/commit identity.
- Validation: static source review only; no runtime reproduction.

**PF-305 — P1 — [`core/pr_gate.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/pr_gate.py)**

- Evidence: The app_boot failure propagation runs before unit_tests and lint are assigned, so those subsequently assigned pass statuses are not invalidated by failed boot.
- Remediation: Compute all statuses first, then apply dependency invalidation.
- Validation: static source review only; no runtime reproduction.

**PF-306 — P1 — [`core/pr_gate.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/pr_gate.py)**

- Evidence: The merge override is trusted from project.json qa.override_merge.approved; approve_override accepts a caller-supplied approved_by default HIL without authenticating the approver.
- Remediation: Use authenticated HIL identity, immutable decision log and scoped expiry/commit binding.
- Validation: static source review only; no runtime reproduction.

**PF-307 — P1 — [`core/qir.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/qir.py)**

- Evidence: Missing coverage/pass-rate signals receive neutral_score 0.78; security uses max(neutral, 1-open_high/3), masking high-severity defects until separate caps apply.
- Remediation: Separate unknown from measured performance; let verified high-severity defects lower security and block release.
- Validation: static source review only; no runtime reproduction.

**PF-308 — P1 — [`core/qa_report.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/qa_report.py)**

- Evidence: Go/no-go marks Install/Packaging green unconditionally, and verification-policy exceptions return green; these dimensions can pass without evidence.
- Remediation: Require recorded packaging/install results and mark unavailable verification as unknown/red per policy.
- Validation: static source review only; no runtime reproduction.

**PF-309 — P1 — [`core/qa_manifest.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/qa_manifest.py)**

- Evidence: The HTML QA snapshot interpolates project, matrix detail and QIR evidence directly without HTML escaping; artifact-derived strings can inject markup/scripts when opened.
- Remediation: HTML-escape all data and restrict untrusted HTML; use template autoescaping.
- Validation: static source review only; no runtime reproduction.

**PF-310 — P1 — [`core/state_machine.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/state_machine.py)**

- Evidence: _save_state deletes existing state.json before renaming the temp file; a crash or rename failure loses the previous state, and transitions have no lock.
- Remediation: Use os.replace with fsync and per-project serialization/optimistic version.
- Validation: static source review only; no runtime reproduction.

**PF-311 — P1 — [`core/plan_evaluator.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/plan_evaluator.py)**

- Evidence: Dependency safety inspects depends_on only, not runs_after; confirm can alter include/skip after safety resolution, and apply_to_dag skips without revalidating dependencies.
- Remediation: Normalize all dependency edges and re-run strict closure immediately before DAG mutation.
- Validation: static source review only; no runtime reproduction.

**PF-312 — P1 — [`core/pipeline_templates.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/pipeline_templates.py)**

- Evidence: validate rejects stages with empty depends_on (valid roots), does not check unknown dependencies/cycles, and to_pipeline_def/apply_template never call validate.
- Remediation: Schema-validate template before execution; allow root stages and reject unknown/cyclic dependencies.
- Validation: static source review only; no runtime reproduction.

**PF-313 — P2 — [`core/progress.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/progress.py)**

- Evidence: Agent position is derived from static stage order plus first live agent, not actual per-agent completion; completed stages can still show an agent index and banner overrides stage/agent without recomputing indices.
- Remediation: Derive progress from persisted per-agent execution records and recompute on banner overrides.
- Validation: static source review only; no runtime reproduction.

**PF-314 — P1 — [`core/run_quality_gate.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/run_quality_gate.py)**

- Evidence: The repo gate runs compileall and wired_audit only for item/amend, not e2e, and its result records are silently dropped on write failure; compileall does not execute tests.
- Remediation: Apply an explicit verified quality policy to all release-capable runs, persist failures durably and require test evidence.
- Validation: static source review only; no runtime reproduction.

**PF-315 — P2 — [`core/main.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/main.py)**

- Evidence: Deprecated CLI run command instantiates GlobalOrchestrator(product_name) and calls .run(), while the current GlobalOrchestrator exposes project lifecycle methods rather than run; main returns success even after caught execution errors.
- Remediation: Remove deprecated CLI entry point or delegate to the supported PipelineExecutor and propagate exit status.
- Validation: static source review only; no runtime reproduction.

### Cross-cutting priorities

1. Replace completion flags with commit-bound, category-specific evidence across PR gate, QIR and Go/No-Go.
2. Make release evidence fail closed when missing, stale or inaccessible; eliminate unconditional green rows.
3. Make state writes atomic and serialized; validate run-plan dependency closure at execution.
4. Add focused tests for boot-failure propagation, unexecuted category tests, malformed templates, missing verification policy and HTML injection.


## Batch AQ — source-deep review, 2026-09-28

**Disposition:** 10 previously pending paths examined; **6 complete pinned-source static reviews** and **4 targeted inspections**. Cumulative **285/394 complete**, **109 pending**. No runtime tests or repository code changes.

### Newly fully reviewed (6)

- `product-forge/core/tool_policy.py`
- `product-forge/core/pipeline_tailoring.py`
- `product-forge/core/write_safety.py`
- `product-forge/core/stop_conditions.py`
- `product-forge/core/vendor_adapters.py`
- `product-forge/core/orchestrator.md`

### Targeted only (not certified)

- `product-forge/core/skills_registry.py`
- `product-forge/core/conversation_models.py`
- `product-forge/core/output_checklist.py`
- `product-forge/core/service_catalog.py`

### New findings (10)

**PF-316 — P1 — [`core/write_safety.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/write_safety.py)**

- Evidence: file_lock imports fcntl on Unix but unconditionally calls msvcrt.locking; safe_update_json/safe_append_json cannot obtain a lock on Unix.
- Remediation: Implement fcntl.flock on Unix, msvcrt on Windows and test both platforms.
- Validation: static source review only; no runtime reproduction.

**PF-317 — P1 — [`core/write_safety.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/write_safety.py)**

- Evidence: Atomic writers use deterministic .tmp/.bak paths and backup/cleanup without lock; concurrent writes can overwrite temp files or each other and destroy recovery backup.
- Remediation: Unique same-directory temporary files, lock around entire transaction and durable os.replace/fsync.
- Validation: static source review only; no runtime reproduction.

**PF-318 — P1 — [`core/write_safety.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/write_safety.py)**

- Evidence: safe_write_checkpoint interpolates unsanitized project/checkpoint_id into filesystem path, permitting traversal if called with untrusted IDs.
- Remediation: Validate IDs, resolve and constrain target beneath products root.
- Validation: static source review only; no runtime reproduction.

**PF-319 — P1 — [`core/pipeline_tailoring.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/pipeline_tailoring.py)**

- Evidence: apply_plan deletes disabled optional stages and silently strips downstream depends_on edges rather than rejecting or re-enabling required prerequisites.
- Remediation: Compute dependency closure, fail closed on incompatible plan, and retain dependency provenance.
- Validation: static source review only; no runtime reproduction.

**PF-320 — P1 — [`core/tool_policy.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/tool_policy.py)**

- Evidence: tools_for adds http_get when free-text role/description/knowledge contains broad substrings such as analysis; no allowlist, approval or deny policy is applied in this module.
- Remediation: Treat dynamic tool selection as a proposal constrained by explicit per-agent capability grants and central execution-time authorization.
- Validation: static source review only; no runtime reproduction.

**PF-321 — P1 — [`core/stop_conditions.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/stop_conditions.py)**

- Evidence: low_confidence_threshold is checked with value >= threshold, so high confidence triggers escalation while low confidence does not; check_conditions also defaults absent metrics to zero.
- Remediation: Support comparator <= for confidence and distinguish absent metrics from measured zero.
- Validation: static source review only; no runtime reproduction.

**PF-322 — P1 — [`core/stop_conditions.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/stop_conditions.py)**

- Evidence: resolve_escalation rewrites the whole JSONL file without locking/atomic replace and silently drops malformed lines, risking lost concurrent escalations and records.
- Remediation: Use append-only resolution events or locked atomic replacement preserving malformed records for quarantine.
- Validation: static source review only; no runtime reproduction.

**PF-323 — P1 — [`core/vendor_adapters.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/vendor_adapters.py)**

- Evidence: run_vendors invokes configured apply and verify commands even when lab_handle is empty and detected CLI status is false; no lab-handle precondition or command allowlist is enforced in this module.
- Remediation: Require explicit authorized lab handle and command policy before any apply/destroy operation.
- Validation: static source review only; no runtime reproduction.

**PF-324 — P2 — [`core/vendor_adapters.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/vendor_adapters.py)**

- Evidence: _phase excludes cli-missing steps (ok=None) from chk, so mixed success and missing CLI can produce overall ok=True despite an unexecuted command.
- Remediation: Represent skipped/unavailable as incomplete and require every mandatory command to execute and succeed.
- Validation: static source review only; no runtime reproduction.

**PF-325 — P2 — [`core/orchestrator.md`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/orchestrator.md)**

- Evidence: Orchestration policy document gives inconsistent budget stop thresholds (100% hard stop, 95% emergency) and failure policies (3 consecutive failures versus retry once then skip), with no normative precedence.
- Remediation: Consolidate a versioned normative policy with one threshold table and conformance tests.
- Validation: static source review only; no runtime reproduction.

### Cross-cutting priorities

1. Repair cross-platform locking and serialized atomic persistence before concurrent project execution.
2. Enforce dependency closure when tailoring the pipeline; reject plans that remove prerequisites.
3. Make tool permissions and vendor commands explicitly authorized at execution time.
4. Correct confidence comparator and preserve escalation events durably.


## Batch AR — source-deep review, 2026-09-28

**Disposition:** 16 previously pending paths examined; **6 complete pinned-source static reviews** and **10 targeted inspections**. Cumulative **291/394 complete**, **103 pending**. No runtime tests or repository code changes.

### Newly fully reviewed (6)

- `product-forge/core/schema_validator.py`
- `product-forge/core/visual_qa.py`
- `product-forge/core/licensing.py`
- `product-forge/core/lock_manager.py`
- `product-forge/core/version_manager.py`
- `product-forge/core/test_matrix.py`

### Targeted only (not certified)

- `product-forge/config/file-manifest.json`
- `product-forge/config/model-catalog.json`
- `product-forge/config/model-tier.json`
- `product-forge/config/store-registry.json`
- `product-forge/core/pipeline_telemetry.py`
- `product-forge/core/marketing.py`
- `product-forge/core/traceability.py`
- `product-forge/core/workflow_docs.py`
- `product-forge/scripts/dev/gen_docs_index.py`
- `product-forge/scripts/gen_model_registry.py`

### New findings (11)

**PF-326 — P1 — [`core/licensing.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/licensing.py)**

- Evidence: verify_key returns signed but expired payload with expired=True instead of rejecting it; downstream callers may accept it unless they separately check expiration.
- Remediation: Return invalid for expired keys by default and require explicit administrative inspection to retrieve expired payloads.
- Validation: static source review only; no runtime reproduction.

**PF-327 — P1 — [`core/licensing.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/licensing.py)**

- Evidence: verify_key checks HMAC and expiration metadata but not licenses.json revocation status; revoked signed keys remain cryptographically valid.
- Remediation: Enforce revocation and current tenant subscription state at entitlement boundary.
- Validation: static source review only; no runtime reproduction.

**PF-328 — P1 — [`core/lock_manager.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/lock_manager.py)**

- Evidence: acquire_lock uses exists/read followed by fixed .tmp write and rename; no exclusive create/CAS, allowing concurrent contenders to overwrite lock ownership.
- Remediation: Use atomic O_EXCL or OS locking with unique temp files and holder-bound fencing tokens.
- Validation: static source review only; no runtime reproduction.

**PF-329 — P1 — [`core/lock_manager.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/lock_manager.py)**

- Evidence: _refresh_lock and extend_lock unlink the existing lock before renaming a fixed .tmp; this creates an unlocked window and races with other holders.
- Remediation: Implement atomic holder-checked compare-and-swap under OS-level lock; never unlink before replacement.
- Validation: static source review only; no runtime reproduction.

**PF-330 — P1 — [`core/visual_qa.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/visual_qa.py)**

- Evidence: analyze_screenshot_vision returns fixed numeric aesthetic scores and generic issues regardless of screenshot; run_visual_qa reports these as vision_analysis after capture.
- Remediation: Label placeholder explicitly and exclude it from verification or integrate actual vision inspection with provenance.
- Validation: static source review only; no runtime reproduction.

**PF-331 — P1 — [`core/visual_qa.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/visual_qa.py)**

- Evidence: no_empty_links check rejects nearly every HTML document containing a normal <a href...> anchor, while heading hierarchy always passes; pass/fail scores are unreliable.
- Remediation: Use an HTML parser and DOM-based accessible-name/heading checks with fixtures.
- Validation: static source review only; no runtime reproduction.

**PF-332 — P1 — [`core/test_matrix.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/test_matrix.py)**

- Evidence: generate_bdd writes TODO step definitions whose Given/When/Then callbacks contain no assertions; generated scaffolds can be mistaken for real tests.
- Remediation: Mark generated steps pending and fail quality gates until meaningful assertions and evidence exist.
- Validation: static source review only; no runtime reproduction.

**PF-333 — P1 — [`core/test_matrix.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/test_matrix.py)**

- Evidence: register_kit interpolates unvalidated name into test-framework/kits path and writes kit.json without path containment or atomicity.
- Remediation: Validate kit IDs and resolve destination beneath kits root; write atomically.
- Validation: static source review only; no runtime reproduction.

**PF-334 — P2 — [`core/schema_validator.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/schema_validator.py)**

- Evidence: validate_agent_md never appends ordinary lines to section_content; parsed sections are empty and most expected sections are dropped before schema validation.
- Remediation: Append non-heading content while in_section; add frontmatter and section parsing regression tests.
- Validation: static source review only; no runtime reproduction.

**PF-335 — P2 — [`core/version_manager.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/version_manager.py)**

- Evidence: bump_from_commits calls bump() and then add_changelog_entry() but entries do not carry release version; generate_changelog defaults them to current version, reassigning old changes after subsequent bumps.
- Remediation: Stamp each entry with its release version at creation and migrate legacy entries.
- Validation: static source review only; no runtime reproduction.

**PF-336 — P2 — [`core/licensing.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/licensing.py)**

- Evidence: issue_key accepts unknown tier while silently deriving trial limits, producing a signed payload naming a tier that entled() rejects; inconsistent entitlement metadata.
- Remediation: Reject unknown tiers at issuance and validate payload schema before signing.
- Validation: static source review only; no runtime reproduction.

### Cross-cutting priorities

1. Fail closed on expired/revoked license credentials and enforce entitlement state at the use boundary.
2. Replace non-exclusive project locks with atomic, holder-bound acquisition/refresh.
3. Separate real QA evidence from placeholder vision scores and test scaffolds.
4. Repair schema parser and ensure changelog entries retain their originating version.


## Batch AS — complete-source static review, 2026-09-28

**Disposition:** 16 previously pending paths examined; **6 complete pinned-source static reviews**, **10 initial-source inspections only** (not certified). Cumulative **297/394 complete**, **97 pending**. No runtime tests or repository changes.

### Newly fully reviewed (6)

- `product-forge/core/tech_stack.py`
- `product-forge/core/video_generation.py`
- `product-forge/core/product_design_spec.py`
- `product-forge/core/domain_research.py`
- `product-forge/core/integration_advisor.py`
- `product-forge/core/websocket_manager.py`

### Initial source only, not certified (10)

- `product-forge/core/business_skills_selector.py`
- `product-forge/core/customer_onboarding.py`
- `product-forge/core/mobile_tester.py`
- `product-forge/core/marketing.py`
- `product-forge/core/presentation_generator.py`
- `product-forge/core/skills_registry.py`
- `product-forge/core/service_catalog.py`
- `product-forge/core/workflow_docs.py`
- `product-forge/core/views.py`
- `product-forge/core/product_plan.py`

### New findings (8)

**PF-337 — P1 — [`core/video_generation.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/video_generation.py)**

- Evidence: FFmpeg shell script interpolates unescaped scene.title and output_dir into shell commands and drawtext; arbitrary product input can break commands or enable command injection if the script is run.
- Remediation: Use argument arrays and FFmpeg drawtext escaping, shell-quote every path, and treat generated scripts as untrusted.
- Validation: static source review only; no runtime reproduction.

**PF-338 — P1 — [`core/video_generation.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/video_generation.py)**

- Evidence: Generated scene clips use a color-only video source without audio; final background-music command references [0:a], which is absent, so the documented pipeline cannot complete as generated.
- Remediation: Create silent audio explicitly or mix only available streams, and add an end-to-end media smoke test.
- Validation: static source review only; no runtime reproduction.

**PF-339 — P1 — [`core/websocket_manager.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/websocket_manager.py)**

- Evidence: websocket_endpoint accepts arbitrary topic subscriptions and get_stats without any authentication or per-project authorization check in this module; broadcast pipeline events use project-specific topics.
- Remediation: Require authenticated principal at handshake and authorize each topic and stats request; validate upstream route enforcement.
- Validation: static source review only; no runtime reproduction.

**PF-340 — P1 — [`core/domain_research.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/domain_research.py)**

- Evidence: Research reports present hard-coded domain trend adoption_rate values (for example 65% embedded finance and 75% telemedicine) as factual rates with no source, measurement population, or freshness provenance.
- Remediation: Remove unsupported numerical adoption claims or attach dated cited evidence and scope.
- Validation: static source review only; no runtime reproduction.

**PF-341 — P2 — [`core/product_design_spec.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/product_design_spec.py)**

- Evidence: _extract_section and _extract_list match any line containing section keywords and markdown markers; _extract_list continues across bold non-heading sections and may blend unrelated bullets into canonical design spec.
- Remediation: Parse markdown heading hierarchy explicitly, preserve source provenance, and test section boundary cases.
- Validation: static source review only; no runtime reproduction.

**PF-342 — P2 — [`core/tech_stack.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/tech_stack.py)**

- Evidence: build_decision compares requested technologies only against chosen languages/frameworks; requested database, cache, or deployment selections are marked changed even when honored in chosen database/cache/deploy fields.
- Remediation: Normalize and compare all supported technology dimensions before requesting change approval.
- Validation: static source review only; no runtime reproduction.

**PF-343 — P2 — [`core/integration_advisor.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/integration_advisor.py)**

- Evidence: recommend and apply_choices suppress persistence exceptions and still return in-memory recommendations/choices, allowing callers to believe integration approvals were saved when no file was written.
- Remediation: Return explicit persisted status and fail closed on committed choices when writes fail.
- Validation: static source review only; no runtime reproduction.

**PF-344 — P2 — [`core/websocket_manager.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/websocket_manager.py)**

- Evidence: setup_ws_events monkey-patches intake_api endpoint symbols after route registration; registered FastAPI routes can retain original endpoint references and bypass the wrappers/events.
- Remediation: Emit events inside registered handlers or use injected event hooks and verify actual route integration.
- Validation: static source review only; no runtime reproduction.

### Cross-cutting priorities

1. Replace unsafe FFmpeg shell-script construction and verify generated media pipeline with actual video/audio fixtures.
2. Authenticate and authorize WebSocket topic subscriptions and stats; confirm registered route event wiring.
3. Require provenance for domain research numerical claims.
4. Harden canonical design-spec extraction, stack-change detection, and persisted integration approvals.


## Batch AT — full source static review (2026-09-28)

**18 distinct pending files examined: 7 complete source reviews, 11 targeted inspections; 304/394 cumulative, 90 pending.** All source reads use pinned commit e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374. No runtime tests or fixes.

### Fully reviewed
- [`product-forge/config/file-manifest.json`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/config/file-manifest.json)
- [`product-forge/core/cost_modeling.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/cost_modeling.py)
- [`product-forge/core/pipeline_telemetry.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/pipeline_telemetry.py)
- [`product-forge/core/interactive.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/interactive.py)
- [`product-forge/core/verification_runner.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/verification_runner.py)
- [`product-forge/core/qa_intelligence.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/qa_intelligence.py)
- [`product-forge/core/spec_review.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/spec_review.py)

### Targeted inspection only — not certified
- `product-forge/core/service_catalog.py`
- `product-forge/core/skills_registry.py`
- `product-forge/core/marketing.py`
- `product-forge/core/output_checklist.py`
- `product-forge/core/mobile_tester.py`
- `product-forge/core/workflow_docs.py`
- `product-forge/core/views.py`
- `product-forge/core/product_plan.py`
- `product-forge/core/customer_onboarding.py`
- `product-forge/core/knowledge_compliance_checker.py`
- `product-forge/core/defect_loop.py`

### New findings

**PF-345 — P1 — [`core/interactive.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/interactive.py)**

- Evidence: ask_many marks unanswered/timed-out or stopped prompts as answered by calling answer(..., default); this converts a default into an apparent explicit human decision.
- Remediation: Keep unanswered requests timed_out/stopped; never call answer for defaults; make approval callers require explicitly answered status.
- Validation: static source review only; no runtime reproduction.

**PF-346 — P1 — [`core/interactive.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/interactive.py)**

- Evidence: _lock returns None after 50 retries, but _submit/answer/_mark_timeout still read and rewrite prompts.json without a lock; _unlock(None) also suppresses the error.
- Remediation: Raise a lock-acquisition error or use a robust cross-platform lock; do not write without ownership.
- Validation: static source review only; no runtime reproduction.

**PF-347 — P1 — [`core/verification_runner.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/verification_runner.py)**

- Evidence: _augment_nfr catches every exception and silently continues; a failed NFR runner may leave a passing base test result and no NFR failure evidence.
- Remediation: Append explicit failed NFR execution evidence and fail the applicable suite on runner errors.
- Validation: static source review only; no runtime reproduction.

**PF-348 — P1 — [`core/verification_runner.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/verification_runner.py)**

- Evidence: Node branch marks ran=True when package.json exists but if no test/build scripts or no npm/pnpm it returns no results; Python branch runs pytest when any Python source exists, but Go/Rust claimed in docstring are not implemented.
- Remediation: Differentiate unsupported/missing runner from verified; implement or explicitly report Go/Rust; require selected categories actually executed.
- Validation: static source review only; no runtime reproduction.

**PF-349 — P1 — [`core/pipeline_telemetry.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/pipeline_telemetry.py)**

- Evidence: budget_status evaluates hard_cost/hard_tokens only inside if soft_cost or soft_tokens; a hard-only budget can exceed its limit while status remains n/a.
- Remediation: Evaluate hard limits independently of soft-budget presence and emit hard-limit alerts.
- Validation: static source review only; no runtime reproduction.

**PF-350 — P2 — [`core/pipeline_telemetry.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/pipeline_telemetry.py)**

- Evidence: audit_index and timing_index use only (stage_id, agent_id), so repeated agent invocations overwrite earlier run records and can attach wrong cache/finish/timing metadata.
- Remediation: Index by run/invocation ID and aggregate all invocations; reconcile telemetry totals against ledger.
- Validation: static source review only; no runtime reproduction.

**PF-351 — P1 — [`core/qa_intelligence.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/qa_intelligence.py)**

- Evidence: _age_days returns 0 on malformed/missing defect timestamps, preventing SLA breach alerts for defects whose creation time cannot be parsed.
- Remediation: Flag invalid timestamps as unknown/high-risk evidence and prevent missing timestamps from silently clearing aging alerts.
- Validation: static source review only; no runtime reproduction.

**PF-352 — P1 — [`core/spec_review.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/spec_review.py)**

- Evidence: summary returns {} on unreadable/missing review evidence and blocking_open defaults to zero; callers relying on blocking_open can treat absent QA review as no blocker.
- Remediation: Require a valid persisted review record and fail closed when evidence is absent or malformed.
- Validation: static source review only; no runtime reproduction.

**PF-353 — P1 — [`core/spec_review.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/spec_review.py)**

- Evidence: update_finding accepts arbitrary status and waived without validating authorized approver, resolution evidence, or HIL decision; blocking findings can be cleared by an unverified status update.
- Remediation: Validate transition and approver permissions, require evidence and explicit waiver authorization, and retain immutable audit history.
- Validation: static source review only; no runtime reproduction.

**PF-354 — P2 — [`core/cost_modeling.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/cost_modeling.py)**

- Evidence: estimate_product_costs ignores product_type and always uses hard-coded AWS profiles; unknown providers and instance types silently fall back to arbitrary prices without freshness or region.
- Remediation: Make cost estimates provider/region/product-specific, require dated pricing provenance, and label unknown prices as estimates or errors.
- Validation: static source review only; no runtime reproduction.

### Cross-cutting priorities

1. Fail closed on missing review evidence and unanswered human prompts.
2. Make NFR verification failures visible and independently enforce hard budgets.
3. Add invocation-level telemetry provenance and dated pricing inputs.


## Batch AU — full source static review (2026-09-28)

**11 distinct pending files examined: 3 complete source reviews, 8 targeted inspections; 307/394 cumulative, 87 pending.** All source reads use pinned commit e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374. No runtime tests or fixes. Legacy views are reviewed for security and consistency only; dashboard redesign remains out of scope.

### Fully reviewed
- [`product-forge/core/defect_loop.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/defect_loop.py)
- [`product-forge/core/knowledge_compliance_checker.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/knowledge_compliance_checker.py)
- [`product-forge/core/views.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/views.py)

### Targeted inspection only — not certified
- `product-forge/core/output_checklist.py`
- `product-forge/core/mobile_tester.py`
- `product-forge/core/workflow_docs.py`
- `product-forge/core/product_plan.py`
- `product-forge/core/marketing.py`
- `product-forge/core/customer_onboarding.py`
- `product-forge/core/service_catalog.py`
- `product-forge/core/skills_registry.py`

### New findings

**PF-355 — P1 — [`core/defect_loop.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/defect_loop.py)**

- Evidence: reconcile(all_passed=True) resolves, verifies, and closes every open defect without matching individual test IDs or confirming each defect was exercised.
- Remediation: Require defect-to-test mapping and individual passing execution evidence; preserve unresolved defects on aggregate-only suite results.
- Validation: static source review only; no runtime reproduction.

**PF-356 — P1 — [`core/defect_loop.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/defect_loop.py)**

- Evidence: open_defects returns [] on tracker exceptions, so defect_brief can present no open defects when the defect store is unavailable.
- Remediation: Return an explicit error/unavailable state and block defect-dependent closure until tracker access succeeds.
- Validation: static source review only; no runtime reproduction.

**PF-357 — P1 — [`core/knowledge_compliance_checker.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/knowledge_compliance_checker.py)**

- Evidence: ComplianceResult.passed checks only critical_count==0, while configured security checks default to medium and missing or unreadable artifacts are skipped; empty coverage can pass.
- Remediation: Require nonzero applicable checks, verified artifact reads and explicit security-policy severity thresholds; fail closed on missing evidence.
- Validation: static source review only; no runtime reproduction.

**PF-358 — P2 — [`core/knowledge_compliance_checker.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/knowledge_compliance_checker.py)**

- Evidence: role_missing is calculated before guidelines_loaded is populated and the dynamically assigned role_missing/role_layers fields are absent from to_dict, so role coverage is lost in persisted results.
- Remediation: Compute role coverage after guideline resolution and include role coverage in the declared result schema and serialization.
- Validation: static source review only; no runtime reproduction.

**PF-359 — P1 — [`core/views.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/views.py)**

- Evidence: render_backlog_html injects raw json.dumps(rows) inside an HTML script element; backlog titles containing </script> can terminate the script and inject markup/script.
- Remediation: Use script-safe JSON serialization (escape < and script terminators), a JSON script data element, or external JSON fetched with a strict CSP.
- Validation: static source review only; no runtime reproduction.

**PF-360 — P2 — [`core/views.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/views.py)**

- Evidence: render_backlog_html describes a live fetch of /api/backlog/all, but refresh() reloads the page and the 15-second timer only reloads; static HTML never fetches API changes.
- Remediation: Implement the documented API polling with error/status handling or relabel the page as regenerated snapshot-only.
- Validation: static source review only; no runtime reproduction.

**PF-361 — P2 — [`core/defect_loop.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/defect_loop.py)**

- Evidence: route_stage_issues carries feature_id from a previous issue when the next issue lacks one, so later defects can be linked to the wrong feature.
- Remediation: Compute feature_id independently for each issue; validate feature IDs before linking.
- Validation: static source review only; no runtime reproduction.

### Cross-cutting priorities

1. Do not auto-close defects from aggregate suite success; require test-to-defect evidence.
2. Make compliance gates fail closed on missing evidence and enforce security severity policy.
3. Escape JSON embedded in generated HTML; avoid treating legacy snapshot views as live API integrations.


## Batch AV — targeted follow-up review (2026-09-28)

**11 pending files revisited; 0 complete source reviews; 11 targeted inspections. Cumulative remains 307/394, 87 pending.** Source retrieval hit a connector call limit before complete manual source reviews could be completed. Do not count any AV file as certified. No runtime tests or code changes.

### Targeted inspections — not certified
- [`product-forge/core/service_catalog.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/service_catalog.py)
- [`product-forge/core/skills_registry.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/skills_registry.py)
- [`product-forge/core/output_checklist.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/output_checklist.py)
- [`product-forge/core/marketing.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/marketing.py)
- [`product-forge/core/customer_onboarding.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/customer_onboarding.py)
- [`product-forge/core/mobile_tester.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/mobile_tester.py)
- [`product-forge/core/workflow_docs.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/workflow_docs.py)
- [`product-forge/core/product_plan.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/product_plan.py)
- [`product-forge/config/model-catalog.json`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/config/model-catalog.json)
- [`product-forge/config/model-tier.json`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/config/model-tier.json)
- [`product-forge/config/store-registry.json`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/config/store-registry.json)

### New findings

**PF-362 — P2 — [`core/service_catalog.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/service_catalog.py)**

- Evidence: parse_service_selection silently returns the recommended service when a nonempty user selection is unrecognized; a typo can be treated as affirmative selection.
- Remediation: Return a validation error for unrecognized selections and require explicit confirmation of defaults.
- Validation: targeted static source inspection only; no runtime reproduction.

**PF-363 — P2 — [`core/skills_registry.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/skills_registry.py)**

- Evidence: Seed ModelRecommendation labels openai/whisper-1 as supporting both speech-to-text and text-to-speech, although the named model is transcription-only; stale hard-coded recommendations are marked refreshed without provider validation.
- Remediation: Separate STT/TTS capabilities and verify model availability and capabilities against dated provider catalogs before marking refreshed.
- Validation: targeted static source inspection only; no runtime reproduction.

**PF-364 — P1 — [`core/output_checklist.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/output_checklist.py)**

- Evidence: For per-feature agents, check_id_integrity_all failures are appended only to recommended_missing and explicitly excluded from essential_missing; the final ok result can remain true despite requirement-ID integrity failures.
- Remediation: Make duplicate/undefined requirement-ID integrity a separately enforced hard gate while allowing a controlled remediation path for uncertain parser results.
- Validation: targeted static source inspection only; no runtime reproduction.

**PF-365 — P2 — [`core/customer_onboarding.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/customer_onboarding.py)**

- Evidence: generate_onboarding_package writes generated onboarding materials directly to fixed filenames without preserving existing customized documents; repeated generation can overwrite user edits.
- Remediation: Use generated/versioned output paths or compare-before-overwrite with explicit approval and backups.
- Validation: targeted static source inspection only; no runtime reproduction.

**PF-366 — P2 — [`core/marketing.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/marketing.py)**

- Evidence: generate_marketing_package writes GTM, positioning and campaign documents directly to fixed filenames, replacing prior content on repeated generation.
- Remediation: Version generated marketing packages or require explicit overwrite approval with change diff and backup.
- Validation: targeted static source inspection only; no runtime reproduction.

### Next-batch priority

Obtain complete source in manageable ranges for compact pending core modules, then certify only after manual end-to-end review. Follow with larger execution/orchestration modules.


## Batch AW — complete source review of compact pending core modules (2026-09-28)

**19 distinct pending files examined: 10 complete source static reviews; 9 targeted inspections (not certified). Cumulative 317/394; 77 pending.** No runtime tests or repository changes. All findings are static hypotheses requiring tests to establish exploitability or runtime impact.

### Fully reviewed — new certifications
- [`product-forge/core/run_plan.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/run_plan.py)
- [`product-forge/core/run_entry.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/run_entry.py)
- [`product-forge/core/test_framework_bridge.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/test_framework_bridge.py)
- [`product-forge/core/tool_registry.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/tool_registry.py)
- [`product-forge/core/product_ingestion.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/product_ingestion.py)
- [`product-forge/core/rerun_review.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/rerun_review.py)
- [`product-forge/core/pipeline_capabilities.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/pipeline_capabilities.py)
- [`product-forge/core/model_recommendation.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/model_recommendation.py)
- [`product-forge/core/model_catalog.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/model_catalog.py)
- [`product-forge/core/project_journal.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/project_journal.py)

### Targeted only — still pending
- [`product-forge/core/service_catalog.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/service_catalog.py)
- [`product-forge/core/skills_registry.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/skills_registry.py)
- [`product-forge/core/output_checklist.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/output_checklist.py)
- [`product-forge/core/customer_onboarding.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/customer_onboarding.py)
- [`product-forge/core/marketing.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/marketing.py)
- [`product-forge/core/product_plan.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/product_plan.py)
- [`product-forge/core/test_framework_integration.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/test_framework_integration.py)
- [`product-forge/core/product_analyzer.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/product_analyzer.py)
- [`product-forge/core/model_registry.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/model_registry.py)

### Findings and remediation

**PF-367 — P1 — [`core/tool_registry.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/tool_registry.py)**

- Evidence: _safe_path checks lexical abspath/commonpath but not resolved symlinks; read_file/write_file/list_dir can follow workspace symlinks to outside paths.
- Remediation: Resolve real paths before every filesystem operation, disallow symlink escapes, and protect against symlink swaps.
- Validation: complete static source review; runtime reproduction pending.

**PF-368 — P1 — [`core/tool_registry.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/tool_registry.py)**

- Evidence: http_get accepts arbitrary URLs with no host, scheme, DNS or private-network restrictions; execute dispatch does not enforce ToolSpec.requires_approval.
- Remediation: Enforce egress/SSRF policy and tool-specific approval and agent allowlist in the execution boundary.
- Validation: complete static source review; runtime reproduction pending.

**PF-369 — P1 — [`core/run_plan.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/run_plan.py)**

- Evidence: ensure_plan marks the plan confirmed and returns it even when save() swallows a persistence failure; apply_to_dag silently ignores skip errors.
- Remediation: Propagate persistence and DAG errors; require durable confirmed-plan write before advancing.
- Validation: complete static source review; runtime reproduction pending.

**PF-370 — P1 — [`core/run_entry.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/run_entry.py)**

- Evidence: begin_run reports ok=True after acquiring the lock even if backfill/reconcile raises, so an unreconciled run may proceed.
- Remediation: Fail or explicitly quarantine a run when reconciliation fails; release its lock and record the failure.
- Validation: complete static source review; runtime reproduction pending.

**PF-371 — P2 — [`core/test_framework_bridge.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/test_framework_bridge.py)**

- Evidence: Missing/malformed suite config and unknown test mode silently fall back to generic unit/api/integration/e2e categories, which may omit the requested NFR or packaging tests.
- Remediation: Fail closed for mandatory release suites and validate suite config and category coverage.
- Validation: complete static source review; runtime reproduction pending.

**PF-372 — P1 — [`core/product_ingestion.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/product_ingestion.py)**

- Evidence: Deprecated folder ingestion counts source files as imported but never copies them, then overwrites product-plan.json, traceability.json and agent_ledger.json with new empty structures.
- Remediation: Keep deprecated ingestion unreachable; replace with non-destructive source import, versioned metadata and preservation of existing project records.
- Validation: complete static source review; runtime reproduction pending.

**PF-373 — P1 — [`core/rerun_review.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/rerun_review.py)**

- Evidence: decide() accepts and persists any decision string without checking the documented continue/accept-recommendations/reject set; errors saving the decision are swallowed.
- Remediation: Validate decisions and require durable recorded approval before clearing or rerunning artifacts.
- Validation: complete static source review; runtime reproduction pending.

**PF-374 — P1 — [`core/pipeline_capabilities.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/pipeline_capabilities.py)**

- Evidence: _probe marks any non-None result successful, including False and {success:false}; on each run the product_ingestion probe can invoke deprecated destructive ingestion when src exists.
- Remediation: Use capability-specific success predicates and remove side-effectful ingestion from routine health probes.
- Validation: complete static source review; runtime reproduction pending.

**PF-375 — P1 — [`core/pipeline_capabilities.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/pipeline_capabilities.py)**

- Evidence: safe_write_json falls back to an unprotected direct overwrite when the safety layer fails, negating its atomicity/backup guarantee.
- Remediation: Fail closed for protected stores; report write errors rather than bypassing safety.
- Validation: complete static source review; runtime reproduction pending.

**PF-376 — P1 — [`core/model_recommendation.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/model_recommendation.py)**

- Evidence: recommend_multiple does not filter minimum quality or maximum cost and displays violating candidates; recommend_model fallback returns an arbitrary highest-quality model with estimated_cost=0 even when no model meets hard constraints.
- Remediation: Enforce hard constraints in all recommendation paths; return no eligible model with explicit infeasibility instead of a misleading fallback.
- Validation: complete static source review; runtime reproduction pending.

**PF-377 — P1 — [`core/model_catalog.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/model_catalog.py)**

- Evidence: fit() returns ok=True when required tool/reasoning/structured-output or context/output capability is unknown (None), potentially accepting unverified hard requirements.
- Remediation: Return unknown/non-eligible for missing hard capability evidence and require provider verification before selection.
- Validation: complete static source review; runtime reproduction pending.

**PF-378 — P1 — [`core/project_journal.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/project_journal.py)**

- Evidence: build_status treats every key in stage_summary as completed regardless of reported stage/agent status, and get_project_status returns persisted state without freshness checking.
- Remediation: Derive completion from explicit successful stage status and reject stale persisted status on resume.
- Validation: complete static source review; runtime reproduction pending.

### Follow-up tests

- Workspace symlink escape and SSRF/private-network HTTP tool tests.
- Failed plan-save/reconcile and rejected rerun-decision persistence tests.
- Missing suite config, model hard-requirement unknown, and false capability success tests.
- Existing-project ingestion data-preservation and stage-status freshness tests.


## Batch AX — agent configuration, messaging, intake and skill selection (2026-09-28)

**17 distinct pending files examined: 5 complete source static reviews; 12 targeted inspections (not certified). Cumulative 322/394; 72 pending.** No runtime tests or repository changes.

### Fully reviewed — new certifications
- [`product-forge/core/agent_migrator.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/agent_migrator.py)
- [`product-forge/core/business_skills_selector.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/business_skills_selector.py)
- [`product-forge/core/agent_messenger.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/agent_messenger.py)
- [`product-forge/core/agent_card_loader.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/agent_card_loader.py)
- [`product-forge/core/intake_files.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/intake_files.py)

### Targeted only — still pending
- [`product-forge/core/output_checklist.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/output_checklist.py)
- [`product-forge/core/compliance_verifier.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/compliance_verifier.py)
- [`product-forge/core/customer_onboarding.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/customer_onboarding.py)
- [`product-forge/core/marketing.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/marketing.py)
- [`product-forge/core/product_plan.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/product_plan.py)
- [`product-forge/core/service_catalog.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/service_catalog.py)
- [`product-forge/core/skills_registry.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/skills_registry.py)
- [`product-forge/core/agent_ledger.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/agent_ledger.py)
- [`product-forge/core/agent_memory.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/agent_memory.py)
- [`product-forge/core/budget_tracker.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/budget_tracker.py)
- [`product-forge/core/compliance_check.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/compliance_check.py)
- [`product-forge/core/cross_review.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/cross_review.py)

### Findings and remediation

**PF-379 — P1 — [`core/agent_messenger.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/agent_messenger.py)**

- Evidence: _save serializes MessageType/MessagePriority enums through json.dump(default=str), producing strings such as MessageType.NOTIFICATION; _load expects MessageType(value) with values like notification, so persisted history/queues cannot be reconstructed.
- Remediation: Serialize enum .value explicitly; add persistence round-trip tests.
- Validation: complete static source review; runtime reproduction pending.

**PF-380 — P1 — [`core/agent_messenger.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/agent_messenger.py)**

- Evidence: send persists only every tenth message; clear_queue, subscribe and mark_read do not persist state; crashes or restarts can replay cleared/read messages or lose recent sends.
- Remediation: Use a durable append-only queue or transactional persistence per state transition, with idempotent delivery/ACK.
- Validation: complete static source review; runtime reproduction pending.

**PF-381 — P1 — [`core/agent_card_loader.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/agent_card_loader.py)**

- Evidence: REQUIRED_SECTIONS lists Primary Functions, but _validate emits only WARNING when absent; valid rejects only ERROR, so missing required agent sections pass validation.
- Remediation: Make missing mandatory sections errors; validate against the actual standardized agent-card schema.
- Validation: complete static source review; runtime reproduction pending.

**PF-382 — P1 — [`core/agent_migrator.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/agent_migrator.py)**

- Evidence: compute_migration_diff rebuilds frontmatter with permission={} despite the comment saying permissions will be preserved, potentially stripping agent-specific tool restrictions on migration.
- Remediation: Parse and preserve full structured frontmatter and permissions; block migration when lossless round-trip cannot be guaranteed.
- Validation: complete static source review; runtime reproduction pending.

**PF-383 — P1 — [`core/agent_migrator.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/agent_migrator.py)**

- Evidence: apply_migration copies backup to a fixed nested .backups directory without creating its parent, and overwrites agent files directly; migration can fail before backup or leave a partial file after write errors.
- Remediation: Create versioned backup directory, fsync backup and use atomic replacement after diff approval.
- Validation: complete static source review; runtime reproduction pending.

**PF-384 — P2 — [`core/business_skills_selector.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/business_skills_selector.py)**

- Evidence: TECHSTACK_GUIDELINES maps Vue/Angular/Svelte/Flutter to React guidance, GCP/Azure to AWS guidance, and Java/C# to Python style guidance, risking unsuitable generated architecture and coding standards.
- Remediation: Use stack-specific guideline mappings; report missing guidance explicitly instead of silently substituting unrelated stacks.
- Validation: complete static source review; runtime reproduction pending.

**PF-385 — P1 — [`core/intake_files.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/intake_files.py)**

- Evidence: store_dir passes _safe_name(source) to os.path.join without rejecting dot-only values; source=".." resolves outside _files, undermining intended intake archive containment.
- Remediation: Reject dot-only source names and enforce resolved-path containment beneath _FILES_ROOT.
- Validation: complete static source review; runtime reproduction pending.

**PF-386 — P2 — [`core/intake_files.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/intake_files.py)**

- Evidence: extract() returns ok=True for binary/image files without text and ingest_file substitutes a descriptive placeholder body; downstream ingestion may treat a placeholder as extracted document evidence.
- Remediation: Expose separate archived/extracted flags and require real extracted content before promoting document-derived claims.
- Validation: complete static source review; runtime reproduction pending.

### Follow-up tests

- Enum message serialization and restart/ACK replay tests.
- Required agent-card section enforcement and migration permission-preservation round-trip.
- Intake source traversal and binary placeholder provenance tests.


## Batch AY — complete static source review, 2026-09-28

**Disposition:** 20 pending paths inspected; **6 complete pinned-source static reviews**, **14 targeted-only inspections**. Cumulative **328/394 complete**, **66 pending**. No runtime tests or repository code changes.

### Newly fully reviewed (6)

- `product-forge/core/qa_cycles.py`
- `product-forge/core/squad_manager.py`
- `product-forge/core/test_adapters.py`
- `product-forge/core/vcs.py`
- `product-forge/core/agent_ledger.py`
- `product-forge/core/cross_review.py`

### Targeted only (not certified)

- `product-forge/core/customer_onboarding.py`
- `product-forge/core/marketing.py`
- `product-forge/core/output_checklist.py`
- `product-forge/core/product_plan.py`
- `product-forge/core/service_catalog.py`
- `product-forge/core/skills_registry.py`
- `product-forge/core/workflow_docs.py`
- `product-forge/scripts/pipeline.py`
- `product-forge/scripts/run_pipeline.py`
- `product-forge/core/mobile_tester.py`
- `product-forge/core/portfolio.py`
- `product-forge/core/presentation_generator.py`
- `product-forge/core/product_analyzer.py`
- `product-forge/core/compliance_check.py`

### New findings (10)

**PF-387 — P1 — [`core/vcs.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/vcs.py)**

- Evidence: init() ignores failed git init/checkout/add/commit and unconditionally returns ok=True; downstream may assume a repository was initialized.
- Remediation: Propagate each Git command failure; only report success after verifying repository, expected branches, and commit.
- Validation: static source review only; no runtime reproduction.

**PF-388 — P1 — [`core/vcs.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/vcs.py)**

- Evidence: merge() ignores checkout(target) result and can merge on the wrong current branch if checkout fails.
- Remediation: Abort on checkout failure and verify current branch equals target before merge.
- Validation: static source review only; no runtime reproduction.

**PF-389 — P1 — [`core/qa_cycles.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/qa_cycles.py)**

- Evidence: STAGE_CYCLES maps stage 7 to full, but default_suites defines no full suite and ensure_suites creates no full cycle; stage 7 cannot resolve its declared cycle.
- Remediation: Define and persist a full suite or map stage 7 to a defined cycle; test every stage mapping.
- Validation: static source review only; no runtime reproduction.

**PF-390 — P1 — [`core/cross_review.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/cross_review.py)**

- Evidence: address_feedback marks an issue addressed without a reviewer verification state, and update_review_status can mark a review completed irrespective of unresolved critical feedback.
- Remediation: Separate author response from reviewer-verified closure; block completed/approved verdicts while mandatory feedback remains unresolved.
- Validation: static source review only; no runtime reproduction.

**PF-391 — P1 — [`core/agent_ledger.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/agent_ledger.py)**

- Evidence: record_work uses len(work_items)+1 for IDs and _save directly overwrites JSON without a lock or atomic replace; concurrent writers can duplicate IDs or lose records.
- Remediation: Use UUID/ULID IDs, transactional/locked writes and atomic replace; test concurrent recording.
- Validation: static source review only; no runtime reproduction.

**PF-392 — P2 — [`core/squad_manager.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/squad_manager.py)**

- Evidence: analyze_task uses substring keyword matches (e.g. build selects both implement and devops), ignores stage and agent capacity, and form_squad truncates alphabetically to max_agents; required capabilities can be dropped.
- Remediation: Select by explicit required capabilities, stage, availability, permissions and budget; detect unfilled roles instead of silent truncation.
- Validation: static source review only; no runtime reproduction.

**PF-393 — P1 — [`core/test_adapters.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/test_adapters.py)**

- Evidence: NodeAdapter.command ignores requested test category and defaults to one generic npm/playwright/jest command; category-specific results can be reported from the same generic run.
- Remediation: Resolve category-specific scripts and paths and require category evidence in the returned test result.
- Validation: static source review only; no runtime reproduction.

**PF-394 — P2 — [`core/test_adapters.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/test_adapters.py)**

- Evidence: select_adapter prioritizes DesktopAdapter before NodeAdapter and can return an empty command for Electron/Tauri projects without E2E scripts even when npm test is present only in a nonstandard location; run_tests returns ok=None.
- Remediation: Explicitly distinguish unavailable from passed and configure a verified fallback for desktop test categories.
- Validation: static source review only; no runtime reproduction.

**PF-395 — P1 — [`core/qa_cycles.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/qa_cycles.py)**

- Evidence: ensure_suites catches SuiteManager and cycles.json write failures, logs them, but returns suites and cycles as though persisted successfully.
- Remediation: Return explicit persistence status or raise; fail QA setup when required cycle registration fails.
- Validation: static source review only; no runtime reproduction.

**PF-396 — P2 — [`core/cross_review.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/cross_review.py)**

- Evidence: get_agent_quality_score returns 100 when an agent has no reviews or feedback; unreviewed work receives a perfect numeric quality score.
- Remediation: Return unrated/no evidence when no completed reviews exist and separate severity, remediation and coverage.
- Validation: static source review only; no runtime reproduction.

### Cross-cutting priorities

1. Fail closed and verify branch/repository state on Git operations.
2. Ensure every pipeline QA stage has a registered, persisted test cycle.
3. Make cross-review closure evidence-based and make agent ledgers concurrency-safe.
4. Preserve per-category test provenance rather than accepting generic runner results.


## Batch AZ — complete static source review, 2026-09-28

**Disposition:** 16 previously pending paths examined; **3 complete pinned-source static reviews**, **13 targeted-only inspections**. Cumulative **331/394 complete**, **63 pending**. No runtime tests or repository code changes.

### Newly fully reviewed (3)

- `product-forge/core/memory_api.py`
- `product-forge/core/portfolio.py`
- `product-forge/core/knowledge_router.py`

### Targeted only (not certified)

- `product-forge/core/service_catalog.py`
- `product-forge/core/skills_registry.py`
- `product-forge/core/output_checklist.py`
- `product-forge/core/marketing.py`
- `product-forge/core/customer_onboarding.py`
- `product-forge/core/product_plan.py`
- `product-forge/core/workflow_docs.py`
- `product-forge/scripts/pipeline.py`
- `product-forge/scripts/run_pipeline.py`
- `product-forge/core/mobile_tester.py`
- `product-forge/core/presentation_generator.py`
- `product-forge/core/product_analyzer.py`
- `product-forge/core/test_framework_integration.py`

### New findings (8)

**PF-397 — P1 — [`core/knowledge_router.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/knowledge_router.py)**

- Evidence: validate_resource checks repository-relative path, but get_resource_content opens resource.path relative to process CWD; legitimate routed content can be silently absent.
- Remediation: Resolve all resource reads against one validated repository root; test non-root working directories.
- Validation: static source review only; no runtime reproduction.

**PF-398 — P1 — [`core/knowledge_router.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/knowledge_router.py)**

- Evidence: register_resource accepts untrusted path; validate_resource joins it without containment and get_resource_content reads it directly, allowing registered path traversal outside the knowledge root.
- Remediation: Canonicalize and require contained paths at registration and read time; reject symlink escapes.
- Validation: static source review only; no runtime reproduction.

**PF-399 — P1 — [`core/portfolio.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/portfolio.py)**

- Evidence: worker_loop and run_supervisor catch all capacity-check errors and proceed to start jobs; quota/governor errors fail open.
- Remediation: Fail closed on capacity-check errors, surface actionable blocked state, and test unavailable governor.
- Validation: static source review only; no runtime reproduction.

**PF-400 — P1 — [`core/portfolio.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/portfolio.py)**

- Evidence: requeue_stale unconditionally resets every running legacy job to queued without checking worker liveness or ownership, allowing duplicate execution.
- Remediation: Requeue only confirmed dead/expired claims with leases and compare-and-swap ownership.
- Validation: static source review only; no runtime reproduction.

**PF-401 — P1 — [`core/portfolio.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/portfolio.py)**

- Evidence: Project strings are joined into products paths in register/control/worker_loop without validating a project slug or resolved-path containment.
- Remediation: Enforce project identifiers and resolved containment at all entry points.
- Validation: static source review only; no runtime reproduction.

**PF-402 — P2 — [`core/memory_api.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/memory_api.py)**

- Evidence: import_bundle exposes overwrite=True but ignores the argument and delegates to store_batch; callers may believe existing entries were replaced.
- Remediation: Implement explicit overwrite semantics or remove the parameter and reject unsupported requests.
- Validation: static source review only; no runtime reproduction.

**PF-403 — P1 — [`core/memory_api.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/memory_api.py)**

- Evidence: load_export/import_bundle do not validate bundle.project against the current MemoryAPI project; cross-project memory entries can be imported without an explicit cross-project migration approval.
- Remediation: Require project match or explicit authorized migration with provenance and audit records.
- Validation: static source review only; no runtime reproduction.

**PF-404 — P2 — [`core/memory_api.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/memory_api.py)**

- Evidence: delete_by_tag/source/expired increments deleted count without checking memory.delete return or exception; reported deletion count can exceed successful deletions.
- Remediation: Count confirmed deletions and return per-entry failures.
- Validation: static source review only; no runtime reproduction.

### Cross-cutting priorities

1. Fail closed on portfolio capacity and prevent duplicate claims.
2. Enforce project and knowledge resource path containment.
3. Make memory import project-scoped and clarify overwrite/deletion semantics.


## Batch BA — configuration and targeted source review, 2026-09-28

**Disposition:** 9 previously pending paths examined; **2 complete pinned-source configuration reviews**, **7 targeted-only inspections**. Cumulative **333/394 complete**, **61 pending**. No runtime tests or repository code changes.

### Newly fully reviewed (2)

- `product-forge/config/model-tier.json`
- `product-forge/config/store-registry.json`

**Configuration verification:** `model-tier.json` parses, contains 28 agent entries and five profiles; all 5 distinct base agent/stage model names exist in the pinned 632-entry model catalog, and profile model references were cross-checked against the catalog or their profile-local declarations. `store-registry.json` parses with 177 store records; every store record has owner, kind and scope. These structural checks do not establish runtime provider availability or enforcement of store rules.

### Targeted only (not certified)

- `product-forge/core/output_checklist.py`
- `product-forge/core/customer_onboarding.py`
- `product-forge/core/skills_registry.py`
- `product-forge/core/service_catalog.py`
- `product-forge/core/marketing.py`
- `product-forge/core/product_plan.py`
- `product-forge/core/workflow_docs.py`

### New findings (3)

**PF-405 — P1 — [`core/output_checklist.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/output_checklist.py)**

- Evidence: check() explicitly demotes failed check_id_integrity_all() results to recommended_missing rather than essential_missing; ok remains true when section headings exist despite duplicate or undefined requirement IDs.
- Remediation: Separate advisory parser noise from deterministic integrity failures; require an explicit blocking policy and test duplicate/undefined IDs.
- Validation: static inspection only; no runtime reproduction.

**PF-406 — P2 — [`config/store-registry.json`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/config/store-registry.json)**

- Evidence: The audit allowlist exempts the bare credential filename gcp-key.json; any matching filename can bypass the store ownership audit if the wired auditor applies this allowlist as documented.
- Remediation: Remove credential-file exceptions from the broad allowlist; enforce dedicated secret-storage rules and scan credential artifacts independently.
- Validation: static inspection only; no runtime reproduction.

**PF-407 — P2 — [`core/customer_onboarding.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/customer_onboarding.py)**

- Evidence: Generated welcome emails assert the product has helped thousands of customers without product-specific evidence; setup and support material contains placeholder support@example.com and generic pip/docker installation commands.
- Remediation: Require verified customer claims, configured support contacts and stack-specific tested installation instructions before marking onboarding material publishable.
- Validation: static inspection only; no runtime reproduction.

### Cross-cutting priorities

1. Make deterministic requirement-ID integrity violations block the relevant quality gate.
2. Remove credential-name exemptions from broad audit allowlists.
3. Validate customer-facing claims, support details and installation commands before publication.


## Batch BB — budget, queue, issue and project-state deep review (2026-09-28)

**Disposition:** 15 pending paths examined; **5 complete pinned-source static reviews**, **10 targeted-only inspections**. Cumulative **338/394 certified**, **56 pending**. No runtime tests or code changes.

### Newly certified (5)

- `product-forge/core/budget_tracker.py`
- `product-forge/core/output_checklist.py`
- `product-forge/core/issue_tracker.py`
- `product-forge/core/queue_manager.py`
- `product-forge/core/project_store.py`

### Targeted only (not certified)

- `product-forge/core/customer_onboarding.py`
- `product-forge/core/marketing.py`
- `product-forge/core/product_plan.py`
- `product-forge/core/workflow_docs.py`
- `product-forge/core/skills_registry.py`
- `product-forge/core/service_catalog.py`
- `product-forge/core/agent_memory.py`
- `product-forge/core/build_utility.py`
- `product-forge/core/mobile_tester.py`
- `product-forge/core/presentation_generator.py`

### New findings (8)

**PF-408 — P1 — [`core/budget_tracker.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/budget_tracker.py)**

- Evidence: Default budget windows are labeled hourly/daily/weekly but configured as 5/168/720 hours; nominal alert and spend controls therefore run over incorrect time horizons.
- Remediation: Set windows to 1/24/168 hours, define monthly separately if required, and add rollover tests.
- Validation: static source review only; no runtime reproduction.

**PF-409 — P1 — [`core/budget_tracker.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/budget_tracker.py)**

- Evidence: _load_budget catches every exception and returns empty windows; can_spend then iterates no windows and returns True, permitting spend when the budget store is unavailable.
- Remediation: Fail closed or use a separately validated durable emergency ceiling; test corrupt/unavailable store.
- Validation: static source review only; no runtime reproduction.

**PF-410 — P1 — [`core/budget_tracker.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/budget_tracker.py)**

- Evidence: record_spend and can_spend accept negative costs/amounts; negative spend can reduce recorded usage and negative requested spend can bypass the budget check.
- Remediation: Validate finite nonnegative costs and spend requests at entry points; test negative, NaN and infinite values.
- Validation: static source review only; no runtime reproduction.

**PF-411 — P1 — [`core/issue_tracker.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/issue_tracker.py)**

- Evidence: save_issue_list/load_issue_list interpolate project, stage and agent into filesystem paths without path containment; untrusted identifiers can traverse out of products/<project>/issues.
- Remediation: Validate identifiers, resolve and enforce project-root containment, and test traversal payloads.
- Validation: static source review only; no runtime reproduction.

**PF-412 — P2 — [`core/issue_tracker.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/issue_tracker.py)**

- Evidence: add_issue increments severity counters but does not update counters when issue severity changes or issues are removed; serialized summary may disagree with the issue list.
- Remediation: Derive counts from current issues when serializing and reporting, with mutation regression tests.
- Validation: static source review only; no runtime reproduction.

**PF-413 — P2 — [`core/queue_manager.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/queue_manager.py)**

- Evidence: get_statistics labels queue[0] and queue[-1] as oldest/newest, but enqueue sorts by priority first; timestamps are not globally ordered and statistics can be wrong.
- Remediation: Compute min/max by queued_at independently of scheduling priority.
- Validation: static source review only; no runtime reproduction.

**PF-414 — P1 — [`core/project_store.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/project_store.py)**

- Evidence: path(project) joins the caller-supplied project directly into products_dir; save/update can write outside the intended project root via traversal identifiers.
- Remediation: Validate project slugs and resolve/verify containment before all reads and writes.
- Validation: static source review only; no runtime reproduction.

**PF-415 — P2 — [`core/output_checklist.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/output_checklist.py)**

- Evidence: check() reports ok=True and applicable=False when no checklist configuration exists, and has no hard failure for unreadable/empty artifacts beyond heading presence; an unconfigured agent can pass without verified output.
- Remediation: Distinguish not-applicable from pass; require expected artifacts and explicit policy for unconfigured agents.
- Validation: static source review only; no runtime reproduction.

### Previously identified issues reconfirmed, not double-counted

- PF-012: non-atomic multi-section budget writes.
- PF-013: spending check does not reserve budget across concurrent workers.
- PF-014: JSON queue read-modify-write loses concurrent updates.
- PF-053: project-store lock failure falls through to an unlocked mutation.
- PF-405: output checklist demotes failed requirement-ID integrity to advisory.

### Suggested regression coverage

Test corrupt budget files, 1/24/168-hour rollover, negative/nonfinite spend, project and issue path traversal, priority-vs-age queue statistics, and unconfigured output checklists.


## Batch BC — artifact, job, logging, NFR, deployment and intake deep review (2026-09-28)

**Disposition:** 28 pending paths examined; **8 complete pinned-source static reviews**, **20 targeted inspections**. Cumulative **346/394 certified**, **48 pending**. No runtime tests or repository modifications.

### Newly certified (8)

- `product-forge/core/artifact_store.py`
- `product-forge/core/job_manager.py`
- `product-forge/core/logging_manager.py`
- `product-forge/core/nfr_runner.py`
- `product-forge/core/phase3_advanced.py`
- `product-forge/core/conversation_compiler.py`
- `product-forge/core/deploy_providers.py`
- `product-forge/core/intake_channels.py`

### Targeted only (not certified)

- `product-forge/core/service_catalog.py`
- `product-forge/core/skills_registry.py`
- `product-forge/core/customer_onboarding.py`
- `product-forge/core/marketing.py`
- `product-forge/core/workflow_docs.py`
- `product-forge/core/product_plan.py`
- `product-forge/core/presentation_generator.py`
- `product-forge/core/product_analyzer.py`
- `product-forge/core/release_manager.py`
- `product-forge/core/test_framework_integration.py`
- `product-forge/scripts/pipeline.py`
- `product-forge/scripts/run_pipeline.py`
- `product-forge/core/agent_memory.py`
- `product-forge/core/build_utility.py`
- `product-forge/core/code_analyzer.py`
- `product-forge/core/compliance_check.py`
- `product-forge/core/compliance_verifier.py`
- `product-forge/core/conversation_models.py`
- `product-forge/core/mobile_tester.py`
- `product-forge/core/model_registry.py`

### New findings (12)

**PF-416 — P1 — [`core/job_manager.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/job_manager.py)**

- Evidence: enqueue() updates run_id, item_ids, actor, tier and schedule on an existing running project while retaining state=running; the active worker may finish under the wrong job metadata.
- Remediation: Reject enqueue of running project or store distinct run rows with immutable run identity.
- Validation: static source review only; no runtime reproduction.

**PF-417 — P1 — [`core/job_manager.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/job_manager.py)**

- Evidence: mark_paused(), resume(), cancel() and finish() do not require expected state or worker/run ownership; stale actors can mutate or finish another run.
- Remediation: Require compare-and-swap state, worker/run ID and authorization for every transition.
- Validation: static source review only; no runtime reproduction.

**PF-418 — P1 — [`core/deploy_providers.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/deploy_providers.py)**

- Evidence: run_deploy_up() and run_deploy() derive passed from checkable steps, potentially overriding provider verification failure; Kubernetes/Helm/command provider appends smoke results after computing ok.
- Remediation: Aggregate apply, verify, smoke and destroy statuses explicitly; missing verification must remain not-run.
- Validation: static source review only; no runtime reproduction.

**PF-419 — P1 — [`core/deploy_providers.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/deploy_providers.py)**

- Evidence: DockerProvider.destroy() executes docker compose down -v, deleting named volumes; Terraform destroy auto-approves without an explicit destruction approval in this module.
- Remediation: Make destructive cleanup opt-in with recorded approval and protected-data safeguards.
- Validation: static source review only; no runtime reproduction.

**PF-420 — P1 — [`core/intake_channels.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/intake_channels.py)**

- Evidence: _next_id() scans existing JSON indexes then adds one without a transaction or lock; concurrent intake submissions can reuse IN identifiers and overwrite index entries.
- Remediation: Use a transactional counter/unique constraint and atomic append/index update.
- Validation: static source review only; no runtime reproduction.

**PF-421 — P1 — [`core/intake_channels.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/intake_channels.py)**

- Evidence: close_verified() directly sets status=closed without checking the referenced backlog item verification despite its documented invariant.
- Remediation: Verify backlog item and evidence at this entry point and restrict arbitrary status updates.
- Validation: static source review only; no runtime reproduction.

**PF-422 — P1 — [`core/nfr_runner.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/nfr_runner.py)**

- Evidence: run_security()/run_gates() return empty lists when scanners or scripts are unavailable; minimal environment can have no executed security/a11y/performance checks without an explicit failing or not-run result.
- Remediation: Return mandatory-category coverage status and fail release gates on absent required evidence.
- Validation: static source review only; no runtime reproduction.

**PF-423 — P1 — [`core/nfr_runner.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/nfr_runner.py)**

- Evidence: run_bom() writes a minimal CycloneDX-like document with only manifest names, then reports ok=True; package_contents() creates a placeholder proprietary LICENSE and dependency-name-only NOTICE.
- Remediation: Mark these outputs provisional, require actual SBOM component inventory and reviewed licensing/third-party notices.
- Validation: static source review only; no runtime reproduction.

**PF-424 — P1 — [`core/artifact_store.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/artifact_store.py)**

- Evidence: create_or_update_artifact() joins caller-controlled agent into output filename without containment checks and overwrites directly; its version is capped at 2 with no preserved history.
- Remediation: Validate agent slug, enforce resolved stage-root containment, write atomically and retain immutable revisions.
- Validation: static source review only; no runtime reproduction.

**PF-425 — P2 — [`core/logging_manager.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/logging_manager.py)**

- Evidence: Custom RotatingFileHandler.emit() bypasses RotatingFileHandler.shouldRollover/doRollover, so stated 1MB x 5 rotation is not performed.
- Remediation: Delegate to superclass emit after formatting or explicitly perform rollover under handler lock.
- Validation: static source review only; no runtime reproduction.

**PF-426 — P2 — [`core/phase3_advanced.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/phase3_advanced.py)**

- Evidence: SemanticCache.get() never checks expires_at and caches only in memory despite defining cache_file; expired results may be reused, while restarts lose all entries.
- Remediation: Enforce expiry on reads and implement guarded persistence or remove unsupported durability claims.
- Validation: static source review only; no runtime reproduction.

**PF-427 — P2 — [`core/conversation_compiler.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/conversation_compiler.py)**

- Evidence: Deprecated compiler returns a fabricated generic idea when LLM extraction fails, and _adjudicate() does not perform its promised second model pass; compile_conversation can mark this output compiled.
- Remediation: Keep fallback explicitly unverified and never promote synthetic extraction to accepted compilation.
- Validation: static source review only; no runtime reproduction.

### Suggested regression coverage

Concurrent enqueue/claim/finish and intake ID allocation; worker-owned state transitions; provider failure-vs-step aggregation; missing scanner evidence; destructive deployment approvals; artifact path traversal and revision history; log rotation under load; semantic-cache TTL; LLM failure fallback classification.


## Batch BD — release and presentation generation deep review (2026-09-28)

**Disposition:** 11 pending paths examined; **2 complete pinned-source static reviews**, **9 targeted inspections**. Cumulative **348/394 certified**, **46 pending**. No runtime tests or repository modifications.

### Newly certified (2)

- `product-forge/core/release_manager.py`
- `product-forge/core/presentation_generator.py`

### Targeted only (not certified)

- `product-forge/core/customer_onboarding.py`
- `product-forge/core/marketing.py`
- `product-forge/core/service_catalog.py`
- `product-forge/core/skills_registry.py`
- `product-forge/core/workflow_docs.py`
- `product-forge/core/product_plan.py`
- `product-forge/core/test_framework_integration.py`
- `product-forge/core/product_analyzer.py`
- `product-forge/scripts/gen_model_registry.py`

### New findings (6)

**PF-428 — P1 — [`core/release_manager.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/release_manager.py)**

- Evidence: create_backup() copies only version.json and state.json; rollback() restores version.json alone, then returns success=True, without restoring application binaries, database or state.json.
- Remediation: Use verified full rollback snapshots and report exact restored components; require post-restore health checks.
- Validation: static source review only; no runtime reproduction.

**PF-429 — P1 — [`core/release_manager.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/release_manager.py)**

- Evidence: create_deploy_ticket() does not verify artifact_id/version integrity, update_deploy_status() accepts arbitrary status without transition or evidence checks; a caller can mark a deployment completed without verified deploy evidence.
- Remediation: Require registered verified artifact, guarded state transitions, deployment run identity and signed gate evidence.
- Validation: static source review only; no runtime reproduction.

**PF-430 — P1 — [`core/presentation_generator.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/presentation_generator.py)**

- Evidence: _generate_pptx() and _generate_pdf() write plain Markdown text to .pptx/.pdf on ImportError and return paths as though valid files were produced.
- Remediation: Fail with explicit dependency error or emit correctly named .md fallback with partial status and MIME validation.
- Validation: static source review only; no runtime reproduction.

**PF-431 — P1 — [`core/presentation_generator.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/presentation_generator.py)**

- Evidence: _generate_html() interpolates product and slide text into raw HTML without escaping, allowing stored script/markup injection in generated presentation pages.
- Remediation: HTML-escape all untrusted content and apply a restrictive content-security policy.
- Validation: static source review only; no runtime reproduction.

**PF-432 — P2 — [`core/presentation_generator.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/presentation_generator.py)**

- Evidence: VideoGenerator.generate_demo_video() produces script and shell commands, not a rendered demo video; generated ffmpeg command paths are unquoted and assume screenshots/narration exist.
- Remediation: Represent as a preparation package; validate inputs and execute a safe subprocess pipeline before claiming rendered video.
- Validation: static source review only; no runtime reproduction.

**PF-433 — P2 — [`core/release_manager.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/release_manager.py)**

- Evidence: estimate_footprint() returns a mutable object from base_footprints then multiplies fields in place for tech stack adjustments, making estimates sensitive to repeated stack entries; project path is also joined from caller input without explicit containment validation.
- Remediation: Normalize unique stack components, copy baseline footprint, and validate project slug/path containment.
- Validation: static source review only; no runtime reproduction.

### Suggested regression coverage

Missing presentation dependencies and file signature checks; HTML injection in slides; video absent input validation; artifact mismatch and arbitrary deployment transitions; full rollback restoration, failure injection and integrity checks.


## Batch BE — compliance verification and skills registry (2026-09-28)

**Disposition:** 8 pending paths examined; **2 complete pinned-source static reviews**, **6 targeted inspections**. Cumulative **350/394 certified**, **44 pending**. No runtime tests or repository modifications.

### Newly certified (2)

- `product-forge/core/compliance_verifier.py`
- `product-forge/core/skills_registry.py`

### Targeted only (not certified)

- `product-forge/core/marketing.py`
- `product-forge/core/customer_onboarding.py`
- `product-forge/core/service_catalog.py`
- `product-forge/core/workflow_docs.py`
- `product-forge/core/product_plan.py`
- `product-forge/scripts/gen_model_registry.py`

### New findings (5)

**PF-434 — P1 — [`core/compliance_verifier.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/compliance_verifier.py)**

- Evidence: VerificationReport.passed is all(r.passed for r in results), which returns True for an empty results list; unknown agent IDs and execute_verification with no checks produce empty passing reports.
- Remediation: Require a nonempty expected-check set and return not-configured/blocked status rather than PASS.
- Validation: static source review only; no runtime reproduction.

**PF-435 — P1 — [`core/compliance_verifier.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/compliance_verifier.py)**

- Evidence: build_verification_prompt silently skips unreadable artifact paths and includes only 6000 characters per file, stopping after 24000 characters, yet execute_verification can return PASS without proving required evidence was read.
- Remediation: Validate every required artifact, report omissions and truncation, and block PASS unless coverage requirements are met.
- Validation: static source review only; no runtime reproduction.

**PF-436 — P1 — [`core/compliance_verifier.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/compliance_verifier.py)**

- Evidence: _parse_verification_response uses bool(item.get("passed")), so the string "false" evaluates True; confidence is neither bounded nor used as a passing threshold.
- Remediation: Require boolean passed values, clamp/validate confidence and enforce minimum evidence-backed confidence.
- Validation: static source review only; no runtime reproduction.

**PF-437 — P1 — [`core/skills_registry.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/skills_registry.py)**

- Evidence: recommend_for_project returns hard-coded skill/MCP IDs and model recommendations without checking that IDs exist in the registry, agent tool permissions, current provider availability, or configured project budget; defaults also label Whisper speech-to-text as a text-to-speech-capable voice option.
- Remediation: Resolve recommendations against live registered capabilities and role policy; validate modality direction, budget and availability.
- Validation: static source review only; no runtime reproduction.

**PF-438 — P2 — [`core/skills_registry.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/skills_registry.py)**

- Evidence: seed_defaults calls add_skill/add_mcp_server/add_model_recommendation repeatedly; each call rewrites the same JSON registry nonatomically and without locking, risking lost updates and partially written state.
- Remediation: Stage defaults in memory and commit once using atomic replacement and a writer lock.
- Validation: static source review only; no runtime reproduction.

### Suggested regression coverage

Unknown-agent empty check set; missing/truncated evidence; verifier JSON string booleans and confidence bounds; recommendation ID and modality validity; concurrent registry seed/write failure injection.


## Batch BF — adoption, closure, Git isolation and intake (2026-09-28)

**Disposition:** 10 pending paths examined; **4 complete pinned-source static reviews**, **6 targeted metadata/contract inspections**. Cumulative **354/394 certified**, **40 pending**. No runtime tests or repository modifications.

### Newly certified (4)

- `product-forge/core/adopt_project.py`
- `product-forge/core/close_loop.py`
- `product-forge/core/git_manager.py`
- `product-forge/core/intake.py`

### Targeted only (not certified)

- `product-forge/core/marketing.py`
- `product-forge/core/customer_onboarding.py`
- `product-forge/core/service_catalog.py`
- `product-forge/core/workflow_docs.py`
- `product-forge/core/product_plan.py`
- `product-forge/scripts/gen_model_registry.py`

### New findings (8)

**PF-439 — P1 — [`core/adopt_project.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/adopt_project.py)**

- Evidence: adopt() joins the caller-provided name directly under PRODUCTS without validating or resolving containment; names with parent traversal can write project.json and adopted-project.md outside products.
- Remediation: Validate project slugs and enforce resolved-path containment before creating or copying anything.
- Validation: static source review only; no runtime reproduction.

**PF-440 — P1 — [`core/adopt_project.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/adopt_project.py)**

- Evidence: adopt(copy=True) silently suppresses each copy exception, skips copying a directory if the destination already exists, and still reports adoption success; a partial or stale project may be treated as imported.
- Remediation: Stage copy in a temporary directory, report per-file errors, verify expected content and commit atomically.
- Validation: static source review only; no runtime reproduction.

**PF-441 — P1 — [`core/close_loop.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/close_loop.py)**

- Evidence: _compliance_passed returns True when any *-latest.json says pass, without rejecting other failing or missing required compliance reports; verify_run can close backlog on incomplete compliance evidence.
- Remediation: Require the expected set of checks and fail if any mandatory report is missing, stale or failed.
- Validation: static source review only; no runtime reproduction.

**PF-442 — P1 — [`core/close_loop.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/close_loop.py)**

- Evidence: _tests_passed casts qa-manifest passed fields with bool(), so the string "false" evaluates True; _no_blocking_defects treats unreadable issue records as empty and non-blocking.
- Remediation: Require strict boolean test evidence and fail closed on malformed/unreadable defect records.
- Validation: static source review only; no runtime reproduction.

**PF-443 — P1 — [`core/git_manager.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/git_manager.py)**

- Evidence: create_project_branch calls create_branch(branch_name, create=True), but create_branch accepts only branch_name and start_point; safe_commit on main/master/None raises TypeError, catches it and returns False.
- Remediation: Correct branch creation API, check each Git command result, and cover main/master and detached HEAD cases.
- Validation: static source review only; no runtime reproduction.

**PF-444 — P1 — [`core/git_manager.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/git_manager.py)**

- Evidence: create_worktree calls create_branch(branch, create=True) with the same unsupported keyword and returns None after the TypeError only if caught as CalledProcessError (it is not), so worktree setup can raise unexpectedly.
- Remediation: Use the supported create_branch signature and add isolated worktree creation integration tests.
- Validation: static source review only; no runtime reproduction.

**PF-445 — P1 — [`core/intake.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/intake.py)**

- Evidence: _archive_raw joins the unvalidated source string directly under products/inbox; a crafted source containing parent traversal can redirect raw-payload JSON writes outside the intended inbox.
- Remediation: Constrain source to registered adapter identifiers and verify resolved-path containment.
- Validation: static source review only; no runtime reproduction.

**PF-446 — P2 — [`core/intake.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/intake.py)**

- Evidence: Source conversation deduplication uses only source_conversation_id and does not namespace it by source_platform; unrelated providers sharing an external ID can be incorrectly deduplicated.
- Remediation: Use a compound source-platform plus external-ID key and persist idempotency checks transactionally.
- Validation: static source review only; no runtime reproduction.

### Suggested regression coverage

Traversal attempts for project names and intake sources; partial copy and pre-existing project; mixed compliance report statuses; string false and malformed issues; branch/worktree creation; cross-provider duplicate external IDs.


## Batch BG — build evidence, self-improvement diffs and model analysis (2026-09-28)

**Disposition:** 11 previously pending paths examined; **3 complete pinned-source static reviews**, **8 targeted metadata/partial-source inspections**. Cumulative **357/394 certified**, **37 pending**. No runtime tests or repository modifications.

### Newly certified (3)

- `product-forge/core/build_utility.py`
- `product-forge/core/code_analyzer.py`
- `product-forge/scripts/dev/generate_model_analysis.py`

### Targeted only (not certified)

- `product-forge/scripts/gen_model_registry.py`
- `product-forge/core/marketing.py`
- `product-forge/core/customer_onboarding.py`
- `product-forge/core/service_catalog.py`
- `product-forge/core/workflow_docs.py`
- `product-forge/core/product_plan.py`
- `product-forge/core/compliance_check.py`
- `product-forge/core/mobile_tester.py`

### New findings (5)

**PF-447 — P1 — [`core/build_utility.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/build_utility.py)**

- Evidence: build_web invokes robocopy or cp without checking return code or validating copied files, then unconditionally returns success when the source dist/build/.next directory exists.
- Remediation: Use checked copy operations (shutil.copytree with verified outputs), propagate errors, and test copy-failure injection.
- Validation: static source review only; no runtime reproduction.

**PF-448 — P2 — [`core/build_utility.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/build_utility.py)**

- Evidence: build_ios and build_android take the first recursive .app/.apk from output directories without verifying freshness, build variant, signing, or relation to the just-completed build; stale artifacts can be packaged.
- Remediation: Clean or isolate build directories, inspect build manifest and artifact timestamps, verify release variant and signing.
- Validation: static source review only; no runtime reproduction.

**PF-449 — P1 — [`core/code_analyzer.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/code_analyzer.py)**

- Evidence: The Python improvement generator returns the original function unchanged; JSON improvement returns the input object; general HTML uses the first 50 existing lines as placeholder. analyze_improvement still returns ANALYZED and rollback_available=True.
- Remediation: Represent unsupported transformations as blocked/needs_generation and require a nonempty verified diff plus an actual rollback snapshot before declaring an actionable plan.
- Validation: static source review only; no runtime reproduction.

**PF-450 — P1 — [`core/code_analyzer.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/code_analyzer.py)**

- Evidence: All generated FileChange objects initialize file_path to an empty string; _generate_file_changes never fills it with rel_path. _assess_risk relies on change.file_path, so high-risk file names are never recognized and most changes are rated LOW.
- Remediation: Populate canonical repo-relative file_path on each change and enforce high-risk path classification and nonempty targets before plan approval.
- Validation: static source review only; no runtime reproduction.

**PF-451 — P2 — [`scripts/dev/generate_model_analysis.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/dev/generate_model_analysis.py)**

- Evidence: Both live provider fetches swallow exceptions into empty dictionaries; main still overwrites docs/modelanalysis.md with a timestamp and hard-coded tier recommendations/free model health claims, without distinguishing stale, failed or unverified data.
- Remediation: Fail or mark sections unavailable when fetches fail; timestamp each source independently, validate model availability and pricing, and preserve the last verified report.
- Validation: static source review only; no runtime reproduction.

### Suggested regression coverage

Copy failure and stale artifact injection; unchanged placeholder diffs; high-risk target path risk scoring; provider metadata fetch failure and stale-model claims.


## Batch BH — test-cycle integrity and customer-facing claims (2026-09-28)

**Disposition:** 5 pending paths examined; **1 complete pinned-source static review**, **4 targeted/partial-source inspections**. Cumulative **358/394 certified**, **36 pending**. No runtime tests or repository modifications.

### Newly certified (1)

- `product-forge/core/test_framework_integration.py`

### Targeted only (not certified)

- `product-forge/core/customer_onboarding.py`
- `product-forge/core/marketing.py`
- `product-forge/core/service_catalog.py`
- `product-forge/core/workflow_docs.py`

### New findings (5)

**PF-452 — P1 — [`core/test_framework_integration.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/test_framework_integration.py)**

- Evidence: run_cycle calls mgr.complete_cycle before _run_plan_item category runs and mobile results are executed. The returned status uses only boot failure or the primary runner status, so later category/mobile failures do not change overall status.
- Remediation: Complete the cycle after all test modalities finish and aggregate explicit pass/fail/unknown for primary, category, boot, mobile and lifecycle checks.
- Validation: static source inspection only; no runtime reproduction.

**PF-453 — P1 — [`core/test_framework_integration.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/test_framework_integration.py)**

- Evidence: register_project catches a projects.yaml write failure, prints an error, but returns the expected path. run_cycle continues after failed registration; missing test framework itself returns None, leaving callers to interpret the absence.
- Remediation: Return a structured registration result and fail the test gate on unavailable framework or failed registration unless an explicitly approved waiver exists.
- Validation: static source inspection only; no runtime reproduction.

**PF-454 — P1 — [`core/test_framework_integration.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/test_framework_integration.py)**

- Evidence: The Playwright BDD pre-generation command result is ignored, and optional extra test categories can be skipped if category directories/configs are absent. The primary suite can pass even when required category tests did not execute.
- Remediation: Treat required-category missing tests, BDD generation failures and missing runners as blocking outcomes; record planned vs executed category coverage.
- Validation: static source inspection only; no runtime reproduction.

**PF-455 — P2 — [`core/test_framework_integration.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/test_framework_integration.py)**

- Evidence: run_cycle writes BASE_URL and DEPLOY_URL into process-wide os.environ when starting a test app, but does not restore previous values after run_deploy_down. Later projects may inherit a prior project URL.
- Remediation: Pass URLs in scoped subprocess environments and restore prior environment values in finally.
- Validation: static source inspection only; no runtime reproduction.

**PF-456 — P1 — [`core/customer_onboarding.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/customer_onboarding.py)**

- Evidence: The onboarding package generator emits unverified assertions such as SOC 2 Type II certification, 100+ integrations, 14-day full-feature trial, refund guarantee and thousands of customers, plus generic installation commands regardless of product implementation.
- Remediation: Generate claims only from verified product manifests, compliance evidence and approved commercial terms; label unknown information as requiring confirmation.
- Validation: static source inspection only; no runtime reproduction.

### Suggested regression coverage

Failing category tests after a passing main suite; BDD pre-generation failure; missing framework or projects.yaml write failure; concurrent projects with different BASE_URL; approval-gated onboarding claim generation.


## Batch BI — model routing, prompt contracts, compliance and deprecated intake (2026-09-28)

**Disposition:** 4 previously pending files fully reviewed from the pinned commit; cumulative **362/394 certified**, **32 pending**. No runtime tests or repository changes.

### Newly certified (4)

- `product-forge/core/orchestrator/model_router.py`
- `product-forge/core/orchestrator/prompt_builder.py`
- `product-forge/core/orchestrator/compliance.py`
- `product-forge/core/intake_api.py`

### New findings (9)

**PF-457 — P1 — [`core/orchestrator/compliance.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/orchestrator/compliance.py)**

- Evidence: Multiple required or optional check exceptions (knowledge, code quality, stack, verification, test cycle, spec review, QA gate) are logged without marking the overall compliance result failed; validate verification with ran=False is explicitly skipped.
- Remediation: Represent every required check as pass/fail/unavailable and fail closed on exceptions, missing evidence and skipped verification unless an authorized waiver is recorded.
- Validation: static source review only; no runtime reproduction.

**PF-458 — P1 — [`core/orchestrator/compliance.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/orchestrator/compliance.py)**

- Evidence: run_rule_compliance converts a non-passing report with summary.total=0 to passed=True, so an agent without configured checks is treated as compliant.
- Remediation: Require an explicit applicability decision and baseline controls; distinguish not-applicable from pass.
- Validation: static source review only; no runtime reproduction.

**PF-459 — P1 — [`core/orchestrator/compliance.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/orchestrator/compliance.py)**

- Evidence: Stage 10a NO-GO can be overridden by a truthy qa.override_gonogo field in project.json; this module does not verify approval actor, provenance, expiry or reason.
- Remediation: Require a signed or otherwise authenticated, auditable approval record tied to the exact gate and run; never trust a mutable boolean alone.
- Validation: static source review only; no runtime reproduction.

**PF-460 — P1 — [`core/orchestrator/prompt_builder.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/orchestrator/prompt_builder.py)**

- Evidence: tool_directive mandates a Python src/<package>/main.py skeleton, requirements.txt and python -c for all implement/devops/fix agents, including non-Python products.
- Remediation: Generate stack-specific skeleton and test commands from the agreed tech-stack manifest, and test Go/Java/Node/mobile scenarios.
- Validation: static source review only; no runtime reproduction.

**PF-461 — P2 — [`core/orchestrator/prompt_builder.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/orchestrator/prompt_builder.py)**

- Evidence: The implement-ui branch in output_requirements is unreachable because an earlier agent_id.startswith("implement") branch always returns first.
- Remediation: Reorder specialized agent conditions before generic prefix matching, or compose common and role-specific directives.
- Validation: static source review only; no runtime reproduction.

**PF-462 — P1 — [`core/orchestrator/model_router.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/orchestrator/model_router.py)**

- Evidence: cheapest_opencode_go_model compares (cost_per_1k_input or 0)+(cost_per_1k_output or 0), treating missing prices as zero and potentially selecting an unknown-price model as cheapest.
- Remediation: Exclude unpriced models from cost optimization, require verified pricing, and record cost-estimate confidence.
- Validation: static source review only; no runtime reproduction.

**PF-463 — P2 — [`core/orchestrator/model_router.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/orchestrator/model_router.py)**

- Evidence: Unknown active profile names fall back silently to base configuration; malformed config files are skipped to later candidates, potentially changing cost or capability policy without explicit approval.
- Remediation: Validate profile existence and config schema; fail with an actionable configuration error for policy-controlled runs.
- Validation: static source review only; no runtime reproduction.

**PF-464 — P1 — [`core/intake_api.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/intake_api.py)**

- Evidence: Deprecated router declares no authentication/authorization dependencies for conversation retrieval, message listing, approval/rejection, project listing and change-package actions. If mounted, these endpoints expose or modify cross-project content.
- Remediation: Keep the deprecated router unmounted; if reactivated, require authenticated tenant-scoped RBAC and endpoint-level authorization tests.
- Validation: static source review only; no runtime reproduction.

**PF-465 — P2 — [`core/intake_api.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/intake_api.py)**

- Evidence: Conversation deduplication queries only source conversation_id, omitting source_platform, and action endpoints do not check expected prior status before approval or rejection.
- Remediation: Deduplicate on (source_platform, external_id) scoped by tenant and enforce state-transition preconditions.
- Validation: static source review only; no runtime reproduction.

### Suggested regression coverage

Missing verification files; check exceptions and empty rules; unauthorized QA override; non-Python implementation prompt; missing model pricing and invalid profiles; legacy intake authentication and tenant isolation if mounted.


## Batch BJ — model registry integrity and pending large-module triage (2026-09-28)

**Disposition:** 12 pending files examined; **2 certified** (one full 632-record structured catalog validation and one full 330-line generator review), **10 targeted** (not certified). Cumulative **364/394**, **30 pending**. The user requested completion of all pending files; this was not achieved, and no partial review is counted as complete. No runtime tests or code changes.

### Certified
- `product-forge/config/model-catalog.json`
- `product-forge/scripts/gen_model_registry.py`

### Targeted only — still pending
- `product-forge/core/customer_onboarding.py`
- `product-forge/core/marketing.py`
- `product-forge/core/mobile_tester.py`
- `product-forge/core/service_catalog.py`
- `product-forge/core/workflow_docs.py`
- `product-forge/scripts/pipeline.py`
- `product-forge/scripts/run_pipeline.py`
- `product-forge/core/product_plan.py`
- `product-forge/core/conversation_models.py`
- `product-forge/core/agent_memory.py`

### Findings

**PF-466 — P1 — [`scripts/gen_model_registry.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/gen_model_registry.py)**

- Evidence: Despite claiming mymoney/llm-catalog.ts as its source of truth, the generator never reads that file: it embeds approximately 195 hard-coded model tuples, including prices, capabilities and subjective quality scores.
- Remediation: Generate from a validated versioned catalog with provider provenance and freshness timestamps; treat subjective scores as estimates and do not publish static prices as current.
- Validation: static source/structured data review only; no runtime reproduction.

**PF-467 — P1 — [`scripts/gen_model_registry.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/gen_model_registry.py)**

- Evidence: Generator writes to relative products/.pipeline/model_registry.json without creating its parent directory; invocation from another working directory writes elsewhere or fails, and existing registry is overwritten non-atomically.
- Remediation: Resolve repository root from __file__/core.paths; create directory, write a unique temporary file, fsync and atomically replace under a lock.
- Validation: static source/structured data review only; no runtime reproduction.

**PF-468 — P2 — [`config/model-catalog.json`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/config/model-catalog.json)**

- Evidence: The 632-entry catalog contains 522 openrouter and 53 zen entries but sources metadata declares openrouter_count=458 and zen_count=43. It also has 57 registry-only entries. These stale source counts undermine refresh/provenance reporting.
- Remediation: Recompute source counts from the persisted model map during every refresh and validate them in CI.
- Validation: static source/structured data review only; no runtime reproduction.

**PF-469 — P1 — [`config/model-catalog.json`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/config/model-catalog.json)**

- Evidence: 110/632 catalog records lack a complete pricing pair, and the same 110 lack complete tools/reasoning capability metadata; downstream cheapest-model and capability routing must not interpret unknown as free or supported. Unknown-capability issue previously noted as PF-179; this finding adds the missing-price inventory and combined routing invariant.
- Remediation: Require complete pricing before cost ranking and explicit supported capability before hard-capability assignment; expose unknown separately from zero-cost/unsupported.
- Validation: static source/structured data review only; no runtime reproduction.

### Remaining work

30 large pending files require complete sequential source inspection, especially pipeline_executor and its four legacy backups, orchestrator agent execution/runner/LLM/stage runner, backlog, code executor, memory, and large CLI scripts. Preserve the 394-file frozen scope. Separate historical backup review from active runtime risks.


## Batch BK — pipeline entry, legacy conversation store and report integrity (2026-09-28)

**Disposition:** 12 pending files examined; **3 complete** full source static reviews, **9 targeted** source scans. Cumulative **367/394**, **27 pending**. No runtime tests or repository modifications.

### Fully reviewed
- `product-forge/scripts/run_pipeline.py`
- `product-forge/core/conversation_models.py`
- `product-forge/core/orchestrator/reporting.py`

### Targeted only — not certified
- `product-forge/core/customer_onboarding.py`
- `product-forge/core/marketing.py`
- `product-forge/core/mobile_tester.py`
- `product-forge/core/product_analyzer.py`
- `product-forge/core/product_plan.py`
- `product-forge/core/service_catalog.py`
- `product-forge/core/workflow_docs.py`
- `product-forge/scripts/pipeline.py`
- `product-forge/core/agent_memory.py`

### Findings (7)

**PF-470 — P1 — [`scripts/run_pipeline.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/scripts/run_pipeline.py)**

- Evidence: Capacity preflight only prints WARNING when can_start returns ok=False; it then proceeds to run_entry.begin_run. This CLI does not make the capacity check a hard gate.
- Remediation: Enforce capacity in the authoritative atomic run admission path, and test simultaneous starts and exhausted slots.
- Validation: pinned-commit static source review; no runtime reproduction.

**PF-471 — P1 — [`scripts/run_pipeline.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/scripts/run_pipeline.py)**

- Evidence: The CLI concatenates unvalidated project argument into products_dir and calls os.makedirs before run_entry; absolute and traversal project names can create paths outside the intended product root before downstream validation.
- Remediation: Validate project identifiers and resolve/contain paths before any filesystem side effect; reject absolute and traversal names.
- Validation: pinned-commit static source review; no runtime reproduction.

**PF-472 — P1 — [`core/conversation_models.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/core/conversation_models.py)**

- Evidence: Deprecated ConversationStore._save rewrites shared JSON files directly without lock or atomic replace. Concurrent intake and updates can lose records or leave truncated JSON on failure.
- Remediation: Use a transaction-capable tenant-scoped store or per-file locks plus unique-temp atomic replacement and corruption alerts.
- Validation: pinned-commit static source review; no runtime reproduction.

**PF-473 — P1 — [`core/conversation_models.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/core/conversation_models.py)**

- Evidence: Deprecated chunk buffer constructs .chunks_<conv_id> without validating conv_id; store_chunk accepts arbitrary chunk_index and total_chunks; combine_chunks treats missing indexed chunks as empty strings when received file count matches total.
- Remediation: Validate UUID/slug, path containment and bounded contiguous indexes; verify checksums and require every chunk before assembling.
- Validation: pinned-commit static source review; no runtime reproduction.

**PF-474 — P1 — [`core/orchestrator/reporting.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/core/orchestrator/reporting.py)**

- Evidence: generate_final_report references datetime.fromisoformat without importing datetime; the broad surrounding exception swallows NameError, leaving derived timing data absent or zero.
- Remediation: Import datetime explicitly and add report regression tests with stage executions and known durations.
- Validation: pinned-commit static source review; no runtime reproduction.

**PF-475 — P1 — [`core/orchestrator/reporting.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/core/orchestrator/reporting.py)**

- Evidence: print_summary counts rejected agents as completed in its displayed completion rate; generated JSON instead reports compliance_passed, so console completion and report compliance are different measures under the same Compliance Summary label.
- Remediation: Separate accepted, rejected, skipped, completed and compliance-passed counts, and derive consistent metrics from one typed result schema.
- Validation: pinned-commit static source review; no runtime reproduction.

**PF-476 — P2 — [`core/orchestrator/reporting.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/core/orchestrator/reporting.py)**

- Evidence: QA manifest is built only inside print_summary; generate_final_report writes both JSON files before any QA manifest integration. The attempted report["qa"] in print_summary catches NameError, so final JSON lacks this QA section.
- Remediation: Build QA manifest during report generation, include it before atomic persistence, and verify JSON/console parity.
- Validation: pinned-commit static source review; no runtime reproduction.

### Priority and remaining work

Prioritize active pipeline run admission, path containment and final-report correctness. The conversation store is explicitly deprecated; determine if any live callers remain before treating its weaknesses as active production exposure. Remaining 27 files are predominantly large orchestration, memory, backlog, code-execution and historical pipeline backups. Do not certify them from a structural scan.


## Batch BL — intake routing, legacy orchestration and wiring audit (2026-09-28)

**Disposition:** 18 pending files examined; **3 complete** full source static reviews, **15 targeted** structural scans. Cumulative **370/394**, **24 pending**. No runtime tests or repository modifications.

### Fully reviewed
- `product-forge/core/global_orchestrator.py`
- `product-forge/core/intent_router.py`
- `product-forge/scripts/dev/wired_audit.py`

### Targeted only — not certified
- `product-forge/core/customer_onboarding.py`
- `product-forge/core/marketing.py`
- `product-forge/core/mobile_tester.py`
- `product-forge/core/product_plan.py`
- `product-forge/core/service_catalog.py`
- `product-forge/core/workflow_docs.py`
- `product-forge/scripts/pipeline.py`
- `product-forge/core/product_analyzer.py`
- `product-forge/core/model_registry.py`
- `product-forge/core/agent_memory.py`
- `product-forge/core/compliance_check.py`
- `product-forge/core/orchestrator/agent_execution.py`
- `product-forge/core/orchestrator/agent_runner.py`
- `product-forge/core/orchestrator/llm_client.py`
- `product-forge/core/orchestrator/stage_runner.py`

### Findings (5)

**PF-477 — P1 — [`core/intent_router.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/intent_router.py)**

- Evidence: The live new_project, new_project_quick, modify_project, add_context and apply_change_package routes join unvalidated conversation project identifiers directly beneath products_dir. Absolute paths and ../ segments can escape the product root; creation and context writes then operate at that path.
- Remediation: Validate a strict project slug at intake and resolve/contain all project paths before existence checks, mkdir or writes; test absolute/traversal identifiers.
- Validation: pinned-commit static source review; no runtime reproduction.

**PF-478 — P1 — [`core/intent_router.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/intent_router.py)**

- Evidence: _route_new_project sets conversation status BUILDING before _start_pipeline; even when pipeline definition is missing or startup returns error, response says Project created. Pipeline started. _route_new_project_quick also sets BUILDING despite only scaffolding a prototype.
- Remediation: Only set BUILDING after confirmed run admission; return startup error explicitly and use a separate PROTOTYPE_READY status for quick scaffolds.
- Validation: pinned-commit static source review; no runtime reproduction.

**PF-479 — P1 — [`scripts/dev/wired_audit.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/dev/wired_audit.py)**

- Evidence: store_audit returns success (0) when the authoritative store-registry cannot be read; diff_audit also returns success on missing/invalid manifest, failed manifest writes and failed registry reads. A broken governance input therefore turns mandatory contract checks green.
- Remediation: Fail closed for required governance inputs, preserve a separate explicit bootstrap mode, and test unreadable/corrupt registry and manifest.
- Validation: pinned-commit static source review; no runtime reproduction.

**PF-480 — P2 — [`scripts/dev/wired_audit.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/dev/wired_audit.py)**

- Evidence: main classifies import reachability using plain substring matches, including comments and string literals; this can mark modules RUNTIME or ASSISTED without actual import edges. invocation_audit adds another check but does not make the displayed classification a real dependency graph.
- Remediation: Build Python AST import edges and resolve call paths; label textual references separately from proven invocation.
- Validation: pinned-commit static source review; no runtime reproduction.

**PF-481 — P2 — [`core/global_orchestrator.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/global_orchestrator.py)**

- Evidence: Deprecated GlobalOrchestrator.health_check only flags running projects with expired locks if get_lock_info returns a lock, but get_lock_info removes expired locks and returns None; a running project with a missing/expired lock can therefore be reported healthy.
- Remediation: If legacy orchestrator is retained, flag any RUNNING project lacking a valid owned lock and add missing/expired-lock regression tests; otherwise archive it and remove callable entry points.
- Validation: pinned-commit static source review; no runtime reproduction.

### Priority and remaining work

Prioritize live intake path containment and accurate pipeline-admission status; make governance checks fail closed. GlobalOrchestrator is explicitly deprecated and its issue is a legacy exposure only unless callers still invoke it. The remaining 24 files are mostly large source files, including active pipeline execution and historical backups; do not certify from structural scans.


## Batch BM — documentation integrity and model registry audit (2026-09-28)

**Disposition:** 2 previously pending files examined and fully source-reviewed. Cumulative **372/394**, **22 pending**. No runtime tests or repository changes.

### Fully reviewed
- `product-forge/scripts/dev/gen_docs_index.py`
- `product-forge/core/model_registry.py`

### Findings (4)

**PF-482 — P1 — [`scripts/dev/gen_docs_index.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/dev/gen_docs_index.py)**

- Evidence: TOP, HIST, FOLDER and TRUTH assign static percentages and implemented labels; scan reads file presence and first lines but never checks corresponding code implementations. Generated documentation therefore presents curated or guessed adoption as verified 100% implementation.
- Remediation: Separate manually curated adoption estimates from code-verified coverage; compute verified status from linked tests, artifacts and traceability evidence, and label unverifiable values as estimates.
- Validation: pinned-commit full static source review; no runtime reproduction.

**PF-483 — P1 — [`core/model_registry.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/model_registry.py)**

- Evidence: _load catches JSON corruption and I/O errors, calls _initialize, and returns DEFAULT_MODELS. A transient read error or malformed saved registry can overwrite persisted model enable/disable decisions and custom model entries without an operator alert.
- Remediation: Fail closed on registry corruption; preserve the damaged file and last-known-good backup; require explicit recovery before restoring defaults.
- Validation: pinned-commit full static source review; no runtime reproduction.

**PF-484 — P1 — [`core/model_registry.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/model_registry.py)**

- Evidence: _save writes the entire registry directly to model_registry.json with no temp-file atomic replacement or interprocess lock. Concurrent updates and interrupted writes can lose model changes or corrupt the registry; subsequent _load may then reset it to defaults.
- Remediation: Use locked read-modify-write and fsync/atomic replace with version or ETag conflict detection; test concurrent model disable/add and crash recovery.
- Validation: pinned-commit full static source review; no runtime reproduction.

**PF-485 — P2 — [`core/model_registry.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/model_registry.py)**

- Evidence: find_best_model checks max_cost only against input-token price, not output-token price or an estimated input/output token budget; select_with_fallback also returns a fallback chain model without reapplying requested tier or cost constraints.
- Remediation: Evaluate total estimated request cost and apply all hard tier/capability/cost constraints to every fallback; return an explicit no-feasible-model result when none qualifies.
- Validation: pinned-commit full static source review; no runtime reproduction.

### Existing related finding

PF-174 already documents that gen_docs_index.py --check returns success even with unclassified docs; it is not counted again.

### Remaining scope

22 pending files: large active execution/orchestration modules, backlog and memory, product services, historical pipeline backups, and scripts/pipeline.py. Prioritize active run admission, code execution, durable state, and access controls.


## Batch BN — service catalog and remaining large-module triage

Pinned commit: `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`. Exactly **9 pending paths examined**, **1 newly full-reviewed** (`core/service_catalog.py`), **8 targeted/partial** (`core/customer_onboarding.py`, `core/marketing.py`, `core/product_plan.py`, `core/workflow_docs.py`, `scripts/pipeline.py`, `core/mobile_tester.py`, `core/product_analyzer.py`, `core/agent_memory.py`). No runtime execution. **373/394** complete; **21 pending**. The eight targeted paths remain uncertified.

### New findings

**PF-486 — P1 — [`core/service_catalog.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/service_catalog.py)**

- Evidence: `parse_service_selection` returns `category.get_recommended()` for any unrecognized input rather than rejecting it or requesting confirmation. An invalid choice silently selects a deployment technology, including required database/API services.
- Remediation: Reject unknown inputs, present valid options, and require explicit confirmation for defaults; test typo, malformed custom and out-of-range numeric inputs.
- Validation: complete pinned-commit static source review; no runtime reproduction.

**PF-487 — P1 — [`core/service_catalog.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/service_catalog.py)**

- Evidence: the prompt advertises `custom <key>:<port>`, while the parser expects the numeric port *before* the colon (`custom 8080:technology`); the documented syntax cannot be parsed and silently falls back to the recommended service.
- Remediation: Make documented and accepted formats identical, validate the 1–65535 port range and the service key, and fail visibly on malformed custom selections.
- Validation: complete pinned-commit static source review; no runtime reproduction.

**PF-488 — P1 — [`core/service_catalog.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/service_catalog.py)**

- Evidence: multiple generated service configurations default to fixed credential placeholders (`change-me`, `change-me-in-production`, `minioadmin`) and `ConfigItem` does not enforce replacement before deployment; the Redis password is even marked `secret=False`, so its value can be shown in prompts. The catalog also includes Elasticsearch with security disabled by default.
- Remediation: Make production deployment refuse placeholder credentials and insecure defaults, require secret-manager input, and mark every password/token secret; test redaction and secure provisioning.
- Validation: complete pinned-commit static source review; actual generator/deployment enforcement must be checked separately.

### Targeted observations, not additional findings or full certifications

- `customer_onboarding.py` and `marketing.py` generate large static document packages from templates; examine product-data validation and claim verification before using outputs externally.
- `product_plan.py` includes mutable deserialization (`from_dict` pops fields), and non-atomic markdown replacement; inspect callers and persistence fully before assigning separate findings.
- `workflow_docs.py` generates a static 17+-agent pipeline narrative and HTML; reconcile against active DAG and escaping.
- `scripts/pipeline.py` is ~79 KB; legacy imports and CLI handlers need complete review.
- `mobile_tester.py`, `product_analyzer.py`, `agent_memory.py` are substantial modules and remain partial.

### Next

21 pending paths. Prioritize active execution/orchestration, backlog, code executor, memory, and the four historical pipeline backups. Do not count partial source inspections as full reviews.


## Batch BO — mobile test integrity and product-plan mutation

Pinned commit: `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`. **6 pending paths examined**, **2 newly complete static source reviews** (`core/mobile_tester.py`, `core/product_plan.py`), **4 targeted/partial** (`core/customer_onboarding.py`, `core/marketing.py`, `core/workflow_docs.py`, `core/product_analyzer.py`). No runtime execution. **375/394** complete; **19 pending**.

### New findings

**PF-489 — P1 — [`core/mobile_tester.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/mobile_tester.py)**

- Evidence: `_run_vitest_mobile`, `_run_stowaway`, and `_run_maestro` calculate test totals by counting `✓` and `✗` in stdout but do not check the actual test command's `returncode`. Nonzero exits with zero or misleading symbols can be reported without an error. `test_dir` is ignored by Vitest and Stowaway.
- Remediation: require successful process exit and structured runner reports (JUnit/JSON), distinguish zero tests from success, honor `test_dir`, and regression-test nonzero exits and unusual stdout.

**PF-490 — P1 — [`core/product_plan.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/product_plan.py)**

- Evidence: `Feature.from_dict` pops implementation/testing/security/quality and `Module.from_dict` pops features. `get_module`, `get_modules`, `update_module_status`, and `get_features_for_requirement` pass live dictionaries rather than defensive copies. Read calls therefore remove nested data from `self.plan` and later persistence can lose it.
- Remediation: make `from_dict` pure by copying input; test repeated reads, queries followed by `save`, and nested field retention.

**PF-491 — P1 — [`core/mobile_tester.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/mobile_tester.py)**

- Evidence: `save_result` stores a run under a fixed platform/framework/phase filename, while `_update_test_cycle` increments cumulative counters each time it is called. Rerunning the same phase overwrites the detailed file but adds counts again to the cycle, yielding inconsistent totals. Writes are non-atomic and unlocked.
- Remediation: persist immutable run IDs and derive aggregates from run records; use atomic writes and concurrency control.

**PF-492 — P1 — [`core/product_plan.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/product_plan.py)**

- Evidence: `save` deletes the existing `product-plan.json` before renaming a temporary file. A failure between deletion and rename can leave the canonical plan absent; there is no writer lock. `save_markdown` repeats the delete-before-rename pattern.
- Remediation: use atomic `os.replace` on the same filesystem, a per-project lock, and crash/concurrency tests.

**PF-493 — P2 — [`core/product_plan.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/product_plan.py)**

- Evidence: `get_project_health` reports `healthy` whenever there are zero blocked features, even when features have failing tests, unresolved security issues, or rejected reviews; the same module already computes `needs_rework` but does not use it in health classification.
- Remediation: derive health from blocked and rework counts plus explicit test/security/review gates; test a no-blocked-but-failing scenario.

### Targeted inspections (not certified)

`core/customer_onboarding.py` (1,228 lines), `core/marketing.py` (1,695 lines), `core/workflow_docs.py` (1,300 lines), and deprecated `core/product_analyzer.py` (1,193 lines) were fetched and their top-level contracts examined, but their full source paths were not exhaustively reviewed in this batch. No additional finding or certification is claimed for them.

### Remaining scope

19 pending: 18 core files and one script, including the large active orchestration/agent runner, backlog, code executor, compliance checker, memory, and historical pipeline backup files. This remains static review only; no runtime tests or code fixes were performed.


## Batch BP — agent memory persistence and knowledge compilation

Pinned commit: `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`. **4 pending paths examined**, **1 newly complete static source review** (`core/agent_memory.py`, lines 1–1058), **3 targeted/partial** (`core/orchestrator/agent_runner.py`, `core/backlog.py`, `core/workflow_docs.py`). No runtime execution. **376/394** complete; **18 pending**.

### New findings

**PF-494 — P1 — [`core/agent_memory.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/agent_memory.py#L204-L260)**

- Evidence: `project` is concatenated into `memory_dir` without validation or containment, and optional `entry_id` is interpolated directly into a JSON filename. A caller supplying traversal components in project or entry_id can target files outside the intended project memory directory; `_save_entry` then opens the computed path for writing. `import_entries` also accepts caller-provided entry IDs. Actual exposure depends on upstream trust boundaries.
- Remediation: validate project slugs, generate immutable server-side memory IDs, and resolve/check all paths against the authorized project memory root. Add traversal and cross-tenant regression tests.

**PF-495 — P2 — [`core/agent_memory.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/agent_memory.py#L624-L728)**

- Evidence: `compile_knowledge` maintains a global `seen_ids` across *all* tag groups, marking entries seen even when the current group has fewer than `min_entries`. An entry shared across tags is omitted from later tag compilations; groups may disappear or produce incomplete evidence summaries. The compilation also does not require validated source entries.
- Remediation: deduplicate independently within each tag group, preserve source provenance, and provide an explicit validated-only mode or require validation for trusted compilations. Test overlapping tag groups and unvalidated memories.

**PF-496 — P2 — [`core/agent_memory.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/agent_memory.py#L387-L405)**

- Evidence: `get(entry_id)` returns expired entries without checking `is_expired`; `get_validated`, `search_by_tag`, and `get_by_source` likewise return expired records. Only `retrieve` defaults to filtering expiry. Callers can therefore consume stale memory unless they remember to check TTL.
- Remediation: centralize expiry checks in all read APIs with explicit opt-in for historical access; test expired policy and working-memory entries across retrieval methods.

### Existing finding reconfirmed

PF-081 already covers non-atomic live JSON writes and false success when memory validation persistence fails; it is **not** counted again. Additional failure propagation gaps affect update, delete, and expiry purge, and should be addressed under the same persistence fix.

### Targeted inspections, not certified

- `core/orchestrator/agent_runner.py` lines 1–120: prompt/artifact and dynamic tool-policy integration inspected; complete source review remains pending.
- `core/backlog.py` lines 1–120: project-scope path construction and persistence entry points inspected; complete source review remains pending.
- `core/workflow_docs.py` lines 1100–1200: generated Draw.io XML interpolates workflow strings directly, and the generator writes dashboard HTML/diagrams; full escaping and caller analysis remain pending.

### Remaining scope

**18 pending files**. Prioritize active orchestration, backlog, code execution and pipeline CLI. Historical `.bak_pre_*` pipeline copies are lower-priority archival reviews. Static analysis only; no code changes or runtime tests.


## Batch BQ — larger 18-file sweep of remaining active execution and product support modules

Pinned commit: `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`. **18 distinct pending paths examined**: **3 complete static source reviews**, **15 targeted/structural inspections**. Cumulative **379/394 certified; 15 pending**. No runtime tests or code changes.

### Newly completed full static reviews
- [`core/code_executor.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/code_executor.py)
- [`core/orchestrator/agent_execution.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/orchestrator/agent_execution.py)
- [`core/traceability.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/traceability.py)

### New findings

**PF-497 — P1 — [`core/code_executor.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/code_executor.py#L244-L269)**
- Evidence: run_tests returns (True, "pytest not found - skipping tests") on FileNotFoundError. execute_plan treats that as tests_passed and can report a successful code change with no tests executed.
- Remediation: Fail closed when the runner is unavailable; record executed test count and require nonzero verified tests.

**PF-498 — P1 — [`core/code_executor.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/code_executor.py#L128-L200)**
- Evidence: backup_file and apply_changes join caller-provided file_path directly under repository root without canonical path containment; selected plan paths can traverse outside the repo if the caller is not trusted.
- Remediation: Validate and resolve paths inside a strict allowed workspace, reject symlinks and traversal, and enforce approval provenance.

**PF-499 — P1 — [`core/code_executor.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/code_executor.py#L172-L206)**
- Evidence: modify branch uses line_start/line_end to replace a slice but never checks whether change.old_code actually matches the target; stale line numbers can silently overwrite unrelated source.
- Remediation: Check exact expected old content or a content hash before mutation, and reject stale edits.

**PF-500 — P1 — [`core/orchestrator/agent_execution.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/orchestrator/agent_execution.py#L360-L397)**
- Evidence: compliance blocking_action == approve only prints a message; execution proceeds to subsequent checks and final completion without requiring that approval in this branch. A separate HIL may run, but it does not prove this compliance-specific approval was satisfied.
- Remediation: Convert compliance approval action into a mandatory explicit gate with linked decision evidence.

**PF-501 — P2 — [`core/orchestrator/agent_execution.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/orchestrator/agent_execution.py#L287-L347)**
- Evidence: Agent audit entry is written while execution.status is still running and completed_at has not been set, producing a zero/near-zero duration and a running status for a subsequently completed, rejected or failed agent. Circuit breaker success is also recorded before the HIL decision.
- Remediation: Emit a final audit record after terminal decision and record success only after all blocking gates.

**PF-502 — P1 — [`core/traceability.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/traceability.py#L507-L560)**
- Evidence: A requirement is counted as secured whenever security_issues is empty, even if no security review was performed. fully_covered similarly requires only the absence of recorded issues, not verified review evidence.
- Remediation: Track explicit security review status/evidence and distinguish not reviewed from reviewed clean.

**PF-503 — P2 — [`core/traceability.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/traceability.py#L565-L604)**
- Evidence: get_coverage_by_module uses the number of feature IDs as denominator but increments counts per matching requirement entry, so modules with many requirements per feature can exceed 100% coverage.
- Remediation: Aggregate by unique feature ID or use matching requirement count as denominator consistently.

**PF-504 — P2 — [`core/traceability.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/traceability.py#L752-L785)**
- Evidence: Markdown report labels Fully Covered count but prints coverage[implemented] rather than the actual fully_covered count; coverage metrics do not store fully_covered as an absolute count.
- Remediation: Store fully_covered count and use it in generated reports; test mixed coverage cases.

**PF-505 — P1 — [`scripts/pipeline.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/pipeline.py#L1344-L1380)**
- Evidence: CLI mark_stage_complete directly sets completed and potentially pipeline_complete without checking evidence, approvals, tests or gates. Exposure depends on CLI access and caller permissions.
- Remediation: Require gate evidence and authorization, or explicitly mark this as a privileged administrative override with audit trail.

**PF-506 — P2 — [`core/product_analyzer.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/product_analyzer.py#L503-L562)**
- Evidence: Estimated test coverage is computed as test-file count divided by Python source-file count; quality labels based on that ratio can present high coverage without running any tests or measuring executed lines.
- Remediation: Label file-count ratio as a heuristic and require measured coverage artifacts for release decisions.

**PF-507 — P1 — [`core/customer_onboarding.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/customer_onboarding.py#L13-L94)**
- Evidence: generate_onboarding_package joins unvalidated product_name under products_dir and writes eleven output files; traversal or absolute names can direct output outside the intended product folder when exposed to untrusted inputs. marketing.py uses the same path construction.
- Remediation: Validate product IDs and enforce canonical path containment at every output writer.

### Existing findings reconfirmed
PF-005 already covers lossy flattened backup paths and broken rollback in code_executor; PF-035 already covers fail-open readiness exceptions in agent_execution. These were not assigned duplicate new IDs.

### Targeted inspection only — not certified
- `core/backlog.py`
- `core/compliance_check.py`
- `core/customer_onboarding.py`
- `core/marketing.py`
- `core/orchestrator/agent_runner.py`
- `core/orchestrator/llm_client.py`
- `core/orchestrator/stage_runner.py`
- `core/pipeline_executor.py`
- `core/pipeline_executor.py.bak_pre_agent_exec`
- `core/pipeline_executor.py.bak_pre_agent_runner`
- `core/pipeline_executor.py.bak_pre_llm_extract`
- `core/pipeline_executor.py.bak_pre_stage_runner`
- `core/product_analyzer.py`
- `core/workflow_docs.py`
- `scripts/pipeline.py`

Targeted inspections covered source retrieval, structural/method maps, risk-pattern screening and selected relevant source spans. Large active modules and historical `.bak_pre_*` snapshots were not counted as complete manual source reviews. Full sequential review is still required.

### Next batch
15 remaining: 10 active core files, 4 historical pipeline-executor backup snapshots and 1 pipeline CLI script. Prioritize active pipeline executor and orchestration runner/LLM/stage runner; archive backups separately.


## Batch BR — onboarding complete and active governance targeted review

Pinned commit `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`. **4 pending files examined; 1 complete source review; 3 targeted source reviews. Cumulative 380/394; 14 pending.** No runtime tests or repository edits.

### Fully certified
- [`core/customer_onboarding.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/customer_onboarding.py) — 1,228-line source reviewed including generation of all 11 onboarding documents, data inputs, claims, write paths and errors.

### New findings

**PF-508 — P1 — [`core/customer_onboarding.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/customer_onboarding.py#L588-L715)**
- Evidence: Generated FAQ unconditionally claims SOC 2 Type II certification, 100+ integrations, a 14-day trial with full feature access, a 30-day refund guarantee and other product-specific commercial/privacy assertions without checking product_data or verified evidence.
- Remediation: Use approved, versioned claims registry with evidence; omit unsupported claims and require legal/security approval before publishing.

**PF-509 — P1 — [`core/customer_onboarding.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/customer_onboarding.py#L201-L280)**
- Evidence: Installation guide ignores the retrieved tech_stack and prints pip install, Docker image and CLI commands synthesized from product name; those commands may not exist and are presented as operational instructions.
- Remediation: Generate only from verified package/build/deployment manifests and validate executable installation commands in release CI.

**PF-510 — P2 — [`core/customer_onboarding.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/customer_onboarding.py#L437-L588)**
- Evidence: Manual appends non-f-string literal text containing {name} and {api = product_data.get(...)} placeholders; these appear in generated customer documentation instead of being resolved.
- Remediation: Use explicit template rendering and a no-unresolved-placeholder quality gate.

**PF-511 — P1 — [`core/orchestrator/stage_runner.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/orchestrator/stage_runner.py#L174-L205)**
- Evidence: The sequential stage runner logs failed constitution rules R001–R005 but does not block stage execution at that decision point; whether another gate blocks later requires end-to-end verification.
- Remediation: Convert blocking constitution rules to terminal stage failures with recorded evidence and integration tests.

### Existing finding reconfirmed
PF-507 already records the unvalidated product-name path traversal in customer_onboarding; not duplicated.

### Targeted only — not certified
- `core/compliance_check.py`
- `core/orchestrator/llm_client.py`
- `core/orchestrator/stage_runner.py`

The three large modules were inspected at selected critical source ranges, not end-to-end. The complete-review total excludes them.

### Next batch
14 pending: prioritize active stage runner, agent runner, LLM client, compliance check, backlog, marketing, pipeline executor, product analyzer, workflow docs and CLI; four historical executor snapshots are lower-priority.


## Batch BS — marketing and stage execution full-source review

Pinned commit `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`. **3 pending paths examined; 2 complete source reviews; 1 targeted review. Cumulative 382/394; 12 pending.** No runtime tests or repository edits.

### Fully certified
- [`core/marketing.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/marketing.py) — 1,695 lines reviewed, including all eight document generators, templating, data inputs and write paths.
- [`core/orchestrator/stage_runner.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/orchestrator/stage_runner.py) — 780 lines reviewed, including parallel execution, agent retries, budget/stop checks, stage status, lifecycle events, QA gate and VCS release.

### New findings

**PF-512 — P1 — [`core/orchestrator/stage_runner.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/orchestrator/stage_runner.py#L570-L601)**
- Evidence: all_passed tests only agent execution status; the DAG stage is marked completed even when compliance_passed is false, explicitly reported as compliance warnings. An empty stage_executions list also makes all_passed vacuously true.
- Remediation: Require at least one expected agent execution and enforce mandatory compliance severity before marking a stage complete; test empty, skipped, failed and noncompliant agent scenarios.

**PF-513 — P1 — [`core/orchestrator/stage_runner.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/orchestrator/stage_runner.py#L742-L764)**
- Evidence: For stage 10a, QA NO-GO without override marks the stage failed, but _vcs_release() is invoked unconditionally in the next try block. This could still perform a release action after the block decision.
- Remediation: Return immediately on NO-GO and enforce the same gate inside _vcs_release; integration-test blocked releases.

**PF-514 — P1 — [`core/marketing.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/marketing.py#L16-L25)**
- Evidence: generate_marketing_package joins caller-controlled product_name directly under products_dir and creates output_dir without validating project identity or canonical path containment.
- Remediation: Validate product identifiers and ensure the resolved output path remains within the authorized products root.

**PF-515 — P2 — [`core/marketing.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/marketing.py#L85-L170)**
- Evidence: The generated GTM, positioning, campaign and partner templates contain unsupported default product claims, placeholder price/ROI targets, assumed partner commissions and generic timelines; output is written as a complete marketing package without an evidence/completeness gate.
- Remediation: Classify these outputs as drafts; require approved product facts, commercial assumptions and placeholder validation before publication.

### Existing finding reconfirmed
PF-511: constitution-rule failures are logged rather than blocking at the stage runner decision point.

### Targeted inspection — not certified
- `core/compliance_check.py`: reviewed derived checklist, output-artifact lookup and selected QA/review checklist contracts. Full 1,445-line source review remains pending.

### Next batch
12 pending: seven active core modules, four historical pipeline-executor backup snapshots and one pipeline CLI script. Prioritize compliance_check, llm_client, agent_runner, backlog, pipeline_executor, product_analyzer, workflow_docs and CLI; treat historical backups as archival.


## Batch BT — LLM client and deprecated product analyzer full-source review

Pinned commit `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`. **2 pending files examined; 2 complete source reviews; 0 targeted. Cumulative 384/394; 10 pending.** No runtime tests or repository edits.

### Fully certified
- [`core/orchestrator/llm_client.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/orchestrator/llm_client.py) — 844-line source, provider resolution, request/response, retries, continuation, chunked map-reduce, caching, token ledger, native tools and fallback.
- [`core/product_analyzer.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/product_analyzer.py) — 1,193-line DEPRECATED analyzer, source structure, quality, heuristic test coverage, security, work-plan and report outputs.

### New findings

**PF-516 — P1 — [`core/orchestrator/llm_client.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/orchestrator/llm_client.py#L616-L675)**
- Evidence: Map-reduce chunking appends successful digests but silently skips failed chunk calls; a reduce result may be returned as a complete artifact despite missing context chunks.
- Remediation: Fail the artifact if any required chunk fails; retain chunk-level evidence and retry missing chunks before reduction.

**PF-517 — P1 — [`core/orchestrator/llm_client.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/orchestrator/llm_client.py#L399-L457)**
- Evidence: When continuation hits a token ceiling, deadline or continuation limit, partial all_content is returned with truncated metadata; callers may treat nonempty partial text as successful generation.
- Remediation: Treat finish_reason=length and interrupted continuations as incomplete; require explicit artifact completeness validation before accepting.

**PF-518 — P2 — [`core/orchestrator/llm_client.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/orchestrator/llm_client.py#L94-L117)**
- Evidence: Pinning a model not equal to the primary inserts it with the primary provider and endpoint rather than the pinned model’s actual provider configuration.
- Remediation: Resolve pinned model through the model registry/provider mapping and reject incompatible endpoints.

**PF-519 — P1 — [`core/product_analyzer.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/product_analyzer.py#L503-L559)**
- Evidence: Deprecated analyzer estimates coverage as count(test files)/count(Python source files), capped at 100%; labels this as test coverage and feeds it to readiness scoring, without executing or measuring tests.
- Remediation: Use actual coverage reports or label the count as test-file density and exclude it from release readiness.

**PF-520 — P1 — [`core/product_analyzer.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/product_analyzer.py#L561-L647)**
- Evidence: Security scan checks only the first 20 code files, with narrow regexes and swallowed read failures; analyze_product sets pipeline_ready when overall_score >=70 and no findings, making an incomplete scan appear clean.
- Remediation: Record scan completeness, use supported SAST/secret scanners and fail readiness when security coverage is incomplete.

**PF-521 — P2 — [`core/product_analyzer.py`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/product_analyzer.py#L697-L789)**
- Evidence: Generated work plan always creates a validate item dependent on implement if tests are missing, but does not add an implement work item; unresolved dependency can prevent plan execution.
- Remediation: Validate work-plan DAG and either add the prerequisite task or remove unsupported dependencies.

### Limitations
Static source review only; no test execution, production exposure verification or repository edits. The deprecated analyzer is not the active generic pipeline.

### Next batch
10 pending: core/backlog.py, core/compliance_check.py, core/orchestrator/agent_runner.py, core/pipeline_executor.py, four historical pipeline_executor.py.bak_pre_* snapshots, core/workflow_docs.py and scripts/pipeline.py. Prioritize active critical modules; archive backup snapshots separately.


## Recovery reconciliation — archived Batch BT checkpoint

The archived Batch BT report and per-batch progress were recovered from the user’s Library and reconciled with the exact 394-path ledger. The regressed local ledger contained 291 fully reviewed paths at Batch AR. The archive lists 93 additional **unique** complete static reviews in batches AS–BT; no path overlaps the AR baseline. Reconciled total: **384/394 certified**, **10 pending**. This recovery does not constitute new source inspection or runtime testing.

Pending paths:
- `product-forge/core/backlog.py`
- `product-forge/core/compliance_check.py`
- `product-forge/core/orchestrator/agent_runner.py`
- `product-forge/core/pipeline_executor.py`
- `product-forge/core/pipeline_executor.py.bak_pre_agent_exec`
- `product-forge/core/pipeline_executor.py.bak_pre_agent_runner`
- `product-forge/core/pipeline_executor.py.bak_pre_llm_extract`
- `product-forge/core/pipeline_executor.py.bak_pre_stage_runner`
- `product-forge/core/workflow_docs.py`
- `product-forge/scripts/pipeline.py`



---

# Batch BU–BV continuation: current and next deep-review passes

**Evidence baseline:** `srinikc/productforge`, `develop` pinned to `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`. Source was retrieved through the connected GitHub repository at that exact commit. This section merges the prior BU targeted-review record with the current expanded semantic inspection of `core/backlog.py`, `core/compliance_check.py`, `core/orchestrator/agent_runner.py` and `core/pipeline_executor.py`. This is a **source-level review**; no code changes, integration tests, exploit reproduction, or deployment checks have been performed. Do not equate full-file retrieval with full line-by-line certification.

**Certification control:** the last fully reconciled, independently evidenced checkpoint remains **384/394 certified**, **10 pending full certification**. Four active files have expanded semantic coverage here; the four historical `.bak_pre_*` files, `core/workflow_docs.py` and `scripts/pipeline.py` still require complete certification. A prior targeted review of all ten does not close the ledger. Existing finding IDs PF-001–PF-521 are retained; candidate identifiers below are provisional and must not be counted as final unique PF findings until full-register deduplication.

## A. Expanded findings: current Batch BU (`backlog.py`, `compliance_check.py`)

| Candidate | Severity | Pinned source | Detailed causal path, consequence and fix |
|---|---|---|---|
| BU-C01 | P1 | [`backlog.py:78–86`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/backlog.py#L78-L86), [`:154–158`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/backlog.py#L154-L158) | `_dir` concatenates a caller-supplied `project` into a storage path, and `_save_item` interpolates `id` into a filename. Neither function enforces an approved project root or validates filename-safe IDs. **Conditional risk:** if untrusted callers reach these APIs, path traversal or writing outside the intended backlog is possible. Canonicalize paths and require `relative_to(allowed_root)`, validate project and item IDs at the API boundary; test `../` and separator-bearing inputs. |
| BU-C02 | P1 | [`backlog.py:127–165`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/backlog.py#L127-L165), [`:168–194`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/backlog.py#L168-L194) | Migration writes each item separately, then rewrites two derived indexes. `_load_all` uses the legacy arrays only when **no** per-item JSON exists. A partial migration can therefore suppress legacy-only items and rewrite indexes without them. Require migration staging/manifest, completeness checks against legacy IDs, atomic publish, and interrupted-migration recovery tests. |
| BU-C03 | P1 | [`backlog.py:632–654`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/backlog.py#L632-L654) | `pair()` reads both sides and calls `update()` twice under separate locks; no cross-scope transaction or rollback. The first side can persist if the second fails, while concurrent edits can be overwritten by the stale read. Require a deterministic two-scope lock order and transactional or reconciled reciprocal linking; inject second-write failure and concurrent pair operations. |
| BU-C04 | P2 | [`backlog.py:286–299`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/backlog.py#L286-L299), [`:817–843`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/backlog.py#L817-L843) | `_hist` silently ignores every journal append failure; `update` returns success after item/index writes even if the audit trail is missing. Make history persistence a mandatory transactional step where required, or expose a durable `audit_pending` reconciliation queue and error metrics. |
| BU-C05 | P1 | [`backlog.py:867–879`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/backlog.py#L867-L879) | `accept(...when='now')` first persists `queued`, then catches and suppresses portfolio `enqueue()` failure. Item state may advertise queued work absent from the actual execution queue. Use an outbox/transaction or explicit `queue_failed` state and retry. |
| BU-C06 | P1 | [`compliance_check.py:40–73`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/compliance_check.py#L40-L73), [`:258–315`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/compliance_check.py#L258-L315) | Derived checks search `artifacts/*/<agent>-output.md` and accept the first existing file, independent of the requested stage and current run. The same project may therefore pass a new agent check using stale output. Require stage/run-scoped artifact path and hash, reject stale artifacts, record provenance in each report. This reinforces PF-006/PF-031 rather than replacing them. |
| BU-C07 | P1 | [`compliance_check.py:180–218`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/compliance_check.py#L180-L218), [`:325–389`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/compliance_check.py#L325-L389) | Final `conformed` is `total_critical_failed == 0 and total_failed == 0`, without requiring any checks or excluding UNKNOWN/SKIPPED. Empty/latest-only aggregation can therefore produce `conformed=true` with zero verified evidence. Require nonempty mandatory executed checks, no unresolved critical unknowns and run-scoped report completeness. Distinct implementation from PF-039 (a different verifier). |
| BU-C08 | P2 | [`compliance_check.py:507–532`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/compliance_check.py#L507-L532) | `audit_log_updated` checks for the agent name anywhere in the last 50 lines, not the requested stage, run ID or timestamp. Old/unrelated log entries can satisfy a current compliance check. Match structured run-scoped audit events. |

**Previously registered, not new:** PF-025 (backlog lock timeout), PF-036 (test directory existence falsely reported as test pass), PF-031 (non-run-scoped latest compliance reports), PF-006 (stale close-loop evidence). `compliance_check.py:305–315` also writes report files directly rather than atomically, reinforcing report-integrity remediation.

## B. Expanded findings: next Batch BV (`agent_runner.py`, `pipeline_executor.py`)

| Candidate | Severity | Pinned source | Detailed causal path, consequence and fix |
|---|---|---|---|
| BV-C01 | P0 | [`pipeline_executor.py:1033–1051`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/pipeline_executor.py#L1033-L1051) | In `_wait_for_approval_ex`, the human-proxy branch obtains `d = decide(...)` but unconditionally returns `_ok` (`decision='approved'`), even if `d` reports rejection, changes or failure. This is a **direct approval-decision propagation bug**. Return a validated mapping of the proxy decision, fail closed on missing/unknown values, and test all decision enums. Closely related to PF-001 (proxy itself fails open), but this separate caller bug persists even if the proxy is fixed. |
| BV-C02 | P1 | [`agent_runner.py:1489–1523`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/orchestrator/agent_runner.py#L1489-L1523) | `execute_agent_tool` enforces `spec.tools` only if a spec exists. If `agent_specs` lacks the supplied `agent_id`, the function can execute a registry tool anyway. Whether this is remotely exploitable depends on caller exposure; as a defense-in-depth authorization bug, reject missing specs and require explicit tool allowlisting before cache lookup or execution. |
| BV-C03 | P1 | [`agent_runner.py:960–1024`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/orchestrator/agent_runner.py#L960-L1024) | Sectioned generation logs missing features/sections but still assembles and returns nonempty text. For per-feature agents it does not retry missing essential sections; truncation is tracked, but an empty section that is not reported as truncated can yield incomplete merged output. Require exact expected-feature and essential-section cardinality before publishing; return `needs_retry` with missing IDs and test empty middle sections. |
| BV-C04 | P1 | [`agent_runner.py:245–257`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/orchestrator/agent_runner.py#L245-L257), [`:479–489`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/orchestrator/agent_runner.py#L479-L489) | The output checklist's exception is swallowed and `_cache_output_ok` returns `True`. The input prompt can be cached despite an unavailable output quality check. Fail closed for applicable mandatory checklists and emit explicit check-error evidence. This is **input-prompt caching**, not output reuse or proof of release approval. |
| BV-C05 | P1 | [`agent_runner.py:430–453`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/orchestrator/agent_runner.py#L430-L453) | Canonical artifact is opened with `w` at its final path. A crash or disk-full failure can truncate the prior good artifact; the per-feature and extra-format writers are intentionally nonfatal. Use temporary-file + fsync + replace for the canonical output, and explicitly classify required versus optional secondary artifacts. |
| BV-C06 | P1 | [`pipeline_executor.py:2860–2874`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/pipeline_executor.py#L2860-L2874) | Run-lock guard checks only whether **a** lock exists, not whether the current process/run owns it; guard exceptions are logged and execution proceeds. A direct `execute_pipeline()` caller may execute under another run's lock or when lock verification fails. Require run-ID/fencing-token ownership verification and fail closed on guard errors; test foreign lock and lock-manager exception. |
| BV-C07 | P1 | [`pipeline_executor.py:3101–3124`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/pipeline_executor.py#L3101-L3124), [`:3174–3198`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/pipeline_executor.py#L3174-L3198) | In emergency conservation mode the loop breaks without explicitly setting FAILED; the finalizer normally detects pending stages, but if the scoped stages are already terminal it can still assign COMPLETION. Mark emergency stop as a distinct terminal failure/paused-budget state before finalization and persist budget evidence. |
| BV-C08 | P2 | [`pipeline_executor.py:3200–3203`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/pipeline_executor.py#L3200-L3203) | Decision log records `pipeline_complete` regardless of final `PipelinePhase.FAILED`, producing a misleading audit event. Emit `pipeline_failed`/`pipeline_completed` based on actual phase. |

**Previously registered, not new:** PF-001 (human-proxy fail-open defaults), PF-055 (limited repo gate scope), PF-060 (failed item quality-gate result ignored after COMPLETION), PF-067 (tool-loop retry counters overwritten), PF-069 (unknown selective-stage IDs can pass `all(empty)`), PF-512 (stage-level compliance completion inconsistency). Do not duplicate their IDs or count these reinforcements as newly discovered.

## C. Additional architectural and evidence observations

1. **Compliance evidence is not current-run bound.** `compliance_check.py` derives artifacts from arbitrary stage directories, `audit_log_updated` uses substring presence in a trailing log window, and final report aggregation reads `*-latest.json` rather than an immutable current-run manifest. A reliable release gate needs an evidence graph: run ID → stage → agent attempt → artifact hash → executed test/check → human decision.
2. **Approval semantics differ by mode.** Auto and semi modes intentionally bypass interactive approval; however, the human-proxy branch discards the proxy's actual decision (BV-C01), while noninteractive modes return `_ok` after recording a request. Define a single explicit policy and make the resulting decision visible in every report.
3. **Persistence is only partially atomic.** The pipeline checkpoint uses a temp file and `os.replace` (`pipeline_executor.py:687–731`), a positive safeguard. Canonical agent output and compliance latest reports do not. Backlog indexes are atomically replaced individually, but multi-file migration and reciprocal pairing lack transactionality.
4. **Completion and quality remain separate.** The executor finalizer checks DAG terminal status, but the repository quality gate is invoked afterward and its result is ignored (existing PF-060). Compliance's empty `conformed` and nonexecuting test check mean an apparently completed DAG cannot be treated as verified product readiness.

## D. Prior BU targeted findings incorporated, not silently certified

The earlier [Batch BU targeted review](Product_Forge_Batch_BU_Review.md) additionally identified `scripts/pipeline.py:1344–1378` manual completion without current-run gate evidence, `scripts/pipeline.py:687–810` legacy queue/lock fallback, and `workflow_docs.py` hardcoded workflow/documentation paths. These remain **targeted candidate findings** pending complete semantic review and permanent-register deduplication. Four `pipeline_executor.py.bak_pre_*` files were fetched but their exhaustive function-level historical comparison is still outstanding; they are archival snapshots, not evidence of active runtime behavior.

## E. Consolidated remediation order and regression acceptance

| Order | Workstream | Consolidated IDs/candidates | Minimum acceptance evidence |
|---|---|---|---|
| 1 | Approval and release fail-closed | PF-001, PF-060, BV-C01 | Proxy reject/changes/error must not approve; failing item gate must persist FAILED and return false; unauthorized override rejected. |
| 2 | Current-run evidence and compliance | PF-006, PF-031, PF-036, PF-039, BU-C06–C08 | Empty/skipped/unknown tests never yield `conformed`; stale stage/run artifact rejected; real test runner evidence includes command, exit code, duration, artifact hash. |
| 3 | Execution isolation and authorization | PF-025, BV-C02, BV-C06 | Foreign run lock blocks direct execution; absent agent spec cannot invoke tools; held backlog lock aborts mutation without duplicate IDs. |
| 4 | Artifact completeness and durability | BV-C03–C05, BU-C02–C04 | Missing per-feature section causes retry; simulated crash preserves prior canonical artifact; interrupted migration preserves all legacy items and audit history. |
| 5 | Backlog state/queue consistency | BU-C01, BU-C05 | Invalid paths rejected; enqueue failure cannot leave an unqueued item claiming successful scheduling. |
| 6 | Finish remaining full-file reviews | 10-file pending ledger | Inspect all control-flow branches and cross-module contracts; diff archival backups; reconcile candidates with PF-001–PF-521 before updating certification count. |

**Coverage and limitation:** This appendix is an expanded static semantic audit of the named high-risk paths, not a claim of exhaustive 10-file line-by-line review. The **authoritative fully certified count stays 384/394** until the remaining files meet the same evidence standard as the earlier batches. The current repository was not modified and runtime regression tests were not run.

---

# Batch BW–BX continuation — CLI, workflow documentation, archival executor comparison

**Evidence:** `srinikc/productforge` at immutable commit `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`; source retrieved through the GitHub connector. This appendix is merged into the preceding BT–BV audit, not a replacement for it. Static source inspection and historical comparison only; no runtime tests or code changes. Candidate IDs are provisional until full PF-001–PF-521 deduplication. The certification ledger remains **384/394** because retrieval and selected deep semantic passes do not equal exhaustive certification.

## 1. Batch BW — `scripts/pipeline.py` (2,179 lines)

The CLI is a mixture of canonical subsystem calls and legacy direct JSON mutation. The high-risk flows examined include project resolution, lock acquisition/release, circuit reset, queue management, resume inference, manual completion, exit, compliance reporting and command dispatch. Pinned references below point to the reviewed commit.

| Candidate | Severity | Source | Causal finding and remediation |
|---|---|---|---|
| BW-C01 | P1 | [`scripts/pipeline.py:1888–1894`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/pipeline.py#L1888-L1894) | `show_compliance()` returns exit code 0 for every `overall_status` other than exactly `fail` or `partial`, including `unknown`, missing and unrecognized values. This can turn failed/absent verification into CI success. Allowlist verified success only, map unknown/skipped/errors to nonzero, and test all status enums. |
| BW-C02 | P1 | [`scripts/pipeline.py:1344–1376`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/pipeline.py#L1344-L1376) | `mark_stage_complete()` directly mutates the derived `pipeline.json` projection without validating the stage's actual execution, approvals, current-run test evidence, or canonical checkpoint. `all([])` is true if the stages map is empty. This confirms and expands the previous targeted BU candidate; do not double-count. Route through an authorized checkpoint transition with mandatory evidence and disallow empty/unknown stage IDs. |
| BW-C03 | P1 | [`scripts/pipeline.py:687–742`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/pipeline.py#L687-L742), [`:768–810`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/pipeline.py#L768-L810) | Legacy fallback reads and writes lock/queue JSON without atomic compare-and-set or exclusive lock; core queue errors fall back to an independent legacy queue, potentially splitting authoritative state. Remove mutable fallback in production; fail closed and migrate through one canonical queue/lock store. Previously targeted BU observation, expanded here. |
| BW-C04 | P1 | [`scripts/pipeline.py:1040–1092`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/pipeline.py#L1040-L1092), [`:1772–1796`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/pipeline.py#L1772-L1796) | `circuit_reset` can release a project lock without validating run ownership, and legacy fallback clears the JSON lock directly. `exit_pipeline` unlinks `.lock` directly rather than using `LockManager`, so a foreign run's lock could be removed if that file is authoritative. Require holder/run-ID fencing and a single lock API; test foreign-owner release. |
| BW-C05 | P2 | [`scripts/pipeline.py:1178–1325`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/pipeline.py#L1178-L1325) | `continue_pipeline()` infers the next stage by parsing a human-readable Markdown table, assuming numeric contiguous stages 0–9. It can report complete on a high stage number even when earlier DAG dependencies remain incomplete; importantly, this function prints guidance rather than actually resuming the executor. Replace status inference with the canonical DAG/checkpoint and label guidance-only behavior explicitly. |
| BW-C06 | P2 | [`scripts/pipeline.py:194–214`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/pipeline.py#L194-L214), [`:1344–1346`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/pipeline.py#L1344-L1346) | The legacy project resolver returns the raw argument; multiple CLI paths concatenate it under `PRODUCTS_DIR`. If an untrusted or malformed project name reaches the CLI, `../` can escape the expected project root. Canonicalize project names and resolve paths under an allowlisted products directory. Exposure is conditional on how the CLI is invoked. |

**Additional CLI observations:** `check_budget` treats missing budget files or missing project budgets as unlimited (`:745–765`), an intentional policy that should be explicit in deployment configuration. `mark-complete` parses an optional stage as `None` (`:2152–2157`) and still calls the mutation function. `show_compliance` displays a saved-report location even when the returned structure does not independently establish a durable report. No command was executed in this audit.

## 2. Batch BX — `core/workflow_docs.py` (1,300 lines)

The module constructs static workflow data, HTML and Draw.io XML and writes generated files to `dashboard/docs`. The inspected source includes all top-level methods, pipeline definition, pipeline HTML/XML generation, agent diagram XML, save routine and index generation entry point. The workflow definition is descriptive and should not be mistaken for the actual configured DAG.

| Candidate | Severity | Source | Causal finding and remediation |
|---|---|---|---|
| BX-C01 | P2 | [`workflow_docs.py:44–55`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/workflow_docs.py#L44-L55), [`:565–567`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/workflow_docs.py#L565-L567), [`:1147–1181`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/workflow_docs.py#L1147-L1181) | The generator ignores its `products_dir` for output and writes to the relative legacy `dashboard/docs`; the pipeline graph and durations are hardcoded. Running from a different working directory changes output location; actual DAG evolution can leave published documentation stale. Parameterize the output root, derive pipeline data from the versioned DAG, and test docs-vs-DAG drift. Legacy dashboard is out of active remediation scope, so this is a documentation generator finding, not a request to fix the old dashboard. |
| BX-C02 | P2 | [`workflow_docs.py:796–860`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/workflow_docs.py#L796-L860), [`:1082–1145`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/workflow_docs.py#L1082-L1145) | Agent names, descriptions and input/output text are interpolated into XML attribute values without XML escaping. A supplied quote, ampersand or angle bracket can break Draw.io XML; if untrusted content enters the workflow objects, HTML-capable diagram values also warrant sanitization. Use an XML serializer, escape attribute values, and parse generated `.drawio` in tests with adversarial strings. |
| BX-C03 | P2 | [`workflow_docs.py:1082–1145`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/workflow_docs.py#L1082-L1145) | Agent step nodes use `x=350+i*180` and page width 1500, with a fixed output node at x=1200; longer agent workflows extend beyond the canvas and overlap/outgrow the output position. Compute canvas and output placement from step count, and verify Draw.io geometry for longest configured agent workflow. |
| BX-C04 | P2 | [`workflow_docs.py:1147–1181`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/workflow_docs.py#L1147-L1181), [`:782–788`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/workflow_docs.py#L782-L788) | Generated HTML advertises `pipeline-workflow.pdf`, but the observed `save_all_documentation` writes HTML and Draw.io, not PDF. The method also overwrites files directly without atomic publication. Either implement and verify PDF output or remove the dead link; publish a complete generated docs set atomically. |

**Evidence caveat:** This is a deep source-based analysis of generation paths, not a runtime XML/HTML validation. The active pipeline's stage configuration was not exhaustively compared to each hardcoded step, so no claim is made about the exact number of stale stages.

## 3. Four historical executor snapshots — comparative disposition

All four pinned historical source files were retrieved. Their line counts and blob SHAs are recorded below for reproducibility. These `.bak_pre_*` files are archival source, not evidence that their code is imported at runtime. Historical defects are recorded as regression cases, not new active defects.

| Snapshot | Lines | Git blob SHA | Comparison and review disposition |
|---|---:|---|---|
| `core/pipeline_executor.py.bak_pre_agent_exec` | 1,555 | `760657f63f8248b9e09f1e3a82bc94e3e9d77bf1` | Monolithic agent execution is still present; `PipelineExecutor` inherits `AgentRunnerMixin` and `StageRunnerMixin`. At lines 1338–1345, time-budget expiry explicitly assigns `PipelinePhase.COMPLETION`; at 1389–1394, finalization completes any nonfailed run. The active executor now marks time-budget expiry FAILED and checks terminal DAG scope. |
| `core/pipeline_executor.py.bak_pre_agent_runner` | 2,416 | `7cc08bdcbb02bcdb619d85f67f2880123e2778ba` | Agent generation, prompt construction and tool invocation are embedded in `PipelineExecutor`, before extraction into `AgentRunnerMixin`. Legacy approval and direct checkpoint writes remain. Structural comparison completed; full semantic function-by-function equivalence has not been established. |
| `core/pipeline_executor.py.bak_pre_llm_extract` | 3,491 | `6e63539c9711a09881f862cb777bd132e409918c` | Pre-extraction monolith contains inlined LLM/API request and response handling alongside agent and pipeline execution. Its earlier checkpoint writer uses direct final-path writes. Full behavioral diff against extracted `llm_client.py` is still pending. |
| `core/pipeline_executor.py.bak_pre_stage_runner` | 1,848 | `93afa4dcfda9c4a84181b73c86ec906eabc23d6c` | `PipelineExecutor` inherits `AgentRunnerMixin` but still contains stage execution. At lines 1337–1344 and 1388–1394 it retains the same false-completion-on-budget-expiry behavior as `bak_pre_agent_exec`. Active executor moved stage logic to `StageRunnerMixin` and changed budget completion behavior. |

**Regression preservation:** Test interrupted resume, timeout, emergency budget stop, stage failures, approval rejection, checkpoint atomicity and artifact provenance against the active executor. Historical copies should be excluded from active-code scanning/deployment packages unless explicitly used as fixtures. No finding is labeled as an active vulnerability solely because it exists in a `.bak_pre_*` snapshot.

## 4. Merged remediation and evidence gates

1. **Fail-closed release and compliance:** Fix the active human-proxy decision propagation (BV-C01), item quality-gate result (existing PF-060), zero-check compliance (BU-C07) and CLI exit-code allowlist (BW-C01). Regression suite must demonstrate rejection/unknown/no-tests cannot produce success.
2. **Single canonical state authority:** Remove CLI writes to the derived `pipeline.json` (BW-C02–C04), enforce run ownership, and use DAG/checkpoint state for resume (BW-C05). Integrate with backlog transaction fixes (BU-C02–C05).
3. **Artifact completeness and provenance:** Enforce run-scoped compliance artifacts, fail closed on mandatory output-checklist exceptions and missing feature sections (BU-C06–C08, BV-C03–C04).
4. **Documentation correctness:** Make docs generated from the configured DAG and use safe XML serialization (BX-C01–C04). The legacy dashboard remains excluded from active scope.
5. **Historical regression controls:** Preserve the four snapshots only as archive; compare extracted components and add tests for corrected old defects. No full behavioral equivalence is asserted.

## 5. Certification accounting

**Last independently reconciled complete-review checkpoint: 384/394.** The six remaining paths from the prior BU–BV report have now been retrieved and subjected to structural inspection, with detailed source review of key CLI and documentation flows and comparative inspection of the four historical snapshots. The prior four active files have expanded semantic reviews. **No additional files are certified solely from this continuation:** full line-by-line review, exhaustive snapshot diffs and complete historical-register deduplication have not been demonstrated. The provisional BW/BX observations should not be added to PF-521 as final numbered findings without that reconciliation. No runtime tests or repository edits were performed.


---
# Batch BY — deep semantic closure: workflow documentation generator

**Scope and evidence:** `srinikc/productforge`, pinned `develop` commit `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`. Complete static source read of `product-forge/core/workflow_docs.py`, 1,300 lines, Git blob `c62d3c7978d7b208c033d61d25e3af5945d6c2ad`. The review covered all dataclasses, the full 12-phase hardcoded pipeline definition, all 17 agent workflow definitions, both HTML emitters, both Draw.io XML emitters, save/publish logic and generated index. Historical BW/BX candidates were reconciled to avoid double counting. This is **static semantic certification**, not a runtime test or validation of rendered documents.

**Updated certified count: 385/394; 9 pending.** This is one new completed full-source review since the last reconciled 384/394 checkpoint. Earlier partial inspection of the same file is not counted again. The nine outstanding paths are `core/backlog.py`, `core/compliance_check.py`, `core/orchestrator/agent_runner.py`, `core/pipeline_executor.py`, four `core/pipeline_executor.py.bak_pre_*` historical snapshots, and `scripts/pipeline.py`.

## BY findings and evidence reconciliation

| Ref | Priority | Source | Deep-review conclusion | Action / test |
|---|---|---|---|---|
| BX-C01 reconfirmed | P2 | `workflow_docs.py:44–55, 185–563, 1147–1184` | The `products_dir` argument is retained but not used to select the output directory; fixed `dashboard/docs` paths are relative to the process CWD. The 12-phase pipeline and 17 agent workflows are independent hardcoded descriptions, including hardcoded model recommendations. Changes to the active DAG or agent registry will not update these docs automatically. | Parameterize documentation output and derive versioned source-of-truth metadata; assert documentation-vs-DAG parity in CI. The old dashboard itself remains excluded from remediation. |
| BX-C02 reconfirmed, strengthened | P2 | `workflow_docs.py:796–860, 1082–1145` | Both Draw.io emitters interpolate text directly into XML attribute values. This is **not merely hypothetical untrusted input**: the built-in phase `Documentation & Onboarding` at lines 133–135 already contains a raw `&`, and `generate_pipeline_drawio()` inserts `phase['name']` unescaped at line 840, so generated pipeline XML is not well-formed for the shipped workflow. Agent names and descriptions are likewise unescaped. | Serialize with `xml.etree.ElementTree` or equivalent and test parsing generated pipeline and all 17 agent diagrams; include `&`, `<`, `>` and quoted input values. |
| BX-C03 reconfirmed | P2 | `workflow_docs.py:1082–1136` | Agent step boxes extend horizontally as `350+i*180` while output is fixed at x=1200 and page width is 1500. The 8-step presentation and product-analyzer flows reach x=1610 for their last step and exceed the fixed output node position. | Derive page width and output placement from the longest workflow; test all agent diagram bounding boxes. |
| BX-C04 reconfirmed | P2 | `workflow_docs.py:782–788, 1147–1184` | Generated pipeline HTML links `pipeline-workflow.pdf`, but the entire save method writes only HTML and `.drawio` outputs. All outputs are direct overwrite writes, so partial publication is possible. | Remove or generate the PDF link; stage output in a temporary directory and atomically publish the complete documentation set. |
| BY-C01 additional | P2 | `workflow_docs.py:862–1080, 1186–1299` | Agent HTML and index use unescaped interpolation for `agent_name`, role, purpose, input/output and workflow-step text. Today `get_agent_workflows()` supplies static strings, limiting current exploitability, but the public `generate_agent_html(agent_workflow)` method accepts caller-supplied dataclass values. If external/custom agent definitions are supported, an HTML injection path exists. | HTML-escape all dynamic text and attribute values; test hostile custom `AgentWorkflow` values. This is a candidate pending full PF-001–PF-521 register deduplication. |

**Call-chain and trust boundaries:** `save_all_documentation()` calls the two pipeline renderers and iterates `get_agent_workflows()` through the two agent renderers, then generates the index. No calls to the active pipeline registry, DAG loader or runtime agent configuration were found in this 1,300-line module. The generator produces documentation only; it does not execute workflow steps or validate agent outputs. No exception handling or rollback wraps the multi-file publish. Model names in this module are documentation recommendations, not verified current model availability.

**Regression tests to add:** (1) generated pipeline XML parses successfully with the shipped `Documentation & Onboarding` phase; (2) all 17 generated agent XML files parse; (3) injected special characters remain literal text after HTML/XML serialization; (4) all links in the generated index and pipeline page resolve to emitted files; (5) diagram bounds encompass all steps; (6) interrupted publish does not leave a mixed documentation set; (7) output root respects configuration; (8) generated metadata matches the active DAG and agent registry.

**Remaining certification queue (9):** four active modules (`backlog.py`, `compliance_check.py`, `orchestrator/agent_runner.py`, `pipeline_executor.py`), one CLI (`scripts/pipeline.py`), four historical executor backups. Prior BU–BX source inspection of those nine remains useful evidence but not completed certification. Existing permanent finding IDs PF-001–PF-521 are preserved; BW/BX and BY candidate references remain provisional pending exhaustive register deduplication. No runtime tests or repository edits performed.

---

# Batch BZ — Nine-file closure attempt and reconciled audit ledger

**Scope:** immutable `develop` commit `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`. This continuation revisited **all nine pending files**, retrieved their complete source blobs and function inventories, and examined additional implementation ranges in the active backlog, compliance engine, runner, executor, CLI and archival snapshots. Source retrieval and structural scanning are **not** substituted for complete semantic review. No runtime tests, repository changes, exhaustive four-way historical diffs or complete PF-001–PF-521 deduplication were performed. Therefore **certified coverage remains 385/394; nine files remain pending full certification**. This report does not claim the requested nine-file deep-review closure was achieved.

## BZ additional findings and stronger evidence

| ID | Priority | File and source lines | Analysis, relationship to earlier findings, and acceptance test |
|---|---|---|---|
| BZ-C01 | P1 | [`core/backlog.py:127–165,168–194`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/backlog.py#L127-L194) | **Interrupted migration can hide legacy backlog items.** `_load_all` switches from legacy arrays to item files whenever *any* item JSON exists. If migration fails after writing only a subset, subsequent loads ignore legacy-only items; rerunning migration may then overwrite lean indexes from that subset. The migration lock also inherits PF-025's timeout behavior. Introduce migration manifest + reconciliation of legacy and item stores before switching authority, transactional publication and interrupted-migration tests. Related to prior BU-C04; do not double-count without reconciliation. |
| BZ-C02 | P1 | [`core/backlog.py:103–108,154–165,427–474`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/backlog.py#L103-L108) | **Multi-file commit is not atomic.** Individual `_wj` writes use fixed `.tmp` plus `os.replace`, but an add/update persists the canonical item, two indexes, counters and history separately. Failure between writes leaves inconsistent projections or missing history; fixed `.tmp` can collide with concurrent lock-bypassing writers. Use an exclusive, verified lock, unique temp files, transaction journal and index rebuild/recovery tests. Reinforces PF-025 and BU backlog persistence candidates. |
| BZ-C03 | P2 | [`scripts/pipeline.py:445–492`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/pipeline.py#L445-L492) | `test_infrastructure` prints `PASS` for existence of directories, JSON parseability and agent Markdown files, not actual infrastructure functionality, and `main()` does not propagate its result as a nonzero exit code. Rename as structural preflight, and add executable health/integration tests with failing exit codes. Distinct from PF-036's compliance `tests_pass` issue. |
| BZ-C04 | P1 | [`scripts/pipeline.py:1817–1894`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/pipeline.py#L1817-L1894), [`core/compliance_check.py:325–389`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/compliance_check.py#L325-L389) | **Cross-module success contract is unsafe.** CLI `show_compliance` returns 0 for unknown/missing status; consolidated compliance `conformed` is true when zero failed checks exist, including zero checks. A no-evidence report can be surfaced as successful. Enforce positive evidence (`total_checks > 0`, all mandatory checks PASS, current run), strict CLI success allowlist and end-to-end tests. Consolidates prior BW-C01/BU-C07, not a separate permanent defect. |
| BZ-C05 | P2 | [`scripts/pipeline.py:1938–2022`](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/pipeline.py#L1938-L2022) | `show_phases` displays the stored `percent_complete` and `completed` counters without reconciling against the phase feature lists, allowing stale or impossible displayed progress. Clamp/derive from canonical feature state and test contradictory counters. Presentation/state-integrity concern, not an execution-gate bypass by itself. |

## Historical-backup cross-check (archival only)

The four snapshots were re-fetched and compared structurally against the active 3,435-line executor. Both `bak_pre_agent_exec` and `bak_pre_stage_runner` set `PipelinePhase.COMPLETION` on time-budget expiry (`:1338–1345` and `:1337–1344`, respectively); the current finalizer at `:3174–3198` requires terminal scoped states, although it still has existing PF-069's unknown-scope-ID filtering defect. `bak_pre_agent_runner:571–622` and `bak_pre_llm_extract:539–590` reject explicit interactive `rejected` decisions; the **new active** human-proxy branch at `pipeline_executor.py:1033–1044` instead discards the returned proxy decision and always returns approved (BV-C01). This is a regression target, not proof that the backups execute. Full function-by-function equivalence/diff of extracted agent, stage and LLM implementations is **not completed**.

## Certification ledger — unchanged, explicit

| Status | Files | Basis |
|---|---:|---|
| Certified before BU | 384 | Prior reconciled 394-path scope |
| Certified in BY | 1 | Full static semantic review of `core/workflow_docs.py` |
| **Certified total** | **385 / 394** | **97.7%** |
| **Pending full certification** | **9** | All have targeted/expanded reviews; not all have exhaustive semantic and archival comparison |

**Nine pending:** `core/backlog.py` (1,087 lines), `core/compliance_check.py` (1,445), `core/orchestrator/agent_runner.py` (1,784), `core/pipeline_executor.py` (3,435), `scripts/pipeline.py` (2,179), `core/pipeline_executor.py.bak_pre_agent_exec` (1,555), `core/pipeline_executor.py.bak_pre_agent_runner` (2,416), `core/pipeline_executor.py.bak_pre_llm_extract` (3,491), and `core/pipeline_executor.py.bak_pre_stage_runner` (1,848). Total ~19,240 source lines. Full closure requires sequential, complete semantic review of these nine; historical snapshots should be separately classified as archival if scope policy permits, rather than falsely certified from targeted diffs.

## Immediate consolidated remediation sequence

1. **P0/P1 fail-closed control plane:** Fix BV-C01 active human-proxy decision propagation; PF-060 item quality gate result; PF-069 unknown selective-stage IDs; BW-C01 and BU-C07/BZ-C04 no-evidence compliance success.
2. **P1 state ownership and integrity:** Fix PF-025 backlog lock timeout, BZ-C01 interrupted migration, BZ-C02 multi-file commit, BW-C02 manual completion, BW-C03 queue/lock fallback, BV-C06 foreign run lock.
3. **P1 output integrity:** Fix BV-C02 missing-spec tool authorization, BV-C03 incomplete sectioned outputs, BV-C04 output-checklist exception handling and BV-C05 canonical artifact atomicity.
4. **Evidence and regression suite:** Verify test commands/exit codes/artifact hashes, explicit human decisions, run-scoped reports, failure injection during migration and checkpoint persistence, and historical timeout/approval regressions.

**Audit limitation:** Static inspection only. Findings are candidates unless already assigned a PF ID in the retained cumulative report. Do not treat the candidate count as new, deduplicated permanent findings or claim the entire 394-file audit has closed.


---

# Batch CA — closure batch 1 of 3: backlog and compliance engine

**Audit target:** immutable commit `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`; legacy dashboard excluded. This appendix supersedes earlier progress statements: **387/394 certified; 7 pending.** Complete source for `core/backlog.py` (1,087 lines) and `core/compliance_check.py` (1,445 lines) was retrieved, with focused semantic review of their full function inventories, all mutation/persistence and reporting paths, checklist declarations, and prior findings. This is *static* certification; there were no runtime tests, repository modifications, or proof of production exploitability. Earlier BU/BZ candidate findings are reconciled by subject rather than assigned new permanent PF IDs; PF-001–PF-521 remain unchanged.

## CA-1 — `core/backlog.py` — full-file static certification

Git blob `cdc69f65bb966118222de78e77a35f04badba0f7`; [pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/backlog.py).

Reviewed scope: normalization/path derivation, JSON and per-item persistence, legacy migration, lock/ID/label generation, similarity and duplicate detection, create/get-or-create, status/link/pair, index/list/history, delete/update/triage/accept, parked/stale/stats, reciprocal checks and CLI entry point. The critical cross-function invariant is **canonical item + derived indexes + counters + history + optional queue event**. Current implementation does not commit those together.

| Reconciled issue | Priority | Verified mechanism | Required regression test |
|---|---|---|---|
| PF-025 / BU-C02 (existing) | P1 | `_lock()` returns `None` after 50 retries; mutating callers continue anyway (`:197–215`, `:427–474`, `:794–843`). `ensure_item` releases lock before calling `add_epic` (`:477–500`). | Hold a foreign lock and concurrently create the same external ID; assert no write/duplicate. |
| BZ-C01 / BU migration (existing candidate) | P1 | `_load_all` switches completely to item JSON whenever **any** file exists (`:127–151`). An interrupted migration leaves legacy-only entries invisible until recovery (`:168–194`). | Inject failure after first of N migrated items; restart and assert all N remain visible. |
| BZ-C02 (existing candidate) | P1 | `_wj` atomically replaces each individual file using a fixed `.tmp` name, but item, indexes, counters and history are independent writes (`:103–108`, `:154–165`, `:427–474`). | Crash after each persistence step; replay/rebuild indexes and verify IDs, counters and journal. |
| BU backlog identity/path (existing candidate) | P1 | Project name is joined into `_PRODUCTS` without a root-containment check (`:78–86`); `update(**fields)` can rewrite `id`, `scope`, `project` while persisting to the original filename (`:817–843`). CLI-only exposure is conditional; callers must be assessed before assigning an exploit claim. | Reject `../` and absolute project paths; reject immutable identity-field updates. |
| BU queue (existing candidate) | P1 | `accept(when='now')` first marks `queued`, then swallows portfolio enqueue errors (`:867–879`). | Force enqueue failure; item must not claim scheduled execution. |
| Additional consistency checks | P2 | `pair()` uses two independent updates (`:632–654`); `triage()` performs two updates (`:846–864`); `delete()` suppresses file-deletion errors (`:794–814`); history append suppresses errors (`:286–299`). | Fault-inject between reciprocal writes and during deletion/history; assert recovery or explicit failure. |

**Disposition:** Deep static file review complete; no new permanent PF IDs assigned before historical-register reconciliation. Backend reciprocity warnings were inspected, but remediation of the legacy dashboard remains out of scope.

## CA-2 — `core/compliance_check.py` — full-file static certification

Git blob `fade16a0d628ebe1df7636c85bef127aa81334e3`; [pinned source](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/compliance_check.py).

Reviewed scope: artifact lookup, derived and explicit checklists, status/severity model, report aggregation, agent execution and exception handling, persistence/final report, file/content/ID/audit/state/test/stub/Docker helper functions, all per-agent declarative checklist categories and CLI runner. The essential invariant is **positive, current-run verification evidence**; existing reporting does not enforce it.

| Reconciled issue | Priority | Verified mechanism | Required regression test |
|---|---|---|---|
| PF-036 (existing) | P1 | `tests_pass()` returns PASS when a test directory exists; explicitly does not run pytest (`:700–720`). | Existing test directory containing a failing test must not yield verified PASS. |
| BU-C07 / BZ-C04 (existing candidate) | P1 | Final `conformed` is true whenever critical/total failures are zero, even if `total_checks==0`, or checks were skipped/unknown/partial (`:325–389`). | Zero-check, all-skipped and all-unknown reports must not conform. |
| BU-C06 (existing candidate) | P1 | `_agent_output_artifact()` searches stage artifacts without binding them to the requested current run (`:40–74`); report files are named by agent/stage and `latest` is overwritten (`:305–324`). | Stale artifact from a prior run must fail current-run validation; concurrent runs must preserve independent reports. |
| BU-C08 (existing candidate) | P1 | Check function exceptions become UNKNOWN (`:258–304`), while noncritical failure aggregation can produce PARTIAL (`:180–218`); neither is inherently fail-closed at the final-report level. | Mandatory checker exception and partial failure must block release and report exact evidence. |
| Additional helper semantics | P2 | `docker_build_works()` checks Compose YAML structure and services; it does not run `docker build` (`:653–697`). `test_files_exist()` counts test files, not test execution (`:586–610`). | Distinguish structural validation from build/test execution in machine-readable evidence. |

**Disposition:** Deep static file review complete. Per-agent checklist entries are declarative specifications, not proof that downstream gates execute every check or honor UNKNOWN/SKIPPED. End-to-end gate enforcement must be tested against `pipeline_executor.py` and `scripts/pipeline.py` in closure batch 2.

## Updated certification ledger and remaining 2 batches

| Checkpoint | Certified | Pending |
|---|---:|---:|
| Previous BY/BZ reconciled checkpoint | 385 | 9 |
| Batch CA: backlog + compliance | **387** | **7** |

**Closure batch 2 (3 active files):** `core/orchestrator/agent_runner.py` (1,784 lines), `core/pipeline_executor.py` (3,435 lines), `scripts/pipeline.py` (2,179 lines). Complete cross-module execution/approval/compliance/CLI-state trace, inspect each remaining implementation branch and reconcile BV/BW findings.

**Closure batch 3 (4 archival files):** `core/pipeline_executor.py.bak_pre_agent_exec` (1,555 lines), `core/pipeline_executor.py.bak_pre_agent_runner` (2,416 lines), `core/pipeline_executor.py.bak_pre_llm_extract` (3,491 lines), `core/pipeline_executor.py.bak_pre_stage_runner` (1,848 lines). Full comparative static review of extracted agent/stage/LLM behavior; classify archival-only risks and confirm backups are not imported or packaged. Do not mark archival files certified on the strength of a targeted diff alone.

**Scope note:** 387/394 is source-review certification, not a clean bill of health or evidence that all defects are resolved. No runtime tests were run. The earlier permanent register remains PF-001–PF-521; candidates are cross-referenced, not added as duplicate permanent findings.


---
# Batch CB — closure batch 2 of 3: active agent runner, pipeline executor and CLI

**Scope and provenance.** `srinikc/productforge`, `develop` pinned at `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`. The three complete pinned source blobs were retrieved (1,784 + 3,435 + 2,179 = 7,398 source lines); their function inventories and execution, state, approval, tool, artifact, compliance and CLI branches were examined. This is a deep **static file-level semantic review**, not an executed test, proof of all possible call paths, or validation of production behavior. Existing permanent PF-001–PF-521 remain unchanged; prior BV/BW observations are reconciled here rather than counted again. Legacy dashboard excluded.

## CB-1. Agent runner — `core/orchestrator/agent_runner.py`

**Blob SHA:** `d848d93d92dcb7d8687eea9eed73f4ee634dda92`. [Pinned file](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/orchestrator/agent_runner.py).

**Semantic paths:** bounded native-tool loop with strict/recovery retries; model/token accounting; input fingerprint and assembled-prompt cache; sectioned and per-feature generation; unusable/truncated/fallback handling; canonical artifact and per-feature file publication; output-checklist validation; knowledge/context assembly; tool schema and invocation authorization; output formatting and delegation to LLM client. The tool loop is bounded, but its accounting and failure paths are not fail-closed.

| Reconciled reference | Priority | Verified source mechanism | Required remediation / test |
|---|---|---|---|
| PF-067 | P2 | `:100–107,166–209`: model tokens/cost are accumulated across tool-loop attempts, while `tool_calls`, `tool_iterations`, `tool_writes` are replaced with latest attempt's stats; fallback to `_call_llm` returns its stats rather than cumulative tool-attempt usage. | Aggregate all attempts and final fallback usage; compare ledger and invoice-equivalent totals in strict/recovery/fallback fixtures. |
| BV-C02 | P1 | `:1489–1507`: `execute_agent_tool` denies a disallowed tool **only when an agent spec exists**. Absent spec bypasses the allowlist and reaches `tool_registry.execute`. `get_tools_for_agent` does return `[]` for absent spec (`:1480–1487`), but direct invocation is not protected by that discovery behavior. | Require a known spec and an explicit tool allowlist on every execution; test direct calls for unknown agents and write-capable tools. |
| BU-01 / BV-C04 | P1 | `:245–257`: `_cache_output_ok` swallows output-checklist exceptions and returns `True`, admitting unverified output to the input-side cache. | Reject caching on mandatory validation exceptions; fault-inject the checker. |
| BU-02 / BV-C05 | P1 | `:419–445`: canonical output is written with `open(...,'w')` directly to final path, then auxiliary feature/index and formatting paths are handled separately. Process failure can truncate a previously valid artifact. | Write run-scoped temp output, fsync/atomic replace after validation, and publish feature/index set consistently; kill-process test at every write boundary. |
| BV-C03 | P1 | `:960–1024`: per-feature generation logs empty feature sections but can return merged nonempty text; non-feature missing essentials are retried once but unresolved omissions do not force failure here. `:369–399` only rejects explicit truncation/unusable content. | Enforce exact expected feature-ID and essential-section sets before completed status; fail or mark needs_retry for omissions, including checklist exceptions. |
| Additional tool-loop failure semantics | P2 | `:180–213`: empty/short tool results fall back to a standalone no-tool LLM call; the fallback may produce a narrative without the intended write_file side effect. Subsequent completion depends on content validity, not proof of expected tool writes. | For write-required agents, require verified workspace writes or explicit policy-approved exception before completion. |

**Scope qualification:** No assertion that the missing-spec path is externally reachable without another caller; the direct method itself does not enforce authorization. The sectioned-output concern is a source-level missing enforcement check, not a claim that every incomplete result bypasses downstream validators.

## CB-2. Active executor — `core/pipeline_executor.py`

**Blob SHA:** `f5b5e68e028050b7a976337a5d41981c97d10696`. [Pinned file](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/pipeline_executor.py).

**Semantic paths:** initialization and config, run/checkpoint lifecycle, resume/invalidation, approval request/decision/timeout policy, human proxy, DAG load, budgets and model preflight, stage scheduling, pause/stop, terminal-state finalization, schema and quality checks, final reports and journal. The executor delegates agent/stage behavior to mixins, so cross-module invariants matter more than isolated method success.

| Reconciled reference | Priority | Verified source mechanism | Required remediation / test |
|---|---|---|---|
| BV-C01 | P0 | `:1033–1044`: `human_proxy.decide` result is logged, then `_wait_for_approval_ex` returns `_ok` (`decision=approved`) irrespective of the actual proxy decision. | Propagate and validate actual decision; test reject/changes/regenerate/abort/exception and ensure none is silently approved. |
| Existing PF-060 | P0 | `:3174–3198,3233–3267`: phase is set COMPLETION and checkpoint saved before `gate_if_item_run`; its returned result is ignored and only exceptions print a skipped warning. Final return depends on phase only. | Execute mandatory quality gate before completion, inspect its boolean/result, persist FAILED on rejection and return false. |
| Existing PF-069 | P1 | `:3117–3123,3177–3185`: selected stage IDs missing from DAG are filtered from `all(...)`, so a nonempty unknown-only scope can appear terminal and complete. | Validate selected IDs before execution and require exact selected set matches; mixed/unknown-only tests. |
| BV-C06 | P1 | `:2859–2873`: run-lock preflight checks whether **some** project lock exists, not whether its holder/run ID matches this executor; exceptions skip lock validation. | Verify owner token and active run ID, fail closed on lock-manager error, test foreign lock and lost-lock races. |
| CB-C01 (new candidate) | P1 | `:743–775`: `_restore_from_checkpoint` restores completed stage states, then scans each stage directory for `*-output.md` and reconstructs completed agent executions without matching artifact run ID, checksum or checkpoint provenance. An older file may be attached to a resumed completed stage. | Store per-agent artifact manifest (run ID, hash, timestamp and expected agent set) in checkpoint; on resume reject stale/missing artifacts and invalidate affected stage. Test a completed stage with files from a prior run. |
| CB-C02 (new candidate) | P1 | `:930–959,975–1010`: approval file is keyed only by stage and agent, overwritten directly, and `_check_approval_status` returns status without checking stored `run_id` or request ID. The interactive wait accepts a decided status from the file. A stale or concurrently overwritten decision can be applied to a different run. | Use run-scoped approval path/request ID, validate run and artifact digest at decision consumption, atomically update with optimistic versioning. Test stale approval from previous run and two concurrent requests. |
| CB-C03 (new candidate) | P2 | `:687–731`: checkpoint uses fixed `state_file+'.tmp'` and swallows persistence errors; the derived `pipeline.json` sync failure is also swallowed. This is individually atomic only if a single writer owns the file; a foreign run lock is not reliably rejected (BV-C06). | Unique temp path and verified ownership; fail/stop on mandatory checkpoint failure, recover projection from canonical checkpoint. |
| Existing completion correction | Positive evidence | `:3084–3094,3174–3198`: time-budget expiry now sets FAILED and normal completion requires terminal scoped stages, unlike two historical backups. This does not repair PF-060 or PF-069. | Preserve in regression tests; do not relabel old snapshot defects as new active findings. |

**Cross-module gate trace:** `AgentRunnerMixin` can publish a syntactically nonempty artifact; `ComplianceChecker.tests_pass` can PASS without running tests (PF-036); `generate_final_report` can conform with zero failures even when no checks ran (BU-C07); executor then can mark COMPLETION before and irrespective of item quality-gate result (PF-060). Fixes must be tested end-to-end rather than only as unit-level return-value changes.

## CB-3. CLI — `scripts/pipeline.py`

**Blob SHA:** `31da655e755a36031ffe5d082570845857f90c0d`. [Pinned file](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/scripts/pipeline.py).

**Semantic paths:** command routing, project selection and status/health, infrastructure checks, locks and queue, budget, circuit reset, resume instructions, manual stage completion, compliance command/exit code, metrics and reporting, adoption. The CLI mixes reporting and legacy state mutation; legacy fallbacks must not bypass the canonical execution authority.

| Reconciled reference | Priority | Verified source mechanism | Required remediation / test |
|---|---|---|---|
| BW-C01 | P1 | Compliance CLI uses a status-to-exit-code mapping that fails only explicit fail/partial; unknown/empty status can return success (see earlier BW appendix). `main:2162–2168` propagates that return as process exit code. | Allow exit 0 only for verified PASS with required evidence; inject UNKNOWN, SKIPPED and empty reports. |
| BU-03 / BW-C02 | P1 | `:1344–1376,2152–2157`: `mark-complete` directly sets derived `pipeline.json` stage status and `pipeline_complete` when all dictionary entries are completed; no run-bound gate evidence and nonexistent stage prints success. | Route completion through canonical DAG/approval/quality authority; reject unknown stage, require verified current-run evidence. |
| BU-04 / BW-C03 | P1 | `:687–742,768–810`: legacy fallback lock and queue use unguarded JSON read-modify-write; queue manager exception triggers legacy queue instead of surfacing failure, allowing divergent authorities. | Remove mutable legacy fallback or enforce a single canonical lock/queue manager; concurrency and manager-failure tests. |
| BW-C04 | P1 | `:1040–1089`: circuit-reset core path calls `reset_all()` without a project argument, while legacy fallback resets project `pipeline.json` and clears its lock. Scope and authority differ across code paths. | Define project-scoped reset semantics, explicit permission and audit evidence; test unrelated projects remain unchanged. |
| BW-C05 | P2 | `:1178–1321`: continue guidance parses `docs/pipeline-state.md` with hardcoded stages 0–9 and infers next stage as last completed +1, while active execution resumes from canonical checkpoint/DAG. It prints a resume claim but does not invoke executor. | Read canonical DAG/checkpoint and report actual runnable/blocked stages; label command informational or wire it to run entry. |
| CB-C04 (new candidate) | P2 | `:445–491,2061–2063`: `test_infrastructure` checks paths, JSON syntax and agent-file existence only; `main` ignores its computed `overall` and exits normally even if checks failed. A shell/CI caller sees success for a failed infrastructure check. | Return `overall`, map false to nonzero process exit and separate smoke checks from execution tests. |
| CB-C05 (new candidate) | P2 | `:2153–2157`: `mark-complete` converts the stage argument using `int`, despite stage keys including alphanumeric IDs such as 7a/7b; this command cannot address those stages and may throw ValueError. | Accept and validate stage IDs as DAG strings; test numeric and alphanumeric stages. |

## CB-4. Consolidated disposition and certification

**Static review ledger:** prior Batch CA **387/394**. This batch certifies three additional active-file static semantic reviews, yielding **390/394 (98.98%)**, with **four archival executor snapshots pending**. The certification means the full source blobs and major function inventories/behavioral paths were reviewed and findings reconciled by issue; it does **not** mean exhaustive branch coverage, complete call-site proof, runtime testing or remediation. If a stricter definition requires executed branch tests, retain the earlier 387/394 *test-validated* count; none of the reviewed files has passed that stronger gate.

| File | Lines | Review disposition |
|---|---:|---|
| `core/orchestrator/agent_runner.py` | 1,784 | Static semantic review completed; existing PF-067/BV findings reconciled. |
| `core/pipeline_executor.py` | 3,435 | Static semantic review completed; PF-060/PF-069/BV findings reconciled; new CB-C01–C03 candidates. |
| `scripts/pipeline.py` | 2,179 | Static semantic review completed; BW/BU findings reconciled; new CB-C04–C05 candidates. |
| Four `.bak_pre_*` executor snapshots | 9,310 | **Pending** full archival comparison and import/package reachability assessment. |

**Priority order:** (1) propagate human-proxy decisions and enforce quality-gate result; (2) bind approvals, restored artifacts and compliance reports to current run and artifact digest; (3) eliminate missing-spec tool execution and derived-state CLI mutations; (4) make checkpoints/queue/lock ownership atomic and fail closed; (5) make infrastructure/compliance commands return evidence-based nonzero exit codes.

**No runtime tests executed; no repository files changed.** All CB-Cxx IDs are provisional and must be deduplicated against the full PF register before allocating permanent IDs. Historical appendix material is retained in full above, including legacy-dashboard exclusions and previously certified file inventory.

---
# Batch CC — final scoped archival executor review and consolidated closure

**Baseline:** `srinikc/productforge` at immutable `develop` commit `e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374`. **Scope:** four remaining archived `core/pipeline_executor.py.bak_*` snapshots. Each complete blob was retrieved through the GitHub connector; full function inventories, import structure and high-risk execution/approval/checkpoint/compliance/agent-execution paths were compared with the active executor and the prior cumulative register. This is **static semantic source review**, not exhaustive dynamic branch coverage, byte-for-byte diff certification, or a test run. Legacy dashboard remains excluded.

## CC-1. Archival snapshot inventory and extraction boundaries

| Archived file | Source lines | Blob SHA | Architecture and archival role | Static disposition |
|---|---:|---|---|---|
| `core/pipeline_executor.py.bak_pre_agent_exec` | 1,555 | `760657f63f8248b9e09f1e3a82bc94e3e9d77bf1` | `PipelineExecutor(AgentRunnerMixin, StageRunnerMixin)`; older in-class `execute_agent` plus extracted runner/stage mixins. | Reviewed as historical snapshot; not the active `.py` module. |
| `core/pipeline_executor.py.bak_pre_agent_runner` | 2,416 | `7cc08bdcbb02bcdb619d85f67f2880123e2778ba` | Monolithic `PipelineExecutor`, in-class generation, tool dispatch and stage execution. | Reviewed as pre-agent-runner extraction baseline. |
| `core/pipeline_executor.py.bak_pre_llm_extract` | 3,491 | `6e63539c9711a09881f862cb777bd132e409918c` | Largest monolithic snapshot with pre-extraction LLM methods, agent generation and stage execution. | Reviewed as historical baseline for LLM extraction. |
| `core/pipeline_executor.py.bak_pre_stage_runner` | 1,848 | `93afa4dcfda9c4a84181b73c86ec906eabc23d6c` | `PipelineExecutor(AgentRunnerMixin)`; stage runner remains in class. | Reviewed as pre-stage-runner extraction baseline. |

**Important archival qualification:** These filenames lack the `.py` suffix and are not the active `core/pipeline_executor.py` imported by ordinary Python module resolution. The review does **not** establish that no packaging script, manual invocation, backup restore or other tool can copy/execute them. Repository-wide packaging and reference search was not completed; treat reachability as **not verified**, rather than asserting that archival defects are impossible to activate.

## CC-2. Reconciled historical regression findings (no duplicate permanent PF IDs)

| Cross-reference | Severity if reintroduced | Historical evidence | Active-code comparison | Regression requirement |
|---|---|---|---|---|
| CC-H01 / prior BW historical completion defect | P0 | `bak_pre_agent_exec:1338–1345`; `bak_pre_agent_runner:1905–1912`; `bak_pre_llm_extract:2775–2782`; `bak_pre_stage_runner:1337–1345`: time-budget failure sets `PipelinePhase.COMPLETION`. Their finalizers also set COMPLETION whenever not FAILED (e.g. `bak_pre_agent_exec:1389–1398`, `bak_pre_llm_extract:2826–2835`). | Active executor `:3084–3094` sets FAILED on time-budget expiry. Active completion still has independent PF-060/PF-069 weaknesses; historical fix is not proof of overall correct completion. | Parameterized budget-expiry test on active executor; verify failed/resumable checkpoint and no `pipeline_complete` event, even when earlier stages passed. |
| CC-H02 / existing state-integrity family | P1 | All four archived `_save_checkpoint` methods directly truncate `self.state_file` with `open(...,'w')`: `bak_pre_agent_exec:471–505`; `bak_pre_agent_runner:469–503`; `bak_pre_llm_extract:437–471`; `bak_pre_stage_runner:470–504`. Their `pipeline_complete` field is derived from `bool(self.execution.completed_at)`, not a verified completion phase. | Active executor `:687–731` uses temp file and atomic replacement and derives completion from phase, though its fixed `.tmp`, error suppression and owner verification remain CB-C03/BV-C06. | Interrupt write and run two writers; assert last valid checkpoint survives and a failed run cannot be projected complete. |
| CC-H03 / approval lifecycle | P1 | All four archived approval waits use a fixed 3,600-second polling loop and return `True` in noninteractive mode after creating a request (`bak_pre_agent_exec:573–623`, `bak_pre_agent_runner:571–621`, `bak_pre_llm_extract:539–589`, `bak_pre_stage_runner:572–622`). Requests are stage/agent-keyed and not validated against a current-run decision at consumption. | Active executor `:1033–1179` adds structured decisions and configurable timeout policies, but has the separately documented P0 human-proxy decision overwrite (BV-C01) and stale approval identity risk (CB-C02). | Reject/changes/abort/timeout, stale-run decision and noninteractive pending-request tests; require explicit policy before auto-approval. |
| CC-H04 / authorization inheritance | P1 | `bak_pre_agent_runner:1657–1674` returns no schemas for a missing spec but its direct `execute_agent_tool` denies unauthorized tools only **if spec exists**. | The same missing-spec authorization condition persists in active `core/orchestrator/agent_runner.py:1480–1507` (BV-C02). This is one inherited issue, not a new finding. | Unknown-agent direct tool execution must fail for read and write-capable tools. |
| CC-H05 / forced-convergence semantic drift | P1 | `bak_pre_stage_runner:1490–1503` marks a stage `completed` with `{"skipped":true,"reason":"forced_convergence"}` when convergence requests skip; its outer loop counts completed DAG stages. | Stage-runner extraction and active DAG status semantics need cross-file regression coverage; do not assume a historical skip-as-completed policy is still active. | Simulate forced-convergence skip and assert final release requires all mandatory stages and verification evidence. |

## CC-3. Snapshot-by-snapshot comparative interpretation

**Pre-agent-exec (1,555 lines).** Already imports both extracted runner and stage mixins but still defines in-class `execute_agent`, making this a transition snapshot rather than a clean architectural reference. Its checkpoint uses direct overwrite and its pipeline loop conflates timeout with completion. Keep it for regression provenance only, not as a restore target without applying current fixes.

**Pre-agent-runner (2,416 lines).** Includes monolithic agent generation, tool dispatch and stage execution. The direct tool-execution method has the same missing-spec allowlist bypass as the active extracted runner; extraction did not introduce or eliminate that vulnerability. Historical timeout and checkpoint issues match the other snapshots.

**Pre-LLM-extract (3,491 lines).** Retains the largest in-class generation and LLM-related implementation. Historical timeout, finalization and direct checkpoint writes are confirmed at the cited line ranges. Its additional in-class LLM functionality should not be assumed equivalent to the extracted current `llm_client` without an exhaustive semantic diff; prior PF-516–PF-521 findings against current LLM paths remain authoritative.

**Pre-stage-runner (1,848 lines).** Imports the agent-runner mixin while retaining in-class stage execution. The inspected forced-convergence skip path records a skipped stage as DAG-completed. Its timeout and checkpoint behavior match the earlier snapshots. Compare skip semantics against active `core/orchestrator/stage_runner.py` before using this archive as a reference implementation.

## CC-4. Deduplication, release risks and recommended work order

The archived snapshots **do not add four new copies** of the same timeout, checkpoint, approval or tool-auth issue. They provide dated code-line regression evidence and extraction lineage. The active issues requiring remediation remain those already registered in the cumulative report: PF-060 (completion before/without enforcing the quality gate), PF-069 (unknown selected-stage IDs), PF-036 (test-directory existence masquerading as test execution), PF-001/BV-C01 (human-proxy approval fail-open), BV-C02 (unknown agent tool authorization), CB-C01 (stale checkpoint artifact rehydration), CB-C02 (approval identity), and CB-C03 (checkpoint ownership/persistence). Historical issues should be regression tests, not separately prioritized live vulnerabilities absent proof the backup is executed.

**Recommended order:** (1) fail-closed approvals and tool authorization; (2) run-bound verification evidence and quality gate before COMPLETION; (3) transactional state/approval/artifact persistence and run-lock fencing; (4) regression tests using the historical timeout/skip cases; (5) packaging hygiene to exclude archival snapshots from distributable artifacts and prevent accidental restoration.

## CC-5. Final 394-file scoped audit ledger

| Checkpoint | Static-semantic-reviewed scoped files | Pending scoped files |
|---|---:|---:|
| Original BT checkpoint | 384 | 10 |
| BY documentation review | 385 | 9 |
| CA backlog and compliance | 387 | 7 |
| CB three active execution files | 390 | 4 |
| **CC four historical snapshots** | **394** | **0** |

**Scope closure:** All **394/394 selected paths** have now received the project’s established **static semantic source-review treatment**; the four historical snapshots were fully retrieved and their structure and high-risk paths compared. This is **not** a claim that every line/branch was individually tested or that every possible inter-file interaction was proved. The original Git tree had **3,026 tracked files**, so this closure applies only to the previously agreed **394-file scoped inventory**, not the entire repository. Legacy dashboard is excluded. **No runtime, integration, concurrency, build or packaging tests were executed; no repository code was modified.** The cumulative permanent finding register PF-001–PF-521 remains intact and candidate findings retain their existing cross-references pending formal register triage.

### Pinned source references

- [Pre-agent-exec backup](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/pipeline_executor.py.bak_pre_agent_exec)
- [Pre-agent-runner backup](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/pipeline_executor.py.bak_pre_agent_runner)
- [Pre-LLM-extract backup](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/pipeline_executor.py.bak_pre_llm_extract)
- [Pre-stage-runner backup](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/pipeline_executor.py.bak_pre_stage_runner)
- [Active pipeline executor](https://github.com/srinikc/productforge/blob/e7a0dd57e01b3c81c1c26ce7ae70ff1b018d4374/product-forge/core/pipeline_executor.py)
