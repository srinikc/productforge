import json

def load(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)

def save(p, s):
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(s, f, indent=2, ensure_ascii=False)
        f.write('\n')

# --- audit-log-entry.v1: add telemetry fields we legitimately write ---
ap = 'docs/schemas/audit-log-entry.v1.schema.json'
a = load(ap)
props = a['properties']
extra = {
    'agent_id': {'type': 'string'},
    'stage_id': {'type': 'string'},
    'model': {'type': 'string'},
    'provider': {'type': 'string'},
    'input_tokens': {'type': 'integer'},
    'output_tokens': {'type': 'integer'},
    'cached_tokens': {'type': 'integer'},
    'reasoning_tokens': {'type': 'integer'},
    'total_tokens': {'type': 'integer'},
    'cost': {'type': 'number'},
    'cache_hit': {'type': 'boolean'},
    'chunking_used': {'type': 'boolean'},
    'chunks_count': {'type': 'integer'},
    'model_context_window': {'type': 'integer'},
    'prompt_chars': {'type': 'integer'},
    'output_chars': {'type': 'integer'},
    'artifacts_used': {'type': 'array'},
    'started_at': {'type': 'string'},
    'completed_at': {'type': 'string'},
    'duration_ms': {'type': 'integer'},
    'finish_reason': {'type': 'string'},
    'truncated': {'type': 'boolean'},
    'retries': {'type': 'integer'},
    'compaction_used': {'type': 'boolean'},
    'compaction_saved_chars': {'type': 'integer'},
    'continuations': {'type': 'integer'},
}
for k, v in extra.items():
    props.setdefault(k, v)
save(ap, a)
print('audit-log-entry.v1 props:', len(props))

# --- pipeline-state.v1: add checkpoint fields we write ---
pp = 'docs/schemas/pipeline-state.v1.schema.json'
p = load(pp)
props = p['properties']
extra = {
    'pipeline_id': {'type': 'string'},
    'started_at': {'type': 'string'},
    'current_iteration': {'type': 'integer'},
    'completed_stages': {'type': 'array'},
    'total_tokens': {'type': 'integer'},
    'total_cost': {'type': 'number'},
    'stage_durations': {'type': 'array'},
    'decision_log': {'type': 'array'},
    'saved_at': {'type': 'string'},
}
for k, v in extra.items():
    props.setdefault(k, v)
save(pp, p)
print('pipeline-state.v1 props:', len(props))

# --- project.v1 schema (new) ---
schema = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "https://product-forge.dev/schemas/project.v1.schema.json",
    "title": "Project Config",
    "description": "Schema for products/<project>/project.json",
    "type": "object",
    "required": ["name"],
    "properties": {
        "name": {"type": "string"},
        "idea": {"type": "string"},
        "description": {"type": "string"},
        "auto_approve": {"type": "boolean"},
        "approval_mode": {"type": "string", "enum": ["interactive", "auto", "semi"]},
        "max_total_time": {"type": "integer"},
        "parallel_stages": {"type": "boolean"},
        "business_model": {"type": "string"},
        "product_domain": {"type": "string"},
        "tech_stack": {"type": "array", "items": {"type": "string"}},
        "tech_stack_hints": {"type": "array", "items": {"type": "string"}},
        "implementation_iterations": {"oneOf": [{"type": "string"}, {"type": "integer"}]},
        "enable_delegation": {"type": "boolean"},
        "enable_tools": {"type": "boolean"},
        "budget": {
            "type": "object",
            "properties": {
                "currency": {"type": "string"},
                "soft_cost": {"type": "number"},
                "hard_cost": {"type": "number"},
                "soft_tokens": {"type": "integer"},
                "hard_tokens": {"type": "integer"},
                "variance_percent": {"type": "number"},
                "rate_limit_tokens_per_min": {"type": "integer"},
            },
        },
        "created_at": {"type": "string"},
    },
    "additionalProperties": True,
}
save('docs/schemas/project.v1.schema.json', schema)
print('project.v1 created')
