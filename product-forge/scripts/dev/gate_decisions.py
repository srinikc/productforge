"""Gate decision recording + Gate 2 status (BI-PF-1469 tooling).

Kept OUT of core/backlog.py so the shipped control-plane module does not import git/dev tooling: core
delegates here lazily at the Gate 2 boundary (a few lines), and all git/evidence logic lives in scripts/dev.

* gate2_status(item, eid): the same predicate as gate2_completion_check;
* record_gate_decision(...): validates evidence + findings, appends a seq-bound decision.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "scripts" / "dev")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _ar():
    import architect_review
    return architect_review


def _dp():
    import disposition_policy
    return disposition_policy


def _gp():
    import gate_predicates
    return gate_predicates


def gate2_status(item: dict, eid: str) -> tuple[bool, str]:
    try:
        ar, gp = _ar(), _gp()
        view = ar.gate_view(eid, "diff")
        skip = (ar._config().get("size_gate") or {}).get("skip_globs") or ["docs/**", "**/*.md", "config/**"]
        docs_only = gp.is_docs_only(ar.changed_files(), skip)
        if view is None and not docs_only:
            return False, "NO_DIFF_EVIDENCE"
        sha = ((view or {}).get("review") or {}).get("sha") if view else "docs-only"
        return gp.gate2_ready(item, str(sha or ""), view, allow_missing_view=view is None)
    except Exception as e:  # fail closed
        return False, f"GATE_ERROR:{e}"


def record_gate_decision(backlog, scope: str, project: str | None, eid: str, gate: int, decision: str,
                         by: str, note: str = "", hil_confirmed: bool = False):
    ar, gp = _ar(), _gp()
    item = backlog.get_epic(scope, project, eid) or {}
    if not item:
        return None
    if int(gate) not in (1, 2):
        print(f"[Backlog] refusing gate {gate} decision for {eid}: only gates 1 and 2 exist")
        return None
    if not hil_confirmed:
        print(f"[Backlog] refusing gate {gate} decision for {eid}: requires explicit HIL confirmation")
        return None
    if not str(by).startswith("hil:"):
        print(f"[Backlog] refusing gate {gate} decision for {eid}: by must be hil:<actor>")
        return None
    if str(gate) not in ("1", "1.5", "2", "2.5"):
        print(f"[Backlog] refusing gate {gate} decision for {eid}: unknown gate")
        return None
    mode = "design" if str(gate) in ("1", "1.5") else "diff"
    modes = [mode] if str(gate) in ("1", "1.5") else ["design", "diff"]
    if str(gate) == "2":
        import ac_policy
        bad_ac = ac_policy.problems(item)
        if bad_ac:
            print(f"[Backlog] refusing gate 2 decision for {eid}: {'; '.join(bad_ac)}")
            return None
    for m in modes:
        for prob in _dp().problems(item, m, lambda i: backlog.get_epic(scope, project, i)):
            print(f"[Backlog] refusing gate {gate} decision for {eid}: {prob}")
            return None
    if str(decision).upper() not in gp.APPROVED:
        print(f"[Backlog] refusing gate {gate} decision for {eid}: only APPROVE/APPROVE_WITH_ATTENTION")
        return None
    gate = int(gate)
    view = ar.gate_view(eid, "design" if gate == 1 else "diff")
    if view is None:
        if gate == 1:
            print(f"[Backlog] refusing gate 1 decision for {eid}: no Gate 1.5 design evidence")
            return None
        skip = (ar._config().get("size_gate") or {}).get("skip_globs") or ["docs/**", "**/*.md", "config/**"]
        if not gp.is_docs_only(ar.changed_files(), skip):
            print(f"[Backlog] refusing gate 2 decision for {eid}: no Gate 2.5 evidence and change is not docs-only")
            return None
    if view is not None and (not view.get("parsed_ok", True) or view.get("blocking")):
        print(f"[Backlog] refusing gate {gate} decision for {eid}: findings are pending/unparsable")
        return None
    sha = ar.design_sha(item) if gate == 1 else str(((view or {}).get("review") or {}).get("sha") or "docs-only")
    try:
        import gate_package
        text = gate_package.render(eid, int(gate))
        print(text)
        gate_package.persist(eid, int(gate), text)
    except Exception as e:
        print(f"[Backlog] refusing gate {gate} decision for {eid}: cannot render gate package: {e}")
        return None
    dec = list(item.get("decisions") or [])
    dec.append({"at": datetime.now(timezone.utc).isoformat(), "by": by, "decision": str(decision).upper(),
                "gate": gate, "findings_sha": sha, "findings_digest": gp.findings_digest(view),
                "seq": len(dec) + 1, "note": note, "hil_confirmed": True})
    res = backlog.update(scope, project, eid, decisions=dec)
    try:
        from core import execution_trail as trail
        trail.record(eid, f"gate{gate}", "pass",
                     summary=f"Gate {gate} {str(decision).upper()} by {by}",
                     refs={"findings_sha": dec[-1].get("findings_sha"), "findings_digest": dec[-1].get("findings_digest")},
                     actor=str(by))
    except Exception as e:
        try:
            from core import execution_trail as _t
            _t.write_failure(f"gate{gate}", e, eid)
        except Exception:
            pass
        print(f"[Gates] WARNING execution trail write failed: {e}")
    return res
