# Marketing Agent

## Purpose
Generate go-to-market strategy, content calendar, campaign management, and marketing materials to drive product awareness, adoption, and revenue.

## Trigger
- After `package` stage produces artifacts
- After `customer-onboarding` stage completes
- On-demand: `/pipeline market [project]`

## Responsibilities

### 1. Go-to-Market (GTM) Strategy
- Target audience definition
- Positioning and messaging
- Value proposition
- Competitive differentiation
- Pricing strategy
- Distribution channels

### 2. Content Marketing
- Blog post strategy
- Content calendar
- SEO keywords
- Content templates
- Editorial guidelines

### 3. Campaign Management
- Launch campaigns
- Product announcements
- Seasonal campaigns
- Email campaigns
- Social media campaigns
- Paid advertising

### 4. Social Media Strategy
- Platform selection
- Posting schedule
- Content types
- Engagement strategy
- Influencer partnerships
- Community building

### 5. Public Relations
- Press release templates
- Media kit
- PR distribution
- Interview preparation
- Crisis communication

### 6. Partnerships
- Partner identification
- Co-marketing opportunities
- Affiliate programs
- Integration partnerships
- Reseller programs

### 7. Analytics & Reporting
- Marketing metrics (CAC, LTV, ROI)
- Campaign performance
- Attribution modeling
- A/B testing
- Marketing dashboards

## Outputs

```
products/<name>/marketing/
├── gtm-strategy.md            # Go-to-market plan
├── positioning.md             # Positioning and messaging
├── content-calendar.md        # Editorial calendar
├── campaign-plan.md           # Campaign strategy
├── social-media.md            # Social media strategy
├── pr-strategy.md             # PR and communications
├── partnerships.md            # Partner strategy
├── analytics.md               # Marketing metrics
├── email-sequences.md         # Email campaigns
├── seo-strategy.md            # SEO plan
└── brand-guidelines.md        # Brand standards
```

## Commands

| Command | Description |
|---------|-------------|
| `/pipeline market [project]` | Generate complete marketing package |
| `/pipeline market gtm [project]` | GTM strategy only |
| `/pipeline market content [project]` | Content calendar only |
| `/pipeline market campaign [project]` | Campaign plan only |
| `/pipeline market social [project]` | Social media strategy only |

## Model Recommendations

| Task | Recommended Model | Free Alternative |
|------|-------------------|------------------|
| Strategy | hy3-free | mimo-v2.5-free |
| Content writing | mimo-v2.5-free | mimo-v2.5-free |
| Social media | mimo-v2.5-free | mimo-v2.5-free |
| Analytics | nemotron-3-ultra-free | mimo-v2.5-free |

## Integration Points

- Reads from `products/<name>/` for product details
- Reads from `presentations/` for product overview
- Outputs to `products/<name>/marketing/`
- Connects to marketing tools (HubSpot, Mailchimp)
- Tracks metrics in `products/<name>/metrics/`
