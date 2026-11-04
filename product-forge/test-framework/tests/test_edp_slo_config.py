import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_slo_config_has_bounded_groups_and_positive_limits():
    cfg = json.loads((ROOT / "config/edp-slo.json").read_text(encoding="utf-8"))
    assert cfg["version"] >= 1
    assert cfg["defaults"]["p95_ms"] > 0
    assert cfg["defaults"]["p99_ms"] >= cfg["defaults"]["p95_ms"]
    allowed = {"db", "object", "artifact", "memory", "job", "project", "run", "cache", "queue"}
    assert set(cfg["groups"]) <= allowed
    for name, slo in cfg["groups"].items():
        assert slo["p95_ms"] > 0 and slo["p99_ms"] >= slo["p95_ms"], name


def test_slo_assets_exist():
    for rel in ("ops/prometheus/edp-slo.rules.yml", "ops/grafana/edp-slo-dashboard.json"):
        assert (ROOT / rel).is_file(), rel
