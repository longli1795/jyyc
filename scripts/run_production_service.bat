@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

if not exist logs mkdir logs

call scripts\production_env.bat

set "PYTHON_EXE=python"
where python >nul 2>&1
if errorlevel 1 (
    if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
        set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    ) else (
        echo [%date% %time%] ERROR: python not found>>logs\service.log
        exit /b 1
    )
)

echo [%date% %time%] Service watchdog started>>logs\service.log

:wait_redis
"%PYTHON_EXE%" -c "import os,redis; redis.from_url(os.environ.get('REDIS_URL','redis://localhost:6379/0')).ping()" >nul 2>&1
if errorlevel 1 (
    echo [%date% %time%] Waiting for Redis...>>logs\service.log
    timeout /t 5 /nobreak >nul
    goto wait_redis
)
echo [%date% %time%] Redis is ready>>logs\service.log

:loop
echo [%date% %time%] Starting app>>logs\service.log
"%PYTHON_EXE%" app.py >>logs\service_stdout.log 2>>logs\service_stderr.log
set "EXIT_CODE=%ERRORLEVEL%"
echo [%date% %time%] App exited with code %EXIT_CODE%, restart in 10s>>logs\service.log
timeout /t 10 /nobreak >nul
goto loop
