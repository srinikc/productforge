"""Branch/item consistency guard (prevents cross-item branch contamination).

The branch name encodes the item (`feat/bi-pf-1308-...`, `chore/backlog-bi-pf-1408-delivery`). A commit on
that branch must reference the SAME item id in its message; otherwise work silently lands under the wrong
item (as happened when EDP-16 commits were merged via a BI-PF-1471 PR).

Usage:
  python scripts/dev/branch_item_check.py --message-file .git/COMMIT_EDITMSG   # commit-msg hook
  python scripts/dev/branch_item_check.py --head                               # precheck detection

Merge/sync commits are skipped. Branches without a BI id (develop, feature/<name>) only warn.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ID_RE = re.compile(r"BI-(?:PF-)?\d+", re.I)


def _git(*args: str) -> str:
    r = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True)
    return (r.stdout or "").strip()


def _norm(ids) -> set[str]:
    return {i.upper() for i in ids}


def branch_id(branch: str) -> str:
    m = ID_RE.search(branch or "")
    return m.group(0).upper() if m else ""


def message_ids(msg: str) -> set[str]:
    return _norm(ID_RE.findall(msg or ""))


def check(branch: str, message: str) -> tuple[bool, str]:
    first = (message or "").strip().splitlines()[0] if (message or "").strip() else ""
    if first.startswith("Merge ") or first.startswith("Revert "):
        return True, "merge/revert commit"
    want = branch_id(branch)
    got = message_ids(message)
    if not want:
        return True, f"branch has no item id (message ids: {sorted(got) or 'none'})"
    if not got:
        return False, f"branch {branch} is for {want} but the commit message references no item"
    if want not in got:
        return False, (f"branch {branch} is for {want} but the commit message references "
                       f"{sorted(got)} - wrong branch?")
    if len(got) > 1:
        return True, f"branch {want} matches (message also mentions {sorted(got - {want})})"
    return True, f"branch {want} matches the commit message"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Branch/item consistency guard")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--message-file")
    g.add_argument("--head", action="store_true")
    a = ap.parse_args(argv)
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    if a.message_file:
        try:
            top = Path(_git("rev-parse", "--show-toplevel") or ROOT)
            mp = Path(a.message_file)
            if not mp.is_absolute():
                mp = top / a.message_file
            msg = mp.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            print(f"branch-item: cannot read commit message: {e}")
            return 2
    else:
        msg = _git("log", "-1", "--format=%B")
    ok, why = check(branch, msg)
    if ok:
        print(f"branch-item: OK ({why})")
        return 0
    print(f"branch-item: FAIL - {why}")
    print("   fix: switch to the branch for the item in the commit message (or correct the message id)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
