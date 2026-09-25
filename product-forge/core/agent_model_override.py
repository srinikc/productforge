"""Per-agent runtime MODEL OVERRIDE - persisted, project-scoped. Single writer (BI-0178).

Lets the dashboard change ONE agent's model at runtime without editing config. Precedence applied
in `model_router.get_agent_model_config`:  override > stage > agent > default.

Store: `products/<project>/agent-model-overrides.json`
    { "<agent_id>": {"model": "...", "note": "...", "updated_at": "..."} }
"""
import json
import os
from datetime import datetime
from typing import Dict, Optional

FILENAME = "agent-model-overrides.json"


def _path(project_dir: str) -> str:
    return os.path.join(project_dir or "", FILENAME)


def _read(project_dir: str) -> Dict:
    try:
        with open(_path(project_dir), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _write(project_dir: str, data: Dict) -> None:
    p = _path(project_dir)
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, p)


def load(project_dir: str) -> Dict:
    """All overrides for a project: {agent_id: {model, note, updated_at}}."""
    return _read(project_dir)


def get(project_dir: str, agent_id: str) -> Optional[Dict]:
    """The override for one agent, or None."""
    return _read(project_dir).get(str(agent_id)) or None


def set(project_dir: str, agent_id: str, model: str, note: str = "") -> Dict:
    """Set/persist an agent's model override."""
    if not str(model or "").strip():
        raise ValueError("model is required")
    d = _read(project_dir)
    d[str(agent_id)] = {"model": str(model).strip(), "note": note or "",
                        "updated_at": datetime.now().isoformat()}
    _write(project_dir, d)
    return d[str(agent_id)]


def clear(project_dir: str, agent_id: str) -> bool:
    """Remove an agent's override (falls back to tier resolution). True if one existed."""
    d = _read(project_dir)
    if str(agent_id) in d:
        d.pop(str(agent_id), None)
        _write(project_dir, d)
        return True
    return False


def effective(project_dir: str, agent_id: str, tier_model: str = "") -> Dict:
    """Effective model + source for display: override wins over the tier-resolved model."""
    ov = get(project_dir, agent_id)
    if ov and ov.get("model"):
        return {"model": ov["model"], "source": "override"}
    return {"model": tier_model, "source": "tier"}


def _main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Per-agent model override store (BI-0178)")
    ap.add_argument("--project-dir", required=True)
    sub = ap.add_subparsers(dest="cmd")
    g = sub.add_parser("get"); g.add_argument("agent")
    s = sub.add_parser("set"); s.add_argument("agent"); s.add_argument("model"); s.add_argument("--note", default="")
    c = sub.add_parser("clear"); c.add_argument("agent")
    sub.add_parser("list")
    a = ap.parse_args(argv)
    if a.cmd == "get":
        print(json.dumps(get(a.project_dir, a.agent), indent=2, ensure_ascii=False))
    elif a.cmd == "set":
        print(json.dumps(set(a.project_dir, a.agent, a.model, a.note), indent=2, ensure_ascii=False))
    elif a.cmd == "clear":
        print("cleared" if clear(a.project_dir, a.agent) else "none")
    elif a.cmd == "list":
        print(json.dumps(load(a.project_dir), indent=2, ensure_ascii=False))
    else:
        ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
