@echo off
REM Shared production environment variables.
set FLASK_ENV=production
set FLASK_DEBUG=False
set FLASK_HOST=0.0.0.0
set FLASK_PORT=8080
set PYTHONIOENCODING=utf-8
set SECRET_KEY=bf_prod_8f3a9c2e1d4b7e6f5a0c8d9e1f2b3a4c5d6e7f8091a2b3c4d5e6f708192a3b
set REDIS_URL=redis://localhost:6379/0
set DATABASE_TYPE=sqlite
set SESSION_COOKIE_SECURE=false
set CLEAR_SESSIONS_ON_STARTUP=0
