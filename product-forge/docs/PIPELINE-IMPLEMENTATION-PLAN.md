# Pipeline Implementation Plan — All Gaps

**Version:** 1.0
**Date:** 2026-09-01
**Purpose:** Fix all 77 identified gaps to make pipeline produce working, verified, tested software

---

## Gap Filtering: What's Needed vs Not Needed

### GAPS REMOVED (Not Needed for This Pipeline)

| # | Gap | Reason Removed |
|---|-----|---------------|
| 11 | Idea Assessment Before Coding | Our pipeline already has Ideation stage with scope assessment. Adding separate assessment stage adds ceremony without value for software dev. |
| 12 | Extensible Workflows / Domain Presets | Nice-to-have. We're building a software development pipeline. Other domains (research, data analysis) are out of scope. |
| 16 | Shared Workspace / Data Plane | Already have `products/<project>/` structure. Creating virtual workspace adds complexity without benefit. |
| 19 | Tools as Agent Interfaces (ACI) | Pipeline.py already exists as CLI. Agents use bash. Redesigning as ACI is over-engineering. |
| 21 | Least Privilege per Agent | Important for production but adds complexity now. All agents need similar access during development. Defer to production. |
| 42 | Distributed Systems Foundation | Paradigm shift. Agents are not microservices. Adding message queues, actor model is over-architecture. |
| 45 | Topology Selection (sequential/parallel/etc.) | We only need sequential + parallel for implementation phases. Full topology selection is over-engineering. |
| 46 | Actor Model for Agents | Too big a paradigm shift. Keep current agent model. |
| 49 | Workflow Automation (n8n/Trigger.dev) | External tools not needed. Pipeline.py handles orchestration. |
| 50 | AI Observability (full) | Basic logging is enough. Full observability (Grafana, Prometheus) is overkill for this stage. |
| 30 | Context Optimizer / Context Compiler | Nice-to-have. Current context loading (read files) works. Optimization is a performance concern, not a correctness concern. |
| 29 | Memory Categories (short-term, episodic, semantic, procedural) | Over-engineering. Agent state is tracked in pipeline.json and agent-context.md. |
| 43 | Agent State/Memory/Consistency (full) | Partially needed but full implementation is overkill. pipeline.json + agent-context.md is sufficient. |

**Total Removed: 13**

### GAPS KEPT: 64

---

## Implementation Phases

### PHASE 0: Foundation (Must Complete First)

**Goal:** Fix the root causes that make everything else fail.

| # | Gap | What to Build | Files Affected | Agent Affected |
|---|-----|---------------|----------------|----------------|
| 0.1 | #1 - Constitution Layer | Create `docs/CONSTITUTION.md` with project principles: architecture rules, coding standards, security rules, quality thresholds, testing requirements, definition of done | NEW: `docs/CONSTITUTION.md` | ALL agents reference it |
| 0.2 | #4 - Coding Guidelines Referenced | Wire `docs/guidelines/` to every agent contract. Each agent loads relevant guidelines before work. | MODIFY: all 26 `.opencode/agent/*.md` files | implement, code-review, architect, design, security |
| 0.3 | #11 - Knowledge Router Wired | Confirm `core/knowledge_router.py` works. Add knowledge_router call to every agent contract. | MODIFY: all agent contracts | ALL agents |
| 0.4 | #23 - Implementation Root Cause | Analyze WHY implement agent produces half-baked code. Fix: (a) chunk architecture into smaller pieces, (b) give explicit file list per feature, (c) enforce E2E integration in prompt, (d) consider stronger model | MODIFY: `implement` agent contract | implement |
| 0.5 | #6 - AGENTS.md Project Contract | Create `products/<project>/AGENTS.md` with project-wide rules: purpose, architecture, conventions, constraints, verification requirements | NEW: `products/<project>/AGENTS.md` | ALL agents reference it |

**Verification:** After Phase 0, every agent contract references constitution, guidelines, and knowledge router.

---

### PHASE 1: Pipeline Stage Ordering & HIL

**Goal:** Fix the pipeline sequence so code review happens at the right time and human reviews happen at the right gates.

| # | Gap | What to Build | Files Affected |
|---|-----|---------------|----------------|
| 1.1 | #7, #23 - Code Review Timing | Move code review to AFTER each implementation phase, BEFORE testing. New order per phase: Implement → Code Review → Fix → Validate → Human Approve → Next Phase | MODIFY: `scripts/pipeline.py` stage ordering |
| 1.2 | #15 - HIL After Wireframes | Add explicit HIL gate after Stage 1 (Design) where human reviews wireframes before architecture | MODIFY: `scripts/pipeline.py`, agent contracts |
| 1.3 | #16 - Pause After Each Agent | After EVERY agent run, pause and show summary table. Ask "Review or continue?" | MODIFY: `scripts/pipeline.py`, orchestrator contract |
| 1.4 | #13 - Periodic Agent Status Update | Generate exact table format after every agent run (see format below) | NEW: `scripts/pipeline_helpers.py` function |
| 1.5 | #29 - Central Audit Log | Every agent logs to `agent-audit.md` with timestamp, agent name, stage, phase, action | MODIFY: all agent contracts |
| 1.6 | #30 - Orchestrator State Management | Orchestrator monitors pipeline.json, pipeline-state.md, agent-audit.md. Knows current stage, active agent, expected artifacts | MODIFY: orchestrator agent contract |
| 1.7 | #21 - Pipeline Exit Mechanism | After final summary, ask "Exit pipeline?" Release lock, cleanup, exit | MODIFY: `scripts/pipeline.py` |

**Agent Status Update Format:**
```
Summary of Agents work done - Status: [COMPLETED/IN_PROGRESS/FAILED]

| Field | Value |
|-------|-------|
| Previous Agent | [name] |
| Current Agent Name | [name] |
| Model Name | [model] |
| Scope | [what was done] |
| Start Time | [timestamp] |
| End Time | [timestamp] |
| Time Taken | [duration] |
| Implemented | [list of things implemented] |
| Artifacts | [list of files created with links] |
| Tokens Used | [count] |
| Stage | [stage number] |
| Phase | [phase number if applicable] |
| Issues Found | [count + list] |
| Next Agent | [name] |
| Action/Reviews Needed | [yes/no + details] |
| State Files Updated | [context] [pipeline] [memory] [state] |
```

**Verification:** After Phase 1, pipeline runs in correct order with human gates and status updates.

---

### PHASE 2: Multi-Layer Implementation Agents

**Goal:** Split implement agent into sub-agents that work layer by layer, skeleton first then enable features.

| # | Gap | What to Build | Files Affected |
|---|-----|---------------|----------------|
| 2.1 | #4, #33 - Multi-Layer Implementation | Create sub-agents: `implement-ui`, `implement-api`, `implement-db`, `implement-logic`. Each focuses on one layer. | NEW: `.opencode/agent/implement-ui.md`, `implement-api.md`, `implement-db.md`, `implement-logic.md` |
| 2.2 | #5 - Skeleton-First Approach | Phase 0 = skeleton (empty UI with routing, DB schema, API endpoints with stubs, basic business logic). Phase 1+ = enable features one by one | MODIFY: pipeline stage definitions, implement agent prompts |
| 2.3 | #4 - Implementation Layer Order | Order: DB Layer → API Layer → Business Logic → UI Layer → Integration. Each layer builds on previous. | MODIFY: pipeline stages |
| 2.4 | #2 - Implement Agent Quality | Fix prompt to: (a) read architecture in chunks, (b) follow coding guidelines, (c) write E2E integrated code, (d) verify own output before declaring done | MODIFY: implement agent contract |
| 2.5 | #23 - E2E Integration Enforcement | After each phase, verify ALL layers work together: UI calls API, API calls logic, logic calls DB. Not just individual files. | MODIFY: validation agent, pipeline verification |

**Implementation Phase Structure (Revised):**
```
Stage 4-0: Skeleton
  ├── implement-db: Create DB schema, migrations
  ├── implement-api: Create API endpoints (return mock for now)
  ├── implement-logic: Create business logic framework
  ├── implement-ui: Create UI shell with routing, empty pages
  └── HIL: Human reviews skeleton in browser

Stage 4a: Enable Phase 1 Features (Auth, Dashboard, Search, ToDo)
  ├── implement-db: Add feature-specific DB tables/queries
  ├── implement-api: Add feature-specific API endpoints (real logic)
  ├── implement-logic: Implement feature business logic
  ├── implement-ui: Build feature UI components
  ├── code-review: Review all Phase 1 code
  ├── fix: Fix any issues
  ├── validate: Run Phase 1 tests
  └── HIL: Human tests features in browser

Stage 4b: Enable Phase 2 Features (Calendar, Goals, News, Health)
  ├── [same pattern as 4a]
  └── HIL: Human tests + verifies Phase 1 still works

Stage 4c: Enable Phase 3 Features (Exploratory, Spiritual, Documents, Financial)
  ├── [same pattern as 4a]
  └── HIL: Human tests + verifies Phase 1+2 still work

Stage 4d: Enable Phase 4 (Mobile)
  ├── implement-mobile: React Native app
  ├── code-review: Review mobile code
  ├── validate: Run mobile tests
  └── HIL: Human tests on device
```

**Verification:** After Phase 2, implementation produces layered, integrated code with skeleton-first approach.

---

### PHASE 3: Test Framework Integration

**Goal:** ALL tests created within test framework, run from there, results logged there.

| # | Gap | What to Build | Files Affected |
|---|-----|---------------|----------------|
| 3.1 | #9, #27 - Test Framework as Central Hub | All agents create tests WITHIN `test-framework/tests/<project>/`. Tests are run FROM test framework. Results logged TO test framework. | MODIFY: implement agent, validate agent, all agent contracts |
| 3.2 | #27 - Test Types in Framework | Ensure test framework supports ALL types: unit, api, db, visual, e2e, stress, performance, load, security, packaging, install/uninstall/upgrade/patch | MODIFY: `test-framework/config/test-suites.yaml`, templates |
| 3.3 | #27 - Test Modes | Test modes: Sanity, Feature, NFR, Packaging/Install, Full Suite. Each mode runs specific categories. | MODIFY: `test-framework/config/test-suites.yaml` |
| 3.4 | #27 - Test Comments | Each test run has comments section explaining WHY test was run (which phase, which feature, which fix) | MODIFY: test framework runner, reporter |
| 3.5 | #27 - Test Traceability Matrix | Map: Requirement → Feature → Tests → Results. Each test traces back to FR/NFR. | MODIFY: test framework reporter |
| 3.6 | #27 - Test Dashboard Link | Validate agent provides test dashboard link per project: `http://localhost:3011?project=<name>` | MODIFY: validate agent contract |
| 3.7 | #27 - Tests Per Phase | After each implementation phase: generate phase-specific tests, run them, log results. After fixes: run specific tests for fixed files. | MODIFY: pipeline stages, implement agent |
| 3.8 | #27 - Test Results in Pipeline | Test results feed into pipeline.json and agent-audit.md. Dashboard shows test results per phase. | MODIFY: pipeline.py, dashboard |

**Test Framework Project Structure:**
```
test-framework/tests/<project>/
├── unit/
│   ├── test_auth.py
│   ├── test_todo.py
│   └── ...
├── api/
│   ├── test_auth_api.py
│   ├── test_todo_api.py
│   └── ...
├── db/
│   ├── test_user_db.py
│   ├── test_todo_db.py
│   └── ...
├── e2e/
│   ├── test_login_flow.py
│   ├── test_todo_flow.py
│   └── ...
├── visual/
│   ├── test_dashboard_visual.py
│   └── ...
├── security/
│   ├── test_auth_security.py
│   ├── test_sql_injection.py
│   └── ...
├── performance/
│   ├── test_api_load.py
│   └── ...
├── stress/
│   └── ...
├── install/
│   ├── test_install.py
│   ├── test_uninstall.py
│   └── ...
├── packaging/
│   └── ...
└── results/
    ├── run-20260901-001.json
    └── ...
```

**Verification:** After Phase 3, all tests live in test framework, are run from there, results are logged there.

---

### PHASE 4: Dashboard Live Data

**Goal:** Dashboard shows live pipeline data, agent details, test results.

| # | Gap | What to Build | Files Affected |
|---|-----|---------------|----------------|
| 4.1 | #1 - Dashboard Live Data | Rebuild dashboard to read from: pipeline.json, agent-context.md, agent-audit.md, feature-status.md, test results | MODIFY: `pipeline_dashboard/serve.py`, dashboard HTML |
| 4.2 | #17 - Pipeline Workflow Tab | Tab 1: Text-based workflow diagram + generated draw.io diagram. Color-coded by status. General (not product-specific). | NEW: dashboard tab |
| 4.3 | #18 - Agents Tab | Tab 2: Each agent as card showing: name, model, status, tokens, time, iterations, skills used. Click → detail page. | NEW: dashboard tab |
| 4.4 | #19, #31 - Agent Detail Pages | Click agent card → shows: full prompt, role, inputs, artifacts, verification, tokens, iterations, tools, context details, model, errors, skills | NEW: dashboard page |
| 4.5 | #20 - Final Summary Tab | Tab: Complete project summary with all features, agents, tokens, FR/NFR status, issues, tech stack, links | NEW: dashboard tab |
| 4.6 | #20 - Final Summary Report | Generate `products/<project>/docs/FINAL_SUMMARY.md` at pipeline completion | MODIFY: pipeline.py |
| 4.7 | #29 - Audit Trail View | Dashboard reads agent-audit.md and shows timeline of all agent actions | NEW: dashboard section |
| 4.8 | #14 - Test Results Tab | Dashboard shows test results per phase: pass/fail rates, per-feature breakdown, traceability | NEW: dashboard tab (or embed test framework dashboard) |

**Dashboard Tabs:**
```
Tab 1: Pipeline Workflow (text + draw.io diagram)
Tab 2: Agents (cards with status)
Tab 3: Agent Detail (click card → full info)
Tab 4: Test Results (embed test framework dashboard or summary)
Tab 5: Architecture (diagram + tech stack + NFR status)
Tab 6: Live Data (real-time from pipeline.json, agent-audit.md)
Tab 7: Final Summary (complete project report)
```

**Verification:** After Phase 4, dashboard shows live data from all pipeline sources.

---

### PHASE 5: Multi-Model Architecture Review

**Goal:** Architecture reviewed by 2-3 agents with different models for 360-degree review.

| # | Gap | What to Build | Files Affected |
|---|-----|---------------|----------------|
| 5.1 | #10 - Multi-Model Review | Create review agents with different model focuses: general, security, performance | NEW: `.opencode/agent/review-general.md`, `review-security.md`, `review-performance.md` |
| 5.2 | #10 - Review Merge Process | All 3 review agents run in parallel. Findings merged and deduplicated. Human reviews merged report. | MODIFY: pipeline stages |
| 5.3 | #36 - NFR Agent System Prompts | Add complete system prompts for: performance agent, security agent, accessibility agent | MODIFY: agent contracts |
| 5.4 | #12 - Architect Completeness | Architect agent must produce: features, FR/NFR, techstack, packaging, deployment, install/upgrade, architecture diagram, UI/UX theme, skills used | MODIFY: architect agent contract |
| 5.5 | #32 - Architecture Diagram | Generate draw.io diagram + PDF from architecture.md | MODIFY: architect agent |
| 5.6 | #32 - UI/UX Theme .md | Architect produces `docs/uiux-theme.md` with colors, typography, components, responsive breakpoints | MODIFY: architect agent |

**Review Process:**
```
Architecture Complete
    │
    ├──→ review-general agent (different model)
    │      Output: general-review.md
    │
    ├──→ review-security agent (different model)
    │      Output: security-review.md
    │
    └──→ review-performance agent (different model)
           Output: performance-review.md
    │
    ↓
Orchestrator merges findings (dedup + prioritize)
    │
    ↓
Unified Review Report → Human approves/rejects
```

**Verification:** After Phase 5, architecture is reviewed by 3 independent agents.

---

### PHASE 6: Comprehensive Security

**Goal:** Full security coverage: threat analysis, vulnerability scanning, penetration testing.

| # | Gap | What to Build | Files Affected |
|---|-----|---------------|----------------|
| 6.1 | #35 - Threat Analysis | After architecture: generate STRIDE threat model. Identify threats per component. | MODIFY: security agent |
| 6.2 | #35 - Package CVE Scan | After each phase: run Snyk/Trivy scan on 3rd party packages. Report findings. | MODIFY: security agent, pipeline stages |
| 6.3 | #35 - OWASP ZAP Scan | Before packaging: run OWASP ZAP against running app. Report High/Medium/Low findings. | MODIFY: security agent |
| 6.4 | #35 - SQL Injection Testing | Test all API endpoints for SQL injection. | MODIFY: security agent, test framework |
| 6.5 | #35 - URL Injection Testing | Test all URL parameters for injection. | MODIFY: security agent |
| 6.6 | #35 - Login/Password/Secrets Validation | Verify: no hardcoded secrets, passwords hashed, secrets in env vars, tokens expire. | MODIFY: security agent |
| 6.7 | #35 - Communication Security | Verify: TLS enabled, certificates valid, no plain HTTP. | MODIFY: security agent |
| 6.8 | #35 - DOS Resilience | Basic rate limiting test, timeout test. | MODIFY: security agent, test framework |

**Security Stages:**
```
After Architecture:    Threat Analysis Report (STRIDE)
After Phase 1:         Package CVE scan (Snyk/Trivy)
After Phase 2:         Package CVE scan
After Phase 3:         Package CVE scan
After Phase 4:         Package CVE scan
Before Packaging:      OWASP ZAP scan + SQL injection + URL injection
Before Deploy:         Penetration test (basic)
After Deploy:          Smoke test + monitoring check
```

**Verification:** After Phase 6, security is validated at multiple points.

---

### PHASE 7: Comprehensive Packaging

**Goal:** Multi-platform packages with help files, BOM, install/uninstall verification.

| # | Gap | What to Build | Files Affected |
|---|-----|---------------|----------------|
| 7.1 | #25 - Package Formats | Generate: Docker image, Windows (.msi), Linux Debian (.deb), Linux RPM (.rpm), macOS (.dmg) | MODIFY: package agent |
| 7.2 | #24, #25 - Package Contents | Every package includes: app, config, INSTALL.md, USER_GUIDE.md, API guide, LICENSE, BOM.md, checksums, VERSION | MODIFY: package agent |
| 7.3 | #25 - BOM (Bill of Materials) | Generate BOM: all components, versions, licenses, sizes | MODIFY: package agent |
| 7.4 | #22 - Package Footprint | Document: disk space, RAM, OS requirements, dependencies | MODIFY: package agent |
| 7.5 | #22 - Install + Verify | Package includes install script. After install: verify services up, UI accessible, run sanity test | MODIFY: package agent |
| 7.6 | #22 - Uninstall + Verify | Package includes uninstall script. After uninstall: verify clean removal | MODIFY: package agent |
| 7.7 | #22 - Upgrade + Rollback | Package supports upgrade with data migration. Rollback if upgrade fails. | MODIFY: package agent |
| 7.8 | #26 - Port Configuration | During ideation: ask user for ports. Store in project-config.json. Docker compose uses these. | MODIFY: pipeline.py, ideation stage |

**Package Structure:**
```
packages/<project>/
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── <project>.tar.gz
├── windows/
│   ├── <project>-setup.msi
│   └── <project>-setup.exe
├── linux-deb/
│   └── <project>_1.0.0_amd64.deb
├── linux-rpm/
│   └── <project>-1.0.0-1.x86_64.rpm
├── macos/
│   └── <project>-1.0.0.dmg
├── docs/
│   ├── INSTALL.md
│   ├── USER_GUIDE.md
│   ├── API_GUIDE.md
│   ├── UPGRADE.md
│   └── UNINSTALL.md
├── BOM.md
├── checksums.sha256
└── VERSION
```

**Verification:** After Phase 7, packages exist for all platforms with help files and BOM.

---

### PHASE 8: Deployment

**Goal:** Deploy agent handles multiple environments with E2E validation.

| # | Gap | What to Build | Files Affected |
|---|-----|---------------|----------------|
| 8.1 | #28 - Deploy Environment | Ask user: deploy to (local folder, Docker, cloud, Vercel, etc.) | MODIFY: deploy agent, pipeline.py |
| 8.2 | #28 - Deploy Scripting | Deploy agent creates deployment scripts for target environment | MODIFY: deploy agent |
| 8.3 | #28 - E2E Validation | After deploy: verify app accessible, run sanity test, check all features | MODIFY: deploy agent |
| 8.4 | #28 - Post-Deploy Smoke Test | After deploy: run smoke test suite from test framework | MODIFY: deploy agent |

**Verification:** After Phase 8, app is deployed and verified working.

---

### PHASE 9: Documentation

**Goal:** Complete documentation including install guide, API guide, help per page.

| # | Gap | What to Build | Files Affected |
|---|-----|---------------|----------------|
| 9.1 | #24 - Install Guide | Document agent produces INSTALL.md with step-by-step instructions | MODIFY: document agent |
| 9.2 | #24 - User Guide | Document agent produces USER_GUIDE.md with page-by-page help | MODIFY: document agent |
| 9.3 | #24 - API Guide | Document agent produces API_GUIDE.md with endpoint docs | MODIFY: document agent |
| 9.4 | #24 - Help Per Page | Each UI page has help section (can be tooltip or help page) | MODIFY: implement-ui agent |

**Verification:** After Phase 9, documentation is complete and accurate.

---

## Summary: All 64 Gaps Mapped to Phases

| Phase | Gaps Covered | Count |
|-------|-------------|-------|
| Phase 0: Foundation | #1, #4, #11, #23, #24 | 5 |
| Phase 1: Pipeline Ordering & HIL | #7, #13, #15, #16, #21, #29, #30 | 7 |
| Phase 2: Multi-Layer Implementation | #2, #4, #5, #33 | 4 |
| Phase 3: Test Framework Integration | #9, #14, #27 | 8 |
| Phase 4: Dashboard Live Data | #1, #17, #18, #19, #20, #31 | 8 |
| Phase 5: Multi-Model Review | #10, #12, #32, #36 | 6 |
| Phase 6: Comprehensive Security | #35 | 8 |
| Phase 7: Comprehensive Packaging | #22, #24, #25, #26 | 8 |
| Phase 8: Deployment | #28 | 4 |
| Phase 9: Documentation | #24 | 4 |
| **TOTAL** | | **64** |

---

## Implementation Order

```
Phase 0 (Foundation)
    ↓
Phase 1 (Pipeline Ordering & HIL)
    ↓
Phase 2 (Multi-Layer Implementation)
    ↓
Phase 3 (Test Framework Integration)
    ↓
Phase 4 (Dashboard Live Data)
    ↓
Phase 5 (Multi-Model Review)
    ↓
Phase 6 (Comprehensive Security)
    ↓
Phase 7 (Comprehensive Packaging)
    ↓
Phase 8 (Deployment)
    ↓
Phase 9 (Documentation)
```

**Each phase must complete before next phase starts.**

---

## What Each Phase Produces

| Phase | Produces |
|-------|----------|
| 0 | Constitution.md, AGENTS.md, wired knowledge base, fixed implement prompt |
| 1 | Correct pipeline order, HIL gates, status updates, audit log |
| 2 | 4 sub-agents (UI/API/DB/Logic), skeleton-first approach |
| 3 | All tests in test framework, run from there, results logged |
| 4 | Live dashboard with all tabs and agent detail pages |
| 5 | 3 review agents, architecture completeness, draw.io diagrams |
| 6 | Threat analysis, CVE scans, OWASP ZAP, injection testing |
| 7 | Multi-platform packages with help files, BOM, install/uninstall |
| 8 | Deploy scripts for multiple environments, E2E validation |
| 9 | Install guide, user guide, API guide, page help |

---

*Document generated by Pipeline Implementation Plan — 2026-09-01*
