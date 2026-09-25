---
name: compliance-check
description: Compliance verification skill for checking regulatory requirements. Use when: checking compliance, verifying regulations, assessing compliance gaps, or creating compliance reports.
allowed-tools:
  - Read
  - Write
  - Grep
---

# Compliance Check Skill

## Overview

Regulatory compliance verification based on product domain and industry requirements.

## When to Use

- Checking compliance with regulations
- Verifying regulatory requirements
- Assessing compliance gaps
- Creating compliance reports
- Domain-specific compliance checks

## Compliance Regulations by Domain

### Finance
- **PCI-DSS**: Payment card security
- **SOC2**: Service organization controls
- **SOX**: Financial reporting controls

### Healthcare
- **HIPAA**: Health information privacy
- **HITECH**: Health IT security

### Ecommerce
- **PCI-DSS**: Payment security
- **GDPR**: Data protection (EU)
- **CCPA**: Consumer privacy (CA)

### Government
- **FISMA**: Federal information security
- **FedRAMP**: Cloud security

### Education
- **FERPA**: Student data privacy

### Social
- **GDPR**: Data protection
- **CCPA**: Consumer privacy

## Compliance Check Process

1. **Identify Domain**: What industry/domain?
2. **Identify Regulations**: What regulations apply?
3. **Map Requirements**: What are the requirements?
4. **Assess Current State**: Are we compliant?
5. **Identify Gaps**: What's missing?
6. **Recommend Remediation**: How to fix?

## Output Format

```markdown
# Compliance Report

## Domain: [domain]

## Regulations

| Regulation | Status | Gaps |
|------------|--------|------|
| PCI-DSS | Partial | Missing encryption at rest |

## Requirements

| Regulation | Requirement | Status | Gap |
|------------|-------------|--------|-----|
| PCI-DSS | Encryption at rest | Not Met | No AES-256 |

## Recommendations
1. [Recommendation 1]
2. [Recommendation 2]
```

## Compliance Status Values

- **Met**: Requirement is satisfied
- **Not Met**: Requirement is not satisfied
- **Partial**: Requirement partially satisfied
- **N/A**: Requirement not applicable

## References

- NIST Compliance Framework
- ISO 27001
- SOC 2 Trust Principles
