@echo off
setlocal
title SimEx AI - NDMA Simulation Exercise Chatbot

REM Always run from the project root, regardless of where the .bat is invoked from
cd /d "%~dp0"

set "HOST=127.0.0.1"
set "PORT=8000"

echo ================================================
echo   SimEx AI - starting up
echo ================================================
echo.

REM --- 1. Locate uv -------------------------------------------------------
where uv >nul 2>&1
if errorlevel 1 (
    if exist "%USERPROFILE%\.local\bin\uv.exe" (
        set "PATH=%USERPROFILE%\.local\bin;%PATH%"
    ) else (
        echo [ERROR] 'uv' was not found on PATH.
        echo         Install it with:  winget install astral-sh.uv
        echo         or see https://docs.astral.sh/uv/
        echo.
        pause
        exit /b 1
    )
)

REM --- 2. Check .env ------------------------------------------------------
if not exist ".env" (
    echo [WARN] No .env file found. PINECONE_API_KEY / OLLAMA_BASE_URL will fall
    echo        back to defaults and the app may fail to answer queries.
    if exist ".env.example" (
        echo        Copy .env.example to .env and fill in your keys:
        echo            copy .env.example .env
    )
    echo.
)

REM --- 3. Sync dependencies ----------------------------------------------
echo [1/3] Syncing dependencies (uv sync)...
call uv sync
if errorlevel 1 (
    echo.
    echo [ERROR] 'uv sync' failed. Fix the errors above and re-run.
    pause
    exit /b 1
)
echo.

REM --- 4. Free the port if something is already listening -----------------
netstat -ano | findstr /r /c:"LISTENING" | findstr /c:":%PORT% " >nul 2>&1
if not errorlevel 1 (
    echo [WARN] Port %PORT% is already in use.
    echo        Close the other server, or set PORT above to a free port.
    echo.
    pause
    exit /b 1
)

REM --- 5. Open the browser once the server is up --------------------------
echo [2/3] Opening http://%HOST%:%PORT% in your browser...
start "" /b cmd /c "timeout /t 5 /nobreak >nul & start "" http://%HOST%:%PORT%"

REM --- 6. Run the server (foreground - Ctrl+C to stop) --------------------
echo [3/3] Starting FastAPI server on http://%HOST%:%PORT%
echo       Press Ctrl+C in this window to stop.
echo.
call uv run uvicorn backend.app:app --host %HOST% --port %PORT%

echo.
echo Server stopped.
pause
endlocal
