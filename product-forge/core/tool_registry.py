"""
Tool Registry (framework-agnostic)

Neutral tool definitions + safe execution used by agent tool loops. Tools are
mapped to whatever runtime we use (our own loop, MCP, or OpenAI function
calling). Safety is enforced here:

  - Filesystem tools are sandboxed to the project workspace (path traversal
    outside the workspace is rejected).
  - `run_command` uses an allow-list of executables and runs inside the
    workspace with a timeout.

This module does NOT itself call an LLM; it defines tools and executes them.
"""
import json
import os
import shlex
import subprocess
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional


DEFAULT_ALLOWED_COMMANDS = [
    "python", "python3", "pip", "pytest",
    "node", "npm", "npx", "pnpm", "yarn", "tsc",
    "ruff", "mypy", "black", "eslint",
    "git", "make",
]


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: Dict[str, Any]          # JSON schema
    dangerous: bool = False
    requires_approval: bool = False

    def to_dict(self) -> Dict:
        return {"type": "function", "function": {
            "name": self.name, "description": self.description,
            "parameters": self.parameters}}


@dataclass
class ToolResult:
    ok: bool
    output: str = ""
    error: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)


class ToolRegistry:
    def __init__(self, allowed_commands: Optional[List[str]] = None):
        self.allowed = set(allowed_commands or DEFAULT_ALLOWED_COMMANDS)
        self._tools: Dict[str, ToolSpec] = {}
        self._register_defaults()

    # ── registration ─────────────────────────────────────────────
    def register(self, spec: ToolSpec):
        self._tools[spec.name] = spec

    def _register_defaults(self):
        obj = lambda props, req: {"type": "object", "properties": props, "required": req}
        self.register(ToolSpec(
            "write_file", "Write content to a file inside the project workspace.",
            obj({"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"])))
        self.register(ToolSpec(
            "read_file", "Read a file inside the project workspace.",
            obj({"path": {"type": "string"}}, ["path"])))
        self.register(ToolSpec(
            "list_dir", "List files/directories inside the project workspace.",
            obj({"path": {"type": "string"}}, ["path"])))
        self.register(ToolSpec(
            "run_command", "Run an allowed shell command in the project workspace.",
            obj({"command": {"type": "string"}}, ["command"]), dangerous=True))
        self.register(ToolSpec(
            "http_get", "HTTP GET a URL (read-only).",
            obj({"url": {"type": "string"}}, ["url"])))
        self.register(ToolSpec(
            "web_search", "Search the web (backend-configurable: self-host whoogle/searxng, or cloud brave/tavily with a key).",
            obj({"query": {"type": "string"}, "limit": {"type": "integer"}}, ["query"])))

    # ── introspection ────────────────────────────────────────────
    def names(self) -> List[str]:
        return sorted(self._tools.keys())

    def schemas(self, names: Optional[List[str]] = None) -> List[Dict]:
        names = names or list(self._tools.keys())
        return [self._tools[n].to_dict() for n in names if n in self._tools]

    # ── execution ────────────────────────────────────────────────
    def execute(self, name: str, args: Dict[str, Any], workspace: str) -> ToolResult:
        handler: Optional[Callable] = {
            "write_file": self._write_file,
            "read_file": self._read_file,
            "list_dir": self._list_dir,
            "run_command": self._run_command,
            "http_get": self._http_get,
            "web_search": self._web_search,
        }.get(name)
        if handler is None:
            return ToolResult(False, error=f"unknown tool: {name}")
        try:
            return handler(args or {}, workspace)
        except Exception as e:
            return ToolResult(False, error=str(e))

    @staticmethod
    def _safe_path(workspace: str, rel: str) -> str:
        ws = os.path.abspath(workspace)
        target = os.path.abspath(os.path.join(ws, rel))
        if os.path.commonpath([ws, target]) != ws:
            raise ValueError(f"path escapes workspace: {rel}")
        return target

    def _write_file(self, args, workspace) -> ToolResult:
        path = self._safe_path(workspace, args["path"])
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(args.get("content", ""))
        return ToolResult(True, output=f"wrote {len(args.get('content',''))} chars to {args['path']}")

    def _read_file(self, args, workspace) -> ToolResult:
        path = self._safe_path(workspace, args["path"])
        if not os.path.exists(path):
            return ToolResult(False, error=f"not found: {args['path']}")
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return ToolResult(True, output=f.read())

    def _list_dir(self, args, workspace) -> ToolResult:
        path = self._safe_path(workspace, args.get("path", "."))
        if not os.path.isdir(path):
            return ToolResult(False, error=f"not a directory: {args.get('path', '.')}")
        return ToolResult(True, output="\n".join(sorted(os.listdir(path))))

    def _run_command(self, args, workspace) -> ToolResult:
        cmd = (args.get("command") or "").strip()
        if not cmd:
            return ToolResult(False, error="empty command")
        try:
            parts = shlex.split(cmd, posix=False)
        except ValueError:
            parts = cmd.split()
        exe = os.path.basename(parts[0]).lower().replace(".exe", "")
        if exe not in self.allowed:
            return ToolResult(False, error=f"command not allowed: {exe}")
        try:
            r = subprocess.run(parts, cwd=workspace, capture_output=True,
                               text=True, timeout=300)
            out = (r.stdout or "") + (("\n[stderr]\n" + r.stderr) if r.stderr else "")
            return ToolResult(r.returncode == 0, output=out[:20000])
        except subprocess.TimeoutExpired:
            return ToolResult(False, error="command timed out (300s)")

    def _http_get(self, args, workspace) -> ToolResult:
        try:
            import requests
            r = requests.get(args["url"], timeout=30)
            return ToolResult(r.status_code == 200, output=r.text[:20000])
        except Exception as e:
            return ToolResult(False, error=str(e))

    # ── web_search (BI-PF-0438): a client over a configurable search backend ──
    # Builds ON the existing HTTP capability (requests); no new dependency.
    # Default backend `none` = disabled/offline-safe. Self-host (whoogle/searxng) = no key;
    # cloud (brave/tavily) = bring-your-own-key (a customer supplies their own account at ship time).
    @staticmethod
    def _ws_cfg():
        try:
            from core import tool_settings
            e = tool_settings.effective()
            return (str(e.get("backend") or "none").strip().lower(),
                    str(e.get("url") or "").strip(),
                    str(e.get("key") or "").strip())
        except Exception:
            return ("none", "", "")

    @staticmethod
    def _ws_anchors(html: str, limit: int):
        import re as _re
        out, seen = [], set()
        for m in _re.finditer(r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', html, _re.I | _re.S):
            url = m.group(1)
            title = _re.sub(r"<[^>]+>", "", m.group(2)).strip()
            if not title or url in seen:
                continue
            seen.add(url)
            out.append({"title": title, "url": url, "snippet": ""})
            if len(out) >= limit:
                break
        return out

    def _web_search(self, args, workspace) -> ToolResult:
        try:
            import requests
        except Exception as e:
            return ToolResult(False, error=f"requests unavailable: {e}")
        q = str(args.get("query") or "").strip()
        if not q:
            return ToolResult(False, error="web_search: query required")
        limit = int(args.get("limit") or 5)
        backend, url, key = self._ws_cfg()
        if backend in ("", "none", "off", "disabled"):
            return ToolResult(False, error=("web_search disabled (set PF_WEB_SEARCH_BACKEND: "
                                            "whoogle|searxng|duckduckgo_html|brave|tavily)"))
        try:
            if backend == "searxng":
                r = requests.get((url or "http://127.0.0.1:8888").rstrip("/") + "/search",
                                 params={"q": q, "format": "json"}, timeout=20)
                r.raise_for_status()
                rows = [{"title": x.get("title"), "url": x.get("url"), "snippet": x.get("content", "")}
                        for x in (r.json().get("results") or [])]
            elif backend == "whoogle":
                r = requests.get((url or "http://127.0.0.1:5000").rstrip("/") + "/search",
                                 params={"q": q}, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
                r.raise_for_status()
                rows = self._ws_anchors(r.text, limit)
            elif backend == "duckduckgo_html":
                r = requests.get("https://duckduckgo.com/html/", params={"q": q}, timeout=20,
                                 headers={"User-Agent": "Mozilla/5.0"})
                r.raise_for_status()
                rows = self._ws_anchors(r.text, limit + 5)
            elif backend == "brave":
                k = key or os.environ.get("BRAVE_SEARCH_API_KEY", "")
                if not k:
                    return ToolResult(False, error="brave: key required (PF_WEB_SEARCH_KEY or BRAVE_SEARCH_API_KEY)")
                r = requests.get("https://api.search.brave.com/res/v1/web/search",
                                 params={"q": q, "count": limit},
                                 headers={"Accept": "application/json", "X-Subscription-Token": k}, timeout=20)
                r.raise_for_status()
                rows = [{"title": x.get("title"), "url": x.get("url"), "snippet": x.get("description", "")}
                        for x in ((r.json().get("web") or {}).get("results") or [])]
            elif backend == "tavily":
                k = key or os.environ.get("TAVILY_API_KEY", "")
                if not k:
                    return ToolResult(False, error="tavily: key required (PF_WEB_SEARCH_KEY or TAVILY_API_KEY)")
                r = requests.post("https://api.tavily.com/search",
                                  json={"api_key": k, "query": q, "max_results": limit}, timeout=20)
                r.raise_for_status()
                rows = [{"title": x.get("title"), "url": x.get("url"), "snippet": x.get("content", "")}
                        for x in (r.json().get("results") or [])]
            else:
                return ToolResult(False, error=f"unknown PF_WEB_SEARCH_BACKEND: {backend}")
        except Exception as e:
            return ToolResult(False, error=f"web_search({backend}): {type(e).__name__}: {e}")
        out = [{"title": str(x.get("title") or ""), "url": str(x.get("url") or ""),
                "snippet": str(x.get("snippet") or "")} for x in rows[:limit]]
        return ToolResult(True, output=json.dumps(out, ensure_ascii=False))
