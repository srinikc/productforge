"""Stage-0 product repo setup: recommend a GitHub repo name, confirm, create, connect.

Composes existing owners only (``core.github.create_repo``, ``core.vcs.connect_remote``,
``core.project_store``). **Fail-closed**: nothing is created unless ``confirm=True``; when ``gh``/token is
unavailable it degrades to **local-only** with a clear reason (never silent). No new store/engine.
"""
import os
import re
from typing import Any, Optional


def _slug(text: str, maxlen: int = 48) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")
    return s[:maxlen].strip("-")


def recommend_name(project: str, idea: str = "") -> str:
    """A recommended GitHub repo name from the idea (fallback: the project name)."""
    return _slug(idea or "") or _slug(project or "") or "product"


def remote_url(project_dir: str) -> str:
    try:
        from core.vcs import VCSManager
        v = VCSManager(project_dir)
        return v._git(["config", "--get", f"remote.{v.remote}.url"]).get("out", "")
    except Exception:
        return ""


def status(project: str, project_dir: str, idea: str = "") -> dict:
    return {"project": project, "recommended_name": recommend_name(project, idea),
            "remote_url": remote_url(project_dir)}


def setup(project: str, project_dir: str, *, name: str = "", idea: str = "", private: bool = True,
          confirm: bool = False, owner: str = "", create: bool = True) -> dict:
    """Confirm -> (optionally) create the GitHub repo -> connect the product remote.

    ``confirm=False`` (default) returns the recommendation WITHOUT creating (caller shows it and re-calls
    with ``confirm=True``). Fail-closed local-only when gh/token is unavailable.
    """
    name = str(name or "").strip() or recommend_name(project, idea)
    out: dict[str, Any] = {"project": project, "name": name, "private": bool(private), "created": False,
                           "connected": False, "url": "", "confirmed": bool(confirm)}
    if not confirm:
        out["reason"] = "confirmation required"
        return out
    if create:
        from core import github
        r = github.create_repo(name, private=private, owner=owner)
        if not r.get("ok"):
            out.update({"reason": r.get("reason") or "create failed", "adapter": r.get("adapter", ""),
                        "local_only": True})
            return out
        out.update({"created": True, "url": r.get("url", ""), "full_name": r.get("full_name", name),
                    "adapter": r.get("adapter", "")})
    if out["url"]:
        from core.vcs import VCSManager
        c = VCSManager(project_dir).connect_remote(out["url"])
        out["connected"] = bool(c.get("ok"))
    try:
        from core import project_store
        project_store.update_section(project, "repo",
                                     {"name": name, "url": out["url"], "private": bool(private)},
                                     os.path.dirname(os.path.abspath(project_dir)))
    except Exception:
        pass
    return out
