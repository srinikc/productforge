"""BI-PF-1399 Phase 4 (demote): regenerate the DERIVED backlog projections from the DB SoR.

Files are NOT deleted - they are rebuilt from the DB (the source of truth under PF_BACKLOG_DB=on). This is
the recovery/consistency tool for the demoted projections: item files + the open/closed indexes are
regenerated per scope from ``backlog_items``.

Usage: PF_DB_DSN=... python scripts/dev/backlog_rebuild_projections.py [--apply]
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main(argv: list[str]) -> int:
    apply_ = "--apply" in argv
    dsn = os.environ.get("PF_DB_DSN")
    if not dsn:
        print("PF_DB_DSN required", file=sys.stderr)
        return 2
    from core import backlog

    import psycopg
    with psycopg.connect(dsn) as c, c.cursor() as cur:
        cur.execute("SELECT data FROM backlog_items")
        items = [r[0] for r in cur.fetchall() if isinstance(r[0], dict) and r[0].get("id")]

    by_scope: dict[tuple[str, str | None], list[dict]] = defaultdict(list)
    for it in items:
        scope = str(it.get("scope") or "product_forge")
        project = str(it.get("project") or "") or None
        by_scope[(scope, project)].append(it)

    total = sum(len(v) for v in by_scope.values())
    print(f"projections: {total} items across {len(by_scope)} scope(s)")
    if not apply_:
        print("(dry-run; pass --apply to write the derived files)")
        return 0

    for (scope, project), group in by_scope.items():
        d, _of, _cf, _h, _c = backlog._paths(scope, project)
        op = [i for i in group if backlog._normalize_status(i.get("status", "new")) not in backlog._CLOSED]
        cl = [i for i in group if backlog._normalize_status(i.get("status", "new")) in backlog._CLOSED]
        for it in group:
            backlog._wj(os.path.join(backlog._items_dir(d), f"{it['id']}.json"), it)
        backlog._write_indexes(scope, project, op, cl)
        print(f"  rebuilt scope={scope} project={project or '-'} items={len(group)} (open={len(op)} closed={len(cl)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
