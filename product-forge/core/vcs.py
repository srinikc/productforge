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
import json
import os
import re
import subprocess
from datetime import datetime
from typing import Any


class VCSManager:
    def __init__(self, project_dir: str, config: dict | None = None):
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

    # ── branch naming (ENG-3) ───────────────────────────────────
    @staticmethod
    def _slug(s: Any) -> str:
        return re.sub(r"[^a-z0-9._-]+", "-", str(s or "").strip().lower()).strip("-")

    @staticmethod
    def feature_branch_name(area: str, task_id: str) -> str:
        return f"feature/{VCSManager._slug(area) or 'task'}/{VCSManager._slug(task_id) or 'unknown'}"

    @staticmethod
    def validation_branch_name(run_id: str) -> str:
        return f"validation/{VCSManager._slug(run_id) or 'run'}"

    def is_protected(self, branch: str = "") -> bool:
        """develop/main (integration/release) are never written directly - only a controlled merge."""
        b = str(branch or self.current_branch() or "")
        return b in (set(self.protected) | {self.integration_branch, self.release_branch})

    @classmethod
    def config_path(cls, project_dir: str) -> str:
        return os.path.join(project_dir, cls.CONFIG_FILE)

    @classmethod
    def load_config(cls, project_dir: str) -> dict[str, Any]:
        p = cls.config_path(project_dir)
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f) or dict(cls.DEFAULT_CONFIG)
        except Exception:
            return dict(cls.DEFAULT_CONFIG)

    @classmethod
    def save_config(cls, project_dir: str, config: dict[str, Any]) -> str:
        cfg = dict(cls.DEFAULT_CONFIG)
        cfg.update({k: v for k, v in (config or {}).items() if v not in (None, "")})
        p = cls.config_path(project_dir)
        os.makedirs(project_dir, exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        return p

    def history(self, limit: int = 100) -> dict[str, Any]:
        """BI-0089: check-ins + tags + branches for the project (read-only)."""
        out: dict[str, Any] = {"is_repo": self.is_repo(), "config": self.cfg}
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
    def _git(self, args: list[str], check: bool = False) -> dict[str, Any]:
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

    def init(self) -> dict[str, Any]:
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

    def head_commit(self, ref: str = "HEAD") -> str:
        """Full SHA for a ref (read-only)."""
        return self._git(["rev-parse", ref]).get("out", "")

    def has_remote(self) -> bool:
        return self._git(["remote"]).get("out", "").find(self.remote) >= 0

    def remote_ref(self) -> str:
        """The remote-tracking ref of the integration branch (e.g. ``origin/develop``)."""
        return f"{self.remote}/{self.integration_branch}"

    def connect_remote(self, url: str, remote: str = "") -> dict[str, Any]:
        """Add or replace a remote URL so delivery can push (uses the configured remote name)."""
        rem = str(remote or self.remote or "origin")
        if not str(url or "").strip():
            return {"ok": False, "error": "empty url"}
        if self.has_remote():
            return self._git(["remote", "set-url", rem, str(url)])
        return self._git(["remote", "add", rem, str(url)])

    def fetch(self) -> dict[str, Any]:
        """Fetch the remote (no-op with a reason if no remote). Stage 2a (git sync)."""
        if not self.has_remote():
            return {"ok": False, "error": "no remote configured"}
        return self._git(["fetch", self.remote, "--prune"])

    def base_ref(self, base: str = "") -> str:
        """Base ref for a new worktree: explicit ``base`` > ``origin/<integration>`` (after fetch) > local.

        Using ``origin/<integration>`` keeps cross-system workers from branching off a stale local develop.
        """
        b = str(base or "").strip()
        if b and self._git(["rev-parse", "--verify", b]).get("ok"):
            return b
        if self.has_remote():
            self.fetch()
            rr = self.remote_ref()
            if self._git(["rev-parse", "--verify", rr]).get("ok"):
                return rr
        return self.integration_branch

    @staticmethod
    def auto_push_enabled() -> bool:
        """Whether auto-push-after-merge is enabled (``PF_AUTO_PUSH``; default off)."""
        try:
            from core import env_flags
            return str(env_flags.get("PF_AUTO_PUSH", "0") or "0").lower() in ("1", "true", "yes", "on")
        except Exception:
            return False

    def sync(self, push: bool = True, integration: bool = True) -> dict[str, Any]:
        """Fetch the remote and optionally push the integration branch (Stage 2a git sync).

        Explicit ``sync`` (operator/CLI) always pushes when ``push`` is true; auto-push after a controlled
        merge is gated by ``PF_AUTO_PUSH`` (see ``auto_push_enabled``).
        """
        if not self.has_remote():
            return {"ok": False, "error": "no remote configured"}
        fetched = bool(self.fetch().get("ok"))
        out: dict[str, Any] = {"ok": fetched, "fetched": fetched, "pushed": False}
        if push:
            br = self.integration_branch if integration else self.current_branch()
            r = self.push(br)
            out["pushed"] = bool(r.get("ok"))
            out["push"] = r
        return out

    def has_conflicts(self) -> list[str]:
        out = self._git(["diff", "--name-only", "--diff-filter=U"]).get("out", "")
        return [x for x in out.splitlines() if x.strip()]

    def status(self) -> dict[str, Any]:
        """Working-tree status: branch + modified/untracked files (read-only)."""
        if not self.is_repo():
            return {"is_repo": False, "clean": True, "branch": "",
                    "modified": [], "untracked": [], "remote": False}
        rows = [x for x in (self._git(["status", "--porcelain"]).get("out") or "").splitlines()
                if x.strip()]
        return {"is_repo": True, "clean": not rows, "branch": self.current_branch(),
                "modified": [x[3:].strip() for x in rows if not x.startswith("??")],
                "untracked": [x[3:].strip() for x in rows if x.startswith("??")],
                "remote": self.has_remote(), "conflicts": self.has_conflicts()}

    def branches(self) -> list[str]:
        """Local branch names (read-only)."""
        out = self._git(["branch", "--format=%(refname:short)"]).get("out", "")
        return [x.strip() for x in out.splitlines() if x.strip()]

    # ── worktrees (ENG-3: workers never share a mutable working dir) ──
    def worktree_root(self) -> str:
        """Sibling ``<repo>-worktrees/`` unless configured (git-config.json -> worktree_root)."""
        cfg = str(self.cfg.get("worktree_root") or "").strip()
        if cfg:
            return cfg if os.path.isabs(cfg) else os.path.abspath(os.path.join(self.project_dir, cfg))
        p = os.path.normpath(self.project_dir)
        return os.path.join(os.path.dirname(p), os.path.basename(p) + "-worktrees")

    def list_worktrees(self) -> list[dict[str, Any]]:
        if not self.is_repo():
            return []
        out = self._git(["worktree", "list", "--porcelain"]).get("out", "")
        rows: list[dict[str, Any]] = []
        cur: dict[str, Any] = {}
        for line in (out or "").splitlines():
            line = line.strip()
            if not line:
                if cur:
                    rows.append(cur)
                    cur = {}
                continue
            if line.startswith("worktree "):
                cur["path"] = line[len("worktree "):]
            elif line.startswith("HEAD "):
                cur["head"] = line[len("HEAD "):]
            elif line.startswith("branch "):
                cur["branch"] = line[len("branch "):].replace("refs/heads/", "")
            elif line == "bare":
                cur["bare"] = True
        if cur:
            rows.append(cur)
        return rows

    def add_worktree(self, name: str, branch: str = "", base: str = "") -> dict[str, Any]:
        """Create an isolated worktree on a feature branch (fixes PF-050: no bad create kwarg)."""
        if not self.is_repo():
            return {"ok": False, "error": "not a git repository"}
        safe = self._slug(name)
        if not safe:
            return {"ok": False, "error": "invalid worktree name"}
        path = os.path.join(self.worktree_root(), safe)
        branch = str(branch or "").strip() or f"worktree/{safe}"
        base_ref = ""
        try:
            os.makedirs(self.worktree_root(), exist_ok=True)
        except Exception as e:
            return {"ok": False, "error": str(e)}
        if self._git(["rev-parse", "--verify", branch]).get("ok"):
            r = self._git(["worktree", "add", path, branch])
        else:
            # Stage 2a: prefer origin/<integration> (fetched) so cross-system workers aren't stale.
            base_ref = self.base_ref(base)
            if not self._git(["rev-parse", "--verify", base_ref]).get("ok"):
                base_ref = self.current_branch() or "HEAD"
            r = self._git(["worktree", "add", "-b", branch, path, base_ref])
        return {"ok": r.get("ok", False), "name": safe, "path": path, "branch": branch,
                "base": base_ref, "error": r.get("error", "")}

    def remove_worktree(self, name: str) -> dict[str, Any]:
        path = os.path.join(self.worktree_root(), self._slug(name))
        r = self._git(["worktree", "remove", path, "--force"])
        self._git(["worktree", "prune"])
        return {"ok": r.get("ok", False), "path": path, "error": r.get("error", "")}

    # ── branches ────────────────────────────────────────────────
    def ensure_develop(self) -> dict[str, Any]:
        r = self._git(["rev-parse", "--verify", self.integration_branch])
        if r.get("ok"):
            return {"ok": True, "branch": self.integration_branch}
        return self._git(["checkout", "-b", self.integration_branch])

    def feature_branch(self, name: str, base: str | None = None) -> dict[str, Any]:
        base = base or self.integration_branch
        self.ensure_develop()
        self._git(["checkout", base])
        return self._git(["checkout", "-b", name])

    def checkout(self, branch: str) -> dict[str, Any]:
        return self._git(["checkout", branch])

    # ── commits / push ──────────────────────────────────────────
    def commit(self, message: str, paths: list[str] | None = None) -> dict[str, Any]:
        if paths:
            self._git(["add", *paths])
        else:
            self._git(["add", "-A"])
        r = self._git(["commit", "-m", message])
        sha = self._git(["rev-parse", "HEAD"]).get("out", "")
        return {"ok": r.get("ok", False), "sha": sha, "error": r.get("error", "")}

    def push(self, branch: str | None = None, set_upstream: bool = True) -> dict[str, Any]:
        if not self.has_remote():
            return {"ok": False, "error": "no remote configured"}
        br = branch or self.current_branch()
        args = ["push"]
        if set_upstream:
            args += ["-u", self.remote, br]
        return self._git(args)

    def rebase(self, onto: str | None = None) -> dict[str, Any]:
        onto = onto or self.integration_branch
        r = self._git(["rebase", onto])
        return {"ok": r.get("ok", False), "conflicts": self.has_conflicts(), "error": r.get("error", "")}

    # ── stash (ephemeral only) ──────────────────────────────────
    def stash(self, label: str = "") -> dict[str, Any]:
        return self._git(["stash", "push", "-m", label or f"run-{datetime.now():%Y%m%d%H%M%S}"])

    def unstash(self) -> dict[str, Any]:
        return self._git(["stash", "pop"])

    # ── merge / tag ─────────────────────────────────────────────
    def merge(self, source: str, target: str, message: str = "",
              require_gate: bool = True) -> dict[str, Any]:
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

    def checkins(self, limit: int = 100) -> list[dict[str, Any]]:
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

    def tag(self, name: str, message: str = "", sign: bool | None = None) -> dict[str, Any]:
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
    def wip_snapshot(self, run_id: str = "") -> dict[str, Any]:
        dirty = self._git(["status", "--porcelain"]).get("out", "")
        if not dirty.strip():
            return {"ok": True, "committed": False}
        return self.commit(f"wip({run_id or 'auto'}): snapshot {datetime.now():%Y-%m-%d %H:%M}")
