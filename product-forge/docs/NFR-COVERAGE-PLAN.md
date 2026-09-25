# NFR Coverage Plan for Product Forge Pipeline

> **Date:** 2026-08-31
> **Issue:** Current pipeline only addresses 8 of 244 NFRs for a complete product
> **Solution:** Map NFRs to specific agents/stages

---

## Problem Statement

A complete product has **244+ NFRs across 57 categories**. The current pipeline only addresses 8 of them. This means most operational, performance, deployment, packaging, install/upgrade, versioning, and lifecycle concerns are NOT being handled.

## NFR Categories by Pipeline Stage

### Stage 1 (Design) - User Experience NFRs
**Scope:** What the user experiences

| NFR Category | What Design Does |
|---|---|
| Performance (page load, TTI) | Sets targets (<2s load, <300ms TTI) |
| Accessibility (WCAG AA) | Defines a11y patterns, ARIA labels |
| Internationalization | Design supports multi-language, RTL |
| Error UX | Design defines error states, empty states |
| Onboarding UX | Design defines first-run experience, tutorials |
| Help system | Design defines tooltips, in-app help |
| Notifications UX | Design defines notification patterns |
| Mobile UX | Design defines touch targets, gestures |

### Stage 2 (Architect) - System NFRs
**Scope:** System-level architecture decisions

| NFR Category | What Architect Does |
|---|---|
| Performance (architecture) | Caching strategy (Redis, CDN), DB indexing |
| Scalability | Horizontal scaling plan, sharding, read replicas |
| Load handling | Load balancer, auto-scaling, queue management |
| Caching | Cache layers (HTTP, app, DB, Redis) |
| Rendering | SSR/SSG/ISR strategy, streaming, hydration |
| Reliability | Circuit breakers, retries, fallbacks |
| Availability | Multi-AZ, failover, health checks |
| Security (architecture) | Encryption, auth, OWASP, secret management |
| Privacy (architecture) | Data isolation, encryption, GDPR |
| Compliance | SOC 2, HIPAA, PCI, GDPR design |
| Observability | Logging, metrics, tracing architecture |
| API design | REST conventions, OpenAPI, versioning |
| Email/notifications | Provider choice, template system |
| Search architecture | Search engine choice (PG FTS, ES, Meilisearch) |
| Mobile architecture | RN setup, offline sync, push |
| Cost | Infrastructure cost estimates |
| Backup/DR | Backup strategy, RTO/RPO |
| Migration plan | Zero-downtime migration strategy |
| Data retention | Retention policies, archival |
| Rate limiting | Token bucket, per-user limits |
| API versioning | URL versioning (/api/v1/) |
| Error handling | Error categories, retry logic |
| Logging | Structured logs, log levels, retention |
| Monitoring | Health checks, alerting |
| Feature flags | LaunchDarkly or similar |
| Multi-tenancy | Tenant isolation, RLS |
| Dependency management | Pinned versions, vulnerability scanning |
| License management | SBOM, third-party licenses |
| API Versioning | URL or header versioning |

### Stage 3 (Review) - Validation
**Scope:** Verify all NFRs from Design + Architect are covered

| NFR Check | What Review Does |
|---|---|
| All FRs have NFRs | Check traceability |
| All NFRs have measurable targets | Validate targets are specific |
| All NFRs have measurement methods | Validate how to verify |
| Conflicts identified | Find conflicting NFRs |
| Missing NFRs identified | Check for gaps |

### Stage 4 (Implement) - Implementation NFRs
**Scope:** Code-level NFRs

| NFR Category | What Implement Does |
|---|---|
| Caching | Implement Redis cache layer, HTTP cache headers |
| Rendering | Implement SSR pages, streaming responses |
| Email/notifications | Implement SendGrid integration, push notifications |
| Mobile | Implement offline sync, push handlers |
| Search | Implement full-text search, ranking |
| Rate limiting | Implement token bucket, per-endpoint limits |
| API versioning | Implement /api/v1/ routes |
| Error handling | Implement error classes, retry logic |
| Logging | Implement structured logging, correlation IDs |
| Monitoring | Implement health checks, metrics endpoints |
| Feature flags | Implement LaunchDarkly integration |
| Multi-tenancy | Implement RLS, tenant context middleware |
| Audit logging | Implement audit event recording |
| Code quality | Linting, type checking, test coverage |
| Performance (code) | Implement indexes, optimized queries |
| Security (code) | Implement input validation, parameterized queries |

### Stage 5 (Code Review) - Code-Level Validation
**Scope:** Verify code-level NFRs are properly implemented

| NFR Check | What Code Review Does |
|---|---|
| Caching actually used | Check Redis imports, cache decorators |
| Real error handling | Check no bare `except:` |
| Structured logging | Check JSON log format |
| Rate limiting in place | Check middleware, decorators |
| Input validation | Check Pydantic usage |
| SQL injection safe | Check parameterized queries |
| XSS safe | Check React escaping, CSP headers |
| Auth on all endpoints | Check middleware |
| Tests exist | Check test files, coverage |

### Stage 6 (Validate) - Runtime NFRs
**Scope:** Verify runtime behavior meets NFRs

| NFR Category | What Validate Does |
|---|---|
| Performance (runtime) | Run load tests, measure latency |
| Load testing | Use k6, Locust, or JMeter |
| Accessibility (testing) | Run axe, pa11y, screen reader tests |
| Browser compatibility | Run cross-browser tests |
| API contract | Run contract tests, schema validation |
| Security scanning | Run OWASP ZAP, Snyk, Trivy |
| Visual regression | Run Percy or similar |
| E2E flows | Run Playwright tests |

### Stage 7 (Fix) - Fix NFR Violations
**Scope:** Fix any NFR issues found in validation

### Stage 8 (Document) - Document NFRs
**Scope:** User-facing and ops docs

| NFR Category | What Document Does |
|---|---|
| API documentation | OpenAPI, integration guides |
| User documentation | Help articles, tutorials, FAQ |
| Operations runbook | Deployment, monitoring, incident response |
| Security disclosure | Responsible disclosure policy |
| Terms of Service | Legal terms |
| Privacy policy | Data handling, GDPR compliance |
| SLA documentation | Uptime guarantees, support response |
| Architecture docs | ADRs, diagrams, design decisions |
| Contribution guide | How to contribute code |
| Code of conduct | Community standards |

### Stage 9 (Package) - Distribution NFRs
**Scope:** Packaging and distribution

| NFR Category | What Package Does |
|---|---|
| Install | One-command install, dependencies |
| Uninstall | Clean removal, data cleanup |
| Upgrade | Version migration, backwards compat |
| Versioning | SemVer, breaking change docs |
| Packaging | Docker, Helm, OS packages, mobile binaries |
| Distribution | App stores, package registries |
| SBOM | Software Bill of Materials |
| License files | Third-party license compliance |
| Checksums | Verify package integrity |
| Signatures | Cryptographic signing |

---

## New Stages to Add

To properly address NFRs, the pipeline needs ADDITIONAL stages beyond the current 0-9:

### Stage 10: Performance & Load (after Stage 9)
- Run load tests (k6, Locust)
- Measure latency under load
- Generate performance report
- Identify bottlenecks

### Stage 11: Security Audit (after Stage 6)
- Run OWASP ZAP, Snyk, Trivy
- Penetration testing
- Generate security report
- Fix vulnerabilities

### Stage 12: Accessibility Audit (after Stage 4)
- Run axe, pa11y
- Screen reader testing
- Generate a11y report

### Stage 13: Release (after Stage 9)
- Generate changelog
- Create release notes
- Tag git
- Publish to distribution

### Stage 14: Operations Setup (after Stage 9)
- Configure monitoring
- Setup alerting
- Create runbooks
- Configure backups

---

## Immediate Fix: Update Existing Stages

Even without new stages, we MUST update the current stages to address the most critical missing NFRs.

### Stage 1 (Design) - ADD:
- Help system patterns
- Error UX states
- Empty states
- Loading states
- Onboarding flow

### Stage 2 (Architect) - ADD:
- Caching architecture
- Load balancing
- Backup/DR strategy
- Migration plan
- API versioning
- Rate limiting
- CI/CD architecture
- Email/notifications
- Mobile architecture
- Feature flags
- Multi-tenancy (if applicable)
- Audit logging

### Stage 4 (Implement) - ADD:
- All architectural decisions must be implemented
- Real caching code (Redis)
- Real error handling
- Real logging
- Real monitoring
- Real rate limiting
- Real feature flags

---

## Configuration

Create a system-level NFR config: `products/.pipeline/nfr-checklist.json`

```json
{
  "version": "1.0",
  "categories": {
    "performance": {
      "stage": "design+architect+implement",
      "must_address": [
        "Page load < 2s",
        "API p95 < 500ms",
        "DB query < 100ms"
      ]
    },
    "scalability": {
      "stage": "architect+implement",
      "must_address": [
        "Horizontal scaling plan",
        "DB connection pooling",
        "Stateless API servers"
      ]
    },
    "load": {
      "stage": "architect+implement+validate",
      "must_address": [
        "Load test before launch",
        "Target: N concurrent users",
        "Auto-scaling triggers"
      ]
    },
    "caching": {
      "stage": "architect+implement",
      "must_address": [
        "HTTP cache headers",
        "Redis for hot data",
        "CDN for static assets"
      ]
    },
    "rendering": {
      "stage": "design+implement",
      "must_address": [
        "Server Components for SEO",
        "Streaming for long pages",
        "Suspense boundaries"
      ]
    },
    "security": {
      "stage": "architect+implement+security-audit",
      "must_address": [
        "OWASP Top 10 coverage",
        "Encryption at rest + in transit",
        "Rate limiting",
        "Audit logging"
      ]
    },
    "accessibility": {
      "stage": "design+implement+a11y-audit",
      "must_address": [
        "WCAG 2.1 AA",
        "Keyboard navigation",
        "Screen reader support"
      ]
    },
    "i18n": {
      "stage": "design+implement",
      "must_address": [
        "i18next or similar",
        "RTL support",
        "Currency/timezone handling"
      ]
    },
    "privacy": {
      "stage": "architect+implement",
      "must_address": [
        "GDPR data export",
        "Right to be forgotten",
        "Consent management"
      ]
    },
    "observability": {
      "stage": "architect+implement",
      "must_address": [
        "Structured JSON logging",
        "Prometheus metrics",
        "Distributed tracing"
      ]
    },
    "testing": {
      "stage": "implement+validate",
      "must_address": [
        "Unit tests > 80%",
        "Integration tests for all APIs",
        "E2E for critical flows"
      ]
    },
    "documentation": {
      "stage": "document",
      "must_address": [
        "API docs (OpenAPI)",
        "User help articles",
        "Architecture docs"
      ]
    },
    "deployment": {
      "stage": "architect+package",
      "must_address": [
        "CI/CD pipeline",
        "Blue-green or canary",
        "Rollback capability"
      ]
    },
    "packaging": {
      "stage": "package",
      "must_address": [
        "Docker images",
        "Helm charts",
        "Mobile binaries"
      ]
    },
    "install": {
      "stage": "package+document",
      "must_address": [
        "One-command install",
        "Clear upgrade path",
        "Data migration scripts"
      ]
    },
    "versioning": {
      "stage": "architect+package",
      "must_address": [
        "SemVer for releases",
        "API URL versioning",
        "Deprecation policy"
      ]
    },
    "ci_cd": {
      "stage": "architect+package",
      "must_address": [
        "GitHub Actions workflows",
        "Automated tests in CI",
        "Auto-deploy to staging"
      ]
    },
    "help_system": {
      "stage": "design+implement+document",
      "must_address": [
        "In-app tooltips",
        "Onboarding tour",
        "Help center"
      ]
    },
    "backup": {
      "stage": "architect+package",
      "must_address": [
        "Daily DB backups",
        "Cross-region backup",
        "Restore tested monthly"
      ]
    }
  }
}
```

This checklist is validated at:
- Stage 3 (Review) - verify all must_address are covered in design+architect
- Stage 5 (Code Review) - verify code-level NFRs are implemented
- Stage 6 (Validate) - verify runtime NFRs meet targets
- Stage 8 (Document) - verify docs cover NFRs
- Stage 9 (Package) - verify packaging NFRs

---

## Summary

| NFR Category | Where Handled | Agent |
|---|---|---|
| UX NFRs (perf targets, a11y, i18n UX) | Stage 1 | design |
| System NFRs (scaling, security arch, caching arch) | Stage 2 | architect |
| Code NFRs (real caching, real logging, real validation) | Stage 4 | implement |
| Code review NFRs (no mocks, no shortcuts) | Stage 5 | code-review |
| Runtime NFRs (load tests, security scans) | Stage 6 | validate |
| Doc NFRs (user docs, ops runbooks) | Stage 8 | document |
| Package NFRs (Docker, install, upgrade) | Stage 9 | package |
| Performance NFRs (load tests) | NEW Stage 10 | performance |
| Security NFRs (pen test) | NEW Stage 11 | security |
| Accessibility NFRs (a11y audit) | NEW Stage 12 | accessibility |
| Release NFRs (changelog, tags) | NEW Stage 13 | release |
| Ops NFRs (monitoring, backups) | NEW Stage 14 | operations |
