---
name: security-analysis
description: Comprehensive security analysis skill for multi-phase security testing. Use when: performing security analysis, running security scans, checking vulnerabilities, assessing security risks, or when user asks for security review.
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
---

# Security Analysis Skill

## Overview

Comprehensive security analysis across all pipeline phases, from design through implementation.

## When to Use

- Security analysis at any pipeline phase
- Running security scans (SAST, DAST, dependency, secrets)
- Checking for vulnerabilities
- Assessing security risks
- Security compliance verification

## Core Principles

1. **Defense in Depth**: Multiple layers of security controls
2. **Least Privilege**: Minimum required permissions
3. **Fail Secure**: System fails to secure state
4. **Separation of Duties**: Different roles for different tasks
5. **Security by Design**: Security built-in, not bolted-on

## Security Analysis Phases

### Phase 1: Design Security
- Threat modeling (STRIDE)
- Compliance requirements
- Security architecture requirements

### Phase 2: Architecture Security
- Security controls review
- Third-party component analysis
- Security architecture validation

### Phase 3: Implementation Security
- Static analysis (SAST)
- Dependency vulnerability scanning
- Secret detection

### Phase 4: Validation Security
- Dynamic analysis (DAST)
- Penetration testing
- Vulnerability assessment

## Security Tools

| Tool | Purpose | Language |
|------|---------|----------|
| Bandit | Python SAST | Python |
| Semgrep | Multi-language SAST | All |
| Trivy | Dependencies | All |
| Safety | Python deps | Python |
| npm audit | Node.js deps | JavaScript |
| TruffleHog | Secrets | All |
| GitLeaks | Secrets | All |
| OWASP ZAP | DAST | Web |
| Nuclei | Vulnerabilities | All |

## Output Format

```markdown
# Security Analysis Report

## Summary
- Total Findings: [count]
- Critical: [count]
- High: [count]
- Medium: [count]
- Low: [count]

## Findings

| ID | Severity | File | Issue |
|----|----------|------|-------|
| SEC-001 | critical | src/auth.py:42 | SQL Injection |

## Recommendations
1. [Recommendation 1]
2. [Recommendation 2]
```

## Quality Gates

- All critical issues must be fixed before deployment
- High issues must be addressed within 1-2 weeks
- Medium issues tracked for next sprint
- Low issues tracked for future

## References

- OWASP Top 10:2025
- CWE/SANS Top 25
- NIST Security Framework
