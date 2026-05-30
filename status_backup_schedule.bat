@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "TASK_DAILY=BusinessForecastBackupDaily"
set "TASK_WEEKLY=BusinessForecastBackupWeekly"
set "TASK_CLEANUP=BusinessForecastBackupCleanup"

echo ========================================================================
echo Backup schedule status
echo ========================================================================
echo.

call scripts\backup_env.bat
echo BACKUP_ROOT                 = %BACKUP_ROOT%
echo BACKUP_DAILY_RETENTION_DAYS = %BACKUP_DAILY_RETENTION_DAYS%
echo BACKUP_WEEKLY_RETENTION_WEEKS = %BACKUP_WEEKLY_RETENTION_WEEKS%
echo SNAPSHOT_PRELOAD_RETENTION  = %SNAPSHOT_PRELOAD_RETENTION%
echo.

set "FOUND=0"
for %%T in ("%TASK_DAILY%" "%TASK_WEEKLY%" "%TASK_CLEANUP%") do (
    schtasks /Query /TN %%~T >nul 2>&1
    if not errorlevel 1 (
        set "FOUND=1"
        echo --- %%~T ---
        schtasks /Query /TN %%~T /FO LIST /V | findstr /I "TaskName Status Next Run Time Task To Run"
        echo.
    )
)

if "%FOUND%"=="0" (
    echo No backup scheduled tasks installed.
    echo Run install_backup_schedule.bat to create them.
)

if exist logs\backup.log (
    echo --- Recent backup log ---
    powershell -NoProfile -Command "Get-Content -Path 'logs\backup.log' -Tail 15 -ErrorAction SilentlyContinue"
) else (
    echo logs\backup.log not found yet.
)

echo.
echo Manual run:
echo   scripts\run_daily_backup.bat
echo   scripts\run_weekly_backup.bat
echo   scripts\run_cleanup_backups.bat
echo ========================================================================
pause
