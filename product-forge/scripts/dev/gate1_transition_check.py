"""BI-PF-1466: machine-enforce Gate 1 at the backlog ``new -> in_progress`` transition.

Gate 1 is the design/HIL approval point. This deterministic precheck gate inspects the backlog items that
transitioned to ``in_progress`` in the change set and, when a Gate 1.5 (design) review exists for that item,
requires **no pending BLOCKER/MAJOR** (and parseable evidence). Items with no design review are grandfathered
(reported, not blocked) so legacy/backlog-only items keep flowing.

Run: python scripts/dev/gate1_transition_check.py   (wired into precheck fast)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts" / "dev") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts" / "dev"))
import architect_review as ar  # noqa: E402

_MARK = "/data/backlog/items/"


def _git(*args: str) -> str:
    r = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True)
    return (r.stdout or "").strip()


def _repo_root() -> str:
    return _git("rev-parse", "--show-toplevel") or str(ROOT)


def _load(path_rel_repo: str) -> dict:
    try:
        return json.loads(Path(_repo_root(), path_rel_repo).read_text(encoding="utf-8"))
    except Exception:
        return {}


def transitions(base: str = "", repo_root: str = "") -> list[str]:
    """Item ids that moved to ``in_progress`` in the committed change set (merge-base..HEAD)."""
    base = base or _git("merge-base", "develop", "HEAD") or "origin/develop"
    rr = repo_root or _repo_root()
    changed = _git("diff", "--name-only", f"{base}..HEAD").splitlines()
    out = []
    for rel in changed:
        rel = rel.replace("\\", "/")
        if _MARK not in rel or not rel.endswith(".json"):
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


def check(item_ids: list[str], gate_view=None) -> list[tuple[str, str]]:
    """Return [(item_id, problem)] for reviewed items with pending BLOCKER/MAJOR or unparsable evidence."""
    gv = gate_view or ar.gate_view
    problems: list[tuple[str, str]] = []
    for iid in item_ids:
        view = gv(iid, "design")
        if view is None:
            continue  # grandfathered: no Gate 1.5 evidence
        if not view.get("parsed_ok", True):
            problems.append((iid, "Gate 1.5 evidence could not be parsed (indeterminate)"))
        elif view.get("blocking"):
            problems.append((iid, f"{len(view['blocking'])} pending BLOCKER/MAJOR at Gate 1"))
    return problems


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description="Gate 1 transition enforcement (BI-PF-1466)").parse_args(argv)
    ids = transitions()
    problems = check(ids)
    reviewed = [i for i in ids if ar.gate_view(i, "design") is not None]
    if problems:
        print(f"gate1-transition: FAIL ({len(problems)} item(s) moved to in_progress with unresolved Gate 1 findings)")
        for iid, why in problems:
            print(f"   - {iid}: {why}")
        print("   fix: python scripts/dev/gate1_check.py --item <ID>  (disposition all BLOCKER/MAJOR)")
        return 1
    print(f"gate1-transition: OK ({len(ids)} transition(s); {len(reviewed)} reviewed, "
          f"{len(ids) - len(reviewed)} grandfathered without a design review)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
