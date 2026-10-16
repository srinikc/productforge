"""EXPLAIN evidence for EDP-17 hot query paths (BI-PF-1309).

Confirms the canonical indexes exist and that the tenant/run/stage listing queries use an index rather
than a sequential scan. Uses ``PF_DB_DSN`` and forces ``enable_seqscan=off`` so the plan reflects index
availability even on small/empty tables.

Usage: python scripts/dev/db_explain_check.py
"""
from __future__ import annotations

import os
import sys

QUERIES: list[tuple[str, str]] = [
    ("projects by tenant (ordered)", "SELECT id, tenant_id, slug, name, status, version "
                                     "FROM projects WHERE tenant_id = 't' ORDER BY slug"),
    ("runs by tenant+status", "SELECT id, tenant_id, project_id, status, version "
                              "FROM runs WHERE tenant_id = 't' AND status = 'running'"),
    ("stages by run (ordered)", "SELECT id, run_id, ordinal, status "
                                "FROM stages WHERE run_id = 'r' ORDER BY ordinal"),
    ("attempts by stage (ordered)", "SELECT id, stage_id, attempt, status "
                                    "FROM attempts WHERE stage_id = 's' ORDER BY attempt"),
    ("usage by tenant+metric+period", "SELECT id FROM usage "
                                      "WHERE tenant_id = 't' AND metric = 'm' ORDER BY period_start DESC"),
]

EXPECTED_INDEXES = {
    "idx_memberships_tenant", "idx_projects_tenant", "idx_runs_tenant_status", "idx_runs_project",
    "idx_stages_run", "idx_attempts_stage", "idx_usage_tenant_metric",
    # BI-PF-1421: direct scope/project discriminators
    "idx_backlog_items_scope_project", "idx_stages_project", "idx_attempts_project",
}


def main() -> int:
    dsn = os.environ.get("PF_DB_DSN")
    if not dsn:
        print("PF_DB_DSN is not set", file=sys.stderr)
        return 2
    import psycopg

    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("SELECT indexname FROM pg_indexes WHERE schemaname = current_schema()")
        present = {r[0] for r in cur.fetchall()}
        missing = EXPECTED_INDEXES - present
        print(f"indexes present: {len(EXPECTED_INDEXES - missing)}/{len(EXPECTED_INDEXES)}")
        if missing:
            print(f"  MISSING: {sorted(missing)}")

        cur.execute("SET enable_seqscan = off")
        ok = True
        for label, sql in QUERIES:
            cur.execute("EXPLAIN " + sql)
            plan = "\n".join(r[0] for r in cur.fetchall())
            used = "Index Scan" in plan or "Index Only Scan" in plan
            ok = ok and used
            print(f"  [{'OK ' if used else 'SEQ'}] {label}")

    if missing or not ok:
        print("db-explain: FAIL")
        return 1
    print("db-explain: OK (all hot paths use an index; all indexes present)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
