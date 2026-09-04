@echo off
setlocal
cd /d "%~dp0\.."
python -m app.sap_gui.set_sap_credential
exit /b %ERRORLEVEL%
