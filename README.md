# F5 BIG-IP MCP Server for Copilot

Connect any AI Copilot in VS Code to your F5 BIG-IP load balancers. Runs as an HTTP server that exposes F5 management tools via the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/).

Works with **GitHub Copilot**, **Cline**, **Continue**, **Roo Code**, and any VS Code extension that supports MCP over Streamable HTTP.

## What It Does

Ask your Copilot to manage F5 devices in natural language:

- "Show me all pools and their member status"
- "Create a virtual server on port 443 with SSL offloading"
- "Why is pool member 10.0.1.5 marked down?"
- "Search F5 docs for iRule HTTP redirect examples"

The server provides 13 tools: device management, TMSH/bash execution, local + external knowledge search.

---

## Prerequisites

| Requirement | Details |
|---|---|
| **Python** | 3.10 or higher |
| **F5 BIG-IP** | Any version with SSH enabled |
| **SSH access** | Key-based or password-based (password requires `sshpass`) |
| **VS Code** | Any version with a Copilot/AI extension installed |

### Install `sshpass` (only if using password auth)

| OS | Command |
|---|---|
| macOS | `brew install hudochenkov/sshpass/sshpass` |
| Ubuntu/Debian | `sudo apt install sshpass` |
| RHEL/CentOS | `sudo yum install sshpass` |
| Windows | Not natively available. Use SSH keys or run from WSL. |

---

## Quick Start

### 1. Clone the repo

```bash
git clone https://github.com/darshandkd/f5-mcp-copilot.git
cd f5-mcp-copilot
```

### 2. Run setup

**macOS / Linux:**
```bash
chmod +x setup.sh
./setup.sh
```

**Windows (Command Prompt):**
```cmd
setup.bat
```

**Manual (any OS):**
```bash
python -m venv .venv
# Activate: source .venv/bin/activate (Linux/Mac) or .venv\Scripts\activate (Windows)
pip install -r requirements.txt python-dotenv
```

### 3. Configure

Edit `.env` (created automatically from `.env.example`):

```env
# F5 Device (seeds initial device on startup)
F5_HOST=10.1.1.100            # Your F5 management IP
F5_USER=admin                  # SSH username
F5_SSH_KEY=~/.ssh/f5_key       # SSH key path (use this OR password)
# F5_PASSWORD=your-password    # Uncomment for password auth
F5_PORT=22

# Server
MCP_HOST=0.0.0.0               # Bind address
MCP_PORT=8080                   # Server port
MCP_API_KEY=your-secret-key     # Protects the /mcp endpoint
```

> Pick **one** auth method: `F5_SSH_KEY` or `F5_PASSWORD`. If both are set, SSH key takes priority.

### 4. Start the server

**macOS / Linux:**
```bash
./run_server.sh
```

**Windows:**
```cmd
run_server.bat
```

**Manual:**
```bash
source .venv/bin/activate    # Linux/Mac
# .venv\Scripts\activate     # Windows
python f5_mcp_copilot.py
```

You should see:
```
========================================
 F5 MCP Copilot Server
 Port: 8080 | Auto-restart: enabled
 Logs: /path/to/logs/server.log
========================================
[date] Starting server...
F5 MCP Copilot Server starting on http://0.0.0.0:8080/mcp
API Key auth: enabled
Default F5 device: admin@10.1.1.100
```

The launcher (`run_server.sh`) automatically restarts the server on crashes with a cooldown window.

### 5. Verify

```bash
curl -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -H "x-api-key: your-secret-key" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
```

You should get a JSON response listing all 13 tools.

---

## Connect to VS Code Copilot

### Option A: Use the included config (recommended)

This repo includes `.vscode/mcp.json`. Open the project folder in VS Code and it will auto-detect the MCP server. VS Code will prompt you for the API key on first use.

### Option B: Add to any VS Code workspace

Create or edit `.vscode/mcp.json` in your project:

```json
{
  "servers": {
    "f5-mcp": {
      "type": "http",
      "url": "http://localhost:8080/mcp",
      "headers": {
        "x-api-key": "${input:f5-api-key}"
      }
    }
  },
  "inputs": [
    {
      "id": "f5-api-key",
      "type": "promptString",
      "description": "API key for F5 MCP server",
      "password": true
    }
  ]
}
```

### Option C: Add to VS Code User Settings (global)

Open **Settings** > search for `mcp` > edit `settings.json`:

```json
{
  "mcp": {
    "servers": {
      "f5-mcp": {
        "type": "http",
        "url": "http://localhost:8080/mcp",
        "headers": {
          "x-api-key": "${input:f5-api-key}"
        }
      }
    }
  },
  "inputs": [
    {
      "id": "f5-api-key",
      "type": "promptString",
      "description": "API key for F5 MCP server",
      "password": true
    }
  ]
}
```

> **Note:** Avoid hardcoding the API key in `settings.json` — use `${input:f5-api-key}` so VS Code prompts for it securely.

### Using it

1. Open **Copilot Chat** in VS Code (Ctrl+Shift+I / Cmd+Shift+I)
2. Switch to **Agent mode** (click the mode dropdown at the top of the chat panel)
3. The F5 tools appear automatically. Ask questions like:
   - "List my F5 devices"
   - "Show the status of all pools"
   - "What version of BIG-IP is running?"

> **Agent mode is required.** MCP tools are not available in Ask or Edit modes.

---

## Compatible AI Extensions

This server works with any VS Code extension that supports MCP over Streamable HTTP:

| Extension | Config Location | Notes |
|---|---|---|
| **GitHub Copilot** | `.vscode/mcp.json` | Built-in MCP support (Agent mode) |
| **Cline** | Cline MCP settings | Add as "Streamable HTTP" server |
| **Continue** | `~/.continue/config.json` | Add under `mcpServers` |
| **Roo Code** | Roo Code settings | Add as MCP server |

All models available through these extensions (GPT-4o, Claude, Gemini, Llama, etc.) can use the F5 tools. The tools are model-agnostic — they return plain text that any LLM can interpret.

---

## Adding More F5 Devices

The `.env` file seeds your first device on startup. You can add more devices anytime — either through the Copilot chat or by editing `.env`.

### In chat (natural language or tool calls)

Just tell your Copilot what you want:

```
"Add F5 device 10.1.1.200 with SSH key ~/.ssh/bigip_prod"
"Add F5 device bigip1.lab with user root and SSH key ~/.ssh/lab_key, call it lab"
"Switch default device to lab"
"Show me all my F5 devices"
"Remove device lab"
```

Or use the tools directly:

| Action | Tool Call |
|---|---|
| Add device | `f5_add_device(host='10.1.1.200', ssh_key='~/.ssh/f5_key')` |
| Add with name | `f5_add_device(host='10.1.1.200', ssh_key='~/.ssh/f5_key', name='prod')` |
| List all | `f5_devices()` |
| Update | `f5_update_device(name='prod', ssh_key='~/.ssh/new_key')` |
| Switch default | `f5_set_default(name='lab')` |
| Remove | `f5_remove_device(name='lab')` |

### In `.env` file (supports both SSH key and password)

Add named devices using the `F5_DEVICE_{NAME}_{FIELD}` pattern, then restart the server:

```env
# Production (password auth)
F5_DEVICE_PROD_HOST=10.1.1.200
F5_DEVICE_PROD_USER=admin
F5_DEVICE_PROD_PASSWORD=your-password

# Lab (SSH key auth)
F5_DEVICE_LAB_HOST=192.168.1.50
F5_DEVICE_LAB_USER=root
F5_DEVICE_LAB_SSH_KEY=~/.ssh/lab_key
```

All named devices load automatically alongside the default device on startup.

> **Why passwords go in `.env`:** Anything typed in chat is visible on screen and sent to your AI provider. SSH key *paths* are safe to type (they're just file locations), but passwords are secrets — so those go in `.env` only.

---

## Tools Reference

| Tool | Description |
|---|---|
| `f5_devices` | List configured devices |
| `f5_add_device` | Add a device (SSH key via chat, password via `.env`) |
| `f5_update_device` | Update device host, user, SSH key, or port |
| `f5_remove_device` | Remove a device (clears credentials from memory) |
| `f5_set_default` | Set the default device |
| `f5_test` | Test SSH connectivity |
| `f5_tmsh` | Execute TMSH commands |
| `f5_bash` | Execute bash commands on F5 |
| `f5_knowledge` | Search local + external F5 knowledge base |
| `f5_search_docs` | Search DevCentral, CloudDocs, AskF5 |
| `f5_doc_urls` | Get official F5 documentation links |
| `f5_query` | Ask F5 questions with optional device validation |

---

## Knowledge Base

The server includes a local knowledge base (`Knowledge/` directory) covering:

- TMSH command reference and cheat sheet
- LTM fundamentals (pools, virtuals, monitors)
- SSL/TLS configuration
- iRules reference
- High availability and failover
- Network configuration
- Troubleshooting guides

When local knowledge doesn't cover a topic, the server automatically searches official F5 sources (DevCentral, CloudDocs, AskF5 K-articles).

---

## Troubleshooting

**Server won't start — port in use:**
Change `MCP_PORT` in `.env` to a different port (e.g., `8081`).

**"sshpass not installed" error:**
Install `sshpass` (see Prerequisites) or switch to SSH key authentication.

**Tools not showing in Copilot:**
- Ensure the server is running (`curl http://localhost:8080/mcp` should respond)
- Ensure you're in **Agent mode** (not Ask or Edit mode)
- Check `.vscode/mcp.json` URL and API key match your `.env`
- Reload VS Code window (Ctrl+Shift+P > "Reload Window")

**SSH connection fails:**
- Verify the F5 is reachable: `ping <F5_HOST>`
- Verify SSH port is open: `nc -zv <F5_HOST> 22`
- Test manually: `ssh -i <key> admin@<F5_HOST> "tmsh show sys version"`
- Check the server logs for detailed error messages

**Windows-specific:**
- Use WSL or Git Bash if `setup.bat` has issues
- For SSH key auth, use forward slashes in key paths (`C:/Users/you/.ssh/f5_key`)
- Symlinks require admin privileges on Windows; copy the `Knowledge/` folder instead

---

## Production Features

| Feature | Details |
|---|---|
| **TMSH Shell Auto-Detection** | Automatically detects if the F5 admin user has TMSH as default shell (vs bash) and adjusts commands accordingly. No configuration needed. |
| **SSH Connection Multiplexing** | Reuses SSH connections via ControlMaster — first command opens the connection, subsequent commands reuse it for ~5 minutes. Dramatically reduces latency. |
| **Auto-Restart** | `run_server.sh` restarts the server on crashes (up to 10 times within 60s cooldown). Logs to `logs/server.log`. |
| **Structured Logging** | All operations logged with timestamps and severity levels. Tool errors are caught and returned as friendly messages instead of crashing the server. |
| **Error Isolation** | Every tool is wrapped with `@_safe_tool` — exceptions are caught, logged, and returned as user-friendly error messages. The server never crashes from a single bad request. |

---

## Security

| What | How |
|---|---|
| **SSH keys** | Add via chat (`ssh_key='~/.ssh/key'`) or `.env` — file paths are not secrets |
| **Passwords** | `.env` file only — never type in chat (they'd be sent to the AI provider) |
| **API key** | Set `MCP_API_KEY` in `.env` — protects the `/mcp` endpoint |
| **Credentials** | Stored in memory only — never written to disk by the server |
| **`.env` file** | Gitignored — your secrets won't be committed |
| **Network** | Binds to `0.0.0.0` by default — use `MCP_HOST=127.0.0.1` for local-only access |
| **Security Guardrails** | Server-side validation blocks command injection, credential theft, lateral movement, privilege escalation, and data exfiltration before commands reach the device |

---

## License

MIT
