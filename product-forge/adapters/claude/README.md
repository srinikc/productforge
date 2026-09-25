# Product Forge - Claude MCP Server Adapter

Thin MCP (Model Context Protocol) server that wraps the Product Forge REST API, allowing Claude Code to send conversations directly to the factory.

## Setup

1. Copy `claude_desktop_config.json` to your Claude Desktop config directory:
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`

2. Restart Claude Desktop

3. The "product-factory" tools will appear in Claude's available tools

## Available Tools

| Tool | Description |
|------|-------------|
| `factory_send_conversation` | Send a conversation with intent (save_idea, new_project, modify_project, add_context) |
| `factory_list_conversations` | List recent conversations with optional filters |
| `factory_get_conversation` | Get details of a specific conversation |
| `factory_list_projects` | List projects created from conversations |
| `factory_list_ideas` | List extracted ideas pending review |

## Usage Example

In Claude Code, you can say:
- "Send this conversation to the factory to create a new project"
- "List recent conversations in the factory"
- "Show me ideas from the factory"

## Configuration

Set environment variables in `claude_desktop_config.json`:
- `FACTORY_API_URL`: Backend API URL (default: http://localhost:8765)
- `FACTORY_API_KEY`: API key for authentication (optional)
