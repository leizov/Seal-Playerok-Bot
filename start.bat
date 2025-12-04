@echo off
chcp 65001 >nul
title Seal Playerok Bot

cd /d "%~dp0"

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

set "VENV_PYTHON=venv\Scripts\python.exe"

if "%VENV_PYTHON%"=="" (
    echo.
    echo   ERROR: Virtual environment not found!
    echo   Please run Setup.bat first
    echo.
    pause
    exit /b 1
)

echo.
echo   Starting Seal Playerok Bot...
echo.

"%VENV_PYTHON%" bot.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo   ============================================
    echo   ERROR: Bot crashed with code %ERRORLEVEL%
    echo   ============================================
    echo.
    echo   Window closes in 30 seconds...
    timeout /t 30
    exit /b 1
)

echo.
echo   Bot stopped
pause
