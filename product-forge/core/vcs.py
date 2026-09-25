"""
VCS manager (orchestrator-owned git automation).

The orchestrator performs ALL git operations on behalf of agents; agents only
read/write files. Model:
  feat/fix/* -> develop (all changes) -> main (release only, when green + QA GO + HIL)

Config (project.json -> "vcs"):
  { provider, remote, branch_model, protected:[...], base_branch, sign_tags }

Everything is guarded: if git/repo/remote is unavailable the manager degrades to
no-ops (returns {"ok": False, ...}) instead of failing the pipeline.
"""
import os
import json
import re
import subprocess
from datetime import datetime
from typing import Any, Dict, List, Optional


class VCSManager:
    def __init__(self, project_dir: str, config: Optional[Dict] = None):
        self.project_dir = project_dir
        # BI-0086: load the per-project git config (connect/create, provider/remote/branch model)
        # unless an explicit config was passed. Single source of truth: products/<p>/git-config.json.
        self.cfg = config if config is not None else self.load_config(project_dir)
        self.base_branch = self.cfg.get("base_branch") or "develop"
        self.integration_branch = self.base_branch
        self.release_branch = self.cfg.get("release_branch") or "main"
        self.protected = set(self.cfg.get("protected") or [self.release_branch])
        self.sign_tags = bool(self.cfg.get("sign_tags", False))
        self.remote = self.cfg.get("remote") or "origin"

    CONFIG_FILE = "git-config.json"
    DEFAULT_CONFIG = {"provider": "github", "remote": "origin", "branch_model": "git-flow",
                      "base_branch": "develop", "release_branch": "main",
                      "protected": ["main"], "sign_tags": False}

    @classmethod
    def config_path(cls, project_dir: str) -> str:
        return os.path.join(project_dir, cls.CONFIG_FILE)

    @classmethod
    def load_config(cls, project_dir: str) -> Dict[str, Any]:
        p = cls.config_path(project_dir)
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f) or dict(cls.DEFAULT_CONFIG)
        except Exception:
            return dict(cls.DEFAULT_CONFIG)

    @classmethod
    def save_config(cls, project_dir: str, config: Dict[str, Any]) -> str:
        cfg = dict(cls.DEFAULT_CONFIG)
        cfg.update({k: v for k, v in (config or {}).items() if v not in (None, "")})
        p = cls.config_path(project_dir)
        os.makedirs(project_dir, exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        return p

    def history(self, limit: int = 100) -> Dict[str, Any]:
        """BI-0089: check-ins + tags + branches for the project (read-only)."""
        out: Dict[str, Any] = {"is_repo": self.is_repo(), "config": self.cfg}
        if not out["is_repo"]:
            return out
        try:
            out["checkins"] = self.checkins(limit)
        except Exception:
            out["checkins"] = []
        try:
            out["current_branch"] = self.current_branch()
        except Exception:
            out["current_branch"] = ""
        return out


    # ── primitives ──────────────────────────────────────────────
    def _git(self, args: List[str], check: bool = False) -> Dict[str, Any]:
        try:
            r = subprocess.run(["git", *args], cwd=self.project_dir, capture_output=True,
                               text=True, timeout=120)
            out = (r.stdout or "").strip()
            err = (r.stderr or "").strip()
            if check and r.returncode != 0:
                return {"ok": False, "cmd": " ".join(args), "error": err or out}
            return {"ok": r.returncode == 0, "out": out, "error": err}
        except FileNotFoundError:
            return {"ok": False, "error": "git not installed"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def is_repo(self) -> bool:
        return self._git(["rev-parse", "--is-inside-work-tree"]).get("ok", False)

    def init(self) -> Dict[str, Any]:
        if self.is_repo():
            self.ensure_develop()
            return {"ok": True, "already": True}
        self._git(["init"])
        self._ensure_identity()
        self._git(["checkout", "-b", self.release_branch])
        self._git(["add", "-A"])
        self._git(["commit", "--allow-empty", "-m", "chore: initialize repository"])
        self.ensure_develop()
        return {"ok": True}

    def _ensure_identity(self):
        if not self._git(["config", "user.email"]).get("out"):
            self._git(["config", "user.email", "product-forge@local"])
        if not self._git(["config", "user.name"]).get("out"):
            self._git(["config", "user.name", "Product Forge"])

    def current_branch(self) -> str:
        return self._git(["rev-parse", "--abbrev-ref", "HEAD"]).get("out", "")

    def has_remote(self) -> bool:
        return self._git(["remote"]).get("out", "").find(self.remote) >= 0

    def has_conflicts(self) -> List[str]:
        out = self._git(["diff", "--name-only", "--diff-filter=U"]).get("out", "")
        return [x for x in out.splitlines() if x.strip()]

    # ── branches ────────────────────────────────────────────────
    def ensure_develop(self) -> Dict[str, Any]:
        r = self._git(["rev-parse", "--verify", self.integration_branch])
        if r.get("ok"):
            return {"ok": True, "branch": self.integration_branch}
        return self._git(["checkout", "-b", self.integration_branch])

    def feature_branch(self, name: str, base: Optional[str] = None) -> Dict[str, Any]:
        base = base or self.integration_branch
        self.ensure_develop()
        self._git(["checkout", base])
        return self._git(["checkout", "-b", name])

    def checkout(self, branch: str) -> Dict[str, Any]:
        return self._git(["checkout", branch])

    # ── commits / push ──────────────────────────────────────────
    def commit(self, message: str, paths: Optional[List[str]] = None) -> Dict[str, Any]:
        if paths:
            self._git(["add", *paths])
        else:
            self._git(["add", "-A"])
        r = self._git(["commit", "-m", message])
        sha = self._git(["rev-parse", "HEAD"]).get("out", "")
        return {"ok": r.get("ok", False), "sha": sha, "error": r.get("error", "")}

    def push(self, branch: Optional[str] = None, set_upstream: bool = True) -> Dict[str, Any]:
        if not self.has_remote():
            return {"ok": False, "error": "no remote configured"}
        br = branch or self.current_branch()
        args = ["push"]
        if set_upstream:
            args += ["-u", self.remote, br]
        return self._git(args)

    def rebase(self, onto: Optional[str] = None) -> Dict[str, Any]:
        onto = onto or self.integration_branch
        r = self._git(["rebase", onto])
        return {"ok": r.get("ok", False), "conflicts": self.has_conflicts(), "error": r.get("error", "")}

    # ── stash (ephemeral only) ──────────────────────────────────
    def stash(self, label: str = "") -> Dict[str, Any]:
        return self._git(["stash", "push", "-m", label or f"run-{datetime.now():%Y%m%d%H%M%S}"])

    def unstash(self) -> Dict[str, Any]:
        return self._git(["stash", "pop"])

    # ── merge / tag ─────────────────────────────────────────────
    def merge(self, source: str, target: str, message: str = "",
              require_gate: bool = True) -> Dict[str, Any]:
        project = os.path.basename(os.path.normpath(self.project_dir))
        if require_gate:
            try:
                from core.pr_gate import can_merge
                gate = can_merge(project, self.project_dir)
                if not gate.get("can_merge"):
                    return {"ok": False, "blocked": True, "reason": gate.get("reason"),
                            "unmet": gate.get("unmet")}
            except Exception as e:
                return {"ok": False, "blocked": True, "reason": f"gate error: {e}"}
        self._git(["checkout", target])
        r = self._git(["merge", "--no-ff", source, "-m", message or f"merge {source} into {target}"])
        return {"ok": r.get("ok", False), "conflicts": self.has_conflicts(), "error": r.get("error", "")}

    def checkins(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Commit/PR history: hash, author, date, brief, PR# (when present)."""
        out = self._git(["log", f"-{limit}", "--pretty=format:%H|%an|%aI|%s|%b<<<EOR>>>"])
        rows = []
        for chunk in (out.get("out") or "").split("<<<EOR>>>"):
            chunk = chunk.strip()
            if not chunk:
                continue
            parts = chunk.split("|", 4)
            if len(parts) < 4:
                continue
            sha, author, date, subject = parts[0], parts[1], parts[2], parts[3]
            body = parts[4] if len(parts) > 4 else ""
            m = re.search(r"#(\d+)", subject + " " + body)
            rows.append({"sha": sha[:10], "author": author, "date": date,
                         "brief": subject, "pr": (f"#{m.group(1)}" if m else ""),
                         "merge": subject.lower().startswith("merge")})
        return rows

    def tag(self, name: str, message: str = "", sign: Optional[bool] = None) -> Dict[str, Any]:
        sign = self.sign_tags if sign is None else sign
        args = ["tag", "-a", name, "-m", message or name]
        if sign:
            try:
                from core.signing import tag_args
                extra = tag_args(self.project_dir)   # env key OR HIL-provided key
                if extra:
                    args = ["tag", "-s", name, "-m", message or name] + extra
            except Exception:
                pass
        r = self._git(args)
        r["signed"] = "-s" in args
        return r

    # ── WIP safety net ──────────────────────────────────────────
    def wip_snapshot(self, run_id: str = "") -> Dict[str, Any]:
        dirty = self._git(["status", "--porcelain"]).get("out", "")
        if not dirty.strip():
            return {"ok": True, "committed": False}
        return self.commit(f"wip({run_id or 'auto'}): snapshot {datetime.now():%Y-%m-%d %H:%M}")
