@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "TASK_NAME=BusinessForecastProduction"
set "STARTUP_LNK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\BusinessForecastProduction.lnk"

echo ========================================================================
echo Autostart / Service Status
echo ========================================================================
echo.

schtasks /Query /TN "%TASK_NAME%" /FO LIST /V 2>nul
if errorlevel 1 (
    echo Scheduled task: NOT installed
) else (
    echo.
    echo Scheduled task: INSTALLED
)

if exist "%STARTUP_LNK%" (
    echo Startup shortcut: INSTALLED
) else (
    echo Startup shortcut: NOT installed
)

echo.
echo Process check (python app.py):
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*app.py*' } | Select-Object ProcessId, CommandLine | Format-List"

echo.
echo Recent service log:
if exist logs\service.log (
    powershell -NoProfile -Command "Get-Content -Path 'logs\service.log' -Tail 10"
) else (
    echo logs\service.log not found
)

echo ========================================================================
pause
