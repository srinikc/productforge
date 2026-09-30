# MCP (Model Context Protocol) Interop — Design (BI-0196)

## Goal
Make Product Forge's tools the ecosystem standard: **expose our `ToolRegistry` as an MCP server** and
**consume external MCP servers** as tools our agents can call — modular, API-first, no fork of the tool
loop.

## 360° — verified current state
| Concern | Now | Target | Owner |
|---|---|---|---|
| Tools | `core/tool_registry.py` (`ToolRegistry`, `ToolSpec{name,description,parameters,dangerous,requires_approval}`, `schemas()`, `execute(name,args,workspace)->ToolResult`) | expose via MCP; consume external | reuse |
| Tool loop | `agent_runner._generate_with_tools` + `tool_policy.tools_for` | unchanged; external MCP tools join the registry | reuse |
| MCP config | `byot_integration.CustomMCPServer` (metadata only) | real client/server | reuse + extend |
| Registry framework | `core/plugins.py` (BI-0200) kind `tool` | a `mcp` plugin kind could register servers | reuse |
| API | `/api/v1/tools` (if any) | + `/api/v1/mcp/*` | `dashboard/api` |

**Blast radius:** new `core/mcp.py` (pure JSON-RPC maps + client), API endpoints, optional wiring.
**No network in tests** (stdio/loopback fake). No new store (servers read from config/plugins).

## Design decisions (modular)
- **New `core/mcp.py`** — the MCP protocol mapping + a minimal, dependency-free implementation:
  - **Server side (`handle(request, registry)`)**: JSON-RPC 2.0 — `initialize`, `tools/list`
    (map `ToolSpec`→MCP `{name,description,inputSchema}`), `tools/call` (`execute`→`{content:[{type:"text",text}]}`).
    Follows the danger/approval flag: `requires_approval` tools return an MCP error unless approved.
  - **Client side (`call(server, method, params)`)**: JSON-RPC over stdio (subprocess) or HTTP; returns
    parsed result; **fail-closed** on transport/JSON errors (never raises into the pipe).
  - **`ingest_tools(server) -> [ToolSpec]`**: `tools/list` from an external server → `ToolSpec`s registered
    into `ToolRegistry` (so agents call them like any tool).
- **Reuse, never fork:** the tool loop, `ToolRegistry`, `ToolResult`, and danger/approval semantics are
  unchanged; MCP is a **transport/adapter** around them. MCP servers are config (byot/plugins), not a new store.
- **Security/approval at the boundary:** `tools/call` for a `requires_approval`/`dangerous` tool must carry
  an explicit approval token; otherwise **fail-closed** (mirror `tool_policy` / EOS boundary authz). No
  shell injection: `run_command` stays allowlisted.
- **API-first:** `GET /api/v1/mcp/tools` (our tools as MCP descriptors), `POST /api/v1/mcp/rpc` (JSON-RPC
  endpoint = the MCP server surface), `GET /api/v1/mcp/servers` (configured external servers).
- **Scalable:** stateless JSON-RPC; stdio client per call (bounded); no global state.
- **Optional live:** actual stdio spawn only when a server is configured; tests use an in-process fake.

## Plan (branch `feature/bi-0196-mcp`)
1. `docs/MCP-DESIGN.md` (this file).
2. `core/mcp.py` — `handle`/`describe_tools` (server), `call` (client), `ingest_tools`.
3. `config/mcp-servers.json` (external server list; empty) + register in store-registry.
4. `dashboard/api/app.py` — `/api/v1/mcp/tools`, `/api/v1/mcp/rpc`, `/api/v1/mcp/servers`.
5. Wire: allow `ingest_tools` results into a `ToolRegistry` via `tool_policy`/agent tool loop (guarded).
6. Tests `test_mcp.py` — server `initialize`/`tools/list`/`tools/call` round-trip; approval gate fails
   closed; client call against a fake server; ingest registers external tools.
7. Gates: compileall, wired_audit, workflow_matrix, pipeline tests, precheck.
8. Merge; close `BI-0196` through the loop.

## Acceptance
- An MCP client can `tools/list` + `tools/call` our tools via `/api/v1/mcp/rpc` (round-trip).
- Our agents can ingest + call an external (fake) MCP tool.
- `requires_approval`/`dangerous` tools fail-closed without approval; unknown method/tool ⇒ JSON-RPC error.
- `precheck` PASS; no new module fork; API-first.

## Out of scope (tracked separately)
A2A (0197), remote auth flows for MCP, streaming MCP transports.
