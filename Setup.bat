@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul 2>&1
title Seal Playerok Bot - Установщик

set "ROOT=%~dp0"
set "VENV=%ROOT%venv"
set "REQ=%ROOT%requirements.txt"
set "PYTHON_CMD="

echo.
echo +======================================================================+
echo ^|                      SEAL PLAYEROK BOT                               ^|
echo ^|                     УСТАНОВКА НА WINDOWS                             ^|
echo +======================================================================+
echo.
echo [Информация] Этот установщик подготовит окружение и зависимости.
echo.

echo [Шаг 1/4] Поиск Python 3.12...

py -3.12 --version >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "PYTHON_CMD=py -3.12"
)

if not defined PYTHON_CMD (
    python3.12 --version >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        set "PYTHON_CMD=python3.12"
    )
)

if not defined PYTHON_CMD (
    python --version >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        for /f "tokens=2" %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
        echo !PY_VER! | findstr /r "^3\.12" >nul
        if !ERRORLEVEL! equ 0 (
            set "PYTHON_CMD=python"
        )
    )
)

if not defined PYTHON_CMD (
    echo [Ошибка] Python 3.12 не найден.
    echo Установите Python 3.12 и повторите запуск.
    echo Ссылка: https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe
    echo.
    pause
    exit /b 1
)

echo [OK] Найден интерпретатор: !PYTHON_CMD!
echo.

echo [Шаг 2/4] Создание виртуального окружения...
if exist "%VENV%" (
    echo [Информация] Найдено старое окружение, удаляю...
    rmdir /s /q "%VENV%" 2>nul
)

%PYTHON_CMD% -m venv "%VENV%"
if %ERRORLEVEL% neq 0 (
    echo [Ошибка] Не удалось создать виртуальное окружение.
    echo.
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('"%VENV%\Scripts\python.exe" --version 2^>^&1') do set "VENV_PY_VER=%%v"
echo !VENV_PY_VER! | findstr /r "^3\.12" >nul
if %ERRORLEVEL% neq 0 (
    echo [Ошибка] Окружение создано на Python !VENV_PY_VER!, а требуется 3.12.x
    rmdir /s /q "%VENV%" 2>nul
    echo.
    pause
    exit /b 1
)

echo [OK] Виртуальное окружение создано.
echo.

echo [Шаг 3/4] Установка зависимостей...
if not exist "%REQ%" (
    echo [Ошибка] Не найден файл зависимостей:
    echo "%REQ%"
    echo.
    pause
    exit /b 1
)

call "%VENV%\Scripts\activate.bat"
if %ERRORLEVEL% neq 0 (
    echo [Ошибка] Не удалось активировать виртуальное окружение.
    echo.
    pause
    exit /b 1
)

"%VENV%\Scripts\python.exe" -m pip install --upgrade pip
if %ERRORLEVEL% neq 0 (
    echo [Ошибка] Не удалось обновить pip.
    call "%VENV%\Scripts\deactivate.bat" >nul 2>&1
    echo.
    pause
    exit /b 1
)

"%VENV%\Scripts\python.exe" -m pip install -U -r "%REQ%"
if %ERRORLEVEL% neq 0 (
    echo [Ошибка] Не удалось установить зависимости из requirements.txt
    call "%VENV%\Scripts\deactivate.bat" >nul 2>&1
    echo.
    pause
    exit /b 1
)

call "%VENV%\Scripts\deactivate.bat" >nul 2>&1

echo [OK] Зависимости установлены.
echo.

echo [Шаг 4/4] Завершение...
echo.
echo +======================================================================+
echo ^|                            ГОТОВО                                    ^|
echo +======================================================================+
echo.
echo Бот подготовлен к запуску.
echo Запустите файл Start.bat
echo.
pause
exit /b 0
