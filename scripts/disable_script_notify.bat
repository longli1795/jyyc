@echo off
setlocal
cd /d "%~dp0\.."
python -m app.sap_gui.disable_script_notify
echo.
echo Restart required: close ALL SAP Logon / sapgui windows, then log on to PRD again.
pause
