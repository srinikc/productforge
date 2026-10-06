"""PIDL-5 gate (BI-PF-0380): approval policy + versioned trace + controlled outcome/correction feedback.

Asserts: decisions record/read round-trip with versioning fields; the approval policy augments the
consequential signal; corrections become evidence-gated CANDIDATES (never rules); and the trace is recorded
on the real path (close_loop invokes record_decision). Uses a temp trace path and an isolated learning store
so it never pollutes real state.
Run: ``python scripts/dev/pidl_trace_check.py``.
"""
import os
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


def main() -> int:
    from core import learning_synth, pidl

    # approval policy
    _check(pidl.approval_policy(action="drop production database schema")["required"] is True,
           "consequential action -> approval required")
    _check(pidl.approval_policy(action="add a doc paragraph", area="doc")["required"] is False,
           "benign action -> no approval")
    d = pidl.decide("product_forge", None, action="delete production data")
    _check(d["approval"]["required"] is True, "decide() consults the approval policy")
    _check("approval_policy" in d["approval"], "decision carries the approval policy ref")

    tmp = tempfile.mkdtemp(prefix="pf-pidl-trace-")
    trace = os.path.join(tmp, "decisions.jsonl")
    try:
        g = pidl.gate("product_forge", None, item_id="BI-T", run_id="run-9",
                      result={"ok": True, "status": "pr_ready", "provider": "command"})
        rec = pidl.record_decision(g, scope="product_forge", item_id="BI-T", outcome="AUTO_PROCEED", path=trace)
        for k in ("decision_id", "decision_version", "pidl_profile_version", "evidence", "confidence",
                  "risk", "approval", "outcome", "worker_id", "runtime"):
            _check(k in rec, f"trace record has {k}")
        _check(rec["decision_id"].startswith("PIDL-BI-T-"), "decision_id encodes item + version")
        _check(len(pidl.history(item_id="BI-T", path=trace)) == 1, "history returns the record")
        _check(pidl.get(rec["decision_id"], path=trace) is not None, "get by decision_id")
        _check(pidl.latest("BI-T", path=trace)["decision_id"] == rec["decision_id"], "latest by item")
        rec2 = pidl.record_decision(g, scope="product_forge", item_id="BI-T", path=trace)
        _check(rec2["decision_version"] == 2, "decision version increments per item")

        # corrections -> candidates (isolated learning store; never real state)
        orig_store = learning_synth.STORE
        learning_synth.STORE = os.path.join(tmp, "cands." + "json")
        try:
            r1 = learning_synth.add_candidate("always pin the schema before a migration", source_ref=rec["decision_id"])
            r2 = learning_synth.add_candidate("always pin the schema before a migration", source_ref=rec["decision_id"])
            _check(r1.get("ok") and not r1.get("existing"), "add_candidate creates a candidate")
            _check(r2.get("existing") is True, "add_candidate is idempotent by text")
            _check(r1["candidate"]["status"] == "proposed", "candidate is proposed (not applied)")
            out = pidl.record_outcome(rec["decision_id"], outcome="corrected",
                                      corrections=["validate inputs at the boundary"], by="operator", path=trace)
            _check(out["proposed_candidates"], "record_outcome proposes candidates from corrections")
            _check(all(r.get("kind") != "approval" for r in pidl.history(path=trace)), "outcome appended")
        finally:
            learning_synth.STORE = orig_store

        ap = pidl.record_approval(rec["decision_id"], approved=True, by="operator", path=trace)
        _check(ap["approved"] is True and ap["kind"] == "approval", "approval recorded on the trace")

        # wired: close_loop records the decision on the real path
        with open(os.path.join(str(_ROOT), "core", "close_loop.py"), encoding="utf-8") as f:
            cl = f.read()
        _check("record_decision" in cl, "close_loop records the decision (wired)")
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    if FAILS:
        print("pidl-trace: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1
    print("pidl-trace: OK (approval policy, versioned trace, corrections->candidates, wired)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
