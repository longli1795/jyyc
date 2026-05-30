@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

if not exist logs mkdir logs
call scripts\backup_env.bat

set "PYTHON_EXE=python"
where python >nul 2>&1
if errorlevel 1 (
    if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
        set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    ) else (
        echo [%date% %time%] ERROR: python not found>>logs\backup.log
        exit /b 1
    )
)

"%PYTHON_EXE%" scripts\backup_data.py --mode daily
exit /b %ERRORLEVEL%
