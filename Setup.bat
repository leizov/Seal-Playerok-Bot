@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo.
echo   🦭✨ ═══════════════════════════════════════════════════════════ ✨🦭
echo   ║                                                                   ║
echo   ║         🐚  SEAL PLAYEROK BOT - УСТАНОВЩИК  🐚                     ║
echo   ║                                                                   ║
echo   ║    Привет! Сейчас я помогу тебе всё настроить                     ║
echo   ║                                                                   ║
echo   🦭✨ ═══════════════════════════════════════════════════════════ ✨🦭
echo.

:: ═══════════════════════════════════════════════════════════════════════
:: ШАГ 0: Проверка Python 3.12 (ТОЛЬКО эта версия поддерживается)
:: ═══════════════════════════════════════════════════════════════════════

echo   🔍 [0/4] Проверяю Python 3.12...
echo   ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

set "PYTHON_CMD="

:: Сначала пробуем py launcher с 3.12
py -3.12 --version >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "PYTHON_CMD=py -3.12"
    echo   ✅ Найден Python 3.12 через py launcher
    goto :python_found
)

:: Пробуем python напрямую 3.12
python3.12 --version >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "PYTHON_CMD=python3.12"
    echo   ✅ Найден Python 3.12
    goto :python_found
)

:: Пробуем любой python и проверяем версию
python --version >nul 2>&1
if %ERRORLEVEL% equ 0 (
    :: Проверяем версию
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
    echo   ⚠️  Найден Python !PY_VER!
    
    :: Проверяем что это 3.12
    echo !PY_VER! | findstr /r "^3\.12" >nul
    if %ERRORLEVEL% equ 0 (
        echo   ✅ Это Python 3.12
        set "PYTHON_CMD=python"
        goto :python_found
    ) else (
        echo   ❌ Версия Python !PY_VER! не поддерживается!
        echo   💡 ТРЕБУЕТСЯ ТОЛЬКО Python 3.12
    )
)

:: Python не найден или неподходящая версия
echo.
echo   ❌ Python 3.12 не найден!
echo   💡 SealPlayerok Bot требует ТОЛЬКО Python 3.12
echo.
echo   📥 Попытка автоматической установки Python 3.12...
echo.

:: Скачиваем установщик Python 3.12
echo   🌐 Скачиваю установщик Python 3.12...
powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe' -OutFile 'python-3.12.7-amd64.exe'"
if %ERRORLEVEL% neq 0 (
    echo   ❌ Не удалось скачать установщик Python
    echo   💡 Пожалуйста, установите Python 3.12 вручную:
    echo      https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe
    echo.
    echo   ⚠️  При установке ОБЯЗАТЕЛЬНО отметьте:
    echo      [✓] Add Python to PATH
    pause
    exit /b 1
)

:: Устанавливаем Python в тихом режиме
echo   📦 Устанавливаю Python 3.12...
python-3.12.7-amd64.exe /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
if %ERRORLEVEL% neq 0 (
    echo   ❌ Ошибка установки Python
    echo   💡 Пожалуйста, установите Python 3.12 вручную:
    echo      https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe
    echo.
    echo   ⚠️  При установке ОБЯЗАТЕЛЬНО отметьте:
    echo      [✓] Add Python to PATH
    pause
    exit /b 1
)

:: Удаляем установщик
del python-3.12.7-amd64.exe

:: Обновляем PATH
echo   🔄 Обновляю PATH...
call refreshenv

:: Проверяем установку
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo   ❌ Python не установился или не добавлен в PATH
    echo   💡 Пожалуйста, установите Python 3.12 вручную:
    echo      https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe
    echo.
    echo   ⚠️  При установке ОБЯЗАТЕЛЬНО отметьте:
    echo      [✓] Add Python to PATH
    pause
    exit /b 1
)

echo   ✅ Python 3.12 успешно установлен!
set "PYTHON_CMD=python"
goto :python_found

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
:: ШАГ 3: Проверка C компилятора
:: ═══════════════════════════════════════════════════════════════════════


:done
:: Деактивируем venv
call "%~dp0venv\Scripts\deactivate.bat" 2>nul

echo.
echo   🦭✨ ═══════════════════════════════════════════════════════════ ✨🦭
echo   ║                                                                   ║
echo   ║                    🎉 УСТАНОВКА ЗАВЕРШЕНА! 🎉                      ║
echo   ║                                                                   ║
echo   ║   ✅ Создано изолированное окружение (venv)                       ║
echo   ║   ✅ Все библиотеки установлены в него                            ║
echo   ║                                                                   ║
echo   ║   Теперь можешь запустить бота:                                   ║
echo   ║   • Дважды кликни на Start.bat                                    ║
echo   ║                                                                   ║
echo   ║   Удачи! Пусть тюленчик принесёт тебе много продаж~ 🦭💕           ║
echo   ║                                                                   ║
echo   🦭✨ ═══════════════════════════════════════════════════════════ ✨🦭
echo.
echo   ┌────────────────────────────────────────────────────────────────┐
echo   │  📢 Канал:  @SealPlayerok       https://t.me/SealPlayerok      │
echo   │  💬 Чат:    @SealPlayerokChat   https://t.me/SealPlayerokChat  │
echo   │  🤖 Бот:    @SealPlayerokBot    https://t.me/SealPlayerokBot   │
echo   │  📦 GitHub: github.com/leizov/Seal-Playerok-Bot                │
echo   │  👨‍💻 Автор:  @leizov                                           │
echo   └────────────────────────────────────────────────────────────────┘
echo.
pause
