# M0 Status & Audit Coverage

> Generated 2026-09-29. Supersedes the "where are we" question for the audit
> `Product_Forge_Audit_Organized_Executive_Master_With_Execution_Guardrails_20260929.md`,
> `final_required_changes.md`, and `LOGS-AND-OBSERVABILITY.md`.
> Gate status: `compileall` 0 · `wired_audit` 0 · `workflow_matrix_check` PASS · **510 tests pass**.

## 1. Where we are
- **M0 (fail-closed execution) is implemented, tested, and merged to `develop`** (merge commit `1a510e4`, pushed to `origin/develop`).
- Epic **`BI-PF-0236`** + children **`BI-PF-0237…0243`** (F0-1…F0-7) are **completed**.
- The **11-scenario acceptance suite** (`test_m0_acceptance.py`) passes; the **execution contract** is wired into `execute_agent`.
- Active work now on branch **`feature/m0-followups-f1-f2`**.
- The discipline is **in every agent** (prompt `discipline_guard` + knowledge `kb-engineering-principles`).
- **Latest deltas:** guard restored to the explicit **THINK → DESIGN → PLAN → 360 → PRODUCE** order (role-agnostic,
  applies to any deliverable, not code-only); EOS §0 keeps the original sentences + “Think before you do”;
  **F2 hygiene `BI-PF-0255/0256/0257` done**; **F1 started** — `BI-PF-0234` (terminal events carry `run_id`;
  `run-status` reconciles leftover `running` stages/agents on completion/failure).

## 2. Audit PF-xx coverage

**Covered by M0** (implemented + tested): PF-001, PF-004, PF-011, PF-014, PF-015, PF-016, PF-016, PF-021,
PF-023, PF-024, PF-025, PF-026, PF-031, PF-032, PF-033, PF-036, PF-039, PF-060, PF-067, PF-069, PF-145, PF-147,
PF-157, PF-158, PF-227, PF-017 (explicit UNKNOWN), BV-C01, BV-C02, BV-C05, BV-C08, CB-C01, CB-C02, BW-C01,
BU-C06, BU-C07, BZ-C04, BZ-C01 (legacy-merge).

**Partial** (control present; hardening remains): PF-006 (close-loop run-bound done; broader projection pending),
PF-007/PF-020/PF-228 (lifecycle events exist; unified log/event SSOT is F1), PF-013 (token reservation already
enforced via `budget_manager.request_tokens`; dollar `budget.reserve` added), PF-151 (proxy truth done; PR-gate HIL
proof pending), PF-003/PF-035 (readiness exists; credential fail-open hardening pending), BU-C02/BZ-C02 (per-file
atomic + legacy-merge done; full transaction journal + migration manifest pending).

**Pending** (grouped; tracked under backlog / F1 / F2):
- **DAG/state:** PF-002, PF-007/020, PF-018 (immutable attempt history), PF-041.
- **Models/budget:** PF-008 (HIL/token floors), PF-012/013 (dollar reservation wiring), PF-019/038/204 (context caps),
  PF-154 (substitution destination reqs), PF-155 (delegation double-invoke), PF-179 (catalog metadata).
- **Authorization/tenancy:** PF-022 (tenant-scoped principal), PF-027 (WebSocket auth), PF-049, PF-117/118, PF-123/124/125
  (registry HIL), PF-151 (PR-gate HIL proof).
- **API/intake:** PF-028, PF-107–116, PF-112–116, PF-159.
- **CI/security scanners:** PF-090–098, PF-160, PF-206, PF-225.
- **Docs/CLI/tooling:** BX-C01–C04, BW-C02/C03/C05/C06, CB-C04/C05, PF-161, PF-171–197.
- **Agent cards/config:** PF-119–122, PF-126, PF-130/131/143, PF-168–170, PF-176–178, PF-190/196/203/205.
- **Other modules:** PF-009, PF-010, PF-040, PF-042, PF-057, PF-080–089, PF-099–105, PF-148/149/150, PF-191–193,
  PF-206–224 (many), PF-229–521 (batches AF–CC).

> The register is large (PF-001–PF-521 + candidate batches). **M0 covered the execution-integrity core** (the
> mandatory set). The remaining findings are grouped above and tracked; formal register triage
> (**`BI-PF-0254`**) is needed to finalize per-ID disposition (duplicate / extends / new).

## 3. Section D — industry-standard blueprint (implemented?)

| Standard | Status | Where / backlog |
|---|---|---|
| OpenTelemetry + GenAI semconv | **not implemented** | `BI-0199`, `BI-PF-0244` (F1) |
| W3C trace context (`trace_id=run_id`) | **not implemented** | `BI-PF-0234` (F1) |
| Structured JSONL logging (one schema) | **not implemented** | `BI-PF-0233` (F1) |
| Event sourcing / CQRS | **partial** | run-manifest + lifecycle events exist; unified stream `BI-PF-0233/0260` |
| Three pillars + SLIs/SLOs | **not implemented** | `BI-PF-0244` (F1) |
| 12-Factor (stdout/config/disposability) | **partial** | env-driven config yes; stdout logger partial |
| Per-run trace UI (OpenLLMetry/Langfuse-like) | **not implemented** | `BI-0229`, F1 |
| Idempotency + checkpoint/resume + DLQ + backpressure | **partial** | checkpoint+hash resume (CB-C01) done; idempotent `ensure_item`; DLQ exists |
| Retention / rotation / redaction | **not implemented** | `BI-PF-0233` (F1) |

**Net:** Section D is mostly **F1 (not yet)**; M0 delivered the *execution* invariants, and the **discipline**
(§11 principles) is enforced in prompts/knowledge. F1 (`BI-PF-0244` + `BI-PF-0233/34/35` + `BI-0229`) is next.

## 4. Backlog still open
- **product_forge: 65 open** — F1 (`BI-0221–0230`, `BI-PF-0233/34/35`, `BI-PF-0244–0247`), F2
  (`BI-PF-0248–0254`), hygiene (`BI-PF-0255–0260`), plus the multi-modal/modular-core epics
  (`BI-0185–0214`), product page/BOM/ops (`BI-0215–0219`).
- **ProductForge-Dashboard: 146 open** (front-end, backend-first).
- **Test projects:** e2e-smoke 6, smoke-all 11, test-project 1.

## 5. Next (order)
1. **F1 observability SSOT** — `BI-PF-0233` (one writer/schema/tree/stream), `BI-PF-0234` (run_id everywhere + derive
   status), `BI-PF-0235` (logs query API), `BI-0229` (verbose/prompt/tool capture), `BI-PF-0244` (OTel/SLIs).
2. **F2 quick wins** — `BI-PF-0255` (untrack run artifacts), `BI-PF-0256` (config log paths), `BI-PF-0257` (cp1252),
   `BI-PF-0259` (CI gate), then docs generator/CLI (`BI-PF-0249/0250`).
3. **M0 follow-ups** — context caps (PF-019/038/204), tenant authz (PF-022), websocket (PF-027), registry HIL
   (PF-123-125), backlog transaction journal (BU-C02/BZ-C02), dollar reservation wiring (PF-013).
4. **`BI-PF-0254`** register triage (dedupe candidate IDs → permanent PF IDs, evidence labels).
