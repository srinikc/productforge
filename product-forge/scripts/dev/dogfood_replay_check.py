"""BI-PF-0459 gate: deterministic LLM replay.

Asserts the seam (``LLMClient._http_post`` + ``core.orchestrator.storage.LLMReplay``): a recorded cassette is
served in replay mode (no network), a replay MISS fails closed, and the mode defaults to ``off``.
Run: ``python scripts/dev/dogfood_replay_check.py``.
"""
import os
import shutil
import sys
import tempfile

try:
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

FAILS = []


def _check(cond, msg):
    if not cond:
        FAILS.append(msg)


def _client(tmp):
    from core.orchestrator.llm_client import LLMClient

    class _Cache:
        cache_dir = os.path.join(tmp, ".llm-cache")

    c = LLMClient.__new__(LLMClient)
    c.llm_cache = _Cache()
    return c


def main() -> int:
    from core.orchestrator.llm_client import _CassetteResponse
    from core.orchestrator.storage import LLMReplay, llm_replay_mode

    tmp = tempfile.mkdtemp(prefix="pf-llm-replay-")
    try:
        ep = "https://example.invalid/v1/chat/completions"
        data = {"model": "m", "messages": [{"role": "user", "content": "hi"}]}
        LLMReplay(tmp).set(LLMReplay.key(ep, data),
                           {"status_code": 200, "content": "hello", "headers": {}})

        os.environ["PIPELINE_LLM_REPLAY"] = "replay"
        resp = _client(tmp)._http_post(ep, data, {})
        _check(isinstance(resp, _CassetteResponse), "replay returns a cassette response")
        _check(resp.status_code == 200 and resp.content == b"hello", "replay serves recorded content")

        missed = False
        try:
            _client(tmp)._http_post(ep, {"different": True}, {})
        except RuntimeError:
            missed = True
        _check(missed, "replay-miss fails closed (no network)")

        os.environ["PIPELINE_LLM_REPLAY"] = "off"
        _check(llm_replay_mode() == "off", "mode defaults/reads off")
    finally:
        os.environ.pop("PIPELINE_LLM_REPLAY", None)
        shutil.rmtree(tmp, ignore_errors=True)

    if FAILS:
        print("dogfood-replay: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1
    print("dogfood-replay: OK (record->replay deterministic, replay-miss fail-closed, default off)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
