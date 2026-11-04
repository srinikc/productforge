import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_degradation_config_is_bounded():
    cfg = json.loads((ROOT / "config/edp-degradation.json").read_text(encoding="utf-8"))
    assert cfg["version"] >= 1
    assert 0 < cfg["max_duration_seconds"] <= 900
    allowed = {"db", "object", "cache", "queue"}
    assert set(cfg["stores"]) <= allowed
    for store, rule in cfg["stores"].items():
        if rule.get("enabled"):
            assert rule.get("reason") and rule.get("owner") and rule.get("expires_at"), store
