@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "TASK_NAME=BusinessForecastProduction"
set "STARTUP_LNK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\BusinessForecastProduction.lnk"

echo Removing scheduled task: %TASK_NAME%
schtasks /Delete /TN "%TASK_NAME%" /F 2>nul
if errorlevel 1 (
    echo Scheduled task not found or already removed.
) else (
    echo [OK] Scheduled task removed.
)

if exist "%STARTUP_LNK%" (
    del /f /q "%STARTUP_LNK%"
    echo [OK] Startup shortcut removed.
) else (
    echo Startup shortcut not found.
)

echo.
echo Note: If the service window is still running, close it manually
echo       or end the python.exe process in Task Manager.
pause
