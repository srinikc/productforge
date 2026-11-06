# Spec Chain (PF-SB)

Binding order for backlog items created on/after `2026-11-06`:

1. **Gate 0 — readiness**: item, reconciliation, impact table, language/API/AC decisions.
2. **Gate 0.5 — functional freeze**: `functional_spec` + `engineering/specs/<ID>.md`.
3. **Design / architect**: `design_pack` + `engineering/design/<ID>.md`.
4. **Conditional spec pack**: `spec_pack` + `engineering/specs/<ID>-spec-pack.md`.
5. **Conformance**: FR → design coverage → test → evidence.
6. **Gate 1.5 — design review**: functional spec + design pack + spec pack + conformance.
7. **Gate 1 — HIL approval**: freezes functional/design SHAs.
8. **Implement**.
9. **Gate 2.5 — delivery review**: diff against frozen functional/design + evidence.
10. **Gate 2 — HIL approval**.
11. **Precheck/CI → merge → closure**.

## Required artifacts

| Artifact | Owner | Required | Check |
|---|---|---|---|
| Functional spec | requirements/design author | Always | `functional_spec.py` |
| Design pack | architect/design author | Always | `design_pack.py` |
| Conditional spec pack | design author | Always (rows may be N/A) | `spec_pack.py` |
| Conformance matrix | design author | Always | `conformance_check.py` |
| Review evidence/dispositions | reviewer/worker | Gate 1.5/2.5 | review tools |

## Conditional specs

`config/spec-pack.json` is the source of truth. Every row is:

- `APPLICABLE` with owner, reason, artifact, sections, and existing evidence, or
- `N/A` with a concrete reason.

Required rows: product design, API, data, config, NFR/SLO, security threat model, migration/backfill, rollback/DR, observability/runbook, accessibility/i18n, privacy/compliance, implementation plan, release verification.

## Review charter

- **Gate 1.5** reviews only the functional spec, design pack, conditional applicability, conformance, and standards.
- **Gate 2.5** reviews only the diff against the approved functional/design contract, tests, evidence, and operations.
- New requirements/features are `OUT_OF_SCOPE` unless HIL changes scope.
- BLOCKER = violates AC/security/data loss; MAJOR = approved contract cannot be met; MINOR/NIT = hardening.
- One full review per frozen SHA; fixes use delta review; HIL decides after the agreed delta pass.

## No shortcuts

- No placeholders in enforced fields.
- `N/A` needs a reason.
- Every FR needs a design coverage row with tests + evidence.
- Functional/design/review evidence is bound to the frozen SHA.
