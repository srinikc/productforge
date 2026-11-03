# Work Execution Contract

Binding for every work item and every agent role. This is the compact operational contract; EOS is the
engineering standard, `REVIEW-GATES-LIFECYCLE.md` owns the gates, and `PF-DESIGN-DELIVERY-CONTRACT.md`
owns executable design requirements.

## 1. Intake and design

- Think before acting: problem → design → 360° impact → implement.
- Find/assign the correct epic; backlog context, AC, scope, non-goals and risks must be complete.
- Backlog writes are API-only (`backlog_write_guard`); never edit backlog storage directly.
- Produce the RECONCILIATION block:
  `PRIOR DECISIONS / EXISTING PATH / ASSUMPTIONS / DIVERGENCES / OPEN QUESTIONS`.
- No assumption is implemented unconfirmed; no divergence is silent; decisions are append-only; unknown
  facts are investigated, never extrapolated.
- Every design must cite AGENTS.md, EOS, the review lifecycle, and the design-quality RCCA.
- Every capability states: runtime entrypoint, exact call site/file/function, production adapter,
  contract/failure behavior, failing E2E test, evidence path, and non-goals.

## 2. Implementation

- Work on a feature branch, never directly on `develop`/`main`.
- Implement no shortcuts: real code, real adapter, real path, no placeholders/fakes as proof.
- API-first: decide whether an API is required; design and implement it; verify E2E and every AC.
- Add tests before merge/push; run them.
- Read and apply the relevant language/database/API/test guide selected by `config/coding-guidelines.json` before writing code.
- Reuse existing owners first; keep the surface minimal; delete unused code/imports/duplication.
- Scope to the change; unrelated debt becomes a backlog item.
- New shipped/sensitive logic is Go; Python is for tooling/tests/config/docs.

## 3. Decisions, issues, risks

- Highlight risks and mitigations before implementation.
- Issues require RCCA: issue → RCCA → backlog item → proper fix, not a shortcut.
- If new functionality is needed, design it and ask for approval with details.
- Decision-ready summary required: epic #, backlog #, title, change, why, language check, API check,
  AC, impact table, risks/mitigations, and the exact approval requested.

## 4. Delivery

- Sync with develop often; merge, never rebase/reset.
- Run precheck/CI, full-candidate review, and the merge gate.
- Push/merge to `develop` only through the delivery lane.
- No OpenCode runtime dependency in product code; the dashboard is legacy and must not gain new references.
- Before acting, state one line of context: designing / implementing / fixing / running precheck / CI / merge.
- Tool discipline: read → edit exact block/write → shell only for tests/gates/git → show `git diff --stat`.

## 5. Review triage

- Freeze the exact candidate SHA before Gate 2.5.
- Review only the approved design, AC, and `review_scope`.
- BLOCKER/MAJOR/MINOR: fix; ACCEPTED/DEFERRED/SCOPE/REJECTED are not valid dispositions.
- NIT: fix or record an evidence-backed exception.
- OUT_OF_SCOPE/pre-existing: fix or invalidate with evidence; do not hide it behind SCOPE.
- False positive/stale: close with concrete code/test/evidence.
- One remediation pass maximum; delta reviews verify fixes and do not consume the full-review budget.

## 6. Gate order

Gate 0 reconciliation/contract → Gate 1.5 design review → Gate 1 HIL → implement red-first → Gate 2.5
full-candidate review → Gate 2 HIL → precheck/CI → merge → closure.
