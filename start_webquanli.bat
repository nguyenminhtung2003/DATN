@echo off
setlocal

set "ROOT_DIR=%~dp0"
set "ROOT_PROJECT_DIR=%ROOT_DIR%WebQuanLi"
set "DEPS_DIR=%ROOT_DIR%.pytest_deps"
set "HOST=0.0.0.0"
set "PORT=8000"
set "CHECK_ONLY=0"

if /I "%~1"=="--check" set "CHECK_ONLY=1"

set "PROJECT_DIR=%ROOT_PROJECT_DIR%"
set "PROJECT_SOURCE=root WebQuanLi"

echo ========================================
echo DrowsiGuard - Start WebQuanLi Dashboard
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

if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else if exist "%ROOT_DIR%.venv\Scripts\python.exe" (
    set "PYTHON=%ROOT_DIR%.venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)

if exist "%DEPS_DIR%" (
    set "PYTHONPATH=%DEPS_DIR%;%PROJECT_DIR%;%PYTHONPATH%"
)

if not defined SECRET_KEY set "SECRET_KEY=drowsiguard-local-dev-secret"
if not defined ADMIN_USERNAME set "ADMIN_USERNAME=minhtung2003"
if not defined ADMIN_PASSWORD set "ADMIN_PASSWORD=minhtung2003"

echo Project : %PROJECT_DIR%
echo Source  : %PROJECT_SOURCE%
echo URL     : http://127.0.0.1:%PORT%
echo Python  : %PYTHON%
if exist "%DEPS_DIR%" echo Deps    : %DEPS_DIR%
echo.

"%PYTHON%" -c "import uvicorn; import app.main" >nul 2>nul
if errorlevel 1 (
    echo ERROR: WebQuanLi cannot import required Python modules.
    echo Checked project:
    echo     %PROJECT_DIR%
    echo Checked dependency path:
    echo     %DEPS_DIR%
    echo.
    echo If dependencies are missing, run:
    echo     %PYTHON% -m pip install --target "%DEPS_DIR%" -r "%PROJECT_DIR%\requirements.txt"
    echo.
    pause
    exit /b 1
)

if "%CHECK_ONLY%"=="1" (
    echo Check OK: WebQuanLi imports successfully.
    exit /b 0
)

start "" "http://127.0.0.1:%PORT%"

echo Starting WebQuanLi...
echo Keep this window open while testing.
echo Press Ctrl+C to stop the server.
echo.

"%PYTHON%" -m uvicorn app.main:app --host %HOST% --port %PORT% --reload

echo.
echo WebQuanLi server stopped.
pause
