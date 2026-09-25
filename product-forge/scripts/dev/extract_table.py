import json
import os

PROJ = 'products/test-pipeline'
report = json.load(open(os.path.join(PROJ, 'pipeline-execution-report.json'), encoding='utf-8'))
pipeline = json.load(open('pipeline-definition.json', encoding='utf-8-sig'))
audit = json.load(open(os.path.join(PROJ, 'agent-audit-log.json'), encoding='utf-8'))

# cache_hit lookup by (stage, agent)
cache = {(e['stage_id'], e['agent_id']): e.get('cache_hit', False) for e in audit}

# timing lookup by (stage, agent)
timings = {}
for t in report.get('timings', {}).get('agents', []):
    timings[(t['stage_id'], t['agent_id'])] = t.get('duration_seconds', 0)

PHASES = {
    '0': '1-Ideation', '0a': '1-Ideation',
    '1': '2-Design', '1a': '2-Design', '1b': '2-Design', '1c': '2-Design',
    '2': '3-Architecture', '3': '3-Architecture',
    '4-0': '4-Implementation', '4a': '4-Implementation', '4a-vqa': '4-Implementation',
    '4b': '4-Implementation', '4b-vqa': '4-Implementation',
    '4c': '4-Implementation', '4c-vqa': '4-Implementation',
    '5': '5-Verification', '6': '5-Verification', '7': '5-Verification',
    '8': '6-Delivery', '9': '6-Delivery', '10': '6-Delivery',
    '11': '6-Delivery', '12': '6-Delivery',
}

stages = pipeline['stages']
rows = []
tot_in = tot_out = tot_cached = tot_tokens = 0
tot_cost = tot_time = 0.0
hits = misses = 0

for stage_id, sdata in report['stage_summary'].items():
    budget = stages.get(stage_id, {}).get('budget_limit', 0.0)
    stage_cost = sdata.get('total_cost', 0.0)
    status = 'OVER' if stage_cost > budget else 'under'
    for a in sdata['agents']:
        key = (stage_id, a['agent_id'])
        hit = cache.get(key, False)
        if hit:
            hits += 1
        else:
            misses += 1
        t = timings.get(key, 0)
        row = {
            'phase': PHASES.get(stage_id, '?'),
            'stage': stage_id,
            'agent': a['agent_id'],
            'model': a.get('selected_model', ''),
            'in': a.get('input_tokens', 0),
            'out': a.get('output_tokens', 0),
            'cached': a.get('cached_tokens', 0),
            'hit': 'HIT' if hit else 'miss',
            'total': a.get('total_tokens', 0),
            'cost': a.get('cost', 0.0),
            'time': t,
            'budget': budget,
            'status': status,
        }
        rows.append(row)
        tot_in += row['in']; tot_out += row['out']; tot_cached += row['cached']
        tot_tokens += row['total']; tot_cost += row['cost']; tot_time += row['time']

# Print markdown table
hdr = ("| Phase | Stage | Agent | Model | In | Out | Cached | Cache | Total tok | Cost $ | Time s | Budget $ | Status |")
sep = ("|---|---|---|---|---:|---:|---:|:--:|---:|---:|---:|---:|:--:|")
print(hdr)
print(sep)
for r in rows:
    print("| {phase} | {stage} | {agent} | {model} | {in} | {out} | {cached} | {hit} | {total} | {cost:.6f} | {time:.1f} | {budget:.1f} | {status} |".format(**r))
print("| **TOTAL** |  | **{} agents** |  | **{}** | **{}** | **{}** | HIT={} miss={} | **{}** | **{:.6f}** | **{:.1f}** |  |  |".format(
    len(rows), tot_in, tot_out, tot_cached, hits, misses, tot_tokens, tot_cost, tot_time))

print()
print("PIPELINE: %s -> %s | wall-clock %ss (%.2f min)" % (
    report['started_at'], report['completed_at'],
    round(report.get('total_duration_seconds', 0), 1),
    report.get('total_duration_seconds', 0) / 60.0))
bs = report.get('budget_summary', {})
print("BUDGET (global token budget): used=%s max=%s (%.1f%%), alerts=%s" % (
    bs.get('total_used'), bs.get('total_max'), bs.get('used_percent', 0), bs.get('alerts')))
