@echo off
setlocal
cd /d "%~dp0\.."
python -m app.sap_gui.probe_gui_scripting
exit /b %ERRORLEVEL%
