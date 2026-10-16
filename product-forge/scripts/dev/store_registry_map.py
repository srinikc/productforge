"""Store -> DB target mapping (BI-PF-1408, Slice B - domain-reviewed).

For every store, records a ``target`` = where its data lives after EDP migration. The decision is made PER
DOMAIN (kind), then applied to each store of that kind:
  kind -> (kind, ref, status, owner_item)
    kind      : table | file | derived | object-store
    ref       : the table/entity (or object store) it maps to
    status    : exists | planned
    owner_item: the backlog item that will create the table (for planned), else ""

config/derived stay files (retained). Runtime domains map to the canonical schema; where the table does not
yet exist it is ``planned`` with its owning EDP item (EDP-15/18/19/20/21). Tooling (``scripts/``) writes the
registry. ``--apply`` writes; default is a dry-run summary.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REG = ROOT / "config" / "store-registry.json"

DOMAIN_MAP: dict[str, tuple[str, str, str, str]] = {
    # file-retained
    "config": ("file", "", "retained", ""),
    "derived": ("derived", "", "retained", ""),
    # system of record (Postgres) - existing core tables
    "execution": ("table", "runs", "exists", "BI-PF-1309"),
    # planned tables, each with its owning EDP item
    "work-items": ("table", "backlog_items", "planned", "BI-PF-1399"),
    "audit": ("table", "audit", "planned", "BI-PF-1312"),
    "knowledge-base": ("table", "memory", "planned", "BI-PF-1313"),
    "scheduling": ("table", "jobs", "planned", "BI-PF-1311"),
    "control": ("table", "control_state", "planned", "BI-PF-1292"),
    "state": ("table", "state", "planned", "BI-PF-1292"),
    "tool-settings": ("table", "tool_settings", "planned", "BI-PF-1292"),
    "tool-secrets": ("table", "secrets", "planned", "BI-PF-1292"),
    "decomposition": ("table", "decomposition", "planned", "BI-PF-1292"),
    "product-registry": ("table", "products", "planned", "BI-PF-1292"),
    "provider-registry": ("table", "providers", "planned", "BI-PF-1292"),
    "traceability-matrix": ("table", "traceability", "planned", "BI-PF-1292"),
    "problems": ("table", "problems", "planned", "BI-PF-1292"),
    "insights": ("table", "insights", "planned", "BI-PF-1292"),
    "registry": ("table", "registries", "planned", "BI-PF-1292"),
    "data": ("table", "data", "planned", "BI-PF-1292"),
    "ledger": ("table", "ledger", "planned", "BI-PF-1292"),
    "allocation-registry": ("table", "allocations", "planned", "BI-PF-1292"),
    # object payloads
    "evidence": ("object-store", "artifacts", "planned", "BI-PF-1307"),
    "intake-raw": ("object-store", "intake", "planned", "BI-PF-1292"),
    "builds": ("object-store", "builds", "planned", "BI-PF-1292"),
}


def target_for(kind: str) -> dict:
    k, ref, status, owner = DOMAIN_MAP.get(kind, ("table", kind or "unknown", "planned", "BI-PF-1292"))
    t = {"kind": k, "status": status}
    if ref:
        t["ref"] = ref
    if owner:
        t["owner_item"] = owner
    return t


def main(argv: list[str]) -> int:
    apply_ = "--apply" in argv
    d = json.loads(REG.read_text(encoding="utf-8"))
    counts: Counter = Counter()
    for v in d["stores"].values():
        if not isinstance(v, dict):
            continue
        t = target_for(str(v.get("kind", "?")))
        v["target"] = t
        counts[t["kind"]] += 1
    n = sum(counts.values())
    print(f"store-registry-map: {n} stores -> " + ", ".join(f"{k}={c}" for k, c in sorted(counts.items())))
    if apply_:
        REG.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {REG}")
    else:
        print("(dry-run; pass --apply to write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
