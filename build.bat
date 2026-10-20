@echo off
cd /d "%~dp0"
title Secondhand EC Agent V3 - Build Portable

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.11/3.12 and check "Add to PATH".
    pause
    exit /b 1
)

python -c "import flask, dotenv, requests, PyInstaller" >nul 2>nul
if errorlevel 1 (
    echo [INFO] Installing dependencies, please wait...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Dependency install failed.
        pause
        exit /b 1
    )
)

rem ---------- clean old artifacts ----------
if exist "dist\SecondhandECAgent" rmdir /s /q "dist\SecondhandECAgent"
if exist "build" rmdir /s /q "build"
if exist "SecondhandECAgent.spec" del "SecondhandECAgent.spec"

rem ---------- PyInstaller (real secrets.env is NOT bundled) ----------
python -m PyInstaller --noconfirm --clean --name SecondhandECAgent ^
  --paths . ^
  --add-data "app\templates;app\templates" ^
  run.py
if errorlevel 1 (
    echo [ERROR] PyInstaller failed.
    pause
    exit /b 1
)

rem ---------- portable runtime files ----------
if not exist "dist\SecondhandECAgent" mkdir "dist\SecondhandECAgent"
copy "dist\SecondhandECAgent.exe" "dist\SecondhandECAgent\SecondhandECAgent.exe" >nul
if errorlevel 1 (
    echo [ERROR] Could not copy SecondhandECAgent.exe into the portable folder.
    pause
    exit /b 1
)
if not exist "dist\SecondhandECAgent\config" mkdir "dist\SecondhandECAgent\config"
copy "config\secrets.env.example" "dist\SecondhandECAgent\config\secrets.env.example" >nul
if not exist "dist\SecondhandECAgent\data" mkdir "dist\SecondhandECAgent\data"
if not exist "dist\SecondhandECAgent\logs" mkdir "dist\SecondhandECAgent\logs"
copy "start.bat" "dist\SecondhandECAgent\start.bat" >nul
copy "README_*.txt" "dist\SecondhandECAgent\" >nul
copy "README_*.md" "dist\SecondhandECAgent\" >nul
copy "requirements.txt" "dist\SecondhandECAgent\requirements.txt" >nul

echo.
echo [DONE] Portable folder: dist\SecondhandECAgent\
echo Copy the whole folder to the target PC, edit config\secrets.env, run start.bat.
echo Note: real secrets are NOT bundled; re-fill them on the target PC.
pause
