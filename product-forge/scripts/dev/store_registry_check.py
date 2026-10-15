"""Store-registry completeness gate (BI-PF-1408 / BI-PF-1409).

FAILS if any store in ``config/store-registry.json`` lacks a ``classification`` carrying the required keys
(``sensitivity, tenant_scope, backend, retention, recovery_tier, migration_status``). This is the
"completeness gate" EDP-02 promised and never built, so the discovery can never again be closed half-done.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REG = ROOT / "config" / "store-registry.json"
REQUIRED = ("sensitivity", "tenant_scope", "backend", "retention", "recovery_tier", "migration_status")


def main() -> int:
    d = json.loads(REG.read_text(encoding="utf-8"))
    stores = d.get("stores") or {}
    bad: list[str] = []
    for name, v in stores.items():
        cls = (v or {}).get("classification") if isinstance(v, dict) else None
        if not isinstance(cls, dict) or any(k not in cls for k in REQUIRED):
            bad.append(name)
    if bad:
        print(f"store-registry: FAIL ({len(bad)}/{len(stores)} stores missing a complete classification)")
        for n in bad[:15]:
            print(f"   {n}")
        return 1
    print(f"store-registry: OK ({len(stores)} stores classified)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
