# Product Type Classification Reference

## Overview
When a project is created, the system classifies it by **product type** (determining rigor level) and **product domain** (determining compliance/security requirements). These classifications drive:
- Adaptive question depth during ideation
- Agent selection and quality tiers
- Security and compliance requirements

## Product Types (Rigor Levels)

### 1. Exploration (Minimum Viable)
**When to use:** Quick experiments, proof-of-concepts, tech demos
**Questions asked:** 2-3 basic questions
- What problem are you exploring?
- What technologies are interesting to try?
- Expected rough timeline?

**Agents enabled:**
- ✅ Ideation, Design, Architect, Review, Implement
- ✅ Validate (basic only - no E2E)
- ❌ Code Review, Fix, Document, Package

**Quality tier:** Minimal
- No formal security testing
- No documentation required
- No packaging
- Basic smoke tests only

**Model tier suggestion:** zenfree or orouterfree (cheapest)

---

### 2. Learning (Educational Focus)
**When to use:** Personal learning projects, tutorials, skill development
**Questions asked:** 4-5 educational questions
- What skill/concept are you learning?
- What resources already exist?
- Expected learning outcomes?

**Agents enabled:**
- ✅ Ideation, Design, Architect, Review, Implement
- ✅ Validate (unit tests only)
- ✅ Document (educational focus)
- ❌ Fix, Package

**Quality tier:** Basic
- Basic unit testing
- Educational documentation
- No security/compliance requirements

**Model tier suggestion:** Recommended

---

### 3. Fun/Hobby (Low-Stakes)
**When to use:** Personal projects, hobbies, weekend builds
**Questions asked:** 5-7 casual questions
- What are you building for fun?
- Who (if anyone) will use it?
- Any specific features you want?

**Agents enabled:**
- ✅ Ideation, Design, Architect, Review, Implement
- ✅ Code Review, Validate
- ✅ Document (basic)
- ⚠️ Fix (on failure only), Package (optional)

**Quality tier:** Moderate-low
- Basic security checks
- README + inline comments
- Optional packaging

**Model tier suggestion:** Recommended or Hybrid

---

### 4. Prototype/MVP (Proof of Concept)
**When to use:** Startup MVPs, investor demos, validation projects
**Questions asked:** 6-8 focused questions
- Target user base?
- Core problem being solved?
- Key features for MVP?
- Monetization approach?

**Agents enabled:**
- ✅ Ideation, Design, Architect, Review, Implement
- ✅ Code Review, Validate, Fix
- ✅ Document (minimal)
- ⚠️ Package (optional)

**Quality tier:** Moderate
- Basic security (OWASP Top 10)
- API docs only
- Basic packaging optional

**Model tier suggestion:** Hybrid or Recommended

---

### 5. Personal (Self-Use Tool)
**When to use:** Tools you'll use yourself, small utilities
**Questions asked:** 7-10 questions
- Who is the primary user?
- Daily usage scenario?
- Key pain point being addressed?
- Preferred tech stack?

**Agents enabled:**
- ✅ All agents except Package
- ⚠️ Document (standard), Fix (full)

**Quality tier:** Standard
- Unit + integration tests
- Standard documentation
- Basic security review

**Model tier suggestion:** Recommended

---

### 6. Internal (Business Tool)
**When to use:** Company-internal tools, employee productivity apps
**Questions asked:** 8-12 comprehensive questions
- Who are the users?
- Data sensitivity level?
- Integration requirements?
- Security requirements?
- Deployment environment?
- Maintenance plan?

**Agents enabled:**
- ✅ All agents including Package
- 🔒 Enhanced security checks
- 🔒 Compliance validation based on domain

**Quality tier:** High
- Full test coverage
- Standard documentation
- Security scanning (Trivy)
- Basic packaging

**Model tier suggestion:** Recommended or Premium

---

### 7. Product (Commercial Product)
**When to use:** Public-facing products, products for sale
**Questions asked:** 10-15 detailed questions
- Target market?
- Revenue model?
- Distribution channels?
- Support requirements?
- Scalability needs?
- Update/release strategy?

**Agents enabled:**
- ✅ All agents with full rigor
- 🔒 Security audit
- 🔒 Performance testing
- 🔒 Compliance validation

**Quality tier:** High
- Full test suite (unit, integration, E2E)
- Full documentation (user guide, API docs)
- Security audit
- Professional packaging

**Model tier suggestion:** Recommended or Premium

---

### 8. Business/Enterprise (High-Stakes)
**When to use:** Enterprise software, high-revenue products, regulated industries
**Questions asked:** 12-20 exhaustive questions
- Company details (size, structure)?
- Regulatory compliance requirements?
- Data governance policy?
- Incident response plan?
- SLA requirements?
- Team structure and roles?
- Budget and ROI timeline?
- International expansion plans?

**Agents enabled:**
- ✅ All agents with maximum rigor
- 🔒 Security audit + penetration testing
- 🔒 Compliance validation
- 🔒 Accessibility audit
- 🔒 Privacy audit

**Quality tier:** Maximum
- Enterprise-grade testing
- Full compliance documentation
- Security audit report
- Professional packaging with signing
- Release management

**Model tier suggestion:** Premium

---

## Product Domains (Compliance Triggers)

### Finance (Finance/Fintech)
**Triggers:**
- Security audit mandatory (any product type ≥ prototype)
- Transaction logging required
- Fraud detection considerations
- PCI DSS compliance for payment features

**Additional questions:**
- What type of financial data is handled?
- Payment processing method?
- Regulatory jurisdiction?

### Healthcare (Healthtech)
**Triggers:**
- HIPAA compliance validation
- Patient data encryption at rest/in transit
- Audit logs for all PHI access
- Age-appropriate design if involving minors

**Additional questions:**
- What level of health data (PHI/non-PHI)?
- User base (patients/providers/researchers)?
- Regulatory jurisdiction?

### E-commerce (Retail/Shopping)
**Triggers:**
- PCI DSS security scan
- Payment fraud detection
- Return/refund policy validation
- Inventory management considerations

**Additional questions:**
- Payment providers?
- Inventory system?
- Shipping logistics?

### Education (Edtech)
**Triggers:**
- COPPA compliance if involving minors
- FERPA for student records
- Accessibility compliance (WCAG)
- Parental consent workflows

**Additional questions:**
- Target age group?
- Student data handling?
- Institutional vs consumer?

### Social Networking
**Triggers:**
- GDPR data privacy compliance
- Content moderation requirements
- Data export/portability support
- Age verification

**Additional questions:**
- Public vs private network?
- Content types?
- User-generated content moderation?

### Government/Public Sector
**Triggers:**
- Section 508 accessibility compliance
- FedRAMP/FISMA security controls (US)
- Open source requirements
- Public records requirements

**Additional questions:**
- Jurisdiction?
- Public accessibility requirements?
- Security clearance levels?

### IoT/Embedded
**Triggers:**
- Firmware security review
- OTA update mechanism
- Device authentication
- Data encryption

**Additional questions:**
- Device types and count?
- Network connectivity?
- Update frequency expectations?

### AI/ML
**Triggers:**
- Model security review
- Data privacy for training data
- Bias detection and mitigation
- Explainability requirements

**Additional questions:**
- Training data sources?
- Model deployment target?
- Explainability requirements?

### Blockchain/Crypto
**Triggers:**
- Smart contract security audit
- Wallet security review
- Regulatory compliance (varies by jurisdiction)
- Tokenomics validation

**Additional questions:**
- Blockchain platform?
- Token type (utility/security)?
- Jurisdiction for compliance?

### Productivity Tools
**No special triggers.** Standard development practices apply.

### Gaming
**Triggers:**
- Performance optimization focus
- Player data privacy (if social features)
- Age-appropriate content

**Additional questions:**
- Target platforms?
- Multiplayer features?
- Monetization model?

### General (Default)
**No special triggers.** Standard requirements apply based on product type.

---

## Agent Selection Matrix

### Default Agents (All Product Types)
- **ideation** - Always
- **design** - Always
- **architect** - Always
- **review** - Always
- **implement** - Always

### Conditional Agents

| Agent | Exploration | Learning | Fun | Prototype | Personal | Internal | Product | Business |
|-------|------------|----------|-----|-----------|----------|----------|---------|----------|
| **code-review** | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **validate** | ✅ (basic) | ✅ (unit) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **fix** | ❌ | ❌ | ⚠️ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **document** | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **package** | ❌ | ❌ | ⚠️ | ⚠️ | ⚠️ | ✅ | ✅ | ✅ |

Legend:
- ✅ Required
- ⚠️ Optional/conditional
- ❌ Not required

---

## Adaptive Question Framework

### Question Depth by Product Type

**Exploration (2-3 questions):**
1. Core idea/concept
2. Technologies to explore
3. (Optional) Expected outcome

**Learning (4-5 questions):**
1. Core idea/concept
2. Skills/knowledge to gain
3. Preferred learning approach
4. (Optional) Target outcome
5. (Optional) Constraints

**Fun/Hobby (5-7 questions):**
1. Core idea/concept
2. Target users (if any)
3. Key features you're excited about
4. Tech stack preferences
5. (Optional) Timeline
6. (Optional) Inspiration sources
7. (Optional) Success criteria

**Prototype/MVP (6-8 questions):**
1. Core idea/concept
2. Target audience
3. Problem being solved
4. Key features for MVP
5. Success metrics
6. (Optional) Monetization approach
7. (Optional) Budget estimate
8. (Optional) Launch timeline

**Personal (7-10 questions):**
1. Core idea/concept
2. Target user (yourself)
3. Problem being solved
4. Key features
5. Tech stack preferences
6. Deployment approach
7. (Optional) Timeline
8. (Optional) Success criteria
9. (Optional) Similar tools you've tried

**Internal (8-12 questions):**
1. Core idea/concept
2. Target users (departments, roles)
3. Problem being solved
4. Key features
5. Integration requirements
6. Data sensitivity level
7. Security requirements
8. Deployment environment
9. (Optional) Budget estimate
10. (Optional) Timeline
11. (Optional) Maintenance plan
12. (Optional) Success metrics

**Product (10-15 questions):**
1. Core idea/concept
2. Target market
3. Problem being solved
4. Key features
5. Revenue model
6. Distribution channels
7. Support requirements
8. Scalability needs
9. Update/release strategy
10. (Optional) Budget/timeline
11. (Optional) Competition analysis
12. (Optional) Pricing model
13. (Optional) Launch timeline
14. (Optional) Success metrics
15. (Optional) Team structure

**Business/Enterprise (12-20 questions):**
1. Core idea/concept
2. Company context (size, industry)
3. Target users/audiences
4. Problem being solved
5. Key features
6. Revenue model
7. Regulatory compliance
8. Data governance
9. Integration requirements
10. Scalability needs
11. Security requirements
12. Deployment environment
13. Support/maintenance plan
14. Update/release strategy
15. Team structure/roles
16. Budget and ROI timeline
17. (Optional) International expansion
18. (Optional) Incident response
19. (Optional) SLA requirements
20. (Optional) Success metrics

### Domain-Specific Questions

When a domain is selected, 1-3 additional questions are asked:

- **Finance:** Data sensitivity, payment processing, regulatory jurisdiction
- **Healthcare:** PHI handling level, user types, regulatory jurisdiction
- **E-commerce:** Payment providers, inventory system, shipping logistics
- **Education:** Target age group, student data handling, institutional vs consumer
- **Social:** Network visibility, content types, moderation needs
- **Government:** Jurisdiction, accessibility requirements, security tier
- **IoT:** Device types/count, connectivity, update frequency
- **AI/ML:** Training data sources, deployment target, explainability needs
- **Blockchain:** Blockchain platform, token type, jurisdiction
- **Productivity:** No additional questions
- **Gaming:** Target platforms, multiplayer features, monetization
- **General:** No additional questions

---

## Model Tier Suggestions

| Product Type | Default Tier | Rationale |
|---------------|-------------|-----------|
| Exploration | zenfree | Cost-effective for experiments |
| Learning | recommended | Quality matters for education |
| Fun | recommended | Balance of quality and cost |
| Prototype | hybrid | Recommended for design, cheap for implementation |
| Personal | recommended | Good quality for self-use |
| Internal | recommended | Professional quality needed |
| Product | premium | Maximum quality for commercial |
| Business | premium | Enterprise-grade quality required |

---

## Quality Tiers

| Tier | Test Coverage | Security | Documentation | Packaging |
|------|--------------|----------|---------------|-----------|
| Minimal | Smoke tests only | None | None | None |
| Basic | Unit tests | OWASP Top 10 | Educational | None |
| Moderate-low | Unit + basic | Basic scan | README only | Optional |
| Moderate | Unit + integration | Basic scan | Minimal | Optional |
| Standard | Full suite | Security scan | Standard | Basic |
| High | Full + E2E | Audit + scan | Full | Full |
| Maximum | Full + E2E + perf | Audit + pentest | Full + compliance | Professional |

## Implementation Notes

1. Users can override auto-selected quality tier during ideation
2. Domain-specific requirements can escalate quality tiers (e.g., finance domain always escalates to at least "High" for product/business types)
3. The pipeline skips Document/Package stages if not selected
4. Model tier can be changed at any time via `/models <tier>`