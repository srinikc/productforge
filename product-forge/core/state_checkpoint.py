"""BI-PF-1257: automatic durable-state checkpoint.

Durable PF work-state (backlog items/indexes/history/counters, issues, id-blocks, portfolio registry) must
live on the integration branch so a fresh clone can resume. The runtime tree writes it, but nothing committed
it - so a fresh clone showed delivered items as ``new`` and lacked new items.

This module is the single writer of the checkpoint: it commits ONLY the durable paths and pushes them to the
integration branch via a PR (``develop`` is protected - never a direct push). Ephemeral runtime stores
(events/quality-gate/validation/github/provider-health/portfolio-state/run outputs) are excluded by
``.gitignore`` so they are never swept here.

Owner: this module (no new store; composes core.vcs + core.github/gh).
"""
import contextlib
import os
import shutil
import subprocess
import time

from core.paths import ROOT

_INTEGRATION = "develop"

# App-relative durable paths (the SSOT + derived indexes/audit that must match on every clone).
_DURABLE = (
    "data/backlog/items", "data/backlog/history",
    "data/backlog/open.json", "data/backlog/closed.json", "data/backlog/counters.json",
    "issues/items", "issues/history",
    "issues/open.json", "issues/closed.json", "issues/counters.json",
    "config/id-blocks.json",
    "data/portfolio/portfolio-registry.json",
)


def _norm(p: str) -> str:
    """Normalize a git-reported path to app-relative (strip a leading ``product-forge/``)."""
    p = p.replace("\\", "/").strip()
    if p.startswith("product-forge/"):
        p = p[len("product-forge/"):]
    return p


def _is_durable(app_rel: str) -> bool:
    a = _norm(app_rel)
    for d in _DURABLE:
        if a == d or a.startswith(d + "/"):
            return True
    return False


def _git(cwd: str, *args: str):
    return subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True)


def durable_changes() -> list:
    """App-relative durable paths with uncommitted changes in the runtime tree."""
    out = _git(str(ROOT), "status", "--porcelain").stdout
    changed = []
    for line in out.splitlines():
        if len(line) < 4:
            continue
        p = line[3:].strip()
        if " -> " in p:  # rename
            p = p.split(" -> ", 1)[1]
        if p and _is_durable(p):
            changed.append(_norm(p))
    return changed


def _copy_durable(src_app: str, dst_app: str) -> None:
    for rel in _DURABLE:
        s = os.path.join(src_app, rel)
        d = os.path.join(dst_app, rel)
        if os.path.isdir(s):
            shutil.copytree(s, d, dirs_exist_ok=True)
            for root, _dirs, files in os.walk(d):  # mirror deletions
                for f in files:
                    r = os.path.relpath(os.path.join(root, f), d)
                    if not os.path.exists(os.path.join(s, r)):
                        os.remove(os.path.join(root, f))
        elif os.path.isfile(s):
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copy2(s, d)


def _app_dir_of(wt_path: str) -> str:
    sub = os.path.join(wt_path, "product-forge")
    if os.path.isdir(sub) and os.path.isfile(os.path.join(sub, "core", "paths.py")):
        return sub
    return wt_path


def _gh() -> str:
    try:
        from core import github
        return github._gh()
    except Exception:
        return shutil.which("gh") or ""


def _land_via_pr(branch: str, note: str) -> dict:
    """Open a PR for the state branch and merge it (develop is protected)."""
    gh = _gh()
    if not gh:
        return {"ok": False, "reason": "gh unavailable"}
    title = f"[data] {note or 'durable-state checkpoint'}"
    c = subprocess.run([gh, "pr", "create", "--base", _INTEGRATION, "--head", branch,
                        "--title", title, "--body", "Automated durable-state checkpoint (BI-PF-1257)."],
                       cwd=str(ROOT), capture_output=True, text=True, timeout=180)
    number = ""
    if c.returncode == 0 and c.stdout.strip():
        number = c.stdout.strip().splitlines()[-1].rstrip("/").split("/")[-1]
    if not number:  # idempotent: reuse an existing PR for this head
        v = subprocess.run([gh, "pr", "view", branch, "--json", "number"],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=60)
        with contextlib.suppress(Exception):
            import json
            number = str(json.loads(v.stdout).get("number") or "")
    if not number:
        return {"ok": False, "reason": f"PR create failed: {((c.stderr or c.stdout) or '').strip()[:200]}"}
    m = subprocess.run([gh, "pr", "merge", number, "--merge"],
                       cwd=str(ROOT), capture_output=True, text=True, timeout=300)
    if m.returncode != 0:
        # BI-PF-1285: sync the state branch with develop, then retry the merge once.
        with contextlib.suppress(Exception):
            subprocess.run([gh, "pr", "update-branch", number], cwd=str(ROOT),
                           capture_output=True, text=True, timeout=180)
        m = subprocess.run([gh, "pr", "merge", number, "--merge"],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=300)
    if m.returncode != 0:
        # BI-PF-1285: fail cleanly - never leave a conflicting state PR/branch behind (that spam is the defect).
        with contextlib.suppress(Exception):
            subprocess.run([gh, "pr", "close", number, "--delete-branch"], cwd=str(ROOT),
                           capture_output=True, text=True, timeout=120)
        return {"ok": False, "reason": f"PR merge failed (closed): {((m.stderr or m.stdout) or '').strip()[:200]}"}
    return {"ok": True, "pr": number}


def checkpoint(note: str = "") -> dict:
    """Commit the durable work-state and push it to the integration branch (via PR). Idempotent, fail-closed."""
    from core.vcs import VCSManager
    v = VCSManager(str(ROOT))
    if not v.is_repo() or not v.has_remote():
        return {"ok": True, "skipped": "no remote"}
    changed = durable_changes()
    if not changed:
        return {"ok": True, "skipped": "clean", "files": 0}

    ts = int(time.time())
    br = f"state/{ts}"
    with contextlib.suppress(Exception):
        v.fetch()  # BI-PF-1285: base the state branch on a FRESH origin/develop (a stale base causes conflicts)
    wt = v.add_worktree(f"state-{ts}", branch=br, base=v.base_ref(_INTEGRATION))
    if not wt.get("ok"):
        return {"ok": False, "reason": f"worktree: {wt.get('error')}"}
    wt_path = wt["path"]
    try:
        _copy_durable(str(ROOT), _app_dir_of(wt_path))
        _git(wt_path, "add", "-A", "--", "product-forge/data/backlog", "product-forge/issues",
             "product-forge/config/id-blocks.json", "product-forge/data/portfolio/portfolio-registry.json")
        staged = [l for l in _git(wt_path, "status", "--porcelain").stdout.splitlines() if l.strip()]
        if not staged:
            return {"ok": True, "skipped": "no staged durable change", "files": 0}
        cm = _git(wt_path, "-c", "user.email=worker@productforge", "-c", "user.name=PF Checkpoint",
                  "commit", "-q", "-m", f"[data] {note or 'durable-state checkpoint'}")
        if cm.returncode != 0:
            return {"ok": False, "reason": f"commit failed: {cm.stderr.strip()[:200]}"}
        ps = v.push(br)
        if not ps.get("ok"):
            return {"ok": False, "reason": f"push failed: {str(ps.get('error'))[:200]}"}
        land = _land_via_pr(br, note)
        if not land.get("ok"):
            return {"ok": False, "reason": land.get("reason"), "branch": br}
        with contextlib.suppress(Exception):
            v.fetch()
        return {"ok": True, "branch": br, "pr": land.get("pr"), "files": len(changed)}
    finally:
        with contextlib.suppress(Exception):
            v.remove_worktree(wt.get("name"))
            _git(str(ROOT), "branch", "-D", br)


def _main(argv=None) -> int:
    """CLI: ``python -m core.state_checkpoint [--note TEXT]`` -> JSON result."""
    import argparse
    import json
    ap = argparse.ArgumentParser(description="Durable-state checkpoint (BI-PF-1257)")
    ap.add_argument("--note", default="durable-state checkpoint")
    a = ap.parse_args(argv)
    print(json.dumps(checkpoint(a.note), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
