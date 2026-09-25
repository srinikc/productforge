"""Consistent banner for the whole orchestrator/pipeline (console + views)."""
from typing import Optional

TITLE = "PRODUCT FORGE  -  MULTI-AGENT ORCHESTRATOR / PIPELINE"


def rule(ch: str = "=", n: int = 74) -> str:
    return ch * n


def banner(context: Optional[str] = None) -> str:
    lines = [rule(), f"  {TITLE}"]
    if context:
        lines.append(f"  {context}")
    lines.append(rule())
    return "\n".join(lines)


def print_banner(context: Optional[str] = None):
    print(banner(context))


def stage_line(stage_id: str, name: str = "", context: Optional[str] = None) -> str:
    ctx = f" | {context}" if context else ""
    nm = f" ({name})" if name else ""
    return f"{TITLE}{ctx} | Stage {stage_id}{nm}"
