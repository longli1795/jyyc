@echo off
REM Scheduled backup environment variables (sourced by install_backup_schedule.bat)

REM Backup root: use another disk or network path, e.g. D:\BusinessForecastBackups
if not defined BACKUP_ROOT set "BACKUP_ROOT=D:\BusinessForecastBackups"

REM Daily backup retention (days)
if not defined BACKUP_DAILY_RETENTION_DAYS set "BACKUP_DAILY_RETENTION_DAYS=14"

REM Weekly backup retention (weeks)
if not defined BACKUP_WEEKLY_RETENTION_WEEKS set "BACKUP_WEEKLY_RETENTION_WEEKS=8"

REM snapshot_pre_load_* retention count
if not defined SNAPSHOT_PRELOAD_RETENTION set "SNAPSHOT_PRELOAD_RETENTION=10"
