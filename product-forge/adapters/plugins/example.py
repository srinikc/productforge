"""Example plugin adapters (BI-0200) — prove drop-in registration without core edits.

These live OUTSIDE ``core/`` so the invocation audit does not classify them as unwired core modules;
they are resolved at runtime by dotted name via ``core.plugins``.
"""


def build_tool(context: dict) -> dict:
    """A trivial 'echo' tool port: {spec, handler}. No side effects, no network."""
    def _handler(args, workspace):
        return {"output": f"echo: {args.get('text', '')}"}

    return {
        "spec": {"name": context.get("config", {}).get("name", "echo_plugin"),
                 "description": "Example plugin tool: echoes text (BI-0200 demo).",
                 "parameters": {"text": "string"},
                 "dangerous": False,
                 "requires_approval": False},
        "handler": _handler,
    }


def build_stage(context: dict) -> dict:
    """A pack-shaped stage contribution consumed by pipeline_composition (no new enable path)."""
    sid = context.get("config", {}).get("stage_id", "0x-example")
    after = context.get("config", {}).get("after", "0a")
    return {
        "stages": [{"id": sid, "after": after, "name": context.get("config", {}).get("name", "Example Plugin Stage"),
                    "ideal_flow": [], "depends_on": [after], "optional": True}],
        "agent_stages": [],
        "validator_stages": [],
    }
