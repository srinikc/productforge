---
name: threat-modeling
description: STRIDE threat modeling skill for identifying and mitigating security threats. Use when: modeling threats, analyzing attack vectors, identifying security risks, or creating threat models.
allowed-tools:
  - Read
  - Write
  - Grep
---

# Threat Modeling Skill

## Overview

STRIDE-based threat modeling for identifying and mitigating security threats in system design.

## When to Use

- Analyzing system design for threats
- Identifying attack vectors
- Creating threat models
- Security risk assessment
- Design phase security review

## STRIDE Methodology

### Spoofing
- **Description**: Impersonating someone or something
- **Examples**: Fake authentication, identity theft
- **Mitigation**: Strong authentication, MFA, cryptographic verification

### Tampering
- **Description**: Modifying data or code
- **Examples**: Data injection, code modification
- **Mitigation**: Input validation, integrity checks, digital signatures

### Repudiation
- **Description**: Denying actions
- **Examples**: Denying transactions, denying access
- **Mitigation**: Audit logging, non-repudiation mechanisms

### Information Disclosure
- **Description**: Exposing sensitive information
- **Examples**: Data leaks, verbose errors
- **Mitigation**: Encryption, access control, error handling

### Denial of Service
- **Description**: Making system unavailable
- **Examples**: Resource exhaustion, DDoS
- **Mitigation**: Rate limiting, resource quotas, redundancy

### Elevation of Privilege
- **Description**: Gaining unauthorized access
- **Examples**: Privilege escalation, bypassing controls
- **Mitigation**: Authorization checks, least privilege, RBAC

## Threat Analysis Process

1. **Identify Assets**: What are we protecting?
2. **Identify Entry Points**: Where can attackers enter?
3. **Identify Threats**: What can go wrong?
4. **Assess Risk**: How serious is each threat?
5. **Identify Mitigations**: How do we prevent it?

## Output Format

```markdown
# Threat Model

## Assets
- [Asset 1]: [Description]
- [Asset 2]: [Description]

## Entry Points
- [Entry Point 1]: [Description]
- [Entry Point 2]: [Description]

## Threats

| ID | Category | Threat | Risk | Mitigation |
|----|----------|--------|------|------------|
| THR-001 | Spoofing | Weak authentication | High | Implement MFA |

## Recommendations
1. [Recommendation 1]
2. [Recommendation 2]
```

## Risk Matrix

| Likelihood \ Impact | Low | Medium | High |
|---------------------|-----|--------|------|
| **High** | Medium | High | Critical |
| **Medium** | Low | Medium | High |
| **Low** | Low | Low | Medium |

## References

- Microsoft STRIDE
- OWASP Threat Modeling
- NIST SP 800-30
