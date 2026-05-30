@echo off
cd /d "%~dp0"

echo ========================================================================
echo Business Forecast System - Production Mode
echo ========================================================================
echo.

call scripts\production_env.bat

echo [1/3] Checking Redis...
python scripts\prod_preflight.py
if errorlevel 1 (
    pause
    exit /b 1
)
echo.

echo [3/3] Starting app in production mode...
echo Press Ctrl+C to stop the server
echo ========================================================================
echo.

python app.py
pause
