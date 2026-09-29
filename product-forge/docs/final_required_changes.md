# Product Forge — Final Required Changes (consolidated)

> **Sources reconciled:** `Product_Forge_Audit_Organized_Executive_Master_With_Execution_Guardrails_20260929.md`
> (register PF-001–PF-521 + candidate batches A–CC), `todo_sept292026.md`, `pipeline_current_issues.md`,
> `LOGS-AND-OBSERVABILITY.md`.
> **Method:** dedupe by root cause; map each audit workstream to an action; mark what is already covered.
> **Status of audit:** static semantic review of a **394-file scoped subset** at commit `e7a0dd5` (our current
> `develop`); **no runtime tests**. Findings are risk scenarios, not proven incidents. Legacy dashboard excluded.
> **Verified in code (spot-check):** BV-C01 (proxy decision computed then `return _ok`) and PF-060 (quality gate
> runs after `PipelinePhase.COMPLETION`, result ignored) — both confirmed.

---

## 0. Reconciliation — audit vs our existing docs

| Topic | Our doc | Audit refs | Verdict |
|---|---|---|---|
| Cost/latency over-generation; many serial calls; HIL hidden cost | `pipeline_current_issues.md` §1–4 | **PF-008**, PF-067, BV-C01 | **Audit extends** ours (adds fail-open + accounting) |
| Run-status vs state disagreement; stale status | `pipeline_current_issues.md` §7 | **PF-007, PF-020, PF-228** | Audit confirms + deeper cause |
| Logs/events scattered, two streams, no SSOT | `LOGS-AND-OBSERVABILITY.md` (+ BI-PF-0233/34/35) | **PF-224, PF-149, PF-200, PF-228** | Audit corroborates; our backlog already tracks |
| Verbose/prompt/tool logging | `LOGS-AND-OBSERVABILITY.md` App. D, BI-0229 | **PF-067, PF-149** | Aligned |
| Industry-standard observability blueprint (OTel, trace context, structured logging, event sourcing/CQRS, SLIs, 12-factor, trace UI) | `LOGS-AND-OBSERVABILITY.md` **App. D** | PF-149, PF-224, PF-228 | Mapped to **F1.0** |
| Backlog hygiene (dup/reciprocity/tier drift) | `pipeline_current_issues.md` §8 | PF-025, BU-C01–C05 | Audit extends to **transactional integrity** (P0/P1) |
| Non-backlog hygiene (artifacts tracked, config paths, encoding) | `todo_sept292026.md` §C | PF-174/175/189/195 (scripts exit 0) | Aligned; add script exit-code fixes |

**Conclusion:** our three docs cover the **cost, latency, observability and hygiene** layer (M1/M2). The audit's
**unique, mandatory contribution is the execution-integrity layer (M0)**: approvals, verification/completion truth,
authorization, run-bound provenance, and transactional state. Both must be done; M0 gates autonomy.

---

## 1. F0 — MANDATORY (block unattended execution until done + tested)

### F0.1 Fail-closed approvals & human/proxy decisions
- **BV-C01 (P0, verified):** `_wait_for_approval_ex` discards the proxy decision and returns approved → propagate/validate the real decision; reject/timeout/malformed/`changes` must never approve.
- **PF-001 (P0):** `human_proxy` returns `approve` on parse error/exception → fail closed.
- **PF-151 (P1):** PR-gate approval can be asserted without an authenticated HIL proof → require signed HIL proof bound to run+artifact.
- **PF-140/PF-178 (P1):** production-deploy / post-production grant `run_command` with no machine-readable approval/rollback → enforce approval at the deployment tool boundary.
- Acceptance: reject / timeout / malformed / error / stale-run decision all block; approval bound to principal+run+digest.

### F0.2 Truthful verification & completion
- **PF-060 (P0, verified):** quality gate runs **after** COMPLETION and its result is ignored → run gate **before** completion, persist FAILED on rejection, return false.
- **PF-036 / BU-C07 / BZ-C04 (P0/P1):** `tests_pass` passes on directory existence; compliance conforms with **zero** executed checks → require positive, executed, current-run evidence; UNKNOWN/SKIPPED ≠ PASS.
- **PF-039 (P1):** empty verification report `all([])` == passed → require ≥1 applicable executed check.
- **PF-069 (P1):** unknown selected-stage IDs filtered by `all(...)` → validate selected IDs against DAG; reject unknown-only scope.
- **PF-157/PF-158 (P1):** GO/NO-GO green when policy unavailable; QIR security score floored → fail closed; no unconditional-green rows.
- **PF-145 (P1):** code quality gate passes with 0 scanned files → require scanned_files>0 when code expected.
- **PF-171/PF-172/PF-142/PF-138/PF-195 (P1):** audit/verify/E2E/migration scripts print but exit 0 → return nonzero on failure.
- Acceptance: absent/skipped/unknown tests, failed gate, unknown stage never yield success/exit 0.

### F0.3 Run-bound artifact provenance & resume
- **PF-006 / PF-031 / BU-C06 (P0/P1):** close-loop/compliance accept any stage markdown / latest report / substring log → bind to run ID + stage + artifact hash.
- **CB-C01 (P1):** resume rehydrates completed stages from any `*-output.md` without run/hash → per-agent artifact manifest in checkpoint; reject stale on resume.
- **CB-C02 (P1):** approval file keyed only by stage+agent, overwritten → run-scoped path + optimistic versioning.
- Acceptance: prior-run artifact/report/approval is rejected; resume is run-bound.

### F0.4 Transactional state, locks, queues
- **PF-025 / BU-C02 / BZ-C01 / BZ-C02 (P1):** backlog proceeds after lock timeout; multi-file add/update non-atomic; interrupted migration hides legacy items → exclusive verified lock, unique temp + journal, migration manifest, fail closed.
- **PF-024 / PF-054 / BV-C06 (P1):** lock via rename (not CAS); run-lock checks existence not ownership → `O_CREAT|O_EXCL`/DB lease with fencing token; verify owner run ID.
- **PF-011–PF-016 (P1):** budget/queue/tenancy/model-catalog non-atomic writes → single atomic mutation; SQLite/transactional authority.
- **PF-026 / BV-C05 (P1):** artifacts overwritten in place, version hard-coded → immutable revisions + atomic write.
- **PF-032/PF-033/PF-034 / PF-228 / PF-224 (P1):** audit log, caches, checkpoint, run-status, log_router non-atomic/suppressed → atomic writes; fail visible.
- Acceptance: fault injection at each write preserves state; no lost updates; no duplicate IDs.

### F0.5 Authorization at the tool/API boundary
- **PF-004 / BV-C02 (P0/P1):** text tool loop / `execute_agent_tool` authorize only if an agent spec exists → missing spec must **deny**; enforce allowlist for both loops.
- **PF-125 / PF-123/124 (P1):** no registry-level HIL/approval; tool policy/registry gaps → enforce at registry execution.
- **PF-021 / PF-022 / PF-023 / PF-027 / PF-117/118 (P0/P1):** `operator_guard` doesn't authenticate; tenant routes use shared token only; SSE public; WebSocket unauthenticated → authenticated principal + tenant/project authorization; fail closed when token unset.
- **PF-227 / BU-C01 / BW-C06 (P1):** product/backlog path joins without containment → reject traversal/absolute; resolve under allowed root.
- Acceptance: anonymous/spoofed-role/cross-tenant/missing-spec/disallowed-tool all rejected before side effects.

### F0.6 Budget / model / delegation limits
- **PF-008 (P1):** default `PIPELINE_MIN_TOTAL_TOKENS=200000` ceiling; HIL unbounded → tier/task caps incl. HIL proxy.
- **PF-013 / PF-011 / PF-102/103 / PF-183 (P1):** `can_spend` not reserved; lock timeout continues → atomic reserve/reconcile; fail closed.
- **PF-017 / PF-154 / PF-179 (P1/P2):** UNKNOWN model fit not blocked; substitution ignores destination requirements; 110 catalog records missing context/tools → gate high-risk capabilities on verified fit.
- **PF-019 / PF-038 / PF-194 / PF-204 (P1/P2):** context/input budget checks incomplete → validate instructions+context+tool-schema+output-reserve at the model-call boundary.
- **PF-067 (P2):** tool-loop accounting overwrites per-attempt stats; fallback not cumulated → aggregate all attempts.
- **PF-147 / PF-155 (P1/P2):** delegation budget not enforced; TypeError fallback can invoke twice → enforce budget+resolved target atomically; no duplicate side effects.
- Acceptance: parallel last-budget race → one reservation; caps enforced; full usage aggregated.

### F0.7 Execution contract + acceptance suite (the real gate)
- Implement the audit's **immutable per-task contract** (identity/provenance · work scope · permissions · limits · verification · recovery); missing/unknown/unverifiable → BLOCKED/UNVERIFIED.
- Implement the **11-scenario "Minimum end-to-end acceptance suite"** and run it in **serial supervised → unattended → parallel** order before claiming readiness.
- Record per gate: test run ID, commit, environment, executed count, failures, artifacts.

---

## 2. F1 — Reliability & scaling (unlock the corresponding feature after F0)

### F1.0 Observability — industry-standard blueprint (`LOGS-AND-OBSERVABILITY.md` Appendix D)
- **OpenTelemetry** (traces/metrics/logs) + **GenAI semantic conventions** → one span per agent + per LLM/tool call; OTLP export. (`BI-0199` OTel; audit PF-149/PF-224)
- **W3C Trace Context** (`trace_id`/`span_id`, = run_id) on every record → no blank ids. (`BI-PF-0234`)
- **Structured JSONL logging**, one schema + levels → machine-queryable. (`BI-PF-0233`, PF-224)
- **Event sourcing + CQRS** → append-only event log is SSOT; state derived, not stored twice (kills the 5-file disagreement). (PF-007/020/228)
- **Three pillars + RED/USE + SLIs/SLOs** → per-stage duration/tokens/cost/retry; run-success + p95 SLOs. (`BI-0256`-adjacent; PF-108/067)
- **12-Factor** (logs as stdout event stream; env config; disposability).
- **Per-run trace UI pattern** (OpenLLMetry/Langfuse/Helicone/LangSmith) → run→agent→call tree with opt-in, redacted prompt/response. (`BI-0229`)
- **Idempotency + checkpoint/resume + DLQ + backpressure** (wire existing DLQ/circuit-breakers to the stream). (PF-063/134)
- **Retention/rotation/sampling/redaction** enforced in `log_router` (`keep_runs`, `max_bytes`). (PF-224)

### F1.1 Cost / latency / capability (from `pipeline_current_issues.md`)
- **Observability SSOT (our backlog):** **BI-PF-0233** (one writer/schema/tree/stream), **BI-PF-0234** (run_id everywhere + derive status), **BI-PF-0235** (logs query API) + **BI-0229** (verbose + prompt/tool capture). Audit refs: PF-224, PF-149, PF-200, PF-228, PF-067.
- **Cost/latency (`pipeline_current_issues.md`):** capability steering **BI-0221/0222/0223**, structured+render **BI-0224**, parallel sections **BI-0225**, context discipline **BI-0226**, fallback/escalate **BI-0227**; audit refs PF-008, PF-067, PF-017, PF-038/204.
- **Model selection & cost reporting:** PF-017, PF-154, PF-216, PF-218, PF-188, PF-100/PF-101; catalog metadata PF-179.
- **Recovery & resilience:** DLQ PF-063/PF-211/PF-226 (enum serialization), circuit-breaker PF-134, stop conditions PF-207/PF-209.
- **Concurrency beyond tested profile:** lock/queue/state fixes from F0.4 under parallel workers; PF-014/PF-018.
- **Intake integrity:** PF-028/112/113/114/115/116, PF-107/108/109, PF-129.

### F1.2 Remaining `pipeline_current_issues.md` items (explicit)
- **`tool_calls: 0` all run** (tool loop never exercised) → PF-004, BV-C02, PF-125; verify the native tool path on `kctier`.
- **HIL hidden cost** (42 calls / 450k prompt tokens, invisible per-agent) → PF-008, BV-C01 + `BI-0229`/`BI-PF-0234` surface it.
- **Model registry drift** (`free-trial-fast` 3 ids + 1 live mismatch) and **110 catalog records missing context/tools** → PF-179, refresh registry.
- **OpenCode Zen free tier not API-usable (403)** → provider fallback policy (`kctier`/opencode-go) is config, document + guard.
- **Dashboard backlog = 146 open** vs backend 45 → dual-backlog reciprocity (Dashboard `BI-*`), keep backend-first.
- **Windows cp1252 crash** in `core.backlog --similar` → `todo_sept292026.md` §C.

## 3. F2 — Maintainability, docs & hygiene (after first reliable milestone)

- **Docs generator truth (BX/BY):** XML escaping (& already breaks shipped XML), canvas sizing, dead `pipeline-workflow.pdf`, DAG parity, atomic publish; index `--check` must exit nonzero (PF-174).
- **CLI correctness:** PF-161, BW-C01/C02/C05/C06, CB-C04/C05 (alphanumeric stages, exit codes, no derived-state mutation).
- **Packaging/archival hygiene:** exclude the four `.bak_pre_*` snapshots from distributable artifacts; PF-094/PF-096/PF-135/PF-175 (tooling writes/reads).
- **Agent-card contract consistency:** PF-130/131/143/168/169/170/176/177/190/196/203/205 (declared tools vs instructions; permission conflicts; model pins vs tier).
- **Generated-script exit codes:** PF-138/142/171/172/195 (scripts that print but never fail).
- **Register/hygiene:** formal candidate→PF triage (dedupe BV/BW/BX/BY/BZ/CB/CC), evidence-level labels, and our `todo_sept292026.md` §C items (untrack run artifacts, fix config log paths, cp1252 encoding bug, auto-refresh docs, backlog hygiene).

---

## 4. Coverage matrix — every audit area maps to a final action

| Audit area / batches | Anchor findings | Lands in |
|---|---|---|
| Executor, HIL, finalize (D, H, W, BU–CB) | BV-C01, PF-060, PF-069, PF-001 | F0.1, F0.2, F0.3 |
| Verification/compliance/QA (E, AA, AT, AX, BE) | PF-036, PF-039, BU-C07, PF-157/158 | F0.2 |
| Locks/queue/budget/state (B, G, K, BB) | PF-007/011–025, PF-102/103 | F0.4, F0.6 |
| Artifacts/provenance (C, D, L, BC) | PF-026, PF-006, CB-C01/C02 | F0.3 |
| API authz/tenancy (C, F, O) | PF-021/022/023/027, PF-117/118 | F0.5 |
| Tool policy/registry/agent specs (Q, AA, AB) | PF-004, BV-C02, PF-123/124/125 | F0.5, F2 |
| Model routing/registry (BI, BJ, BM) | PF-017, PF-154, PF-179 | F0.6, F1 |
| Intake/adapters (C, M, N, BF, BL) | PF-028, PF-107–116 | F1 |
| Backlog/persistence (C, BU, BZ, CA) | PF-025, BU-C01–C05 | F0.4, F1 |
| CLI (BW, CB) | BW-C01–C06, CB-C04/C05 | F0.2, F2 |
| Docs generator (BX, BY) | BX-C01–C04 | F2 |
| Security scanners/CI/deploy (K, O, AF) | PF-090–098, PF-160, PF-206, PF-225 | F0.6, F1, F2 |
| Licensing/billing/tenancy (L, AD) | PF-049, PF-099, PF-180, PF-191/192/193 | F0.5, F1 |
| Agent cards/prompts/config (Y–AB, AU) | PF-120/122/130/131/143/168–170/176–178 | F2 |
| Knowledge/memory/insights (BP, M) | PF-081, PF-148, PF-210, PF-222 | F1, F2 |
| Observability/logging (AY, BT, our docs) | PF-224, PF-149, PF-228 | F1 |
| Tests/tooling scripts (AF, Z, BA) | PF-138/142/171/172/195 | F0.2, F2 |
| Archival `.bak_pre_*` (CC) | CC-H01–H05 | F2 (regression tests + packaging) |

**Coverage statement:** every audit workstream (1–6), every M0/M1/M2 row, every cross-cutting family, and every
batch (A–CC) maps to an F0/F1/F2 action above. No audit area is left unassigned. Individual PF IDs nested under a
theme inherit that theme's action; candidate IDs (BV/BW/BX/BY/BZ/CB/CC) remain provisional until formal register triage.

---

## 5. Backlog mapping (what to create)

- **Epic: `M0 fail-closed execution`** with children:
  - `Approval truth` (BV-C01, PF-001, PF-151, PF-140/178) — **new** (builds on BI-PF-0234/0235 observability).
  - `Completion & verification truth` (PF-060, PF-036, PF-039, PF-069, PF-157/158) — **new** (BI-0184 quality gate relates).
  - `Run-bound provenance & resume` (PF-006, PF-031, CB-C01/C02) — **new**.
  - `Transactional state & locks` (PF-024/025/011–016/026/032–034, BU/BZ) — **new** (extends PF-025; relates BI-0179).
  - `API/tool authorization fail-closed` (PF-004/021/022/023/027, BV-C02) — **new**.
  - `Budget/model/delegation limits` (PF-008/013/017/019/038/067/147/154/155) — **new** (relates BI-0221–0223).
  - `Acceptance suite (11 scenarios) + contract` — **new**.
- **Existing backlog** covers the M1 layer: **BI-0221–BI-0230**, **BI-PF-0231/0232/0233/0234/0235**.
- **Our `todo_sept292026.md`** covers the M2/hygiene layer.

---

## 6. Final recommendation

1. **Freeze autonomy & multi-tenant exposure** until F0.1–F0.6 are implemented and the **acceptance suite** passes.
2. Do **F0 in this order:** (1) approval truth → (2) completion/verification truth → (3) run-bound provenance →
   (4) transactional state/locks → (5) authorization → (6) budget/model/delegation → (7) acceptance suite + contract.
3. Run **F1 (cost/latency + observability SSOT)** in parallel — it is already in the backlog
   (BI-0221–0230, BI-PF-0233/34/35).
4. Do **F2 hygiene** last (docs generator, CLI, packaging, agent-card consistency, generated-script exit codes).
5. **Register triage:** map candidate IDs → permanent PF IDs; label evidence level; keep the audit as the risk
   source of record.
6. **Operate human-supervised** with explicit audited overrides until F0's suite is green; never allow silent success.

---

## 7. Backlog coverage — what existing items already cover (and what does not)

Searched all backlog scopes (open + closed, 402 items). Verdict per change:

| Change (F0/F1/F2) | Existing backlog item(s) | Verdict |
|---|---|---|
| Fail-closed approvals (BV-C01, PF-001, PF-151) | `BI-0093` (closed, HIL decision model), `BI-0074` (closed, wait timeout) | **Gap** — the fail-open bug is untracked |
| API/tenant authorization (PF-021/022/023/027, PF-117/118) | `BI-0059` (closed, operator role), `BI-0041` (closed, RBAC), `BI-0057/0058` (closed, licensing) | **Gap** — endpoint authz not tracked |
| Tool authorization (PF-004, BV-C02, PF-123/124/125) | `BI-0221` (tools in capability vector), `BI-0200` (plugin/registry framework) | **Partial** |
| Completion truth / quality gate (PF-060) | `BI-0220` (epic), Dashboard `BI-0137` | **Partial** |
| Verification evidence (PF-036, PF-039, BU-C07, BZ-C04, PF-157/158) | — | **Gap** |
| Unknown selected-stage IDs (PF-069) | `BI-0220` (epic) | **Partial** |
| Run-bound provenance + resume (PF-006, PF-031, CB-C01/C02) | `BI-0219` (provenance/C2PA), `BI-0218` (versioning) | **Gap** (different concern) |
| Transactional state / locks / queues (PF-024/025, PF-011–016, PF-026, PF-032–034, BU/BZ) | `BI-0220` (epic); `BI-0007`, `BI-0179` (closed single-writer) | **Partial/Gap** |
| Budget/model/delegation limits (PF-008/013/017/019/038/067/147/154/155) | `BI-0221/0222/0223`; `BI-0192`, `BI-0210`; `BI-0207` (closed) | **Partial** |
| Observability / log SSOT (PF-224, PF-149, PF-200, PF-228, PF-007/020) | **`BI-PF-0233`, `BI-PF-0234`, `BI-PF-0235`, `BI-0229`**; `BI-0198` (AG-UI), `BI-0199` (OTel) | **Covered** |
| Cost / latency / capability steering | **`BI-0221`–`BI-0230`** | **Covered** |
| Docs generator / CLI (BX/BY, BW-C01/C02/C05/C06, PF-174) | — | **Gap** |
| Packaging / archival (`.bak_pre_*`) | — | **Gap** |
| Agent-card contract consistency (PF-130/131/143/168–170/176/177/190/196) | — | **Gap** |
| Generated-script exit codes (PF-138/142/171/172/195) | — | **Gap** |
| Intake / any-file (PF-028/112–116) | **`BI-PF-0232`**; `BI-0051/0052/0053`, `BI-0156` (closed) | **Covered / Partial** |
| Model routing / pins / tier (PF-154, PF-170, PF-179) | `BI-0192`, `BI-0193`, `BI-0210` | **Partial** |
| Security scanners / CI (PF-090–098) | `BI-0205` (PR workflow); `BI-0024` (closed) | **Partial** |
| Dashboard/UI surfaces | Dashboard backlog `BI-*` (146 open) | Out of active backend scope |

**Verdict:** roughly **one third** of the required changes are already backed by a backlog item — specifically
the M1 **observability/cost/intake** layer (`BI-0221–0230`, `BI-PF-0231/0232/0233/0234/0235`) plus some closed
reliability items. The **M0 execution-integrity core has no owning item** and must be added.

**Action:** expand **`BI-0220`** (EPIC: pipeline E2E reliability) into the **M0 epic**, or create a new epic
**"M0 — fail-closed execution"** with the seven children listed in §5. Add the F2 gaps (docs generator, CLI,
packaging, agent-card consistency, generated-script exit codes) as individual tech-debt items.
