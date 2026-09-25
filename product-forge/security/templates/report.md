# Security Report Template

## Project: {{project}}
## Phase: {{phase}}
## Generated: {{timestamp}}

---

## Summary

| Metric | Value |
|--------|-------|
| Total Findings | {{total_findings}} |
| Critical | {{critical_count}} |
| High | {{high_count}} |
| Medium | {{medium_count}} |
| Low | {{low_count}} |
| Info | {{info_count}} |

---

## Findings

| ID | Severity | File | Line | Issue |
|----|----------|------|------|-------|
{{#findings}}
| {{id}} | {{severity}} | {{file}} | {{line}} | {{issue}} |
{{/findings}}

---

## Details

{{#findings}}
### {{id}}

- **Severity**: {{severity}}
- **File**: {{file}}:{{line}}
- **OWASP**: {{owasp_category}}
- **CWE**: {{cwe}}
- **CVSS**: {{cvss}}

**Description**: {{description}}

**Recommendation**: {{recommendation}}

---
{{/findings}}

---

## Recommendations

{{#recommendations}}
1. {{this}}
{{/recommendations}}

---

## Tools Used

{{#tools_used}}
- {{this}}
{{/tools_used}}

---

## Report Generated

- **Timestamp**: {{timestamp}}
- **Tool**: Security Agent
- **Version**: 1.0.0
