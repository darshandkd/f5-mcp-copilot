#!/bin/bash
# F5 MCP Copilot Server Launcher — production-grade with auto-restart
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
LOG_DIR="$SCRIPT_DIR/logs"
MAX_RESTARTS=10
RESTART_DELAY=3
COOLDOWN_WINDOW=60  # reset restart counter if stable for this many seconds

# Auto-setup if venv missing
if [ ! -d "$VENV_DIR" ]; then
    echo "Virtual environment not found. Running setup..."
    "$SCRIPT_DIR/setup.sh"
fi

# Source .env if present (non-secret config only)
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    source "$SCRIPT_DIR/.env"
    set +a
fi

# Prompt for MCP_API_KEY if not set via environment
# Secure usage: MCP_API_KEY=xxx ./run_server.sh
# Or: export MCP_API_KEY=xxx
if [ -z "$MCP_API_KEY" ]; then
    read -s -p "Enter MCP API Key (or press Enter to skip): " MCP_API_KEY
    echo
    if [ -n "$MCP_API_KEY" ]; then
        export MCP_API_KEY
    fi
fi

# Create logs directory
mkdir -p "$LOG_DIR"

# Cleanup stale processes on same port
PORT="${MCP_PORT:-8080}"
EXISTING_PID=$(lsof -ti :"$PORT" 2>/dev/null || true)
if [ -n "$EXISTING_PID" ]; then
    echo "Port $PORT in use by PID $EXISTING_PID — stopping it..."
    kill "$EXISTING_PID" 2>/dev/null || true
    sleep 1
fi

echo "========================================"
echo " F5 MCP Copilot Server"
echo " Port: $PORT | Auto-restart: enabled"
echo " Logs: $LOG_DIR/server.log"
echo "========================================"

restart_count=0
last_start=0

while true; do
    now=$(date +%s)

    # Reset counter if server was stable for COOLDOWN_WINDOW seconds
    elapsed=$((now - last_start))
    if [ "$elapsed" -gt "$COOLDOWN_WINDOW" ]; then
        restart_count=0
    fi

    if [ "$restart_count" -ge "$MAX_RESTARTS" ]; then
        echo "[$(date)] FATAL: Server crashed $MAX_RESTARTS times within ${COOLDOWN_WINDOW}s. Giving up."
        echo "[$(date)] Check logs: $LOG_DIR/server.log"
        exit 1
    fi

    last_start=$now
    restart_count=$((restart_count + 1))

    if [ "$restart_count" -gt 1 ]; then
        echo "[$(date)] Restarting server (attempt $restart_count/$MAX_RESTARTS) in ${RESTART_DELAY}s..."
        sleep "$RESTART_DELAY"
    fi

    echo "[$(date)] Starting server..."
    "$VENV_DIR/bin/python" "$SCRIPT_DIR/f5_mcp_copilot.py" 2>&1 | tee -a "$LOG_DIR/server.log"
    EXIT_CODE=$?

    if [ "$EXIT_CODE" -eq 0 ]; then
        echo "[$(date)] Server stopped cleanly (exit 0)."
        break
    fi

    echo "[$(date)] Server exited with code $EXIT_CODE."
done
