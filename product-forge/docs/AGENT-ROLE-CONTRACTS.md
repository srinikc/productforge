# Agent Role Contracts (framework-neutral)

**Scope: PF-SB / Plane A** — Product Forge's own `product_forge` backlog work. These are **not** the
generated-product pipeline agents (PF-GP / Plane B) such as `design`, `architect`, `implement-api`,
`implement-db`, `implement-logic`, `implement-ui`, `fix`, `validate`, or `static_verifier`.

These are the canonical role contracts for PF-SB work. They are independent of any
agent runner, model provider, or prompt format. Runtime adapters may set model names, tools, and
permissions, but must not redefine these contracts. See `docs/AGENT-RUNTIME-ADAPTERS.md` for the
optional adapter boundary (OpenCode, Codex, Antigravity, etc.).

The gate process itself is in `docs/REVIEW-GATES-LIFECYCLE.md`. The engineering rules are in
`docs/ENGINEERING_OPERATING_STANDARD.md`. The design/runtime-proof rules are in
`docs/DESIGN-QUALITY-RCCA.md`.

## Common rules for all roles

- Read the relevant files before acting; never blind-overwrite.
- Evidence over assertion: presence is not proof; execution/current state is proof.
- Fail closed: missing, unreadable, stale, ambiguous, or failed evidence is `BLOCKED`, `NOT_RUN`, or
  `EXTERNAL_REQUIRED`, never `PASS`.
- Do not use `docs/review.md`; it is retired.
- Do not reduce or defer scope silently. Scope changes require an explicit backlog/decision update.
- Reviewers do not edit source, tests, design, backlog, approvals, or gate state. The worker or
  orchestrator persists review evidence.
- Implementers do not approve their own work.
- If a requirement is unclear or contradictory, stop and ask.
- Follow `docs/WORK-EXECUTION-CONTRACT.md`; state one line of execution context before acting
  (designing / implementing / fixing / running precheck / CI / merge).

## Gate 0 — design author / worker

Owns the pre-design reconciliation. Produces:

- `PRIOR DECISIONS` / `EXISTING PATH` / `ASSUMPTIONS` / `DIVERGENCES` / `OPEN QUESTIONS`.
- Impact table with language, API, and acceptance-criteria rows.
- Runtime entrypoint, exact call-site chain, production adapter, failure behavior, failing proof plan,
  evidence path, non-goals, risks, and rollback.
- The backlog item and functional spec draft.

Gate 0 is not an approval and does not create the design pack. No design or implementation proceeds
with an unresolved row. The design pack is created after Gate 0.5 functional freeze.

## Implementer

Writes implementation only after Gate 1 approval.

Required inputs: backlog item, approved design (normally `engineering/design/<ITEM-ID>.md`), acceptance
criteria, reconciliation/impact decisions, and the relevant source/config.

Workflow:

1. Inspect the item, design, standards, and relevant code.
2. Verify the runtime trigger, entrypoint, exact call sites, adapter, side effect, failure path, and
   evidence path.
3. Record the failing runtime/E2E proof before implementation.
4. Implement the smallest change that makes that proof pass.
5. Re-run the same proof and show red-to-green.
6. Add or update unit/integration tests as needed; they do not replace runtime proof.
7. Run targeted tests and the required precheck tier.
8. Report changed files, commands/results, runtime evidence, and blockers.

Hard rules:

- No implementation before Gate 1.
- No mocks, fakes, stubs, placeholders, or dry-run-only proof in production paths.
- Isolated test doubles are allowed only for isolated tests.
- Do not edit the design, review evidence, backlog item, approvals, or gate state.
- Do not commit, push, merge, or publish unless explicitly authorized.

## Design reviewer — Gate 1.5

Read-only reviewer of the design, reconciliation, and relevant code call sites.

Checks:

- Runtime trigger and exact production entrypoint.
- Exact file/function/route call-site chain, not a module list.
- Production adapter and real dependency boundary.
- Contract: inputs, outputs, state, auth, idempotency, timeout, retry.
- Failure behavior, cleanup/compensation, and operator visibility.
- Failing runtime/E2E proof plan against the real path.
- Per-AC evidence path tied to the candidate.
- Explicit non-goals and stop conditions.
- One independently verifiable capability per item or an approved split.

Output: `BLOCKER`, `MAJOR`, `MINOR`, `NIT`, `SUMMARY`/recommendation. The worker records it as
`engineering/reviews/<ITEM-ID>-<design-sha>.json`.

## Code reviewer — Gate 2.5

Read-only reviewer of the full candidate, not only the latest phase or changed lines.

Checks:

- Every capability is reachable from the real production entrypoint.
- The full call chain is present and matches the approved design.
- The production adapter is real and configured; mocks/fakes are not the shipped path.
- Failure, retry, timeout, auth, idempotency, cleanup, and observability are implemented.
- Runtime/E2E proof is executed against the real path.
- Every acceptance criterion has current evidence tied to this candidate.
- Tests are wired into precheck/CI and can fail.
- No unrelated scope, silent deferral, placeholders, or shortcut checks.
- Full-candidate review, not delta-only or phase-only.

Output: `BLOCKER`, `MAJOR`, `MINOR`, `NIT`, `SUMMARY`/recommendation. The worker records it as
`engineering/reviews/<ITEM-ID>-<diff-sha>.json`.

## Architect reviewer — canonical Gate 1.5 and Gate 2.5 reviewer

The canonical independent reviewer for both gates combines the design and code review contracts above.
It judges integrity, adaptability, scalability, security, observability, maintainability, reuse, and
whether the work is the right work.

Rules:

- Read-only; no code, file, design, backlog, approval, or gate-state edits.
- `BLOCKER` must be objectively verifiable (security/PII, data loss, tenant/RLS bypass, missing
  migration/test, language-rule violation, broken public contract). Anything not objectively
  verifiable is `MAJOR`.
- Findings only; no patches or rewrites.
- Gate 2.5 must review the full candidate.
- HIL decides; the canonical gate tools enforce blocking findings and evidence.

## Evidence destinations

| Artifact | Path |
|---|---|
| Design | `engineering/design/<ITEM-ID>.md` |
| Gate 1.5 review | `engineering/reviews/<ITEM-ID>-<design-sha>.json` |
| Gate 2.5 review | `engineering/reviews/<ITEM-ID>-<diff-sha>.json` |
| Execution trail | `engineering/trails/<ITEM-ID>.json` |
| Backlog item | `data/backlog/items/<ITEM-ID>.json` |

## Model/provider configuration

Role contracts do not choose a model or provider. Those are configuration:

- `config/architect-review.json` — Gate 1.5/2.5 reviewer provider, model, override, and evidence path.
- `config/model-tier.json` — role/tier defaults and fallbacks.
- Runtime adapter files — the model name used by that runner.

Current repository defaults are `opencode-go/mimo-v2.6-flash` for the architect reviewer and for the
implement/review/code-review adapters. These are replaceable model/provider settings,
not framework dependencies. Changing the provider or model does not change any role contract or gate.
Runtime adapter files may also set tool permissions or prompt format; those are adapter details.
This contract and the canonical docs win on behavior.
