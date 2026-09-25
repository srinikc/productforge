# E2E Pipeline Dashboard — Design (from scratch)

> One dashboard for the whole Product Forge lifecycle: **idea → design → build →
> test/QA → release → deploy → delivery**, unifying the current fragmented views
> (`pipeline_dashboard/*` and `test-framework/dashboard/*`, port 3011).

---

## 0. Goals & audience
- **HIL/owner**: answer "where is it, is it good, can we ship?" in one screen.
- **Operators**: start/stop/pause/resume, rerun, pick tier/target, approve/override.
- **Engineers/QA**: drill into stages, agents, tests, defects, spec reviews, coverage.
- **End-customer/delivery**: a shareable, mostly-read **snapshot** for the final product report.

**North star:** one RAG summary (QIR + Go/No-Go) + one project selector + drill-down to evidence for every number.

---

## 1. Principles
1. **Evidence-linked**: every metric/status links to its artifact (file, cycle, defect, commit).
2. **Single source of truth**: read the pipeline/QA files + APIs; never duplicate state in the UI.
3. **Zero-trust to the UI**: the backend computes status (RAG/QIR/Go-No-Go); the UI only renders.
4. **Works offline**: static snapshot export for delivery (no server).
5. **Same data everywhere**: console, snapshot, delivery report, and CI all read identical APIs.

---

## 2. Information architecture (pages)
| Page | Shows | Primary source |
|---|---|---|
| **Overview** | project selector, RAG, **QIR number+band+trend**, **Go/No-Go**, current stage, progress, open defects, next action | `quality/status`, `qir`, `go-no-go` |
| **Pipeline** | DAG of stages `0→12` (live status/color), timings, dependencies, gate badges (`3a`,`10a`) | `pipeline-state.json`, `agents-live.json` |
| **Agents** | cards (name, model, status, tokens, time) → detail: prompt, tools, inputs, artifacts, compliance, timings | `agent-audit-log.json`, `stage_execution` |
| **Builds & Releases** | version + build#, changelog, RC/release tags, artifacts + md5/sha256 + signature | `build-info.json`, `builds/`, `docs/releases/` |
| **Check-ins & PR** | commit list (hash, PR#, author, brief), **PR merge checklist**, HIL override | `/api/checkins`, `/api/pr-gate` |
| **Tests** | suites (smoke/sanity/feature/nfr/packaging), cycles, **per-category executions**, pass/fail | `test-framework/results/*/cycles.json` |
| **Quality** | **QIR profile** (ISO 25010), **Go/No-Go matrix** (Spec Review + Verification coverage rows), coverage FR/NFR | `qir.json`, `go-no-go.json`, `nfr_coverage` |
| **Defects / RCCA / Insights** | open/resolved defects by severity & feature, RCCA prevention, AI insights with evidence | `defects/`, `insights.json` |
| **Spec Reviews** | per-artifact findings (blocking/optional), resolution status, HIL waivers | `spec-review.json`, `docs/qa/reviews/*` |
| **Traceability** | FR/NFR → tests → status (matrix) | `TestReporter.get_traceability_matrix` |
| **Targets & Sizing** | recommended targets (delivery surface + substrate), **footprint** (CPU/RAM/DISK/GPU per env), deploy status | `targets.json`, `sizing.json`, `deploy/` |
| **Delivery** | final report, artifacts index (`qa-manifest`), static snapshot link | `final-report.json`, `qa-manifest.json` |
| **Control** | run/pause/stop/resume, rerun (agent/stage/from), tier pick, target pick, HIL approve/override | `control.json`, tier API |
| **Budget & Cost** | tokens/cost per stage/agent, alerts, conservation mode | `budget-tracking.json`, `cost_kpi` |
| **Compliance (existing)** | rule/knowledge/gate/stack results | `compliance/` |
| **Logs (existing)** | pipeline logs/journal | journal/logs APIs |
| **Settings** | auth, tiers, integrations, target catalog, weights | config files |

---

## 3. Data & API contract (unified)
Reuse/extend a single read API surface (project-scoped via `?project=`):
```
GET /api/projects
GET /api/quality/status        → { rag, qir, decision, spec_review, insights, top_risks }
GET /api/pipeline/status       → stages[], current, live agents
GET /api/qir | /api/gonogo
GET /api/builds | /api/release-notes
GET /api/checkins | /api/pr-gate
GET /api/cycles | /api/suites | /api/executions/<cycle>
GET /api/metrics | /api/trends | /api/features
GET /api/defects | /api/rcca | /api/insights
GET /api/spec-review | /api/traceability | /api/coverage/cycle/<id>
GET /api/targets | /api/sizing
GET /api/delivery-report
POST /api/control {start|stop|pause|resume|rerun|tier|target|approve|override}
GET /api/logs?tail= | /api/journal
```
**Rule:** every page = 1–3 endpoints; endpoints never expose secrets; unknown project → 404.

---

## 4. Real-time & refresh
- **Default: polling** (2–5s) on the active page + a 30s global refresh (simple, robust).
- **Optional SSE** `/api/stream` for stage/agent live status (stdlib-friendly) — v1 can poll `agents-live.json`.
- **Live badges**: current stage, running agents, open defects, RAG.

---

## 5. Tech stack & architecture (decision needed)
| Option | Pros | Cons |
|---|---|---|
| **A. Consolidate on stdlib** (extend test-framework console; vanilla JS + Chart.js CDN) | zero-dep, easy to ship, already 14 tabs | less “app-like” |
| **B. Consolidate on `pipeline_dashboard` stack** (custom HTML/JS + modular API) | richer UI, many tabs already | two code paths today |
| **C. New SPA (React/Vite) + thin JSON API** | best UX, real-time, components | adds build/deps |

**Recommendation:** **A** for the shared backbone (stdlib server + vanilla JS), and *if* richer UX is needed later, layer C on top of the **same JSON APIs** (API-first, so the UI is swappable). The test-framework console becomes the single QA/quality+dashboard app; `pipeline_dashboard` folds in or proxies the same endpoints.

**Server**: one process, `http.server` (stdlib), serves `index.html` + `/api/*`; optional auth token.

---

## 6. Auth & multi-project
- **Project selector** in the header (from `/api/projects`) + `?project=` deep links.
- **Auth**: token/session (reuse test-framework `auth.py`) or none on localhost; bind to `127.0.0.1` by default.
- **Delivery URL**: `http://<host>:3011/?project=<p>` recorded into the final report + `qa-manifest`.

---

## 7. Delivery snapshot (offline)
- "Export snapshot" → self-contained `test-framework/reports/<project>/index.html` (embeds the JSON; no server).
- Linked from the **Delivery** page and the pipeline’s final report.

---

## 8. Non-functional
- **Perf**: page loads from cached JSON; large lists paginated/virtualized; snapshot < 2 MB.
- **Security**: no secret values; token auth optional; CORS localhost-only by default.
- **Reliability**: UI never blocks the pipeline; read-only except Control (which writes `control.json`).
- **Traceability**: every number links to its artifact path.

---

## 9. Build plan (phases) — from scratch
1. **P1 Backbone**: single stdlib server, project selector, `/api/quality/status` + Overview page (RAG/QIR/Go-No-Go).
2. **P2 Pipeline & Agents**: DAG live view, agent cards + detail (timings/tokens/artifacts).
3. **P3 Quality**: QIR profile, Go/No-Go matrix, Spec Reviews, Traceability, Coverage.
4. **P4 Tests & Defects**: cycles/suites/executions, defects/RCCA, insights.
5. **P5 Builds/Check-ins/PR**: builds+release notes, commit list, PR checklist + override.
6. **P6 Targets/Sizing + Control**: recommended targets, footprint, run/pause/rerun/tier/target/approve.
7. **P7 Delivery & snapshot**: final report page + static export + record URL in delivery.
8. **P8 Fold in `pipeline_dashboard`** (Compliance/Budget/Logs/Settings) or proxy.

**Acceptance per phase**: page renders from live files; every metric drill-links to evidence; unknown/absent data shows `not_run` (never fake); snapshot exports.

---

## 10. Open decisions (need your call)
1. **Stack**: A (stdlib/vanilla, recommended) vs B (existing pipeline_dashboard) vs C (React SPA)?
2. **One app vs two**: fold `pipeline_dashboard` into the QA console, or keep two with shared APIs?
3. **Real-time**: polling only (recommended v1) vs SSE stream?
4. **Auth**: token (like today) vs none on localhost?
5. **v1 scope**: which pages first — Overview+Pipeline+Quality (recommended) vs full 18 pages?
