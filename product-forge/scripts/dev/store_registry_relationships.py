"""Store -> DB relationships + migration status (BI-PF-1408, Slice C).

Slice A classified every store, Slice B mapped it to a target. Slice C records the table relationships the
targets participate in and keeps ``migration_status`` honest against the schema that actually exists.

Rules enforced (fail-closed):
  * every ``target.kind == "table"`` + ``status == "exists"`` names a table created by a migration;
  * a ``planned`` target whose owner item is already completed is stale (flip it or fix the owner);
  * ``migration_status`` must agree with the target (migrated | retained | pending);
  * every declared relationship references known tables and a real child column;
  * the canonical tenancy/FK edges below are present (they are the discovery's acceptance set).

Usage:
  python scripts/dev/store_registry_relationships.py            # check (gate)
  python scripts/dev/store_registry_relationships.py --apply    # record relationships + statuses
  python scripts/dev/store_registry_relationships.py --registry <path>   # check an alternate registry
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REG = ROOT / "config" / "store-registry.json"
ITEMS = ROOT / "data" / "backlog" / "items"

# (child table, parent table, child column, kind, note)
RELATIONSHIPS = [
    ("memberships", "tenants", "tenant_id", "fk", "membership belongs to a tenant"),
    ("projects", "tenants", "tenant_id", "fk", "project belongs to a tenant"),
    ("runs", "tenants", "tenant_id", "fk", "run is tenant-scoped"),
    ("runs", "projects", "project_id", "fk", "run belongs to a project"),
    ("stages", "runs", "run_id", "fk", "stage belongs to a run"),
    ("attempts", "stages", "stage_id", "fk", "attempt belongs to a stage"),
    ("artifacts", "tenants", "tenant_id", "fk", "artifact is tenant-scoped"),
    ("artifacts", "projects", "project_id", "fk", "artifact belongs to a project"),
    ("artifacts", "runs", "run_id", "fk", "artifact is produced by a run"),
    ("jobs", "tenants", "tenant_id", "fk", "job is tenant-scoped"),
    ("outbox", "tenants", "tenant_id", "fk", "outbox message is tenant-scoped"),
    ("backlog_items", "tenants", "tenant_id", "fk", "work item is tenant-scoped"),
    ("memory", "tenants", "tenant_id", "fk", "memory record is tenant-scoped"),
    ("memory", "projects", "project_id", "fk", "memory record belongs to a project"),
    ("memory", "stored_objects", "object_ref", "object-ref", "payload lives in the object store"),
    ("audit", "tenants", "tenant_id", "logical", "audit rows carry the tenant id (no FK by design)"),
]
REQUIRED = {(c, p, col) for c, p, col, _, _ in RELATIONSHIPS}
# Schema objects the discovery claims exist (audit domain): the gate fails if a migration loses them.
REQUIRED_TRIGGERS = (
    "audit_partitioned_append_only",
    "audit_partition_config_touch",
    "audit_legal_hold_guard",
    "audit_partitioned_no_truncate",
)
DONE = {"completed", "closed", "done"}


def _trigger_names() -> set[str]:
    names: set[str] = set()
    for f in sorted(glob.glob(str(ROOT / "migrations" / "*.up.sql"))):
        s = Path(f).read_text(encoding="utf-8", errors="replace")
        names.update(m.group(1).lower() for m in re.finditer(r"CREATE TRIGGER\s+\"?([a-z_][a-z0-9_]*)\"?", s, re.I))
    return names


def _tables() -> tuple[set[str], dict[str, set[str]]]:
    """Parse migrations for created tables and their columns (best effort, case-insensitive)."""
    tables: dict[str, set[str]] = {}
    for f in sorted(glob.glob(str(ROOT / "migrations" / "*.up.sql"))):
        s = Path(f).read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(
                r"CREATE TABLE (?:IF NOT EXISTS )?(?:public\.)?\"?([a-z_][a-z0-9_]*)\"?\s*\((.*?)\);", s, re.I | re.S):
            name = m.group(1).lower()
            if name == "public":
                continue
            cols = set(c.lower() for c in re.findall(r"^\s*([a-z_][a-z0-9_]*)\s+", m.group(2), re.M))
            tables.setdefault(name, set()).update(cols)
    return set(tables), tables


def _item_status(owner: str) -> str:
    p = ITEMS / f"{owner}.json"
    try:
        return str(json.loads(p.read_text(encoding="utf-8")).get("status") or "").lower()
    except FileNotFoundError:
        return ""
    except Exception:
        return "unknown"


def _expected_status(target: dict) -> str:
    st = str(target.get("status") or "")
    kind = str(target.get("kind") or "")
    if st == "retained":
        return "retained"
    if st == "planned":
        return "pending"
    if st == "exists":
        return "migrated" if kind in {"table", "object-store"} else "retained"
    return "pending"


def _record(reg: dict, tables: set[str], table_cols: dict[str, set[str]]) -> list[dict]:
    rels = []
    for child, parent, col, kind, note in RELATIONSHIPS:
        rels.append({
            "from": child, "to": parent, "via": col, "kind": kind,
            "note": note, "owner_item": "BI-PF-1309",
            "verified": child in tables and parent in tables and col in table_cols.get(child, set()),
        })
    return rels


def apply(reg: dict, tables: set[str], table_cols: dict[str, set[str]]) -> dict:
    reg["relationships"] = _record(reg, tables, table_cols)
    for v in (reg.get("stores") or {}).values():
        tgt = v.get("target") or {}
        # Discovery follows delivery: a planned target whose owner item is done and whose table now exists
        # is recorded as exists (no longer planned).
        if tgt.get("status") == "planned":
            owner = str(tgt.get("owner_item") or "")
            ref = str(tgt.get("ref") or "")
            kind = str(tgt.get("kind") or "")
            if owner and _item_status(owner) in DONE and (ref in tables or (kind == "object-store" and ref in tables)):
                tgt["status"] = "exists"
        cls = v.setdefault("classification", {})
        cls["migration_status"] = _expected_status(tgt)
    return reg


def check(reg: dict, tables: set[str], table_cols: dict[str, set[str]]) -> list[str]:
    bad: list[str] = []
    stores = reg.get("stores") or {}
    for name, v in stores.items():
        tgt = (v or {}).get("target") or {}
        kind, ref, st = str(tgt.get("kind") or ""), str(tgt.get("ref") or ""), str(tgt.get("status") or "")
        if kind == "table" and st == "exists" and ref not in tables:
            bad.append(f"{name}: target table {ref!r} is not created by any migration")
        if st == "planned":
            owner = str(tgt.get("owner_item") or "")
            if owner and _item_status(owner) in DONE:
                bad.append(f"{name}: planned under completed {owner} - flip to exists or fix the owner")
        want = _expected_status(tgt)
        have = str((v.get("classification") or {}).get("migration_status") or "")
        if have != want:
            bad.append(f"{name}: migration_status={have!r}, expected {want!r}")
    rels = reg.get("relationships") or []
    if not rels:
        return bad + ["relationships: missing (run --apply)"]
    seen = set()
    for r in rels:
        child, parent = str(r.get("from") or ""), str(r.get("to") or "")
        col, kind = str(r.get("via") or ""), str(r.get("kind") or "")
        key = (child, parent, col)
        if key in seen:
            bad.append(f"relationship duplicate: {child}.{col} -> {parent}")
        seen.add(key)
        if kind not in {"fk", "logical", "object-ref"}:
            bad.append(f"relationship {child}.{col} -> {parent}: unknown kind {kind!r}")
        if child not in tables:
            bad.append(f"relationship child table {child!r} does not exist")
        if parent not in tables:
            bad.append(f"relationship parent table {parent!r} does not exist")
        if child in tables and col not in table_cols.get(child, set()):
            bad.append(f"relationship {child}.{col}: column not found in the migration")
        if r.get("verified") is not True:
            bad.append(f"relationship {child}.{col} -> {parent}: not marked verified")
    for t in REQUIRED_TRIGGERS:
        if t not in _trigger_names():
            bad.append(f"required trigger missing from migrations: {t}")
    missing = REQUIRED - {(str(r.get("from")), str(r.get("to")), str(r.get("via"))) for r in rels}
    for c, p, col in sorted(missing):
        bad.append(f"required relationship missing: {c}.{col} -> {p}")
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write relationships + migration_status")
    ap.add_argument("--registry", default=str(REG))
    a = ap.parse_args(argv)
    path = Path(a.registry)
    reg = json.loads(path.read_text(encoding="utf-8"))
    tables, table_cols = _tables()
    if a.apply:
        reg = apply(reg, tables, table_cols)
        path.write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    bad = check(reg, tables, table_cols)
    counts = {"migrated": 0, "retained": 0, "pending": 0}
    for v in (reg.get("stores") or {}).values():
        s = str(((v or {}).get("classification") or {}).get("migration_status") or "")
        if s in counts:
            counts[s] += 1
    if bad:
        print(f"store-relationships: FAIL ({len(bad)} problem(s))")
        for b in bad[:20]:
            print("   " + b)
        return 1
    print(f"store-relationships: OK ({len(reg.get('stores') or {})} stores; "
          f"{len(reg.get('relationships') or [])} relationships; "
          f"migrated={counts['migrated']} retained={counts['retained']} pending={counts['pending']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
