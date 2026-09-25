# AI Product Factory — Master Product & Engineering Checklist
Version: 1.0
Status: Factory baseline
Purpose: Prevent omissions by giving every relevant agent its applicable obligations before execution and by independently verifying the resulting evidence.

---

## 0. Factory Doctrine

The Factory is responsible for producing a **useful, correct, secure, maintainable, deployable, commercially viable product**, not merely code that compiles.

### Non-negotiable rules

- [ ] No implementation before sufficient product/design/architecture decisions exist.
- [ ] Every material requirement has an acceptance criterion.
- [ ] Every acceptance criterion has an implementation path and verification evidence.
- [ ] Agents receive their applicable checklist **before** doing work.
- [ ] Agents receive the skills/knowledge required for their responsibility before doing work.
- [ ] Agents do not define their own success conditions.
- [ ] Claims of completion require evidence.
- [ ] Deterministic checks are automated whenever practical.
- [ ] Independent verification uses a different model/context from the maker when risk warrants it.
- [ ] Critical failures block progression.
- [ ] Unknown is not equivalent to pass.
- [ ] Not-applicable and deferred items require explicit rationale.
- [ ] Exceptions are recorded, scoped, approved, and reviewable.
- [ ] The final release decision is made by the Factory quality gates, not by the implementation agent.
- [ ] The Factory continuously learns from defects, failed checks, incidents, and customer outcomes.

---

# 1. Checklist Model

Every checklist item should have:

```yaml
id: UI-A11Y-001
domain: ui
severity: high
applies_when: ...
requirement: ...
expected_evidence: ...
verification:
  - automated
  - static
  - dynamic
  - expert_review
block_release: true
```

### Statuses

- `PASS` — verified with evidence.
- `FAIL` — evidence demonstrates non-compliance.
- `UNKNOWN` — insufficient evidence; never silently pass.
- `N/A` — genuinely not applicable, with reason.
- `DEFERRED` — intentionally postponed, with owner/milestone/risk.
- `EXCEPTION` — approved deviation with scope and expiry.
- `NOT_STARTED` — no work/evidence yet.

### Severity

- `BLOCKER` — cannot proceed/release.
- `CRITICAL` — normally blocks release; only explicit high-authority exception can override.
- `HIGH` — blocks the relevant gate unless explicitly waived.
- `MEDIUM` — should be fixed before release or tracked with accepted risk.
- `LOW` — improvement/cleanup; does not normally block.

---

# 2. Agent Input Contract

Every agent invocation must be assembled from:

1. Mission and authority.
2. Product context.
3. Relevant requirements.
4. Relevant prior artifacts.
5. Applicable domain knowledge.
6. Applicable skills.
7. Technology-stack knowledge.
8. Applicable checklist subset.
9. Coding/design/business/security standards.
10. Constraints and non-goals.
11. Required output artifacts.
12. Evidence requirements.
13. Known risks and open decisions.
14. Allowed tools.
15. Model/risk tier.

### Agent completion package

Every producing agent returns:

- [ ] Work product/artifact.
- [ ] Checklist status for every applicable item.
- [ ] Evidence references.
- [ ] Tests/checks run.
- [ ] Decisions made.
- [ ] Assumptions.
- [ ] Risks.
- [ ] Open questions.
- [ ] N/A/deferred/exception items with reasons.
- [ ] Suggested follow-up tasks.
- [ ] Traceability links to requirements.

---

# 3. Master Lifecycle

```text
IDEA
 ↓
Discovery
 ↓
Market / Customer / Domain Research
 ↓
Product Strategy
 ↓
Business Model
 ↓
Requirements
 ↓
UX / Product Design
 ↓
Technical Architecture
 ↓
Security / Privacy / Compliance Design
 ↓
Implementation Plan
 ↓
Task Graph
 ↓
Implementation
 ↓
Automated Validation
 ↓
Specialist Reviews
 ↓
Integration / E2E
 ↓
Performance / Security / Accessibility
 ↓
Product / UX / Business Review
 ↓
Release Readiness
 ↓
Packaging
 ↓
Staging
 ↓
Production Deployment
 ↓
Production Verification
 ↓
Observability / Operations
 ↓
Customer Feedback / Outcomes
 ↓
Maintenance / Learning
 ↓
Factory Improvement
```

---

# 4. Discovery & Problem Definition

- [ ] Problem statement is specific.
- [ ] Problem is based on evidence rather than assumption.
- [ ] Target user is defined.
- [ ] Primary user/job is defined.
- [ ] Secondary users are identified.
- [ ] Buyer and user are distinguished where different.
- [ ] Current workflow is understood.
- [ ] Existing workaround is understood.
- [ ] Cost of the current problem is understood.
- [ ] Frequency of the problem is understood.
- [ ] Severity/urgency is understood.
- [ ] Trigger events are identified.
- [ ] Desired outcome is defined.
- [ ] Jobs-to-be-done are documented.
- [ ] User pain points are documented.
- [ ] User motivations are documented.
- [ ] User constraints are documented.
- [ ] Environmental/contextual constraints are documented.
- [ ] Alternatives and competitors are known.
- [ ] Why-now factor is understood.
- [ ] Key assumptions are explicit.
- [ ] Unknowns are explicit.
- [ ] Risks are explicit.
- [ ] Research gaps are identified.
- [ ] Discovery evidence is stored.
- [ ] Contradictory evidence is surfaced.
- [ ] Problem is worth solving is justified.
- [ ] Problem is not merely a technology looking for a use case.
- [ ] Non-problems and out-of-scope needs are documented.

---

# 5. Customer & User Research

- [ ] Relevant user segments identified.
- [ ] ICP identified where applicable.
- [ ] Personas are evidence-based.
- [ ] User journeys mapped.
- [ ] Current-state workflow mapped.
- [ ] Pain points ranked.
- [ ] Desired outcomes ranked.
- [ ] Frequency and volume estimated.
- [ ] Willingness-to-pay signals investigated.
- [ ] Adoption barriers investigated.
- [ ] Switching costs investigated.
- [ ] Trust requirements investigated.
- [ ] Accessibility needs investigated.
- [ ] Mobile/device/environment constraints investigated.
- [ ] User language/terminology captured.
- [ ] Stakeholder conflicts identified.
- [ ] Research source provenance recorded.
- [ ] Findings separated from interpretation.
- [ ] Interpretation separated from assumptions.
- [ ] Research confidence recorded.
- [ ] Research is not presented as certainty where evidence is weak.

---

# 6. Domain Expertise

- [ ] Domain vocabulary established.
- [ ] Core domain entities identified.
- [ ] Domain relationships identified.
- [ ] Domain workflows mapped.
- [ ] Domain actors/roles identified.
- [ ] Domain state transitions identified.
- [ ] Business rules documented.
- [ ] Domain invariants documented.
- [ ] Exceptions documented.
- [ ] Regulatory requirements identified.
- [ ] Industry standards identified.
- [ ] Common professional practices identified.
- [ ] Domain-specific calculations verified.
- [ ] Domain-specific units/formats verified.
- [ ] Domain-specific dates/time rules verified.
- [ ] Jurisdiction differences identified.
- [ ] Domain expert assumptions marked.
- [ ] Domain sources have provenance.
- [ ] Conflicting domain sources are reconciled.
- [ ] High-risk domain claims receive expert/authoritative verification.
- [ ] Domain knowledge is converted into reusable skills where appropriate.

---

# 7. Product Strategy

- [ ] Product vision defined.
- [ ] Target segment defined.
- [ ] Positioning defined.
- [ ] Value proposition defined.
- [ ] Differentiation defined.
- [ ] Core use cases prioritized.
- [ ] Non-goals defined.
- [ ] MVP boundary defined.
- [ ] Future scope separated.
- [ ] Product principles documented.
- [ ] Product success metrics defined.
- [ ] Leading indicators defined.
- [ ] Lagging indicators defined.
- [ ] North-star metric defined where useful.
- [ ] Risks to adoption identified.
- [ ] Risks to retention identified.
- [ ] Product-market assumptions documented.
- [ ] Competitive alternatives considered.
- [ ] Build-vs-buy decisions considered.
- [ ] Product trade-offs recorded.

---

# 8. Business Model & Economics

- [ ] Revenue model defined.
- [ ] Pricing model defined.
- [ ] Packaging defined.
- [ ] Free/trial strategy defined where applicable.
- [ ] Usage metric defined where applicable.
- [ ] Unit economics estimated.
- [ ] CAC assumptions documented.
- [ ] LTV assumptions documented.
- [ ] Gross margin estimated.
- [ ] Infrastructure cost estimated.
- [ ] AI/model cost estimated.
- [ ] Third-party API costs estimated.
- [ ] Support/operations costs estimated.
- [ ] Customer onboarding cost considered.
- [ ] Churn risk considered.
- [ ] Expansion/upsell path considered.
- [ ] Discount policy considered.
- [ ] Enterprise requirements considered where applicable.
- [ ] Cost abuse scenarios considered.
- [ ] Margin under realistic usage tested.
- [ ] Pricing aligns with customer value.
- [ ] Pricing does not depend on impossible assumptions.
- [ ] Business risks are explicit.

---

# 9. Marketing

- [ ] ICP messaging defined.
- [ ] Positioning statement defined.
- [ ] Core value proposition defined.
- [ ] Messaging hierarchy defined.
- [ ] Primary claims supported by evidence.
- [ ] Competitive differentiation is defensible.
- [ ] Landing-page information architecture defined.
- [ ] Conversion path defined.
- [ ] CTA strategy defined.
- [ ] Acquisition channels identified.
- [ ] SEO opportunity assessed where relevant.
- [ ] Content strategy assessed where relevant.
- [ ] Referral/viral loops considered where relevant.
- [ ] Attribution requirements defined.
- [ ] Analytics events mapped.
- [ ] Marketing promises match actual product capability.
- [ ] Pricing shown consistently.
- [ ] Legal/compliance constraints on claims reviewed.
- [ ] Launch plan defined.
- [ ] Post-launch learning loop defined.

---

# 10. Sales

- [ ] Buyer identified.
- [ ] User identified.
- [ ] Economic buyer identified where applicable.
- [ ] Buying committee identified where applicable.
- [ ] Qualification criteria defined.
- [ ] Sales motion defined.
- [ ] Self-serve vs sales-assisted decision made.
- [ ] Demo journey defined.
- [ ] Objections identified.
- [ ] Competitive objections identified.
- [ ] Security/procurement objections identified.
- [ ] Pricing objections identified.
- [ ] Implementation objections identified.
- [ ] Proof/ROI requirements identified.
- [ ] Sales collateral requirements identified.
- [ ] CRM requirements identified where applicable.
- [ ] Lead lifecycle defined.
- [ ] Pipeline stages defined.
- [ ] Conversion metrics defined.
- [ ] Handoff from sales to onboarding defined.
- [ ] Handoff from onboarding to support/customer success defined.

---

# 11. Requirements

- [ ] Functional requirements complete.
- [ ] Non-functional requirements complete.
- [ ] Requirements uniquely identified.
- [ ] Requirements are testable.
- [ ] Acceptance criteria exist.
- [ ] Edge cases identified.
- [ ] Negative cases identified.
- [ ] Failure behavior defined.
- [ ] Permission requirements defined.
- [ ] Role requirements defined.
- [ ] Data requirements defined.
- [ ] Integration requirements defined.
- [ ] Performance requirements defined.
- [ ] Availability requirements defined.
- [ ] Security requirements defined.
- [ ] Privacy requirements defined.
- [ ] Accessibility requirements defined.
- [ ] Localization requirements defined where applicable.
- [ ] Analytics requirements defined.
- [ ] Audit requirements defined where applicable.
- [ ] Migration requirements defined where applicable.
- [ ] Backward compatibility requirements defined.
- [ ] Deletion/retention requirements defined.
- [ ] Operational requirements defined.
- [ ] Requirements have owners.
- [ ] Requirements have priority.
- [ ] Ambiguities resolved or explicitly tracked.

---

# 12. Requirement Traceability

Every material feature should support:

```text
GOAL → REQUIREMENT → ACCEPTANCE CRITERION → DESIGN
→ TASK → CODE → TEST → REVIEW → EVIDENCE
```

Checklist:

- [ ] Every goal maps to requirements.
- [ ] Every requirement maps to acceptance criteria.
- [ ] Every acceptance criterion maps to design.
- [ ] Every acceptance criterion maps to implementation tasks.
- [ ] Every implemented requirement maps to code/artifacts.
- [ ] Every critical criterion maps to tests.
- [ ] Every critical criterion maps to verification evidence.
- [ ] Orphan requirements are detected.
- [ ] Orphan implementation is detected.
- [ ] Tests without requirement purpose are identified where appropriate.
- [ ] Changed requirements trigger impact analysis.
- [ ] Requirement changes invalidate stale verification where necessary.

---

# 13. UX / Information Architecture

- [ ] Information architecture defined.
- [ ] Navigation hierarchy defined.
- [ ] User flows defined.
- [ ] Critical path identified.
- [ ] Primary action identified.
- [ ] Secondary actions identified.
- [ ] Information priority established.
- [ ] Content hierarchy established.
- [ ] Terminology matches users/domain.
- [ ] Search behavior defined where relevant.
- [ ] Filtering behavior defined where relevant.
- [ ] Sorting behavior defined where relevant.
- [ ] Pagination/infinite-scroll decision made.
- [ ] Empty states designed.
- [ ] Loading states designed.
- [ ] Error states designed.
- [ ] Success states designed.
- [ ] Partial failure states designed.
- [ ] Offline behavior defined where relevant.
- [ ] Confirmation behavior defined.
- [ ] Undo behavior considered.
- [ ] Destructive actions protected.
- [ ] Form flows defined.
- [ ] Validation behavior defined.
- [ ] Recovery paths defined.
- [ ] Onboarding defined.
- [ ] Help/discovery affordances considered.
- [ ] User feedback mechanisms considered.
- [ ] User journey can be completed without accidental dead ends.

---

# 14. UI / Visual Design

- [ ] Design system selected/created.
- [ ] Design tokens defined.
- [ ] Typography system defined.
- [ ] Color system defined.
- [ ] Spacing system defined.
- [ ] Grid/layout system defined.
- [ ] Breakpoints defined.
- [ ] Component library defined.
- [ ] Component variants defined.
- [ ] Component states defined.
- [ ] Iconography consistent.
- [ ] Visual hierarchy is intentional.
- [ ] Primary actions have appropriate emphasis.
- [ ] Secondary actions do not compete with primary actions.
- [ ] Density matches task.
- [ ] Content is readable.
- [ ] Tables remain usable at relevant widths.
- [ ] Charts communicate intended meaning.
- [ ] Color has semantic consistency.
- [ ] Color is not the sole information carrier.
- [ ] Dark mode designed where applicable.
- [ ] Motion/animation has purpose.
- [ ] Animation can be reduced/disabled where required.
- [ ] No accidental visual inconsistency.
- [ ] Actual rendered UI is inspected, not only source code.

---

# 15. Accessibility

- [ ] Semantic HTML used where applicable.
- [ ] Keyboard navigation works.
- [ ] Focus is visible.
- [ ] Focus order is logical.
- [ ] Focus is managed after dialogs/navigation.
- [ ] Screen-reader labels are meaningful.
- [ ] Images have appropriate alternatives.
- [ ] Decorative images are excluded appropriately.
- [ ] Form fields have labels.
- [ ] Validation errors are accessible.
- [ ] Status updates are announced appropriately.
- [ ] Dialogs are accessible.
- [ ] Menus are accessible.
- [ ] Tooltips are accessible.
- [ ] Touch targets are adequate.
- [ ] Contrast is adequate.
- [ ] Color is not sole semantic signal.
- [ ] Motion sensitivity is respected.
- [ ] Zoom/reflow behavior is usable.
- [ ] Accessibility is tested with automation and representative manual review.
- [ ] Applicable WCAG target is explicitly selected.

---

# 16. Responsive / Device Experience

- [ ] Mobile layout defined.
- [ ] Tablet layout defined.
- [ ] Desktop layout defined.
- [ ] Large-screen behavior defined.
- [ ] Breakpoint transitions tested.
- [ ] Overflow handled.
- [ ] Horizontal scrolling is intentional.
- [ ] Touch interactions work.
- [ ] Hover-only functionality has alternatives.
- [ ] Virtual keyboard behavior considered.
- [ ] Orientation changes considered.
- [ ] Small viewport heights considered.
- [ ] Slow network behavior considered.
- [ ] Low-power/mobile constraints considered where relevant.

---

# 17. Frontend Architecture

- [ ] Framework version pinned/controlled.
- [ ] Component boundaries intentional.
- [ ] Server/client boundaries intentional.
- [ ] State ownership is clear.
- [ ] Global state is justified.
- [ ] Local state is preferred when sufficient.
- [ ] Derived state is not unnecessarily duplicated.
- [ ] Data fetching strategy defined.
- [ ] Cache/revalidation strategy defined.
- [ ] Error boundaries defined.
- [ ] Loading boundaries defined.
- [ ] Form architecture defined.
- [ ] Validation centralized where appropriate.
- [ ] Routing is coherent.
- [ ] URL state used where appropriate.
- [ ] Deep links work.
- [ ] Back/forward behavior works.
- [ ] Browser refresh behavior works.
- [ ] Race conditions considered.
- [ ] Request cancellation considered.
- [ ] Memory leaks considered.
- [ ] Event listeners cleaned up.
- [ ] Timers/subscriptions cleaned up.
- [ ] Bundle splitting used appropriately.
- [ ] Lazy loading used appropriately.
- [ ] Images optimized.
- [ ] Fonts optimized.
- [ ] Unnecessary dependencies avoided.

---

# 18. Rendering

- [ ] Rendering strategy explicitly selected.
- [ ] SSR/SSG/ISR/CSR choice justified where relevant.
- [ ] Server/client component choice justified where relevant.
- [ ] Hydration behavior verified.
- [ ] Hydration mismatches eliminated.
- [ ] Streaming considered where useful.
- [ ] Suspense/loading behavior intentional.
- [ ] SEO rendering requirements satisfied where relevant.
- [ ] Metadata is correct.
- [ ] Cache/revalidation behavior understood.
- [ ] Dynamic rendering is intentional.
- [ ] Static rendering is not used where data freshness requires dynamic behavior.
- [ ] Client rendering is not used unnecessarily.
- [ ] Render waterfalls are identified.
- [ ] Actual rendered output is tested.

---

# 19. API Design

- [ ] API style selected consistently.
- [ ] Resource/model naming consistent.
- [ ] HTTP semantics correct where REST is used.
- [ ] Request schemas defined.
- [ ] Response schemas defined.
- [ ] Validation defined.
- [ ] Error model defined.
- [ ] Status codes correct.
- [ ] Pagination defined.
- [ ] Filtering defined.
- [ ] Sorting defined.
- [ ] Search defined where applicable.
- [ ] Versioning strategy defined.
- [ ] Deprecation strategy defined.
- [ ] Idempotency defined for retryable mutations.
- [ ] Timeouts defined.
- [ ] Retry policy defined.
- [ ] Rate limiting defined.
- [ ] Request size limits defined.
- [ ] Response size considerations addressed.
- [ ] Authentication enforced.
- [ ] Authorization enforced.
- [ ] Tenant isolation enforced where applicable.
- [ ] CORS configured intentionally.
- [ ] CSRF protections addressed where applicable.
- [ ] API documentation generated/maintained.
- [ ] OpenAPI/schema is synchronized with implementation where applicable.
- [ ] Backward compatibility checked.
- [ ] API contract tests exist for important contracts.

---

# 20. Business Logic / Domain Logic

- [ ] Business rules explicitly modeled.
- [ ] Domain invariants enforced.
- [ ] Preconditions enforced.
- [ ] Postconditions enforced.
- [ ] State transitions are valid.
- [ ] Invalid state transitions rejected.
- [ ] Calculations are independently verified.
- [ ] Boundary conditions tested.
- [ ] Time/date logic tested.
- [ ] Time zones handled intentionally.
- [ ] Currency/precision rules handled correctly.
- [ ] Rounding rules defined.
- [ ] Duplicate operations handled.
- [ ] Idempotency handled.
- [ ] Concurrency handled.
- [ ] Transaction boundaries are correct.
- [ ] Authorization is enforced at the business-operation boundary.
- [ ] UI is not the only place enforcing business rules.
- [ ] API is not the only place enforcing critical domain invariants where deeper enforcement is required.
- [ ] Business logic is testable independently of UI.
- [ ] Business rules are traceable to requirements/domain evidence.

---

# 21. Database

- [ ] Data model reviewed.
- [ ] Tables/entities justified.
- [ ] Primary keys defined.
- [ ] Foreign keys defined.
- [ ] Unique constraints defined.
- [ ] Check constraints defined where useful.
- [ ] Nullability intentional.
- [ ] Defaults intentional.
- [ ] Indexes match actual query patterns.
- [ ] Composite indexes considered.
- [ ] Index bloat considered.
- [ ] N+1 queries avoided.
- [ ] Query plans inspected for critical paths.
- [ ] Transactions defined.
- [ ] Isolation requirements understood.
- [ ] Race conditions considered.
- [ ] Deadlocks considered.
- [ ] Connection pooling configured.
- [ ] Connection limits considered.
- [ ] Migrations versioned.
- [ ] Migrations are reproducible.
- [ ] Migrations tested.
- [ ] Rollback/forward recovery strategy defined.
- [ ] Large-table migration strategy defined.
- [ ] Seed/fixture strategy defined.
- [ ] Backup strategy defined.
- [ ] Restore tested.
- [ ] Retention defined.
- [ ] Archival defined where needed.
- [ ] Deletion strategy defined.
- [ ] PII/data classification defined.
- [ ] Audit fields defined where required.
- [ ] Multi-tenant isolation enforced where applicable.

---

# 22. Caching

For every significant cache:

- [ ] Why cache exists is documented.
- [ ] Cacheable data identified.
- [ ] Non-cacheable data identified.
- [ ] Cache key defined.
- [ ] Key includes required tenant/user dimensions.
- [ ] TTL defined.
- [ ] Freshness requirement defined.
- [ ] Invalidation strategy defined.
- [ ] Stale-data behavior defined.
- [ ] Cache miss behavior works.
- [ ] Cache outage behavior works.
- [ ] Cache stampede considered.
- [ ] Cache penetration considered.
- [ ] Cache poisoning considered.
- [ ] Memory limits considered.
- [ ] Eviction policy understood.
- [ ] Authorization is not bypassed by caching.
- [ ] Sensitive data is not accidentally shared.
- [ ] Distributed consistency expectations documented.
- [ ] Cache metrics exist where operationally important.
- [ ] Cache is not added merely because it is fashionable.

---

# 23. Integrations / External Services

- [ ] Each external dependency has an owner.
- [ ] Dependency purpose documented.
- [ ] SLA/availability considered.
- [ ] Authentication method documented.
- [ ] Secrets managed securely.
- [ ] Timeout defined.
- [ ] Retry defined.
- [ ] Backoff defined.
- [ ] Idempotency handled.
- [ ] Rate limits understood.
- [ ] Quotas understood.
- [ ] Failure behavior defined.
- [ ] Circuit breaking considered.
- [ ] Fallback considered.
- [ ] Data mapping documented.
- [ ] Schema changes considered.
- [ ] Webhook authenticity verified.
- [ ] Duplicate webhooks handled.
- [ ] Ordering assumptions documented.
- [ ] Third-party costs monitored.
- [ ] Vendor lock-in assessed where material.
- [ ] Terms/license restrictions reviewed.
- [ ] Integration tests exist where important.

---

# 24. Authentication & Identity

- [ ] Authentication mechanism selected.
- [ ] Password policy defined where passwords exist.
- [ ] Passwords are never stored reversibly.
- [ ] Session/token lifecycle defined.
- [ ] Expiration defined.
- [ ] Refresh strategy defined.
- [ ] Logout/revocation behavior defined.
- [ ] MFA considered/implemented where required.
- [ ] OAuth/OIDC configuration validated where used.
- [ ] Redirect URIs restricted.
- [ ] Account recovery secured.
- [ ] Account enumeration considered.
- [ ] Brute-force protection considered.
- [ ] Device/session management considered.
- [ ] Service identities separated from users.
- [ ] Secrets are not embedded in client bundles.
- [ ] Authentication failures are safely logged.

---

# 25. Authorization

- [ ] Roles defined.
- [ ] Permissions defined.
- [ ] Resource ownership defined.
- [ ] Tenant boundaries defined.
- [ ] Server-side authorization enforced.
- [ ] Privilege escalation tested.
- [ ] Horizontal access control tested.
- [ ] Vertical access control tested.
- [ ] Admin functions protected.
- [ ] Background jobs respect authorization boundaries.
- [ ] Export/download endpoints respect authorization.
- [ ] Search endpoints respect authorization.
- [ ] Caches respect authorization.
- [ ] Object-level authorization is tested.
- [ ] Default-deny behavior used where appropriate.

---

# 26. Security

- [ ] Threat model performed for material/high-risk systems.
- [ ] Attack surface mapped.
- [ ] Trust boundaries identified.
- [ ] Sensitive assets identified.
- [ ] Threats prioritized.
- [ ] Security controls mapped to threats.
- [ ] Input validation performed.
- [ ] Output encoding performed where required.
- [ ] XSS considered.
- [ ] SQL injection prevented.
- [ ] Command injection prevented.
- [ ] SSRF prevented.
- [ ] Path traversal prevented.
- [ ] File upload secured.
- [ ] Deserialization risks addressed.
- [ ] CSRF addressed where applicable.
- [ ] CORS is intentional.
- [ ] Security headers configured.
- [ ] Rate limiting configured where needed.
- [ ] Abuse controls considered.
- [ ] Secrets scanning enabled.
- [ ] Dependency vulnerability scanning enabled.
- [ ] Container/image scanning enabled where relevant.
- [ ] Supply-chain risks considered.
- [ ] Least privilege applied.
- [ ] Sensitive data not logged.
- [ ] Error messages do not leak sensitive information.
- [ ] Security events are auditable where required.
- [ ] Security regression tests exist for material findings.

---

# 27. Privacy & Data Governance

- [ ] Data inventory exists.
- [ ] Personal/sensitive data identified.
- [ ] Purpose of collection documented.
- [ ] Data minimization applied.
- [ ] Consent requirements assessed.
- [ ] Legal basis assessed where applicable.
- [ ] Retention period defined.
- [ ] Deletion process defined.
- [ ] Export/access process defined where required.
- [ ] Correction/update process defined where required.
- [ ] Data processor/vendor responsibilities assessed.
- [ ] Cross-border transfer issues assessed where applicable.
- [ ] Encryption requirements defined.
- [ ] Access controls defined.
- [ ] Audit requirements defined.
- [ ] Privacy notices match actual behavior.
- [ ] Product behavior matches published privacy commitments.

---

# 28. AI / LLM Systems

- [ ] Model selection justified.
- [ ] Model fallback strategy considered.
- [ ] Prompt/version management defined.
- [ ] Context construction defined.
- [ ] Context limits handled.
- [ ] Retrieval strategy defined where applicable.
- [ ] RAG sources are permission-aware.
- [ ] Source provenance preserved where required.
- [ ] Tool permissions defined.
- [ ] Tool inputs validated.
- [ ] Tool outputs validated.
- [ ] Excessive agency risks assessed.
- [ ] Prompt injection assessed.
- [ ] Indirect prompt injection assessed.
- [ ] Data exfiltration risks assessed.
- [ ] Sensitive data leakage assessed.
- [ ] Model output is not blindly trusted for critical operations.
- [ ] Structured outputs/schema validation used where appropriate.
- [ ] Hallucination handling defined.
- [ ] Uncertainty/escalation behavior defined.
- [ ] Human approval boundary defined.
- [ ] Model refusal/failure behavior tested.
- [ ] Cost controls defined.
- [ ] Token limits defined.
- [ ] Rate limits defined.
- [ ] Abuse scenarios considered.
- [ ] Model latency considered.
- [ ] Evaluation dataset defined.
- [ ] Quality metrics defined.
- [ ] Regression evaluation exists.
- [ ] Prompt/model changes trigger relevant evaluation.
- [ ] AI-specific observability exists.

---

# 29. Coding Standards

- [ ] Language conventions followed.
- [ ] Framework conventions followed.
- [ ] Naming is consistent.
- [ ] Functions have focused responsibilities.
- [ ] Modules have coherent responsibilities.
- [ ] Dependency direction is intentional.
- [ ] Circular dependencies avoided.
- [ ] Dead code removed.
- [ ] Duplicate logic minimized.
- [ ] Error handling consistent.
- [ ] Logging consistent.
- [ ] Configuration separated from code.
- [ ] Environment-specific behavior is explicit.
- [ ] Types are used effectively.
- [ ] Unsafe casts are justified.
- [ ] Magic values are avoided where harmful.
- [ ] Comments explain why, not obvious what.
- [ ] Public interfaces are documented.
- [ ] Complexity is controlled.
- [ ] Abstraction is justified.
- [ ] YAGNI applied.
- [ ] DRY applied without harmful over-abstraction.
- [ ] Code is readable by a new engineer.
- [ ] Linter passes.
- [ ] Formatter passes.
- [ ] Type checker passes.
- [ ] Static analysis passes.
- [ ] Dependency lockfile is consistent.
- [ ] No accidental debug code.
- [ ] No secrets or credentials in source.

---

# 30. Design Patterns & Architecture Quality

- [ ] Pattern use is justified by a real problem.
- [ ] No pattern is used solely for ceremony.
- [ ] Dependency injection is used where it improves testability/decoupling.
- [ ] Repository pattern used only where beneficial.
- [ ] Adapter pattern used for external/provider boundaries where beneficial.
- [ ] Strategy pattern used where interchangeable behavior exists.
- [ ] Factory pattern used where construction complexity warrants it.
- [ ] Command/event patterns used where workflow semantics warrant them.
- [ ] State modeling used for complex state machines.
- [ ] Middleware used consistently for cross-cutting concerns.
- [ ] CQRS used only where justified.
- [ ] Event-driven design used only where justified.
- [ ] Domain boundaries are coherent.
- [ ] Presentation logic is separated from domain logic.
- [ ] Infrastructure concerns are separated from business logic where appropriate.
- [ ] Abstraction count is proportional to system complexity.
- [ ] Architecture avoids accidental distributed-system complexity.

---

# 31. Testing

- [ ] Test strategy defined.
- [ ] Unit tests cover important domain logic.
- [ ] Integration tests cover important boundaries.
- [ ] API tests cover critical contracts.
- [ ] Component tests cover important UI behavior.
- [ ] E2E tests cover critical user journeys.
- [ ] Acceptance tests map to acceptance criteria.
- [ ] Negative tests exist.
- [ ] Edge-case tests exist.
- [ ] Permission tests exist.
- [ ] Authentication tests exist.
- [ ] Concurrency tests exist where needed.
- [ ] Failure/retry tests exist where needed.
- [ ] Migration tests exist where needed.
- [ ] Regression tests exist for fixed defects.
- [ ] Accessibility tests exist.
- [ ] Performance tests exist where required.
- [ ] Security tests exist where required.
- [ ] AI evaluations exist where applicable.
- [ ] Tests are deterministic.
- [ ] Flaky tests are tracked and fixed.
- [ ] Test fixtures are maintainable.
- [ ] Tests do not rely unnecessarily on production data.
- [ ] Coverage is reviewed by behavior/risk, not percentage alone.
- [ ] Critical paths have executable proof.

---

# 32. TDD / Implementation Discipline

For suitable implementation tasks:

- [ ] Expected behavior is specified first.
- [ ] Test is written before implementation where TDD is appropriate.
- [ ] Test fails for the expected reason.
- [ ] Minimal implementation is created.
- [ ] Test passes.
- [ ] Refactoring occurs without changing behavior.
- [ ] Full relevant suite passes.
- [ ] Regression behavior remains protected.

---

# 33. Systematic Debugging

When fixing defects:

- [ ] Failure reproduced.
- [ ] Failure scope identified.
- [ ] Evidence collected.
- [ ] Root cause investigated.
- [ ] Hypothesis explicitly stated.
- [ ] Hypothesis tested.
- [ ] Fix targets root cause rather than symptom.
- [ ] Regression test added.
- [ ] Related failure modes considered.
- [ ] Full affected test suite rerun.
- [ ] No random multi-change patching.
- [ ] Environment/configuration differences considered.
- [ ] Race/timing issues investigated where relevant.

---

# 34. Performance

- [ ] Performance objectives defined.
- [ ] Critical user journeys identified.
- [ ] Latency targets defined.
- [ ] p50 considered.
- [ ] p95 considered.
- [ ] p99 considered where appropriate.
- [ ] Throughput requirements defined.
- [ ] Concurrency requirements defined.
- [ ] CPU usage reviewed.
- [ ] Memory usage reviewed.
- [ ] Network usage reviewed.
- [ ] Database performance reviewed.
- [ ] External API latency reviewed.
- [ ] N+1 queries eliminated.
- [ ] Bundle size reviewed.
- [ ] Render cost reviewed.
- [ ] Image/font loading reviewed.
- [ ] Cold starts considered.
- [ ] Queue processing performance considered.
- [ ] Load testing performed where required.
- [ ] Performance regression baseline exists where valuable.
- [ ] Optimization is evidence-driven.

---

# 35. Reliability & Resilience

- [ ] Availability target defined.
- [ ] Failure domains identified.
- [ ] Dependency failures considered.
- [ ] Database failures considered.
- [ ] Network failures considered.
- [ ] Queue failures considered.
- [ ] Worker crashes considered.
- [ ] Retry behavior bounded.
- [ ] Backoff used where appropriate.
- [ ] Idempotency protects retries.
- [ ] Circuit breaking considered.
- [ ] Graceful degradation considered.
- [ ] Timeouts exist.
- [ ] Health checks exist.
- [ ] Readiness checks exist.
- [ ] Liveness checks exist.
- [ ] Recovery behavior defined.
- [ ] Data consistency behavior defined.
- [ ] Disaster recovery requirements defined.
- [ ] RPO defined where applicable.
- [ ] RTO defined where applicable.
- [ ] Restore process tested.

---

# 36. Observability

- [ ] Structured logs.
- [ ] Appropriate log levels.
- [ ] Request/correlation IDs.
- [ ] Error tracking.
- [ ] Metrics.
- [ ] Traces where useful.
- [ ] Health endpoints.
- [ ] Dependency health visibility.
- [ ] Business metrics.
- [ ] Queue metrics.
- [ ] Cache metrics.
- [ ] Database metrics.
- [ ] AI/model metrics where applicable.
- [ ] Cost metrics where applicable.
- [ ] Alerts have owners.
- [ ] Alerts are actionable.
- [ ] Alert thresholds are justified.
- [ ] Sensitive data is redacted.
- [ ] Log retention is defined.
- [ ] Dashboards exist for critical production paths.

---

# 37. DevOps / CI/CD

- [ ] Repository structure is understood.
- [ ] Branch/merge strategy defined.
- [ ] CI pipeline exists.
- [ ] Lint runs in CI.
- [ ] Type checking runs in CI.
- [ ] Tests run in CI.
- [ ] Build runs in CI.
- [ ] Security scans run in CI.
- [ ] Dependency checks run in CI.
- [ ] Artifacts are reproducible.
- [ ] Dependencies are pinned/locked.
- [ ] Secrets are injected securely.
- [ ] Environments are separated.
- [ ] Infrastructure is reproducible.
- [ ] Infrastructure-as-code used where appropriate.
- [ ] Deployment pipeline is auditable.
- [ ] Rollback path exists.
- [ ] Deployment health gates exist.
- [ ] Migration handling exists.
- [ ] Release notes/changelog process exists.

---

# 38. Infrastructure

- [ ] Compute architecture defined.
- [ ] Network architecture defined.
- [ ] DNS defined.
- [ ] TLS defined.
- [ ] CDN defined where useful.
- [ ] Load balancing defined where needed.
- [ ] Storage defined.
- [ ] Database infrastructure defined.
- [ ] Cache infrastructure defined.
- [ ] Queue infrastructure defined.
- [ ] Secrets infrastructure defined.
- [ ] IAM/permissions defined.
- [ ] Resource limits defined.
- [ ] Autoscaling defined where needed.
- [ ] Cost controls defined.
- [ ] Backups defined.
- [ ] Monitoring defined.
- [ ] Disaster recovery defined.
- [ ] Environment isolation defined.
- [ ] Infrastructure changes reviewed.

---

# 39. Packaging

- [ ] Version defined.
- [ ] Build artifact reproducible.
- [ ] Runtime requirements documented.
- [ ] Dependencies included correctly.
- [ ] Lockfile included where applicable.
- [ ] Environment variables documented.
- [ ] Startup command defined.
- [ ] Health endpoint defined.
- [ ] Static assets packaged correctly.
- [ ] Database migrations packaged.
- [ ] Container image built where applicable.
- [ ] Container image minimized.
- [ ] Image runs as non-root where appropriate.
- [ ] SBOM generated where appropriate.
- [ ] Licenses reviewed.
- [ ] Package metadata correct.
- [ ] Artifact provenance available where required.

---

# 40. Release Management

- [ ] Release scope frozen.
- [ ] Requirements complete.
- [ ] Acceptance criteria complete.
- [ ] Tests pass.
- [ ] Build passes.
- [ ] Security gate passes.
- [ ] Performance gate passes where applicable.
- [ ] Accessibility gate passes where applicable.
- [ ] Documentation complete.
- [ ] Migration plan complete.
- [ ] Rollback plan complete.
- [ ] Backup verified.
- [ ] Monitoring ready.
- [ ] Alerts ready.
- [ ] Support readiness checked.
- [ ] Known issues documented.
- [ ] Approved exceptions documented.
- [ ] Release owner identified.
- [ ] Final independent verification completed.

---

# 41. Production Deployment

Before deployment:

- [ ] Correct artifact selected.
- [ ] Correct environment selected.
- [ ] Configuration verified.
- [ ] Secrets verified.
- [ ] Database compatibility verified.
- [ ] Migration order verified.
- [ ] Backups verified.
- [ ] Deployment window/risk assessed.
- [ ] Rollback procedure tested/validated.
- [ ] Monitoring active.
- [ ] Alerts active.
- [ ] Support/on-call ready.

During deployment:

- [ ] Deployment progress observable.
- [ ] Health checks monitored.
- [ ] Error rate monitored.
- [ ] Latency monitored.
- [ ] Resource usage monitored.
- [ ] Migration status monitored.
- [ ] Rollback trigger conditions defined.

After deployment:

- [ ] Smoke tests pass.
- [ ] Critical user journeys pass.
- [ ] Authentication works.
- [ ] Authorization works.
- [ ] Key APIs work.
- [ ] Database operations work.
- [ ] Background jobs work.
- [ ] Integrations work.
- [ ] Analytics work.
- [ ] Error rates acceptable.
- [ ] Performance acceptable.
- [ ] Logs/traces visible.
- [ ] No unexpected security signals.
- [ ] Release marked verified only after evidence exists.

---

# 42. Documentation / Technical Publications

- [ ] README exists.
- [ ] Product overview exists.
- [ ] Installation instructions exist.
- [ ] Configuration instructions exist.
- [ ] Environment variables documented.
- [ ] Architecture documented.
- [ ] API documented.
- [ ] Authentication documented.
- [ ] Deployment documented.
- [ ] Migration documented.
- [ ] Rollback documented.
- [ ] Troubleshooting documented.
- [ ] Runbooks documented.
- [ ] Incident procedures documented.
- [ ] Operational ownership documented.
- [ ] User documentation exists where required.
- [ ] Admin documentation exists where required.
- [ ] Changelog maintained.
- [ ] ADRs maintained for material decisions.
- [ ] Documentation matches implementation.
- [ ] Examples are executable/current where practical.
- [ ] Deprecated documentation is removed or marked.

---

# 43. Analytics & Measurement

- [ ] Product metrics defined.
- [ ] Event taxonomy defined.
- [ ] Event names consistent.
- [ ] Event properties defined.
- [ ] Identity model defined.
- [ ] Funnel defined.
- [ ] Activation defined.
- [ ] Retention defined.
- [ ] Conversion defined.
- [ ] Revenue events defined.
- [ ] Error/business-failure events defined.
- [ ] Privacy constraints applied.
- [ ] Analytics tested.
- [ ] Dashboards exist for critical metrics.
- [ ] Metrics have owners.
- [ ] Product decisions can be connected to measurable outcomes.

---

# 44. Support / Operations

- [ ] Support channels defined.
- [ ] Support ownership defined.
- [ ] Severity levels defined.
- [ ] Escalation path defined.
- [ ] Customer-impacting incident process defined.
- [ ] Common troubleshooting documented.
- [ ] Known issues tracked.
- [ ] Operational runbooks exist.
- [ ] Admin tooling exists where needed.
- [ ] Customer communication templates/process exists where needed.
- [ ] Support can inspect relevant diagnostics without violating privacy.
- [ ] Feedback is captured as structured product evidence.

---

# 45. Maintenance

- [ ] Dependency update process exists.
- [ ] Security patch process exists.
- [ ] Framework/runtime upgrade process exists.
- [ ] Certificate/credential expiry monitored.
- [ ] Secret rotation process exists.
- [ ] Database growth monitored.
- [ ] Storage growth monitored.
- [ ] Cost growth monitored.
- [ ] Performance regression monitored.
- [ ] Error trends reviewed.
- [ ] Deprecated APIs identified.
- [ ] Deprecated dependencies identified.
- [ ] Technical debt tracked.
- [ ] Dead code periodically identified.
- [ ] Backup restore periodically tested.
- [ ] Disaster recovery periodically tested.
- [ ] Capacity planning performed.
- [ ] Operational knowledge updated.
- [ ] Customer feedback feeds roadmap.
- [ ] Escaped defects feed regression tests.
- [ ] Factory checklist evolves from production evidence.

---

# 46. Localization / Internationalization

Where applicable:

- [ ] Locale strategy defined.
- [ ] Translation architecture defined.
- [ ] User-visible strings externalized.
- [ ] Pluralization handled.
- [ ] Date formats handled.
- [ ] Time formats handled.
- [ ] Time zones handled.
- [ ] Currency handled.
- [ ] Number formats handled.
- [ ] Text expansion tested.
- [ ] RTL considered.
- [ ] Locale-specific legal/content requirements considered.
- [ ] AI-generated content localization considered.

---

# 47. Content Quality

- [ ] Product terminology consistent.
- [ ] UI copy understandable.
- [ ] Error messages actionable.
- [ ] Empty-state copy useful.
- [ ] Help text does not contradict behavior.
- [ ] Marketing claims are accurate.
- [ ] Documentation terminology matches UI.
- [ ] Domain terminology is correct.
- [ ] Generated content has appropriate safeguards.
- [ ] Content ownership/review is defined.

---

# 48. Cost & FinOps

- [ ] Major cost drivers identified.
- [ ] Infrastructure costs estimated.
- [ ] Database costs estimated.
- [ ] Storage costs estimated.
- [ ] Network/egress costs considered.
- [ ] Third-party API costs estimated.
- [ ] AI token/model costs estimated.
- [ ] Per-user/per-tenant cost estimated where useful.
- [ ] Usage limits defined.
- [ ] Abuse/cost explosion scenarios considered.
- [ ] Cost alerts configured.
- [ ] Expensive operations observable.
- [ ] Caching/aggregation opportunities assessed.
- [ ] Cost/performance trade-offs documented.
- [ ] Cost per accepted product tracked for the Factory itself.

---

# 49. Legal / Compliance

Applicability depends on product/domain/jurisdiction.

- [ ] Business entity/contracting requirements assessed.
- [ ] Terms of service assessed.
- [ ] Privacy policy requirements assessed.
- [ ] Cookie/tracking requirements assessed.
- [ ] Data-processing requirements assessed.
- [ ] Intellectual property ownership assessed.
- [ ] Open-source licenses assessed.
- [ ] Third-party terms assessed.
- [ ] AI provider terms assessed.
- [ ] Industry regulation assessed.
- [ ] Geographic/jurisdiction requirements assessed.
- [ ] Consumer protection requirements assessed.
- [ ] Accessibility/legal requirements assessed.
- [ ] Recordkeeping requirements assessed.
- [ ] Marketing/advertising claim requirements assessed.
- [ ] High-risk legal questions escalated to qualified counsel.

---

# 50. Security Supply Chain

- [ ] Dependency inventory exists.
- [ ] Lockfiles reviewed.
- [ ] Vulnerability scanning enabled.
- [ ] Transitive dependencies considered.
- [ ] Package provenance considered.
- [ ] Untrusted packages avoided.
- [ ] Build environment secured.
- [ ] CI credentials least-privileged.
- [ ] Artifact integrity protected.
- [ ] Container base images controlled.
- [ ] Image vulnerabilities scanned.
- [ ] Secrets excluded from artifacts.
- [ ] SBOM available where required.
- [ ] Release provenance available where required.

---

# 51. Multi-Tenancy

If applicable:

- [ ] Tenant identity established.
- [ ] Tenant isolation strategy defined.
- [ ] Tenant-aware database access enforced.
- [ ] Tenant-aware cache keys enforced.
- [ ] Tenant-aware search enforced.
- [ ] Tenant-aware background jobs enforced.
- [ ] Tenant-aware file/object storage enforced.
- [ ] Tenant-aware analytics enforced.
- [ ] Cross-tenant access tests exist.
- [ ] Admin/support access is audited.
- [ ] Tenant deletion/export behavior defined.

---

# 52. Files / Uploads / Exports

If applicable:

- [ ] Allowed file types defined.
- [ ] File size limits defined.
- [ ] Content validation performed.
- [ ] Malware scanning considered.
- [ ] Filename/path safety handled.
- [ ] Storage access controlled.
- [ ] Signed URLs expire appropriately.
- [ ] Download authorization enforced.
- [ ] Export authorization enforced.
- [ ] Large export strategy defined.
- [ ] Export audit requirements defined.
- [ ] Temporary files cleaned up.

---

# 53. Search

If applicable:

- [ ] Search requirements defined.
- [ ] Ranking expectations defined.
- [ ] Filtering defined.
- [ ] Permissions enforced in search.
- [ ] Tenant isolation enforced.
- [ ] Typo tolerance assessed.
- [ ] Empty results handled.
- [ ] Index freshness defined.
- [ ] Reindex strategy defined.
- [ ] Search failure fallback defined.
- [ ] Performance tested.

---

# 54. Background Jobs / Queues

If applicable:

- [ ] Job ownership defined.
- [ ] Queue semantics defined.
- [ ] Retry policy defined.
- [ ] Backoff defined.
- [ ] Maximum attempts defined.
- [ ] Dead-letter handling defined.
- [ ] Idempotency defined.
- [ ] Job timeout defined.
- [ ] Job cancellation defined where needed.
- [ ] Ordering requirements defined.
- [ ] Duplicate delivery handled.
- [ ] Monitoring exists.
- [ ] Queue growth alerts exist.
- [ ] Graceful shutdown implemented.
- [ ] Poison-message handling defined.

---

# 55. Concurrency / Distributed Systems

If applicable:

- [ ] Shared mutable state identified.
- [ ] Race conditions analyzed.
- [ ] Locking strategy defined where needed.
- [ ] Optimistic concurrency considered.
- [ ] Pessimistic locking considered.
- [ ] Idempotency used for retries.
- [ ] Duplicate events handled.
- [ ] Event ordering assumptions explicit.
- [ ] Exactly-once assumptions avoided unless truly guaranteed.
- [ ] Eventual consistency understood.
- [ ] Read-after-write requirements defined.
- [ ] Distributed transaction requirements assessed.
- [ ] Clock/time assumptions assessed.

---

# 56. Web / Browser Security & Performance

- [ ] HTTPS enforced.
- [ ] Secure cookies used where applicable.
- [ ] SameSite policy intentional.
- [ ] CSP considered.
- [ ] HSTS considered.
- [ ] Referrer policy configured.
- [ ] Permissions policy considered.
- [ ] Browser storage use reviewed.
- [ ] Sensitive information not stored insecurely.
- [ ] Third-party scripts reviewed.
- [ ] Third-party script impact measured.
- [ ] Core performance metrics assessed where relevant.
- [ ] Caching headers intentional.
- [ ] Compression configured.
- [ ] CDN behavior verified.

---

# 57. Accessibility + Visual QA Gate

The Factory should inspect the **actual rendered product**.

- [ ] Application starts successfully.
- [ ] Representative pages render.
- [ ] Representative user journeys render.
- [ ] Screenshots captured.
- [ ] Responsive screenshots captured.
- [ ] Visual hierarchy reviewed.
- [ ] Alignment reviewed.
- [ ] Spacing reviewed.
- [ ] Typography reviewed.
- [ ] Component consistency reviewed.
- [ ] Empty/loading/error states reviewed.
- [ ] Data-dense screens reviewed.
- [ ] Dark/light modes reviewed where applicable.
- [ ] Accessibility reviewed.
- [ ] Visual regressions compared against baseline where applicable.
- [ ] Visual reviewer is independent of the implementation maker.

---

# 58. Product Quality Review

Ask independently:

### A. Did we build the requested product?

- [ ] All committed requirements implemented.
- [ ] Acceptance criteria satisfied.
- [ ] Scope respected.
- [ ] No critical requirement omitted.
- [ ] UX matches approved intent.

### B. Did we build it correctly?

- [ ] Architecture sound.
- [ ] Code maintainable.
- [ ] Security acceptable.
- [ ] Performance acceptable.
- [ ] Reliability acceptable.
- [ ] Tests sufficient.
- [ ] Observability sufficient.

### C. Is it actually useful?

- [ ] User can accomplish the intended job.
- [ ] Workflow is understandable.
- [ ] Product reduces the intended pain.
- [ ] Product does not introduce unacceptable new friction.
- [ ] Value proposition is visible in actual use.
- [ ] Product behavior matches business/domain reality.

---

# 59. Independent Verification Protocol

Verification must not be a self-congratulation step.

### Review layers

1. Deterministic automated checks.
2. Specification-compliance review.
3. Engineering-quality review.
4. Security review.
5. UX/accessibility review.
6. Domain/business review.
7. Product usefulness review.
8. Completeness audit.
9. Evidence audit.
10. Production verification.

### Independent verifier rules

- [ ] Prefer a different model from the maker.
- [ ] Prefer fresh context.
- [ ] Do not rely solely on the maker's summary.
- [ ] Inspect source/artifacts directly.
- [ ] Inspect tests directly.
- [ ] Run deterministic checks where possible.
- [ ] Inspect rendered behavior for UI.
- [ ] Challenge unsupported claims.
- [ ] Mark unknowns explicitly.
- [ ] Search for missing work, not only bad work.
- [ ] Verify exceptions.
- [ ] Verify evidence freshness.
- [ ] Block on critical findings.

---

# 60. Completeness Auditor

The Completeness Auditor asks:

> **What should exist but does not?**

Checklist:

- [ ] Every product goal has requirements.
- [ ] Every requirement has acceptance criteria.
- [ ] Every acceptance criterion has an implementation path.
- [ ] Every important implementation has tests.
- [ ] Every critical path has end-to-end evidence.
- [ ] Every external dependency has failure handling.
- [ ] Every state has valid transitions.
- [ ] Every important user flow has loading/error/empty behavior.
- [ ] Every protected resource has authorization.
- [ ] Every sensitive data path has privacy/security treatment.
- [ ] Every production component has observability.
- [ ] Every deployment has rollback/recovery.
- [ ] Every migration has a safe operational strategy.
- [ ] Every exception is documented.
- [ ] Every deferred item has an owner/milestone.
- [ ] Every release artifact is documented.
- [ ] Every critical operational procedure has a runbook.
- [ ] No unexplained orphan code/features.
- [ ] No unexplained orphan database tables/endpoints/components.
- [ ] No requirement is silently dropped.
- [ ] No critical checklist item is silently skipped.

---

# 61. Evidence Ledger

Every important PASS should have evidence.

Recommended evidence types:

- Source file/line.
- Automated test result.
- Build output.
- Lint/typecheck output.
- Security scan.
- Dependency scan.
- Database migration/test.
- API contract test.
- Screenshot/video.
- Browser/E2E result.
- Performance measurement.
- Configuration inspection.
- Production metric.
- Human/domain expert approval.
- External authoritative source.
- Customer research evidence.

Evidence rules:

- [ ] Evidence is linked to the checklist item.
- [ ] Evidence is from the correct version/build.
- [ ] Evidence is reproducible where possible.
- [ ] Evidence is not merely an agent assertion.
- [ ] Evidence has timestamp/version context where needed.
- [ ] Stale evidence is invalidated after material changes.

---

# 62. Exceptions / Waivers

Every exception must contain:

```yaml
check_id:
status: EXCEPTION
reason:
risk:
scope:
approved_by:
date:
expiry:
mitigation:
follow_up:
```

Rules:

- [ ] Exception is specific.
- [ ] Risk is explicit.
- [ ] Scope is explicit.
- [ ] Approval authority is appropriate.
- [ ] Expiry/review date exists where appropriate.
- [ ] Mitigation exists where required.
- [ ] Exception does not silently lower a critical security/product requirement.
- [ ] Exceptions are included in release reports.

---

# 63. Gate Definitions

## Gate 0 — Discovery Ready

Requires:

- [ ] Problem understood.
- [ ] User understood.
- [ ] Evidence sufficient.
- [ ] Major unknowns identified.

## Gate 1 — Product Ready

Requires:

- [ ] Product strategy.
- [ ] Requirements.
- [ ] Acceptance criteria.
- [ ] Business/domain validation.
- [ ] Product risks.

## Gate 2 — Design Ready

Requires:

- [ ] UX.
- [ ] User flows.
- [ ] Product design specification.
- [ ] Architecture direction.
- [ ] Security/privacy considerations.

## Gate 3 — Build Ready

Requires:

- [ ] Architecture.
- [ ] Implementation plan.
- [ ] Task graph.
- [ ] Agent checklists.
- [ ] Skills/knowledge selected.
- [ ] Test strategy.

## Gate 4 — Feature Complete

Requires:

- [ ] Implementation.
- [ ] Tests.
- [ ] Specification review.
- [ ] Engineering review.
- [ ] No unresolved blocker/critical findings.

## Gate 5 — Release Candidate

Requires:

- [ ] Full relevant test suite.
- [ ] Security.
- [ ] Performance.
- [ ] Accessibility.
- [ ] E2E.
- [ ] Documentation.
- [ ] Packaging.
- [ ] Deployment readiness.
- [ ] Independent product review.
- [ ] Completeness audit.

## Gate 6 — Production Verified

Requires:

- [ ] Deployment succeeded.
- [ ] Smoke tests passed.
- [ ] Critical journeys passed.
- [ ] Observability confirmed.
- [ ] Production metrics acceptable.
- [ ] No unexpected critical errors.

---

# 64. Agent-Specific Checklist Composition

Do not give every agent the entire master checklist.

The Orchestrator should compose:

```text
MASTER CHECKLIST
+
PRODUCT REQUIREMENTS
+
DOMAIN CHECKLIST
+
TECH-STACK CHECKLIST
+
RISK CHECKLIST
+
AGENT-SPECIFIC CHECKLIST
=
AGENT CONTRACT
```

Example:

### UI/UX Agent

Receives:

- Product.
- User research.
- Domain terminology.
- Product requirements.
- UX checklist.
- Accessibility checklist.
- Responsive checklist.
- Design-system skills.
- Selected frontend-stack knowledge.
- Visual QA requirements.

### API Agent

Receives:

- Requirements.
- Domain model.
- API checklist.
- Security checklist.
- Authorization checklist.
- Performance checklist.
- Selected framework/API knowledge.
- Database contract.

### Database Agent

Receives:

- Domain model.
- Data requirements.
- Database checklist.
- Security/privacy checklist.
- Migration checklist.
- Selected database technology knowledge.

### Coding Agent

Receives:

- Approved design.
- Architecture.
- Implementation plan.
- Task-specific checklist.
- Coding standards.
- Design-pattern guidance.
- Framework/language skills.
- Tests/acceptance criteria.

### DevOps Agent

Receives:

- Architecture.
- Infrastructure checklist.
- Security checklist.
- Deployment checklist.
- Observability checklist.
- Cost checklist.
- Selected cloud/container/orchestration knowledge.

### Business/Marketing/Sales Agent

Receives:

- Product brief.
- Customer evidence.
- Domain knowledge.
- Business checklist.
- Marketing/sales checklist.
- Pricing/packaging requirements.
- Compliance constraints.

---

# 65. Skill / Knowledge Selection

For every agent task:

- [ ] Required skills identified.
- [ ] Required domain knowledge identified.
- [ ] Required technology knowledge identified.
- [ ] Required standards identified.
- [ ] Relevant examples identified.
- [ ] Relevant templates identified.
- [ ] Skill dependencies resolved.
- [ ] Skill provenance known.
- [ ] Skill quality tested/approved.
- [ ] Outdated knowledge detected where possible.
- [ ] Conflicting guidance surfaced.
- [ ] Only relevant context passed to agent.

Skills should be artifact-producing where practical:

```text
Research → Evidence Table
Premortem → Risk Register
Architecture → ADR/Architecture Spec
Security → Threat Model
Coding → Code + Tests + Verification
Product Review → Product Review Report
```

---

# 66. Technology-Stack Overlay

The master checklist is technology-neutral.

The Factory must add stack-specific checks dynamically:

```text
Core
+
Frontend framework
+
Backend framework
+
Language
+
Database
+
Cache
+
Queue
+
Cloud
+
Container/runtime
+
CI/CD
+
Observability
+
AI stack
+
Domain
```

Examples of stack overlays:

- React
- Next.js
- Vue
- Angular
- Svelte
- TypeScript
- Python
- Node.js
- Go
- Java
- FastAPI
- PostgreSQL
- MySQL
- MongoDB
- Redis
- Kafka
- Docker
- Kubernetes
- AWS
- GCP
- Azure
- Serverless
- Mobile/native stacks
- AI/LLM providers

No technology-specific rule should be assumed applicable without checking the selected stack.

---

# 67. Factory Self-Quality

The Factory itself must be tested.

- [ ] Checklist schema validated.
- [ ] Checklist IDs unique.
- [ ] No contradictory mandatory rules.
- [ ] Applicability rules tested.
- [ ] Agent-to-checklist routing tested.
- [ ] Verification reports are machine-readable.
- [ ] Evidence references are valid.
- [ ] Gate logic tested.
- [ ] Exception logic tested.
- [ ] Unknown cannot silently become pass.
- [ ] Critical failure blocks correctly.
- [ ] Stale evidence is detected.
- [ ] Checklist changes are versioned.
- [ ] Skills are versioned.
- [ ] Skill dependencies are validated.
- [ ] Evaluation cases exist for important skills.
- [ ] Factory workflows are regression-tested.
- [ ] Escaped defects become new evaluation/checklist cases.

---

# 68. Factory Learning Loop

```text
Production
 ↓
Incident / Feedback / Missed Requirement
 ↓
Root Cause
 ↓
Classify:
  checklist gap
  skill gap
  knowledge gap
  routing gap
  model limitation
  verification gap
  tool limitation
  process gap
 ↓
Create regression case
 ↓
Update skill/checklist/workflow
 ↓
Test Factory
 ↓
Version
 ↓
Deploy improved Factory
```

Checklist:

- [ ] Every escaped defect has root-cause classification.
- [ ] Repeated defects trigger systemic analysis.
- [ ] New defect creates regression coverage where appropriate.
- [ ] Checklist gaps are distinguished from implementation mistakes.
- [ ] Verification gaps are distinguished from maker mistakes.
- [ ] Factory improvements are evaluated before adoption.
- [ ] Historical quality can be compared across Factory versions.

---

# 69. Final Release Report

The Factory should produce:

```text
PRODUCT
VERSION
RUN
DATE

PRODUCT
  Requirements             PASS
  Acceptance Criteria      PASS
  User Flows               PASS
  Domain Validation        PASS
  Business Model           PASS

UX
  UX                       PASS
  Accessibility            PASS
  Responsive               PASS
  Visual QA                PASS

ENGINEERING
  Architecture             PASS
  Frontend                 PASS
  Backend/API              PASS
  Database                 PASS
  Business Logic           PASS
  Testing                  PASS
  Performance              PASS

SECURITY
  Authentication           PASS
  Authorization            PASS
  Application Security     PASS
  Privacy                  PASS
  AI Security              PASS

OPERATIONS
  Observability            PASS
  DevOps                   PASS
  Packaging                PASS
  Deployment               PASS
  Disaster Recovery        PASS

COMMERCIAL
  Marketing                PASS
  Sales                    PASS
  Pricing                  PASS

DOCUMENTATION
  Technical                PASS
  User                     PASS
  Operational              PASS

COMPLETENESS AUDIT          PASS
EVIDENCE AUDIT              PASS
APPROVED EXCEPTIONS         N
BLOCKERS                    0

RELEASE DECISION: APPROVED
```

Scores may be used for dashboards, but **gates + evidence are authoritative**.

---

# 70. Core Factory Workflow

```text
                     USER IDEA
                         │
                         ▼
                ┌─────────────────┐
                │ ORCHESTRATOR     │
                └────────┬────────┘
                         │
             Product / domain discovery
                         │
                         ▼
                 REQUIREMENTS
                         │
                         ▼
                 MASTER CHECKLIST
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
       PRODUCT          UX          ENGINEERING
       SKILLS         SKILLS           SKILLS
          │              │              │
          └──────────────┼──────────────┘
                         ▼
                  DESIGN PACKAGE
                         │
                  APPROVAL GATE
                         │
                         ▼
                 ARCHITECTURE
                         │
                         ▼
                  TASK GRAPH
                         │
             ┌───────────┼───────────┐
             ▼           ▼           ▼
            UI          API          DB
             │           │           │
             └───────────┼───────────┘
                         ▼
                    INTEGRATION
                         │
                         ▼
                  AUTOMATED TESTS
                         │
                         ▼
             ┌──────────────────────┐
             │ INDEPENDENT REVIEW   │
             │ DIFFERENT MODEL      │
             └──────────┬───────────┘
                        │
       ┌────────────────┼─────────────────┐
       ▼                ▼                 ▼
 Specification      Engineering        Product
 Compliance          Quality            Value
       │                │                 │
       └────────────────┼─────────────────┘
                        ▼
                COMPLETENESS AUDIT
                        │
                 Evidence Audit
                        │
                        ▼
                  RELEASE GATE
                        │
                        ▼
                    PACKAGE
                        │
                        ▼
                    DEPLOY
                        │
                        ▼
              PRODUCTION VERIFICATION
                        │
                        ▼
               OPERATE / MONITOR
                        │
                        ▼
                FEEDBACK / LEARN
                        │
                        └──────→ FACTORY IMPROVEMENT
```

---

# 71. Final Principles

1. **Build the right product, not merely working software.**
2. **Give agents their obligations before they execute.**
3. **Skills provide knowledge; agents provide responsibility and execution.**
4. **The orchestrator owns workflow/context/budget; agents own bounded tasks.**
5. **Artifacts carry decisions between agents.**
6. **Do not make one giant context the communication mechanism.**
7. **Use deterministic automation whenever judgment is unnecessary.**
8. **Use independent models for meaningful verification.**
9. **Verify evidence, not claims.**
10. **Unknown is not pass.**
11. **Exceptions are explicit and auditable.**
12. **Every requirement must be traceable to evidence.**
13. **Test behavior, not just code coverage.**
14. **Inspect the actual rendered product.**
15. **Review product usefulness separately from engineering quality.**
16. **Do not over-engineer: YAGNI and proportionality matter.**
17. **Use parallel agents only when dependencies permit safe parallelism.**
18. **Fresh context is preferred for bounded implementation/review tasks.**
19. **Security, privacy, accessibility, reliability and operations are part of product quality, not final polish.**
20. **The Factory itself must be continuously evaluated and improved.**

## Definition of Done

A product is not done because an agent says it is done.

It is done only when:

```text
Intent                  ✓
Customer evidence       ✓
Domain correctness      ✓
Requirements            ✓
Business viability      ✓
UX/product design       ✓
Architecture            ✓
Implementation          ✓
Testing                 ✓
Security                ✓
Privacy                 ✓
Accessibility            ✓
Performance              ✓
Reliability              ✓
Observability            ✓
Documentation            ✓
Packaging                ✓
Deployment               ✓
Production verification  ✓
Independent verification ✓
Completeness audit       ✓
Evidence                 ✓
Approved exceptions      ✓
```

> **The Factory owns correctness. Agents own execution. Evidence owns the release decision.**
