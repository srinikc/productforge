"""WorkerGrid config + paths (shared by the CLI and client)."""
import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))


def load() -> dict:
    try:
        with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def state_dir() -> str:
    d = os.path.join(ROOT, str(load().get("state_dir") or "state"))
    os.makedirs(d, exist_ok=True)
    return d


def instructions_path() -> str:
    return os.path.join(ROOT, str(load().get("instructions_file") or "instructions.md"))


def read_json(name: str, default):
    p = os.path.join(state_dir(), name)
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def write_json(name: str, data) -> None:
    p = os.path.join(state_dir(), name)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, p)
