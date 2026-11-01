@echo off
title AGY Short-Drama Studio
cd /d "%~dp0"
echo AGY Short-Drama Studio

rem 1. Find Python 3
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PY (
    echo LOI: Khong tim thay Python. Cai tu https://www.python.org/downloads/ ^(tick "Add Python to PATH"^).
    goto :fail
)

rem 2. Private environment + packages
if not exist ".venv\Scripts\python.exe" (
    echo Lan chay dau: dang tao moi truong .venv ...
    %PY% -m venv .venv || goto :fail
)
set "VPY=.venv\Scripts\python.exe"

fc /b requirements.txt .venv\requirements.stamp >nul 2>nul
if errorlevel 1 (
    echo Dang cai thu vien ^(opencv, numpy, Pillow^). Lan dau mat vai phut...
    "%VPY%" -m pip install --upgrade pip >nul
    "%VPY%" -m pip install -r requirements.txt || goto :fail
    echo Dang cai faster-whisper de tao sub ^(khong bat buoc^)...
    "%VPY%" -m pip install faster-whisper || echo CANH BAO: Khong cai duoc faster-whisper. App van chay, co the khong tao duoc sub.
    copy /y requirements.txt .venv\requirements.stamp >nul
)

rem 3. ffmpeg is needed to cut and render video
where ffmpeg >nul 2>nul || echo CANH BAO: Chua co ffmpeg. App mo duoc nhung khong xuat duoc video. Cai bang: winget install Gyan.FFmpeg

"%VPY%" app.py %*
if errorlevel 1 goto :fail
exit /b 0

:fail
echo.
echo Co loi xay ra. Bam phim bat ky de dong.
pause >nul
exit /b 1
