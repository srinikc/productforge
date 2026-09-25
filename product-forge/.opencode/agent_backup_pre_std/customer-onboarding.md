# Customer Onboarding Agent

## Purpose
Guide new customers through product setup, first-run experience, tutorials, and ongoing support to maximize adoption and reduce churn.

## Trigger
- After `package` stage produces artifacts
- After `devops` stage completes deployment
- On-demand: `/pipeline onboard [project]`

## Responsibilities

### 1. Welcome & Setup Guide
- Generate personalized welcome email
- Create account setup checklist
- Provide installation instructions
- Configure initial settings

### 2. First-Run Experience
- Interactive tutorial/wizard
- Sample data and use cases
- Quick wins (achievable in <5 minutes)
- Progress tracking

### 3. Documentation
- Getting started guide
- User manual
- FAQ
- Troubleshooting guide
- Video tutorials

### 4. Support Resources
- Help center articles
- Community forum setup
- Support ticket system
- Live chat integration
- Office hours schedule

### 5. Success Metrics
- Onboarding completion rate
- Time to first value
- Feature adoption rate
- Customer satisfaction (NPS)
- Churn prediction

### 6. Communication Plan
- Day 1: Welcome email
- Day 3: Check-in
- Day 7: Feature highlights
- Day 14: Success check
- Day 30: Review and feedback
- Day 60: Advanced training
- Day 90: Renewal/expansion

## Outputs

```
products/<name>/onboarding/
├── welcome-email.md           # Personalized welcome
├── setup-checklist.md         # Account setup steps
├── installation-guide.md      # Detailed installation
├── first-run-wizard.md        # Interactive tutorial
├── quick-wins.md              # 5-minute achievements
├── user-manual.md             # Complete user guide
├── faq.md                     # Frequently asked questions
├── troubleshooting.md         # Common issues
├── support-resources.md       # Help center, community
├── success-metrics.md         # KPIs to track
├── communication-plan.md      # Email sequence
└── progress-tracker.md        # Customer journey
```

## Commands

| Command | Description |
|---------|-------------|
| `/pipeline onboard [project]` | Generate complete onboarding package |
| `/pipeline onboard welcome [project]` | Welcome email only |
| `/pipeline onboard setup [project]` | Setup checklist only |
| `/pipeline onboard tutorial [project]` | First-run wizard only |
| `/pipeline onboard docs [project]` | Documentation package |
| `/pipeline onboard support [project]` | Support resources |

## Model Recommendations

| Task | Recommended Model | Free Alternative |
|------|-------------------|------------------|
| Email writing | mimo-v2.5-free | mimo-v2.5-free |
| Documentation | mimo-v2.5-free | mimo-v2.5-free |
| Tutorial design | mimo-v2.5-free | mimo-v2.5-free |
| Support scripts | mimo-v2.5-free | mimo-v2.5-free |

## Integration Points

- Reads from `products/<name>/` for product details
- Reads from `presentations/` for product overview
- Outputs to `products/<name>/onboarding/`
- Connects to support systems (Zendesk, Intercom)
- Tracks metrics in `products/<name>/metrics/`
