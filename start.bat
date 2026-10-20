@echo off
cd /d "%~dp0"
title Secondhand EC Agent V3 - Local Service

rem ---------- 1. create local config if missing ----------
if not exist "config\secrets.env" (
    if not exist "config" mkdir config
    copy "config\secrets.env.example" "config\secrets.env" >nul
    echo.
    echo [INFO] config\secrets.env created from the template.
    echo        Edit it if you want to enable DeepSeek, then run this file again.
    echo.
    pause
    exit /b 1
)

rem ---------- 2. start packaged executable when present ----------
if exist "SecondhandECAgent.exe" (
    echo Starting packaged local service...
    start "" http://127.0.0.1:8765
    SecondhandECAgent.exe
    pause
    exit /b %errorlevel%
)

rem ---------- 3. source mode: check Python ----------
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.11/3.12 and check "Add to PATH".
    pause
    exit /b 1
)

rem ---------- 4. install dependencies on first run ----------
python -c "import flask, dotenv, requests" >nul 2>nul
if errorlevel 1 (
    echo [INFO] Installing dependencies, please wait...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Install failed. Run manually: python -m pip install -r requirements.txt
        pause
        exit /b 1
    )
)

rem ---------- 5. ensure runtime directories ----------
if not exist "data" mkdir data
if not exist "logs" mkdir logs

rem ---------- 6. start source version ----------
echo Starting local service, opening http://127.0.0.1:8765 ...
echo Close this window to stop the service.
start "" http://127.0.0.1:8765
python run.py

pause
