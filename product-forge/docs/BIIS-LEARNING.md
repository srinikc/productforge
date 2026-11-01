# BIIS and Review-Loop Learning

**Purpose:** capture the review-loop analysis, the disposable proof, and the BIIS template
analysis in one place.

---

## 1. Earlier analysis and recommendation

### Observed loop

The loop was:

1. review design/code,
2. find blockers/majors,
3. change design/code,
4. new SHA,
5. review again,
6. find different blockers/majors,
7. repeat.

This was not random. It had identifiable causes:

| Cause | Effect |
|---|---|
| Implicit design decisions | Reviewer discovers sentinel/length/Unicode/ownership gaps |
| Fixes add new surface | New migration/index/alert/evidence creates new findings |
| Incomplete fixes | Same class returns as a deeper finding |
| Reviewer scope not bound | Out-of-scope/pre-existing improvements become majors |
| Severity not calibrated | Future hardening is treated as a release blocker |
| Moving candidate SHA | Every fix invalidates evidence and triggers another review |
| No stop rule | Every finding becomes another code change |

### Disposable proof

A tiny Go `slugify` capability was used outside BI-PF-1509.

| Run | BLOCKER | MAJOR | MINOR | NIT |
|---|---:|---:|---:|---:|
| Original design review 1 | 0 | 2 | 5 | 2 |
| Original design review 2 | 0 | 3 | 3 | 1 |
| Updated design review 1 | 0 | 1 | 3 | 2 |
| Updated design review 2 | 0 | 1 | 3 | 2 |
| Final design review 1 | 0 | 0 | 3 | 3 |
| Final design review 2 | 0 | 0 | 3 | 2 |
| Final code review 1 | 0 | 0 | 3 | 3 |
| Final code review 2 | 0 | 0 | 4 | 3 |

The original design reviews found different majors because decisions were implicit.
After explicit decisions, operation order, binding non-goals, calibrated severity,
and edge tests, design reviews converged to **0 blockers / 0 majors**. Code review
was already **0 blockers / 0 majors**; only advisory minors varied.

### Recommendation

1. Make design decisions explicit: sentinel values, limits, encoding, ownership,
   failure taxonomy, non-goals, and accepted risks.
2. Bind non-goals in the review prompt; non-goal findings are `OUT_OF_SCOPE`.
3. Calibrate severity:
   - BLOCKER = AC/security/data loss.
   - MAJOR = approved contract cannot be met.
   - MINOR/NIT = improvement/hardening.
4. Freeze the exact candidate SHA before review.
5. One design review; one code review per frozen SHA.
6. Fix only in-scope blockers/majors once.
7. Disposition minors/nits; do not loop.
8. Require current-SHA evidence and executable controls.
9. Classify follow-up findings:
   `DESIGN_GAP`, `IMPLEMENTATION_GAP`, `VERIFICATION_GAP`, `FIX_INDUCED`,
   `FIX_INCOMPLETE`, `ORIGINAL_MISS`, `OUT_OF_SCOPE`/`PRE_EXISTING`, `FALSE_POSITIVE`.
10. If a final review still finds a blocker, HIL decides; no automatic re-review.

---

## 2. BIIS template analysis

The BIIS template is a strong **product/backlog item specification**. It is broader
than the runtime/control contract used for PF-SB and includes governance, UX, API,
data, security, NFRs, deployment, wiring, testing, operations, and closure evidence.

### Mapping against the slug probe

| BIIS section | Slug probe coverage | Gap |
|---|---|---|
| 1. Identity/governance | Partial | No item ID, owners, status, parent, spec version |
| 2. Problem/outcome | Partial | No business owner/metrics/actors |
| 3. Scope/boundaries | Good | Non-goals present; dependencies/assumptions/impact thin |
| 4. Functional requirements | Partial | AC present; no FR IDs, preconditions, auth, idempotency |
| 5. UX/interaction | N/A | Pure function; no UI |
| 6. Architecture/components | Partial | Entrypoint only; no component/flow diagram |
| 7. API/integration | N/A | No API |
| 8. Data/persistence | N/A | No DB |
| 9. Security/privacy | N/A | No auth/secrets/tenant |
| 10. NFRs | Partial | Max length/determinism; no measured latency |
| 11. Config/deployment | N/A | No config/service |
| 12. E2E wiring | Partial | Direct call/test; no external workflow |
| 13. Testing/verification | Good | Tests exist; no test IDs/actual reports |
| 14. Observability/operations | N/A | No runtime service |
| 15. Plan/traceability | Missing | No task IDs/requirement→design→test matrix |
| 16. Acceptance criteria | Partial | Not Given/When/Then |
| 17. Definition of Done | Partial | Tests pass; governance/approval/evidence incomplete |
| 18. Evidence/closure | Partial | Evidence files; no closure report |

### Predicted design review using BIIS

If BIIS is applied **strictly without N/A/severity discipline**:

- Findings will likely include:
  - missing governance/owners/status,
  - missing FR IDs and preconditions,
  - AC not in Given/When/Then,
  - missing traceability matrix,
  - missing impact/dependency analysis,
  - missing test IDs/evidence report,
  - N/A sections not explicitly justified.
- Some of these will be classified MAJOR because BIIS is written as a complete spec.
- This would cause one design-fix pass and potentially a re-review.

If BIIS is applied with:

- binding N/A rationale,
- binding non-goals,
- calibrated severity,
- explicit decisions,
- one frozen SHA,

then the design review should converge to **0 blockers / 0 majors** after the
specification-completeness pass. The remaining items are minor/nit documentation
or future hardening.

### Predicted code review using BIIS

The slug code itself is unchanged by BIIS. Expected code review:

- 0 blockers
- 0 majors
- 3–4 minors (doc comments, unreachable branch, test coverage)
- 2–3 nits

BIIS does not make code review repeat; it adds specification/governance requirements
before implementation.

### Measured BIIS dry-run results

A complete BIIS was written for the slug probe (`BIIS-SAMPLE.md`) with N/A sections
and non-goals explicitly declared, then reviewed twice with the severity policy.

| Run | BLOCKER | MAJOR | MINOR | NIT |
|---|---:|---:|---:|---:|
| BIIS design review 1 | 0 | 0 | 4 | 2 |
| BIIS design review 2 | 0 | 0 | 4 | 3 |
| BIIS code review 1 | 0 | 0 | 3 | 3 |
| BIIS code review 2 | 0 | 0 | 4 | 3 |

**Result:** no re-review required. Only advisory minors/nits varied:

- invalid UTF-8 behavior not pinned
- sentinel collision acknowledged but not caller-distinguishable
- fuzz/property tests deferred
- regex allocation/performance trade-off
- truncation-boundary test could be stronger
- defensive post-truncation empty branch is unreachable
- evidence naming/lookup convention
- doc/comment and constant compatibility notes

These are valid **MINOR/NIT** items. They are disposition/backlog material, not
blockers or majors.

The BIIS dry run confirms:

- BIIS completeness + binding N/A + severity calibration → design converges.
- Code review remains stable at 0 blockers / 0 majors.
- The reviewer still suggests improvements, but they do not reopen the design.
- No re-review loop if the stop rule is applied.

If BIIS is applied without N/A rationale, binding non-goals, or severity
calibration, missing governance/FR/traceability/evidence sections can be raised as
majors. That is a specification-completeness issue, not a runtime failure.

### Would BIIS cause re-review?

- **No**, if the team treats BIIS sections as N/A with rationale and applies the
  severity/stop rules.
- **Yes**, if missing governance/FR/traceability sections are treated as runtime
  blockers and every review round adds more spec structure.
- **No**, if the first BIIS completion pass is the only spec pass; minors/nits are
  dispositioned or backlogged.

### Key conclusion

BIIS is appropriate for **product/feature/backlog completeness**. It should not be
used as a code-review checklist. For a tiny pure function:

- most UI/API/DB/security/deployment sections are N/A;
- the design contract still needs runtime entrypoint, controls, tests, and evidence;
- code review should be stable once the contract is explicit.

The loop is not caused by BIIS itself. It is caused by:

1. missing explicit decisions,
2. unbounded reviewer scope/severity,
3. changing the candidate after review,
4. treating minors/nits as blockers,
5. having no stop rule.

---

## 3. Practical merge of BIIS + PF-SB contract

Use BIIS for the item-level spec:

- identity/governance,
- problem/outcome/actors,
- scope/non-goals/dependencies,
- FR/NFR IDs,
- impact,
- acceptance criteria.

Use the PF-SB design/control contract for execution:

- exact runtime entrypoint/call chain,
- adapter/DB/API contracts,
- failure taxonomy,
- controls with commands/evidence,
- current-SHA proof,
- review scope,
- rollback/recovery,
- observability/runbook.

Use the review triage policy to stop:

- fix only in-scope blockers/majors,
- disposition minors/nits,
- backlog out-of-scope/pre-existing,
- one final review per frozen SHA,
- HIL decides if a new blocker appears.

**A design cannot be made perfect. It can be made explicit, testable, bounded, and approved.**

---

## 4. Probe evidence

The disposable probe files are outside the PF repository:

`C:\Users\ADMIN\AppData\Local\Temp\opencode\pf-probe`

Key files:

- `DESIGN-v3.md`
- `slugify.go`
- `slugify_test.go`
- `go-test-v3.txt`
- `go-vet-v3.txt`
- `gofmt-v3.txt`
