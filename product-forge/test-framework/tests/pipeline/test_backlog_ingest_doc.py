"""BI-PF-1396: doc-driven backlog ingest - parse sections, route fields, upsert diff (API-only writes)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.dev import backlog_ingest_doc as bi  # noqa: E402

DOC = """# Plan

## BI-PF-1309 - EDP-17 canonical schema
objective: canonical PostgreSQL schema
affected_files:
- migrations/0002_core_schema.up.sql
- go/store/pg.go
risks: migration drift, data loss
type: feature

## BI-PF-1301 - EDP-09
objective: tenant RLS
"""


def test_parse_sections_maps_fields_and_lists():
    s = bi.parse_sections(DOC)
    assert set(s) == {"BI-PF-1309", "BI-PF-1301"}
    a = s["BI-PF-1309"]
    assert a["objective"] == "canonical PostgreSQL schema"
    assert a["affected_files"] == ["migrations/0002_core_schema.up.sql", "go/store/pg.go"]
    assert a["risks"] == ["migration drift", "data loss"]
    assert a["type"] == "feature"
    assert a["title"] == "EDP-17 canonical schema"


def test_compute_changes_fills_missing_only():
    cur = {"objective": "already here", "owner": ""}
    desired = {"objective": "new", "owner": "alice", "approach": "x"}
    assert bi.compute_changes(cur, desired, overwrite=False) == {"owner": "alice", "approach": "x"}


def test_compute_changes_overwrite():
    assert bi.compute_changes({"objective": "old"}, {"objective": "new"}, overwrite=True) == {"objective": "new"}


def test_route_splits_endpoints():
    ctx, edit, deps = bi._route({"objective": "o", "type": "bug", "blocked_by": ["BI-PF-1293"]})
    assert ctx == {"objective": "o"}
    assert edit == {"type": "bug"}
    assert deps == {"blocked_by": ["BI-PF-1293"]}


def test_dry_run_never_writes():
    calls = []

    class FakeClient:
        def get_item(self, iid, scope, project):
            return {"objective": ""}

        def create_item(self, *a, **k):
            calls.append("create")
            return {}

        def call(self, *a, **k):
            calls.append("call")
            return {}

    report = bi.run(bi.parse_sections(DOC), FakeClient(), "BI-PF-1292", "product_forge", "", False, False, False)
    assert calls == []
    assert {r["state"] for r in report} == {"preview"}
    assert "objective" in report[0]["changed"]


def test_apply_routes_context_to_endpoint():
    seen = []

    class FakeClient:
        def get_item(self, iid, scope, project):
            return {"objective": ""}

        def create_item(self, *a, **k):
            return {}

        def call(self, method, path, body=None):
            seen.append((method, path))
            return {}

    bi.run(bi.parse_sections(DOC), FakeClient(), "BI-PF-1292", "product_forge", "", True, False, False)
    assert any(p.endswith("/context") for _, p in seen)
    assert any(m == "PATCH" for m, _ in seen)


def test_missing_item_reported_without_create():
    class FakeClient:
        def get_item(self, iid, scope, project):
            return None

        def create_item(self, *a, **k):
            raise AssertionError("should not create")

        def call(self, *a, **k):
            raise AssertionError("should not call")

    report = bi.run(bi.parse_sections(DOC), FakeClient(), "BI-PF-1292", "product_forge", "", True, False, False)
    assert {r["state"] for r in report} == {"not_found"}


def test_extract_text_reads_markdown(tmp_path):
    p = tmp_path / "plan.md"
    p.write_text(DOC, encoding="utf-8")
    assert "canonical PostgreSQL schema" in bi.extract_text(p)
