"""BI-PF-0665: grooming runs the advisory AI context review and stores it on analysis.context_review."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
os.environ.setdefault("PF_OFFLINE", "1")

from core import backlog, context_review, grooming  # noqa: E402

ITEM = {"id": "BI-Z", "title": "Add Z", "analysis": {},
        "brief": {"problem": "p", "what_adds": "w", "source": "authored"}}


def test_groom_attaches_context_review(monkeypatch):
    store = {"analysis": {}}

    monkeypatch.setattr(grooming, "_gather_context", lambda s, p, it: {})
    monkeypatch.setattr(grooming, "_run_ai", lambda it, ctx, proj, product: {"architecture_fit": "REUSE"})
    monkeypatch.setattr(grooming, "guidelines", lambda: {"context_review": {"enabled": True}, "default_mode": "ai"})
    monkeypatch.setattr(grooming, "_mark_duplicates", lambda s, p, it, ctx: [])
    monkeypatch.setattr(grooming, "_same_project_dups", lambda s, p, it, ctx: [])
    monkeypatch.setattr(context_review, "review",
                        lambda it, **k: {"ok": True, "source": "llm", "missing": [], "reason": ""})
    monkeypatch.setattr(backlog, "get_epic", lambda s, p, i: dict(ITEM, analysis=store["analysis"]))

    def _set_analysis(s, p, i, **kw):
        store["analysis"] = dict(store["analysis"]); store["analysis"].update(kw.get("analysis") or {})
        return dict(ITEM)

    def _update(s, p, i, **kw):
        if "analysis" in kw:
            store["analysis"] = dict(kw["analysis"])
        return dict(ITEM)

    monkeypatch.setattr(backlog, "set_analysis", _set_analysis)
    monkeypatch.setattr(backlog, "update", _update)
    monkeypatch.setattr(backlog, "set_priority", lambda *a, **k: None)
    monkeypatch.setattr(backlog, "set_dependencies", lambda *a, **k: None)

    grooming.groom("product_forge", None, "BI-Z", mode="ai")
    assert store["analysis"].get("context_review", {}).get("ok") is True
