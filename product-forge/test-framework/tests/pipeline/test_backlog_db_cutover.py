"""BI-PF-1399 Phase 1: the backlog dual-write mirror behaviour (off = no-op; dual = best-effort; on = strict)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from core import backlog  # noqa: E402


def test_mode_defaults_off(monkeypatch):
    monkeypatch.delenv("PF_BACKLOG_DB", raising=False)
    assert backlog._backlog_db_mode() == "off"


def test_mirror_noop_when_off(monkeypatch):
    monkeypatch.delenv("PF_BACKLOG_DB", raising=False)
    # No network attempted; must not raise.
    backlog._mirror_item_to_db({"id": "BI-PF-0000", "title": "x"})


def test_mirror_skips_without_id(monkeypatch):
    monkeypatch.setenv("PF_BACKLOG_DB", "dual")
    backlog._mirror_item_to_db({"title": "no id"})  # no id -> no-op


def test_mirror_dual_is_best_effort(monkeypatch):
    monkeypatch.setenv("PF_BACKLOG_DB", "dual")
    monkeypatch.setenv("PF_BACKLOG_API", "http://127.0.0.1:1")  # unreachable
    # best-effort: swallows the failure (files remain the source of truth)
    backlog._mirror_item_to_db({"id": "BI-PF-0000", "title": "x", "type": "feature", "status": "new"})


def test_mirror_sends_full_item_as_data(monkeypatch):
    import json as _j

    monkeypatch.setenv("PF_BACKLOG_DB", "dual")
    monkeypatch.setenv("PF_BACKLOG_API", "http://127.0.0.1:1")
    captured = {}

    class _R:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def _fake(req, timeout=0):
        captured["body"] = req.data
        return _R()

    from urllib import request as _ur
    monkeypatch.setattr(_ur, "urlopen", _fake)
    item = {"id": "BI-PF-0000", "type": "feature", "status": "new",
            "acceptance_criteria": ["criterion that is at least forty characters long"]}
    backlog._mirror_item_to_db(item)
    payload = _j.loads(captured["body"])
    assert payload["Data"] == item  # lossless: the full item is sent as Data


def test_shadow_compare_equal(monkeypatch):
    item = {"id": "BI-PF-0000", "title": "x"}
    monkeypatch.setattr(backlog, "_fetch_item_from_db", lambda i, t: {"Data": item})
    assert backlog._shadow_compare(item) is True


def test_shadow_compare_detects_drift(monkeypatch):
    monkeypatch.setattr(backlog, "_fetch_item_from_db", lambda i, t: {"Data": {"id": "BI-PF-0000", "title": "DIFFERENT"}})
    assert backlog._shadow_compare({"id": "BI-PF-0000", "title": "x"}) is False


def test_shadow_compare_fetch_failure_is_false(monkeypatch):
    def _boom(i, t):
        raise RuntimeError("db down")
    monkeypatch.setattr(backlog, "_fetch_item_from_db", _boom)
    assert backlog._shadow_compare({"id": "BI-PF-0000", "title": "x"}) is False


def test_save_item_shadow_mode_compares(tmp_path, monkeypatch):
    monkeypatch.setenv("PF_BACKLOG_DB", "shadow")
    calls = {"mirror": 0, "compare": 0}
    monkeypatch.setattr(backlog, "_mirror_item_to_db", lambda item: calls.__setitem__("mirror", calls["mirror"] + 1))
    monkeypatch.setattr(backlog, "_shadow_compare", lambda item: calls.__setitem__("compare", calls["compare"] + 1) or True)
    d = str(tmp_path)
    backlog._save_item(d, {"id": "BI-PF-0000", "title": "x", "scope": "product_forge"})
    assert calls["mirror"] == 1 and calls["compare"] == 1


def test_load_all_on_mode_reads_db(monkeypatch):
    import json as _j

    monkeypatch.setenv("PF_BACKLOG_DB", "on")
    monkeypatch.setenv("PF_BACKLOG_API", "http://127.0.0.1:1")
    items = [{"ID": "BI-PF-1", "Data": {"id": "BI-PF-1", "status": "new"}},
             {"ID": "BI-PF-2", "Data": {"id": "BI-PF-2", "status": "completed"}}]

    class _R:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return _j.dumps({"items": items}).encode("utf-8")

    from urllib import request as _ur
    monkeypatch.setattr(_ur, "urlopen", lambda req, timeout=0: _R())
    op, cl = backlog._load_all("product_forge", None)
    assert [i["id"] for i in op] == ["BI-PF-1"]
    assert [i["id"] for i in cl] == ["BI-PF-2"]


def test_mirror_on_propagates_failure(monkeypatch):
    monkeypatch.setenv("PF_BACKLOG_DB", "on")
    monkeypatch.setenv("PF_BACKLOG_API", "http://127.0.0.1:1")
    with pytest.raises(Exception):
        backlog._mirror_item_to_db({"id": "BI-PF-0000", "title": "x", "type": "feature", "status": "new"})
