@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "TASK_NAME=BusinessForecastProduction"
set "SAP_TASK=BusinessForecastSapMonthlyExport"
set "STARTUP_LNK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\BusinessForecastProduction.lnk"

echo Removing scheduled task: %TASK_NAME%
schtasks /Delete /TN "%TASK_NAME%" /F 2>nul
if errorlevel 1 (
    echo Scheduled task not found or already removed.
) else (
    echo [OK] Scheduled task removed.
)

echo Removing SAP export task: %SAP_TASK%
schtasks /Delete /TN "%SAP_TASK%" /F 2>nul
if errorlevel 1 (
    echo SAP export task not found or already removed.
) else (
    echo [OK] SAP export task removed.
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
echo       Daily backup tasks are separate and were not changed.
pause
