# Product Forge Constitution

**Every agent MUST follow these rules. No exceptions.**

---

## 1. Working Code Only

- Every feature must run. No stubs, no TODOs, no placeholders.
- If you can't build it, say BLOCKER. Don't fake it.
- Tests must pass. Real tests, real results.

## 2. Human Approves Before Moving On

- After every agent finishes, human reviews and says "approve" or "fix this".
- Pipeline never advances without human approval.
- Human can always say "show me more" before deciding.

## 3. Code Review After Every Phase

- After implementation, code review happens BEFORE testing.
- Code review finds issues → fix agent fixes → code review re-checks → then test.
- Never skip code review.

## 4. Tests Live in Test Framework

- All tests (unit, API, DB, UI, security, performance, install) go in `test-framework/tests/<project>/`.
- Tests are run FROM test framework.
- Results are logged TO test framework.
- Dashboard shows test results from test framework.

## 5. Follow the Guidelines

- Before coding, load relevant guidelines from `docs/guidelines/`.
- Frontend code follows `docs/guidelines/frontend/`.
- Backend code follows `docs/guidelines/backend/`.
- API code follows `docs/guidelines/api/`.
- Security follows `docs/guidelines/security/`.
- Architecture follows `docs/guidelines/architecture/`.

## 6. Each Agent Logs Its Work

- Every agent writes to `agent-audit.md` with timestamp.
- Format: `[TIME] [AGENT] [STAGE] [ACTION]`
- This is the pipeline journal.

## 7. Build Layer by Layer

- Implementation order: DB → API → Business Logic → UI → Integration.
- Skeleton first (empty shell), then enable features one by one.
- Like building a house: foundation first, then walls, then rooms, then furniture.

## 8. Architecture Must Cover Everything

Architect agent must address:
- UI/UX design and theme
- Database schema
- API endpoints
- Business logic
- Security (auth, secrets, encryption)
- Packaging (Docker, Windows, Linux, macOS)
- Install/uninstall/upgrade/rollback
- Deployment
- Performance targets
- All 22+ NFR subsections

## 9. Packaging Must Be Complete

Every package must include:
- Application files
- Install script
- Uninstall script
- User guide
- API guide
- BOM (Bill of Materials)
- Version file
- Checksums

## 10. Security Is Not Optional

- Threat analysis after architecture.
- Package CVE scan after each phase.
- OWASP ZAP scan before packaging.
- SQL injection, URL injection testing.
- No hardcoded secrets. Passwords hashed. TLS enabled.

## 11. Dashboard Shows Everything

Dashboard must show:
- Pipeline workflow (current stage, what's done, what's next)
- Each agent's status and details
- Test results per phase
- Issues found and resolved
- Final summary when done

## 12. Final Summary at End

When pipeline completes, generate:
- All features implemented
- Each agent's work summary
- Tokens used
- FR/NFR status
- Issues found and resolved
- Tech stack used
- Where app is running
- Links to guides and test results

## 13. Pipeline Exit

After final summary, ask: "Exit pipeline?"
- Yes → release lock, cleanup, done.
- No → show options: review, make changes, redeploy, export.

---

## How to Start a New Project

1. Tell the orchestrator: "Start new project: [name]"
2. Orchestrator creates project directory and pipeline.json
3. Ideation agent asks: what do you want to build?
4. Pipeline runs through stages, human approves each one.
5. At the end, you have working, tested, packaged software.

---

*This constitution applies to ALL projects. Every agent reads it before starting work.*
