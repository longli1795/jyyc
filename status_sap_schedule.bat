@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo Use status_autostart.bat for production + SAP task status.
echo.
call "%~dp0status_autostart.bat"
