"""
Product Factory - Claude MCP Server Adapter

Thin MCP server that wraps the Product Factory REST API,
allowing Claude Code to send conversations directly to the factory.

Usage:
  python server.py

Claude Desktop config (claude_desktop_config.json):
{
  "mcpServers": {
    "product-factory": {
      "command": "python",
      "args": ["C:/Users/ADMIN/Documents/Srinikc/AI Products/Exploring/adapters/claude/server.py"],
      "env": {
        "FACTORY_API_URL": "http://localhost:8765"
      }
    }
  }
}
"""

import os
import sys
import json
import urllib.request
import urllib.error
from typing import Any, Dict, Optional

# ─── Configuration ────────────────────────────────────────────────

FACTORY_API_URL = os.environ.get("FACTORY_API_URL", "http://localhost:8765")
FACTORY_API_KEY = os.environ.get("FACTORY_API_KEY", "")


def api_request(method: str, path: str, data: Optional[Dict] = None) -> Dict:
    """Make a request to the Product Factory REST API."""
    url = f"{FACTORY_API_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if FACTORY_API_KEY:
        headers["Authorization"] = f"Bearer {FACTORY_API_KEY}"

    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else str(e)
        return {"error": f"HTTP {e.code}: {error_body}"}
    except Exception as e:
        return {"error": str(e)}


# ─── MCP Protocol (stdio) ────────────────────────────────────────

def read_message():
    """Read a JSON-RPC message from stdin."""
    header_line = sys.stdin.readline()
    if not header_line:
        return None

    content_length = 0
    while True:
        line = sys.stdin.readline().strip()
        if not line:
            break
        if line.lower().startswith("content-length:"):
            content_length = int(line.split(":", 1)[1].strip())

    if content_length == 0:
        return None

    body = sys.stdin.read(content_length)
    return json.loads(body)


def write_message(msg: Dict):
    """Write a JSON-RPC message to stdout."""
    body = json.dumps(msg)
    sys.stdout.write(f"Content-Length: {len(body.encode())}\r\n\r\n{body}")
    sys.stdout.flush()


def handle_initialize(params: Dict) -> Dict:
    """Handle MCP initialize request."""
    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {
            "tools": {
                "listChanged": False
            }
        },
        "serverInfo": {
            "name": "product-factory",
            "version": "1.0.0"
        }
    }


def handle_tools_list() -> Dict:
    """Handle MCP tools/list request."""
    return {
        "tools": [
            {
                "name": "factory_send_conversation",
                "description": "Send a conversation to the Product Factory for extraction and project creation",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Title for the conversation"
                        },
                        "intent": {
                            "type": "string",
                            "enum": ["save_idea", "new_project", "new_project_quick", "modify_project", "add_context"],
                            "description": "What to do with this conversation"
                        },
                        "messages": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "role": {"type": "string", "enum": ["user", "assistant"]},
                                    "content": {"type": "string"}
                                }
                            },
                            "description": "Conversation messages"
                        },
                        "project_name": {
                            "type": "string",
                            "description": "Project name (for new_project/new_project_quick)"
                        },
                        "target_project": {
                            "type": "string",
                            "description": "Target project name (for modify_project/add_context)"
                        }
                    },
                    "required": ["title", "intent", "messages"]
                }
            },
            {
                "name": "factory_list_conversations",
                "description": "List recent conversations sent to the factory",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string", "description": "Filter by source platform"},
                        "status": {"type": "string", "description": "Filter by status"},
                        "limit": {"type": "integer", "description": "Max results (default 20)"}
                    }
                }
            },
            {
                "name": "factory_get_conversation",
                "description": "Get details of a specific conversation",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "conversation_id": {"type": "string", "description": "Conversation ID"}
                    },
                    "required": ["conversation_id"]
                }
            },
            {
                "name": "factory_list_projects",
                "description": "List projects created from conversations",
                "inputSchema": {"type": "object", "properties": {}}
            },
            {
                "name": "factory_list_ideas",
                "description": "List extracted ideas pending review",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "description": "Filter by status (new, approved, rejected, promoted)"}
                    }
                }
            }
        ]
    }


def handle_tools_call(name: str, arguments: Dict) -> Dict:
    """Handle MCP tools/call request."""
    if name == "factory_send_conversation":
        data = {
            "source_platform": "claude",
            "intent": arguments.get("intent", "save_idea"),
            "title": arguments.get("title", ""),
            "messages": arguments.get("messages", []),
            "project_name": arguments.get("project_name", ""),
            "target_project_name": arguments.get("target_project", "")
        }
        result = api_request("POST", "/api/v1/intake", data)
        return {
            "content": [{
                "type": "text",
                "text": json.dumps(result, indent=2)
            }]
        }

    elif name == "factory_list_conversations":
        params = {}
        if arguments.get("source"):
            params["source"] = arguments["source"]
        if arguments.get("status"):
            params["status"] = arguments["status"]
        query = "&".join(f"{k}={v}" for k, v in params.items())
        path = f"/api/v1/conversations?{query}" if query else "/api/v1/conversations"
        result = api_request("GET", path)
        return {
            "content": [{
                "type": "text",
                "text": json.dumps(result, indent=2)
            }]
        }

    elif name == "factory_get_conversation":
        conv_id = arguments.get("conversation_id", "")
        result = api_request("GET", f"/api/v1/intake/{conv_id}")
        return {
            "content": [{
                "type": "text",
                "text": json.dumps(result, indent=2)
            }]
        }

    elif name == "factory_list_projects":
        result = api_request("GET", "/api/v1/projects")
        return {
            "content": [{
                "type": "text",
                "text": json.dumps(result, indent=2)
            }]
        }

    elif name == "factory_list_ideas":
        params = {}
        if arguments.get("status"):
            params["status"] = arguments["status"]
        query = "&".join(f"{k}={v}" for k, v in params.items())
        path = f"/api/v1/ideas?{query}" if query else "/api/v1/ideas"
        result = api_request("GET", path)
        return {
            "content": [{
                "type": "text",
                "text": json.dumps(result, indent=2)
            }]
        }

    else:
        return {
            "content": [{
                "type": "text",
                "text": f"Unknown tool: {name}"
            }],
            "isError": True
        }


def main():
    """Main MCP server loop."""
    while True:
        try:
            msg = read_message()
            if msg is None:
                break

            msg_id = msg.get("id")
            method = msg.get("method")
            params = msg.get("params", {})

            if method == "initialize":
                result = handle_initialize(params)
                write_message({"jsonrpc": "2.0", "id": msg_id, "result": result})

            elif method == "notifications/initialized":
                pass  # No response needed for notifications

            elif method == "tools/list":
                result = handle_tools_list()
                write_message({"jsonrpc": "2.0", "id": msg_id, "result": result})

            elif method == "tools/call":
                tool_name = params.get("name", "")
                arguments = params.get("arguments", {})
                result = handle_tools_call(tool_name, arguments)
                write_message({"jsonrpc": "2.0", "id": msg_id, "result": result})

            elif method == "ping":
                write_message({"jsonrpc": "2.0", "id": msg_id, "result": {}})

            else:
                write_message({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"}
                })

        except Exception as e:
            print(f"[MCP Error] {e}", file=sys.stderr)
            if msg_id:
                write_message({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32603, "message": str(e)}
                })


if __name__ == "__main__":
    main()
