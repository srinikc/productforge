# Review Gates — Backlog Item Lifecycle (SSOT)

The authoritative gate chain for taking a backlog item from **take-up → merge → close**. Binding with
`AGENTS.md` (EOS). If this doc and a tool disagree, the tool wins and the doc is corrected.

## Lifecycle (in order)

1. **Gate 1 — Take-up / design approval (HIL, manual).**
   Reconciliation block (PRIOR DECISIONS / EXISTING PATH / ASSUMPTIONS / DIVERGENCES / OPEN) + IMPACT REVIEW
   (LANGUAGE CHECK, API CHECK, AC) + risks. `language_rule_review.py` verdict. **No code before approval.**

1.5 **Gate 1.5 — Architect design review (optional, recommended for large/security/schema work).**
   Fresh-context review of the **design** by a different model (see Gate 2.5 rules), before coding.

2. **Implement on a feature branch** (never `develop`). Backlog writes are **API-only**; integrity gates apply
   at write time: **AC required** at create (`POST /items` → 400), **api_impact** (`api-first`),
   **context/brief** (`backlog-context`), **epic** (`backlog-epic`), **ids / monotonic / reconcile / write-guard**.

3. **Gate 2 — Delivery review (HIL).**
   Self/peer review of the diff + **AC verified independently** (verifier ≠ implementer) + linked evidence.

4. **Gate 2.5 — Second-model Architect review (before precheck).**  ← see §Gate 2.5

5. **`precheck` — fast tier (blocking, deterministic, offline).** ~40–58 gates (compile, wired-audit,
   store-contract, api-contract/governance/docs, language-rule, backlog-*, api-first, docs-fresh, secret-scan,
   compliance, data-plane-threats, intent-trace, validation-engine, feature-pr, merge-gate, rate-budget,
   tests-scoped).

6. **`--full` / `--release` tiers.** Full adds lifecycle gates (dogfood/replay/schedule, repo-setup,
   docs-fresh-strict, release, final-audit, backlog-e2e) + the full test suite; release adds `secret-scan-all`.

7. **PR / CI gate.** `structure.yml` runs precheck fast on the PR (required).

8. **Merge gate.** `merge_gate_check` (pr_gate + validation evidence) → **PR merge, no admin-merge**.

9. **Closure guard (BI-PF-1413).** `status→completed` rejects unless **AC + verification/evidence +
   `verified_by` ≠ `worker_id`**.

10. **Delivery provenance.** `set_delivery` (branch / merge_sha / PR) (+ usage/duration).

11. **Definition of Done.** `intent-trace` descriptors resolve; evidence linked; language/API checks green.

## Gate 2.5 — Second-model Architect review

**Purpose:** an *independent* architect-lens review (integrity, adaptability, scalability, security,
future-proofing, reuse/no-duplication, "the right thing") before precheck/PR.

**Rules (binding):**
- **Fresh context, separate invocation** — not the implementer's context.
- **Different model**, **configurable** — default `mimo-v2.6`, **rotatable/second-opinion** allowed; never
  hard-code one model for all reviews (a different model is *not* a different person).
- **Inputs:** item + AC + the diff + relevant ADRs / `AGENTS.md` / standards.
- **Output:** structured findings `{BLOCKER | MAJOR | MINOR | NIT}` + a short summary + evidence file
  `engineering/reviews/<item>-<sha>.json`; append the summary to the item context.
- **Advisory vs blocking:** only **objectively verifiable** classes may hard-block (secret/PII leak,
  data-loss, missing migration/test, language-rule violation, RLS bypass). **MAJOR/MINOR/NIT are advisory** →
  **HIL decides**. Never make subjective LLM output a flaky CI blocker.
- **Size gate:** run on **code / schema / security** changes; skip trivial docs/config-only change sets.
- **Not inside `precheck`** (it makes network/model calls). Run as a separate **Gate-2.5 step**; store results
  as evidence. Record usage/cost/time.

**Tool:** `scripts/dev/architect_review.py` (tooling; Python OK). Implementation tracked in the backlog
(`BI-PF-1427`). Until it exists, Gate 2.5 is performed manually by the architect session.

## One line
**Gate 1 (design) → Gate 1.5 (design review) → implement → Gate 2 (review + AC verify) → Gate 2.5 (second-model
architect review) → precheck fast → PR/CI → merge gate → closure guard → delivery → DoD.**
