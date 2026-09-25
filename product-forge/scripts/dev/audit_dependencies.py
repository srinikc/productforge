import json
from collections import defaultdict, deque


def load():
    with open('pipeline-definition.json', encoding='utf-8-sig') as f:
        return json.load(f)


def deps_of(stage_id, sdef):
    deps = list(sdef.get('depends_on', []) or [])
    ra = sdef.get('runs_after')
    if isinstance(ra, str):
        deps.append(ra)
    elif isinstance(ra, (list, tuple)):
        deps.extend(ra)
    return [d for d in dict.fromkeys(deps) if d and d != stage_id]


def main():
    data = load()
    stages = data['stages']
    ids = list(stages.keys())
    idset = set(ids)

    print('=' * 78)
    print('PIPELINE DEPENDENCY AUDIT')
    print('=' * 78)

    problems = []

    # 1. Validate dependency references
    print('\n[1] Dependency validation')
    for sid in ids:
        for d in deps_of(sid, stages[sid]):
            if d not in idset:
                problems.append(f'stage {sid}: unknown dependency {d!r}')

    # 2. Roots
    roots = [s for s in ids if not deps_of(s, stages[s])]
    print('  Roots (no dependencies):', roots)

    # 3. Cycle detection + topological order
    graph = {s: deps_of(s, stages[s]) for s in ids}
    indeg = {s: 0 for s in ids}
    for s, ds in graph.items():
        for d in ds:
            if d in indeg:
                indeg[s] += 1
    queue = deque([s for s in ids if indeg[s] == 0])
    order = []
    while queue:
        n = queue.popleft()
        order.append(n)
        for m in ids:
            if n in graph[m]:
                indeg[m] -= 1
                if indeg[m] == 0:
                    queue.append(m)
    if len(order) != len(ids):
        remaining = [s for s in ids if s not in order]
        problems.append(f'cycle detected among: {remaining}')
    print('  Topological order:', order)

    # 4. Per-stage detail
    print('\n[2] Stage details (deps, agents, agent-order, parallel flag)')
    for sid in ids:
        s = stages[sid]
        agents = s.get('ideal_flow', [])
        subs = s.get('sub_agents', {}) or {}
        sub_flow = {}
        for a, cfg in subs.items():
            if cfg.get('sub_flow'):
                sub_flow[a] = cfg['sub_flow']
        print(f'  {sid:<8} {s.get("name",""):<26} deps={graph[sid]}')
        print(f'           agents(seq): {" -> ".join(agents) if agents else "-"}')
        if sub_flow:
            for a, flow in sub_flow.items():
                print(f'           sub_flow[{a}]: {" -> ".join(flow)}')

    # 5. Parallel candidates: stages sharing the same dependencies
    print('\n[3] Potential parallel groups (same dependency set)')
    by_deps = defaultdict(list)
    for sid in ids:
        by_deps[tuple(sorted(graph[sid]))].append(sid)
    for deps, group in sorted(by_deps.items(), key=lambda x: str(x[0])):
        if len(group) > 1:
            print(f'  deps={list(deps)} -> can run in parallel: {group}')
    alone = [g[0] for g in by_deps.values() if len(g) == 1]
    print('  sequential (unique dep set):', alone)

    # 6. Agent-level ordering within a stage
    print('\n[4] Agent-level ordering within each stage')
    for sid in ids:
        agents = stages[sid].get('ideal_flow', [])
        if len(agents) > 1:
            chain = ' -> '.join(agents)
            print(f'  {sid:<8} {chain}')

    print('\n[5] Problems')
    if problems:
        for p in problems:
            print('  !!', p)
    else:
        print('  none')

    print('\nTotal stages:', len(ids))


if __name__ == '__main__':
    main()
