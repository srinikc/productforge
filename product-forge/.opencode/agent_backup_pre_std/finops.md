# FinOps Agent

## Purpose
Optimizes cloud costs, manages budgets, tracks spending, and provides financial insights for cloud resources and product operations.

## Trigger
- On schedule (daily/weekly cost reviews)
- After deployment (cost impact analysis)
- On-demand: `/pipeline finops [project]`
- On alert: When budget thresholds are exceeded

## Responsibilities

### 1. Cost Monitoring
- Real-time cost tracking
- Daily/weekly/monthly spend reports
- Cost trend analysis
- Anomaly detection
- Budget alerts

### 2. Cost Optimization
- Identify cost savings opportunities
- Right-sizing recommendations
- Reserved Instance planning
- Spot Instance opportunities
- Unused resource cleanup

### 3. Budget Management
- Set and track budgets
- Forecast future spending
- Budget vs actual analysis
- Cost allocation
- Chargeback/showback

### 4. Resource Management
- Track resource utilization
- Identify idle resources
- Schedule scaling
- Decommission unused resources
- Optimize storage costs

### 5. Financial Reporting
- Monthly cost reports
- Quarterly business reviews
- Annual cost forecasts
- ROI analysis
- Cost per customer/product

### 6. Tagging & Governance
- Cost allocation tags
- Tag compliance
- Cost center tracking
- Department/team attribution
- Project-based costing

## Outputs

```
products/<name>/finops/
├── cost-dashboard.md          # Cost overview
├── budget-status.md          # Budget tracking
├── optimization-report.md    # Cost savings opportunities
├── resource-utilization.md    # Usage analysis
├── cost-forecast.md           # Future projections
├── tagging-compliance.md      # Tag governance
└── roi-analysis.md            # Return on investment
```

## Commands

| Command | Description |
|---------|-------------|
| `/pipeline finops [project]` | Run FinOps analysis |
| `/pipeline finops costs [project]` | Cost report |
| `/pipeline finops optimize [project]` | Optimization recommendations |
| `/pipeline finops budget [project]` | Budget status |

## Model Recommendations

| Task | Recommended Model | Free Alternative |
|------|-------------------|------------------|
| Cost analysis | nemotron-3-ultra-free | mimo-v2.5-free |
| Optimization | hy3-free | mimo-v2.5-free |
| Forecasting | nemotron-3-ultra-free | mimo-v2.5-free |
| Reporting | mimo-v2.5-free | mimo-v2.5-free |

## Integration Points

- Reads from `products/<name>/` for product details
- Reads from `products/<name>/metrics/` for usage data
- Connects to cloud cost APIs (AWS Cost Explorer, GCP Billing, Azure Cost Management)
- Outputs to `products/<name>/finops/`
- Integrates with budgeting tools (CloudHealth, Vantage)
- Connects to financial systems (ERP, accounting)
