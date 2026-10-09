"""BI-PF-0565: LLM-judged backlog context review (injected llm; advisory no-validator)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
os.environ.setdefault("PF_OFFLINE", "1")
os.environ.setdefault("API_ALLOW_ANON", "1")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import app  # noqa: E402
from core import backlog, context_review  # noqa: E402

ITEM = {"id": "BI-X", "title": "Add X", "objective": "Add X to Y",
        "brief": {"problem": "p", "what_adds": "w", "why": "y"},
        "in_scope": ["a"], "out_of_scope": ["b"], "affected_components": ["c"], "affected_files": ["f"],
        "approach": "do a then b", "acceptance_criteria": ["ac"], "verification": ["v"]}


def test_review_implementable():
    r = context_review.review(ITEM, llm=lambda p: '{"implementable": true, "missing": [], "reason": "good"}')
    assert r["ok"] is True and r["source"] == "llm"


def test_review_thin():
    r = context_review.review(ITEM, llm=lambda p: '{"implementable": false, "missing": ["where", "how"], "reason": "no files"}')
    assert r["ok"] is False and "where" in r["missing"]


def test_review_no_validator():
    r = context_review.review(ITEM, llm=None, fallback_llm=False)
    assert r["ok"] is None and r["source"] == "no-validator"


def test_review_unparseable():
    r = context_review.review(ITEM, llm=lambda p: "not json")
    assert r["ok"] is None and r["source"] == "llm-unparseable"


def test_api_endpoint(monkeypatch):
    monkeypatch.setattr(context_review, "review",
                        lambda it: {"ok": True, "source": "llm", "implementable": True,
                                    "missing": [], "reason": ""})
    monkeypatch.setattr(backlog, "get_epic", lambda s, p, i: {"id": i, "title": "t"})
    client = TestClient(app)
    r = client.post("/api/v1/backlog/items/BI-X/context-review", json={})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["item_id"] == "BI-X"
