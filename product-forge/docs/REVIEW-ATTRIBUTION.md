# Review Finding Attribution

Every finding after the first full review gets an `origin_class`:

| Class | Meaning | Owner |
|---|---|---|
| ORIGINAL_MISS | The defect existed in the first candidate and was inside first-review scope | Reviewer/process + implementer |
| FIX_INDUCED | The defect exists only because of the fix for a prior finding | Implementer/fix process |
| FIX_INCOMPLETE | The same defect remains because the prior fix was partial | Implementer |
| DESIGN_GAP | The implementation followed an incomplete design | Design author |
| PRE_EXISTING | Defect existed before this item and is out of scope | Backlog owner |
| OUT_OF_SCOPE | Finding is outside declared review scope | Scope owner |
| FALSE_POSITIVE | Reviewer claim is wrong or stale | Reviewer/process |
| ENV | Test/environment failure | Tooling owner |

## Rules

- First review: full item diff, design, AC, guidelines, evidence.
- Follow-up review: only the fix diff plus verification of prior findings.
- Every follow-up finding gets an `origin_class` and a link to the prior SHA/finding.
- ORIGINAL_MISS → fix code and add reviewer escape RCCA.
- FIX_INDUCED/FIX_INCOMPLETE → fix root cause and add regression test.
- OUT_OF_SCOPE/PRE_EXISTING → backlog; do not expand the item.
- FALSE_POSITIVE → close with evidence.
- No automatic re-review after attribution.
