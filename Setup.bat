@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo.
echo   🦭✨ ═══════════════════════════════════════════════════════════ ✨🦭
echo   ║                                                                   ║
echo   ║         🐚  SEAL PLAYEROK BOT - УСТАНОВЩИК  🐚                  ║
echo   ║                                                                   ║
echo   ║    Привет! Сейчас я помогу тебе всё настроить~ ^^               ║
echo   ║                                                                   ║
echo   🦭✨ ═══════════════════════════════════════════════════════════ ✨🦭
echo.

:: ═══════════════════════════════════════════════════════════════════════
:: ШАГ 0: Проверка Python 3.11
:: ═══════════════════════════════════════════════════════════════════════

echo   🔍 [0/4] Проверяю Python...
echo   ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

set "PYTHON_CMD="

:: Сначала пробуем py launcher с 3.11
py -3.11 --version >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "PYTHON_CMD=py -3.11"
    echo   ✅ Найден Python 3.11 через py launcher
    goto :python_found
)

:: Пробуем 3.10
py -3.10 --version >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "PYTHON_CMD=py -3.10"
    echo   ✅ Найден Python 3.10 через py launcher
    goto :python_found
)

:: Пробуем любой Python через py
py --version >nul 2>&1
if %ERRORLEVEL% equ 0 (
    :: Проверяем версию
    for /f "tokens=2" %%v in ('py --version 2^>^&1') do set "PY_VER=%%v"
    echo   ⚠️  Найден Python !PY_VER! 
    
    :: Проверяем что это не 3.13+ (проблемы совместимости)
    echo !PY_VER! | findstr /r "^3\.1[3-9]" >nul
    if %ERRORLEVEL% equ 0 (
        echo   ⚠️  Python 3.13+ может иметь проблемы совместимости!
        echo   💡 Рекомендуется установить Python 3.11
    )
    set "PYTHON_CMD=py"
    goto :python_found
)

:: Пробуем python напрямую
python --version >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "PYTHON_CMD=python"
    echo   ✅ Найден Python через PATH
    goto :python_found
)

:: Python не найден
echo.
echo   ❌ Python не найден!
echo.
echo   📥 Пожалуйста, установите Python 3.11:
echo      https://www.python.org/downloads/release/python-3119/
echo.
echo   ⚠️  При установке ОБЯЗАТЕЛЬНО отметьте:
echo      [✓] Add Python to PATH
echo.
pause
exit /b 1

:python_found
echo.

:: ═══════════════════════════════════════════════════════════════════════
:: ШАГ 1: Создание виртуального окружения
:: ═══════════════════════════════════════════════════════════════════════

echo   📦 [1/4] Создаю виртуальное окружение...
echo   ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:: Удаляем старое venv если есть
if exist "%~dp0venv" (
    echo   🗑️  Удаляю старое окружение...
    rmdir /s /q "%~dp0venv" 2>nul
)

:: Создаём новое venv
%PYTHON_CMD% -m venv "%~dp0venv"
if %ERRORLEVEL% neq 0 (
    echo   ❌ Не удалось создать виртуальное окружение!
    pause
    exit /b 1
)

echo   ✅ Виртуальное окружение создано!
echo.

:: ═══════════════════════════════════════════════════════════════════════
:: ШАГ 2: Установка зависимостей
:: ═══════════════════════════════════════════════════════════════════════

echo   🌊 [2/4] Устанавливаю зависимости бота...
echo   ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:: Активируем venv и устанавливаем
call "%~dp0venv\Scripts\activate.bat"
python -m pip install --upgrade pip >nul 2>&1
pip install -U -r "%~dp0requirements.txt"
echo.
echo   ✅ Зависимости бота установлены!
echo.

:: ═══════════════════════════════════════════════════════════════════════
:: ШАГ 3: Установка Nuitka
:: ═══════════════════════════════════════════════════════════════════════

echo   📦 [3/4] Устанавливаю Nuitka...
echo   ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
pip install nuitka colorama requests
echo.
echo   ✅ Nuitka установлена!
echo.

:: ═══════════════════════════════════════════════════════════════════════
:: ШАГ 4: Проверка C компилятора
:: ═══════════════════════════════════════════════════════════════════════

echo   🔨 [4/4] Проверяю C компилятор...
echo   ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

python -m nuitka --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo   ⚠️  Nuitka не работает, пропускаю
    goto :done
)

echo.
echo   💡 Nuitka сама скачает gcc при первой компиляции.
echo.

:done
:: Деактивируем venv
call "%~dp0venv\Scripts\deactivate.bat" 2>nul

echo.
echo   🦭✨ ═══════════════════════════════════════════════════════════ ✨🦭
echo   ║                                                                   ║
echo   ║                    🎉 УСТАНОВКА ЗАВЕРШЕНА! 🎉                   ║
echo   ║                                                                   ║
echo   ║   ✅ Создано изолированное окружение (venv)                     ║
echo   ║   ✅ Все библиотеки установлены в него                          ║
echo   ║                                                                   ║
echo   ║   Теперь можешь запустить бота:                                 ║
echo   ║   • Дважды кликни на Start.bat                                  ║
echo   ║                                                                   ║
echo   ║   Удачи! Пусть тюленчик принесёт тебе много продаж~ 🦭💕       ║
echo   ║                                                                   ║
echo   🦭✨ ═══════════════════════════════════════════════════════════ ✨🦭
echo.
pause
