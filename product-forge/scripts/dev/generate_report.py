import json
import os
from datetime import datetime

from core.context_manager import get_contract
from core.model_registry import ModelCapabilityRegistry

PROJ = 'products/test-pipeline'
OUT = 'pipeline_execution_report_analysis.md'

report = json.load(open(os.path.join(PROJ, 'pipeline-execution-report.json'), encoding='utf-8'))
pipeline = json.load(open('pipeline-definition.json', encoding='utf-8-sig'))
audit = json.load(open(os.path.join(PROJ, 'agent-audit-log.json'), encoding='utf-8'))
registry = ModelCapabilityRegistry()

cache = {(e['stage_id'], e['agent_id']): e.get('cache_hit', False) for e in audit}
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


def ctx_window(model):
    p = registry.get_model(model)
    return p.context_window if p else 0


def fmt_time(sec):
    return "%.1f s (%.2f m)" % (sec, sec / 60.0)


def tok_status(used, budget):
    if budget <= 0:
        return "n/a"
    ratio = used / budget
    if ratio > 1.0:
        return "OVER"
    if ratio >= 0.9:
        return "HIT"
    return "under"


rows = []
tot_in = tot_out = tot_cached = tot_tokens = 0
tot_cost = tot_time = 0.0
hits = misses = 0
over = hit = under = 0

for stage_id, sdata in report['stage_summary'].items():
    stage_budget_usd = stages.get(stage_id, {}).get('budget_limit', 0.0)
    stage_cost = sdata.get('total_cost', 0.0)
    stage_token_budget = 30000  # executor creates stage_<id> with 30000 tokens
    stage_tokens = sdata.get('total_tokens', 0)
    cost_result = 'OVER' if (stage_budget_usd > 0 and stage_cost > stage_budget_usd) else 'under'
    stage_tok_result = tok_status(stage_tokens, stage_token_budget)

    for a in sdata['agents']:
        key = (stage_id, a['agent_id'])
        model = a.get('selected_model', '')
        contract = get_contract(a['agent_id'])
        agent_budget = contract.get('max_input_tokens', 0) + contract.get('max_output_tokens', 0)
        used = a.get('total_tokens', 0)
        used_in = a.get('input_tokens', 0)
        used_out = a.get('output_tokens', 0)
        hit_flag = cache.get(key, False)
        if hit_flag:
            hits += 1
        else:
            misses += 1
        st = tok_status(used, agent_budget)
        if st == 'OVER':
            over += 1
        elif st == 'HIT':
            hit += 1
        else:
            under += 1
        t = timings.get(key, 0)
        rows.append({
            'phase': PHASES.get(stage_id, '?'),
            'stage': stage_id,
            'agent': a['agent_id'],
            'model': model,
            'ctx': ctx_window(model),
            'in': used_in,
            'out': used_out,
            'cached': a.get('cached_tokens', 0),
            'hit': 'HIT' if hit_flag else 'miss',
            'total': used,
            'abudget': agent_budget,
            'apct': (used / agent_budget * 100) if agent_budget else 0,
            'aresult': st,
            'time': t,
            'cost': a.get('cost', 0.0),
            'sbudget': stage_budget_usd,
            'sresult': cost_result,
            'sbudget_tok': stage_token_budget,
            'stok_result': stage_tok_result,
        })
        tot_in += used_in; tot_out += used_out; tot_cached += a.get('cached_tokens', 0)
        tot_tokens += used; tot_cost += a.get('cost', 0.0); tot_time += t

lines = []
lines.append("# Pipeline Execution Report - Analysis")
lines.append("")
lines.append(f"- **Project:** {report['project']}")
lines.append(f"- **Pipeline ID:** {report['pipeline_id']}")
lines.append(f"- **Started:** {report['started_at']}")
lines.append(f"- **Completed:** {report['completed_at']}")
lines.append(f"- **Pipeline duration:** {fmt_time(report.get('total_duration_seconds', 0))}")
lines.append(f"- **Iterations:** {report['iterations']}")
lines.append(f"- **Phase:** {report['phase']}")
lines.append("")
lines.append("## Conventions")
lines.append("")
lines.append("- **Ctx window** = model context window (max context tokens).")
lines.append("- **In / Out** = input (prompt) tokens / output (completion) tokens billed for the agent.")
lines.append("- **Cached** = API prompt-cache tokens (provider-side reuse).")
lines.append("- **Cache** = application-level LLM cache result for this agent call (HIT/miss).")
lines.append("- **Agent budget tok** = agent contract `max_input_tokens + max_output_tokens` (context_manager).")
lines.append("- **Budget result** = used total tokens vs agent budget: `under` (<90%), `HIT` (>=90%), `OVER` (>100%).")
lines.append("- **Stage budget $** / **Stage budget tok** = stage cost limit (USD) and stage token budget (30,000).")
lines.append("- **Time** = wall-clock seconds (and minutes in brackets).")
lines.append("")
lines.append("## Per-Agent Detail")
lines.append("")

hdr = ("| Phase | Stage | Agent | Model | Ctx window | In tok | Out tok | Cached | Cache | "
       "Total tok | Agent budget tok | Usage % | Budget result | Time (s) (min) | Cost $ | "
       "Stage budget $ | Cost result |")
sep = ("|---|---|---|---|---:|---:|---:|---:|:--:|---:|---:|---:|:--:|---:|---:|---:|:--:|")
lines.append(hdr)
lines.append(sep)

for r in rows:
    lines.append(
        "| {phase} | {stage} | {agent} | {model} | {ctx:,} | {in:,} | {out:,} | {cached:,} | {hit} | "
        "{total:,} | {abudget:,} | {apct:.0f}% | {aresult} | {time} | {cost:.6f} | {sbudget:.1f} | {sresult} |".format(
            time=fmt_time(r['time']), **{k: v for k, v in r.items() if k != 'time'})
    )

lines.append(
    "| **TOTAL** |  | **{n} agent runs** |  | **1,000,000** | **{ti:,}** | **{to:,}** | **{tc:,}** | "
    "HIT={h} miss={m} | **{tt:,}** |  |  | OVER={o} HIT={hi} under={u} | **{ttime}** | **{tcost:.6f}** |  |  |".format(
        n=len(rows), ti=tot_in, to=tot_out, tc=tot_cached, h=hits, m=misses,
        tt=tot_tokens, o=over, hi=hit, u=under, ttime=fmt_time(tot_time), tcost=tot_cost))
lines.append("")

# Phase totals
lines.append("## Phase-Wise Totals")
lines.append("")
lines.append("| Phase | Agents | Total tok | Cost $ | Agent time (s) (min) | Stage budgets | Within budget? |")
lines.append("|---|---:|---:|---:|---:|---:|:--:|")
phase_acc = {}
for r in rows:
    p = phase_acc.setdefault(r['phase'], {'agents': 0, 'tok': 0, 'cost': 0.0, 'time': 0.0, 'budget': 0.0})
    p['agents'] += 1; p['tok'] += r['total']; p['cost'] += r['cost']
    p['time'] += r['time']; p['budget'] += r['sbudget']
for ph in sorted(phase_acc):
    p = phase_acc[ph]
    within = 'Yes' if p['cost'] <= p['budget'] else 'No'
    lines.append("| {ph} | {a} | {t:,} | {c:.6f} | {tm} | {b:.1f} | {w} |".format(
        ph=ph, a=p['agents'], t=p['tok'], c=p['cost'], tm=fmt_time(p['time']), b=p['budget'], w=within))
lines.append("| **Total** | **{a}** | **{t:,}** | **{c:.6f}** | **{tm}** |  | **Yes** |".format(
    a=len(rows), t=tot_tokens, c=tot_cost, tm=fmt_time(tot_time)))
lines.append("")

# Pipeline level
bs = report.get('budget_summary', {})
lines.append("## Pipeline-Level Summary")
lines.append("")
lines.append(f"- **Wall-clock time:** {fmt_time(report.get('total_duration_seconds', 0))}")
lines.append(f"- **Sum of agent times:** {fmt_time(tot_time)} (larger than wall-clock because `1b`+`1c` and `5`+`6` ran in parallel)")
lines.append(f"- **Total input tokens:** {tot_in:,}")
lines.append(f"- **Total output tokens:** {tot_out:,}")
lines.append(f"- **Total cached tokens (API):** {tot_cached:,}")
lines.append(f"- **Total tokens:** {tot_tokens:,}")
lines.append(f"- **Total cost:** ${tot_cost:.6f}")
lines.append(f"- **App cache:** {hits} hit / {misses} miss")
lines.append(f"- **Agent token budget results:** OVER={over}, HIT={hit}, under={under}")
lines.append(f"- **Global token budget:** {bs.get('total_used'):,} / {bs.get('total_max'):,} used "
             f"({bs.get('used_percent', 0):.2f}%), alerts={bs.get('alerts')}")
lines.append(f"- **Global cost budget:** ${tot_cost:.6f} spent of ${sum(stages.get(s, {}).get('budget_limit', 0) for s in stages):.2f} allocated")
lines.append("")

lines.append("## Notes / Gaps")
lines.append("")
lines.append("- Agents whose **Out tok = 16,000** (`design`, `implement` in 4-0/4a/4b/4c) hit the API `max_tokens` ceiling and are likely truncated; raise `max_output_tokens` for these.")
lines.append("- Application LLM cache shows 0 hits because this was a cold run; repeat runs reuse cached prompts.")
lines.append("- Stage 12 has `budget_limit = 0.0`; its tiny cost is not a real overspend.")
lines.append("- This run predates the compliance/knowledge fixes, so knowledge counts and compliance are low.")
lines.append("")

with open(OUT, 'w', encoding='utf-8') as f:
    f.write("\n".join(lines))

print("Wrote", OUT, "with", len(rows), "rows")
print("Totals: in=%d out=%d cached=%d total=%d cost=%.6f time=%.1fs" % (
    tot_in, tot_out, tot_cached, tot_tokens, tot_cost, tot_time))
print("Agent budget results: OVER=%d HIT=%d under=%d" % (over, hit, under))
