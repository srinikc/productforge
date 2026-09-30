# Evidence-Gated Learning Pipeline — Design (BI-PF-0293 / 0294 / 0295)

## Goal
Add **evidence-gated, approval-based** adaptation — never auto-injection, never self-rewriting prompts.
Approved additions are appended as **additional data points** (bounded), scoped and **selected on need**,
and applied only after explicit approval. Text and multimodal share **one** learning layer.

## Principle (binding)
- **Execution contract = STATIC** (agent cards/roles/guards/base prompts) — never auto-mutated.
- **Adaptation = DYNAMIC but gated**: (a) *selection* (which knowledge/model/context/assets apply),
  (b) *candidates* distilled from outcomes → approved → applied through the owning module.
- One writer per store; API-first (reads via API, writes via owner modules); reversible + audited.

## 360° — verified current state
| Concern | Now | Target | Owner |
|---|---|---|---|
| Learnings | `data/learnings.json` GLOBAL; injected into every agent every run (`agent_runner.py:1330`) | scoped (project/area) + need-based | `core/learnings.py` |
| Who writes learnings | only `issues.set_rcca(generalized=True)` (`issues.py:423`) — manual | `learning_synth` proposes; approval applies | new `core/learning_synth.py` |
| Overlays | `prompt_overlays` (project/global) | candidate → approved overlay | reuse |
| Knowledge/skill | `knowledge_registry`, `skills_registry` (static/seed) | operator-gated registration from candidates | reuse |
| Memory | written (`agent_execution`), **never read** | bounded read-back (opt-in) | `agent_memory` + `agent_runner` |
| Evidence sources | issues/RCCA, review_ledger, defect_loop, **media_qa (BI-0191)**, quality/QIR | collect at teardown | reuse |
| API | `/api/v1/issues*` exists | + `/api/v1/learning/candidates*` | `dashboard/api` |

## E2E workflow
```
[teardown]      [collect]        [cluster+score]     [propose]            [review/approve]     [apply→owner store]      [inject need-based]   [measure]
RCCA/QA/review ─► learning_synth ─► dedupe(≥0.6)+conf ─► candidate ──────► HIL/API approve ───► learnings.add(scoped) ─► bounded render ─────► effectiveness
defects/quality ── evidence[] ──── evidence[]         data/learning-       reject/edit         prompt_overlays.set()   project/area filter    next-run delta
                                                      candidates.json                          knowledge/skill reg.    (no prompt rewrite)
```
- **Collect:** `learning_synth.collect(project_dir)` at run teardown (after quality/QIR) — evidence from
  closed RCCAs (`issues`), `review_ledger` feedback, `defect_loop` reconciles, **`media_qa` findings**,
  quality/QIR deltas.
- **Cluster+score:** reuse `learnings._sim ≥ 0.6`; attach `evidence[]`, `confidence` (frequency × severity
  × recurrence). **Fail-closed:** no evidence ⇒ no candidate.
- **Propose:** write `data/learning-candidates.json` (single writer `learning_synth`) — `{id, kind:
  learning|overlay|skill|knowledge, text, rationale, evidence[], confidence, scope, status:proposed}`.
  **Nothing enters a prompt here.**
- **Review:** HIL/API approve|reject|edit (authz at boundary, audited). Opt-in deterministic auto-approve
  only when `confidence ≥ threshold AND scope=area` (never blanket).
- **Apply:** promote into the **owner** store via its API (never direct write):
  `learnings.add` / `prompt_overlays.set_overlay` / `knowledge_registry.add` / `SkillsRegistry.add_skill`.
- **Inject (need-based):** `learnings.render(project=, area=)` (BI-PF-0294) at the existing injection site;
  overlays appended; memory read-back (opt-in, bounded). Static instructions untouched.
- **Measure:** tag applied candidates; compare next-run quality/defect/acceptance; regressions ⇒ flag revert.
  (Full learned-routing deferred — Doc 2 §21.)

## Scope & selection (your requirement)
- **Default scope = `project:<p>` or `area:<module>`**; **`global` only by deliberate promotion**
  (requires recurrence evidence across projects + a separate approval). So an approved item does **not**
  automatically apply to every project.
- **Need-based injection:** `render()` filters by project/area/agent; knowledge/skills already select by
  agent/tech-stack. Approved items are **static data once written**, chosen per run.

## API-first contract
- `GET  /api/v1/learning/candidates?scope=&status=` — list proposals + evidence
- `GET  /api/v1/learning/candidates/{id}` — candidate + evidence + confidence
- `POST /api/v1/learning/candidates/{id}/approve|reject` — the gate (records who/when)
- `POST /api/v1/learning/candidates/{id}/edit` — adjust text/scope before approval
- `GET  /api/v1/learning/effectiveness` — applied candidates + measured effect
- Reuse `/api/v1/issues*`, overlays, knowledge, skills. **Reads via API; writes via owner modules.**

## Plan (staged)
- **BI-PF-0293 (first):** `core/learning_synth.py` + `data/learning-candidates.json` + collect/score/propose
  + **API + HIL approval gate** + apply-into-owner-store. No auto-injection.
- **BI-PF-0294:** scoped learnings (project/area store + fallback) + need-based `render()` + memory read-back.
- **BI-PF-0295:** operator-gated knowledge/skill registration from candidates (+ live-guideline check).
- Later: measured routing/effectiveness loop.

## Acceptance (BI-PF-0293)
- Evidence sources collected; no evidence ⇒ no candidate; candidates carry evidence + confidence + scope.
- Approval (API/HIL) promotes into the owner store; rejection changes nothing; static instructions untouched.
- Default scope project/area; global requires explicit promotion. `precheck` PASS; new store registered.

## Out of scope
Self-improving prompts (rejected by design), RL routing (deferred), per-candidate A/B (later).
