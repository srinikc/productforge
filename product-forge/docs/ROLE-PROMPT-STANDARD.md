# Role-Prompt Standard (BI-0228)

> Standard for every `.opencode/agent/*.md` card so the roster's role prompts are consistent
> and borrow proven OSS structure while keeping Product Forge's artifact/compliance contracts.

## Required frontmatter
`description`, `mode` (primary|subagent), `model`, `agent_id` (+ optional `version`, `spec_version`,
`permission`).

## Canonical sections (top of the card, before the verbatim instructions)
- `## 0. METADATA` — Agent ID, Version, Spec Version, Model tier, Tools, Stages.
- `## 1. ROLE` — identity + what it decides / does NOT do.
- `## 2. INPUTS` — allowed vs forbidden inputs (information diet).
- `## 3. OUTPUTS` — artifact format + contract (`max_input`/`max_output`).
- `## 4. RULES` — do / don't (no mocks/TODOs/placeholders; respect scope + tech stack).
- `## 5. WORKFLOW` — ordered steps.
- `## 6. ARTIFACTS` — role-specific outputs.
- `## 7. QUALITY CHECKS` — pass criteria.
- `## 8. STATE UPDATES` — audit/context updates.

## OSS structure borrowed (keep PF contracts)
| OSS pattern | Mapped to |
|---|---|
| role / goal / backstory (CrewAI, MetaGPT SOP) | `## 1. ROLE` (+ the verbatim persona) |
| tool contract (Claude Code/Cursor/Devin) | frontmatter `permission` + METADATA `Tools` + §4 RULES |
| do / don't + termination (ChatDev, 12-factor-agents) | `## 4. RULES`, `## 5. WORKFLOW`, VERDICT rules |
| output schema / information diet | `## 3. OUTPUTS`, `## 2. INPUTS` |

> Keep PF-specific: artifact contracts, compliance checklists, stage rules, and the
> `discipline_guard` (design→plan→360→produce; no placeholders; fail-closed).

## Enforcement (advisory)
`scripts/dev/role_prompt_audit.py` (also run as an advisory step in `scripts/dev/wired_audit.py`)
reports any card missing a required frontmatter key or canonical section. Non-fatal.
