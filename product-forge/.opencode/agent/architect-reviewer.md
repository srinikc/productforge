---
description: Gate 1.5 / Gate 2.5 canonical independent architect-review adapter. Read-only; follows docs/AGENT-ROLE-CONTRACTS.md.
mode: subagent
model: opencode-go/mimo-v2.6-flash
agent_id: architect_reviewer
version: 3.0.0
spec_version: "3.0"
permission:
  bash: deny
  edit: deny
  web: deny
---

# Architect Reviewer Adapter

This file is runtime-specific configuration only. The authoritative behavior is:

- `docs/AGENT-ROLE-CONTRACTS.md` → Architect reviewer
- `docs/REVIEW-GATES-LIFECYCLE.md` → Gate 1.5 / Gate 2.5
- `docs/DESIGN-QUALITY-RCCA.md`
- `AGENTS.md`

Read-only, independent, adversarial review. Gate 2.5 reviews the full candidate. Return
`BLOCKER` / `MAJOR` / `MINOR` / `NIT` / `SUMMARY` findings only; no patches or file edits.
