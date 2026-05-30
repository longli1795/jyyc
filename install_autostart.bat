@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "TASK_NAME=BusinessForecastProduction"
set "SERVICE_BAT=%~dp0scripts\run_production_service.bat"
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
goto ask_start

:install_ok
echo [OK] Scheduled task installed.
goto ask_start

:install_failed
echo [FAILED] Could not install autostart.
pause
exit /b 1

:ask_start
echo.
echo Optional: start the service now?
choice /C YN /M "Start service now"
if errorlevel 2 goto done
if errorlevel 1 (
    start "BusinessForecastService" /MIN cmd /c ""%SERVICE_BAT%""
    echo [OK] Service started in minimized window.
    echo      Check logs\service.log for status.
)

:done
echo.
echo To remove autostart, run uninstall_autostart.bat
echo To check status, run status_autostart.bat
echo ========================================================================
pause
