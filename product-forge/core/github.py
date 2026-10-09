"""ENG-5: GitHub / PR / CI orchestration (Product Forge-owned).

GitHub owns the repository/branches/commits/PRs/reviews/CI/checks/merge state (updated plan §17, §28);
Product Forge orchestrates the lifecycle. This module:

  * assembles **run-bound PR evidence** from the canonical stores (it never duplicates them),
  * creates the PR through the OPTIONAL ``gh`` adapter (a client; PF degrades gracefully without it),
  * reads CI status through the same adapter,
  * keeps a local, append-only PR record store (single writer) so the lifecycle lives in PF regardless.

NEVER: force-push shared branches, bypass required CI, disable tests, overwrite another worktree, retarget a
validation run silently, or alter evidence after the fact. Those are encoded as ``POLICY`` and guards here.
"""
import json
import os
import shutil
import subprocess
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.paths import PRODUCTS_DIR, ROOT

FILENAME = "pr-records.json"
POLICY = (
    "never force-push shared branches",
    "never bypass required CI",
    "never disable tests for a pass",
    "never overwrite another worktree",
    "never silently retarget a validation run",
    "never alter evidence after the fact",
)


def _norm_scope(scope: str) -> str:
    return "product_forge" if str(scope) in ("portfolio", "product_forge") else "project"


def _dir(scope: str, project: Optional[str] = None) -> str:
    if _norm_scope(scope) == "product_forge":
        return os.path.join(ROOT, "github")
    return os.path.join(PRODUCTS_DIR, str(project or "_unknown"), "github")


def path(scope: str, project: Optional[str] = None) -> str:
    return os.path.join(_dir(scope, project), FILENAME)


def _lock(d: str) -> str:
    os.makedirs(d, exist_ok=True)
    lp = os.path.join(d, ".lock")
    for _ in range(50):
        try:
            fd = os.open(lp, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return lp
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(lp) > 300:
                    os.remove(lp)
                    continue
            except Exception:
                pass
            time.sleep(0.1)
    raise TimeoutError("could not acquire pr-record lock")


def _unlock(lp: str) -> None:
    try:
        os.remove(lp)
    except Exception:
        pass


def _read(scope: str, project: Optional[str] = None) -> Dict[str, Any]:
    try:
        with open(path(scope, project), encoding="utf-8-sig") as f:
            d = json.load(f)
        if isinstance(d, dict) and isinstance(d.get("prs"), list):
            return d
    except Exception:
        pass
    return {"prs": []}


def _write(scope: str, project: Optional[str], data: Dict[str, Any]) -> None:
    p = path(scope, project)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, p)


def _gh() -> str:
    return shutil.which("gh") or ""


def _hash(obj: Any) -> str:
    import hashlib
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def available() -> Dict[str, Any]:
    """Adapter availability (``gh`` is optional - PF never depends on it)."""
    return {"gh": bool(_gh()), "remote": "origin", "policy": list(POLICY)}


def create_repo(name: str, *, private: bool = True, owner: str = "", description: str = "") -> Dict[str, Any]:
    """Create a GitHub repository (OPTIONAL adapter). ``gh`` preferred; else REST via GITHUB_TOKEN.

    Fail-closed: returns ``{ok: False, reason}`` when neither is available; never raises.
    """
    name = str(name or "").strip()
    if not name:
        return {"ok": False, "reason": "empty repo name"}
    full = f"{owner}/{name}" if owner else name
    gh = _gh()
    if gh:
        args = [gh, "repo", "create", full, "--private" if private else "--public"]
        if description:
            args += ["--description", description]
        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=120)
            if r.returncode == 0:
                url = (r.stdout or "").strip().splitlines()[-1] if r.stdout else ""
                return {"ok": True, "adapter": "gh", "full_name": full,
                        "url": url or f"https://github.com/{full}"}
            return {"ok": False, "adapter": "gh", "reason": ((r.stderr or r.stdout) or "").strip()[:200]}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "adapter": "gh", "reason": type(e).__name__}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    if token:
        import requests
        api = f"https://api.github.com/orgs/{owner}/repos" if owner else "https://api.github.com/user/repos"
        try:
            r = requests.post(api, json={"name": name, "private": bool(private), "description": description},
                              headers={"Authorization": f"Bearer {token}",
                                       "Accept": "application/vnd.github+json"}, timeout=60)
            if r.status_code in (200, 201):
                d = r.json() or {}
                return {"ok": True, "adapter": "rest", "full_name": d.get("full_name", full),
                        "url": d.get("html_url", "")}
            return {"ok": False, "adapter": "rest", "reason": f"HTTP {r.status_code}"}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "adapter": "rest", "reason": type(e).__name__}
    return {"ok": False, "reason": "no gh CLI and no GITHUB_TOKEN/GH_TOKEN"}


def build_evidence(project: str, project_dir: str, *, run_id: str = "", task_id: str = "",
                   base_sha: str = "", head_sha: str = "", backlog_ref: str = "") -> Dict[str, Any]:
    """Assemble run-bound PR evidence from the canonical stores (read-only aggregation)."""
    ev: Dict[str, Any] = {"run_id": run_id, "task_id": task_id, "commit_sha": head_sha,
                          "base_sha": base_sha, "backlog": backlog_ref, "generated_at": datetime.now().isoformat()}
    try:
        from core import close_loop
        ev["validation"] = close_loop.verify_run(project_dir, run_id=run_id) if run_id \
            else close_loop.verify_run(project_dir)
    except Exception:
        ev["validation"] = {}
    try:
        from core import qa_report
        gng = qa_report.load(project)
        ev["tests"] = {"go_no_go": gng.get("decision", ""), "qir": gng.get("qir", {})}
    except Exception:
        ev["tests"] = {}
    try:
        from core import artifact_store
        summ = artifact_store.get_artifact_summary(project_dir)
        ev["artifacts"] = {"total": summ.get("total_artifacts", 0), "project": summ.get("project", project)}
    except Exception:
        ev["artifacts"] = {}
    issues_open, issues_closed = [], []
    try:
        from core import issues as _issues
        issues_open = _issues.list_open("project", project)
        issues_closed = _issues.list_closed("project", project)
    except Exception:
        pass
    ev["issues"] = [i.get("id") for i in issues_open]
    ev["rcca"] = [i.get("id") for i in issues_closed if i.get("rcca")]
    ev["security"] = [i.get("id") for i in issues_open
                      if str(i.get("kind")) in ("risk", "bug") and str(i.get("severity", "")).lower() in ("high", "critical")]
    return ev


def record_pr(scope: str, project: Optional[str], record: Dict[str, Any]) -> Dict[str, Any]:
    """Append-only PR record (evidence is immutable: records are never updated)."""
    d = _lock(_dir(scope, project))
    try:
        store = _read(scope, project)
        store["prs"].append(record)
        _write(scope, project, store)
        return record
    finally:
        _unlock(d)


def list_prs(scope: str, project: Optional[str] = None) -> List[Dict[str, Any]]:
    return list(_read(scope, project).get("prs", []))


def get_pr(scope: str, project: Optional[str], number: Any) -> Optional[Dict[str, Any]]:
    n = str(number)
    return next((p for p in list_prs(scope, project) if str(p.get("number")) == n), None)


def create_pr(project: str, project_dir: str, *, title: str, body: str = "", base: str = "", head: str = "",
              run_id: str = "", task_id: str = "", backlog_ref: str = "",
              scope: str = "project") -> Dict[str, Any]:
    """Push-ready -> PR orchestration. Guarded; degrades to a local 'pr_ready' record without ``gh``."""
    from core.vcs import VCSManager
    v = VCSManager(project_dir)
    if not v.is_repo():
        return {"ok": False, "error": "not a git repository"}
    head = str(head or v.current_branch() or "")
    base = str(base or v.integration_branch or "")
    if not head:
        return {"ok": False, "error": "no head branch"}
    if v.is_protected(head):
        return {"ok": False, "error": f"refusing to open a PR from protected branch {head!r}"}
    if head == base:
        return {"ok": False, "error": f"head and base are the same branch {head!r}"}
    commit_sha = v.head_commit(head)
    evidence = build_evidence(project, project_dir, run_id=run_id, task_id=task_id,
                              base_sha=v.head_commit(base), head_sha=commit_sha, backlog_ref=backlog_ref)
    number, url, status = "", "", "pr_ready"
    gh = _gh()
    if gh:
        text = f"{body}\n\n---\nPF evidence: run_id={run_id} task_id={task_id} commit={commit_sha[:10]}"
        try:
            r = subprocess.run([gh, "pr", "create", "--base", base, "--head", head,
                                "--title", title or f"{task_id or head}", "--body", text],
                               cwd=project_dir, capture_output=True, text=True, timeout=120)
            if r.returncode == 0:
                url = (r.stdout or "").strip().splitlines()[-1] if r.stdout else ""
                number = url.rstrip("/").split("/")[-1] if url else ""
                status = "created"
            else:
                status, body = "pr_ready", body
        except Exception:
            status = "pr_ready"
    record = {"project": project, "number": number, "url": url, "head": head, "base": base,
              "commit_sha": commit_sha, "task_id": task_id, "run_id": run_id, "backlog_ref": backlog_ref,
              "status": status, "adapter": "gh" if gh else "none",
              "evidence_hash": _hash(evidence), "created_at": datetime.now().isoformat()}
    record_pr(scope, project, record)
    return {"ok": True, "pr": record, "evidence": evidence}


def ci_status(project_dir: str, number: Any = "") -> Dict[str, Any]:
    """CI checks for a PR via the optional adapter; ``available: false`` when ``gh`` is absent."""
    gh = _gh()
    if not gh:
        return {"available": False, "checks": [], "reason": "gh CLI not installed (adapter optional)"}
    args = [gh, "pr", "checks"]
    if str(number):
        args.append(str(number))
    try:
        r = subprocess.run(args, cwd=project_dir, capture_output=True, text=True, timeout=120)
        return {"available": True, "checks": (r.stdout or "").splitlines(), "ok": r.returncode == 0}
    except Exception as e:
        return {"available": False, "checks": [], "reason": str(e)}
