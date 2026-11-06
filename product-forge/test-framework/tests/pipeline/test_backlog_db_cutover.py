"""BI-PF-1399 Phase 1: the backlog dual-write mirror behaviour (off = no-op; dual = best-effort; on = strict)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from core import backlog  # noqa: E402


def test_mode_defaults_on(monkeypatch):
    monkeypatch.delenv("PF_BACKLOG_DB", raising=False)
    assert backlog._backlog_db_mode() == "on"


def test_mirror_noop_when_off(monkeypatch):
    monkeypatch.setenv("PF_BACKLOG_DB", "off")
    # No network attempted; must not raise.
    backlog._mirror_item_to_db({"id": "BI-PF-0000", "title": "x"})


def test_mirror_skips_without_id(monkeypatch):
    monkeypatch.setenv("PF_BACKLOG_DB", "dual")
    backlog._mirror_item_to_db({"title": "no id"})  # no id -> no-op


def test_mirror_dual_is_best_effort(monkeypatch):
    monkeypatch.setenv("PF_BACKLOG_DB", "dual")
    monkeypatch.setenv("PF_EDP_API_URL", "http://127.0.0.1:1")  # unreachable
    # best-effort: swallows the failure (files remain the source of truth)
    backlog._mirror_item_to_db({"id": "BI-PF-0000", "title": "x", "type": "feature", "status": "new"})


def test_mirror_sends_full_item_as_data(monkeypatch):
    import json as _j

    monkeypatch.setenv("PF_BACKLOG_DB", "dual")
    monkeypatch.setenv("PF_EDP_API_URL", "http://127.0.0.1:1")
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
    monkeypatch.setenv("PF_EDP_API_URL", "http://127.0.0.1:1")
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
    monkeypatch.setenv("PF_EDP_API_URL", "http://127.0.0.1:1")
    with pytest.raises(Exception):
        backlog._mirror_item_to_db({"id": "BI-PF-0000", "title": "x", "type": "feature", "status": "new"})


def test_id_allocator_defaults_on(monkeypatch):
    from core import id_allocator
    monkeypatch.delenv("PF_BACKLOG_DB", raising=False)
    assert id_allocator._db_enabled("product_forge") is True


def test_on_mode_fails_closed_without_db(monkeypatch):
    import urllib.error
    monkeypatch.setenv("PF_BACKLOG_DB", "on")
    monkeypatch.setenv("PF_EDP_API_URL", "http://127.0.0.1:1")
    with pytest.raises(RuntimeError, match="BACKLOG_DB_UNAVAILABLE"):
        backlog.list_open("product_forge", None)


def test_rollback_off_restores_file_mode(monkeypatch):
    monkeypatch.setenv("PF_BACKLOG_DB", "off")
    assert backlog._backlog_db_mode() == "off"
    assert backlog._db_for("product_forge") is False


def test_rollback_off_writes_authoritative_file(monkeypatch):
    calls = []
    monkeypatch.setenv("PF_BACKLOG_DB", "off")
    monkeypatch.setattr(backlog, "_wj", lambda path, value: calls.append((path, value)))
    backlog._save_item("ignored", {"id": "BI-PF-2", "scope": "product_forge", "title": "x"})
    assert calls, "off mode did not write the file path"


def test_unverified_scope_stays_file_mode(monkeypatch):
    from core import backlog
    monkeypatch.setenv("PF_BACKLOG_DB", "on")
    monkeypatch.setenv("PF_BACKLOG_DB_SCOPES", "product_forge")
    assert backlog._db_for("product_forge") is True
    assert backlog._db_for("unverified_scope") is False
    assert backlog._db_for("product_forge") is True
    assert backlog._db_for("arbitrary_scope") is False


def test_invalid_mode_fails_closed(monkeypatch):
    import pytest
    from core import backlog
    monkeypatch.setenv("PF_BACKLOG_DB", "bogus")
    with pytest.raises(RuntimeError, match="BACKLOG_DB_MODE_INVALID"):
        backlog._backlog_db_mode()


def test_tenant_attribution_rejects_mismatch():
    import importlib.util
    from pathlib import Path as P
    root = P(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location("bf", root / "scripts" / "dev" / "backlog_db_backfill.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    p = P("products") / "ProductA" / "data" / "backlog" / "items" / "BI-PF-1.json"
    assert m.tenant_for_item({"project": "ProductA"}, p) == "ProductA"
    try:
        m.tenant_for_item({"project": "ProductB"}, p)
    except ValueError as e:
        assert "tenant attribution mismatch" in str(e)
    else:
        raise AssertionError("mismatch accepted")


def test_id_allocator_scope_gate(monkeypatch):
    from core import id_allocator
    monkeypatch.setenv("PF_BACKLOG_DB", "on")
    monkeypatch.setenv("PF_BACKLOG_DB_SCOPES", "product_forge")
    assert id_allocator._db_enabled("product_forge") is True
    assert id_allocator._db_enabled("unverified") is False


def test_parity_scans_products(monkeypatch, tmp_path):
    import importlib.util, json
    from pathlib import Path as P
    root = P(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location("par", root / "scripts" / "dev" / "backlog_db_parity.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    (tmp_path / "data" / "backlog" / "items").mkdir(parents=True)
    (tmp_path / "products" / "X" / "data" / "backlog" / "items").mkdir(parents=True)
    (tmp_path / "products" / "X" / "data" / "backlog" / "items" / "BI-PF-9.json").write_text(json.dumps({"id":"BI-PF-9","project":"X"}), encoding="utf-8")
    m.ROOT = tmp_path; m.ITEMS = tmp_path / "data" / "backlog" / "items"
    assert set(m.file_items("X")) == {"BI-PF-9"}


def test_id_allocator_db_failure_never_falls_back(monkeypatch):
    import pytest
    from core import id_allocator
    monkeypatch.setattr(id_allocator, "_db_enabled", lambda scope=None: True)
    monkeypatch.setattr(id_allocator, "_reserve_db", lambda *a, **k: None)
    with pytest.raises(RuntimeError, match="refusing a Git/local id fallback"):
        id_allocator._mint("product_forge", None, 0, 0)


def test_on_mode_never_writes_file(monkeypatch, tmp_path):
    from core import backlog
    monkeypatch.setenv("PF_BACKLOG_DB", "on")
    monkeypatch.setenv("PF_BACKLOG_DB_SCOPES", "product_forge")
    calls = []
    monkeypatch.setattr(backlog, "_mirror_item_to_db", lambda item: calls.append(item["id"]))
    backlog._save_item(str(tmp_path), {"id": "BI-PF-700", "scope": "product_forge"})
    assert calls == ["BI-PF-700"]
    assert not (tmp_path / "items" / "BI-PF-700.json").exists()


def test_export_write_skip_overwrite(monkeypatch, tmp_path):
    import sys, types
    from pathlib import Path as P
    class Cur:
        def execute(self, *a, **k): pass
        def fetchall(self): return [("BI-PF-1", {"id": "BI-PF-1", "title": "x"})]
        def __enter__(self): return self
        def __exit__(self, *a): return False
    class Conn:
        def cursor(self): return Cur()
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def commit(self): pass
    fake = types.SimpleNamespace(connect=lambda dsn: Conn())
    monkeypatch.setitem(sys.modules, "psycopg", fake)
    monkeypatch.setenv("PF_DB_DSN", "x")
    root = P(__file__).resolve().parents[3]
    import importlib.util
    spec = importlib.util.spec_from_file_location("exp", root / "scripts" / "dev" / "backlog_db_export.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    monkeypatch.setattr(sys, "argv", ["x", "--tenant", "product_forge", "--out-dir", str(tmp_path)])
    assert m.main() == 0
    assert (tmp_path / "BI-PF-1.json").is_file()
    assert m.main() == 0  # skipped existing
