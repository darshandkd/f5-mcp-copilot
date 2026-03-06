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

echo Starting F5 MCP Copilot Server...
.venv\Scripts\python f5_mcp_copilot.py
