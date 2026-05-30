@echo off
echo Adding Windows Firewall inbound rule for TCP port 8080...
netsh advfirewall firewall add rule name="BusinessForecast8080" dir=in action=allow protocol=TCP localport=8080
if errorlevel 1 (
    echo [FAILED] Right-click this file and choose "Run as administrator"
    pause
    exit /b 1
)
echo [OK] Firewall rule added. LAN clients can access port 8080.
pause
