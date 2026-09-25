# Business Knowledge Layer

## Overview

The Business Knowledge Layer provides essential business context for 20 common business types. Each business type includes:

- **Core Processes**: Key business processes and workflows
- **Integrations**: Common third-party integrations
- **Metrics**: Key performance indicators (KPIs)
- **Compliance**: Regulatory requirements
- **Tech Stack**: Recommended technology choices

## Business Types (20)

| # | Type | Description |
|---|------|-------------|
| 1 | SaaS | Software as a Service |
| 2 | E-commerce | Online retail |
| 3 | Content Platform | Content management and publishing |
| 4 | Marketplace | Multi-sided platform |
| 5 | Agency | Professional services |
| 6 | Fintech | Financial technology |
| 7 | Healthtech | Healthcare technology |
| 8 | Edtech | Education technology |
| 9 | Real Estate | Property management |
| 10 | Logistics | Supply chain and delivery |
| 11 | Hospitality | Travel and accommodation |
| 12 | Media & Entertainment | Digital media |
| 13 | Non-profit | charitable organizations |
| 14 | Enterprise | B2B software |
| 15 | Consumer App | B2C mobile/web apps |
| 16 | API Platform | Developer tools |
| 17 | IoT | Internet of Things |
| 18 | AI/ML | Artificial Intelligence |
| 19 | Gaming | Video games |
| 20 | Social Network | Social platforms |

## Usage

The knowledge router loads business context based on the project type. When a user describes their idea, the system:

1. Classifies the business type
2. Loads relevant processes, integrations, and metrics
3. Provides context to agents for better decision-making

## File Structure

```
docs/guidelines/business/
├── README.md                    # This file
├── business-types.json          # Master list of business types
├── saas.md                      # SaaS business model
├── ecommerce.md                 # E-commerce business model
├── content-platform.md          # Content platform business model
├── marketplace.md               # Marketplace business model
├── agency.md                    # Agency business model
├── fintech.md                   # Fintech business model
├── healthtech.md                # Healthtech business model
├── edtech.md                    # Edtech business model
├── real-estate.md               # Real estate business model
├── logistics.md                 # Logistics business model
├── hospitality.md               # Hospitality business model
├── media-entertainment.md       # Media & entertainment business model
├── non-profit.md                # Non-profit business model
├── enterprise.md                # Enterprise business model
├── consumer-app.md              # Consumer app business model
├── api-platform.md              # API platform business model
├── iot.md                       # IoT business model
├── ai-ml.md                     # AI/ML business model
├── gaming.md                    # Gaming business model
└── social-network.md            # Social network business model
```
