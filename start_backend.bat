@echo off
:: WBL Backend Auto-Start Script
:: This script starts the FastAPI backend and keeps it running.
:: Register this in Windows Task Scheduler to run at system startup.

cd /d "%~dp0"

:: Set encoding
set PYTHONIOENCODING=utf-8

:: Ensure logs directory exists
if not exist "logs\" mkdir "logs"

echo [%date% %time%] Starting WBL Backend... >> "logs\backend_startup.log"

:: Start uvicorn from the wbl-backend root so fapi.main:app resolves correctly
"%~dp0venv\Scripts\python.exe" -m uvicorn fapi.main:app --host 0.0.0.0 --port 8000 >> "logs\backend_startup.log" 2>&1

echo [%date% %time%] WBL Backend stopped. >> "logs\backend_startup.log"
