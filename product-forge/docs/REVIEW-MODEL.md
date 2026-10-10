# Review Model (Product Forge)

How Product Forge reviews work: **what reviews what, when, and what blocks**. Framework-agnostic.
(BI-PF-1070, EPIC BI-PF-1066.)

## TL;DR
Reviews run **per build iteration** (one implementation stage + its VQA; the iteration planner decides the
feature subset). Two layers:
- **LLM review** — the `code-review` agent, driven by the production-risk checklist in `docs/REVIEW-FOCUS.md`.
- **Non-LLM gates** — mechanical checks + the PR merge gate.
**Critical findings block**; the PR gate is **fail-closed**.

## 1. LLM review (per iteration)
| what | where |
|---|---|
| Code Review agent (Stage 5) | `agents/code-review.agent.json` |
| Production-risk checklist it reads | `docs/REVIEW-FOCUS.md` (from `config/review-focus.json`) |
| Output | `reports/code-review.md` (verdict: READY FOR VALIDATION / NEEDS FIXES) |
| Checks | business-logic correctness; security; injection (SQL/command/template); performance (N+1); unhandled edges; "what breaks in production"; contract/migration/config; failure modes; idempotency; observability; test adequacy; traceability |
**Always flags** auth / authorization / payments / data-deletion. **Ignores style** (lint owns it). **Critical ⇒ block.**

## 2. Non-LLM gates
| gate | scope | role |
|---|---|---|
| `spec_review` (stage 3a) | pre-implementation | reviews requirements/design/architecture/UX; **BLOCKING** findings stop implementation (E6: testable AC + concrete NFR targets + edge/error cases; E7: contracts/migration/trust-boundaries/data-model/license) |
| `review_static_check` | changed files | high-risk patterns (SQL string-concat, `eval`/`exec`, `shell=True`, `os.system`, `pickle`, `yaml.load`, `DELETE`) |
| `lint` (ruff) | changed files | style/static |
| `secret_scan` | changed files | no committed secrets |
| `dependency_catalog_check` | changed files | a new dependency must resolve in the tool catalog (`bundle_allowed`) |
| `api_governance` / `api_contract` | repo | committed OpenAPI in sync with the live app |
| `traceability_check` | project | requirement matrix implemented + tested (E8) |
| `security-audit` (agent) | release | scans/pen-tests; **BLOCKS release** on critical findings |

## 3. The PR merge gate (blocking, fail-closed)
`core/pr_gate.py` — every merge requires a PR whose checklist passes; **items that cannot be proven are
`unknown` and DO NOT pass**:
`code_review` (the LLM review approved) · `review_changes_done` · `db_tests` · `api_tests` · `unit_tests` ·
`lint` · `ui_e2e` · `app_boot` · `structure_contract`.
Override is **HIL-only** (`qa.override_merge`), recorded + audited.

## 4. Shift-left (catch earlier than review)
- **spec/design gate** (E6) and **architecture/contract gate** (E7) run **before** code.
- **Traceability** (E8) proves requirement → design → code → test.
- **`api_impact` + `consumer_impact`** (E9/BI-PF-1171): every item records an API/consumer decision (internal /
  UI-orchestrator / external / worker) — the API is built only when needed.

> **Legacy scope exclusion.** Scopes declared legacy in `config/pf-review-scope.json` (currently
> `project:ProductForge-Dashboard`) are excluded from the reciprocity / duplicates / api_impact advisory checks
> but retained in the backlog (never deleted). The backend↔dashboard reciprocity rule is **suspended** while
> `dashboard_reciprocity.active=false`; it re-activates when the new dashboard lands.

## 5. Flows
```
ideation → design → [spec/arch gate: E6/E7] → architect → implement (iteration)
   → code-review (LLM, REVIEW-FOCUS) → fix → validate (non-LLM gates) → document → package → devops
   └ per iteration; traceability populated (E8); PR gate blocks merge until review + gates pass
```
