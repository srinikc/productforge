import json
import os
import sys

PROJ = 'products/test-pipeline'
audit_path = os.path.join(PROJ, 'agent-audit-log.json')

def load(p):
    try:
        if os.path.exists(p):
            with open(p, 'r', encoding='utf-8-sig') as f:
                return json.load(f)
    except Exception:
        pass
    return []


def main():
    rows = load(audit_path)
    report = load(os.path.join(PROJ, 'pipeline-execution-report.json'))
    print("=" * 118)
    print("LIVE PIPELINE STATUS - test-pipeline")
    print("=" * 118)
    if not rows:
        print("(waiting for first agent to complete...)")
        return
    hdr = "%-7s %-16s %-18s %8s %8s %9s %9s %7s %6s" % (
        "stage", "agent", "model", "in", "out", "total", "cost$", "time_s", "trunc")
    print(hdr)
    print("-" * 118)
    ti = to = tt = 0
    tc = 0.0
    ttime = 0.0
    trunc = 0
    for r in rows:
        in_t = r.get('input_tokens', 0)
        out_t = r.get('output_tokens', 0)
        tot = r.get('total_tokens', 0)
        cost = r.get('cost', 0.0)
        tsec = r.get('duration_seconds', 0)
        tr = bool(r.get('truncated', False)) or out_t >= 16000
        ti += in_t; to += out_t; tt += tot; tc += cost; ttime += tsec
        trunc += 1 if tr else 0
        print("%-7s %-16s %-18s %8d %8d %9d %9.6f %7.1f %6s" % (
            r.get('stage_id', ''), r.get('agent_id', ''), r.get('model', ''),
            in_t, out_t, tot, cost, tsec, "Y" if tr else ""))
    print("-" * 118)
    print("%-42s %8d %8d %9d %9.6f %7.1f %6d" % ("TOTAL (%d agents)" % len(rows), ti, to, tt, tc, ttime, trunc))
    print()
    if report:
        print("phase=%s | iterations=%s | wall_clock=%.1fs | total_tokens=%s | total_cost=%.6f" % (
            report.get('phase'), report.get('iterations'),
            report.get('total_duration_seconds', 0) or 0,
            report.get('total_tokens'), report.get('total_cost', 0.0)))
    else:
        print("(no final report yet - run in progress)")


if __name__ == '__main__':
    main()
