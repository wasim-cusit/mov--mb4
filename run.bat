@echo off
setlocal EnableExtensions
cd /d "%~dp0"

REM MOV to MP4 Converter - Launch
REM Developer: MUHAMMAD WASIM | +923257627554

chcp 65001 >nul 2>&1
title MOV to MP4 Converter ^| MUHAMMAD WASIM
mode con: cols=80 lines=40
color 0B

set "PS_UI=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%PS_UI%" set "PS_UI=powershell.exe"

"%PS_UI%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0console_ui.ps1" -Action banner-run

set "PY_CMD="
where python >nul 2>&1
if %errorlevel% equ 0 (
    set "PY_CMD=python"
) else (
    where py >nul 2>&1
    if %errorlevel% equ 0 set "PY_CMD=py"
)

if not defined PY_CMD (
    "%PS_UI%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0console_ui.ps1" -Action error -Message "Python not found. Run install.bat first."
    pause
    exit /b 1
)

"%PS_UI%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0console_ui.ps1" -Action checking

"%PY_CMD%" installer.py --quiet --no-banner
if %errorlevel% neq 0 (
    echo.
    "%PS_UI%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0console_ui.ps1" -Action progress -Percent 0 -Label "Running full setup" -Detail ""
    "%PY_CMD%" installer.py --no-banner
    if %errorlevel% neq 0 (
        "%PS_UI%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0console_ui.ps1" -Action error -Message "FFmpeg install failed. Run install.bat as Admin."
        pause
        exit /b 1
    )
)

"%PS_UI%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0console_ui.ps1" -Action success-run
"%PS_UI%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0console_ui.ps1" -Action launching

"%PY_CMD%" app.py
set "APP_ERR=%errorlevel%"
if %APP_ERR% neq 0 (
    "%PS_UI%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0console_ui.ps1" -Action error -Message "Application exited with an error."
    pause
    exit /b %APP_ERR%
)
exit /b 0
