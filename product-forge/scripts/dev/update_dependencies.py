import json
import collections

PATH = 'pipeline-definition.json'

with open(PATH, 'r', encoding='utf-8-sig') as f:
    data = json.load(f, object_pairs_hook=collections.OrderedDict)

stages = data['stages']

# Canonical dependency graph.
# Sequential chain, with two genuinely independent parallel groups:
#   design reviews : 1b (design_critic) and 1c (ux-ia) both after 1a, converge at 2
#   verification   : 5 (security) and 6 (NFR tests) both after 4c-vqa, converge at 7
STAGE_DEPS = {
    "0": [],
    "0a": ["0"],
    "1": ["0a"],
    "1a": ["1"],
    "1b": ["1a"],
    "1c": ["1a"],
    "2": ["1b", "1c"],
    "3": ["2"],
    "4-0": ["3"],
    "4a": ["4-0"],
    "4a-vqa": ["4a"],
    "4b": ["4a-vqa"],
    "4b-vqa": ["4b"],
    "4c": ["4b-vqa"],
    "4c-vqa": ["4c"],
    "5": ["4c-vqa"],
    "6": ["4c-vqa"],
    "7": ["5", "6"],
    "8": ["7"],
    "9": ["8"],
    "10": ["9"],
    "11": ["10"],
    "12": ["11"],
}

PARALLEL_SAFE = {"1b", "1c", "5", "6"}

# Explicit agent-level ordering within a stage. The first agent in ideal_flow
# normally has no predecessor; each subsequent agent depends on the previous.
AGENT_DEPS = {
    "4-0": {"implement": [], "devops": ["implement"]},
    "4a": {"implement": [], "devops": ["implement"],
           "code-review": ["devops"], "validate": ["code-review"]},
    "4b": {"implement": [], "devops": ["implement"],
           "code-review": ["devops"], "validate": ["code-review"]},
    "4c": {"implement": [], "devops": ["implement"],
           "code-review": ["devops"], "validate": ["code-review"]},
    "10": {"devops": [], "orchestrator": ["devops"]},
}

# Sub-agent (implement sub_flow) ordering.
SUB_AGENT_DEPS = {
    "implement-db": [],
    "implement-api": ["implement-db"],
    "implement-logic": ["implement-api"],
    "implement-ui": ["implement-logic"],
}

for sid, sdef in stages.items():
    if sid not in STAGE_DEPS:
        continue
    # Replace runs_after with canonical depends_on.
    sdef.pop('runs_after', None)
    sdef['depends_on'] = STAGE_DEPS[sid]
    sdef['parallel_safe'] = sid in PARALLEL_SAFE

    # Agent-level dependencies for this stage.
    agents = sdef.get('ideal_flow', [])
    if sid in AGENT_DEPS:
        sdef['agent_dependencies'] = AGENT_DEPS[sid]
    elif agents:
        sdef['agent_dependencies'] = {agents[0]: []}
    else:
        sdef['agent_dependencies'] = {}

    # Sub-agent ordering inside implement.sub_agents.
    subs = sdef.get('sub_agents') or {}
    for agent_name, cfg in subs.items():
        if cfg.get('sub_flow'):
            cfg['sub_agent_dependencies'] = {
                a: SUB_AGENT_DEPS.get(a, []) for a in cfg['sub_flow']
            }

data['parallel_groups'] = [
    {"name": "design-reviews", "stages": ["1b", "1c"],
     "runs_after": ["1a"], "converges_at": "2"},
    {"name": "verification", "stages": ["5", "6"],
     "runs_after": ["4c-vqa"], "converges_at": "7"},
]

with open(PATH, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write('\n')

print('Updated stages:', len(STAGE_DEPS))
print('Parallel-safe stages:', sorted(PARALLEL_SAFE))
print('Parallel groups:', [g['name'] for g in data['parallel_groups']])
