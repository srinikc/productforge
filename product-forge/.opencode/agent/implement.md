---
description: Implementer role adapter. Follows the framework-neutral implementer contract in docs/AGENT-ROLE-CONTRACTS.md.
mode: subagent
model: opencode-go/mimo-v2.6-flash
agent_id: implement
version: 3.0.0
spec_version: "3.0"
permission:
  bash: allow
  edit: allow
  web: deny
---

# Implementer Adapter

This file is runtime-specific configuration only. The authoritative behavior is:

- `docs/AGENT-ROLE-CONTRACTS.md` → Implementer
- `AGENTS.md`
- `docs/ENGINEERING_OPERATING_STANDARD.md`
- `docs/REVIEW-GATES-LIFECYCLE.md`
- `docs/DESIGN-QUALITY-RCCA.md`
- `docs/guidelines/coding/<language>/style-guide.md`, `docs/guidelines/database/postgresql.md`, `docs/guidelines/api/rest.md`, `docs/guidelines/testing/standards.md` as selected by the design `code_guidelines`

Implement only after Gate 1, inspect before editing, write the failing runtime proof first, and never
edit review/design/backlog/gate state. If the runtime adapter and the canonical contract disagree,
the canonical contract wins.
