@echo off
title AGY Short-Drama Studio
cd /d "%~dp0"
echo Starting AGY Short-Drama Studio...
python app.py
if errorlevel 1 (
    echo.
    echo An error occurred. Press any key to exit.
    pause >nul
)
