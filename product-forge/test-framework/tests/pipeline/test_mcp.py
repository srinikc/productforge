"""BI-0196: MCP interop — server round-trip, approval fail-closed, client call + ingest."""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import mcp  # noqa: E402


def test_server_initialize_and_tools_list():
    init = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert init["result"]["serverInfo"]["name"] == "product-forge"
    tl = mcp.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = [t["name"] for t in tl["result"]["tools"]]
    assert "read_file" in names and "write_file" in names


def test_tools_call_roundtrip(tmp_path):
    ws = str(tmp_path)
    # run_command is dangerous -> fail-closed without explicit approval
    w = mcp.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                    "params": {"name": "run_command", "arguments": {"command": "echo hi"}}},
                   workspace=ws)
    assert "error" in w
    r = mcp.handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                    "params": {"name": "list_dir", "arguments": {}}}, workspace=ws)
    assert r["result"]["content"][0]["type"] == "text"


def test_unknown_method_and_tool_are_jsonrpc_errors():
    assert mcp.handle({"jsonrpc": "2.0", "id": 5, "method": "bogus"})["error"]["code"] == -32601
    assert mcp.handle({"jsonrpc": "2.0", "id": 6, "method": "tools/call",
                       "params": {"name": "nope"}})["error"]["code"] == -32602


def test_client_call_and_ingest_via_fake_server(tmp_path):
    # a tiny stdio MCP server that answers initialize/tools/list
    script = tmp_path / "fake_mcp.py"
    script.write_text(
        "import sys, json\n"
        "req=json.loads(sys.stdin.read())\n"
        "m=req.get('method')\n"
        "if m=='tools/list':\n"
        "    print(json.dumps({'jsonrpc':'2.0','id':req.get('id'),'result':{'tools':[{'name':'ext_echo','description':'x','inputSchema':{'type':'object'}}]}}))\n"
        "else:\n"
        "    print(json.dumps({'jsonrpc':'2.0','id':req.get('id'),'result':{}}))\n",
        encoding="utf-8")
    server = {"transport": "stdio", "command": [sys.executable, str(script)]}
    r = mcp.call(server, "tools/list")
    assert r["ok"] and r["result"]["tools"][0]["name"] == "ext_echo"

    from core.tool_registry import ToolRegistry
    reg = ToolRegistry()
    names = mcp.ingest_tools(server, reg)
    assert "ext_echo" in names
    # external tools are fail-closed (dangerous/requires_approval)
    assert reg._tools["ext_echo"].requires_approval is True


def test_client_errors_are_fail_closed():
    assert mcp.call({"transport": "stdio", "command": [sys.executable, "-c", "print('not json')"]},
                    "tools/list")["ok"] is False
    assert mcp.call({"transport": "nope"}, "tools/list")["ok"] is False
    assert mcp.call({"transport": "stdio"}, "tools/list")["ok"] is False
