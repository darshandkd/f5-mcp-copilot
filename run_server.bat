@echo off
REM F5 MCP Copilot Server Launcher - Windows
setlocal enabledelayedexpansion

REM Auto-setup if venv missing
if not exist .venv (
    echo Virtual environment not found. Running setup...
    call setup.bat
)

REM Load .env file
if exist .env (
    for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
        set "line=%%a"
        if not "!line:~0,1!"=="#" (
            if not "%%a"=="" set "%%a=%%b"
        )
    )
)

REM Prompt for MCP_API_KEY if not set via environment
REM Secure usage: set MCP_API_KEY=xxx && run_server.bat
if "%MCP_API_KEY%"=="" (
    set /p "MCP_API_KEY=Enter MCP API Key (or press Enter to skip): "
)

echo Starting F5 MCP Copilot Server...
.venv\Scripts\python f5_mcp_copilot.py
