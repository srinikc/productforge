# Engineering Knowledge Base

> Comprehensive engineering standards and best practices for MyWorld Central Portal and all products.

## Overview

This knowledge base contains the official engineering guidelines, standards, and best practices for the MyWorld platform. Every engineer, agent, and automated tool should reference these guidelines when building, reviewing, or maintaining code.

## How to Use This Knowledge Base

1. **Before writing code** — Review the relevant guidelines
2. **During code review** — Reference standards when providing feedback
3. **For new team members** — Start with [Coding Standards](#coding-standards) and [Architecture](#architecture)
4. **For specific tasks** — Use the [Quick Reference](#quick-reference-by-task) below

## Knowledge Sources

These guidelines are derived from:
- **LLM Training Knowledge** — Industry best practices and proven patterns
- **Internet Research** — Latest framework documentation, OWASP, W3C, etc.
- **Project-Specific** — MyWorld Central Portal requirements and decisions
- **Community** — Open source best practices and proven patterns

Acquisition follows the **Knowledge Acquisition Pipeline** (see `knowledgecourse.md`).

## Table of Contents

### Coding Standards
Language-specific coding conventions and patterns.

| Language/Framework | Status | Document |
|---------------------|--------|----------|
| **Python** | ✅ Complete | [coding/python/style-guide.md](coding/python/style-guide.md) |
| **TypeScript** | ✅ Complete | [coding/typescript/style-guide.md](coding/typescript/style-guide.md) |
| **Go** | ✅ Complete | [coding/go/style-guide.md](coding/go/style-guide.md) |

### Architecture
System design, ADRs, and architectural decision-making.

| Topic | Status | Document |
|-------|--------|----------|
| **Architecture Decisions (ADRs)** | ✅ Complete | [architecture/decisions.md](architecture/decisions.md) |

### Frontend
Web and mobile frontend engineering.

| Topic | Status | Document |
|-------|--------|----------|
| **React/Next.js** | ✅ Complete | [frontend/react.md](frontend/react.md) |
| **UI/UX Accessibility** | ✅ Complete | [ui-ux/accessibility.md](ui-ux/accessibility.md) |

### Backend
Server-side engineering.

| Topic | Status | Document |
|-------|--------|----------|
| **FastAPI (Python)** | ✅ Complete | [backend/fastapi.md](backend/fastapi.md) |
| **REST API Design** | ✅ Complete | [api/rest.md](api/rest.md) |

### Database
Data modeling and database engineering.

| Topic | Status | Document |
|-------|--------|----------|
| **PostgreSQL** | ✅ Complete | [database/postgresql.md](database/postgresql.md) |

### Infrastructure
Containers, orchestration, and infrastructure-as-code.

| Topic | Status | Document |
|-------|--------|----------|
| **Docker & Kubernetes** | ✅ Complete | [infrastructure/docker.md](infrastructure/docker.md) |

### Cloud
Cloud provider-specific patterns.

| Topic | Status | Document |
|-------|--------|----------|
| **AWS** | ✅ Complete | [cloud/aws.md](cloud/aws.md) |

### Performance & Scaling
Application and infrastructure performance.

| Topic | Status | Document |
|-------|--------|----------|
| **Performance Optimization** | ✅ Complete | [performance/optimization.md](performance/optimization.md) |
| **Scaling Strategies** | ✅ Complete | [scaling/strategies.md](scaling/strategies.md) |
| **Rendering (SSR/SSG/CSR)** | ✅ Complete | [rendering/strategies.md](rendering/strategies.md) |

### Caching
Multi-level caching strategies.

| Topic | Status | Document |
|-------|--------|----------|
| **Caching Strategies** | ✅ Complete | [caching/strategies.md](caching/strategies.md) |

### Security
Security best practices and compliance.

| Topic | Status | Document |
|-------|--------|----------|
| **OWASP Security** | ✅ Complete | [security/owasp.md](security/owasp.md) |
| **Compliance (GDPR, SOC2, HIPAA, PCI)** | ✅ Complete | [compliance/regulations.md](compliance/regulations.md) |

### Quality Assurance
Testing and quality engineering.

| Topic | Status | Document |
|-------|--------|----------|
| **Testing Standards** | ✅ Complete | [testing/standards.md](testing/standards.md) |

### Operations
Monitoring, logging, and observability.

| Topic | Status | Document |
|-------|--------|----------|
| **Monitoring & Observability** | ✅ Complete | [monitoring/observability.md](monitoring/observability.md) |
| **Packaging & Distribution** | ✅ Complete | [packaging/distribution.md](packaging/distribution.md) |

### Cross-Cutting Concerns
Patterns that apply across all layers.

| Topic | Status | Document |
|-------|--------|----------|
| **Cross-Cutting (errors, logging, i18n, etc.)** | ✅ Complete | [shared/cross-cutting.md](shared/cross-cutting.md) |

---

## Quick Reference by Task

### "I'm building a new REST API endpoint"
1. [REST API Standards](api/rest.md) — URL design, status codes, pagination
2. [FastAPI Patterns](backend/fastapi.md) — Python/FastAPI implementation
3. [Error Handling](shared/cross-cutting.md#error-handling-philosophy) — Standard error responses
4. [Testing Standards](testing/standards.md) — API endpoint tests
5. [Security](security/owasp.md) — Input validation, authentication

### "I'm building a new React component"
1. [React/Next.js Standards](frontend/react.md) — Component patterns, hooks
2. [TypeScript Style Guide](coding/typescript/style-guide.md) — Type safety, patterns
3. [UI/UX Accessibility](ui-ux/accessibility.md) — WCAG 2.1 AA compliance
4. [Testing](testing/standards.md) — Component testing

### "I'm designing a database schema"
1. [PostgreSQL Standards](database/postgresql.md) — Naming, indexes, migrations
2. [Architecture Decisions](architecture/decisions.md) — Write an ADR
3. [Performance](performance/optimization.md) — Query optimization

### "I'm deploying to production"
1. [Docker Standards](infrastructure/docker.md) — Multi-stage builds, security
2. [AWS Deployment](cloud/aws.md) — ECS, RDS, ElastiCache
3. [Monitoring](monitoring/observability.md) — Logging, metrics, alerts
4. [Performance](performance/optimization.md) — Load testing

### "I'm investigating a performance issue"
1. [Performance Optimization](performance/optimization.md) — Profiling, optimization
2. [Caching Strategies](caching/strategies.md) — Multi-level caching
3. [Database Performance](database/postgresql.md) — Query optimization
4. [Scaling](scaling/strategies.md) — Horizontal/vertical scaling

### "I'm handling user data (PII)"
1. [Compliance](compliance/regulations.md) — GDPR, CCPA, data protection
2. [Security](security/owasp.md) — Encryption, access control
3. [Audit Logging](compliance/regulations.md#audit-logging) — Required for sensitive data

### "I'm building a payment feature"
1. [Compliance](compliance/regulations.md#pci-dss) — PCI DSS requirements
2. [Security](security/owasp.md) — Secure transaction handling
3. [Money Handling](shared/cross-cutting.md#money-and-currency) — Decimal precision

---

## Contributing

### Adding New Guidelines

1. **Identify the gap** — Is there a missing topic?
2. **Research** — Gather sources (LLM knowledge, internet, community)
3. **Draft** — Follow the structure of existing guidelines
4. **Review** — Get feedback from subject matter experts
5. **Update index** — Add to this README
6. **Reference** — Link from related guidelines

### Guideline Template

```markdown
# [Topic] Engineering Standards

> [One-line description]

## Table of Contents
1. [Section 1](#section-1)
...

## Section 1
[Content with code examples]

## Best Practices Summary
| ✅ DO | ❌ DON'T |
|---|---|
| [Practice] | [Anti-pattern] |

## References
- [External documentation]
```

### Updating Existing Guidelines

1. **Version the change** — Note updates with date
2. **Explain rationale** — Why the change?
3. **Provide migration path** — How to adopt?
4. **Update related guidelines** — Cross-references

---

## Statistics

- **Total guidelines:** 19 documents
- **Total size:** ~400 KB
- **Coverage:**
  - 3 programming languages (Python, TypeScript, Go)
  - 3 frameworks (FastAPI, Next.js, React)
  - 1 database (PostgreSQL)
  - 1 cloud provider (AWS)
  - 4 compliance frameworks (GDPR, SOC 2, HIPAA, PCI DSS, CCPA)
  - 12+ engineering domains

---

## Roadmap

### Planned Guidelines (On-Demand)

- **Mobile (React Native)** — When mobile app is added
- **GraphQL** — If/when GraphQL APIs are introduced
- **gRPC** — If/when service-to-service gRPC is added
- **Microservices Patterns** — If/when monorepo is split
- **Event Streaming (Kafka)** — If/when event streaming is added
- **Machine Learning Operations** — If/when ML is integrated
- **WebAssembly** — If/when WASM modules are added

### On-Demand Expansion

Guidelines are created on-demand based on:
- New product requirements
- Repeated issues in code reviews
- New team members' questions
- Compliance requirements
- Performance issues

---

## See Also

- [Main Engineering Documentation](../README.md)
- [Architecture Documentation](../architecture.md)
- [Product Plan](../product-plan.md)
- [Enhancement Roadmap](../../../Multi-Agent-Enhancement-Roadmap.md)
