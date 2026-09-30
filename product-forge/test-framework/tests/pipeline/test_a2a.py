"""BI-0197: A2A interop — agnostic card, contract validation, server, client + pipeline tracking."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import a2a  # noqa: E402


def test_agent_card_is_built_from_agnostic_specs():
    card = a2a.agent_card()
    assert card["protocolVersion"] == a2a.CONTRACT
    assert card["name"] == "product-forge"
    # no .opencode dependency: specs come from agents/*.agent.json via core.agent_spec
    specs = a2a._load_specs()
    if specs:
        one = a2a.agent_card(next(iter(specs)))
        assert one and one["name"] in specs


def test_validate_message_contract_fail_closed():
    good = a2a.new_message("analyst", "architect", "design", correlation_id="c1")
    assert a2a.validate_message(good) is None
    assert "contract" in a2a.validate_message({**good, "contract": "x/v9"})
    assert "correlation_id" in a2a.validate_message({**good, "correlation_id": ""})
    assert "to.agent" in a2a.validate_message({**good, "to": {}})
    assert "task.skill" in a2a.validate_message({**good, "task": {}})


def test_server_message_send_and_tasks_get(tmp_path):
    pdir = str(tmp_path)
    msg = a2a.new_message("remote", "analyst", "analyze", correlation_id="c9")
    # target any agent id present; else use a generic one (validation still enforces skill only if known)
    r = a2a.handle({"jsonrpc": "2.0", "id": 1, "method": "message/send",
                    "params": {"message": msg}},
                   project="_t_a2a", products_dir=pdir)
    assert r["result"]["task"]["status"] == "submitted"
    tid = r["result"]["task"]["id"]
    g = a2a.handle({"jsonrpc": "2.0", "id": 2, "method": "tasks/get", "params": {"id": tid}},
                   project="_t_a2a", products_dir=pdir)
    assert g["result"]["task"]["status"] in ("submitted", "working")
    # unknown method / bad message fail-closed
    assert a2a.handle({"jsonrpc": "2.0", "id": 3, "method": "bogus"})["error"]["code"] == -32601
    bad = a2a.handle({"jsonrpc": "2.0", "id": 4, "method": "message/send",
                      "params": {"message": {"contract": "x"}}})
    assert bad["error"]["code"] == -32602


def test_send_rejects_invalid_and_delegate_tracks(tmp_path, monkeypatch):
    pdir = str(tmp_path)
    # invalid message -> fail-closed before any transport
    assert a2a.send({"url": "http://127.0.0.1:1/x"}, {"contract": "x"})["ok"] is False
    # consume disabled by default (opt-in, whitelisted)
    assert a2a.delegate("nope", a2a.new_message("o", "a", "s"))["ok"] is False

    # whitelist a fake remote + enable consume; stub the transport, assert pipeline tracking
    monkeypatch.setenv("A2A_ENABLE_CONSUME", "1")
    monkeypatch.setattr(a2a, "_remote", lambda n: {"url": "http://fake"} if n == "peer" else None)
    monkeypatch.setattr(a2a, "send", lambda *a, **k: {"ok": True, "result": {"task": {"status": "completed"}}})
    msg = a2a.new_message("orchestrator", "peer-agent", "do", correlation_id="c5")
    r = a2a.delegate("peer", msg, project="_t_a2a2", products_dir=pdir)
    assert r["ok"] is True
    ledger = json.loads((Path(pdir) / "_t_a2a2" / "delegations.json").read_text(encoding="utf-8"))
    assert ledger and ledger[-1]["status"] == "completed"
    assert ledger[-1]["remote"] == "peer" and ledger[-1]["contract"] == a2a.CONTRACT
