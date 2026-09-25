"""Network port utilities: detect collisions and pick a free port.

Used before starting a local/docker app so we don't fail on a busy port
(e.g. something else already bound to 8000).
"""
import socket
from typing import Optional

import os


def port_free(port: int, host: str = "0.0.0.0") -> bool:
    if not port:
        return False
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, int(port)))
        return True
    except OSError:
        return False
    finally:
        try:
            s.close()
        except Exception:
            pass


def pick_free_port(preferred: Optional[int] = None, host: str = "0.0.0.0",
                   span: int = 100) -> int:
    """Return `preferred` if free, else the next free port in [preferred, preferred+span)."""
    try:
        p = int(preferred) if preferred else 0
    except Exception:
        p = 0
    if p and port_free(p, host):
        return p
    base = p or 8000
    for cand in range(base, base + span):
        if port_free(cand, host):
            return cand
    # OS-assigned
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((host, 0))
        return s.getsockname()[1]
    finally:
        s.close()


def resolve_app_port(project_dir: str, cfg: Optional[dict] = None) -> dict:
    """Determine the app port: cfg.port -> docs/ports.json -> 8000; pick free if busy."""
    cfg = cfg or {}
    preferred = cfg.get("port")
    if not preferred:
        try:
            import json
            pj = os.path.join(project_dir, "docs", "ports.json")
            if os.path.exists(pj):
                data = json.load(open(pj, encoding="utf-8")) or {}
                for _k, v in (data.get("services") or {}).items():
                    preferred = v.get("external") or v.get("internal")
                    if preferred:
                        break
        except Exception:
            preferred = None
    chosen = pick_free_port(preferred)
    collided = bool(preferred) and chosen != int(preferred)
    return {"preferred": preferred, "port": chosen, "collision": collided}
