"""EDP-02 (BI-PF-1294): every registered store carries a data classification."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.paths import ROOT  # noqa: E402

KEYS = ("sensitivity", "tenant_scope", "backend", "retention", "recovery_tier", "migration_status")


def _registry():
    with open(os.path.join(str(ROOT), "config", "store-registry.json"), encoding="utf-8") as f:
        return json.load(f)


def test_classification_defaults_complete():
    defaults = _registry().get("classification_defaults") or {}
    missing = [k for k in KEYS if k not in defaults]
    assert not missing, f"classification_defaults missing: {missing}"


def test_every_store_resolves_all_classification_keys():
    reg = _registry()
    defaults = reg.get("classification_defaults") or {}
    bad = []
    for name, meta in (reg.get("stores") or {}).items():
        eff = dict(defaults)
        eff.update((meta or {}).get("classification") or {})
        if any(k not in eff for k in KEYS):
            bad.append(name)
    assert not bad, f"stores missing classification: {bad[:20]}"
