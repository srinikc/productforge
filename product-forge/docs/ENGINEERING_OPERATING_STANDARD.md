# Engineering Operating Standard (EOS)

> **What this is:** the standing pattern of thinking, designing, implementing, reasoning, verifying and the
> tools/knowledge required — for every human **and** agent working on Product Forge. It is **referenced on every
> change** and is intended to be **imbibed into Product Forge's own agent knowledge/gates**.
> **Companion:** `RCCA_productForge.md` (why the gaps happened), `final_required_changes.md` (what to fix).
> **Rule:** if a proposed action conflicts with this standard, the standard wins unless an explicit, recorded
> exception is approved.

---

## 0. Prime directive
Make it **truthful, safe, observable** — never trade correctness for the appearance of completion.
“It completed” is only true when the *right, current-run, executed* evidence passed.

---

## 1. Thinking & reasoning patterns
- **Systems thinking:** trace the whole path (pipeline → project → stage → agent → LLM/tool → artifact/state);
  name the invariants at each boundary.
- **Evidence over assertion:** existence ≠ verification. Verify *execution*, not *presence*.
- **Fail-closed by default:** unknown / missing / unreadable / timeout / exception ⇒ **BLOCKED / UNVERIFIED**.
- **360° dependency analysis before any change:** grep every caller/consumer of what you touch; list the blast
  radius; decide what else must change.
- **Reversibility & blast radius:** smallest correct change; feature branch; never direct to `develop`/`main`.
- **5-Why RCCA:** fix the root cause, not the symptom; record it (`RCCA_productForge.md`).
- **Adversarial / second-order:** always ask *“what must NOT happen?”*, not just *“does it work?”*.
- **Cost & latency are first-class:** tokens, context, wall-clock and money are design inputs (context
  engineering, capability steering, routing).
- **Assume concurrency and partial failure:** two writers, crashes mid-write, retries, duplicate events.

## 2. Design principles
1. **One truth per concern, one writer per file.** Derived state is **projected/derived**, never written by hand.
2. **Event sourcing / CQRS:** an append-only event log is the SSOT; status/state are rebuildable projections.
3. **Immutable, run-bound provenance:** every artifact/test/approval carries `run_id · stage · agent · attempt_id ·
   content_hash`. Prior-run evidence is rejected on resume.
4. **Explicit contracts:** immutable task contract (identity, scope, permissions, limits, verification, recovery);
   schemas validated at boundaries.
5. **Deny-by-default authorization at the boundary:** tool allowlists, tenancy, budgets and caps are enforced in
   the executor/tool-registry/API middleware — **never** by prompt text alone.
6. **Idempotency + fencing + atomicity:** `O_CREAT|O_EXCL`/DB lease with fencing token; temp+fsync+replace;
   transactional multi-file updates; idempotency keys for side effects.
7. **Observability by design:** one structured JSONL schema, `trace_id = run_id`, OTel-style spans, SLIs/SLOs.
8. **Bounded autonomy:** cap attempts/tool-calls/tokens/wall-clock/no-progress; escalate-on-failure; terminate
   only after **verified** acceptance.

## 3. Implementation standards
- Atomic writes (`temp + fsync + os.replace`); unique temp paths; exclusive locks with owner verification.
- **Never** `except: pass` / default-`ok` on a gate path; a check that cannot fail is not a check.
- Validate types/shapes at trust boundaries; reject `../`/absolute paths; canonicalize identifiers.
- Backward-compatible changes; no silent behaviour flips; deprecate explicitly.
- Tests **can fail** (assertions, nonzero exit); tests are **hermetic** (no coupling to real config/env state).
- Keep the change reviewable: one concern per commit; rationale in the message; link backlog IDs.

## 4. The mandatory change workflow
1. **Branch:** `feature/<scope>` from `develop` (never commit to `develop`/`main` directly).
2. **Recon + 360 dependency map:** callers, consumers, config, stores, tests; blast radius.
3. **Plan + acceptance criteria**, including the **failure modes** (what must NOT happen).
4. **Implement** the smallest correct change; preserve the invariants in §2.
5. **Add/extend regression tests** — happy path **and** non-happy (empty/skipped/unknown/stale/race/oversized).
6. **Run the gates:** `compileall` + `wired_audit` + `workflow_matrix_check` + `pytest` (pipeline suite).
7. **Verify baseline:** if a test fails, confirm via a stash comparison whether it is pre-existing; **fix it**
   (product bug or stale test) — do not leave it.
8. **Self-review:** regression, security/authz, concurrency, cost, observability.
9. **Commit on the branch** with rationale + backlog IDs; update doc/backlog status.
10. **PR → merge gate** (never bypass; HIL-only override with audit).

## 5. Required tools
`git` (feature branch) · `python -m compileall` · `scripts/dev/wired_audit.py` ·
`scripts/dev/workflow_matrix_check.py` · `pytest` (test-framework/tests/pipeline) · `python -m core.backlog`
(dedup + status) · `scripts/dev/gen_docs_index.py` (+ `gen_backlog_summary.py`) · `call-ledger` ·
`model_catalog`/`model_gate` · the audit register (`docs/final_required_changes.md`).

## 6. Decision heuristics (“logic”)
- Unknown/missing → **block** (fail closed).
- Evidence not bound to the current run → **reject**.
- More than one writer → make it **atomic** or **single-writer**.
- Enforced only in a prompt → **move it to the code boundary**.
- No test can fail → **add one** that can.
- Unbounded cost/loop → **cap and reserve**.
- Irreversible action → **branch/backup/rollback plan** first.
- Generated/legacy output → **don’t trust**; derive or exclude.
- Contradictory sources → the **code is the truth**; fix the docs/state.

## 7. Knowledge domains to draw on
- **AI/LLM engineering:** context engineering & compaction, capability steering (reasoning/structured/tools),
  structured-output-first + deterministic render, model routing & fallback, token/cost economics, evals,
  multimodal plumbing, prompt versioning.
- **Agentic patterns:** planner-execute (ReWOO), ReAct tool loops, orchestrator-workers, evaluator-optimizer,
  human-in-the-loop with explicit decisions, bounded retries/escalation.
- **Distributed systems:** concurrency, idempotency, fencing tokens, transactions/journaling, event sourcing,
  DLQ, backpressure, graceful shutdown.
- **Security:** authn/authz, multi-tenant isolation, least privilege, secret hygiene, provenance/C2PA.
- **Observability:** OpenTelemetry + GenAI semconv, RED/USE, SLIs/SLOs, structured logging, trace context.
- **Software craft:** invariants, contract-first, SOLID, testing pyramid, deterministic tests.
- **Product:** MoSCoW/RICE, unit economics, non-happy-path requirements.

## 8. How this is enforced (so it is imbibed, not aspirational)
- **Referenced from `AGENTS.md`** → every contributor/agent follows it.
- **Fed into Product Forge agent knowledge/guidelines** → pipeline agents apply the same standard.
- **Checked by CI + audits:** `compileall`, `wired_audit` (store/naming/paths/destructive/legacy), and the
  **M0 acceptance suite** (11 scenarios). Gates are *code paths*, not prose.
- **RCCA loop:** every incident/defect produces a 5-Why + a new guard (test/gate/guideline), so the same class
  cannot recur silently.

## 9. Definition of Done (per change)
- [ ] Feature branch; 360° dependency map done.
- [ ] Failure modes specified and tested.
- [ ] `compileall` + `wired_audit` + `workflow_matrix_check` + `pytest` green (no new failures; pre-existing fixed).
- [ ] No fail-open on gate paths; unknown ⇒ blocked.
- [ ] Run-bound provenance + atomicity preserved; authz at the boundary.
- [ ] Cost/observability considered; logs/status accurate.
- [ ] Backlog + docs status updated; committed on the branch with rationale.

---

> **Refer to this standard before every change.** Product Forge is expected to encode §2–§4 and §9 into its
> agent prompts, gates and the M0 acceptance suite so the same discipline is automatic.
