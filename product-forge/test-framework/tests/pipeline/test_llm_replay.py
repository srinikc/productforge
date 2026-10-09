"""BI-PF-0459: deterministic LLM replay — LLMReplay store + LLMClient._http_post seam."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
os.environ.setdefault("PF_OFFLINE", "1")

import pytest  # noqa: E402

from core.orchestrator.llm_client import _CassetteResponse  # noqa: E402
from core.orchestrator.llm_client import LLMClient  # noqa: E402
from core.orchestrator.storage import LLMReplay, llm_replay_mode  # noqa: E402


def _client(tmp):
    class _Cache:
        cache_dir = os.path.join(str(tmp), ".llm-cache")

    c = LLMClient.__new__(LLMClient)
    c.llm_cache = _Cache()
    return c


EP = "https://example.invalid/v1"
DATA = {"model": "m", "messages": [{"role": "user", "content": "hi"}]}


def test_mode_default_off(monkeypatch):
    monkeypatch.delenv("PIPELINE_LLM_REPLAY", raising=False)
    assert llm_replay_mode() == "off"


def test_replay_serves_cassette(tmp_path, monkeypatch):
    monkeypatch.setenv("PIPELINE_LLM_REPLAY", "replay")
    LLMReplay(str(tmp_path)).set(LLMReplay.key(EP, DATA),
                                 {"status_code": 200, "content": "OK", "headers": {}})
    r = _client(tmp_path)._http_post(EP, DATA, {})
    assert isinstance(r, _CassetteResponse)
    assert r.status_code == 200 and r.content == b"OK"


def test_replay_miss_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("PIPELINE_LLM_REPLAY", "replay")
    with pytest.raises(RuntimeError):
        _client(tmp_path)._http_post(EP, {"a": 1}, {})


def test_record_writes_cassette(tmp_path, monkeypatch):
    monkeypatch.setenv("PIPELINE_LLM_REPLAY", "record")

    class _Resp:
        status_code = 200
        content = b'{"ok":1}'
        headers = {"Retry-After": ""}

    import requests
    monkeypatch.setattr(requests, "post", lambda *a, **k: _Resp())
    r = _client(tmp_path)._http_post(EP, DATA, {})
    assert r.status_code == 200
    rec = LLMReplay(str(tmp_path)).get(LLMReplay.key(EP, DATA))
    assert rec and rec["status_code"] == 200 and rec["content"] == '{"ok":1}'
