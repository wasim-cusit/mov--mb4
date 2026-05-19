@echo off
setlocal EnableExtensions
cd /d "%~dp0"

REM MOV to MP4 Converter - Full Setup
REM Developer: MUHAMMAD WASIM | +923257627554

chcp 65001 >nul 2>&1
title MOV to MP4 - Setup ^| MUHAMMAD WASIM
mode con: cols=80 lines=45
color 0B

set "PS_UI=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%PS_UI%" set "PS_UI=powershell.exe"

"%PS_UI%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0console_ui.ps1" -Action banner-install
"%PS_UI%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0console_ui.ps1" -Action steps-install

set "PY_CMD="
where python >nul 2>&1
if %errorlevel% equ 0 (
    set "PY_CMD=python"
) else (
    where py >nul 2>&1
    if %errorlevel% equ 0 set "PY_CMD=py"
)

if not defined PY_CMD (
    "%PS_UI%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0console_ui.ps1" -Action error -Message "Python not installed. Enable Add to PATH during install."
    echo.
    echo    https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

"%PY_CMD%" installer.py --no-banner
set "INSTALL_ERR=%errorlevel%"

if %INSTALL_ERR% neq 0 (
    "%PS_UI%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0console_ui.ps1" -Action error -Message "Setup failed. Read the log above."
    pause
    exit /b 1
)

"%PS_UI%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0console_ui.ps1" -Action footer
pause
exit /b 0
