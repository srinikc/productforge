"""MCP (Model Context Protocol) interop — expose our tools + consume external MCP servers (BI-0196).

Server side: JSON-RPC 2.0 mapping of ``core.tool_registry`` (initialize / tools/list / tools/call).
Client side: a minimal JSON-RPC caller (HTTP or stdio) + ``ingest_tools`` to register an external
server's tools into a ``ToolRegistry`` so agents call them like any tool.

Modular: MCP is a transport/adapter AROUND the existing tool loop (no fork). Fail-closed: transport/JSON
errors never raise into the caller; ``requires_approval``/``dangerous`` tools are refused without an
explicit approval token. See docs/MCP-DESIGN.md.
"""

import json
import os
import subprocess
from typing import Dict, List, Optional

try:
    from core.paths import ROOT as _ROOT
except ImportError:  # script execution
    import sys as _sys
    _d = os.path.abspath(__file__)
    for _ in range(3):
        _d = os.path.dirname(_d)
        if os.path.isfile(os.path.join(_d, "core", "paths.py")):
            _sys.path.insert(0, _d)
            break
    from core.paths import ROOT as _ROOT

SERVERS_STORE = os.path.join(str(_ROOT), "config", "mcp-servers." + "json")
PROTOCOL_VERSION = "2024-11-05"


def _registry():
    from core.tool_registry import ToolRegistry
    return ToolRegistry()


# ── server side (expose OUR tools) ──────────────────────────────────────────
def describe_tools(registry=None) -> List[Dict]:
    """Our tools as MCP tool descriptors ({name, description, inputSchema})."""
    reg = registry or _registry()
    out = []
    for spec in reg._tools.values():
        out.append({"name": spec.name, "description": spec.description,
                    "inputSchema": spec.parameters or {"type": "object", "properties": {}}})
    return out


def _rpc_ok(rid, result) -> Dict:
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def _rpc_err(rid, code: int, message: str) -> Dict:
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


def handle(request: Dict, registry=None, workspace: str = ".", approved: bool = False) -> Dict:
    """Handle one MCP JSON-RPC request. Never raises; unknown method -> JSON-RPC error."""
    reg = registry or _registry()
    rid = (request or {}).get("id")
    method = str((request or {}).get("method") or "")
    params = (request or {}).get("params") or {}
    try:
        if method == "initialize":
            return _rpc_ok(rid, {"protocolVersion": PROTOCOL_VERSION,
                                 "serverInfo": {"name": "product-forge", "version": "1.0"},
                                 "capabilities": {"tools": {}}})
        if method == "tools/list":
            return _rpc_ok(rid, {"tools": describe_tools(reg)})
        if method == "tools/call":
            name = str(params.get("name") or "")
            args = params.get("arguments") or {}
            spec = reg._tools.get(name)
            if spec is None:
                return _rpc_err(rid, -32602, f"unknown tool: {name}")
            if (spec.requires_approval or spec.dangerous) and not approved:
                return _rpc_err(rid, -32001, f"tool '{name}' requires approval")
            res = reg.execute(name, args, workspace)
            if not res.ok:
                return _rpc_err(rid, -32603, res.error or "tool failed")
            return _rpc_ok(rid, {"content": [{"type": "text", "text": res.output}], "isError": False})
        return _rpc_err(rid, -32601, f"method not found: {method}")
    except Exception as e:
        return _rpc_err(rid, -32603, f"internal error: {e}")


# ── client side (consume EXTERNAL MCP servers) ──────────────────────────────
def _servers() -> Dict:
    try:
        with open(SERVERS_STORE, encoding="utf-8-sig") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def list_servers() -> List[Dict]:
    return [{"name": k, **v} for k, v in (_servers().get("servers") or {}).items()]


def call(server: Dict, method: str, params: Optional[Dict] = None, timeout: int = 30) -> Dict:
    """Call an external MCP server (stdio). Fail-closed: returns {'ok':False,'error':...}."""
    try:
        transport = str((server or {}).get("transport") or "stdio")
        if transport != "stdio":
            return {"ok": False, "error": f"unsupported transport: {transport}"}
        cmd = (server or {}).get("command")
        if not cmd:
            return {"ok": False, "error": "no command"}
        req = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
        args = cmd if isinstance(cmd, list) else [cmd]
        p = subprocess.run(args, input=json.dumps(req), capture_output=True, text=True, timeout=timeout)
        try:
            resp = json.loads((p.stdout or "").strip().splitlines()[-1])
        except Exception:
            return {"ok": False, "error": "invalid JSON-RPC response"}
        if "error" in resp:
            return {"ok": False, "error": resp["error"].get("message", "rpc error")}
        return {"ok": True, "result": resp.get("result")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def ingest_tools(server: Dict, registry=None) -> List[str]:
    """tools/list from an external server -> register ToolSpecs. Returns registered names."""
    from core.tool_registry import ToolSpec
    reg = registry or _registry()
    r = call(server, "tools/list")
    if not r.get("ok"):
        return []
    names: List[str] = []
    for t in (r["result"] or {}).get("tools", []):
        spec = ToolSpec(name=str(t.get("name")), description=str(t.get("description") or ""),
                        parameters=t.get("inputSchema") or {"type": "object", "properties": {}},
                        dangerous=True, requires_approval=True)   # external tools: fail-closed
        try:
            reg.register(spec)
            names.append(spec.name)
        except Exception:
            pass
    return names
