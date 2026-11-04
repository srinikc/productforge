"""Validate EDP-22 SLO config, alert rules, and dashboard assets (offline)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQUIRED_GROUPS = {"db", "artifact", "memory", "job", "project", "run"}
REQUIRED_ALERTS = {
    "ProductForgeBenchmarkStale",
    "ProductForgeBenchmarkLatencyRegression",
    "ProductForgeStoreErrors",
    "ProductForgeStoreDegraded",
    "ProductForgeQuotaDenied",
}


def problems() -> list[str]:
    bad = []
    try:
        cfg = json.loads((ROOT / "config/edp-slo.json").read_text(encoding="utf-8"))
    except Exception as e:
        return [f"config/edp-slo.json invalid: {e}"]
    groups = cfg.get("groups") or {}
    missing = REQUIRED_GROUPS - set(groups)
    if missing:
        bad.append(f"missing SLO groups: {sorted(missing)}")
    for name, slo in groups.items():
        if float(slo.get("p99_ms", 0)) < float(slo.get("p95_ms", 0)):
            bad.append(f"{name}: p99 < p95")
    try:
        rules = (ROOT / "ops/prometheus/edp-slo.rules.yml").read_text(encoding="utf-8")
    except Exception as e:
        bad.append(f"rules missing: {e}")
        rules = ""
    for alert in REQUIRED_ALERTS:
        if f"alert: {alert}" not in rules:
            bad.append(f"missing alert: {alert}")
    try:
        dash = json.loads((ROOT / "ops/grafana/edp-slo-dashboard.json").read_text(encoding="utf-8"))
        if not dash.get("panels"):
            bad.append("dashboard has no panels")
    except Exception as e:
        bad.append(f"dashboard invalid: {e}")
    return bad


def main() -> int:
    bad = problems()
    print("edp-slo: " + ("OK" if not bad else "FAIL"))
    for b in bad:
        print("  - " + b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
