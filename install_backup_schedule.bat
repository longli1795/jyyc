@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "TASK_DAILY=BusinessForecastBackupDaily"
set "TASK_WEEKLY=BusinessForecastBackupWeekly"
set "TASK_CLEANUP=BusinessForecastBackupCleanup"

set "DAILY_BAT=%~dp0scripts\run_daily_backup.bat"
set "WEEKLY_BAT=%~dp0scripts\run_weekly_backup.bat"
set "CLEANUP_BAT=%~dp0scripts\run_cleanup_backups.bat"

echo ========================================================================
echo Install scheduled backup tasks
echo ========================================================================
echo.
echo Daily task   : %TASK_DAILY%   (02:00 every day)
echo Weekly task  : %TASK_WEEKLY%  (03:00 every Sunday)
echo Cleanup task : %TASK_CLEANUP% (04:00 on day 1 of each month)
echo.
echo Before continuing, edit scripts\backup_env.bat and set BACKUP_ROOT
echo to another disk or network path, for example:
echo   set BACKUP_ROOT=D:\BusinessForecastBackups
echo.

call scripts\backup_env.bat
echo Current BACKUP_ROOT = %BACKUP_ROOT%
echo.

choice /C YN /M "Continue installing scheduled tasks"
if errorlevel 2 goto cancelled

for %%T in ("%TASK_DAILY%" "%TASK_WEEKLY%" "%TASK_CLEANUP%") do (
    schtasks /Query /TN %%~T >nul 2>&1
    if not errorlevel 1 (
        echo Removing existing task %%~T ...
        schtasks /Delete /TN %%~T /F >nul
    )
)

echo Creating daily backup task...
schtasks /Create /TN "%TASK_DAILY%" /TR "\"%DAILY_BAT%\"" /SC DAILY /ST 02:00 /RL LIMITED /F
if errorlevel 1 goto install_failed

echo Creating weekly backup task...
schtasks /Create /TN "%TASK_WEEKLY%" /TR "\"%WEEKLY_BAT%\"" /SC WEEKLY /D SUN /ST 03:00 /RL LIMITED /F
if errorlevel 1 goto install_failed

echo Creating monthly cleanup task...
schtasks /Create /TN "%TASK_CLEANUP%" /TR "\"%CLEANUP_BAT%\"" /SC MONTHLY /D 1 /ST 04:00 /RL LIMITED /F
if errorlevel 1 goto install_failed

echo.
echo [OK] Scheduled backup tasks installed.
echo.
echo Manual run:
echo   scripts\run_daily_backup.bat
echo   scripts\run_weekly_backup.bat
echo   scripts\run_cleanup_backups.bat
echo.
echo Logs: logs\backup.log
echo Status: status_backup_schedule.bat
echo Remove: uninstall_backup_schedule.bat
echo ========================================================================
pause
exit /b 0

:install_failed
echo.
echo [FAILED] Could not create one or more scheduled tasks.
echo Try running this script as Administrator.
echo ========================================================================
pause
exit /b 1

:cancelled
echo Installation cancelled.
pause
exit /b 0
