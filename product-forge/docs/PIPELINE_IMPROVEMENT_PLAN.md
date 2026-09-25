# Pipeline Improvement Plan

> **Product:** MyWorld  
> **Created:** 2026-09-01  
> **Status:** Draft — Review Required  
>
> **Consolidated tracker:** see [`docs/CHANGE-PLAN.md`](CHANGE-PLAN.md) for the
> live, single-source list of done / pending / separate items across all plan
> documents. This document's remaining items are tracked there (PART 4).

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Human-in-the-Loop (HIL)](#2-human-in-the-loop-hil)
3. [Implementation Phasing](#3-implementation-phasing)
4. [Test Framework Integration](#4-test-framework-integration)
5. [Multi-Model Review for Architecture/Design](#5-multi-model-review-for-architecturedesign)
6. [Knowledge Base Integration](#6-knowledge-base-integration)
7. [Dashboard Improvements](#7-dashboard-improvements)
8. [Code Review Per Phase](#8-code-review-per-phase)
9. [Security Comprehensive](#9-security-comprehensive)
10. [Packaging Comprehensive](#10-packaging-comprehensive)
11. [Final Summary Report](#11-final-summary-report)
12. [Port Configuration](#12-port-configuration)
13. [Pipeline Exit Mechanism](#13-pipeline-exit-mechanism)
14. [State File Ownership](#14-state-file-ownership)
15. [Architecture Completeness Checklist](#15-architecture-completeness-checklist)
16. [Agent-to-Agent Delegation (Opt-In)](#16-agent-to-agent-delegation-opt-in)
17. [Token/Cost Governance (Telemetry, Budgets, Breakers)](#17-tokencost-governance-telemetry-budgets-breakers)

---

## 1. Executive Summary

The current pipeline produced documentation and scaffolding but **NOT a working product**. The Product Forge pipeline has the right structure but fails at execution — agents generate markdown reports instead of working code, validation checks file existence rather than functionality, and there is no mechanism for intermediate verification between stages.

### Root Cause Analysis

| # | Problem | Impact | Root Cause |
|---|---------|--------|------------|
| 1 | Agents write markdown reports instead of working code | No executable product | Agent contracts allow markdown as "completion" |
| 2 | Validation checks file existence, not functionality | False positives — files exist but don't work | Validation scripts only check `exists()` |
| 3 | No human-in-the-loop between stages | Errors compound silently | Pipeline runs end-to-end without gates |
| 4 | Implementation is one giant block (13 features) | Agent runs out of context, produces scaffolding | No phasing strategy |
| 5 | Test framework exists but is not integrated | No automated verification | Pipeline never calls test runner |
| 6 | Knowledge base exists but agents don't use it | Agents don't follow project guidelines | No router invocation in agent contracts |
| 7 | Dashboard is static, not live | No real-time visibility | Dashboard reads static HTML, not pipeline state |
| 8 | No periodic updates during execution | User has no visibility into progress | No progress reporting mechanism |
| 9 | No final summary report | No audit trail or deliverable summary | No final stage in pipeline |

### Goal

Transform the pipeline from "documentation generator" to "product builder" by implementing phased execution, human checkpoints, integrated testing, and comprehensive verification at every stage.

---

## 2. Human-in-the-Loop (HIL)

### 2.1 Required HIL Points

The pipeline MUST pause at each gate and present results to the human for review. No stage proceeds without explicit approval.

| After Stage | What Human Reviews | Duration | Gate Type |
|-------------|-------------------|----------|-----------|
| 0 Ideation | Scope, features, priorities | 2–3 min | Approve/Reject scope |
| 1 Design | Requirements + UX design | 5–10 min | Approve/Reject design |
| 2 Architecture | Tech stack + NFRs + architecture diagram | 5–10 min | Approve/Reject architecture |
| 4a Phase 1 | Auth + Dashboard + Search + ToDo — actually working | 10–15 min | Approve/Request changes |
| 4b Phase 2 | Calendar + Goals + News + Health | 10–15 min | Approve/Request changes |
| 4c Phase 3 | Exploratory + Spiritual + Documents + Financial | 10–15 min | Approve/Request changes |
| 4d Phase 4 | Mobile app | 5–10 min | Approve/Request changes |
| 8 Document | User docs + install guide | 5 min | Approve docs |
| 9 Package | Docker build output | 5 min | Approve package |
| 10 Pre-Production | Final walkthrough | 10 min | Final approval |
| 11 Deploy | Staging verification | 5 min | Deploy go/no-go |

### 2.2 Human Review Interface

When the pipeline reaches a HIL point, it MUST:

1. **Pause execution** — No automatic progression
2. **Display a summary** — What was completed, what was produced, what needs review
3. **Provide evidence** — Links to files, screenshots, test results, working URLs
4. **Offer actions** — Approve, Request Changes, Skip (with reason)
5. **Wait for response** — Block until human responds

```
═══════════════════════════════════════════════════════
HUMAN REVIEW GATE — Stage 4a: Phase 1 Implementation
═══════════════════════════════════════════════════════

Status: WAITING FOR APPROVAL

Phase 1 Features Completed:
  ✅ F-012: Authentication (login, register, JWT)
  ✅ F-011: Dashboard (widgets, layout, theme)
  ✅ F-003: Search (full-text, filters, results)
  ✅ F-004: ToDo (CRUD, categories, priority)

Working Product:
  → Web: http://localhost:3000
  → API: http://localhost:8000/docs

Test Results:
  → Unit: 45/45 passed
  → API: 12/12 passed
  → Feature: 8/8 passed
  → UI: 6/6 passed

Actions:
  [1] Approve — proceed to Phase 2
  [2] Request Changes — describe what to fix
  [3] Skip — proceed without approval (not recommended)

Your choice:
```

### 2.3 Periodic Update Format

After EACH agent completes work, the pipeline MUST display a progress summary:

```
═══════════════════════════════════════════════════════
AGENT WORK SUMMARY
═══════════════════════════════════════════════════════

Status: COMPLETED

Previous Agent: [name]
Current Agent:  [name]
Model Name:     [model-id]
Scope:          [what was requested]
Start Time:     [HH:MM]
End Time:       [HH:MM]
Time Taken:     [X min]

Implemented:
- [feature 1]: [brief description]
- [feature 2]: [brief description]

Artifacts Created:
- [file1] ([size])
- [file2] ([size])

Verification Done:
- [what was checked and result]

Tokens Used: [N]
Stage: [N]
Phase: [if applicable]

Issues Found: [count]
[If issues: list them]

Next Agent: [name]
Action Needed: [approve / fix / continue]

State Files Updated:
- [file] ✅
- [file] ✅
═══════════════════════════════════════════════════════
```

**Minimum fields for every update:**
- Agent name and model
- What was done (scope)
- What was produced (artifacts)
- What was verified (results)
- Token usage
- Issues found (if any)
- Next agent and required action

---

## 3. Implementation Phasing

### 3.1 Why Phase Implementation

| Reason | Explanation |
|--------|-------------|
| 13 features is too much for one agent run | Agent context window fills up; quality degrades |
| No intermediate verification possible | Can't test what isn't built yet |
| Scaffolding easier than real code | Agent defaults to stubs when overwhelmed |
| Bugs compound | One broken component breaks dependent components |
| Human can't review 13 features at once | Review fatigue leads to missed issues |

### 3.2 Proposed Phase Structure

```
PHASE 1: Foundation + Core (4 features)
┌─────────────────────────────────────────────────────┐
│ Features: Auth (F-012), Dashboard (F-011),         │
│           Search (F-003), ToDo (F-004)              │
│ Why: Foundation for everything else                 │
│ Duration: 1 agent run (focused on 4 features)       │
│ Verify: docker compose build && up → browser test   │
│ Human: Reviews each feature in browser              │
│ Code Review: After implementation, before next phase│
└─────────────────────────────────────────────────────┘
              ↓ Human Approves ↓
PHASE 2: Content Features (4 features)
┌─────────────────────────────────────────────────────┐
│ Features: Calendar (F-005), Goals (F-006),          │
│           News (F-007), Health (F-008)              │
│ Why: Content-heavy, can be added incrementally      │
│ Duration: 1 agent run                               │
│ Verify: All Phase 1 still works + new features      │
│ Human: Reviews each feature                         │
│ Code Review: After implementation, before next phase│
└─────────────────────────────────────────────────────┘
              ↓ Human Approves ↓
PHASE 3: Specialized Features (4 features)
┌─────────────────────────────────────────────────────┐
│ Features: Exploratory (F-009), Spiritual (F-010),   │
│           Documents (F-011), Financial (F-012)      │
│ Why: Complex features, depend on foundation         │
│ Duration: 1 agent run                               │
│ Verify: All previous phases still work + new        │
│ Human: Reviews each feature                         │
│ Code Review: After implementation, before next phase│
└─────────────────────────────────────────────────────┘
              ↓ Human Approves ↓
PHASE 4: Mobile (1 feature = 13 screens)
┌─────────────────────────────────────────────────────┐
│ Features: Mobile App (F-013)                        │
│ Why: Depends on web being complete                  │
│ Duration: 1 agent run                               │
│ Verify: Test on phone                               │
│ Human: Tests on device                              │
│ Code Review: After implementation, before packaging │
└─────────────────────────────────────────────────────┘
```

### 3.3 Phase Dependency Map

```
Phase 1 ──→ Phase 2 ──→ Phase 3 ──→ Phase 4
(Auth,      (Calendar,   (Explorer,   (Mobile
 Dash,       Goals,       Spiritual,   App)
 Search,     News,        Docs,
 ToDo)       Health)      Financial)
    │            │            │            │
    ↓            ↓            ↓            ↓
  Review       Review       Review       Review
  & Test       & Test       & Test       & Test
```

### 3.4 Code Review After Each Phase

```
Phase N Code
    │
    ↓
Code Review Agent
    │
    ├── Issues found? ──→ Fix Agent ──→ Re-review
    │                                        │
    │                    Clean? ←────────────┘
    │                       │
    │                  Yes  ↓
    │              Human Approves
    │                       │
    ↓                       ↓
Phase N+1 ─────────────→ Continue
```

---

## 4. Test Framework Integration

### 4.1 Current State

The test framework exists at `test-framework/` with:
- **Runner** — Executes tests, captures results
- **Test generator** — Creates test cases from requirements
- **Reporter** — Generates reports (HTML, JSON, Markdown)
- **Dashboard** — Live results at `localhost:3011`
- **Defect tracker** — Logs defects with severity
- **RCCA analyzer** — Root cause analysis

### 4.2 What's Missing

| Gap | Description | Priority |
|-----|-------------|----------|
| NFR test categories | Performance, security, scalability test types | High |
| Packaging test categories | Install, uninstall, upgrade test types | High |
| Feature-level test organization | Tests grouped by feature, not just type | High |
| Comments section | Why each test was run (audit trail) | Medium |
| Traceability matrix | Feature → Test → Requirement mapping | High |
| Pipeline integration | Test runner called after each phase | Critical |

### 4.3 Required Test Types Per Phase

| Phase | Test Types | When to Run |
|-------|-----------|-------------|
| Phase 1 (Auth, Dashboard, Search, ToDo) | Unit, API, Feature, UI | After each feature built |
| Phase 2 (Calendar, Goals, News, Health) | Unit, API, Feature, UI | After each feature built |
| Phase 3 (Exploratory, Spiritual, Documents, Financial) | Unit, API, Feature, UI | After each feature built |
| Phase 4 (Mobile) | Unit, UI (Playwright), E2E | After mobile built |
| After ALL phases | NFR (perf, security, a11y) | Before packaging |
| Packaging | Install, uninstall, upgrade | After package built |
| Deployment | Deploy, smoke test | After deploy |

### 4.4 Test Dashboard Requirements

The test dashboard (`localhost:3011`) MUST show:

```
┌──────────────────────────────────────────────────────────┐
│  TEST DASHBOARD — MyWorld v1.0.0                         │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Overview                                                │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                   │
│  │ 142  │ │ 138  │ │   2  │ │   2  │                   │
│  │Total │ │Pass  │ │Fail  │ │Block │                   │
│  └──────┘ └──────┘ └──────┘ └──────┘                   │
│                                                          │
│  Per-Feature Results                                     │
│  ┌─────────────────┬──────┬──────┬──────┬──────┐       │
│  │ Feature         │Unit  │API   │Feat  │UI    │       │
│  ├─────────────────┼──────┼──────┼──────┼──────┤       │
│  │ F-012 Auth      │ ✅   │ ✅   │ ✅   │ ✅   │       │
│  │ F-011 Dashboard │ ✅   │ ✅   │ ✅   │ ✅   │       │
│  │ F-003 Search    │ ✅   │ ✅   │ ⚠️   │ ✅   │       │
│  │ F-004 ToDo      │ ✅   │ ✅   │ ✅   │ ❌   │       │
│  └─────────────────┴──────┴──────┴──────┴──────┘       │
│                                                          │
│  Test Mode: [Sanity] [Feature] [NFR] [Full]             │
│                                                          │
│  Comments:                                               │
│  - F-003 Search: Feature test flaky on slow connections  │
│  - F-004 ToDo: UI test fails on Firefox 120+             │
│                                                          │
│  Traceability Matrix →                                   │
│  Screenshots →                                           │
│  Test Dashboard (localhost:3011) →                       │
└──────────────────────────────────────────────────────────┘
```

### 4.5 Test Dashboard Data Model

```json
{
  "test_run": {
    "id": "run-20260901-001",
    "project": "myworld",
    "version": "1.0.0",
    "mode": "feature",
    "started_at": "2026-09-01T10:00:00Z",
    "completed_at": "2026-09-01T10:15:00Z",
    "summary": {
      "total": 142,
      "passed": 138,
      "failed": 2,
      "blocked": 2,
      "skipped": 0
    },
    "features": [
      {
        "feature_id": "F-012",
        "feature_name": "Authentication",
        "phase": 1,
        "tests": {
          "unit": { "total": 12, "passed": 12, "failed": 0 },
          "api": { "total": 8, "passed": 8, "failed": 0 },
          "feature": { "total": 5, "passed": 5, "failed": 0 },
          "ui": { "total": 3, "passed": 3, "failed": 0 }
        },
        "comments": ["All auth flows verified"],
        "screenshots": ["login-success.png", "register-flow.png"]
      }
    ],
    "nfr_tests": {
      "performance": { "total": 10, "passed": 9, "failed": 1 },
      "security": { "total": 8, "passed": 8, "failed": 0 },
      "accessibility": { "total": 6, "passed": 6, "failed": 0 }
    },
    "traceability": [
      {
        "requirement": "FR-012.1",
        "feature": "F-012",
        "tests": ["T-012.1.1", "T-012.1.2"],
        "status": "pass"
      }
    ]
  }
}
```

---

## 5. Multi-Model Review for Architecture/Design

### 5.1 Current State

Single agent reviews design/architecture. This creates blind spots — one model's weakness is never caught by another model's strength.

### 5.2 Proposed Multi-Model Review

**Architecture Review (3 agents, parallel):**

| Agent | Model Focus | Review Angle |
|-------|------------|--------------|
| Agent 1 | General-purpose (e.g., mimo-v2.5-free) | Overall architecture, patterns, completeness |
| Agent 2 | Security-focused (e.g., nemotron-3-ultra-free) | Threats, vulnerabilities, OWASP compliance |
| Agent 3 | Performance-focused (e.g., hy3-free) | Scalability, caching, load handling |

**Design Review (2 agents, parallel):**

| Agent | Model Focus | Review Angle |
|-------|------------|--------------|
| Agent 1 | UX/functional | User flows, accessibility, usability |
| Agent 2 | Design system | Consistency, tokens, component reuse |

### 5.3 Review Merge Process

```
Agent 1 Review ──┐
Agent 2 Review ──┼──→ Orchestrator ──→ Merged Findings ──→ Human
Agent 3 Review ──┘        │
                          ↓
                   Dedup + Prioritize
                          │
                          ↓
                   Unified Report
```

### 5.4 Human Review After Architecture

When the Architect agent completes, the pipeline MUST show the human:

- [ ] All features listed (FR-001 through FR-013)
- [ ] All NFRs listed (NFR-001 through NFR-010)
- [ ] Tech stack selected (with justification)
- [ ] Architecture diagram (draw.io + PDF)
- [ ] Packaging plan (Docker, installers, BOM)
- [ ] Deployment plan (CI/CD, staging, production)
- [ ] Install/uninstall/upgrade/rollback/patching plan
- [ ] Port configuration
- [ ] Multi-model review findings (merged)

Human must approve before implementation begins.

---

## 6. Knowledge Base Integration

### 6.1 Current State

- Knowledge router exists: `core/knowledge_router.py`
- Auto-discovers 19 guidelines from `docs/guidelines/`
- Skills registry exists: `core/skills_registry.py`
- **Problem:** No agent currently calls the knowledge router

### 6.2 Required Fix

Each agent contract MUST include:

```yaml
agent_contract:
  name: "implement-agent"
  knowledge_router:
    enabled: true
    call_before: "work"
    query: "task_description"
    top_k: 5
    token_budget: 4000
  instructions: |
    Before starting work, call KnowledgeRouter.route(task_description)
    to load relevant guidelines. Load the top 3-5 resources within
    token budget. Reference loaded guidelines in your output.
```

### 6.3 Agent-Guideline Mapping

| Agent | Loads Guidelines | Why |
|-------|-----------------|-----|
| Design | `ui-ux/accessibility`, `frontend/react` | Follow project's UI standards |
| Architect | `architecture/decisions`, `cloud/aws`, `infrastructure/docker` | Follow project's infra standards |
| Implement (UI) | `frontend/react`, `ui-ux/accessibility` | Code style, a11y compliance |
| Implement (API) | `backend/fastapi`, `api/rest`, `database/postgresql` | API design, DB patterns |
| Implement (DB) | `database/postgresql` | Schema, migration patterns |
| Code Review | `testing/standards`, `security/owasp` | Review against standards |
| Security | `security/owasp`, `compliance/regulations` | Security requirements |
| Package | `infrastructure/docker`, `packaging/distribution` | Build standards |

### 6.4 Knowledge Router Invocation Flow

```
Agent receives task
    │
    ↓
KnowledgeRouter.route(task_description)
    │
    ↓
Returns top 5 guidelines (within token budget)
    │
    ├──→ guideline_1.md (loaded into context)
    ├──→ guideline_2.md (loaded into context)
    ├──→ guideline_3.md (loaded into context)
    └──→ ...
    │
    ↓
Agent produces output referencing guidelines
    │
    ↓
Output includes: "Following guidelines from [list]"
```

---

## 7. Dashboard Improvements

### 7.1 Current State

Static HTML dashboard. Not connected to real pipeline data. Shows hardcoded content.

### 7.2 Required Dashboard Tabs

#### Tab 1: Pipeline Workflow
- Text-based workflow diagram (stages, transitions, status)
- draw.io diagram generated from `pipeline.json`
- Color-coded: Green (complete), Yellow (in-progress), Red (failed), Gray (pending)

#### Tab 2: Agents
Each agent shown as a card:

```
┌─────────────────────────────────────┐
│ 🤖 Implement Agent (Phase 1)        │
│ Model: mimo-v2.5-free               │
│ Status: ✅ COMPLETED                │
│ Tokens: 45,230                      │
│ Time: 12 min                        │
│ Iterations: 3                       │
│ Skills Used: code-development       │
│ Context: 12,400 / 32,000 tokens    │
│                                     │
│ [View Details →]                    │
└─────────────────────────────────────┘
```

#### Tab 3: Agent Detail Page (click card)
- Agent name, role, model
- Prompt used (full text)
- Input files read (with paths)
- Output files created (with paths and sizes)
- Verification done (results)
- Tokens used (prompt + completion)
- Iterations taken
- Tools called (with counts)
- Time taken
- Skills used
- Context size/budget

#### Tab 4: Test Results
- Embedded link to test framework dashboard (`localhost:3011`)
- Summary of pass/fail rates
- Per-feature breakdown

#### Tab 5: Architecture
- Architecture diagram (draw.io generated)
- Tech stack summary
- NFR compliance status

#### Tab 6: Live Data
- Real-time updates from:
  - `pipeline.json` — Stage status
  - `agent-context.md` — Agent work details
  - `agent-audit.md` — Audit trail
  - `feature-status.md` — Feature completion

#### Tab 7: Final Summary
- Complete project summary (generated at end)
- All features, NFRs, test results, issues

### 7.3 Dashboard Data Flow

```
Pipeline runs
    │
    ├──→ Updates pipeline.json
    ├──→ Updates agent-context.md
    ├──→ Updates agent-audit.md
    ├──→ Updates feature-status.md
    │
    ↓
Dashboard reads files (live or on refresh)
    │
    ↓
Renders current state
```

---

## 8. Code Review Per Phase

### 8.1 Current State

One code review after ALL implementation. By then, issues are entrenched and expensive to fix.

### 8.2 Required Flow

```
Phase N Implementation
    │
    ↓
Code Review Agent (N independent reviews)
    │
    ├──→ Issues Found?
    │       │
    │    Yes ↓
    │    Fix Agent → Re-review → Still issues? → Loop
    │       │
    │    No ↓
    │    Human Approves
    │       │
    ↓       ↓
Phase N+1 Starts
```

### 8.3 Code Review Log Format

Every code review MUST log:

```markdown
## Code Review — Phase N — [Date]

### Review Summary
- Files reviewed: [count]
- Issues found: [count]
- Critical: [count]
- High: [count]
- Medium: [count]
- Low: [count]

### Issues

| # | File | Line | Severity | Guideline | Description | Status |
|---|------|------|----------|-----------|-------------|--------|
| 1 | src/auth.py | 45 | Critical | security/owasp | Password stored in plaintext | Open |
| 2 | src/api.py | 112 | High | api/rest | No rate limiting on login endpoint | Open |
| 3 | src/db.py | 78 | Medium | database/postgresql | Missing index on users.email | Open |
| 4 | src/utils.py | 23 | Low | code-style | Unused import | Open |

### Fixed Issues
| # | Fixed By | Re-reviewed | Result |
|---|----------|-------------|--------|
| 1 | Fix Agent | Review Agent | ✅ Pass |
```

### 8.4 Code Review Criteria

| Category | What's Checked |
|----------|---------------|
| Security | OWASP Top 10, secrets in code, auth bypass |
| Performance | N+1 queries, missing indexes, unbounded loops |
| Architecture | SOLID principles, separation of concerns |
| Testing | Test coverage, test quality, edge cases |
| Code Quality | Naming, complexity, duplication |
| Guidelines | Project-specific guidelines from knowledge base |

---

## 9. Security Comprehensive

### 9.1 Missing Security Stages

| Stage | What's Missing | When Required |
|-------|---------------|---------------|
| Threat Analysis | STRIDE threat model before architecture | After Design, Before Architecture |
| Vulnerability Scanning | 3rd party package CVE scan | After Implementation (each phase) |
| Man-in-the-Middle | Network interception testing | Before Packaging |
| DOS Testing | Denial of service resilience | Before Packaging |
| SQL Injection | Database query injection testing | After Implementation |
| URL Injection | URL manipulation testing | After Implementation |
| AppScan Equivalent | Automated security scanning | Before Packaging |
| Secrets Validation | No hardcoded secrets | After Implementation |
| Communication Security | TLS/SSL validation | Before Packaging |
| Certificate Validation | Cert pinning, chain validation | Before Packaging |

### 9.2 Required Security Stages

```
After Architecture:     Threat Analysis Report (STRIDE)
After Phase 1:          OWASP ZAP scan + Snyk audit
After Phase 2:          OWASP ZAP scan + Snyk audit
After Phase 3:          OWASP ZAP scan + Snyk audit
After Phase 4:          OWASP ZAP scan + Snyk audit
Before Packaging:       Nessus/Trivy full scan
Before Deploy:          Penetration test
After Deploy:           Smoke test + monitoring
```

### 9.3 Security Report Format

```markdown
## Security Report — [Phase/Stage]

### Threat Analysis (STRIDE)
| Threat | Component | Risk | Mitigation |
|--------|-----------|------|------------|
| Spoofing | Auth module | High | JWT + refresh tokens |
| Tampering | API endpoints | Medium | Input validation + CSRF |
| Repudiation | All endpoints | Medium | Audit logging |
| Info Disclosure | Database | High | Encryption at rest |
| DoS | API gateway | Medium | Rate limiting |
| Elevation | Auth module | High | Role-based access |

### Vulnerability Scan Results
- Packages scanned: [count]
- Vulnerabilities found: [count]
  - Critical: [count]
  - High: [count]
  - Medium: [count]
  - Low: [count]

### Penetration Test Results
- Tests performed: [count]
- Vulnerabilities found: [count]
- Remediation required: [list]
```

---

## 10. Packaging Comprehensive

### 10.1 Current State

Only Docker packaging. No installers, no versioning, no BOM.

### 10.2 Required Package Types

| Package | Format | Target | Required |
|---------|--------|--------|----------|
| Docker Image | `.tar.gz` | All platforms | ✅ |
| Windows Installer | `.msi` / `.exe` | Windows 10+ | ✅ |
| Debian Package | `.deb` | Ubuntu/Debian | ✅ |
| RPM Package | `.rpm` | RHEL/CentOS/Fedora | ✅ |
| macOS Package | `.dmg` | macOS 12+ | ✅ |
| iOS App | `.ipa` | iOS 15+ | ✅ |
| Android App | `.aab` / `.apk` | Android 10+ | ✅ |

### 10.3 Required Scripts

| Script | Purpose | When Run |
|--------|---------|----------|
| `install.sh` / `install.ps1` | Install all components | User runs on target machine |
| `uninstall.sh` / `uninstall.ps1` | Clean removal of all components | User runs to remove |
| `upgrade.sh` / `upgrade.ps1` | Upgrade with data migration | User runs to upgrade |
| `rollback.sh` / `rollback.ps1` | Revert to previous version | User runs if upgrade fails |
| `post-install-test.sh` | Verify installation works | Runs automatically after install |
| `post-uninstall-verify.sh` | Verify clean removal | Runs automatically after uninstall |

### 10.4 Package Contents

Every package MUST include:

```
package/
├── app/                    # Application files
├── config/                 # Configuration templates
├── docs/
│   ├── INSTALL.md          # Installation guide
│   ├── USER_GUIDE.md       # User guide
│   ├── UPGRADE.md          # Upgrade guide
│   └── UNINSTALL.md        # Uninstall guide
├── LICENSE                 # License file
├── BOM.md                  # Bill of Materials
├── checksums.sha256        # File checksums
└── VERSION                 # Version file
```

### 10.5 Version Management

```
SemVer: MAJOR.MINOR.PATCH

MAJOR — Breaking changes (data migration required)
MINOR — New features (backward compatible)
PATCH — Bug fixes (backward compatible)

Examples:
  1.0.0 → Initial release
  1.1.0 → Added new feature
  1.1.1 → Bug fix
  2.0.0 → Breaking change (new DB schema)
```

### 10.6 BOM (Bill of Materials)

```markdown
## Bill of Materials — MyWorld v1.0.0

### Application
| Component | Version | License | Size |
|-----------|---------|---------|------|
| MyWorld App | 1.0.0 | MIT | 15MB |

### Dependencies
| Component | Version | License | Size |
|-----------|---------|---------|------|
| Node.js | 20.x | MIT | 45MB |
| PostgreSQL | 15 | PostgreSQL | 80MB |
| Redis | 7.x | BSD | 10MB |
| React | 18.x | MIT | 2MB |
| FastAPI | 0.104 | MIT | 1MB |

### Total Package Size
- Docker: ~250MB
- Windows: ~180MB
- Linux: ~160MB
- macOS: ~170MB
```

---

## 11. Final Summary Report

Generated at the end of ALL stages. Stored at `products/<project>/docs/FINAL_SUMMARY.md`.

### 11.1 Required Sections

```markdown
# Final Summary Report — MyWorld v1.0.0

## Product Overview
- Name: MyWorld
- Version: 1.0.0
- Generated: 2026-09-01

## Features Implemented
| ID | Feature | Status | Phase |
|----|---------|--------|-------|
| F-001 | Landing Page | ✅ Complete | 1 |
| F-002 | Navigation | ✅ Complete | 1 |
| ... | ... | ... | ... |

## NFRs Implemented
| ID | NFR | Status | Verified |
|----|-----|--------|----------|
| NFR-001 | Page load < 3s | ✅ | Yes |
| NFR-002 | 99.9% uptime | ✅ | Yes |
| ... | ... | ... | ... |

## Tech Stack
| Layer | Technology | Version |
|-------|-----------|---------|
| Frontend | React | 18.x |
| Backend | FastAPI | 0.104 |
| Database | PostgreSQL | 15 |
| Cache | Redis | 7.x |
| Container | Docker | 24.x |

## Architecture
[Architecture diagram reference]
[Brief description]

## Agent Work Summary
| Agent | Model | Tokens | Time | Artifacts |
|-------|-------|--------|------|-----------|
| Ideation | mimo-v2.5-free | 12,000 | 3 min | 2 files |
| Design | mimo-v2.5-free | 18,000 | 5 min | 3 files |
| ... | ... | ... | ... | ... |

## Test Results
| Category | Total | Passed | Failed | Rate |
|----------|-------|--------|--------|------|
| Unit | 85 | 85 | 0 | 100% |
| API | 32 | 32 | 0 | 100% |
| Feature | 24 | 23 | 1 | 96% |
| UI | 18 | 17 | 1 | 94% |
| NFR | 15 | 14 | 1 | 93% |
| Security | 10 | 10 | 0 | 100% |

## Issues Found and Resolved
| # | Issue | Severity | Resolved |
|---|-------|----------|----------|
| 1 | Login rate limiting missing | High | ✅ |
| 2 | DB index on email missing | Medium | ✅ |

## Pipeline Phases Completed
- [x] Phase 1: Foundation + Core
- [x] Phase 2: Content Features
- [x] Phase 3: Specialized Features
- [x] Phase 4: Mobile
- [x] Code Review
- [x] Security Scan
- [x] Packaging
- [x] Deployment

## How to Install/Run
[Step-by-step instructions]

## Links
- Test Dashboard: http://localhost:3011
- User Guide: docs/USER_GUIDE.md
- Install Guide: docs/INSTALL.md

## Port Configuration
| Service | Port | Configurable |
|---------|------|-------------|
| Web | 3000 | ✅ |
| API | 8000 | ✅ |
| Database | 5432 | ✅ |
| Redis | 6379 | ✅ |
| Test Dashboard | 3011 | ✅ |

## Next Steps
1. Review the final summary
2. Test the application in browser
3. Deploy to staging
4. Schedule production deployment
```

---

## 12. Port Configuration

### 12.1 Current State

Hardcoded ports:
- Web: 3000
- API: 8000
- Database: 5432
- Redis: 6379

### 12.2 Required Change

**During Ideation/Design, ask:**

```
What ports do you want to use?

  Web frontend:     [3000]
  API backend:      [8000]
  PostgreSQL:       [5432]
  Redis:            [6379]
  Test dashboard:   [3011]

(Press Enter for defaults)
```

**Store in `project-config.json`:**

```json
{
  "project": "myworld",
  "ports": {
    "web": 3000,
    "api": 8000,
    "database": 5432,
    "redis": 6379,
    "test_dashboard": 3011
  }
}
```

**Docker compose uses these values:**

```yaml
services:
  web:
    ports:
      - "${WEB_PORT:-3000}:3000"
  api:
    ports:
      - "${API_PORT:-8000}:8000"
  db:
    ports:
      - "${DB_PORT:-5432}:5432"
  redis:
    ports:
      - "${REDIS_PORT:-6379}:6379"
```

---

## 13. Pipeline Exit Mechanism

### 13.1 After All Stages Complete

```
Pipeline completes all stages
    │
    ↓
Final Summary Report generated
    │
    ↓
Show final summary to human
    │
    ↓
Ask: "Pipeline complete. Do you want to exit?"
    │
    ├──→ Yes: Release lock, clean up temp files, exit
    │
    └──→ No: Show options:
              ├── "Review again" → Show summary again
              ├── "Make changes" → Enter修改 mode
              ├── "Redeploy" → Run deploy stage again
              └── "Export" → Generate exportable package
```

### 13.2 Exit Cleanup

When user chooses to exit:

1. Release project lock (`pipeline.lock`)
2. Archive pipeline state to `products/<project>/docs/archive/`
3. Clean up temporary files (`/tmp/pipeline-*`)
4. Save final audit log
5. Write exit timestamp to `pipeline.json`
6. Display: "Pipeline exited. Project saved at `products/<project>/`"

---

## 14. State File Ownership

### 14.1 File Ownership Matrix

| File | Owner | When Updated |
|------|-------|-------------|
| `pipeline.json` | Orchestrator | Every stage transition |
| `agent-context.md` | Each Agent | After completing work |
| `pipeline-state.md` | Each Agent | After completing work |
| `agent-audit.md` | Each Agent | After completing work |
| `feature-status.md` | Implement Agent | After each feature |
| `reports/*.md` | Validate/Review agents | After each validation |
| `tests/*` | Test Framework | After each test run |

### 14.2 Central Audit Log

All agents MUST write to `products/<project>/docs/agent-audit.md`:

```markdown
# Agent Audit Log — MyWorld

## 2026-09-01

| Time | Agent | Stage | Phase | Action | Status | Details |
|------|-------|-------|-------|--------|--------|---------|
| 10:00 | Orchestrator | 0 | — | Start pipeline | ✅ | — |
| 10:01 | Ideation Agent | 0 | — | Generate scope | ✅ | 13 features defined |
| 10:03 | Orchestrator | 0 | — | HIL Gate | ✅ | Human approved |
| 10:05 | Design Agent | 1 | — | Generate requirements | ✅ | FRs + NFRs defined |
| 10:10 | Orchestrator | 1 | — | HIL Gate | ✅ | Human approved |
| 10:12 | Architect Agent | 2 | — | Generate architecture | ✅ | Tech stack selected |
| 10:20 | Orchestrator | 2 | — | HIL Gate | ✅ | Human approved |
| 10:22 | Implement Agent | 4 | 1 | Build Auth | ✅ | 4 files created |
| 10:25 | Implement Agent | 4 | 1 | Build Dashboard | ✅ | 6 files created |
| ... | ... | ... | ... | ... | ... | ... |
```

### 14.3 Orchestrator Monitoring

The orchestrator monitors `agent-audit.md` to:
- Know which agents have completed
- Detect stalled agents (no update in X minutes)
- Track overall pipeline progress
- Trigger HIL gates at appropriate times
- Generate periodic status updates

---

## 15. Architecture Completeness Checklist

When the Architect agent completes, it MUST address ALL of the following:

### UI/UX
- [ ] UI/UX themes and design tokens defined
- [ ] Component library selected (e.g., Shadcn, MUI, Tailwind)
- [ ] Responsive design strategy
- [ ] Accessibility standards (WCAG 2.1 AA)

### Database
- [ ] Database schema designed
- [ ] Indexing strategy defined
- [ ] Sharding/partitioning plan (if needed)
- [ ] Migration strategy
- [ ] Backup/restore plan

### API
- [ ] API endpoints documented
- [ ] API versioning strategy
- [ ] Rate limiting plan
- [ ] Error handling standards
- [ ] Authentication/authorization flow

### Business Logic
- [ ] Business logic framework selected
- [ ] Service layer architecture
- [ ] Event-driven patterns (if applicable)
- [ ] CQRS/Event Sourcing (if applicable)

### Security
- [ ] Authentication mechanism (JWT, OAuth, etc.)
- [ ] Authorization model (RBAC, ABAC)
- [ ] Encryption at rest
- [ ] Encryption in transit
- [ ] OWASP compliance plan
- [ ] Secrets management

### Packaging
- [ ] Docker image design
- [ ] Installer packages (Windows, Linux, macOS)
- [ ] Mobile packages (iOS, Android)
- [ ] BOM (Bill of Materials)
- [ ] License compliance

### Install/Uninstall/Upgrade
- [ ] Install script design
- [ ] Uninstall script design
- [ ] Upgrade/migration script design
- [ ] Rollback strategy
- [ ] Patch management

### Deployment
- [ ] CI/CD pipeline design
- [ ] Blue-green deployment (if applicable)
- [ ] Canary deployment (if applicable)
- [ ] Staging environment
- [ ] Production environment

### NFRs
- [ ] Performance targets (response time, throughput)
- [ ] Scalability plan (horizontal/vertical)
- [ ] Availability targets (uptime SLA)
- [ ] Disaster recovery plan
- [ ] Monitoring and alerting

### Caching
- [ ] Multi-layer caching strategy
- [ ] Cache invalidation plan
- [ ] CDN strategy (if applicable)

### Rendering
- [ ] Rendering strategy (SSR/SSG/ISR/CSR)
- [ ] SEO requirements
- [ ] Performance implications

### Infrastructure
- [ ] Port configuration
- [ ] Environment variables
- [ ] Configuration management
- [ ] Logging strategy

### Documentation
- [ ] Architecture diagram (draw.io + PDF)
- [ ] UI/UX theme file for implementation
- [ ] Skills used for each section

### After Completion
- [ ] All features listed
- [ ] All FRs and NFRs listed
- [ ] Tech stack selected (with justification)
- [ ] Architecture diagram generated
- [ ] Packaging/install/deploy plan documented
- [ ] Human approves before proceeding

---

## Appendix A: Pipeline Stage Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    PRODUCT FORGE PIPELINE                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Stage 0: Ideation                                             │
│  ├── Agent: Ideation Agent                                     │
│  ├── Output: scope.md, features.md, priorities.md              │
│  ├── HIL: ✅ Review scope (2-3 min)                           │
│  └── Gate: Approve/Reject                                      │
│                                                                 │
│  Stage 1: Design                                               │
│  ├── Agent: Design Agent                                       │
│  ├── Output: requirements.md, ux-design.md                     │
│  ├── HIL: ✅ Review design (5-10 min)                         │
│  └── Gate: Approve/Reject                                      │
│                                                                 │
│  Stage 2: Architecture                                         │
│  ├── Agent: Architect Agent (multi-model review)               │
│  ├── Output: architecture.md, tech-stack.md, diagrams/         │
│  ├── HIL: ✅ Review architecture (5-10 min)                   │
│  └── Gate: Approve/Reject                                      │
│                                                                 │
│  Stage 3: Threat Analysis                                      │
│  ├── Agent: Security Agent                                     │
│  ├── Output: threat-model.md                                   │
│  └── Gate: Auto-continue                                       │
│                                                                 │
│  Stage 4: Implementation (Phased)                              │
│  ├── Phase 1: Auth, Dashboard, Search, ToDo                    │
│  │   ├── Agent: Implement Agent                                │
│  │   ├── Test: Unit, API, Feature, UI                          │
│  │   ├── Review: Code Review Agent                             │
│  │   └── HIL: ✅ Review (10-15 min)                          │
│  ├── Phase 2: Calendar, Goals, News, Health                    │
│  │   ├── Agent: Implement Agent                                │
│  │   ├── Test: Unit, API, Feature, UI                          │
│  │   ├── Review: Code Review Agent                             │
│  │   └── HIL: ✅ Review (10-15 min)                          │
│  ├── Phase 3: Exploratory, Spiritual, Documents, Financial     │
│  │   ├── Agent: Implement Agent                                │
│  │   ├── Test: Unit, API, Feature, UI                          │
│  │   ├── Review: Code Review Agent                             │
│  │   └── HIL: ✅ Review (10-15 min)                          │
│  └── Phase 4: Mobile App                                       │
│      ├── Agent: Implement Agent                                │
│      ├── Test: Unit, UI, E2E                                   │
│      ├── Review: Code Review Agent                             │
│      └── HIL: ✅ Review (5-10 min)                           │
│                                                                 │
│  Stage 5: Security Scan                                        │
│  ├── Agent: Security Agent                                     │
│  ├── Output: security-report.md                                │
│  └── Gate: Auto-continue                                       │
│                                                                 │
│  Stage 6: NFR Testing                                          │
│  ├── Agent: Test Agent                                         │
│  ├── Output: nfr-report.md                                     │
│  └── Gate: Auto-continue                                       │
│                                                                 │
│  Stage 7: Full Test Suite                                      │
│  ├── Agent: Test Agent                                         │
│  ├── Output: test-report.md                                    │
│  └── Gate: Auto-continue                                       │
│                                                                 │
│  Stage 8: Documentation                                        │
│  ├── Agent: Documentation Agent                                │
│  ├── Output: USER_GUIDE.md, INSTALL.md                         │
│  ├── HIL: ✅ Review docs (5 min)                             │
│  └── Gate: Approve                                             │
│                                                                 │
│  Stage 9: Packaging                                            │
│  ├── Agent: Package Agent                                      │
│  ├── Output: Docker image, installers, packages                │
│  ├── HIL: ✅ Review package (5 min)                          │
│  └── Gate: Approve                                             │
│                                                                 │
│  Stage 10: Pre-Production                                      │
│  ├── Agent: Orchestrator                                       │
│  ├── Output: FINAL_SUMMARY.md                                  │
│  ├── HIL: ✅ Final walkthrough (10 min)                      │
│  └── Gate: Final approval                                      │
│                                                                 │
│  Stage 11: Deploy                                              │
│  ├── Agent: Deploy Agent                                       │
│  ├── Output: Running application                               │
│  ├── HIL: ✅ Staging verification (5 min)                    │
│  └── Gate: Deploy go/no-go                                     │
│                                                                 │
│  Stage 12: Exit                                                │
│  ├── Show final summary                                        │
│  ├── Ask: "Exit pipeline?"                                     │
│  ├── Yes: Release lock, cleanup, exit                          │
│  └── No: Allow continued work                                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Appendix B: File Structure After Implementation

```
products/myworld/
├── docs/
│   ├── PIPELINE_IMPROVEMENT_PLAN.md    # This document
│   ├── pipeline.json                   # Pipeline state
│   ├── agent-context.md                # Agent work context
│   ├── agent-audit.md                  # Audit trail
│   ├── feature-status.md               # Feature completion
│   ├── FINAL_SUMMARY.md                # Final report
│   ├── scope.md                        # Scope document
│   ├── features.md                     # Feature list
│   ├── requirements.md                 # FRs + NFRs
│   ├── ux-design.md                    # UX design
│   ├── architecture.md                 # Architecture
│   ├── tech-stack.md                   # Tech decisions
│   ├── threat-model.md                 # Security threats
│   ├── security-report.md              # Security scan
│   ├── nfr-report.md                   # NFR test results
│   ├── test-report.md                  # Full test results
│   ├── USER_GUIDE.md                   # User documentation
│   ├── INSTALL.md                      # Installation guide
│   └── reports/
│       ├── code-review-phase1.md
│       ├── code-review-phase2.md
│       ├── code-review-phase3.md
│       └── code-review-phase4.md
├── src/
│   ├── frontend/                       # React app
│   ├── backend/                        # FastAPI app
│   └── mobile/                         # React Native app
├── tests/
│   ├── unit/
│   ├── api/
│   ├── feature/
│   ├── ui/
│   ├── nfr/
│   └── security/
├── packages/
│   ├── docker/
│   ├── windows/
│   ├── linux-deb/
│   ├── linux-rpm/
│   ├── macos/
│   ├── ios/
│   └── android/
├── docker-compose.yml
├── project-config.json
└── pipeline.lock
```

---

## 16. Agent-to-Agent Delegation (Opt-In)

> **Status:** Implemented (opt-in, off by default)
> **Module:** `core/delegation.py` · **Wiring:** `core/pipeline_executor.py`
> **Config source:** `pipeline-definition.json` → `stages.<id>.sub_agents`, `agent_capabilities`

### 16.1 What it is

Agent-to-agent delegation lets one agent ask another specialized agent to do
something, using the graph already declared in `pipeline-definition.json`
(`sub_agents`, `can_invoke`, `decision_logic`). Examples:

- `code-review` finds a code issue → invoke `fix`
- `implement` hits an architecture problem → invoke `architect`
- `security` finds issues → invoke `fix`

Previously these relationships were declared in config but **never executed** —
the executor only ran each stage's `ideal_flow` in order. Delegation is now
**orchestrator-routed**, not free-form peer chat.

### 16.2 Why it is needed

Some problems cannot be solved by the fixed linear stage flow — they require a
dynamic follow-up by another role. Delegation lets the orchestrator react to an
agent's outcome (a failed review, a detected issue) and invoke the correct
specialist instead of blindly advancing to the next stage. This replaces
hardcoded branches with a declarative `decision_logic` map.

### 16.3 Why it is opt-in (off by default)

1. **It changes behaviour** — enabling it can add extra agent calls and loops.
2. **Cost multiplication** — multi-agent/peer patterns are the classic token
   blow-up (agents ≈ 4× chat; multi-agent ≈ 15×). Spend should be deliberate.
3. **Signals must be trusted** — while `compliance` still fails broadly, a
   default-on delegation would fire redundantly. Opt-in lets us enable it once
   quality signals are meaningful, or only for specific stages.

Enable per project via `products/<project>/project.json`:

```json
{ "enable_delegation": true }
```

Optional env overrides: `DELEGATION_MAX_PER_STAGE`, `DELEGATION_MAX_TOTAL`,
`DELEGATION_MAX_PAYLOAD_CHARS`.

### 16.4 How it is handled (mechanics)

Per agent completion, inside `_execute_stage_sequential`:

1. **Trigger** — `_delegation_signals(execution)` returns candidate signals only
   when the agent did **not** finish cleanly (e.g. `failed` / `needs_retry` /
   `escalated`): `["fix","code_issue","logic_issue","api_issue","db_issue",
   "ui_issue","issues_found","major_change_needed","build_needed"]`.
   Completed agents produce none, so no delegation.
2. **Resolve** — `DelegationRouter.resolve(stage, from_agent, signals)` picks a
   target via `decision_logic` first, then `can_invoke`, then global
   `agent_capabilities`.
3. **Guardrails**
   - `enable_delegation` must be true.
   - **Message budget:** max **2 per stage**, **8 per run**
     (`DelegationBudget`).
   - **Context firewall:** the delegated agent receives a **capped payload**
     (head+tail, default **4,000 chars**) — never the full transcript.
4. **Dispatch** — an optional `AgentMessenger` HANDOFF message is recorded; a
   `DelegationRecord` is persisted to `products/<project>/delegations.json`.
5. **Execute** — the orchestrator runs the target agent **in the same stage**
   through the normal `execute_agent` path (same contracts, model routing,
   telemetry, run breaker).
6. **Observe** — recorded in the run report and exposed via API (see 16.6).

### 16.5 Verified routing (from `pipeline-definition.json`)

| Stage | From agent | Signal | Target |
|-------|-----------|--------|--------|
| 4a | code-review | `code_issue` | `fix` |
| 4a | implement | `architecture_issue` | `architect` |
| 5 | security | `issues_found` | `fix` |
| — | package@9 | `fix` | *(none — no mapping)* |

Payload cap verified: 10,000 chars → 4,060 chars (head + marker + tail).
Budget verified: after 1 invocation in a stage (max=1), `can_invoke` = false.

### 16.6 API surface

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/delegations?project=` | GET | Delegation records for a project |
| `/api/v1/messages?project=` | GET | Inter-agent HANDOFF messages |

### 16.7 Why orchestrator-routed (not peer chat)

Hub-and-spoke keeps cost and traceability under control: artifacts are the
handoff medium, the orchestrator decides and meters every invocation, and the
delegated agent only ever sees a bounded summary. Free-form peer chat
(shared transcripts) is intentionally avoided because each participant would
re-read the growing conversation plus its own preamble on every turn.

---

## 17. Token/Cost Governance (Telemetry, Budgets, Breakers)

> **Status:** Implemented. Complements this plan's model/context strategy.

### 17.1 Telemetry & reporting

- `core/pipeline_telemetry.py` aggregates per call → agent → stage → phase →
  pipeline: input (cached/uncached), output, cost, time, truncation,
  compaction savings, contract token budget state, and alerts.
- Per-call fields captured from the provider: `finish_reason`, `truncated`,
  `retries`, `continuations`.
- Cross-project history via `pipeline_cost_history.json`.
- API: `GET /api/v1/telemetry?project=`, `GET /api/v1/cost-history`,
  `POST /api/v1/cost-history/append`.

### 17.2 Output caps & truncation

- API `max_tokens` is driven by the **agent contract**
  (`context_manager.AGENT_CONTRACTS`), not a global constant.
- On `finish_reason=length`, the executor **auto-continues** the output (up to 3
  times) and merges the pieces, guarded to only continue when there is usable
  content — so artifacts are not silently truncated.
- Contracts recalibrated: design/implement 16K, validate 12K, code-review/security
  8K, architect 10K, default 6K.

### 17.3 Budget spec & tier proposal

- Project budget lives in `project.json`:
  `{ currency, soft_cost, hard_cost, soft_tokens, hard_tokens, variance_percent }`
  (`variance_percent` defaults to **10**; also accepts `tolerance_percent` or a
  top-level `budget_variance_percent`).
- `core/budget_planner.py` proposes a per-agent tier that fits the budget
  **without dropping any agent below its capability floor**, with a rationale
  per agent and an explicit `feasible` / `exceeds_hard` verdict.
- Applying a proposal requires explicit approval and writes a runtime
  `products/<project>/model-tier.json` that the executor consumes.
- API: `GET /api/v1/budget`, `GET /api/v1/tier/proposal`,
  `POST /api/v1/tier/apply` (`approve=true` required).

### 17.4 Run breaker & alerts

- `core/run_breaker.py`: hard cost/token ceiling → **STOP**; soft budget beyond
  the variance band → **THROTTLE** (force cheapest capable model); token-rate
  spike (runaway loop) → **STOP**; 70/90/100% warnings; alerts de-duplicated to
  `products/<project>/alerts.json`.
- API: `GET /api/v1/alerts?project=`.

### 17.5 Live journal / project state

- `core/project_journal.py` (wires `StateMachine` + `AgentLedger`) emits
  `PROJECT-STATUS.md` and `project-status.json` — done / pending / current stage,
  per-stage tokens/cost/time, budget, alerts.
- API: `GET /api/v1/project-status?project=`.

### 17.6 Compaction net-cost tracking

- Deterministic artifact summarization savings are measured
  (`compaction_saved_chars`) and reported alongside `continuations`, so the
  net effect (saved context vs extra continuation calls) is visible.

---

*Document generated by Pipeline Improvement Plan — 2026-09-01*
*Review required before implementation begins.*
