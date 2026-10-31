@echo off
setlocal EnableDelayedExpansion
title REFLOW STUDIO - SANDBOX TEST MODE

for %%i in ("%~dp0..") do set "ROOT=%%~fi"

echo ========================================================
echo        REFLOW STUDIO: ISOLATED SANDBOX TEST
echo ========================================================
echo.
echo [INFO] This script simulates a "Clean Windows Install".
echo [INFO] It hides your installed Python, FFmpeg, and System PATH.
echo [INFO] If the app launches here, it will launch ANYWHERE.
echo.

:: 1. NUKE ENVIRONMENT VARIABLES (Temporarily)
:: We clear the PATH so the app cannot find your system's Python or FFmpeg.
:: We only keep standard Windows system folders.
set PATH=C:\Windows\System32;C:\Windows;C:\Windows\System32\Wbem

:: 2. CLEAR PYTHON VARIABLES
:: This prevents it from accidentally seeing libraries installed on your C: drive.
set PYTHONPATH=
set PYTHONHOME=
set APPDATA=%ROOT%\temp\sandbox_appdata
set LOCALAPPDATA=%ROOT%\temp\sandbox_localappdata

:: 3. CREATE FAKE USER DIRECTORIES
:: We redirect "AppData" to a temp folder so it generates fresh config files.
if not exist "%APPDATA%" mkdir "%APPDATA%"
if not exist "%LOCALAPPDATA%" mkdir "%LOCALAPPDATA%"

echo [STATUS] Environment Stripped. System is now "Naked".
echo [STATUS] Launching Reflow Studio using ONLY portable files...
echo.

:: 4. LAUNCH (Using the Portable Python)
:: If build\windows-portable\python.exe isn't there, this will fail (which is good! It tells us what's missing).
if exist "%ROOT%\build\windows-portable\python.exe" (
    "%ROOT%\build\windows-portable\python.exe" "%ROOT%\main.py"
) else (
    echo [FAIL] Portable Python not found!
    echo        Looked for build\windows-portable\python.exe and failed.
    echo        Since we wiped the system PATH, it cannot fall back to your installed Python.
    echo.
    echo        FIX: Ensure the build\windows-portable folder exists at the project root.
    pause
    exit /b
)

echo.
echo [TEST COMPLETE] App closed.
pause
