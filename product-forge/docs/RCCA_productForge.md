# RCCA — Product Forge (why these gaps existed, and how to prevent recurrence)

> **Scope:** the issues documented in `pipeline_current_issues.md`, `LOGS-AND-OBSERVABILITY.md`,
> `todo_sept292026.md`, `final_required_changes.md`, and the audit
> `Product_Forge_Audit_Organized_Executive_Master_With_Execution_Guardrails_20260929.md`
> (PF-001–PF-521 / workstreams 1–6 / M0·M1·M2).
> **Date:** 2026-09-29 · **Baseline:** commit `e7a0dd5` (`develop`).
> **Status:** analysis + corrective/preventive actions; remediation tracked in `BI-PF-0236…BI-PF-0260`.

---

## 1. Method
Root-Cause Corrective Action (RCCA) per issue family: **symptom → immediate cause → root cause (5-Why) → corrective
action → preventive control**. Issue families come from the audit's cross-cutting table and our three docs. This is
an engineering/process RCCA, not a per-line defect log (the audit register holds line evidence).

---

## 2. Issue families and root cause (5-Why)

### RC-1 — Verification proves *existence*, not *execution* (false success)
- **Symptoms:** `tests_pass` passes on a test **directory** (PF-036); compliance `conformed=true` with **zero** checks (BU-C07/BZ-C04); empty verification `all([])==passed` (PF-039); close-loop accepts any stage markdown / `latest` report / substring log (PF-006/PF-031/BU-C06); quality gate runs **after** `COMPLETION` and is ignored (PF-060).
- **Why chain:** ① any evidence could produce PASS → ② gates check “a file/report/check exists” → ③ the system had no notion of *run-bound, executed* evidence → ④ early design treated artifacts as self-proving (build a doc ⇒ done) → ⑤ **Root:** no **evidence graph** (run→stage→attempt→artifact hash→executed test→approval) and no explicit “unknown/skipped ≠ pass” rule.

### RC-2 — Fail-open defaults to keep runs moving
- **Symptoms:** human-proxy returns `approve` on parse error/exception (PF-001); proxy decision **discarded** and `approved` returned unconditionally (BV-C01); credential-check exception ⇒ `has=True` (PF-003/PF-035); corrupt config ⇒ empty defaults that disable caps (PF-167/PF-193); budget lock timeout ⇒ continue (PF-011).
- **Why chain:** ① errors defaulted to “not blocking” → ② broad `try/except` + `return ok` to avoid aborts → ③ unattended execution valued “progress” over “correctness” → ④ resilience was implemented as “never stop” not “stop safely” → ⑤ **Root:** no **fail-closed-by-default** policy; no distinction between *unknown* and *pass*.

### RC-3 — One truth declared, many writers in practice (state integrity)
- **Symptoms:** backlog proceeds after lock timeout, multi-file add/update non-atomic, interrupted migration hides items (PF-025/BU-C02/BZ-C01/C02); locks via rename, run-lock checks existence not ownership (PF-024/PF-054/BV-C06); artifacts overwritten in place (PF-026/BV-C05); audit/cache/checkpoint/run-status non-atomic & suppressed (PF-032–034/PF-228); budget/queue/tenancy/catalog (PF-011–016).
- **Why chain:** ① components disagreed → ② each module wrote its own JSON with ad-hoc saves → ③ “one writer per file” was a **doc rule**, not an enforced mechanism → ④ features were added incrementally, each with a local store → ⑤ **Root:** no shared **atomic-write + exclusive-lock/fencing + transaction** primitives; derived state duplicated instead of projected.

### RC-4 — Authorization enforced in prompts, not at the boundary
- **Symptoms:** text tool loop / `execute_agent_tool` authorize only if an agent spec exists (PF-004/BV-C02); `operator_guard` doesn’t authenticate; tenant routes share one token; public SSE; unauth WebSocket (PF-021/022/023/027); no registry-level HIL/approval (PF-125); agent-card deny-vs-grant conflicts (PF-130/143).
- **Why chain:** ① unauthorized actions were possible → ② allowlists lived in **prompt text / manifests**, checked (if at all) in code paths with gaps → ③ the executor/tool-registry had no single ACL enforcement point → ④ agent specs were built to *guide* the model, not to *gate* execution → ⑤ **Root:** authorization treated as **policy/instruction** rather than a **runtime, deny-by-default control**; dashboard/tenancy added later without a principal model.

### RC-5 — Observability bolted on, no SSOT, no correlation IDs
- **Symptoms:** two event streams (`.orchestration` vs per-project); per-agent logs have no prompt/response; terminal `run_failed` with empty `run_id`; 5 overlapping status files; log_router/event_bus suppress errors (PF-149/PF-200/PF-224/PF-228).
- **Why chain:** ① failures were hard to trace and status disagreed → ② logs/events/status were added per-module at different times → ③ no canonical schema or correlation id → ④ observability was a **late add-on**, not designed with execution → ⑤ **Root:** no **single log/event SSOT** and no **trace context** (trace_id=run_id) propagated everywhere.

### RC-6 — Cost/model/context limits advisory, not enforced
- **Symptoms:** `PIPELINE_MIN_TOTAL_TOKENS=200000` ceiling; HIL proxy 42 calls/450k tokens invisible; no budget reservation (race) (PF-008/013/PF-067); UNKNOWN model fit not blocked (PF-017/PF-154); context can exceed per-category budget (PF-019/PF-038/PF-204).
- **Why chain:** ① spend/limits drifted and blew up → ② budgets were introduced for **reporting**, computed after the fact → ③ no reservation/atomic accounting at the call boundary → ④ multi-provider/model support arrived later → ⑤ **Root:** limits modeled as **telemetry**, not as **enforced, reserved, boundary-checked** controls.

### RC-7 — The meta-layer (tests/tooling/gates) was never verified
- **Symptoms:** `run_e2e`/`test_gates`/`verify_fixes`/`audit_dependencies`/`migrate_backlog` print but exit 0 (PF-138/142/171/172/195); `gen_docs_index --check` never fails (PF-174); no runtime/concurrency/security tests in the audit.
- **Why chain:** ① failures looked successful in CI → ② “test” scripts were written as **diagnostics** → ③ no assertion/exit-code contract → ④ velocity prioritized features over test rigor → ⑤ **Root:** no **“a check must be able to fail” + CI gate** standard for the tooling layer itself.

### RC-8 — Scope & artifact hygiene (legacy, backups, generated docs, cards)
- **Symptoms:** four `.bak_pre_*` snapshots reachable/not excluded; docs generator writes hardcoded data, unescaped XML, dead PDF link, ignores `products_dir` (BX/BY); agent cards inconsistent; run artifacts committed.
- **Why chain:** ① generated/legacy outputs drifted from truth → ② docs/backups kept for convenience without ownership → ③ generators derived from **hardcoded** lists, not the DAG/registry → ④ no packaging exclusion policy → ⑤ **Root:** no **generated-artifact provenance + packaging** discipline.

---

## 3. Cross-cutting root cause (the single sentence)
**Product Forge was optimised for “the pipeline completes,” not for “the pipeline completes *truthfully, safely, and observably*.”**
Gates, budgets, authorization and logs were implemented as **advisory/reporting layers** and often **fail-open**,
while state was written by many local writers. As autonomy, multi-model and multi-tenant features were added, the
missing invariants (fail-closed, run-bound evidence, atomic single-writer, boundary enforcement, trace context)
became product risks rather than cosmetics.

---

## 4. Corrective actions (now / tracked)
- **BI-PF-0236** M0 epic — children **BI-PF-0237…0243** (approval truth ✅ started, completion/verification truth,
  run-bound provenance, transactional state, authorization, budget/model/delegation, acceptance suite).
- **BI-PF-0237** (approval truth) — **first fix landed this session:** `human_proxy` fails closed on parse
  error/exception; `_wait_for_approval_ex` propagates the real proxy decision (BV-C01). Remaining: PF-151,
  deploy/post-production approval contract.
- **BI-PF-0244** observability to industry standard; **BI-PF-0233/0234/0235**, **BI-0229** (log SSOT, run_id,
  query API, verbose).
- **BI-PF-0248** F2 epic — **BI-PF-0249…0254** (docs, CLI, packaging, agent cards, script exit codes, register triage).
- **BI-PF-0255…0260** hygiene (untrack artifacts, config log paths, cp1252, auto-refresh docs, CI gate, state
  consolidation).

---

## 5. Preventive guidelines going forward (the standards to adopt)

### G1 — Fail-closed by default
Unknown, missing, unreadable, timeout and exception ⇒ **BLOCKED / UNVERIFIED**, never PASS/approve. Ban
`except: pass` and default-`ok`/`approve` on gate paths. Add a lint/review rule for gate modules.

### G2 — Evidence graph, run-bound (no more “existence = done”)
Every artifact/test/approval carries `run_id · stage · agent · attempt_id · content_hash`. Verification consumes
**only current-run** evidence; a new run must invalidate/reject prior-run artifacts, reports and approvals.

### G3 — One writer, atomic, owner-bound (single source of truth)
All state through owner modules using **atomic temp+fsync+replace** and **`O_CREAT|O_EXCL` / DB lease with a
fencing token**; multi-file mutations are transactional (journal + rebuild); derived state is **projected**, never
written by hand. No CLI may mutate derived state.

### G4 — Enforce at the boundary, not in the prompt
Tool allowlists, agent-spec presence, HIL/approval, budget reservation, context/output caps and path containment
are checked in the **executor / tool-registry / API middleware** — deny-by-default. Prompts guide; code gates.

### G5 — Observability SSOT + correlation IDs
One structured JSONL schema, one event stream, `trace_id = run_id` on every record; OTel-style spans per
agent/LLM/tool call; SLIs/SLOs (success rate, p95 latency, tokens, cost, retries). Logs/config/state have canonical
paths; failures are visible (no silent suppression).

### G6 — “A check must be able to fail” + CI gate
Every gate/test is able to fail and returns nonzero on failure. CI runs `compileall` + `wired_audit` +
`workflow_matrix_check` **+ the new execution-integrity acceptance suite** (happy path, missing deliverable,
absent/skipped tests, human reject/timeout/malformed, tool-allowlist breach, repeated no-progress, budget race,
crash-after-write, stale prior-run artifact, mid-DAG budget/time, duplicate dispatch).

### G7 — Contract-first dispatch + bounded autonomy
Every dispatched task carries an immutable contract (identity/provenance, scope, permissions, limits, verification,
recovery). Missing/unknown tools/stages/approvals ⇒ BLOCKED. Cap attempts, tool calls, tokens, wall-clock and
no-progress cycles; escalate-on-failure; terminate only after **verified** acceptance.

### G8 — Design non-happy paths first
For every feature, specify and test the **failure modes** (“what must NOT happen”) alongside the success path.
Externally-exposed surface and parallel/multi-tenant execution require an authz + concurrency review **before**
enablement.

### G9 — Generated-artifact + packaging hygiene
Generated docs derive from the DAG/registry (never hardcoded); outputs are escaped/validated and published
atomically; backups/legacy snapshots are excluded from packages; nothing generated is hand-edited.

### G10 — Risk-register discipline
Maintain the backlog as the single register: group findings by root cause (not per mention), dedupe before adding,
label evidence level (static / conditional / runtime / fixed / regression-verified), and re-run the acceptance
suite on every M0 change.

---

## 6. Why this will not silently recur
The guidelines are **enforced, not aspirational**: G1/G3/G4/G5 are checked by code paths (fail-closed defaults,
atomic writers, boundary ACLs, SSOT logging); G6/G10 are checked by CI + the register; G7/G8 are checked by the
execution contract and the non-happy-path tests. The audit's acceptance suite is the recurring proof.
