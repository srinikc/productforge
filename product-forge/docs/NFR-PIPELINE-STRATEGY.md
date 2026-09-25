# NFR Pipeline Strategy for Product Forge

> **Date:** 2026-08-31
> **Question:** Should NFRs be done at a later stage, after validate and fix?
> **Answer:** NO. NFRs are continuous quality gates at EVERY stage, plus dedicated validation stages after fix.

---

## The Short Answer

**No, NFRs should NOT be deferred to "later stages".**

Here's why, based on how real enterprise products are built:

## How Enterprise Products Actually Handle NFRs

### Pattern 1: Continuous Quality Gates (Google, Amazon, Spotify)

**Not** "build the feature first, check NFRs later". Instead:
- **Design stage:** Define NFRs as specific measurable targets (e.g., "p95 < 500ms")
- **Implementation stage:** Build with NFRs in mind (use Redis, async, pagination from day 1)
- **Pre-launch stage:** Validate NFRs with load tests, security scans, a11y audits
- **Production:** Continuously monitor NFRs, alert on violations

**Why:** If you defer NFRs to the end, you'll have to rewrite the entire app. Adding Redis caching to a synchronous app means rewriting every endpoint.

### Pattern 2: Security Development Lifecycle (Microsoft SDL)

**Not** "build the feature, add security later". Instead:
- **Training:** All developers trained in secure coding
- **Design:** Threat modeling for every feature
- **Implementation:** Secure coding standards enforced
- **Verification:** Security testing in CI/CD
- **Release:** Final security review
- **Response:** Incident response plan ready

**Why:** Security is "built-in" not "bolted-on". Patching security holes in a released app is 10-100x more expensive than building it in.

### Pattern 3: Chaos Engineering (Netflix)

**Not** "test the happy path, ship to production". Instead:
- **Design:** Plan for failure modes
- **Implementation:** Circuit breakers, retries, fallbacks in code
- **Pre-launch:** Chaos testing (kill services randomly)
- **Production:** Continuous chaos testing (Chaos Monkey)
- **Post-incident:** New failure mode tests added

**Why:** Systems fail in production. You want to know how they fail BEFORE users find out.

### Pattern 4: SLOs and Error Budgets (Google SRE)

**Not** "100% uptime is the goal". Instead:
- **Design:** Define SLIs (e.g., request latency, error rate)
- **Implementation:** Build to meet SLOs
- **Pre-launch:** Validate SLOs with synthetic tests
- **Production:** Monitor SLIs, alert on SLO violations
- **Post-incident:** If error budget is consumed, freeze deploys

**Why:** 100% uptime is impossible and expensive. SLOs let you make data-driven trade-offs.

### Pattern 5: Continuous Deployment with Feature Flags (Facebook/Meta)

**Not** "big-bang release, hope it works". Instead:
- **Design:** Lightweight spec, NFRs as targets
- **Implementation:** Every feature behind a feature flag
- **Pre-launch:** Dark launch to internal users
- **Production:** Gradual rollout (1% → 10% → 50% → 100%)
- **Post-launch:** A/B test, measure, iterate

**Why:** Real users are the ultimate test. Roll back instantly if NFRs violated.

---

## The Right Pipeline Structure for NFRs

NFRs are NOT a "later stage". They are **continuous quality gates** PLUS **dedicated validation stages**.

### Stage-by-Stage NFR Treatment

```
Stage 0 (Ideation)
├─ NFR: Define MVP scope (don't over-promise)
└─ Decision: What NFRs are in-scope vs out-of-scope?

Stage 1 (Design)
├─ NFR: User-facing performance targets (<2s load, <300ms search)
├─ NFR: Accessibility UX (WCAG AA patterns)
├─ NFR: Error UX (empty states, loading states, error states)
├─ NFR: i18n UX (language selector, RTL support)
├─ NFR: Onboarding UX (first-run experience, tooltips, help)
└─ NFR: Mobile UX (touch targets, gestures, bottom nav)

Stage 2 (Architect)
├─ NFR: Caching architecture (HTTP, app, DB, CDN layers)
├─ NFR: Scalability architecture (horizontal scaling, sharding)
├─ NFR: Load handling (LB, auto-scaling, queue)
├─ NFR: Security architecture (encryption, auth, OWASP)
├─ NFR: Observability architecture (logs, metrics, tracing)
├─ NFR: Backup/DR architecture
├─ NFR: CI/CD architecture
├─ NFR: API versioning
├─ NFR: Rate limiting
└─ NFR: Multi-tenancy (if applicable)

Stage 3 (Review)
├─ NFR: All NFRs from design+architect are present
├─ NFR: No conflicting NFRs
└─ NFR: All NFRs have measurable targets

Stage 4 (Implement) - NFRs are CODE here
├─ NFR-1: Caching (Redis, HTTP cache headers, cache invalidation)
├─ NFR-2: Real error handling (no bare except, custom exceptions)
├─ NFR-3: Structured logging (JSON, correlation IDs, no PII)
├─ NFR-4: Rate limiting (token bucket, per-user, per-endpoint)
├─ NFR-5: Input validation (Pydantic on all requests)
├─ NFR-6: SQL injection prevention (SQLAlchemy ORM)
├─ NFR-7: Authentication (Depends(get_current_user))
├─ NFR-8: Health check endpoints (/health, /health/ready)
├─ NFR-9: Metrics endpoints (/metrics in Prometheus format)
├─ NFR-10: Email (SendGrid/SES, not raw SMTP)
├─ NFR-11: Mobile push (FCM + APNs, not polling)
├─ NFR-12: File upload (S3, not local filesystem)
├─ NFR-13: Search (PostgreSQL FTS, not LIKE)
├─ NFR-14: Time zones (UTC in DB)
├─ NFR-15: i18n (i18next, no hardcoded strings)
├─ NFR-16: Accessibility (semantic HTML, ARIA)
├─ NFR-17: Performance (indexes, no N+1, async I/O)
├─ NFR-18: API versioning (/api/v1/)
├─ NFR-19: Audit logging (all auth/data events)
└─ NFR-20: Feature flags (LaunchDarkly)

Stage 5 (Code Review)
├─ NFR: Verify each NFR is actually implemented (not just imported)
├─ NFR: No fake cache (real Redis)
├─ NFR: No bare except
├─ NFR: Logs are JSON, not print()
└─ NFR: All routes have auth, validation, rate limiting

Stage 6 (Validate)
├─ NFR: Run tests (unit + integration + E2E)
└─ NFR: All tests pass

NEW Stage 7a: Performance Validation
├─ NFR: Run load tests (k6, Locust)
├─ NFR: Measure p95 latency under load (must be < 500ms)
├─ NFR: Measure throughput (must be > 1000 RPS)
├─ NFR: Measure concurrent users (must be > 10K)
├─ NFR: If fails → BLOCK → go back to Stage 4

NEW Stage 7b: Security Audit
├─ NFR: Run OWASP ZAP scan
├─ NFR: Run Snyk/Trivy dependency scan
├─ NFR: Run secrets scan (no API keys in code)
├─ NFR: Penetration testing
├─ NFR: If critical findings → BLOCK → go to Stage 7 (Fix)

NEW Stage 7c: Accessibility Audit
├─ NFR: Run axe-core
├─ NFR: Run pa11y
├─ NFR: Run WAVE
├─ NFR: Manual screen reader test
├─ NFR: If WCAG AA fails → BLOCK → go to Stage 7 (Fix)

Stage 7 (Fix)
├─ Fix ALL NFR violations from Stages 7a, 7b, 7c
└─ Re-run 7a, 7b, 7c until clean

Stage 8 (Document)
├─ NFR: User docs (help articles per feature)
├─ NFR: API docs (auto-generated OpenAPI)
├─ NFR: Ops runbook (deployment, monitoring, incident response)
├─ NFR: Security disclosure policy
├─ NFR: Terms of Service, Privacy Policy
└─ NFR: SLA documentation

Stage 9 (Package)
├─ NFR: Docker images build
├─ NFR: Helm charts valid
├─ NFR: Mobile binaries (iOS .ipa, Android .aab)
├─ NFR: SBOM (CycloneDX)
├─ NFR: License attribution
├─ NFR: Install/upgrade/uninstall scripts tested
└─ NFR: Version follows SemVer, changelog generated

NEW Stage 10: Pre-Production Validation
├─ NFR: Full smoke test in staging
├─ NFR: All NFRs met (perf, security, a11y, load)
├─ NFR: All tests pass
└─ NFR: Ready for production gate

NEW Stage 11: Production Deployment
├─ NFR: Blue-green or canary deploy
├─ NFR: Feature flags for gradual rollout
├─ NFR: Monitoring configured
├─ NFR: Alerting configured
└─ NFR: Rollback capability verified

NEW Stage 12: Post-Production Monitoring
├─ NFR: SLO dashboards
├─ NFR: Error budget tracking
├─ NFR: Continuous chaos testing
└─ NFR: Post-incident reviews
```

---

## Why This Order Matters

### 1. Front-loading NFRs in Design/Architect prevents expensive rewrites

If you skip NFRs in design and architect:
- Stage 4 builds without caching → Stage 10 (perf test) finds p95 is 3s
- Now you have to rewrite every endpoint to add caching
- Cost: 2-3 weeks of work to fix what could have been 2 hours in design

If you put NFRs in design/architect:
- Stage 4 builds with Redis from day 1
- Stage 10 perf test passes
- Cost: 0 extra work

### 2. NFRs in Implement prevent "we'll add it later" debt

If you defer NFRs to "later":
- "We'll add caching later" → 6 months later, no caching, 10x DB load
- "We'll add rate limiting later" → DDoS takes down the service
- "We'll add audit logging later" → Compliance audit fails

If NFRs are in implement:
- Every endpoint has auth, validation, rate limiting from day 1
- Every query has indexes from day 1
- Every error is logged from day 1

### 3. Dedicated NFR validation stages (7a, 7b, 7c) are MANDATORY

Why separate stages for performance, security, a11y?
- They need different tools (k6 vs OWASP ZAP vs axe-core)
- They need different expertise
- They need to run AFTER functional code is done
- They BLOCK release if they fail

---

## The Updated Pipeline Stages

Current pipeline: 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 (10 stages)

**New pipeline: 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7a → 7b → 7c → 7 → 8 → 9 → 10 → 11 → 12 (16 stages)**

| Stage | Name | Purpose | NFR Focus |
|---|---|---|---|
| 0 | Ideation | Define scope, MVP | Decide NFR scope |
| 1 | Design | UX, components | UX NFRs (perf, a11y, i18n) |
| 2 | Architect | System design | System NFRs (cache, scale, security) |
| 3 | Review | Validate design | NFR conflicts, gaps |
| 4 | Implement | Write code | Code NFRs (all 20) |
| 5 | Code Review | Verify code | NFRs actually implemented |
| 6 | Validate | Run tests | Functional NFRs (tests pass) |
| **7a** | **Performance** | **Load tests** | **Perf NFRs (p95, RPS, concurrent)** |
| **7b** | **Security Audit** | **Pen test** | **Security NFRs (OWASP, secrets)** |
| **7c** | **Accessibility Audit** | **a11y tests** | **a11y NFRs (WCAG AA)** |
| 7 | Fix | Fix violations | Fix NFR violations |
| 8 | Document | User/ops docs | Doc NFRs (help, runbook) |
| 9 | Package | Docker, mobile | Package NFRs (install, SBOM) |
| **10** | **Pre-Production Validation** | **Final check** | **All NFRs verified** |
| **11** | **Production Deploy** | **Canary release** | **Deploy NFRs (gradual rollout)** |
| **12** | **Post-Production** | **Monitoring** | **Continuous NFR monitoring** |

---

## The Cost Comparison

| Approach | Time to Build | Time to Production | Issues Found |
|---|---|---|---|
| **NFRs at every stage (recommended)** | 3 weeks | 1 week | 0 critical (caught early) |
| **NFRs at "later stage" (anti-pattern)** | 2 weeks | 6+ weeks (rewrites) | 50+ critical (rework) |
| **No NFRs (what most startups do)** | 1 week | "Production broke" | Unknown (disaster) |

**Front-loading NFRs is FASTER and CHEAPER than back-loading them.**

---

## Concrete Example: Adding Caching

### Wrong Way (defer to "later")

```
Stage 4 (Implement): Build all endpoints WITHOUT caching
Stage 5 (Code Review): "Looks good, no mocks"
Stage 6 (Validate): All tests pass
Stage 7 (Fix): Nothing to fix
Stage 8 (Document): Write docs
Stage 9 (Package): Build images

NEW Stage 10 (Perf): Run load tests
  → p95 is 4.2s ❌ (target was 500ms)
  → All endpoints too slow

Fix: Add Redis caching to 20 endpoints
  → 2 weeks of work
  → Re-test everything
  → 2 more weeks

Total: 6 weeks to do what should have been 2 hours
```

### Right Way (NFRs at every stage)

```
Stage 1 (Design): "Search results must load in <300ms"
Stage 2 (Architect): "Use Redis cache for search, 5min TTL, invalidate on writes"
Stage 4 (Implement): Code includes `redis_client.get/set` from day 1
Stage 5 (Code Review): "Cache decorator used on all search endpoints ✓"
Stage 6 (Validate): Unit + integration tests pass
Stage 7a (Performance): Load test shows 280ms p95 ✓
Stage 7 (Fix): Nothing to fix (or minor optimizations)

Total: Same time, but production-ready from day 1
```

---

## The Decision: NFRs at Every Stage + Dedicated Validation Stages

I'll add:
1. **NFR requirements in Stages 1, 2, 3, 4, 5** (continuous quality gates)
2. **New Stages 7a (Performance), 7b (Security), 7c (Accessibility)** (dedicated validation)
3. **New Stages 10, 11, 12** (production deployment with NFR monitoring)

This matches industry practice (Google SRE, AWS Well-Architected, Microsoft SDL, Netflix Chaos, Spotify Golden Paths).

**No, NFRs should NOT be a single "later stage". They are continuous + dedicated validation.**
