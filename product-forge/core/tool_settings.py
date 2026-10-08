"""Tool settings store (BI-PF-0439) - API-first, single writer.

Non-secret tool settings (e.g. web_search backend/url) live in ``data/tools/settings.json``; the SECRET key
lives in ``data/tools/secrets.json`` (gitignored) and is NEVER returned by the API (only ``has_key``).

Read precedence: ENV > store (ops can always override, e.g. ``PF_WEB_SEARCH_BACKEND``).
Owner: this module (single writer of both files)."""
import json
import os
import threading

from core.paths import ROOT

_TOOLS_DIR = os.path.join(str(ROOT), "data", "tools")
_SETTINGS = os.path.join(_TOOLS_DIR, "settings.json")
_SECRETS = os.path.join(_TOOLS_DIR, "secrets.json")
_LOCK = threading.Lock()
WEB_SEARCH = "web_search"


def _read(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _write(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def settings(name: str = WEB_SEARCH) -> dict:
    return _read(_SETTINGS).get(name, {}) or {}


def key(name: str = WEB_SEARCH) -> str:
    return str(_read(_SECRETS).get(name, {}).get("api_key", "") or "")


def save(*, backend: str = "", url: str = "", api_key=None, name: str = WEB_SEARCH) -> dict:
    """Persist non-secret settings and (optionally) the secret key. api_key=None leaves it unchanged."""
    with _LOCK:
        data = _read(_SETTINGS)
        cur = dict(data.get(name) or {})
        if backend:
            cur["backend"] = backend
        if url:
            cur["url"] = url
        data[name] = cur
        _write(_SETTINGS, data)
        if api_key is not None:
            sec = _read(_SECRETS)
            cur_s = dict(sec.get(name) or {})
            cur_s["api_key"] = str(api_key)
            sec[name] = cur_s
            _write(_SECRETS, sec)
    return settings(name)


def _env(k: str, d: str = "") -> str:
    v = os.environ.get(k)
    if v not in (None, ""):
        return str(v)
    try:
        from core import env_flags
        f = env_flags.load().get(k)
        if f is not None and str(f.get("default", "")) not in ("", "none"):
            return str(f.get("default"))
    except Exception:
        pass
    return d


def effective(name: str = WEB_SEARCH) -> dict:
    """Resolve the active config: ENV > store; key from ENV (provider/PF) > secret store. Never returns the key."""
    s = settings(name)
    backend = (_env("PF_WEB_SEARCH_BACKEND") or str(s.get("backend") or "") or "none").strip().lower()
    url = (_env("PF_WEB_SEARCH_URL") or str(s.get("url") or "")).strip()
    k = (_env("PF_WEB_SEARCH_KEY") or os.environ.get("BRAVE_SEARCH_API_KEY", "")
         or os.environ.get("TAVILY_API_KEY", "") or key(name))
    source = "env" if _env("PF_WEB_SEARCH_BACKEND") else ("store" if s.get("backend") else "default")
    return {"backend": backend, "url": url, "key": k, "has_key": bool(k), "source": source}
