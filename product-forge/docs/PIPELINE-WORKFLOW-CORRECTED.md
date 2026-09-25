# Pipeline Workflow — Corrected Flow

**Purpose:** Simple, clear pipeline that produces working software.
**Rule:** Code review after EACH phase, BEFORE testing. Human approves after EVERY agent.

---

## Pipeline Stages (Corrected Order)

```
Stage 0: Ideation
    ↓
Stage 1: Design (with wireframe review)
    ↓
Stage 2: Architect (with multi-model review)
    ↓
Stage 3: Refine Requirements
    ↓
Stage 4-0: Skeleton
    ├── implement writes code
    ├── devops builds skeleton
    └── HIL: Human sees structure
    ↓
Stage 4a: Phase 1 Features (web + mobile)
    ├── implement writes code
    ├── devops generates build
    ├── code-review reviews code
    ├── fix fixes issues
    ├── validate runs tests (test cycle)
    └── HIL: Human approves
    ↓
Stage 4b: Phase 2 Features (web + mobile)
    ├── implement writes code
    ├── devops generates build
    ├── code-review reviews code
    ├── fix fixes issues
    ├── validate runs tests (test cycle)
    └── HIL: Human approves
    ↓
Stage 4c: Phase 3 Features (web + mobile)
    ├── implement writes code
    ├── devops generates build
    ├── code-review reviews code
    ├── fix fixes issues
    ├── validate runs tests (test cycle)
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
    ├── devops sets up CI/CD
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

## Stage Details

### Stage 0: Ideation
- **Agent:** ideation
- **Input:** User's idea (free text)
- **Output:** `docs/product-plan.md`, `pipeline.json`
- **Human Gate:** YES — Must approve scope
- **What happens:** Agent asks what to build, creates scope document

### Stage 1: Design
- **Agent:** design
- **Input:** `docs/product-plan.md`
- **Output:** `docs/requirements.md`, `docs/design.md`
- **Human Gate:** YES — Must approve design AND wireframes
- **What happens:** Agent creates requirements and UI/UX design
- **HIL Wireframe Check:** Human reviews wireframes before proceeding

### Stage 2: Architect
- **Agent:** architect (+ 2-3 review agents)
- **Input:** `docs/requirements.md`, `docs/design.md`
- **Output:** `docs/architecture.md`, `docs/architecture.drawio`
- **Human Gate:** YES — Must approve architecture
- **What happens:** Agent designs architecture. 2-3 review agents check it (general, security, performance). Findings merged. Human approves.
- **Architect must include:** UI/UX theme, DB schema, API design, security, packaging, install/upgrade, deployment, all NFRs, caching, rendering

### Stage 3: Refine Requirements
- **Agent:** orchestrator (with user)
- **Input:** `docs/architecture.md`
- **Output:** Updated `docs/requirements.md` (if changes needed)
- **Human Gate:** YES — Must approve before implementation
- **What happens:** Check architecture matches requirements. Fix any gaps.

### Stage 4-0: Skeleton
- **Agent:** implement → devops
- **Input:** `docs/architecture.md`, `docs/requirements.md`
- **Output:** Skeleton code + initial build
- **Human Gate:** YES — Human sees full structure in browser
- **What happens:** 
  1. Implement creates empty shell (DB schema, API endpoints, UI pages)
  2. DevOps generates initial Docker image and web bundle
  3. DevOps verifies build works
  4. Human sees structure in browser

### Stage 4a: Phase 1 Features
- **Agent:** implement → devops → code-review → fix → validate
- **Input:** Architecture + requirements (Phase 1 FRs only)
- **Output:** Working code + deployable build for Auth, Dashboard, Search, ToDo (+ mobile if applicable)
- **Human Gate:** YES — Human tests each feature in browser AND simulator
- **Flow:**
  1. Implement agent builds features (DB → API → Logic → UI)
  2. **DevOps generates deployable build** (Docker image, web bundle, mobile app)
  3. DevOps verifies build works
  4. DevOps registers build in test framework
  5. Code review agent reviews Phase 1 code
  6. Fix agent fixes any issues
  7. Validate agent runs Phase 1 tests **against the build**
  8. Validate logs results to test cycle
  9. Human tests in browser AND simulator, approves or requests fixes
- **Mobile Testing:** If feature has mobile component, test in iOS Simulator / Android Emulator
- **Build Output:** Docker image, web bundle, iOS/Android build in `builds/` directory

### Stage 4b: Phase 2 Features
- **Same flow as 4a**
- **Features:** Calendar, Goals, News, Health
- **Build:** Incremental build including Phase 1+2
- **Human tests:** Phase 1 still works + Phase 2 works (web + mobile)

### Stage 4c: Phase 3 Features
- **Same flow as 4a**
- **Features:** Exploratory, Spiritual, Documents, Financial
- **Build:** Incremental build including Phase 1+2+3
- **Human tests:** Phase 1+2 still work + Phase 3 works (web + mobile)

### Stage 5: Security Scan
- **Agent:** security
- **Input:** All code + `docs/architecture.md`
- **Output:** `docs/reports/security-report.md`
- **What happens:** Threat analysis, CVE scan, OWASP ZAP, injection testing

### Stage 6: NFR Tests
- **Agent:** validate (NFR)
- **Input:** All code + architecture NFRs
- **Output:** `docs/reports/nfr-report.md`
- **What happens:** Performance, accessibility, security tests

### Stage 7: Full Test Suite
- **Agent:** validate
- **Input:** All code + all tests
- **Output:** `docs/reports/test-report.md`
- **What happens:** Run all tests from test framework

### Stage 8: Document
- **Agent:** document
- **Input:** All code + architecture + requirements
- **Output:** README, user guide, API guide, install guide
- **Human Gate:** YES — Human reviews docs

### Stage 9: Package (Detailed)
- **Agent:** package
- **Input:** All code + docs + builds from Stage 4a/4b/4c
- **Output:** BOM, installers, security audit, platform-specific packages
- **Human Gate:** YES — Human sees build output
- **What happens:** This is DETAILED packaging, not initial build. Builds were already generated by DevOps in Stage 4a/4b/4c. This stage adds:
  - Bill of Materials (BOM)
  - Security audit of dependencies
  - Platform-specific installers (Windows EXE, Linux DEB, macOS DMG)
  - Help files and man pages
  - Package signing
  - Install/uninstall verification

### Stage 10: Pre-Production
- **Agent:** devops + orchestrator
- **Input:** Everything
- **Output:** CI/CD pipeline, monitoring setup, `docs/FINAL_SUMMARY.md`
- **Human Gate:** YES — Final walkthrough
- **What happens:** 
  1. DevOps sets up CI/CD pipeline (GitHub Actions, GitLab CI, etc.)
  2. DevOps configures monitoring (Prometheus, Grafana)
  3. DevOps creates deployment configs
  4. Orchestrator generates final summary with all features, agents, tokens, test results, issues, tech stack, links

### Stage 11: Deploy
- **Agent:** devops
- **Input:** Packages, CI/CD configs, deployment configs
- **Output:** Deployed application
- **Human Gate:** YES — Must approve before production
- **What happens:** 
  1. DevOps deploys to staging environment
  2. Human verifies in staging
  3. DevOps deploys to production environment
  4. DevOps sets up production monitoring
  5. DevOps creates rollback plan

### Stage 12: Exit
- **What happens:** Ask "Exit pipeline?" If yes, release lock, cleanup, done.

---

## Agent Status Update Format

After EVERY agent run, generate this table:

```
SUMMARY OF AGENT WORK
======================

| Field | Value |
|-------|-------|
| Previous Agent | [name] |
| Current Agent Name | [name] |
| Model Name | [model] |
| Scope | [what was done] |
| Start Time | [timestamp] |
| End Time | [timestamp] |
| Time Taken | [duration] |
| Implemented | [list of things] |
| Artifacts | [files created with links] |
| Tokens Used | [count] |
| Stage | [stage number] |
| Phase | [phase number] |
| Issues Found | [count + list] |
| Next Agent | [name] |
| Action/Reviews Needed | [yes/no + details] |
| State Files Updated | [context] [pipeline] [audit] |
```

---

## Audit Log Format

Every agent writes to `agent-audit.md`:

```
[TIMESTAMP] [AGENT_NAME] [STAGE] [ACTION]
```

Example:
```
2026-09-01T10:00:00Z [orchestrator] [0] Start pipeline
2026-09-01T10:01:00Z [ideation] [0] Generate scope
2026-09-01T10:03:00Z [orchestrator] [0] HIL Gate - waiting for human
2026-09-01T10:05:00Z [design] [1] Start design
2026-09-01T10:10:00Z [design] [1] Complete - requirements.md, design.md
```

---

## Test Framework Integration

ALL tests go in `test-framework/tests/<project>/`:
- `unit/` — Unit tests
- `api/` — API tests
- `db/` — Database tests
- `e2e/` — End-to-end tests (Playwright)
- `visual/` — Visual regression tests
- `security/` — Security tests
- `performance/` — Performance tests
- `install/` — Install/uninstall tests

Tests are run FROM test framework. Results logged TO test framework.

---

## Build Ownership (Who Generates What)

| Agent | Stage | Responsibility | Output |
|-------|-------|---------------|--------|
| **implement** | 4 | Writes code | Source code |
| **devops** | 4 | Generates builds, registers in test framework | `builds/<phase>/` |
| **code-review** | 4 | Reviews code quality | `reports/code-review.md` |
| **fix** | 4 | Fixes issues found | Updated source code |
| **validate** | 4 | Runs tests, logs to test cycle | Test results in test framework |
| **security** | 5 | Security scans | `docs/reports/security-report.md` |
| **validate** | 6-7 | NFR + full test suite | Test reports |
| **document** | 8 | Creates docs | README, guides |
| **package** | 9 | Detailed packaging (BOM, installers) | `dist/` with installers |
| **devops** | 10 | CI/CD setup, monitoring | `.github/workflows/`, deploy configs |
| **devops** | 11 | Deploys to staging, then production | Deployed app |

### Build Flow Per Phase

```
1. implement writes code
2. devops generates Docker + web build
3. devops verifies build works
4. devops registers build in test framework
5. code-review reviews code
6. fix fixes issues (if any)
7. validate runs tests against build
8. validate logs results to test cycle
9. human approves
```

### Test Cycle Flow

```
1. validate starts test cycle
2. validate runs web tests → adds to cycle
3. validate runs mobile tests → adds to cycle
4. validate runs security tests → adds to cycle
5. validate completes cycle
6. Cycle saved to test-framework/results/test-cycles/
```

---

## Test Cycles

A test cycle groups all testing results for a phase:

### Test Cycle Structure
```json
{
  "cycle_id": "myworld_phase4a_20260901_103000",
  "project": "myworld",
  "phase": "4a",
  "stage": "4",
  "status": "passed",
  "build_version": "1.0.0-phase4a",
  "test_runs": [
    {"test_type": "unit", "framework": "vitest", "passed": 48, "failed": 2},
    {"test_type": "mobile_ios", "framework": "vitest-mobile", "passed": 20, "failed": 0},
    {"test_type": "e2e", "framework": "playwright", "passed": 15, "failed": 0}
  ],
  "total_tests": 83,
  "total_passed": 81,
  "total_failed": 2
}
```

### Test Types in Cycle
- `unit` — Unit tests
- `api` — API tests
- `integration` — Integration tests
- `e2e` — End-to-end tests (Playwright)
- `visual` — Visual regression tests
- `security` — Security tests
- `performance` — Performance tests
- `mobile_ios` — iOS simulator tests
- `mobile_android` — Android emulator tests
- `install` — Install/uninstall tests
- `smoke` — Smoke tests
- `sanity` — Sanity tests

---

## Mobile Testing (Simulators — No Device Required)

Mobile testing happens during EACH phase (4a, 4b, 4c), not as separate stage.

### Recommended Frameworks

| Framework | Platform | Best For | Install |
|-----------|----------|----------|---------|
| **Stowaway** | iOS + Android | React Native E2E via Hermes CDP | `npm install stowaway` |
| **vitest-mobile** | iOS + Android | Component tests in real RN app | `npm install vitest-mobile` |
| **Zeno Mobile Runner** | iOS + Android | Agent-native automation + traces | `npm install zeno-mobile-runner` |
| **Mobilewright** | iOS + Android | Playwright-style mobile API | `npm install mobilewright` |
| **Testa** | iOS only | Real HID gestures + OCR | `brew install testa` |

### How It Works (No Device Deploy)

```
1. Start iOS Simulator / Android Emulator
2. Start Metro bundler (React Native)
3. Build app → installs in simulator automatically
4. Run tests against simulator (not device)
5. Tests interact via:
   - Hermes CDP bridge (Stowaway)
   - Native touch synthesis (vitest-mobile)
   - Accessibility tree + OCR (Testa)
   - ADB/simctl (all frameworks)
```

### Setup for React Native

```bash
# Install simulator testing
npm install stowaway vitest-mobile --save-dev

# iOS (requires Xcode)
npx vitest-mobile bootstrap --platform ios

# Android (requires Android SDK)
npx vitest-mobile bootstrap --platform android

# Run tests
npx vitest run --project ios
npx vitest run --project android
```

### What Gets Tested in Simulator

- UI renders correctly
- Touch interactions work
- Navigation flows
- Form submissions
- Push notifications (iOS: xcrun simctl push)
- Biometric auth (Testa)
- Deep linking
- Offline behavior

---

## Dashboard Tabs

1. **Pipeline Workflow** — Text diagram + draw.io, color-coded by status
2. **Agents** — Each agent as card with status
3. **Agent Detail** — Click card → full info (prompt, inputs, outputs, tokens, skills)
4. **Test Results** — Pass/fail per phase, per feature
5. **Architecture** — Diagram + tech stack + NFR status
6. **Live Data** — Real-time from pipeline.json, agent-audit.md
7. **Final Summary** — Complete project report

---

*This is the corrected pipeline flow. Code review happens after EACH phase, not after all implementation.*
