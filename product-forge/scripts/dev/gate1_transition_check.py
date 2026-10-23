"""BI-PF-1466/1469: hard Gate 1 at the backlog `new -> in_progress` transition.

Every item entering in_progress must have:
  * committed Gate 1.5 (design) evidence for the CURRENT design sha, parseable, zero PENDING BLOCKER/MAJOR;
  * a Gate 1 decision (gate=1, APPROVE/APPROVE_WITH_ATTENTION, by hil:<actor>) bound to that design sha and
    to the current findings digest.

No silent grandfathering: only config/gate-baseline.json entries with a valid, unexpired date are exempt
(printed as ALLOW/BASELINE). `--report` is the explicit dry-run (exit 0) for rollout/impact analysis.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "scripts" / "dev"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import architect_review as ar  # noqa: E402
from gate1_check import evaluate  # noqa: E402  (ONE predicate, no duplication)
from core import gate_predicates as gp  # noqa: E402

_MARK = "/data/backlog/items/"


def _git(*args: str) -> str:
    r = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True)
    return (r.stdout or "").strip()


def _repo_root() -> str:
    return _git("rev-parse", "--show-toplevel") or str(ROOT)


def _load(rel_repo: str) -> dict:
    try:
        return json.loads(Path(_repo_root(), rel_repo).read_text(encoding="utf-8"))
    except Exception:
        return {}


def transitions(base: str = "") -> list[str]:
    base = base or _git("merge-base", "develop", "HEAD") or "origin/develop"
    out = []
    for rel in _git("diff", "--name-only", f"{base}..HEAD").splitlines():
        rel = rel.replace("\\", "/")
        if _MARK not in rel or not rel.endswith(".json") or rel.endswith("open.json") or rel.endswith("closed.json"):
            continue
        cur = _load(rel)
        if str(cur.get("status") or "") != "in_progress":
            continue
        prev_raw = _git("show", f"{base}:{rel}")
        try:
            prev = json.loads(prev_raw) if prev_raw else {}
        except Exception:
            prev = {}
        if str(prev.get("status") or "") != "in_progress":
            out.append(str(cur.get("id") or Path(rel).stem))
    return sorted(set(out))


def _self_test() -> int:
    """Predicate matrix: allow, no decision, no evidence, stale sha, unauthorized approver."""
    from core import gate_predicates as gp
    view = {"parsed_ok": True, "blocking": [], "dispositions": {"sig:a": {"status": "ACTIONED"}},
            "review": {"sha": "abc", "at": "2026-01-01T00:00:00+00:00"}}
    digest = gp.findings_digest(view)
    good = {"decisions": [{"gate": 1, "decision": "APPROVE", "by": "hil:test",
                           "at": "2026-01-02T00:00:00+00:00",
                           "findings_sha": "abc", "findings_digest": digest, "seq": 1}]}
    cases = [
        ("allow", good, "abc", view, True, "OK"),
        ("no-decision", {"decisions": []}, "abc", view, False, "NO_GATE_APPROVAL"),
        ("no-evidence", good, "abc", None, False, "NO_EVIDENCE"),
        ("stale", good, "zzz", view, False, "STALE_APPROVAL"),
        ("unauthorized", {"decisions": [dict(good["decisions"][0], by="system:auto")]}, "abc", view,
         False, "UNAUTHORIZED_APPROVER"),
    ]
    bad = []
    for name, it, sha, v, want_ok, want_reason in cases:
        ok, reason = gp.approval(it, 1, sha, v)
        if ok != want_ok or reason != want_reason:
            bad.append(f"{name}: got {ok}/{reason}, want {want_ok}/{want_reason}")
    if bad:
        for b in bad:
            print("gate1 self-test: FAIL - " + b)
        return 1
    print("gate1: self-test OK (allow, no-decision, no-evidence, stale, unauthorized)")
    return 0


def check(ids: list[str]) -> list[tuple[str, str]]:
    problems: list[tuple[str, str]] = []
    for iid in ids:
        state = gp.baseline_state(iid)
        if state == "ACTIVE":
            print(f"gate1: ALLOW item={iid} reason=BASELINE")
            continue
        if state in {"EXPIRED", "UNKNOWN"}:
            problems.append((iid, f"BASELINE_{state}"))
            continue
        view = evaluate(iid)
        if view is None:
            problems.append((iid, "NO_EVIDENCE"))
            continue
        if not view.get("parsed_ok", True):
            problems.append((iid, "UNPARSABLE"))
            continue
        if view.get("blocking"):
            problems.append((iid, "PENDING_FINDINGS"))
            continue
        item = ar._get_item(iid)
        sha = ar.design_sha(item)
        evidence_sha = str(((view.get("review") or {}).get("sha")) or "")
        if evidence_sha != sha:
            problems.append((iid, "STALE_EVIDENCE"))
            continue
        ok, reason = gp.approval(item, 1, sha, view)
        if not ok:
            problems.append((iid, reason))
        else:
            print(f"gate1: ALLOW item={iid} reason=OK sha={sha}")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Gate 1 transition enforcement (BI-PF-1466/1469)")
    ap.add_argument("--report", action="store_true", help="dry-run: report only, exit 0")
    ap.add_argument("--self-test", action="store_true", help="run the predicate negative matrix")
    ap.add_argument("--base", default="", help="git base (default merge-base develop)")
    a = ap.parse_args(argv)
    if a.self_test and _self_test() != 0:
        return 1
    base_problems = gp.baseline_problems()
    for b in base_problems:
        print(f"gate1: BASELINE_CONFIG {b}")
    ids = transitions(a.base)
    problems = check(ids)
    if base_problems and not a.report:
        print(f"gate1-transition: FAIL ({len(base_problems)} baseline governance problem(s))")
        return 1
    if a.report:
        print(f"gate1: REPORT {len(ids)} transition(s), {len(problems)} would fail")
        for iid, why in problems:
            print(f"gate1: DENY item={iid} reason={why}")
        return 0
    if problems:
        print(f"gate1-transition: FAIL ({len(problems)} item(s) lack a valid Gate 1.5/Gate 1)")
        for iid, why in problems:
            print(f"gate1: DENY item={iid} reason={why}")
        print("   fix: architect_review run --mode design; disposition; record a gate=1 decision")
        return 1
    print(f"gate1-transition: OK ({len(ids)} transition(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
