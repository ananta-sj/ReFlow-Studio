@echo off
setlocal
cd /d "%~dp0"
set "PYTHONDONTWRITEBYTECODE=1"
title Reflow Studio (Ironclad)
color 0F

echo ======================================================
echo    STARTING REFLOW STUDIO
echo ======================================================

REM -------------------------------------------------------------
REM 0. USE A BUILT EXECUTABLE ONLY WHEN PORTABLE PYTHON IS ABSENT
REM    (packaging/build_dist.py / .github/workflows/build.yml) - if it's
REM    been built, it already bundles its own Python runtime and needs
REM    none of the steps below.
REM -------------------------------------------------------------
if not exist "build\windows-portable\python.exe" if exist "dist\ReflowStudio\ReflowStudio.exe" (
    echo [INFO] Launching packaged build...
    "dist\ReflowStudio\ReflowStudio.exe"
    goto :eof
)

echo [INFO] Starting portable source setup.

REM -------------------------------------------------------------
REM 1. LOCATE PYTHON
REM -------------------------------------------------------------
if exist "build\windows-portable\python.exe" (
    set "PY=build\windows-portable\python.exe"
) else if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
) else if exist "python.exe" (
    set "PY=python.exe"
) else (
    echo [WARN] Portable Python not found. Using System Python.
    set "PY=python"
)
echo [INFO] Python Engine: %PY%

REM -------------------------------------------------------------
REM 2. SYSTEM INTEGRITY CHECK (The Gatekeeper)
REM -------------------------------------------------------------
echo.
echo [1/2] RUNNING INTEGRITY GUARD...
"%PY%" core\integrity.py

if %errorlevel% neq 0 (
    color 0C
    echo.
    echo [CRITICAL] INTEGRITY CHECK FAILED.
    echo The app cannot start because required runtime libraries are unavailable.
    echo Check the error message above.
    pause
    exit /b
)

REM -------------------------------------------------------------
REM 3. SETUP FFmpeg
REM -------------------------------------------------------------
if exist "ffmpeg\bin" (
    set "PATH=%~dp0ffmpeg\bin;%PATH%"
    echo [INFO] FFmpeg Path Linked.
) else if exist "ffmpeg" (
    set "PATH=%~dp0ffmpeg;%PATH%"
    echo [INFO] FFmpeg Path Linked.
)

REM -------------------------------------------------------------
REM 4. VERIFY FRONTEND BUILD EXISTS
REM -------------------------------------------------------------
if not exist "frontend\dist\index.html" (
    color 0C
    echo.
    echo [CRITICAL] Frontend build not found at frontend\dist\index.html.
    echo This portable build is incomplete - the UI was never built.
    echo If you are developing this app, run:
    echo     cd frontend ^&^& npm install ^&^& npm run build
    pause
    exit /b
)

REM -------------------------------------------------------------
REM 5. LAUNCH APP
REM -------------------------------------------------------------
echo.
echo [2/2] LAUNCHING REFLOW STUDIO...
"%PY%" main.py

if %errorlevel% neq 0 (
    color 0C
    echo [CRITICAL] The App Crashed. See log above.
    pause
)
