"""Store-registry classification (BI-PF-1408, Slice A).

Populate a per-store ``classification`` on EVERY entry of ``config/store-registry.json`` from the documented
``classification_defaults`` plus a kind-based backend policy, so each store declares
``sensitivity / tenant_scope / backend / retention / recovery_tier / migration_status`` (the discovery was
registered but never classified).

Backend policy: config/derived stores stay files (retained); work-items migrate to Postgres (BI-PF-1399);
object-payload kinds use the object store; other runtime kinds are Postgres candidates.

Tooling (``scripts/``) writes the registry. ``--apply`` writes; default is a dry-run summary.

Usage: python scripts/dev/store_registry_classify.py [--apply]
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REG = ROOT / "config" / "store-registry.json"

FILE_KINDS = {"config", "derived"}
POLICY: dict[str, tuple[str, str]] = {
    "work-items": ("postgres", "pending"),
    "evidence": ("object-store", "pending"),
    "intake-raw": ("object-store", "pending"),
    "knowledge-base": ("postgres", "pending"),
    "audit": ("postgres", "pending"),
    "control": ("postgres", "pending"),
    "scheduling": ("postgres", "pending"),
    "execution": ("postgres", "pending"),
    "builds": ("object-store", "pending"),
}


def backend_for(kind: str) -> tuple[str, str]:
    if kind in FILE_KINDS:
        return "file", "retained"
    return POLICY.get(kind, ("postgres", "pending"))


def _tenant_scope(scope: str) -> str:
    s = str(scope or "")
    if s in ("global",):
        return "global"
    return "tenant"


def main(argv: list[str]) -> int:
    apply_ = "--apply" in argv
    d = json.loads(REG.read_text(encoding="utf-8"))
    defaults = d.get("classification_defaults") or {}
    counts: Counter = Counter()
    for v in d["stores"].values():
        if not isinstance(v, dict):
            continue
        kind = str(v.get("kind", "?"))
        be, ms = backend_for(kind)
        cls = dict(defaults)
        cls.update({"backend": be, "migration_status": ms,
                    "tenant_scope": _tenant_scope(v.get("scope", ""))})
        v["classification"] = cls
        counts[be] += 1
    n = sum(counts.values())
    print(f"store-registry-classify: {n} stores -> " + ", ".join(f"{k}={c}" for k, c in sorted(counts.items())))
    if apply_:
        REG.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {REG}")
    else:
        print("(dry-run; pass --apply to write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
