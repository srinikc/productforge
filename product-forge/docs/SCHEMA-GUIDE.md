# JSON Schema Reference

Product Forge uses JSON Schema (draft-07) as the canonical source of truth for all pipeline artifact validation. Schemas live in `docs/schemas/`.

## Schemas

| Schema | File | Purpose |
|--------|------|---------|
| Pipeline State | `pipeline-state.v1.schema.json` | `products/<project>/pipeline.json` — tracks stage execution, human gates, blockers |
| Agent Contract | `agent-contract.v1.schema.json` | `.opencode/agent/*.md` — defines the common structure all agents must follow |
| Audit Log Entry | `audit-log-entry.v1.schema.json` | `products/<project>/agent-audit.md` — one entry per agent action |
| Product Plan | `product-plan.v1.schema.json` | `products/<project>/product-plan.json` — vision, tech stack, features, pipeline config |
| Compliance Report | `compliance-report.v1.schema.json` | `products/<project>/compliance/<agent>-compliance.md` — compliance check results |
| Error Response | `error-response.v1.schema.json` | Standard error format returned by agents |
| Human Gate | `human-gate.v1.schema.json` | Human approval gate definitions and decisions |

## Versioning

All schemas use `v1` suffix. When a breaking change is needed:
1. Create `v2` file (e.g., `pipeline-state.v2.schema.json`)
2. Update `spec_version` in the corresponding artifact
3. Migration tool handles v1→v2 conversion
4. Old schemas kept for 2 release cycles

## Validation

Validate artifacts against schemas:

```python
from core.schema_validator import validate_artifact, validate_agent_md

# Validate pipeline.json
result = validate_artifact("pipeline-state", pipeline_data)
if not result.valid:
    for err in result.errors:
        print(f"ERROR: {err.path} - {err.message}")

# Validate agent .md file
result = validate_agent_md("design")
if result.valid:
    print(f"Agent {result.data['frontmatter']['agent_id']} is valid")
```

## CLI Validation

```bash
# Validate all schemas
python -m core.schema_validator validate-all

# Validate specific artifact
python -m core.schema_validator validate pipeline-state products/myworld/pipeline.json

# Validate agent .md
python -m core.schema_validator validate-agent design
```

## Schema Properties

### Required Fields

Every schema has `spec_version` at the root. This is used for:
- Determining which schema version to apply
- Migration tool deciding how to transform
- Compliance checker verifying schema conformity

### Severity Levels

When schemas define rules with severity:

| Level | Behavior |
|-------|----------|
| `critical` | Pipeline stops. Must fix before proceeding. |
| `high` | Warning shown. Human decides. |
| `medium` | Logged. Fix in next cycle. |
| `low` | Silent. |
| `info` | Not checked. |

### Additional Properties

Most schemas use `"additionalProperties": false` to enforce strict structure. If a new field is needed, update the schema (not the code).
