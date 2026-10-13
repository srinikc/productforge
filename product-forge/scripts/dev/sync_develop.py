"""BI-PF-1290 / BI-PF-1318: fold ``origin/develop`` into the CURRENT branch - a per-worker sync
(merge, never rebase/reset).

Why per-worker and not a background job: git state is per working directory, so a folder-local job cannot span
sessions and would race the editor (IS-PF-0036). Each session runs this often (at task start + every commit and
push) so merges stay SMALL. The derived merge drivers (``merge=pf-derived``, see ``.gitattributes``) auto-resolve
the shared backlog files, so in practice only SOURCE files can conflict - and those fail closed (abort + report).

Usage (from ``product-forge/``):
  python scripts/dev/sync_develop.py              # fetch + merge origin/develop into the current branch
  python scripts/dev/sync_develop.py --check       # report behind/ahead only (no writes); exit 1 if behind
  python scripts/dev/sync_develop.py --pre-commit  # hook mode: if it merged, exit 1 -> re-run git commit
  python scripts/dev/sync_develop.py --pre-push    # hook mode: if it merged, exit 1 -> re-run git push

Hook mode never leaves a half-merge: it MERGES develop as its own clean commit and then exits non-zero, so the
caller re-runs its command (the merge is included the second time, when it is already up to date).
"""
import argparse
import os
import subprocess
import sys

_INTEGRATION = "develop"


def _git(*args: str):
    r = subprocess.run(["git", *args], capture_output=True, text=True)
    return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()


def _behind_ahead(remote_ref: str):
    rc, out, _ = _git("rev-list", "--left-right", "--count", f"{remote_ref}...HEAD")
    if rc != 0 or not out:
        return 0, 0
    behind, ahead = (out.split() + ["0", "0"])[:2]
    return int(behind), int(ahead)


def _merge_in_progress() -> bool:
    rc, out, _ = _git("rev-parse", "-q", "--verify", "MERGE_HEAD")
    return rc == 0 and bool(out)


def _pf_root() -> str:
    _, top, _ = _git("rev-parse", "--show-toplevel")
    cand = os.path.join(top or os.getcwd(), "product-forge")
    return cand if os.path.isfile(os.path.join(cand, "core", "paths.py")) else ""


def _refresh_docs() -> None:
    """A merge may have changed ``data/backlog`` -> keep the generated docs fresh inside the merge commit
    (a `git merge` commit does not run the pre-commit hook, so the docs-fresh gate would otherwise fail)."""
    root = _pf_root()
    if not root:
        return
    for s in ("gen_backlog_summary.py", "gen_docs_index.py"):
        subprocess.run([sys.executable, os.path.join("scripts", "dev", s)], cwd=root,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    docs = ["product-forge/docs/BACKLOG-SUMMARY.md", "product-forge/docs/documentation-index.html"]
    _, dirty, _ = _git("status", "--porcelain", "--", *docs)
    if dirty.strip():
        _git("add", *docs)
        _git("commit", "--amend", "--no-edit")   # fold the regenerated docs into the merge commit


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Merge origin/develop into the current branch (per-worker sync)")
    ap.add_argument("--check", action="store_true", help="report behind/ahead only; exit 1 if behind")
    ap.add_argument("--pre-push", action="store_true", help="hook mode: exit 1 after a merge (re-run push)")
    ap.add_argument("--pre-commit", action="store_true", help="hook mode: exit 1 after a merge (re-run commit)")
    ap.add_argument("--branch", default=_INTEGRATION, help="integration branch (default: develop)")
    a = ap.parse_args(argv)
    hook = a.pre_push or a.pre_commit

    remote_ref = f"origin/{a.branch}"
    rc, _, err = _git("fetch", "origin", a.branch)
    if rc != 0:
        print(f"sync: could not fetch {remote_ref} ({err or 'offline?'}) - nothing to do", file=sys.stderr)
        return 0 if hook else 1

    behind, ahead = _behind_ahead(remote_ref)
    if behind == 0:
        if not hook:
            print(f"sync: already up to date with {remote_ref} (ahead {ahead})")
        return 0
    if a.check:
        print(f"sync: BEHIND {remote_ref} by {behind} commit(s), ahead {ahead} - "
              "run: python scripts/dev/sync_develop.py")
        return 1

    print(f"sync: merging {remote_ref} ({behind} commit(s)) into the current branch ...")
    rc, _, err = _git("merge", "--no-edit", "--autostash", remote_ref)   # autostash -> safe on a dirty tree
    if rc != 0:
        if _merge_in_progress():
            _, unmerged, _ = _git("diff", "--name-only", "--diff-filter=U")
            _git("merge", "--abort")
            files = ", ".join(unmerged.splitlines()) or "(unknown)"
            print(f"sync: SOURCE conflict in: {files}", file=sys.stderr)
            print(f"sync: aborted the merge - your work is intact. "
                  f"Resolve manually: git merge {remote_ref}", file=sys.stderr)
            return 2
        print(f"sync: merge refused ({err or 'unknown'}) - commit/stash local changes and retry", file=sys.stderr)
        return 1
    print("sync: merged cleanly (the derived backlog files auto-resolve via the merge driver).")
    _refresh_docs()
    if hook:
        rerun = "git push" if a.pre_push else "git commit"
        print(f"sync: re-run '{rerun}' to include the merge.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
