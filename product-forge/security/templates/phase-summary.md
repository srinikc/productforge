# Security Phase Summary Template

## Phase: {{phase}}
## Project: {{project}}
## Status: {{status}}

---

## Execution Details

| Metric | Value |
|--------|-------|
| Started At | {{started_at}} |
| Completed At | {{completed_at}} |
| Duration | {{duration}} |

---

## Findings Summary

| Severity | Count |
|----------|-------|
| Critical | {{critical_count}} |
| High | {{high_count}} |
| Medium | {{medium_count}} |
| Low | {{low_count}} |
| Info | {{info_count}} |
| **Total** | **{{findings_count}}** |

---

## Output Files

{{#output_files}}
- {{this}}
{{/output_files}}

---

## Actions Required

### Fix Now (Critical/High)
{{#fix_now_issues}}
- [ ] {{issue_id}}: {{title}} ({{severity}})
{{/fix_now_issues}}

### Track Later (Medium/Low)
{{#track_later_issues}}
- [ ] {{issue_id}}: {{title}} ({{severity}})
{{/track_later_issues}}

---

## Compliance Status

{{#compliance_status}}
| Regulation | Status |
|------------|--------|
| {{regulation}} | {{status}} |
{{/compliance_status}}

---

## Next Steps

1. Review findings with security team
2. Make fix decisions for each issue
3. Create fix tasks for critical/high issues
4. Update security-issues.md with decisions
5. Proceed to next pipeline phase

---

## Summary Generated

- **Timestamp**: {{timestamp}}
- **Agent**: Security Agent
