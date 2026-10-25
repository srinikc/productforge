# Review Gates — Backlog Item Lifecycle (SSOT)

The authoritative gate chain for taking a backlog item from **take-up → merge → close**. Binding with
`AGENTS.md` (EOS). If this doc and a tool disagree, the tool wins and the doc is corrected.

## Lifecycle (in order)

**Principle — reviews precede HIL at each stage:** an independent review *informs* the human decision.
**Gate 1.5 (design review) → Gate 1 (HIL design approval)**, and **Gate 2.5 (delivery review) → Gate 2 (HIL
delivery approval)**. HIL always sees the reviewer's findings + recommendation as an input to the decision.

1. **Gate 1.5 — Architect DESIGN review (independent; fresh context; configurable model).**
   Reviews the **design / reconciliation block** *before* HIL approval (see §Gate 2.5 rules). Recommended for
   large/security/schema work. Its findings + recommendation are presented to HIL.
   **Default runner = direct provider call** (`architect_review.py run` — one LLM call, no tools, lowest
   cost/latency); the sub-agent `launch_command` is **opt-in** for investigation-heavy reviews (BI-PF-1449).
   Run the **design pre-check checklist** first: `architect_review.py checklist --item <ID>`.

2. **Gate 1 — Take-up / design approval (HIL, manual), informed by Gate 1.5.**
   Reconciliation block (PRIOR DECISIONS / EXISTING PATH / ASSUMPTIONS / DIVERGENCES / OPEN) + IMPACT REVIEW
   (LANGUAGE CHECK, API CHECK, AC) + risks. `language_rule_review.py` verdict.
   **The Gate 1 review MUST state the Gate 1.5 findings + recommendation inline** (so HIL decides with them
   visible; not a separate artifact).

   **Gate 1 is only valid with the consolidated view:** produce it with
   `python scripts/dev/architect_review.py gate --item <ID> --gate 1` and enforce it with
   `python scripts/dev/gate1_check.py --item <ID>` (exits non-zero while any BLOCKER/MAJOR is PENDING). Include
   both in the approval package. Pending MINOR/NIT do not block but must be recorded. Dispositions may be keyed
   by a stable `sig:<digest>` (preferred — survives re-review reordering) or by ordinal (legacy). **No code
   before approval.**

3. **Implement on a feature branch** (never `develop`). Backlog writes are **API-only**; integrity gates apply
   at write time: **AC required** at create (`POST /items` → 400), **api_impact** (`api-first`),
   **context/brief** (`backlog-context`), **epic** (`backlog-epic`), **ids / monotonic / reconcile / write-guard**.

4. **Gate 2.5 — Architect DELIVERY review (independent sub-agent).** *Runs before Gate 2; see §Gate 2.5.*
   Findings + recommendation are presented to HIL.

5. **Gate 2 — Delivery review (HIL), informed by Gate 2.5.**
   Self/peer review of the diff + **AC verified independently** (verifier ≠ implementer) + linked evidence.
   **The Gate 2 review MUST state the Gate 2.5 findings + recommendation inline** (HIL decides with them visible).

6. **`precheck` — fast tier (blocking, deterministic, offline).** ~40–58 gates (compile, wired-audit,
   store-contract, api-contract/governance/docs, language-rule, backlog-*, api-first, docs-fresh, secret-scan,
   compliance, data-plane-threats, intent-trace, validation-engine, feature-pr, merge-gate, architect-review,
   rate-budget, tests-scoped).

7. **`--full` / `--release` tiers.** Full adds lifecycle gates (dogfood/replay/schedule, repo-setup,
   docs-fresh-strict, release, final-audit, backlog-e2e) + the full test suite; release adds `secret-scan-all`.

8. **PR / CI gate.** `structure.yml` runs precheck fast on the PR (required).

9. **Merge gate.** `merge_gate_check` (pr_gate + validation evidence) → **PR merge, no admin-merge**.

10. **Closure guard (BI-PF-1413).** `status→completed` rejects unless **AC + verification/evidence +
    `verified_by` ≠ `worker_id`**.

11. **Delivery provenance.** `set_delivery` (branch / merge_sha / PR) (+ usage/duration).

12. **Definition of Done.** `intent-trace` descriptors resolve; evidence linked; language/API checks green.

## Hard gates for every item (BI-PF-1469)

All four gates are enforced for every backlog item (no silent grandfathering):

1. **Gate 1.5**: `gate1_transition_check.py` inspects items moving `new -> in_progress` in the committed diff and
   requires committed design evidence for the **current design sha** (`architect_review.design_sha`, a canonical
   hash of the design fields), parseable and with zero PENDING BLOCKER/MAJOR.
2. **Gate 1**: a decision `{gate:1, decision:APPROVE|APPROVE_WITH_ATTENTION, by:"hil:<actor>",
   findings_sha:<design sha>, findings_digest:<digest of dispositions>}`. A new design changes the sha and
   invalidates the approval.
3. **Gate 2.5**: unchanged hard rule - committed diff evidence for the change sha.
4. **Gate 2**: `gate2_completion_check.py` (and `core.backlog.set_status`) require Gate 2.5 evidence with zero
   PENDING findings **and** a decision `{gate:2, ..., findings_sha:<diff evidence sha>, findings_digest:...}`.
   Docs/config-only changes use `findings_sha:"docs-only"`.

Shared predicate: `core/gate_predicates.py` (used by both precheck/CI and `set_status`, so local and CI cannot
diverge). Fail-closed: missing/unparsable evidence, stale sha, digest mismatch, unknown/expired baseline, or a
gate-tool error deny. `--report` is the explicit non-blocking dry-run.

Baseline: `config/gate-baseline.json` exempts legacy items that transition during rollout; entries require
`owner_item`, `reason`, and `until` (UTC, inclusive, <=90 days), max 10 entries; expired/unknown entries deny.
Force: `set_status(force=True)` requires `PF_GATE_FORCE=1` and `PF_CI` unset, appends an audited
`gate_override` decision, and is a convenience override - not an authorization boundary.

## Gate 2.5 — Second-model Architect review

**Purpose:** an *independent* architect-lens review (integrity, adaptability, scalability, security,
future-proofing, reuse/no-duplication, "the right thing") before precheck/PR.

**Rules (binding):**
- **Fresh context, separate invocation** — a **separately-launched review sub-agent** (its own context + role),
  not the implementer's context.
- **Configurable model, provider-agnostic** — the reviewer model is set in `config/architect-review.json`
  (default `mimo-v2.6-flash`), overridable per run via `--model` / `PF_ARCHITECT_REVIEW_MODEL`. **Any** model
  works (opencode-go/mimo, google/gemini-2.5-flash, anthropic/claude, …). **Nothing is coupled to OpenCode or
  Mimo**; never hard-code one model for all reviews (a different model is *not* a different person).
- **Inputs:** item + AC + the diff + relevant ADRs / `AGENTS.md` / standards.
- **Output:** structured findings `{BLOCKER | MAJOR | MINOR | NIT}` + a short summary + evidence file
  `engineering/reviews/<item>-<sha>.json`; append the summary to the item context.
- **Advisory vs blocking:** only **objectively verifiable** classes may hard-block (secret/PII leak,
  data-loss, missing migration/test, language-rule violation, RLS bypass). **MAJOR/MINOR/NIT are advisory** →
  **HIL decides**. Never make subjective LLM output a flaky CI blocker.
- **Size gate:** run on **code / schema / security** changes; skip trivial docs/config-only change sets.
- **Presented as part of the HIL gate it informs (binding):** a review is not a standalone artifact — the
  **Gate 1.5 findings + recommendation are stated inside the Gate 1 review**, and the **Gate 2.5 findings +
  recommendation inside the Gate 2 review**, so the human decision always sees them.
- **Decision table + overall recommendation (BI-PF-1479):** `architect_review.py gate --gate 1|2` and
  `gate1_check.py` render every finding as one table (`# | severity | finding | disposition | response`)
  above a computed **overall architect recommendation** - `NOT READY` (blocker/major pending),
  `APPROVE WITH ATTENTION` (all blockers/majors dispositioned but some accepted/deferred/scope/rejected) or
  `APPROVE` (all blockers/majors actioned) - with severity/disposition counts. It is advisory input; the HIL
  still decides. The machine path (`gate1_check --json`) and exit codes are unchanged.
- **The model run is NOT inside `precheck`** (network/model calls) — run it separately as the **Gate-2.5 step**
  and commit the evidence (`engineering/reviews/<item>-<sha>.json`). Record usage/cost/time.
- **ENFORCED as a hard rule** (BI-PF-1428): `precheck` fast runs `scripts/dev/architect_review_check.py`
  (deterministic, offline — no model). A **code / schema / security** change **fails closed** unless a matching
  review evidence file exists for the current diff sha; **docs/config-only** changes are skipped (size gate);
  pre-existing changes are grandfathered via `config/architect-review-baseline.json`. So no change reaches the
  PR/merge gate without a Gate 2.5 review, in every session and worktree.

**Tool:** `scripts/dev/architect_review.py` (tooling; Python OK; `BI-PF-1427`). Model-agnostic:
`emit --mode design|diff` builds the fresh-context reviewer prompt from the item + AC + design/diff;
`ingest --file <review>` parses findings → `engineering/reviews/<item>-<sha>.json` and (with `--apply`)
appends the summary to the item context. The reviewer **sub-agent** (any model from
`config/architect-review.json`) is launched separately; the tool does not embed or lock a model.

## Review learning loop (BI-PF-1449)

Reviews are a learning input, not a one-off artifact:
- **Design-time injection (BI-PF-1467/1468):** before writing a design, run
  `python scripts/dev/design_guardrails.py --item <ID>` — it injects the checklist + the most relevant
  CORRECTION-LEDGER rules + recurring **Gate 1.5** findings into the design. Grooming does this
  **automatically**: the AI groom prompt carries the block and the item records
  `Design guardrails applied (<ID>): sig:<digest>` on evidence. The design-mode review prompt carries the same
  block, so **Gate 1.5 verifies; it is not the first place these are discovered**.
- **Coding-time injection (BI-PF-1468):** the implementation path carries the same source filtered to recurring
  **Gate 2.5** findings — the worker appends `CODING GUARDRAILS` to the objective and the code agents
  (`implement*`, `devops`, `fix`) get it in their prompt. Coding pre-empts the delivery-review classes instead of
  repeating them; the worker records `coding_guardrails` in its run evidence.
- **One source, no repetition:** both phases read `core/design_guardrails.py` (checklist + ledger + recurrence
  report), rules are relevance-ranked and capped, and recurring findings are deduped by `sig:<digest>`.
- **Gate 1 transition enforcement (BI-PF-1466):** `scripts/dev/gate1_transition_check.py` is a precheck gate
  that blocks `new → in_progress` for a reviewed item while any BLOCKER/MAJOR is PENDING (items without a
  design review are grandfathered).
- **Design pre-check** (`architect_review.py checklist --item <ID>`) remains the generic checklist.
- **Gate 1 check** (`scripts/dev/gate1_check.py`) blocks Gate 1 while BLOCKER/MAJOR are PENDING, and treats
  unparsable evidence as indeterminate (BI-PF-1465).
- **Findings → durable rules** (`scripts/dev/review_learnings.py`): recurring findings not captured in
  `docs/CORRECTION-LEDGER.md` are flagged (`--check`) and emitted as ledger rows (`--propose`), each carrying a
  stable `sig:<digest>` so capture is machine-traceable. `--write` persists the durable trend/recurrence report
  to `engineering/learnings/review-findings.json` (registered store) — the machine-readable source for
  `RAG-PROCESS-MEMORY` retrieval.
- **Expected trend:** findings per review should fall over time. If it does not, the design pre-check/ledger is
  not being applied — that is itself a finding.

## One line
**Gate 1.5 (design review) → Gate 1 (HIL design approval) → implement → Gate 2.5 (delivery review) → Gate 2
(HIL delivery approval) → precheck fast → PR/CI → merge gate → closure guard → delivery → DoD.**

**Binding order (hard).** Gate 0 (reconciliation + impact table + language + API) ? Gate 1.5 design review ? HIL Gate 1 ? implement ? Gate 2.5 diff review ? HIL Gate 2 ? precheck ? merge. Completion is also gated: an item cannot reach `completed` without Gate 0 artifacts, current design evidence and a Gate 1 decision, even if it never transitioned through `in_progress`.

## Review budget (BI-PF-1480)

- **One diff review per code freeze.** The Gate 1 decision is the epoch; only diff reviews after it count.
- **Disposition before re-review.** A second diff review for an item is refused while the prior diff review has
  no dispositions. `--rereview --reason` is the audited override: the reason must cite the prior review sha,
  is redacted, capped, and stored as `rereview_reason` in the evidence.
- **Budget.** `config/architect-review.json` `review_budget` sets `warn_after` (2) and `fail_after` (4):
  count > warn prints a structured `review_churn_warn`; count > fail fails a completion in the diff unless the
  item carries a HIL-attested `review_churn` decision (attester allowlist, >=40-char note citing the review sha).
- **Gate.** `scripts/dev/review_churn_check.py` is a fast precheck gate; `--report`/`--json` are the
  non-blocking/machine modes. Reviews are counted from committed `HEAD` evidence; a missing base ref reports
  `skipped` (CI uses full history/`--base`).
- **Why:** EDP-10 hit 8 diff reviews because fixes were made after each review instead of batching and
  dispositioning. This guard makes re-review deliberate and auditable.
