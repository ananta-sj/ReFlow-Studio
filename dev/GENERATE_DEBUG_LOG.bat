@echo off
title Reflow Studio - Debug Tool
color 0E

for %%i in ("%~dp0..") do set "ROOT=%%~fi"

echo ======================================================
echo    REFLOW STUDIO: BLACK BOX RECORDER
echo ======================================================
echo.
echo [INFO] Generating crash report...
echo        Please wait, this may take 10-20 seconds.

set LOGFILE=%ROOT%\debug_log.txt

REM --- HEADER ---
echo REFLOW STUDIO DEBUG LOG > "%LOGFILE%"
echo Generated on %date% %time% >> "%LOGFILE%"
echo ------------------------------------------ >> "%LOGFILE%"

REM --- 1. SYSTEM INFO ---
echo [SYSTEM INFO] >> "%LOGFILE%"
ver >> "%LOGFILE%"
echo. >> "%LOGFILE%"
echo GPU Devices: >> "%LOGFILE%"
wmic path win32_VideoController get name >> "%LOGFILE%" 2>nul
echo. >> "%LOGFILE%"
echo RAM Available: >> "%LOGFILE%"
wmic OS get FreePhysicalMemory /Value >> "%LOGFILE%" 2>nul

REM --- 2. PYTHON ENVIRONMENT ---
echo. >> "%LOGFILE%"
echo ------------------------------------------ >> "%LOGFILE%"
echo [PYTHON ENVIRONMENT] >> "%LOGFILE%"

if exist "%ROOT%\build\windows-portable\python.exe" (
    echo Python Path: build\windows-portable (Portable) >> "%LOGFILE%"
    "%ROOT%\build\windows-portable\python.exe" --version >> "%LOGFILE%"
    echo. >> "%LOGFILE%"
    echo [PIP PACKAGE LIST] >> "%LOGFILE%"
    "%ROOT%\build\windows-portable\python.exe" -m pip list >> "%LOGFILE%"
) else (
    echo Python Path: NOT FOUND / System Default >> "%LOGFILE%"
    python --version >> "%LOGFILE%" 2>&1
)

REM --- 3. FOLDER STRUCTURE ---
echo. >> "%LOGFILE%"
echo ------------------------------------------ >> "%LOGFILE%"
echo [FOLDER INTEGRITY] >> "%LOGFILE%"
echo Project Root: %ROOT% >> "%LOGFILE%"
echo. >> "%LOGFILE%"
echo Critical Files Check: >> "%LOGFILE%"
if exist "%ROOT%\main.py" (echo [OK] main.py) >> "%LOGFILE%" else (echo [MISSING] main.py) >> "%LOGFILE%"
if exist "%ROOT%\core\integrity.py" (echo [OK] core\integrity.py) >> "%LOGFILE%" else (echo [MISSING] core\integrity.py) >> "%LOGFILE%"
if exist "%ROOT%\core\pipeline.py" (echo [OK] core\pipeline.py) >> "%LOGFILE%" else (echo [MISSING] core\pipeline.py) >> "%LOGFILE%"

echo. >> "%LOGFILE%"
echo [DONE] Log saved to '%LOGFILE%'.
echo.
echo ======================================================
echo    DEBUG LOG GENERATED SUCCESSFULLY!
echo ======================================================
echo Please send the file 'debug_log.txt' to support.
echo.
pause
