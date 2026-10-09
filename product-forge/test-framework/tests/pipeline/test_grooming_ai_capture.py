"""BI-PF-1196: AI grooming uses the single LLM owner (one-shot), not the agent runtime.

Stubbed (no live model): the AI path parses the JSON response and surfaces a deterministic fallback.
"""
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import backlog, grooming  # noqa: E402
from core.paths import PRODUCTS_DIR  # noqa: E402

_PROJ = "_test_groom_ai_capture"


def _clean():
    shutil.rmtree(os.path.join(str(PRODUCTS_DIR), _PROJ), ignore_errors=True)


def test_extract_json_fenced_and_bare():
    assert grooming._extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert grooming._extract_json('blah {"a": {"b": 2}} trailing') == {"a": {"b": 2}}
    assert grooming._extract_json("no json here") is None


def test_run_ai_batch_parses_id_keyed_json(monkeypatch):
    payload = {"A1": {"architecture_fit": "REUSE"}, "A2": {"architecture_fit": "EXTEND"}}
    monkeypatch.setattr(grooming, "_ai_enabled", lambda: True)
    monkeypatch.setattr(grooming, "_llm_text", lambda prompt, product: json.dumps(payload))
    res = grooming._run_ai_batch([({"id": "A1"}, {}), ({"id": "A2"}, {}), ({"id": "A3"}, {})],
                                 None, "default")
    assert res["A1"]["architecture_fit"] == "REUSE"
    assert res["A2"]["architecture_fit"] == "EXTEND"
    assert "A3" not in res            # absent -> caller falls back for that item


def test_run_ai_single_parses_proposal(monkeypatch):
    monkeypatch.setattr(grooming, "_ai_enabled", lambda: True)
    monkeypatch.setattr(grooming, "_llm_text", lambda prompt, product: '```json\n{"architecture_fit": "MODIFY"}\n```')
    assert grooming._run_ai({"id": "A1"}, {}, None, "default") == {"architecture_fit": "MODIFY"}


def test_run_ai_returns_none_without_json(monkeypatch):
    monkeypatch.setattr(grooming, "_ai_enabled", lambda: True)
    monkeypatch.setattr(grooming, "_llm_text", lambda prompt, product: "no json")
    assert grooming._run_ai({"id": "A1"}, {}, None, "default") is None


def _status(iid):
    return (backlog.get("project", _PROJ, iid).get("analysis") or {}).get("status")


def test_groom_all_parallel(monkeypatch):
    _clean()
    try:
        ids = []
        for k in range(4):
            iid = backlog.add_epic("project", _PROJ, f"Parallel {k}",
                                   body="## Problem\nx\n## Goal\ny\n## In scope\n- z\n## Acceptance\n- w",
                                   tag="TST")["id"]
            backlog.set_analysis("project", _PROJ, iid, status="NOT_ANALYZED", analysis={}, analyzed_by="")
            ids.append(iid)
        monkeypatch.setattr(grooming, "_ai_enabled", lambda: True)

        def _fake_batch(ctxs, project, product):
            return {str(it.get("id")): {"architecture_fit": "REUSE", "confidence": "high"}
                    for it, _ in ctxs}

        monkeypatch.setattr(grooming, "_run_ai_batch", _fake_batch)
        r = grooming.groom_all("project", _PROJ, mode="ai", batch=2, jobs=2)
        assert r["count"] == 4 and r["jobs"] == 2
        assert all(x["mode"] == "ai" for x in r["results"])
        for iid in ids:
            assert _status(iid) == "IN_PROGRESS"
    finally:
        _clean()


def test_groom_all_ids_filter(monkeypatch):
    _clean()
    try:
        a = backlog.add_epic("project", _PROJ, "A", body="## Problem\nx\n## Goal\ny\n## In scope\n- z\n## Acceptance\n- w", tag="TST")["id"]
        b = backlog.add_epic("project", _PROJ, "B", body="## Problem\nx\n## Goal\ny\n## In scope\n- z\n## Acceptance\n- w", tag="TST")["id"]
        for i in (a, b):
            backlog.set_analysis("project", _PROJ, i, status="NOT_ANALYZED", analysis={}, analyzed_by="")
        monkeypatch.setattr(grooming, "_ai_enabled", lambda: True)
        monkeypatch.setattr(grooming, "_run_ai_batch",
                            lambda ctxs, project, product: {str(it.get("id")): {"architecture_fit": "REUSE"}
                                                            for it, _ in ctxs})
        r = grooming.groom_all("project", _PROJ, mode="ai", batch=3, ids=[a])
        assert r["count"] == 1 and r["groomed"] == [a]
        assert _status(a) == "IN_PROGRESS"
        assert _status(b) != "IN_PROGRESS"   # not selected -> untouched
    finally:
        _clean()


def test_groom_all_surfaces_ai_failure(monkeypatch):
    _clean()
    try:
        iid = backlog.add_epic("project", _PROJ, "Export API",
                               body="## Problem\nx\n## Goal\ny\n## In scope\n- z\n## Acceptance\n- w",
                               tag="TST")["id"]
        backlog.set_analysis("project", _PROJ, iid, status="NOT_ANALYZED", analysis={}, analyzed_by="")
        monkeypatch.setattr(grooming, "_ai_enabled", lambda: True)
        monkeypatch.setattr(grooming, "_llm_text", lambda prompt, product: "garbage, not json")
        r = grooming.groom_all("project", _PROJ, mode="ai", batch=3)
        res = r["results"][0]
        assert res["mode"] == "deterministic"   # fell back
        assert res["ai_failed"] is True         # and it is surfaced (not silent)
    finally:
        _clean()
