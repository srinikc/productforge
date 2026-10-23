"""Store -> DB relationships + migration status (BI-PF-1408, Slice C).

Slice A classified every store, Slice B mapped it to a target. Slice C records the table relationships the
targets participate in and keeps ``migration_status`` honest against the schema that actually exists.

The registry is the single source of truth: ``--apply`` only seeds relationships when they are absent,
recomputes their column existence and reconciles statuses/flips delivered targets. ``check`` fails closed on:
  * an ``exists`` target without its migration table (tables) or metadata table + object backend;
  * a ``planned`` target whose owner item is already completed (stale discovery);
  * ``migration_status`` or backend/kind disagreeing with the target;
  * a relationship whose tables/column are missing, a duplicate, or a missing canonical edge;
  * a required audit trigger missing from the migrations.

Usage:
  python scripts/dev/store_registry_relationships.py              # gate
  python scripts/dev/store_registry_relationships.py --apply      # record/reconcile
  python scripts/dev/store_registry_relationships.py --self-test  # gate + negative tests (CI)
  python scripts/dev/store_registry_relationships.py --registry <path> --verbose
"""
from __future__ import annotations

import argparse
import copy
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REG = ROOT / "config" / "store-registry.json"
ITEMS = ROOT / "data" / "backlog" / "items"

# Seed used only when the registry has no relationships yet: (child, parent, child column, kind, owner, note)
SEED = [
    ("memberships", "tenants", "tenant_id", "fk", "BI-PF-1309", "membership belongs to a tenant"),
    ("projects", "tenants", "tenant_id", "fk", "BI-PF-1309", "project belongs to a tenant"),
    ("runs", "tenants", "tenant_id", "fk", "BI-PF-1309", "run is tenant-scoped"),
    ("runs", "projects", "project_id", "fk", "BI-PF-1309", "run belongs to a project"),
    ("stages", "runs", "run_id", "fk", "BI-PF-1309", "stage belongs to a run"),
    ("attempts", "stages", "stage_id", "fk", "BI-PF-1309", "attempt belongs to a stage"),
    ("artifacts", "tenants", "tenant_id", "fk", "BI-PF-1307", "artifact is tenant-scoped"),
    ("artifacts", "projects", "project_id", "fk", "BI-PF-1307", "artifact belongs to a project"),
    ("artifacts", "runs", "run_id", "fk", "BI-PF-1307", "artifact is produced by a run"),
    ("jobs", "tenants", "tenant_id", "fk", "BI-PF-1311", "job is tenant-scoped"),
    ("outbox", "tenants", "tenant_id", "fk", "BI-PF-1311", "outbox message is tenant-scoped"),
    ("backlog_items", "tenants", "tenant_id", "fk", "BI-PF-1399", "work item is tenant-scoped"),
    ("memory", "tenants", "tenant_id", "fk", "BI-PF-1313", "memory record is tenant-scoped"),
    ("memory", "projects", "project_id", "fk", "BI-PF-1313", "memory record belongs to a project"),
    ("memory", "stored_objects", "object_ref", "object-ref", "BI-PF-1313", "payload lives in the object store"),
    ("audit", "tenants", "tenant_id", "logical", "BI-PF-1312", "audit rows carry the tenant id (no FK by design)"),
]
REQUIRED = {(c, p, col) for c, p, col, _, _, _ in SEED}
REQUIRED_TRIGGERS = (
    "audit_partitioned_append_only",
    "audit_partition_config_touch",
    "audit_legal_hold_guard",
    "audit_partitioned_no_truncate",
)
DONE = {"completed", "closed", "done"}
OBJECT_META = {"artifacts", "stored_objects"}


def _sql_files() -> list[Path]:
    return [Path(f) for f in sorted(glob.glob(str(ROOT / "migrations" / "*.up.sql")))]


def _statements_after(sql: str, head: re.Pattern) -> list[tuple[re.Match, str]]:
    """Yield (match, balanced parenthesised body) for each head match, ignoring nested parens in bodies."""
    out = []
    for m in head.finditer(sql):
        start = sql.find("(", m.start())
        if start < 0:
            continue
        depth, i, quote = 0, start, ""
        while i < len(sql):
            ch = sql[i]
            if quote:
                if ch == quote:
                    quote = ""
            elif ch in "'\"":
                quote = ch
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        out.append((m, sql[start + 1:i]))
    return out


def _schema() -> tuple[set[str], dict[str, set[str]], set[str]]:
    tables: dict[str, set[str]] = {}
    triggers: set[str] = set()
    head = re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:public\.)?\"?([a-z_][a-z0-9_]*)\"?\s*\(",
                      re.I)
    for f in _sql_files():
        s = f.read_text(encoding="utf-8", errors="replace")
        for m, body in _statements_after(s, head):
            name = m.group(1).lower()
            if name == "public":
                continue
            cols = set(c.lower() for c in re.findall(r"^\s*\"?([a-z_][a-z0-9_]*)\"?\s+[a-z]", body, re.M | re.I))
            tables.setdefault(name, set()).update(cols)
        triggers.update(t.group(1).lower() for t in re.finditer(r"CREATE\s+TRIGGER\s+\"?([a-z_][a-z0-9_]*)\"?", s, re.I))
    return set(tables), tables, triggers


def _item_status(owner: str) -> str:
    try:
        return str(json.loads((ITEMS / f"{owner}.json").read_text(encoding="utf-8")).get("status") or "").lower()
    except Exception:
        return ""


def _expected_status(target: dict, backend: str = "") -> str:
    """migration_status describes where the DATA lives, not whether a table exists."""
    st, kind = str(target.get("status") or ""), str(target.get("kind") or "")
    if st == "retained":
        return "retained"
    if st == "planned":
        return "pending"
    if st == "exists":
        if kind == "table":
            return "migrated" if backend == "postgres" else "pending"
        if kind == "object-store":
            return "migrated" if backend == "object-store" else "pending"
        return "retained"
    return "pending"


def _seed_relationships() -> list[dict]:
    return [{"from": c, "to": p, "via": col, "kind": k, "owner_item": o, "note": n}
            for c, p, col, k, o, n in SEED]


def apply(reg: dict, tables: set[str], table_cols: dict[str, set[str]]) -> dict:
    if not isinstance(reg.get("relationships"), list) or not reg["relationships"]:
        reg["relationships"] = _seed_relationships()
    for v in (reg.get("stores") or {}).values():
        tgt = v.get("target") or {}
        cls = v.setdefault("classification", {})
        if tgt.get("status") == "planned":
            owner = str(tgt.get("owner_item") or "")
            ref, kind = str(tgt.get("ref") or ""), str(tgt.get("kind") or "")
            delivered = owner and _item_status(owner) in DONE
            if delivered and ((kind == "table" and ref in tables)
                              or (kind == "object-store" and cls.get("backend") == "object-store"
                                  and ref in OBJECT_META)):
                tgt["status"] = "exists"
        cls["migration_status"] = _expected_status(tgt, str(cls.get("backend") or ""))
    return reg


def check(reg: dict, tables: set[str], table_cols: dict[str, set[str]], triggers: set[str]) -> list[str]:
    bad: list[str] = []
    stores = reg.get("stores") or {}
    for name, v in stores.items():
        tgt = (v or {}).get("target") or {}
        cls = (v or {}).get("classification") or {}
        kind, ref, st = str(tgt.get("kind") or ""), str(tgt.get("ref") or ""), str(tgt.get("status") or "")
        backend = str(cls.get("backend") or "")
        if kind == "table" and st == "exists" and ref not in tables:
            bad.append(f"{name}: target table {ref!r} is not created by any migration")
        if kind == "object-store" and st == "exists":
            if backend != "object-store" or ref not in OBJECT_META:
                bad.append(f"{name}: object-store exists but backend={backend!r} ref={ref!r} "
                           f"(want backend object-store and ref in {sorted(OBJECT_META)})")
        if st == "planned":
            owner = str(tgt.get("owner_item") or "")
            if owner and _item_status(owner) in DONE:
                bad.append(f"{name}: planned under completed {owner} - map it to a real target")
        if kind == "table" and backend not in {"postgres", "file"}:
            bad.append(f"{name}: kind=table but backend={backend!r}")
        if kind == "object-store" and backend != "object-store":
            bad.append(f"{name}: kind=object-store but backend={backend!r}")
        if kind in {"file", "view", "derived"} and backend not in {"file", "derived"}:
            bad.append(f"{name}: kind={kind} but backend={backend!r}")
        want, have = _expected_status(tgt, backend), str(cls.get("migration_status") or "")
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
    missing = REQUIRED - {(str(r.get("from")), str(r.get("to")), str(r.get("via"))) for r in rels}
    for c, p, col in sorted(missing):
        bad.append(f"required relationship missing: {c}.{col} -> {p}")
    for t in REQUIRED_TRIGGERS:
        if t not in triggers:
            bad.append(f"required trigger missing from migrations: {t}")
    return bad


def _counts(reg: dict) -> dict[str, int]:
    out = {"migrated": 0, "retained": 0, "pending": 0}
    for v in (reg.get("stores") or {}).values():
        s = str(((v or {}).get("classification") or {}).get("migration_status") or "")
        if s in out:
            out[s] += 1
    return out


def _report(reg: dict, bad: list[str], verbose: bool) -> int:
    c = _counts(reg)
    print(f"store-relationships: stores={len(reg.get('stores') or {})} "
          f"relationships={len(reg.get('relationships') or [])} "
          f"migrated={c['migrated']} retained={c['retained']} pending={c['pending']}")
    if not bad:
        print("store-relationships: OK")
        return 0
    print(f"store-relationships: FAIL ({len(bad)} problem(s))")
    for b in (bad if verbose else bad[:20]):
        print("   " + b)
    return 1


def _self_test(reg: dict, tables, cols, triggers) -> int:
    failures = []
    bad_ref = copy.deepcopy(reg)
    bad_ref["stores"]["open.json"]["target"]["ref"] = "no_such_table"
    if not check(bad_ref, tables, cols, triggers):
        failures.append("unknown table target was not detected")
    bad_rel = copy.deepcopy(reg)
    bad_rel["relationships"] = [r for r in bad_rel.get("relationships") or [] if r.get("from") != "runs"]
    if not check(bad_rel, tables, cols, triggers):
        failures.append("removed required relationship was not detected")
    bad_status = copy.deepcopy(reg)
    first = next(iter(bad_status["stores"].values()))
    first["classification"]["migration_status"] = "nonsense"
    if not check(bad_status, tables, cols, triggers):
        failures.append("status drift was not detected")
    if failures:
        for f in failures:
            print("self-test: FAIL - " + f)
        return 1
    print("store-relationships: self-test OK (3 negative scenarios)")
    return _report(reg, check(reg, tables, cols, triggers), False)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write relationships + migration_status")
    ap.add_argument("--self-test", action="store_true", help="run the gate plus negative tests")
    ap.add_argument("--verbose", action="store_true", help="print every problem")
    ap.add_argument("--registry", default=str(REG))
    a = ap.parse_args(argv)
    path = Path(a.registry)
    reg = json.loads(path.read_text(encoding="utf-8"))
    tables, cols, triggers = _schema()
    if a.apply:
        reg = apply(reg, tables, cols)
        path.write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    bad = check(reg, tables, cols, triggers)
    if a.self_test:
        return _self_test(reg, tables, cols, triggers)
    return _report(reg, bad, a.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
