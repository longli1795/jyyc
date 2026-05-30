@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "TASK_DAILY=BusinessForecastBackupDaily"
set "TASK_WEEKLY=BusinessForecastBackupWeekly"
set "TASK_CLEANUP=BusinessForecastBackupCleanup"

echo ========================================================================
echo Uninstall scheduled backup tasks
echo ========================================================================

set "REMOVED=0"
for %%T in ("%TASK_DAILY%" "%TASK_WEEKLY%" "%TASK_CLEANUP%") do (
    schtasks /Query /TN %%~T >nul 2>&1
    if not errorlevel 1 (
        schtasks /Delete /TN %%~T /F >nul
        echo [OK] Removed %%~T
        set "REMOVED=1"
    )
)

if "%REMOVED%"=="0" (
    echo No backup scheduled tasks found.
) else (
    echo.
    echo All backup scheduled tasks removed.
)

echo ========================================================================
pause
