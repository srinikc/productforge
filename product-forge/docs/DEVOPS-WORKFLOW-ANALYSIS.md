# DevOps Agent Workflow Analysis

## Current State (What Exists)

### DevOps Agent Current Role
- **Stage**: 13 (post-Package)
- **Responsibilities**: CI/CD, deployment, monitoring, cloud integration
- **Input**: Packaged artifacts from Package agent
- **Output**: CI/CD configs, deployment configs, monitoring setup

### What's Missing
1. **Build generation during implementation** — DevOps should generate builds, not a Python module
2. **Test framework integration** — DevOps should connect builds to test framework
3. **Deployment during pipeline** — DevOps should deploy for testing, not just at the end
4. **Production deployment** — DevOps should handle actual deployment

---

## Correct Workflow Analysis

### Phase 1: Implementation (Stage 4a/4b/4c)

```
implement writes code
    ↓
devops generates build (Docker, web, mobile)
    ↓
code-review reviews code
    ↓
fix fixes issues (if any)
    ↓
validate runs tests against build
    ↓
validate logs results to test cycle
    ↓
human approves
```

**Why DevOps should generate builds:**
- DevOps owns the build pipeline
- DevOps knows how to containerize
- DevOps manages CI/CD — builds are part of that
- DevOps can integrate builds with test framework

### Phase 2: Post-Implementation (Stage 5-9)

```
security runs security scans
    ↓
validate runs NFR tests
    ↓
validate runs full test suite
    ↓
document creates docs
    ↓
package does detailed packaging (BOM, installers)
    ↓
devops sets up CI/CD pipeline
```

### Phase 3: Deployment (Stage 10-12)

```
devops deploys to staging
    ↓
human verifies in staging
    ↓
devops deploys to production
    ↓
devops monitors
```

---

## DevOps Agent Revised Responsibilities

### During Implementation (Stage 4a/4b/4c)

| Task | Description | Output |
|------|-------------|--------|
| **Generate Build** | Build Docker image, web bundle, mobile builds | `builds/<phase>/` |
| **Verify Build** | Ensure build works (docker run, serve, install) | Build verification report |
| **Connect to Test Framework** | Register build in test framework | Build version in test cycle |
| **Deploy for Testing** | Deploy build to test environment | Test environment URL |

### Post-Implementation (Stage 5-9)

| Task | Description | Output |
|------|-------------|--------|
| **CI/CD Setup** | Create GitHub Actions, GitLab CI, etc. | `.github/workflows/` |
| **Security Integration** | Add security scans to CI/CD | Security scan configs |
| **Test Integration** | Add test framework to CI/CD | Test execution in CI |
| **Monitoring Setup** | Configure Prometheus, Grafana | Monitoring dashboards |

### Deployment (Stage 10-12)

| Task | Description | Output |
|------|-------------|--------|
| **Deploy to Staging** | Deploy to staging environment | Staging URL |
| **Deploy to Production** | Deploy to production environment | Production URL |
| **Rollback Plan** | Create rollback procedures | Rollback docs |
| **Monitoring** | Set up production monitoring | Alert configs |

---

## Revised Pipeline Flow

```
Stage 0: Ideation
    ↓
Stage 1: Design (with wireframe review)
    ↓
Stage 2: Architect (with multi-model review)
    ↓
Stage 3: Refine Requirements
    ↓
Stage 4-0: Skeleton → devops builds skeleton → verify build works
    ↓
Stage 4a: Phase 1 Features
    ├── implement writes code
    ├── devops generates build (Docker + web + mobile)
    ├── code-review reviews code
    ├── fix fixes issues (if any)
    ├── validate runs tests against build
    ├── validate logs results to test cycle
    └── HIL: Human approves
    ↓
Stage 4b: Phase 2 Features
    ├── implement writes code
    ├── devops generates build (incremental)
    ├── code-review reviews code
    ├── fix fixes issues
    ├── validate runs tests
    ├── validate logs to test cycle
    └── HIL: Human approves
    ↓
Stage 4c: Phase 3 Features
    ├── implement writes code
    ├── devops generates build (incremental)
    ├── code-review reviews code
    ├── fix fixes issues
    ├── validate runs tests
    ├── validate logs to test cycle
    └── HIL: Human approves
    ↓
Stage 5: Security Scan (security agent)
    ↓
Stage 6: NFR Tests (validate agent)
    ↓
Stage 7: Full Test Suite (validate agent)
    ↓
Stage 8: Document (document agent)
    ↓
Stage 9: Package (package agent — detailed: BOM, installers)
    ↓
Stage 10: Pre-Production
    ├── devops sets up CI/CD pipeline
    ├── devops configures monitoring
    └── orchestrator generates final summary
    ↓
Stage 11: Deploy
    ├── devops deploys to staging
    ├── human verifies in staging
    ├── devops deploys to production
    └── devops sets up monitoring
    ↓
Stage 12: Exit
```

---

## DevOps Agent Updated Contract

### During Implementation Stages (4-0, 4a, 4b, 4c)

**Input:**
- Source code from implement agent
- `docs/architecture.md`
- `docs/requirements.md`

**Output:**
- `builds/<phase>/docker/` — Docker image
- `builds/<phase>/web/` — Web bundle
- `builds/<phase>/ios/` — iOS build (if applicable)
- `builds/<phase>/android/` — Android build (if applicable)
- `builds/<phase>/build-manifest.json` — Build manifest
- Build version registered in test framework

**Actions:**
1. Generate Docker image
2. Generate web bundle
3. Generate mobile builds (if applicable)
4. Verify builds work
5. Register build version in test framework
6. Deploy to test environment (if needed)

### Post-Implementation Stages (5-9)

**Input:**
- All source code
- `docs/architecture.md`
- Security reports
- Test results

**Output:**
- `.github/workflows/` — CI/CD pipeline
- `deploy/` — Deployment configs
- `monitoring/` — Monitoring setup
- `reports/ci-cd-report.md` — CI/CD setup report

**Actions:**
1. Create CI/CD pipeline
2. Add security scans to CI/CD
3. Add test framework to CI/CD
4. Set up monitoring
5. Configure alerts

### Deployment Stages (10-12)

**Input:**
- Packaged artifacts from package agent
- CI/CD configs
- Deployment configs

**Output:**
- Deployed application
- Production URL
- Monitoring dashboards
- Rollback plan

**Actions:**
1. Deploy to staging
2. Verify in staging
3. Deploy to production
4. Set up monitoring
5. Create rollback plan

---

## Summary

| Stage | DevOps Responsibility |
|-------|----------------------|
| 4-0, 4a, 4b, 4c | Generate builds, register in test framework |
| 5-9 | Set up CI/CD, monitoring, deployment configs |
| 10-11 | Deploy to staging, then production |
| 12 | Exit (cleanup) |

**Key Change:** DevOps is now involved from Stage 4 (implementation), not just Stage 13 (post-package).

**Build Ownership:** DevOps generates builds, not implement agent. Implement writes code, DevOps builds it.

**Test Framework Integration:** DevOps registers build version in test framework, so test cycles know which build was tested.
