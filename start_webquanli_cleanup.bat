@echo off
setlocal

set "ROOT_DIR=%~dp0"
set "PROJECT_DIR=%ROOT_DIR%WebQuanLi"
set "LOCAL_DEPS_DIR=%ROOT_DIR%.pytest_deps"
set "SHARED_DEPS_DIR=D:\DATN-testing12\DATN-testing1\.pytest_deps"
set "HOST=0.0.0.0"
set "PORT=8010"
set "CHECK_ONLY=0"

if /I "%~1"=="--check" set "CHECK_ONLY=1"

echo ========================================
echo DrowsiGuard - Start WebQuanLi Cleanup
echo ========================================
echo.

if not exist "%PROJECT_DIR%\app\main.py" (
    echo ERROR: Cannot find WebQuanLi app at:
    echo %PROJECT_DIR%
    echo.
    pause
    exit /b 1
)

cd /d "%PROJECT_DIR%"

if exist "%ROOT_DIR%.venv\Scripts\python.exe" (
    set "PYTHON=%ROOT_DIR%.venv\Scripts\python.exe"
) else if exist "D:\DATN-testing12\DATN-testing1\.venv\Scripts\python.exe" (
    set "PYTHON=D:\DATN-testing12\DATN-testing1\.venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)

if exist "%LOCAL_DEPS_DIR%" (
    set "PYTHONPATH=%LOCAL_DEPS_DIR%;%PROJECT_DIR%;%PYTHONPATH%"
) else if exist "%SHARED_DEPS_DIR%" (
    set "PYTHONPATH=%SHARED_DEPS_DIR%;%PROJECT_DIR%;%PYTHONPATH%"
)

if not defined SECRET_KEY set "SECRET_KEY=drowsiguard-local-dev-secret"
if not defined ADMIN_USERNAME set "ADMIN_USERNAME=minhtung2003"
if not defined ADMIN_PASSWORD set "ADMIN_PASSWORD=minhtung2003"

echo Project : %PROJECT_DIR%
echo Source  : cleanup worktree WebQuanLi
echo URL     : http://127.0.0.1:%PORT%
echo Python  : %PYTHON%
if exist "%LOCAL_DEPS_DIR%" echo Deps    : %LOCAL_DEPS_DIR%
if not exist "%LOCAL_DEPS_DIR%" if exist "%SHARED_DEPS_DIR%" echo Deps    : %SHARED_DEPS_DIR%
echo.

"%PYTHON%" -c "import uvicorn; import app.main" >nul 2>nul
if errorlevel 1 (
    echo ERROR: WebQuanLi cleanup cannot import required Python modules.
    echo Checked project:
    echo     %PROJECT_DIR%
    echo.
    pause
    exit /b 1
)

if "%CHECK_ONLY%"=="1" (
    echo Check OK: WebQuanLi cleanup imports successfully.
    exit /b 0
)

start "" "http://127.0.0.1:%PORT%"

echo Starting WebQuanLi cleanup on port %PORT%...
echo Keep this window open while testing.
echo Press Ctrl+C to stop the server.
echo.

"%PYTHON%" -m uvicorn app.main:app --host %HOST% --port %PORT% --reload

echo.
echo WebQuanLi cleanup server stopped.
pause
