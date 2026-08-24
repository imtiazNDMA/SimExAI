@echo off
REM ===========================================================
REM  SimEx AI - one-command dev launcher
REM
REM  Double-click this file, or run from a terminal:
REM      start.bat
REM      start.bat -Port 8080
REM      start.bat -NoSync
REM      start.bat -NoBrowser
REM      start.bat -Https
REM
REM  All arguments are passed through to start.ps1.
REM ===========================================================

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
set "RC=%errorlevel%"

REM Keep the window open on failure so the error is readable
REM when launched by double-click rather than from a terminal.
REM Captured first: pause resets errorlevel.
if not "%RC%"=="0" (
    echo.
    echo Startup failed - see the messages above.
    pause
)

exit /b %RC%
