# Review Gates — Backlog Item Lifecycle (SSOT)

**Scope: PF-SB / Plane A** — Product Forge's own `product_forge` backlog items. This is not the
generated-product pipeline (PF-GP / Plane B); see `docs/E2E-WORKFLOW.md`.

The authoritative gate chain for taking a PF-SB backlog item from **take-up → merge → close**. Binding with
`AGENTS.md` (EOS). If this doc and a tool disagree, the tool wins and the doc is corrected.

## Canonical roles and evidence

- **Gate 0 owner:** the worker/design author, before design approval. It produces the
  reconciliation, impact table, language/API checks, and AC in the item/design/trail. Gate 0 is
  not a review approval.
- **Gate 1.5 reviewer:** `docs/AGENT-ROLE-CONTRACTS.md` → Architect reviewer. Read-only design review.
- **Gate 2.5 reviewer:** `docs/AGENT-ROLE-CONTRACTS.md` → Architect reviewer. Read-only full-candidate review.
- **Compatibility roles:** runtime adapters may expose design-review or code-review aliases; they are
  read-only and must not create a second review process.
- **Review evidence:** `engineering/reviews/<ITEM-ID>-<design-sha>.json` for Gate 1.5 and
  `engineering/reviews/<ITEM-ID>-<diff-sha>.json` for Gate 2.5.
- **Reviewer write boundary:** reviewers may return findings, but must not edit source, tests,
  design, backlog, approvals, or gate state. The worker/orchestrator persists evidence.
- **Runtime mapping:** `docs/AGENT-RUNTIME-ADAPTERS.md`; an OpenCode/Codex/Antigravity adapter may
  change how the role is invoked, never the gate.
- **Retired artifact:** `docs/review.md` is not a gate and must never be used as approval.

## Lifecycle (in order)

**Principle — reviews precede HIL at each stage:** an independent review *informs* the human decision.
**Gate 1.5 (design review) → Gate 1 (HIL design approval)**, and **Gate 2.5 (delivery review) → Gate 2 (HIL
delivery approval)**. HIL always sees the reviewer's findings + recommendation as an input to the decision.

0. **Gate 0 — Reconciliation and impact contract (worker-authored, no HIL approval).**
   Produce the RECONCILIATION block (PRIOR DECISIONS / EXISTING PATH / ASSUMPTIONS / DIVERGENCES /
   OPEN QUESTIONS) and IMPACT REVIEW (LANGUAGE, API, AC). Record it on the item/design/trail and run
   `scripts/dev/gate0_check.py`. Do not design or implement while any row is unresolved.

1. **Gate 1.5 — Architect DESIGN review (independent; fresh context; configurable model).**
   Reviews the **design / reconciliation block and the relevant code call sites** *before* HIL approval
   (see §Gate 2.5 rules). It verifies the runtime entrypoint, exact call-site map, production adapter,
   failure behavior, failing proof test, and per-AC evidence path. **Required for every PF-SB backlog
   item** (deeper scrutiny still applies to large/security/schema work). Its findings + recommendation
   are presented to HIL.
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
   `python scripts/dev/gate1_check.py --item <ID>` (exits non-zero while any BLOCKER/MAJOR/MINOR is PENDING). Include
   both in the approval package. Pending MINOR blocks; pending NIT is recorded but does not block. Dispositions may be keyed
   by a stable `sig:<digest>` (preferred — survives re-review reordering) or by ordinal (legacy). **No code
   before approval.**

3. **Implement on a feature branch** (never `develop`). Backlog writes are **API-only**; integrity gates apply
   at write time: **AC required** at create (`POST /items` → 400), **api_impact** (`api-first`),
   **context/brief** (`backlog-context`), **epic** (`backlog-epic`), **ids / monotonic / reconcile / write-guard**.

4. **Gate 2.5 — Architect DELIVERY review (independent sub-agent).** *Runs before Gate 2; see §Gate 2.5.*
   Reviews the **full candidate**, not only the latest phase or changed lines. Findings + recommendation
   are presented to HIL.

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

All four gates are enforced for every PF-SB backlog item (no silent grandfathering):

1. **Gate 1.5**: `gate1_transition_check.py` inspects items moving `new -> in_progress` in the committed diff and
   requires committed design evidence for the **current design sha** (`architect_review.design_sha`, a canonical
   hash of the design fields), parseable and with zero PENDING BLOCKER/MAJOR/MINOR.
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
  (default `mimo-v2.6-flash`), overridable per run via `--model` / `PF_ARCHITECT_REVIEW_MODEL`. **Any**
  configured model/provider works. **Nothing is coupled to a specific runtime or model vendor**; never
  hard-code one model for all reviews (a different model is *not* a different person).
- **Inputs:** item + AC + the diff + relevant ADRs / `AGENTS.md` / standards.
- **Output:** structured findings `{BLOCKER | MAJOR | MINOR | NIT}` + a short summary + evidence file
  `engineering/reviews/<item>-<sha>.json`; append the summary to the item context.
- **Finding policy:** BLOCKER/MAJOR/MINOR must be fixed; NIT may be fixed or evidence-backed exception.
  Review findings are not accepted/deferred/scoped away. The HIL decides the design/implementation, not
  whether B/M/m stay unresolved.
- **Size gate:** run on **code / schema / security** changes; skip trivial docs/config-only change sets.
- **Presented as part of the HIL gate it informs (binding):** a review is not a standalone artifact — the
  **Gate 1.5 findings + recommendation are stated inside the Gate 1 review**, and the **Gate 2.5 findings +
  recommendation inside the Gate 2 review**, so the human decision always sees them.
- **Decision table + overall recommendation (BI-PF-1479):** `architect_review.py gate --gate 1|2` and
  `gate1_check.py` render every finding as one table (`# | severity | finding | disposition | response`)
  above a computed **overall architect recommendation** - `NOT READY` (any B/M/m pending),
  `APPROVE WITH ATTENTION` (all B/M/m fixed; NIT exceptions remain) or `APPROVE` (all fixed) - with
  severity/disposition counts. HIL still owns the gate decision; the machine path (`gate1_check --json`)
  and exit codes remain authoritative for open B/M/m.
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
  that blocks `new → in_progress` for a reviewed item while any BLOCKER/MAJOR/MINOR is PENDING (items without a
  design review are grandfathered).
- **Design pre-check** (`architect_review.py checklist --item <ID>`) remains the generic checklist.
- **Gate 1 check** (`scripts/dev/gate1_check.py`) blocks Gate 1 while BLOCKER/MAJOR/MINOR are PENDING, and treats
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

## Review budget (BI-PF-1480 / BI-PF-1485)

- **One full 1.5 design review + one full 2.5 diff review per item/mode.** `config/review-budget.json` sets
  `max_full_reviews_per_mode: 1`.
- **Delta reviews are not full reviews.** `--rereview --since <prior-reviewed-head>` is used only for fix
  verification and is excluded from the full-review budget.
- **No silent extra full review.** A second full review requires a HIL `MATERIAL_CHANGE` decision.
- **Chain validation.** A delta review must have a `base_sha` equal to a previously reviewed head and a
  `head_sha` that covers the current candidate. The review ledger stores `review_scope`, `base_sha`, and
  `head_sha`; `architect_review_check` accepts a valid full + delta chain.
- **No stale approval window.** Material approval is event-bound, not tied to an expired global date.
- **Why:** the budget prevents full re-review churn while allowing bounded delta fixes.

## Execution trail (BI-PF-1481)

Every item carries one append-only trail at `engineering/trails/<ID>.json` (owner `core/execution_trail.py`, governance-allowlisted control-plane evidence logic; `python -m core.execution_trail show --item <ID>`).

- **Stages:** planning, gate0, design_review, gate1, implementation, code_review, diff_review, gate2, tests,
  precheck, pr, merge, delivery, completion - each event has seq/at/actor/status/summary/refs/tests/usage.
- **Written automatically:** `gate0_check` (planning/gate0), `architect_review` (design/diff + provider usage),
  `gate_decisions` (gate1/gate2), `precheck` (implementation/code_review/tests/precheck), `core.backlog`
  `set_delivery`/`set_status` (delivery/completion).
- **Cost:** `config/model-pricing.json` holds configured provider list prices (USD/1M); cost is computed from
  input/cached/output tokens, provider-reported cost wins, and the show prints it in a box-drawn table.
- **Show (one ordered flow, BI-PF-1483):** `python -m core.execution_trail show --item <ID>` renders, in order:
  1. the plain-language brief (what it is / what it adds / why now / who / success),
  2. the Gate 0 reconciliation + impact table,
  3. the flow checklist with the **current stage**,
  4. the Gate 1.5 table + current architect recommendation,
  5. the Gate 1 decision,
  6. implementation + code review,
  7. the Gate 2.5 table + recommendation,
  8. the Gate 2 decision,
  9. the tests table, 10. usage/cost, 11. the final completion/next-item table, and the disposition key.
- **View invariants (read-only projection, no writes):**
  - the stage checklist uses the **latest event per stage** (`_stage_events`; append order under the trail lock,
    monotonic `seq`); the stage table's `Runs` column counts re-runs; the audit history remains in `events()`
    and unknown/legacy stage rows are still shown at the end of the table.
  - **current stage** = `blocked at <stage>` when a committed pre-merge gate (not a review) is `fail`/`error`;
    otherwise the first `STAGES` entry with no committed event while the item is `in_progress` (`planning` for an
    empty trail; `complete` when all stages exist or the item is closed).
  - review stages show the **current** recommendation (`APPROVE` / `APPROVE WITH ATTENTION` / `NOT READY`),
    not the ingest-time event status. `show` re-executes `architect_review.py gate`, which reads
    `engineering/reviews/<ID>-<sha>.json` (sha from the review event refs); this keeps one evidence reader.
    Missing/unreadable evidence renders `not recorded` / `evidence missing`; evidence with no parseable
    recommendation renders `reviewed (recommendation unavailable)` - never a pass.
  - owner: `core/execution_trail.py` (the only renderer); dispositions are owned by `core.backlog`
    (`review_dispositions`) and enforced by `architect_review.py` + `execution_trail_check.py`.
- **Disposition key:** **ACTIONED/FIXED** = fixed in this item (Gate 1.5: design updated; Gate 2.5:
  code/docs/tests updated). BLOCKER, MAJOR, and MINOR must be ACTIONED/FIXED or proven invalid with
  evidence. `ACCEPTED`, `DEFERRED`, `SCOPE`, and `REJECTED` are not valid for B/M/m. NIT may use an
  evidence-backed exception.
- **Guard:** `scripts/dev/execution_trail_check.py` runs as a POST-precheck gate after the tests/precheck
  events are written. It fails a completion when the pre-merge stages are missing/out of order or a DEFERRED
  disposition has no existing follow-up item id. `pr/merge/delivery/completion` are post-merge events.
- **Failure sink:** a trail write failure is appended to `engineering/trails/_failures.jsonl` and logged as a
  structured `execution_trail_write_failed` event; the POST gate fails the completion.


## Final report + disposition policy (BI-PF-1484)

- **AC verification is a Gate 2 requirement.** An item carries `ac_verification[]` (AC text, `result` PASS/FAIL/PENDING,
  evidence, verifier). Gate 2 refuses if any AC is missing/FAIL/PENDING; completion re-checks. 2.5 may flag missing AC
  evidence but does not certify ACs.
- **Fix every BLOCKER, MAJOR, and MINOR.** Only NIT may use an evidence-backed exception. `ACCEPTED`,
  `DEFERRED`, `SCOPE`, and `REJECTED` are not valid for B/M/m. `disposition_policy.py` enforces this at
  Gate 1, Gate 2, and completion. A false positive must be invalidated with code/test/evidence, not accepted.
- **Final report is persisted on the item.** `python scripts/dev/finalize_item.py --item <ID>` writes
  `item.final_report`: AC verification, test results by kind (unit/api/db/logic/go/other with commands/results/
  counts/durations), total time, tokens/cost, accepted/deferred with backlog ids, gate decisions. Merge is blocked
  until ACs are all PASS and the report is persisted.
- **Show** renders AC verification, test results by kind, accepted/deferred, totals and the final table; the final
  report snapshot is the durable record on the backlog item.


## First-pass quality contract + design pack (BI-PF-1484)

- **Design pack is mandatory for new work.** Canonical source: `item.design_pack`; generated snapshot:
  `engineering/design/<ID>.md` (owner `scripts/dev/design_pack.py`; do not hand-edit).
- Required sections: requirements, invariants, contracts (API/DB/files/config), failure matrix, dependencies,
  security, observability, performance, test matrix (AC -> kind/test), rollout/rollback, decisions.
- **Gate 1** validates the pack for items created on/after `config/design-pack.json.enforce_from`; every AC must
  have a test-matrix row. Gate 1.5 reviews the rendered pack; Gate 2 verifies ACs/tests.
- **First-pass contract:** design all invariants/failure modes before code; test-first for guards; self-review;
  run targeted tests + precheck; freeze; one delta review. 2.5 is a safety net, not the first test.
- **ACTIONED evidence:** non-NIT fixes must record the failing scenario + test/check command + result.
- **Fix all BLOCKER/MAJOR/MINOR.** Only NIT may use an evidence-backed exception; no B/M/m acceptance/deferral/scope.
