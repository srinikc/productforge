"""
App boot/import smoke.

Catches the class of failures that shallow unit tests miss: the app **fails to
import/start** (e.g. FastAPI route/signature errors, bad imports, missing deps).
Detects the ASGI/WSGI entrypoint from the Dockerfile/compose or `main.py`, then
imports it in a subprocess and reports the traceback.

Returns {ok, entrypoint, error}.
"""
import json
import os
import re
import subprocess
from typing import Dict, Optional


def _read(p: str) -> str:
    try:
        return open(p, encoding="utf-8", errors="ignore").read()
    except Exception:
        return ""


def detect_entrypoint(project_dir: str) -> Optional[str]:
    # 0) explicit override (any stack): project.json -> deploy.app_entrypoint / app_entrypoint
    try:
        cfg = json.load(open(os.path.join(project_dir, "project.json"), encoding="utf-8")) or {}
        ep = ((cfg.get("deploy") or {}).get("app_entrypoint")
              or cfg.get("app_entrypoint"))
        if ep:
            return str(ep)
    except Exception:
        pass
    # 1) Dockerfile / compose command: uvicorn|gunicorn <module>:app
    for rel in ("Dockerfile", "docker/Dockerfile", "docker-compose.yml",
                "docker-compose.yaml", "compose.yml"):
        txt = _read(os.path.join(project_dir, rel))
        m = re.search(r"\b(?:uvicorn|gunicorn)\s+['\"]?([\w.]+):\w+", txt)
        if m:
            return m.group(1)
    # 2) src/**/main.py declaring an ASGI/WSGI app (any framework entrypoint)
    for base in ("src", "."):
        root = os.path.join(project_dir, base)
        for dp, _dn, fs in os.walk(root):
            for f in fs:
                if f in ("main.py", "app.py", "asgi.py", "wsgi.py", "__init__.py"):
                    txt = _read(os.path.join(dp, f))
                    if re.search(r"^\s*(app|application)\s*=\s*[A-Za-z_]\w*\(", txt, re.M):
                        rel = os.path.relpath(os.path.join(dp, f), project_dir)
                        parts = os.path.splitext(rel)[0].split(os.sep)
                        if parts and parts[0] == "src":
                            parts = parts[1:]
                        if parts and parts[-1] == "__init__":
                            parts = parts[:-1]
                        return ".".join(parts)
    return None


def boot_check(project_dir: str, timeout: int = 60) -> Dict:
    ep = detect_entrypoint(project_dir)
    if not ep:
        return {"ok": None, "entrypoint": "", "error": "no app entrypoint detected"}
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.join(project_dir, "src") + os.pathsep + env.get("PYTHONPATH", "")
    try:
        r = subprocess.run(["python", "-c", f"import {ep}"], cwd=project_dir, env=env,
                           capture_output=True, text=True, timeout=timeout)
        if r.returncode == 0:
            return {"ok": True, "entrypoint": ep, "error": ""}
        return {"ok": False, "entrypoint": ep,
                "error": ((r.stderr or "") + (r.stdout or ""))[-800:]}
    except Exception as e:
        return {"ok": False, "entrypoint": ep, "error": str(e)[:300]}
