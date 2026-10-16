"""Per-store review of config/derived stores (BI-PF-1415).

Replaces the kind heuristic with a scope-aware decision recorded on each store's ``target``:
  - config  + global          -> file    (global authored config, git-reviewed)
  - config  + project/tenant  -> table   (project/tenant settings -> a DB table)
  - derived + global          -> derived (regenerated global projection)
  - derived + project/tenant  -> view    (project data projection -> a DB view over base tables)

Writes ``config/store-registry.json`` (its owner). Run from product-forge/.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REG = ROOT / "config" / "store-registry.json"


def decide(kind: str, scope: str) -> tuple[str, str, str, str]:
    scoped = ("project" in scope) or ("tenant" in scope)
    if kind == "config":
        if scoped:
            return "table", "tool_settings", "exists", "project/tenant-scoped config -> DB settings table"
        return "file", "", "retained", "global authored config -> file (git-reviewed)"
    if kind == "derived":
        if scoped:
            return "view", "", "planned", "project/tenant-scoped derived -> DB view over base tables"
        return "derived", "", "retained", "global generated projection -> regenerated file"
    return kind, "", "retained", "unchanged"


def main() -> int:
    d = json.loads(REG.read_text(encoding="utf-8"))
    counts: Counter = Counter()
    for name, v in d["stores"].items():
        if not isinstance(v, dict):
            continue
        kind = str(v.get("kind", "?"))
        if kind not in ("config", "derived"):
            continue
        k, ref, status, reason = decide(kind, str(v.get("scope", "")))
        t = {"kind": k, "status": status, "reason": reason}
        if ref:
            t["ref"] = ref
        v["target"] = t
        counts[k] += 1
    REG.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")
    print("store-registry-review: " + ", ".join(f"{k}={c}" for k, c in sorted(counts.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
