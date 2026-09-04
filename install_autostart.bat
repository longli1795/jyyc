@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "TASK_NAME=BusinessForecastProduction"
set "SAP_TASK=BusinessForecastSapMonthlyExport"
set "SERVICE_BAT=%~dp0scripts\run_production_service.bat"
set "SAP_BAT=%~dp0scripts\run_sap_monthly_export.bat"
set "WORKDIR=%~dp0"
set "STARTUP_LNK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\BusinessForecastProduction.lnk"

echo ========================================================================
echo Install autostart: Business Forecast Production Service
echo ========================================================================
echo.
echo Task name : %TASK_NAME%
echo Script    : %SERVICE_BAT%
echo Trigger   : At user logon
echo Restart   : Auto-restart 10s after crash
echo Logs      : %WORKDIR%logs\
echo.
echo Also installs: %SAP_TASK%
echo   Script  : %SAP_BAT%
echo   Trigger : 03:00 on day 4 of each month, same as homepage SAP export button
echo   Logon   : /IT interactive desktop (user must be logged on; lock screen is OK)
echo   Note    : Website must be running. Daily backup stays at 02:00.
echo.
echo If you see Access Denied, right-click this script and Run as administrator
echo so Windows Task Scheduler can be updated. Startup-folder fallback still
echo starts the website after login.
echo.

schtasks /Query /TN "%TASK_NAME%" >nul 2>&1
if not errorlevel 1 (
    echo Removing existing scheduled task...
    schtasks /Delete /TN "%TASK_NAME%" /F >nul
)

if exist "%STARTUP_LNK%" (
    del /f /q "%STARTUP_LNK%" >nul 2>&1
)

echo Creating scheduled task...
schtasks /Create /TN "%TASK_NAME%" /TR "%SERVICE_BAT%" /SC ONLOGON /RL LIMITED /F
if not errorlevel 1 goto install_ok

echo [WARN] Scheduled task failed, using Startup folder fallback...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install_startup_shortcut.ps1" -ShortcutPath "%STARTUP_LNK%" -TargetPath "%SERVICE_BAT%" -WorkingDirectory "%WORKDIR%"
if errorlevel 1 goto install_failed
echo [OK] Startup shortcut installed.
goto install_sap

:install_ok
echo [OK] Scheduled task installed.
goto install_sap

:install_sap
echo Creating SAP monthly export task...
schtasks /Create /TN "%SAP_TASK%" /TR "%SAP_BAT%" /SC MONTHLY /D 4 /ST 03:00 /IT /RL LIMITED /F
if not errorlevel 1 (
    echo [OK] SAP monthly export task installed: day 4 at 03:00, interactive /IT
    goto ask_start
)

echo [WARN] Could not write SAP task to Task Scheduler - Access Denied is common without admin.
echo        To apply /IT (interactive desktop), right-click install_autostart.bat
echo        and choose Run as administrator, or run install_sap_schedule.bat as admin.
schtasks /Query /TN "%SAP_TASK%" >nul 2>&1
if errorlevel 1 (
    echo        SAP monthly export is NOT installed.
) else (
    echo        Existing SAP monthly export task was left unchanged.
)
goto ask_start

:install_failed
echo [FAILED] Could not install autostart.
pause
exit /b 1

:ask_start
echo.
echo Start the service now?
choice /C YN /M "Start service now"
if errorlevel 2 goto done
if errorlevel 1 (
    echo Starting service...
    start "BusinessForecastService" /MIN "%SERVICE_BAT%"
    timeout /t 3 /nobreak >nul
    echo [OK] Service launched.
    echo      Check logs\service.log for status.
    echo      Visit http://127.0.0.1:8080 to verify.
)

:done
echo.
echo To remove autostart, run uninstall_autostart.bat
echo To check status, run status_autostart.bat
echo ========================================================================
pause
