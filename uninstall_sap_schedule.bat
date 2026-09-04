@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo SAP monthly export is removed together with uninstall_autostart.bat.
echo This script only removes the SAP task.
echo.

set "TASK_NAME=BusinessForecastSapMonthlyExport"
schtasks /Delete /TN "%TASK_NAME%" /F 2>nul
if errorlevel 1 (
    echo No SAP export scheduled task found.
) else (
    echo [OK] Removed %TASK_NAME%
)
pause
exit /b 0
