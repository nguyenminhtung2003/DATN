@echo off
setlocal

set "JETSON_USER=nano"
set "JETSON_HOST=192.168.2.17"
set "JETSON_DIR=/home/nano/Version3"

echo ========================================
echo DrowsiGuard - Start Jetson AI main.py
echo ========================================
echo.
echo Jetson : %JETSON_USER%@%JETSON_HOST%
echo Path   : %JETSON_DIR%
echo.
echo If SSH asks for password, enter: nano
echo Keep this window open while testing.
echo Press Ctrl+C to stop main.py when it is running from this window.
echo.

ssh -t "%JETSON_USER%@%JETSON_HOST%" "bash -lc 'cd %JETSON_DIR% && if pgrep -af main.py >/dev/null; then echo DrowsiGuard main.py is already running.; echo; pgrep -af main.py; echo; echo Not starting a duplicate process.; else export DISPLAY=:0; export XAUTHORITY=/home/nano/.Xauthority; python3 main.py; fi'"

echo.
echo Jetson command finished.
pause
