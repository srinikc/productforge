# Maintenance Agent

## Purpose
Handles post-deployment maintenance, monitoring, bug fixes, patches, performance optimization, and ongoing product health.

## Trigger
- After `devops` stage completes deployment
- On schedule (daily/weekly maintenance windows)
- On-demand: `/pipeline maintain [project]`
- On alert: When issues are detected

## Responsibilities

### 1. Monitoring & Alerting
- Application performance monitoring (APM)
- Error tracking and reporting
- Uptime monitoring
- Resource utilization
- Custom metrics and alerts

### 2. Issue Management
- Bug triage and prioritization
- Issue tracking and assignment
- Root cause analysis
- Fix verification
- Regression prevention

### 3. Patch Management
- Security patch application
- Dependency updates
- CVE monitoring
- Patch testing
- Rollback procedures

### 4. Performance Optimization
- Database query optimization
- Caching strategies
- Code profiling
- Load testing
- Scalability improvements

### 5. Health Checks
- Daily health checks
- Weekly performance reviews
- Monthly capacity planning
- Quarterly security audits
- Annual architecture review

### 6. Incident Response
- 24/7 on-call rotation
- Incident classification
- Escalation procedures
- Post-mortem analysis
- Communication plan

### 7. Maintenance Windows
- Scheduled maintenance
- Zero-downtime deployments
- Database migrations
- Cache clearing
- Log rotation

## Outputs

```
products/<name>/maintenance/
├── monitoring-config.md       # Monitoring setup
├── alert-rules.md             # Alert configuration
├── runbook.md                 # Operational procedures
├── incident-log.md            # Incident history
├── patch-log.md               # Patch history
├── performance-report.md      # Performance metrics
├── health-check.md            # Health check results
└── maintenance-schedule.md    # Maintenance calendar
```

## Commands

| Command | Description |
|---------|-------------|
| `/pipeline maintain [project]` | Run maintenance check |
| `/pipeline maintain monitor [project]` | Setup monitoring |
| `/pipeline maintain patch [project]` | Apply patches |
| `/pipeline maintain health [project]` | Health check |
| `/pipeline maintain incident [project]` | Incident response |

## Model Recommendations

| Task | Recommended Model | Free Alternative |
|------|-------------------|------------------|
| Monitoring | nemotron-3-ultra-free | mimo-v2.5-free |
| Triage | mimo-v2.5-free | mimo-v2.5-free |
| Root cause | hy3-free | mimo-v2.5-free |
| Documentation | mimo-v2.5-free | mimo-v2.5-free |

## Integration Points

- Reads from `products/<name>/` for product details
- Reads from `reports/` for test results
- Reads from `logs/` for error logs
- Outputs to `products/<name>/maintenance/`
- Connects to monitoring tools (Datadog, New Relic, Sentry)
- Integrates with incident management (PagerDuty, Opsgenie)
