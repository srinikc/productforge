"""Generate EDP-22 Prometheus rules from config; --check enforces drift."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RULES = ROOT / "ops/prometheus/edp-slo.rules.yml"


def _alert_suffix(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", name.title())


def render() -> str:
    cfg = json.loads((ROOT / "config/edp-slo.json").read_text(encoding="utf-8"))
    lines = [
        "groups:",
        "  - name: product-forge-edp-slo",
        "    rules:",
        "      - alert: ProductForgeBenchmarkStale",
        "        expr: absent(edp_bench_last_run_unixtime) or time() - edp_bench_last_run_unixtime > 86400",
        "        for: 30m",
        "        labels:",
        "          severity: ticket",
        "          owner: platform-oncall",
        "          service: edpsvc",
        "        annotations:",
        '          summary: "EDP benchmark baseline is stale or missing"',
        '          runbook: "docs/EDP-22-RUNBOOK.md"',
    ]
    for group in sorted(cfg.get("groups") or {}):
        slo = cfg["groups"][group]
        suffix = _alert_suffix(group)
        lines += [
            f"      - alert: ProductForgeBenchmarkP95{suffix}",
            f'        expr: max by (scenario) (edp_bench_p95_ms{{group="{group}"}}) > {slo["p95_ms"]}',
            "        for: 10m",
            "        labels:",
            "          severity: ticket",
            "          owner: platform-oncall",
            "          service: edpsvc",
            "        annotations:",
            f'          summary: "EDP {group} benchmark p95 exceeded {slo["p95_ms"]}ms"',
            '          runbook: "docs/EDP-22-RUNBOOK.md"',
            f"      - alert: ProductForgeBenchmarkP99{suffix}",
            f'        expr: max by (scenario) (edp_bench_p99_ms{{group="{group}"}}) > {slo["p99_ms"]}',
            "        for: 10m",
            "        labels:",
            "          severity: ticket",
            "          owner: platform-oncall",
            "          service: edpsvc",
            "        annotations:",
            f'          summary: "EDP {group} benchmark p99 exceeded {slo["p99_ms"]}ms"',
            '          runbook: "docs/EDP-22-RUNBOOK.md"',
        ]
    lines += [
        "      - alert: ProductForgeStoreErrors",
        '        expr: sum by (store) (rate(edp_store_requests_total{outcome="error"}[10m])) > 0.05',
        "        for: 10m",
        "        labels:",
        "          severity: page",
        "          owner: platform-oncall",
        "          service: edpsvc",
        "        annotations:",
        '          summary: "EDP store error rate elevated"',
        '          runbook: "docs/EDP-22-RUNBOOK.md"',
        "      - alert: ProductForgeStoreDegraded",
        "        expr: max by (store) (edp_store_degraded) > 0",
        "        for: 1m",
        "        labels:",
        "          severity: page",
        "          owner: platform-oncall",
        "          service: edpsvc",
        "        annotations:",
        '          summary: "EDP store is in degraded mode"',
        '          runbook: "docs/EDP-22-RUNBOOK.md"',
        "      - alert: ProductForgeQuotaDenied",
        "        expr: sum by (store, scope) (rate(edp_quota_denials_total[10m])) > 0.1",
        "        for: 10m",
        "        labels:",
        "          severity: ticket",
        "          owner: platform-oncall",
        "          service: edpsvc",
        "        annotations:",
        '          summary: "EDP quota denials elevated"',
        '          runbook: "docs/EDP-22-RUNBOOK.md"',
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    want = render()
    if a.check:
        got = RULES.read_text(encoding="utf-8") if RULES.is_file() else ""
        if got != want:
            print("gen-edp-slo: STALE - run python scripts/dev/gen_edp_slo.py")
            return 1
        print("gen-edp-slo: OK")
        return 0
    RULES.write_text(want, encoding="utf-8")
    print(f"gen-edp-slo: wrote {RULES.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
