# RCCA Closure Integrity — Design (BI-PF-0270)

## Goal
Close the last mile of `docs/RCCA_productForge.md`: make the **guidelines tell the truth**, make **G8
enforced (not aspirational)**, and **exercise/wire the learning-routing loop** (issue → RCCA → learning →
guideline) so recurrence prevention is provable, not stated.

## 360° — what's actually true today
| Concern | Now | Target | Owner |
|---|---|---|---|
| EOS §12 integration-map status labels | stale: "Gates as code = in progress", "Acceptance suite = to-do", "CI enforcement = to-do", "Compliance = partial" while `BI-PF-0236..0243`, `0243`, `0259` are **completed** and CI is green | labels match closed work | `docs/ENGINEERING_OPERATING_STANDARD.md` |
| G8 non-happy-path checks | `core/compliance_check.py` has **0** failure-mode / "must NOT happen" checks | add explicit failure-mode checks | `core/compliance_check.py` |
| Learning routing (EOS §13) | `issues.list_open/closed` = 0/0; `learnings.all_learnings()` = 0 — loop never exercised | one real end-to-end trace + regression test + wiring proof | `core/issues.py`, `core/learnings.py` |
| Recurrence proof | audit `acceptance suite` is the only recurring proof | a test asserting the RCCA→learning→guideline path | `test-framework/tests/pipeline/` |

**Blast radius / consumers:** `compliance_check` (checks consumers: close-loop, compliance CLI),
`issues`/`learnings` (API `/api/v1/issues*`, `human_proxy` recorder), EOS readers (agents + humans).
No new store, no new module, no new writer.

## Design decisions
- **G8 is a *check family*, not a new gate:** add named failure-mode checks to the existing
  `AGENT_CHECKLISTS`/compliance surface (e.g. `failure_modes`/"what must NOT happen" coverage),
  advisory-or-blocking consistent with the module's current severity model. No parallel writer.
- **Loop proof = a real (small) end-to-end trace, not a fixture-only test:** raise one genuine issue for
  this very item, record its RCCA with `generalized=True` + `guideline_ref` pointing at EOS G8, let
  `issues.set_rcca` route into `learnings.add` (merge rule ≥0.6), and assert:
  (a) issue closes with `can_close_ref=True`; (b) a learning exists referencing the guideline; (c)
  `learnings.render(area=...)` surfaces it; (d) the linked backlog item's close is **gated** until RCCA
  is complete (fail-closed proof).
- **No fabricated history:** the seeded issue is real and about this item; we do not backfill fake
  incidents to make counters non-zero.

## Plan (one branch `feature/bi-pf-0270-rcca-closure`)
1. `docs/ENGINEERING_OPERATING_STANDARD.md` §12 — correct the status labels to match `0236–0260`.
2. `core/compliance_check.py` — add G8 failure-mode coverage checks.
3. `core/issues.py`/`core/learnings.py` — confirm + (if needed) fix `set_rcca(generalized=True)` →
   `learnings.add` routing and the `can_close_ref` gate. Only touch if 360° proves a break.
4. Test `test_rcca_learning_loop.py` — the end-to-end loop + fail-closed close gate.
5. Seed the real issue/RCCA for this item (proof, non-fabricated).
6. Gates: `compileall`, `wired_audit`, `workflow_matrix_check`, pipeline tests, `precheck`.
7. Merge; close `BI-PF-0270` under the RCCA gate.

## Acceptance
- EOS §12 labels match backlog reality (no "in progress"/"to-do" for completed work).
- `compliance_check` exposes ≥1 explicit failure-mode check.
- `test_rcca_learning_loop.py` green; proves issue→RCCA→learning→guideline and the fail-closed close gate.
- `precheck` PASS; no new store/module/writer introduced.

## Out of scope
New observability features; multimodal OTel (`BI-0199`); reparsing the whole audit register.
