# Agent Contract Standard

All agent `.opencode/agent/*.md` files MUST follow this structure. The JSON Schema (`docs/schemas/agent-contract.v1.schema.json`) is the canonical source of truth.

---

## File Format

```markdown
---
description: <one-line description>
mode: <subagent|primary>
model: <model-id>
agent_id: <kebab-case-id>
version: <semver>
spec_version: "1.0"
permission:
  bash: <allow|deny>
  edit: <allow|deny>
  web: <allow|deny>
  skill:
    "<skill-name>": <allow|deny>
---

# <Agent Title>

## 0. METADATA
...
## 1. ROLE
...
## 2. INPUTS
...
## 3. OUTPUTS
...
## 4. RULES
...
## 5. WORKFLOW
...
## 6. ARTIFACTS
...
## 7. QUALITY CHECKS
...
## 8. STATE UPDATES
...
```

---

## Required Sections (0-8)

Every agent MUST have these sections in order:

### Section 0: METADATA

Header with agent metadata. Keep brief — the frontmatter is the primary source.

```markdown
## 0. METADATA

- **Agent ID**: design
- **Version**: 1.0.0
- **Stage**: 1
- **Spec Version**: 1.0
```

### Section 1: ROLE

What this agent does and does NOT do. One paragraph max.

```markdown
## 1. ROLE

Design agent. Extracts formal requirements and produces a design doc from the product plan.
- ✅ Writes: `docs/requirements.md`, `docs/design.md`, `docs/wireframes/`
- ✅ Decides: Feature prioritization, UI/UX design
- ❌ Does NOT write code
- ❌ Does NOT reduce scope without approval
```

### Section 2: INPUTS

What this agent reads. One table. Be specific.

```markdown
## 2. INPUTS

| File | Sections to Read | Why |
|---|---|---|
| `docs/product-plan.md` | Entire file | Source of truth for the idea |
| `docs/requirements.md` | Sections 3-5 | Requirements scope |
```

### Section 3: OUTPUTS

What this agent produces. One table.

```markdown
## 3. OUTPUTS

| File | Purpose | Required |
|---|---|---|
| `docs/design.md` | Complete design doc | Yes |
| `docs/wireframes/` | UI wireframes | Yes |
```

### Section 4: RULES

Binding rules. Grouped by type. Each rule has severity.

```markdown
## 4. RULES

### 4.1 CRITICAL (severity: critical — pipeline stops)

1. NO scope reduction without user approval
2. Every feature gets FRs
3. No "deferred to later" without explicit user decision

### 4.2 HIGH (severity: high — warns)

1. All output files must be written to `docs/`
2. No code in design docs
3. Reference file paths, not URLs

### 4.3 MEDIUM (severity: medium — logged)

1. Keep design docs under 500 lines
2. Use tables for structured data
```

### Section 5: WORKFLOW

Step-by-step flow. Numbered steps. One action per step.

```markdown
## 5. WORKFLOW

1. Read `docs/product-plan.md` (sections: vision, features, tech_stack)
2. Load constitution rules from `docs/CONSTITUTION.md`
3. Write `docs/requirements.md` with all FRs
4. Write `docs/design.md` with architecture decisions
5. Create wireframes in `docs/wireframes/`
6. Return artifacts to orchestrator
```

### Section 6: ARTIFACTS

What this agent produces. One table per artifact type.

```markdown
## 6. ARTIFACTS

| Artifact | Format | Location | Required |
|---|---|---|---|
| Design doc | Markdown | `docs/design.md` | Yes |
| Wireframes | SVG/PNG | `docs/wireframes/` | Yes |
| Requirements | Markdown | `docs/requirements.md` | Yes |
```

### Section 7: QUALITY CHECKS

Automated and manual checks. Each has a verify method.

```markdown
## 7. QUALITY CHECKS

### Auto-verifiable (compliance_check.py runs these)

- [ ] `docs/design.md` exists and is > 100 lines
- [ ] `docs/requirements.md` has FR-001 through FR-N
- [ ] No "TODO" or "PLACEHOLDER" in output files
- [ ] Wireframes directory has at least 1 file

### LLM-verifiable (compliance_verifier.py runs these)

- [ ] Design covers all features from product-plan.md
- [ ] No scope reduction without explicit approval
- [ ] FRs have acceptance criteria
```

### Section 8: STATE UPDATES

What gets written to `agent-audit.md` and `pipeline.json`.

```markdown
## 8. STATE UPDATES

### agent-audit.md
```
[TIME] [design] [1] [agent_start]
[TIME] [design] [1] [agent_complete]
```

### pipeline.json
```json
{
  "stages": { "1": { "status": "completed", "verdict": "APPROVED" } }
}
```
```

---

## Optional Sections (9-12)

### Section 9: TIMING

Expected execution time and resource usage.

```markdown
## 9. TIMING

- **Expected duration**: 2-5 minutes
- **Token usage**: ~5k input, ~10k output
- **Retry budget**: 3 attempts
```

### Section 10: DEPENDENCIES

What this agent needs from other agents or external services.

```markdown
## 10. DEPENDENCIES

- **Requires**: ideation (product-plan.md must exist)
- **Produces for**: architect (design.md)
- **External**: None
```

### Section 11: ERRORS

Error types and recovery strategies.

```markdown
## 11. ERRORS

| Error | Code | Recovery |
|---|---|---|
| Input file missing | EDS-0001 | Fail. Orchestrator re-runs ideation. |
| Output write fails | EDS-0002 | Retry 3x. Then fail. |
```

### Section 12: EXAMPLES

Example inputs/outputs. Keep brief.

```markdown
## 12. EXAMPLES

### Example Input
product-plan.md contains: "Build a todo app with auth"

### Example Output
- docs/design.md: 150 lines, 8 FRs
- docs/wireframes/login.svg: Login page wireframe
```

---

## Agent-Specific Sections (13+)

Only agents with a whitelisted reason may add sections 13+. These are documented in `docs/schemas/agent-contract.v1.schema.json` under `WhitelistedAgentSpecificSections`.

**Restricted sections:**

| # | Section | Restricted To |
|---|---------|---------------|
| 13 | PROMPTS | Any agent |
| 14 | TOOLS | Any agent |
| 15 | INTEGRATION | Any agent |
| 16 | SECURITY | security, security-audit |
| 17 | PERFORMANCE | performance |
| 18 | BILLING | finops |
| 19 | STAGE FLOWS | orchestrator |
| 20 | COMPLIANCE GATES | orchestrator |
| 21 | PARALLEL EXECUTION | orchestrator |
| 22 | RECOVERY | orchestrator |

---

## Migration

Old agents that don't follow this structure can be converted:

```python
from core.agent_migrator import migrate_agent

result = migrate_agent("design")
# Shows diff, asks for approval
```

See `core/agent_migrator.py` for details.
