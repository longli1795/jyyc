@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

if not exist logs mkdir logs
if not exist data\sap_exports mkdir data\sap_exports
set PYTHONIOENCODING=utf-8

set "PYTHON_EXE=python"
where python >nul 2>&1
if errorlevel 1 (
    if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
        set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    ) else (
        echo [%date% %time%] ERROR: python not found>>logs\sap_export.log
        exit /b 1
    )
)

"%PYTHON_EXE%" scripts\run_sap_monthly_export.py --via-http %*
exit /b %ERRORLEVEL%
