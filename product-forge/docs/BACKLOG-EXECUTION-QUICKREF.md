# Backlog Item Execution — Quick Reference (Fix F5 / BI-PF-XXXX)

> Single-page agent reference. Full protocol in `AGENTS.md §BACKLOG ITEM EXECUTION PROTOCOL`.
> Canonical lifecycle in `docs/REVIEW-GATES-LIFECYCLE.md`.

---

## HARD STOP RULES (read first, always)

| Rule | Detail |
|---|---|
| **Never commit to `develop`/`main`** | Feature branch only: `git checkout -b feature/bi-pf-NNNN-short-name` |
| **Backlog writes via API only** | Never edit `data/backlog/` files directly |
| **Scope = `affected_files` only** | Do not touch files outside the item's declared scope |
| **Gate failures ≥ 2 → BLOCKED** | Stop, report BLOCKED, wait for HIL — do not loop |
| **Review cycles ≥ 2 → HIL decides** | After 2 Gate 2.5 delta rounds, escalate; do not run a third review autonomously |
| **No code before Gate 1 approval** | HIL must explicitly approve before implementation starts |

---

## The 6 Steps (exact commands)

### Step 1 — Kickoff
```bash
python scripts/dev/item_kickoff.py --item <ID>
```
- Reads item, runs language rule check, injects design guardrails, takes usage snapshot
- Writes `.pf-session.json`
- Then: write `engineering/designs/<ID>.md` (see DESIGN section below)
- **Wait for HIL approval before proceeding**

### Step 2 — Design Review (Gate 1.5 → Gate 1)
```bash
# 1. Completeness check FIRST — hard stop if design is empty
python scripts/dev/design_completeness_check.py --item <ID>

# 2. Inject guardrails into design evidence
python scripts/dev/design_guardrails.py --item <ID> --record

# 3. Run Gate 1.5 architect review
python scripts/dev/architect_review.py run --item <ID> --mode design --apply

# 4. Check gate status
python scripts/dev/gate1_check.py --item <ID>

# 5. Check session state
python scripts/dev/session_state.py status
```
Disposition all BLOCKER/MAJOR findings before presenting Gate 1 to HIL.
**Wait for HIL Gate 1 approval before coding.**

### Step 3 — Implement
```bash
git checkout -b feature/bi-pf-<NNNN>-<short-name>
```
- Only touch files in `affected_files` / `in_scope`
- Wire every new module (invoked on runtime path)
- Add tests that can fail
- Commit incrementally

### Step 4 — Delivery Review (Gate 2.5 → Gate 2)
```bash
# 1. Run Gate 2.5 (commit the evidence file after)
python scripts/dev/architect_review.py run --item <ID> --mode diff --apply
git add engineering/reviews/ && git commit -m "chore: Gate 2.5 evidence <ID>"

# 2. Check session review cycle counter
python scripts/dev/session_state.py status
```
> **SHA NOTE:** Every code commit changes the diff SHA. The old evidence file is correctly
> invalidated — this is NOT an error. Re-run `architect_review.py run --item <ID> --mode diff --apply`
> and commit the new evidence. Max 2 delta rounds total. After 2 → HIL decides remaining findings.

**Wait for HIL Gate 2 approval.**

### Step 5 — Precheck
```bash
python scripts/dev/precheck.py
```
Fix ONE failing group at a time. Max 2 attempts per gate → BLOCKED if exceeded.
After any fix commit that changes the diff SHA: re-run Gate 2.5 (counts toward the 2-round cap).

### Step 6 — Closeout (after merge)
```bash
python scripts/dev/item_closeout.py --item <ID> --branch <B> --sha <S> --pr <PR>
python scripts/dev/review_learnings.py --propose  # capture any new recurring findings
```

---

## Writing the Design Doc (Step 1 output)

File: `engineering/designs/<ID>.md`

**Required sections** (all must be substantive — no TBD/None/N/A as full content):

```markdown
## PRIOR DECISIONS
<decisions already made that constrain this item>

## EXISTING PATH
<existing code/patterns this builds on or integrates with>

## ASSUMPTIONS
<what we're assuming to be true; what invalidates this design if wrong>

## DIVERGENCES
<where this deviates from existing patterns and why>

## OPEN QUESTIONS
<unresolved questions that need HIL input before or during Gate 1>

## APPROACH
<what will be built; how it works; key design decisions; rollback path>
```

**If you lack information for a section:** write `INSUFFICIENT_DATA: <what is missing>`
— do NOT write TBD. The completeness check treats TBD as a failure.

**Two-phase writing:** Think through the design in prose first (reasoning), then fill the
sections from that reasoning. Do not fill sections top-to-bottom mechanically.

---

## 6 Gates Most Likely to Fail

| Gate | Failure cause | Fix |
|---|---|---|
| `language-rule` | New Go logic written in Python | Rewrite in Go or justify as tooling |
| `wired-audit` | New module not invoked on runtime path | Add call site |
| `architect-review` | Evidence file SHA mismatch (code changed after review) | Re-run `architect_review.py run --mode diff --apply`, commit evidence |
| `backlog-dod` | AC < 40 chars or not set | Update item with detailed AC |
| `backlog-write` | Writing directly to `data/backlog/` | Use `backlog_api.py` in-process API |
| `api-first` | `needs_api` not declared | Run `api_impact_triage.py --item <ID>` |

---

## Session State Commands

```bash
python scripts/dev/session_state.py next              # what to do now
python scripts/dev/session_state.py status            # full state + cycle counters
python scripts/dev/session_state.py advance --to <state>
python scripts/dev/session_state.py record-gate-pass --gate <name>
python scripts/dev/session_state.py record-gate-fail --gate <name>
python scripts/dev/session_state.py record-review-cycle --gate <1.5|2.5>
```

## Review Cycle Cap

After **2 delta review cycles** on Gate 1.5 or Gate 2.5, `session_state.py` will print:
```
HARD STOP: review cycle cap reached (2/2 for gate_2.5_delivery).
Remaining PENDING findings require HIL disposition. Do not loop further.
```
At that point: list all PENDING findings, present to HIL, record dispositions (WONTFIX / DEFERRED / escalate).

---

## Scope Discipline

- Only files in `affected_files` / `in_scope` may be modified
- If a fix requires touching an out-of-scope file: **stop and ask HIL**
- Do NOT refactor unrelated code while fixing a finding — creates new review surface

---

## Anti-Patterns (do not do these)

| Anti-pattern | Why not |
|---|---|
| Write design as TBD placeholders | Gate 1.5 becomes a rubber stamp — real issues land at Gate 2.5 |
| Loop through Gate 2.5 more than twice | Each round creates new surface area; cap exists for this |
| Dispose findings with "ACTIONED — see doc" | Machine-unverifiable; reviewer re-raises them |
| Touch files outside `affected_files` | Creates unreviewed surface area; wired-audit fails |
| Run `architect_review` again hoping for 0 findings | Zero findings = empty design, not quality |
