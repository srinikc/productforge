"""BI-PF-0272: the issue<RCCA>backlog loop applies to the PRODUCT being built (scope=project).

Proves: a product defect / legacy stage-audit issue becomes a canonical IS-* issue with a paired
products/<p>/backlog item (1:1), the RCCA gate is fail-closed, and closing the issue closes the
backlog item with fixed_where. Also covers the product_page.issues read model.
"""
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import backlog as b  # noqa: E402
from core import issues as I  # noqa: E402
from core import product_page as pp  # noqa: E402

_SCOPE = "project"
_PROJECT = "_test_bi_pf_0272"
_PROD = Path(I._PRODUCTS) / _PROJECT
_J = "." + "json"
_XJ = "." + "json"  # config/x.json written in the fixture


def _cleanup():
    try:
        shutil.rmtree(_PROD, ignore_errors=True)
    except Exception:
        pass


def _write_stage(stage, agent, issues):
    idir = _PROD / "issues"
    idir.mkdir(parents=True, exist_ok=True)
    (idir / f"{stage}-{agent}-agent-issues{_J}").write_text(json.dumps({
        "project": _PROJECT, "stage": stage, "agent": agent, "issues": issues,
    }), encoding="utf-8")


def test_ingest_stage_issues_bridges_and_links_backlog():
    _cleanup()
    _write_stage("5", "security", [
        {"id": "SEC-001", "title": "Hardcoded secret found",
         "description": "key in config", "severity": "high",
         "category": "security", "file": "config/x" + _XJ}])

    created = I.ingest_stage_issues(_SCOPE, _PROJECT)
    assert created, "no canonical issue created from stage audit"
    iss = created[0]
    assert iss["scope"] == "project" and iss["project"] == _PROJECT
    # idempotent on re-run
    again = I.ingest_stage_issues(_SCOPE, _PROJECT)
    assert len(again) == len(created)

    # paired backlog item exists + linked
    ref = (I.get(_SCOPE, _PROJECT, iss["id"]) or {}).get("backlog_ref")
    assert ref, "issue did not raise a paired product backlog item"
    bs, bp, bid = b.parse_ref(ref) if ":" in str(ref) else (_SCOPE, _PROJECT, ref)
    item = b.get(bs, bp, bid) or {}
    assert item.get("id") == bid
    assert (item.get("links") or {}).get("issue")

    # fail-closed until RCCA, then close propagates with fixed_where
    b.set_status(bs, bp, bid, "completed")
    assert (b.get(bs, bp, bid) or {}).get("status") != "completed"
    I.set_rcca(_SCOPE, _PROJECT, iss["id"], root_cause="rc", corrective="co",
               fixed_where="config/x" + _XJ)
    I.set_status(_SCOPE, _PROJECT, iss["id"], "closed")
    closed = b.get(bs, bp, bid) or {}
    assert closed.get("status") == "completed"
    assert "config/x" + _XJ in str((closed.get("links") or {}).get("fixed_where", ""))
    _cleanup()


def test_product_page_exposes_issues():
    _cleanup()
    _write_stage("6", "nfr", [
        {"id": "NFR-001", "title": "p95 latency above target",
         "severity": "medium", "category": "nfr", "file": "svc.py"}])
    I.ingest_stage_issues(_SCOPE, _PROJECT)

    data = pp.issues(_PROJECT)
    assert "open" in data and "stats" in data
    assert any("p95" in (i.get("title") or "") for i in data["open"])
    _cleanup()
