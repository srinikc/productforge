<!-- Applies to every PR in this repo (single default template). Fill all sections; delete N/A lines only with a reason. -->

## Backlog item (required)
- **Item:** BI-… (scope: `product_forge` | `project:<id>`)
- **Epic / parent:** BI-… (if any)
- **Type:** feature | bug | change | chore | docs

## Summary (one line — what & why)


## Changes
<!-- files by owner; call out any store/registry/agent/stage addition -->
-

## Reconciliation (required for any change — see AGENTS.md)
- **PRIOR DECISIONS:**
- **EXISTING PATH:**
- **ASSUMPTIONS (owner-confirmed?):**
- **DIVERGENCES:**
- **OPEN QUESTIONS:**

## Gates (paste the result line for each)
- [ ] `python -m compileall -q core scripts dashboard api`
- [ ] `python scripts/dev/pycompat_check.py` (Python 3.11 compatibility — CI target)
- [ ] `python scripts/dev/wired_audit.py` → exit 0 (0 unwired, 0 naming, stores registered)
- [ ] `python scripts/dev/precheck.py --full` → PASS
- [ ] `python -m pytest test-framework/tests -q`
- [ ] secret-scan clean; no new dependency without a `config/tool-catalog.json` entry

## Evidence / links (for `intent_trace_check`)
- **item_id / feature_id:**
- **artifacts / tests (descriptors):**

## Merge gate (`core/pr_gate.py` checklist — unprovable ⇒ `unknown` ⇒ does NOT pass)
- [ ] code_review  - [ ] review_changes_done  - [ ] db_tests  - [ ] api_tests  - [ ] unit_tests
- [ ] lint  - [ ] ui_e2e  - [ ] app_boot  - [ ] structure_contract
<!-- Override is HIL-only (`qa.override_merge`), recorded + audited. -->

## Delivery provenance (filled AFTER merge)
- **branch:**
- **merge_sha:**
- **pr:** #
