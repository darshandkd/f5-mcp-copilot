#!/bin/bash
# F5 MCP Copilot Server Setup
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
MIN_PYTHON="3.10"

echo "=== F5 MCP Copilot Server Setup ==="

# Find Python 3.10+
find_python() {
    for cmd in python3.13 python3.12 python3.11 python3.10 python3; do
        if command -v "$cmd" &>/dev/null; then
            version=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
            if [ "$(printf '%s\n' "$MIN_PYTHON" "$version" | sort -V | head -n1)" = "$MIN_PYTHON" ]; then
                echo "$cmd"
                return 0
            fi
        fi
    done
    return 1
}

PYTHON_CMD=$(find_python)
if [ -z "$PYTHON_CMD" ]; then
    echo "Python $MIN_PYTHON+ required. Install with: brew install python@3.12"
    exit 1
fi
echo "Using $PYTHON_CMD ($($PYTHON_CMD --version))"

# Create/recreate venv
if [ -d "$VENV_DIR" ]; then
    echo "Removing existing venv..."
    rm -rf "$VENV_DIR"
fi

echo "Creating virtual environment..."
"$PYTHON_CMD" -m venv "$VENV_DIR"

echo "Installing dependencies..."
"$VENV_DIR/bin/pip" install --upgrade pip -q
"$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements.txt" -q
"$VENV_DIR/bin/pip" install python-dotenv -q

# Verify Knowledge symlink
if [ -L "$SCRIPT_DIR/Knowledge" ]; then
    echo "Knowledge symlink OK -> $(readlink "$SCRIPT_DIR/Knowledge")"
elif [ -d "$SCRIPT_DIR/../f5-mcp/Knowledge" ]; then
    echo "Creating Knowledge symlink..."
    ln -sf ../f5-mcp/Knowledge "$SCRIPT_DIR/Knowledge"
    echo "Knowledge symlink created"
else
    echo "Warning: Knowledge directory not found. Knowledge search will be unavailable."
fi

# Verify installation
echo "Verifying installation..."
if "$VENV_DIR/bin/python" -c "from mcp.server.fastmcp import FastMCP; print('MCP installed')" 2>/dev/null; then
    echo "All dependencies installed successfully"
else
    echo "Installation failed. Check requirements.txt"
    exit 1
fi

# Test script syntax
if "$VENV_DIR/bin/python" -m py_compile "$SCRIPT_DIR/f5_mcp_copilot.py" 2>/dev/null; then
    echo "f5_mcp_copilot.py syntax OK"
else
    echo "f5_mcp_copilot.py has syntax errors"
    exit 1
fi

# Create .env if missing
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
    echo "Created .env from template - edit with your F5 device details"
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit .env with your F5 device and API key settings"
echo "  2. Run: ./run_server.sh"
echo "  3. Test: curl -X POST http://localhost:8080/mcp -H 'Content-Type: application/json' -H 'x-api-key: YOUR_KEY' -d '{\"jsonrpc\":\"2.0\",\"method\":\"initialize\",\"id\":1,\"params\":{\"protocolVersion\":\"2024-11-05\",\"capabilities\":{},\"clientInfo\":{\"name\":\"test\",\"version\":\"1.0\"}}}'"
