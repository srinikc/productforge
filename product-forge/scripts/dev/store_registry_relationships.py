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
    ("audit_partitioned", "tenants", "tenant_id", "logical", "BI-PF-1312", "partitioned audit parent is tenant-scoped"),
    ("audit_legal_hold_events", "tenants", "tenant_id", "logical", "BI-PF-1312", "legal holds may be tenant-scoped"),
    ("audit_legal_hold_archive", "tenants", "tenant_id", "logical", "BI-PF-1312", "archived held rows keep tenant scope"),
    ("control_state", "tenants", "tenant_id", "fk", "BI-PF-1309", "control state is tenant-scoped"),
    ("derived_outputs", "tenants", "tenant_id", "fk", "BI-PF-1309", "derived outputs are tenant-scoped"),
    ("ledger", "tenants", "tenant_id", "fk", "BI-PF-1309", "ledger entries are tenant-scoped"),
    ("quotas", "tenants", "tenant_id", "fk", "BI-PF-1309", "quota rows are tenant-scoped"),
    ("secrets", "tenants", "tenant_id", "fk", "BI-PF-1309", "secrets are tenant-scoped"),
    ("state", "tenants", "tenant_id", "fk", "BI-PF-1309", "state rows are tenant-scoped"),
    ("tool_settings", "tenants", "tenant_id", "fk", "BI-PF-1309", "tool settings are tenant-scoped"),
    ("usage", "tenants", "tenant_id", "fk", "BI-PF-1309", "usage rows are tenant-scoped"),
    ("stored_objects", "tenants", "tenant_id", "fk", "BI-PF-1307", "object metadata is tenant-scoped"),
]
# SEED is only the initial seeding set for --apply; the registry (and schema-derived expectations) is the
# authority at check time.
REQUIRED_TRIGGERS = (
    "audit_partitioned_append_only",
    "audit_partition_config_touch",
    "audit_legal_hold_guard",
    "audit_partitioned_no_truncate",
)
DONE = {"completed", "closed", "done"}
OBJECT_META = {"artifacts", "stored_objects"}
KINDS = {"table", "file", "derived", "object-store", "view"}
STATUSES = {"exists", "planned", "retained"}
RESERVED_COLS = {"primary", "foreign", "constraint", "unique", "check", "exclude", "like"}
ADR_DOC = ROOT / "docs" / "ARCHITECTURE-DECISIONS.md"
# Stores whose retention is a FORMAL decision (not just a default): they must carry a durable reason and a
# decision_ref that resolves to an ADR index row AND section. Add to this set as the other retained config
# stores are audited; the generic rule below also enforces every retained target that opts in with decision_ref.
FORMALLY_RETAINED = {
    "config/design-systems.json": "ADR-0009",
}


def adr_ids(text: str) -> set[str]:
    """ADR ids that have BOTH an index row ([ADR-NNNN]) and a section (# ADR-NNNN: ...)."""
    index = set(re.findall(r"\[ADR-(\d{4})\]", text or ""))
    sections = set(re.findall(r"^#\s+ADR-(\d{4}):", text or "", re.M))
    return {f"ADR-{i}" for i in index & sections}


def adr_section(text: str, ref: str) -> str:
    m = re.search(rf"^#\s+{re.escape(ref)}:.*?(?=^#\s+ADR-\d{{4}}:|\Z)", text or "", re.M | re.S)
    return m.group(0) if m else ""


def retained_problems(reg: dict, adr_text: str) -> list[str]:
    """Fail-closed retained-store invariants (BI-PF-1476).

    Generic rule: a retained target that opts in with decision_ref must carry a retained_reason and the ref
    must resolve to a real ADR. Pinned rule: FORMALLY_RETAINED entries must exist with the exact retained
    tuple, so deleting the entry or flipping it cannot silently pass.
    """
    bad: list[str] = []
    ids = adr_ids(adr_text)
    stores = reg.get("stores") or {}
    for name, v in stores.items():
        tgt = (v or {}).get("target") or {}
        if str(tgt.get("status")) != "retained":
            continue
        ref = str(tgt.get("decision_ref") or "")
        if ref:
            if not str(tgt.get("retained_reason") or "").strip():
                bad.append(f"{name}: retained target has decision_ref {ref} but no retained_reason")
            if ref not in ids:
                bad.append(f"{name}: decision_ref {ref} does not resolve to an ADR index row + section")
            elif "supersede" not in adr_section(adr_text, ref).lower():
                bad.append(f"{name}: decision_ref {ref} section has no supersede/revisit trigger")
    for name, ref in FORMALLY_RETAINED.items():
        entry = stores.get(name)
        if not isinstance(entry, dict):
            bad.append(f"{name}: formally retained store is missing from the registry")
            continue
        tgt = entry.get("target") or {}
        cls = entry.get("classification") or {}
        want = {"kind": "file", "status": "retained"}
        for k, val in want.items():
            if str(tgt.get(k)) != val:
                bad.append(f"{name}: target.{k}={tgt.get(k)!r}, expected {val!r}")
        if str(entry.get("kind")) != "config":
            bad.append(f"{name}: kind={entry.get('kind')!r}, expected 'config'")
        if str(cls.get("backend")) != "file":
            bad.append(f"{name}: backend={cls.get('backend')!r}, expected 'file'")
        if str(cls.get("migration_status")) != "retained":
            bad.append(f"{name}: migration_status={cls.get('migration_status')!r}, expected 'retained'")
        if str(tgt.get("decision_ref")) != ref:
            bad.append(f"{name}: decision_ref={tgt.get('decision_ref')!r}, expected {ref!r}")
        if not str(tgt.get("retained_reason") or "").strip():
            bad.append(f"{name}: formally retained store has no retained_reason")
    return bad


def retained_audit(reg: dict) -> list[dict]:
    """Machine-readable inventory of retained stores still missing a formal decision (future audit input)."""
    out = []
    for name, v in (reg.get("stores") or {}).items():
        tgt = (v or {}).get("target") or {}
        if str(tgt.get("status")) == "retained" and not str(tgt.get("decision_ref") or "").strip():
            out.append({"store": name, "owner": (v or {}).get("owner") or "",
                        "kind": (v or {}).get("kind") or ""})
    return sorted(out, key=lambda r: r["store"])



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
            cols = {c.lower() for c in re.findall(r"^\s*\"?([a-z_][a-z0-9_]*)\"?\s+[a-z]", body, re.M | re.I)
                    if c.lower() not in RESERVED_COLS}
            tables.setdefault(name, set()).update(cols)
        triggers.update(t.group(1).lower() for t in re.finditer(r"CREATE\s+TRIGGER\s+\"?([a-z_][a-z0-9_]*)\"?", s, re.I))
    return set(tables), tables, triggers


def _item_status(owner: str) -> str:
    try:
        return str(json.loads((ITEMS / f"{owner}.json").read_text(encoding="utf-8")).get("status") or "").lower()
    except Exception:
        return "unknown"


def _expected_status(target: dict, backend: str = "", store_kind: str = "") -> str:
    """migration_status describes where the DATA lives, not whether a table exists."""
    st, kind = str(target.get("status") or ""), str(target.get("kind") or "")
    if st == "retained":
        return "retained"
    if st == "planned":
        return "pending"
    if st == "exists":
        if kind == "table":
            if backend == "postgres":
                return "migrated"
            if store_kind == "config" and target.get("retained_reason"):
                return "retained"
            return "pending"
        if kind == "object-store":
            return "migrated" if backend == "object-store" else "pending"
        return "retained"
    return "pending"


def _seed_relationships() -> list[dict]:
    return [{"from": c, "to": p, "via": col, "kind": k, "owner_item": o, "note": n}
            for c, p, col, k, o, n in SEED]


def apply(reg: dict, tables: set[str], table_cols: dict[str, set[str]]) -> dict:
    # Registry is the storage; the seed is the canonical edge set. Upsert canonical edges, keep extras.
    rels = [r for r in (reg.get("relationships") or []) if isinstance(r, dict)]
    by_key = {(r.get("from"), r.get("to"), r.get("via")): r for r in rels}
    for seed in _seed_relationships():
        key = (seed["from"], seed["to"], seed["via"])
        if key in by_key:
            by_key[key].update({"kind": seed["kind"], "owner_item": seed["owner_item"], "note": seed["note"]})
        else:
            rels.append(seed)
    for r in rels:
        r.pop("verified", None)
    reg["relationships"] = rels
    for v in (reg.get("stores") or {}).values():
        tgt = v.get("target") or {}
        cls = v.setdefault("classification", {})
        # Config domains are deliberately file-retained (EDP decision); keep the recorded target/ref but
        # state why the data stays in files so planning does not see phantom migration work.
        if (str(v.get("kind") or "") == "config" and cls.get("backend") == "file"
                and str(tgt.get("kind") or "") == "table"):
            tgt["retained_reason"] = ("config/tenant settings remain file-backed by EDP decision; "
                                      "the table is reserved for a later cutover")
        if tgt.get("status") == "planned":
            owner = str(tgt.get("owner_item") or "")
            ref, kind = str(tgt.get("ref") or ""), str(tgt.get("kind") or "")
            delivered = owner and _item_status(owner) in DONE
            if delivered and ((kind == "table" and ref in tables)
                              or (kind == "object-store" and cls.get("backend") == "object-store"
                                  and ref in OBJECT_META)):
                tgt["status"] = "exists"
        cls["migration_status"] = _expected_status(tgt, str(cls.get("backend") or ""),
                                                    str(v.get("kind") or ""))
    return reg


def check(reg: dict, tables: set[str], table_cols: dict[str, set[str]], triggers: set[str]) -> list[str]:
    bad: list[str] = []
    stores = reg.get("stores") or {}
    for name, v in stores.items():
        tgt = (v or {}).get("target") or {}
        cls = (v or {}).get("classification") or {}
        kind, ref, st = str(tgt.get("kind") or ""), str(tgt.get("ref") or ""), str(tgt.get("status") or "")
        backend = str(cls.get("backend") or "")
        if kind not in KINDS:
            bad.append(f"{name}: target.kind={kind!r} is not one of {sorted(KINDS)}")
        if st not in STATUSES:
            bad.append(f"{name}: target.status={st!r} is not one of {sorted(STATUSES)}")
        if kind == "table" and st == "exists" and ref not in tables:
            bad.append(f"{name}: target table {ref!r} is not created by any migration")
        if kind == "object-store" and st == "exists":
            if backend != "object-store" or ref not in OBJECT_META:
                bad.append(f"{name}: object-store exists but backend={backend!r} ref={ref!r} "
                           f"(want backend object-store and ref in {sorted(OBJECT_META)})")
        if st == "planned":
            owner = str(tgt.get("owner_item") or "")
            if not owner:
                bad.append(f"{name}: planned target has no owner_item")
            else:
                st_owner = _item_status(owner)
                if st_owner == "unknown":
                    bad.append(f"{name}: planned owner {owner} cannot be read")
                elif st_owner in DONE:
                    bad.append(f"{name}: planned under completed {owner} - map it to a real target")
        if kind == "table" and backend not in {"postgres", "file"}:
            bad.append(f"{name}: kind=table but backend={backend!r}")
        if kind == "object-store" and backend != "object-store":
            bad.append(f"{name}: kind=object-store but backend={backend!r}")
        if kind in {"file", "view", "derived"} and backend not in {"file", "derived"}:
            bad.append(f"{name}: kind={kind} but backend={backend!r}")
        want = _expected_status(tgt, backend, str(v.get("kind") or ""))
        have = str(cls.get("migration_status") or "")
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
    # Expectation is derived from the schema, not a hardcoded list: every table carrying tenant_id must
    # declare its tenancy edge (the core isolation invariant Slice C is meant to prove).
    have = {(str(r.get("from")), str(r.get("to")), str(r.get("via"))) for r in rels}
    expected_tenancy = {(t, "tenants", "tenant_id") for t in tables
                        if t != "tenants" and "tenant_id" in table_cols.get(t, set())}
    for c, p, col in sorted(expected_tenancy - have):
        bad.append(f"tenancy relationship missing: {c}.{col} -> {p}")
    for t in REQUIRED_TRIGGERS:
        if t not in triggers:
            bad.append(f"required trigger missing from migrations: {t}")
    try:
        adr_text = ADR_DOC.read_text(encoding="utf-8")
    except Exception as e:  # fail closed: the decision register must be readable
        bad.append(f"ADR document unreadable: {e}")
    else:
        bad += retained_problems(reg, adr_text)
    return bad


def _counts(reg: dict) -> dict[str, int]:
    out = {"migrated": 0, "retained": 0, "pending": 0, "invalid": 0}
    for v in (reg.get("stores") or {}).values():
        s = str(((v or {}).get("classification") or {}).get("migration_status") or "")
        out[s if s in out else "invalid"] += 1
    return out


def _report(reg: dict, bad: list[str], verbose: bool) -> int:
    c = _counts(reg)
    print(f"store-relationships: stores={len(reg.get('stores') or {})} "
          f"relationships={len(reg.get('relationships') or [])} "
          f"migrated={c['migrated']} retained={c['retained']} pending={c['pending']}"
          + (f" invalid={c['invalid']}" if c["invalid"] else ""))
    if not bad:
        print("store-relationships: OK")
        return 0
    print(f"store-relationships: FAIL ({len(bad)} problem(s))")
    for b in bad:  # always print every problem: truncation hides bulk drift in CI
        print("   " + b)
    return 1


def _self_test(reg: dict, tables, cols, triggers) -> int:
    failures = []
    # ADR referential integrity is BOTH an index row and a section; each half alone must not resolve.
    index_only = "| [ADR-0099](#adr-0099-x) | x | Accepted | 2026-01-01 |"
    both = index_only + "\n# ADR-0099: x\n"
    if adr_ids(index_only) or not adr_ids(both):
        failures.append("ADR index/section matching is not enforced")
    if not isinstance(retained_audit(reg), list):
        failures.append("retained_audit did not return a list")
    applied = apply(copy.deepcopy(reg), tables, cols)
    if check(applied, tables, cols, triggers):
        failures.append("apply() broke the registry invariants")
    try:
        adr_text = ADR_DOC.read_text(encoding="utf-8")
    except Exception:
        adr_text = ""
    if adr_text and not retained_problems(reg, re.sub(r"(?i)supersede", "omitted", adr_text)):
        failures.append("missing supersede trigger was not detected")
    table_store = next((n for n, v in (reg.get("stores") or {}).items()
                        if (v.get("target") or {}).get("kind") == "table"), None)
    if table_store is None:
        print("self-test: FAIL - no table store to mutate")
        return 1
    bad_ref = copy.deepcopy(reg)
    bad_ref["stores"][table_store]["target"]["ref"] = "no_such_table"
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
    # Retained-decision invariants (BI-PF-1476). All mutations are in-memory copies; the live registry is
    # never written by the self-test.
    for name in FORMALLY_RETAINED:
        if name not in (reg.get("stores") or {}):
            continue
        del_missing = copy.deepcopy(reg)
        del_missing["stores"].pop(name, None)
        if not check(del_missing, tables, cols, triggers):
            failures.append(f"deleting formally retained {name} was not detected")
        blank_reason = copy.deepcopy(reg)
        blank_reason["stores"][name]["target"]["retained_reason"] = ""
        if not check(blank_reason, tables, cols, triggers):
            failures.append(f"blank retained_reason on {name} was not detected")
        flipped = copy.deepcopy(reg)
        flipped["stores"][name]["target"]["status"] = "planned"
        if not check(flipped, tables, cols, triggers):
            failures.append(f"flipping {name} to planned was not detected")
        no_ref = copy.deepcopy(reg)
        no_ref["stores"][name]["target"].pop("decision_ref", None)
        if not check(no_ref, tables, cols, triggers):
            failures.append(f"removing decision_ref from {name} was not detected")
        bad_ref = copy.deepcopy(reg)
        bad_ref["stores"][name]["target"]["decision_ref"] = "ADR-9999"
        if not check(bad_ref, tables, cols, triggers):
            failures.append(f"unresolvable decision_ref on {name} was not detected")
    if failures:
        for f in failures:
            print("self-test: FAIL - " + f)
        return 1
    print("store-relationships: self-test OK (status/target/retained-decision negatives)")
    return _report(reg, check(reg, tables, cols, triggers), False)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write relationships + migration_status")
    ap.add_argument("--self-test", action="store_true", help="run the gate plus negative tests")
    ap.add_argument("--verbose", action="store_true", help="print every problem")
    ap.add_argument("--retained-audit", action="store_true",
                    help="print retained stores that still lack a formal decision_ref (JSON)")
    ap.add_argument("--registry", default=str(REG))
    a = ap.parse_args(argv)
    path = Path(a.registry)
    reg = json.loads(path.read_text(encoding="utf-8"))
    tables, cols, triggers = _schema()
    if a.retained_audit:
        print(json.dumps(retained_audit(reg), indent=2))
        return 0
    if a.apply:
        reg = apply(reg, tables, cols)
        path.write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    bad = check(reg, tables, cols, triggers)
    if a.self_test:
        return _self_test(reg, tables, cols, triggers)
    return _report(reg, bad, a.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
