# Engineering Operating Principles (general)

> Transferable engineering discipline for ANY project or session (language- and stack-agnostic).
> This is the loadable product-facing form of `docs/ENGINEERING_OPERATING_STANDARD.md` (EOS); the same
> principles apply to how Product Forge is built and to how Product Forge builds projects.

## Core principles
1. **Truth over appearance.** “Completed” is only true when the right evidence passed.
2. **Evidence over assertion.** Verify execution and state, not presence (a file existing proves nothing).
3. **Fail closed.** Unknown / missing / unreadable / timeout / exception ⇒ BLOCKED/UNVERIFIED, never PASS.
4. **Bind evidence to identity.** Every artifact/test/approval carries run/version/attempt + a content hash;
   reject stale (prior-run) evidence.
5. **One source of truth; one writer.** Derive, don’t duplicate; make one thing authoritative.
6. **Enforce at the boundary, not in prose.** Permissions/limits/validation are code at the execution edge.
7. **Assume concurrency and partial failure.** Atomic writes, exclusive locks/leases + fencing, idempotency,
   transactions, DLQ + retries.
8. **Bound autonomy.** Cap attempts/tokens/cost/time/no-progress; escalate on failure; stop only after verified
   acceptance.
9. **Budget the scarce resource.** Context/tokens/latency/cost are design inputs — compact, route, cache, cap.
10. **Small, reversible, verified steps.** Branch, one concern per change, run the gates, be able to roll back.
11. **Baseline before blaming.** Prove pre-existing vs regression before concluding.
12. **Root-cause (5-Why); every fix adds a guard.** No defect closes without a new test/gate.
13. **Tests that can fail, hermetic, non-happy-first.** Add the failure-mode test.
14. **Observability is design.** Correlation ids, structured events, SLIs/SLOs.
15. **Security by default.** Authn/authz, least privilege, tenant isolation, secret hygiene.
16. **Least surprise & compatibility.** Explicit deprecation; no silent behaviour flips.
17. **Verify claims against the live system** — never trust static/third-party assertions blindly.
18. **Centralize at single-writer points** so provenance/audit cannot be missed.
19. **No placeholders.** Never ship TODO/FIXME/stub/dummy/mock/“not implemented” code, fake data, or empty
    functions — implement the real, working behaviour end to end.
20. **360° impact analysis before any change.** Inspect existing code + dependencies; find every affected
    caller/contract/config/store/test; apply ALL required changes together so the end-to-end flow stays correct.

## How to apply (checklist)
- Before: feature branch · map dependencies/blast radius · state the failure modes.
- During: smallest correct change · keep invariants · enforce at boundaries · atomic/single-writer.
- After: gates green (`compileall`, `wired_audit`, `workflow_matrix`, tests) · regression test added ·
  no fail-open · evidence run-bound · status/docs updated.
