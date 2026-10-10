@echo off
cd /d "%~dp0"
title Secondhand EC Agent V3 - Local Service

rem ---------- 1. auto-create secrets.env from template ----------
if not exist "config\secrets.env" (
    copy "config\secrets.env.example" "config\secrets.env" >nul
    echo.
    echo [INFO] config\secrets.env created from the template.
    echo        Edit it to fill in your DeepSeek API key, then run this file again.
    echo.
    pause
    exit /b 1
)

rem ---------- 2. check Python ----------
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.11/3.12 and check "Add to PATH".
    pause
    exit /b 1
)

rem ---------- 3. install dependencies on first run ----------
python -c "import flask, dotenv, PIL, requests" >nul 2>nul
if errorlevel 1 (
    echo [INFO] Installing dependencies, please wait...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Install failed. Run manually: python -m pip install -r requirements.txt
        pause
        exit /b 1
    )
)

rem ---------- 4. ensure directories ----------
if not exist "data" mkdir data
if not exist "images\imported" mkdir images\imported
if not exist "logs" mkdir logs

rem ---------- 5. start ----------
echo Starting local service, opening http://127.0.0.1:8765 ...
echo Close this window to stop the service.
timeout /t 2 /nobreak >nul
start "" http://127.0.0.1:8765
python run.py

pause
