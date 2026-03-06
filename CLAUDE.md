# CLAUDE.md

## Project Overview

F5 BIG-IP MCP Server for Microsoft Copilot - Streamable HTTP transport variant of f5-mcp.
Runs as a persistent HTTP service that Copilot Studio and VS Code GitHub Copilot connect to via URL.

## Key Constraints

- **Use MCP tools directly** - call `f5_tmsh` and `f5_bash` tools, never create Python scripts or test files
- **Execute commands through MCP only** - do not use raw SSH or subprocess calls
- **Knowledge base is read-only** - search via `f5_knowledge` tool, do not modify markdown files
- **Knowledge/ is a symlink** - points to ../f5-mcp/Knowledge, do not modify

## Architecture

```
f5_mcp_copilot.py (FastMCP server - Streamable HTTP)
    ├── Starlette App: CORS + API Key middleware
    ├── MCP endpoint: POST /mcp (JSON-RPC 2.0)
    ├── Device Registry: in-memory only, seeded from env, never written to disk
    ├── SSH Layer: ssh_exec() with ControlMaster multiplexing + TMSH shell auto-detect
    ├── Security: _security_check() pipeline (injection, credentials, network, privesc, exfil)
    ├── Knowledge Search: search_knowledge() - keyword-based file routing
    ├── External Docs: search_external_docs() - live search of F5 official sources
    ├── Error Handling: @_safe_tool decorator on all tools, structured logging
    └── MCP Tools: 13 tools
```

## Security Guardrails

All commands pass through `_security_check()` before reaching the device. The pipeline blocks:
- **Command injection**: shell chaining, encoded payloads, variable expansion
- **Credential access**: private keys, auth config, master keys
- **Network threats**: outbound connections, lateral movement, tunnel creation
- **Privilege escalation**: shell escapes, cron, kernel operations
- **Data exfiltration**: UCS exports, SCP/TFTP transfers, syslog redirection
- **Unsafe bash**: only allowlisted read-only commands permitted

Destructive TMSH commands (delete virtual/pool, load defaults) pass with a warning banner.

## Running

```bash
./setup.sh          # First time: create venv, install deps
./run_server.sh     # Start HTTP server on port 8080
```

## Configuration

Edit `.env` file:
- `F5_HOST` - F5 management IP (seeds initial device on startup)
- `F5_USER` - SSH username
- `F5_SSH_KEY` - Path to SSH private key
- `F5_PASSWORD` - SSH password (alternative to key)
- `MCP_HOST` - Server bind address (default: 0.0.0.0)
- `MCP_PORT` - Server port (default: 8080)
- `MCP_API_KEY` - API key for authentication

## Device Management

Devices live in memory only. `.env` seeds devices on startup; more can be added/removed via tools.

```
# Add, update, remove, switch default:
f5_add_device(host='10.1.1.100', ssh_key='~/.ssh/f5_key')
f5_add_device(host='10.1.1.100', ssh_key='~/.ssh/f5_key', name='prod')
f5_update_device(name='prod', ssh_key='~/.ssh/new_key')
f5_remove_device(name='prod')
f5_set_default(name='lab')
```

Password auth: configure in `.env` using `F5_DEVICE_{NAME}_PASSWORD`, never pass via tools.

## Differences from f5-mcp (stdio)

| Aspect | f5-mcp | f5-mcp-copilot |
|--------|--------|----------------|
| Transport | stdio | Streamable HTTP |
| Client | Claude Code | Copilot Studio / VS Code |
| Auth | None (local) | API key header |
| Session | Stateful | Stateless |
| Config | claude.json env vars | .env file |
| Device storage | config.json on disk | In-memory only (no file writes) |
| Knowledge path | `knowledge/` (lowercase) | `Knowledge/` (symlink) |
| External search | None (returns URLs only) | Live fetch from CloudDocs, DevCentral, AskF5 |
| Extra tools | — | `f5_search_docs`, `f5_update_device` |
