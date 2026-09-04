@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo SAP monthly export is installed together with autostart.
echo Use install_autostart.bat as the main installer.
echo.
echo This script only (re)creates the SAP task: day 4 at 03:00.
echo The task calls the same /api/sap/export as the homepage button.
echo /IT = run on the logged-on desktop. Website must already be running.
echo Right-click and Run as administrator, otherwise the old task is left unchanged.
echo.

set "TASK_NAME=BusinessForecastSapMonthlyExport"
set "RUN_BAT=%~dp0scripts\run_sap_monthly_export.bat"

schtasks /Query /TN "%TASK_NAME%" >nul 2>&1
if not errorlevel 1 schtasks /Delete /TN "%TASK_NAME%" /F >nul

schtasks /Create /TN "%TASK_NAME%" /TR "%RUN_BAT%" /SC MONTHLY /D 4 /ST 03:00 /IT /RL LIMITED /F
if errorlevel 1 (
    echo [FAILED] Could not create %TASK_NAME%. Try running as Administrator.
    pause
    exit /b 1
)

echo [OK] %TASK_NAME% installed (monthly day 4, 03:00, interactive /IT).
echo Status: status_autostart.bat
pause
exit /b 0
