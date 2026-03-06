@echo off
REM F5 MCP Copilot Server Setup - Windows
setlocal enabledelayedexpansion

echo === F5 MCP Copilot Server Setup ===

REM Find Python 3.10+
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo Python 3.10+ required. Install from https://www.python.org/downloads/
    exit /b 1
)

for /f "tokens=*" %%i in ('python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"') do set PYVER=%%i
echo Using Python %PYVER%

REM Create venv
if exist .venv (
    echo Removing existing venv...
    rmdir /s /q .venv
)

echo Creating virtual environment...
python -m venv .venv

echo Installing dependencies...
.venv\Scripts\pip install --upgrade pip -q
.venv\Scripts\pip install -r requirements.txt -q
.venv\Scripts\pip install python-dotenv -q

REM Check Knowledge directory
if exist Knowledge (
    echo Knowledge directory found.
) else (
    echo Warning: Knowledge directory not found. Knowledge search will be unavailable.
    echo Copy or symlink the Knowledge folder from f5-mcp if available.
)

REM Verify installation
echo Verifying installation...
.venv\Scripts\python -c "from mcp.server.fastmcp import FastMCP; print('MCP installed')"
if %errorlevel% neq 0 (
    echo Installation failed. Check requirements.txt
    exit /b 1
)

REM Create .env if missing
if not exist .env (
    copy .env.example .env
    echo Created .env from template - edit with your F5 device details
)

echo.
echo === Setup Complete ===
echo.
echo Next steps:
echo   1. Edit .env with your F5 device and API key settings
echo   2. Run: run_server.bat
