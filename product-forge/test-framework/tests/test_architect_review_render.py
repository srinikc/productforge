"""Gate 1.5/2.5 decision-table renderer tests (BI-PF-1479)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))

import architect_review as ar  # noqa: E402


def _view(severity: str, text: str, status: str | None, mode: str = "design", note: str = "done"):
    findings = {s: [] for s in ar.SEVERITIES}
    findings["SUMMARY"] = ["overall summary"]
    findings[severity] = [text]
    disp = {}
    if status is not None:
        disp["sig:" + ar.finding_sig(text)] = {"status": status, "note": note}
    return {"review": {"model": "m", "sha": "abc", "findings": findings, "parsed_ok": True, "mode": mode},
            "dispositions": disp, "total": 1, "pending": 0, "blocking": []}


def test_actioned_major_is_approve_with_table():
    out = ar.render_gate_view(_view("MAJOR", "fix this", "ACTIONED", note="fixed in diff"), "design")
    assert "Gate 1.5 - Findings & Dispositions" in out
    assert "**Overall architect recommendation: APPROVE**" in out
    assert "| 1 | MAJOR | fix this | ACTIONED | fixed in diff |" in out
    assert "| # | Severity | Finding | Disposition | Response / resolution |" in out


def test_accepted_major_is_attention():
    out = ar.render_gate_view(_view("MAJOR", "trade-off", "ACCEPTED", note="accepted by HIL"), "design")
    assert "**Overall architect recommendation: APPROVE WITH ATTENTION**" in out
    assert "| 1 | MAJOR | trade-off | ACCEPTED | accepted by HIL |" in out


def test_pending_major_is_not_ready():
    out = ar.render_gate_view(_view("MAJOR", "unresolved", None), "design")
    assert "**Overall architect recommendation: NOT READY**" in out
    assert "| 1 | MAJOR | unresolved | PENDING | (no response yet) |" in out
    assert "1 blocking finding(s) pending" in out


def test_unknown_status_is_pending_fail_closed():
    out = ar.render_gate_view(_view("BLOCKER", "typo status", "ACTIONEDD"), "design")
    assert "**Overall architect recommendation: NOT READY**" in out
    assert "| 1 | BLOCKER | typo status | PENDING | done |" in out


def test_pending_minor_does_not_block():
    out = ar.render_gate_view(_view("MINOR", "small thing", None), "design")
    assert "**Overall architect recommendation: APPROVE**" in out
    assert "1 pending" in out


def test_escapes_pipes_and_newlines():
    out = ar.render_gate_view(_view("MAJOR", "a | b\nsecond line", "ACTIONED", note="x | y"), "design")
    assert "| 1 | MAJOR | a \\| b second line | ACTIONED | x \\| y |" in out


def test_diff_gate_header_and_mixed_attention():
    view = _view("BLOCKER", "gate2 blocker", "ACCEPTED", mode="diff", note="accepted")
    view["review"]["findings"]["MAJOR"] = ["major done"]
    view["dispositions"]["sig:" + ar.finding_sig("major done")] = {"status": "ACTIONED", "note": "fixed"}
    out = ar.render_gate_view(view, "diff")
    assert "Gate 2.5 - Findings & Dispositions" in out
    assert "**Overall architect recommendation: APPROVE WITH ATTENTION**" in out
    assert "| 2 | MAJOR | major done | ACTIONED | fixed |" in out


def test_overall_recommendation_is_pure_and_counts():
    verdict, counts = ar.overall_recommendation([("BLOCKER", "ACTIONED"), ("MAJOR", "SCOPE"), ("MINOR", "PENDING")])
    assert verdict == "APPROVE WITH ATTENTION"
    assert "Findings: 3" in counts and "scope 1" in counts and "pending 1" in counts
    verdict, _ = ar.overall_recommendation([("MAJOR", "PENDING"), ("BLOCKER", "ACTIONED")])
    assert verdict == "NOT READY"
    verdict, _ = ar.overall_recommendation([("MAJOR", "ACTIONED"), ("MINOR", "PENDING")])
    assert verdict == "APPROVE"


def test_gate1_check_uses_the_shared_renderer(monkeypatch, capsys):
    import gate1_check

    view = _view("MAJOR", "shared path", "ACTIONED")
    monkeypatch.setattr(gate1_check, "evaluate", lambda item: view)
    monkeypatch.setattr(ar, "render_gate_view", lambda v, m: "SHARED-TABLE")
    rc = gate1_check.main(["--item", "BI-X"])
    out = capsys.readouterr().out
    assert rc == 0 and "SHARED-TABLE" in out


def test_gate1_check_json_shape_is_unchanged(monkeypatch, capsys):
    import json

    import gate1_check

    view = _view("MAJOR", "json path", "ACTIONED")
    monkeypatch.setattr(gate1_check, "evaluate", lambda item: view)
    rc = gate1_check.main(["--item", "BI-X", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert {"ok", "item", "total", "pending", "blocking_pending", "review_sha", "model",
            "parsed_ok"} <= set(payload)
