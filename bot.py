import datetime
import sys
import os
import subprocess

def _early_install_requirements():
    """Устанавливает зависимости ДО импорта внешних модулей."""
    requirements_path = "requirements.txt"
    if not os.path.exists(requirements_path):
        return
    
    try:
        import pkg_resources
    except ImportError:
        # setuptools не установлен - устанавливаем все
        print("[*] Установка зависимостей...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", requirements_path, "-q"],
            stdout=subprocess.DEVNULL if os.name != 'nt' else None
        )
        return
    
    # Проверяем каждый пакет
    missing = []
    with open(requirements_path, "r", encoding="utf-8") as f:
        for line in f:
            pkg = line.strip()
            if not pkg or pkg.startswith("#"):
                continue
            try:
                pkg_resources.require(pkg)
            except (pkg_resources.DistributionNotFound, pkg_resources.VersionConflict):
                missing.append(pkg)
    
    if missing:
        print(f"[*] Установка недостающих пакетов: {', '.join(missing)}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing, "-q"])
        # Перезагружаем pkg_resources после установки
        import importlib
        importlib.reload(pkg_resources)

# Выполняем установку СРАЗУ
_early_install_requirements()

# ===========================================================================
# Исправление кодировки консоли Windows для поддержки Unicode
# ===========================================================================

# Принудительная UTF-8 кодировка на Windows
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ===========================================================================
# СТРОГАЯ ПРОВЕРКА ВЕРСИИ PYTHON
# ===========================================================================
# 
# ВАЖНО: Скомпилированные плагины (.pyd/.so) работают ТОЛЬКО на той версии
# Python, на которой были скомпилированы!
#
# Пример: plugin.cpython-312-win_amd64.pyd → только Python 3.12 + Windows
#
# Мы компилируем на Python 3.12, поэтому пользователям НУЖЕН Python 3.12!
# ===========================================================================

# ТОЧНАЯ версия Python для совместимости с плагинами
REQUIRED_PYTHON_MAJOR = 3
REQUIRED_PYTHON_MINOR = 12

current_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
required_version = f"{REQUIRED_PYTHON_MAJOR}.{REQUIRED_PYTHON_MINOR}"

if sys.version_info.major != REQUIRED_PYTHON_MAJOR or sys.version_info.minor != REQUIRED_PYTHON_MINOR:
    print("\n" + "=" * 60)
    print("ОШИБКА: НЕСОВМЕСТИМАЯ ВЕРСИЯ PYTHON!")
    print("=" * 60)
    print(f"\n   Текущая версия:   Python {current_version}")
    print(f"   Требуемая версия: Python {required_version}.x")
    print(f"\n   Скомпилированные плагины (.pyd) работают ТОЛЬКО")
    print(f"   на той версии Python, на которой были собраны.")
    print(f"\n   Скачать Python {required_version}:")
    print(f"   https://www.python.org/downloads/release/python-3120/")
    print("\n" + "=" * 60)
    sys.exit(1)

print(f"[OK] Python {current_version} - версия совместима")

# ═══════════════════════════════════════════════════════════════════════
# СОЗДАНИЕ ВСЕХ НЕОБХОДИМЫХ ДИРЕКТОРИЙ
# ═══════════════════════════════════════════════════════════════════════
# Создаём директории ДО любых других операций, чтобы избежать PermissionError

import paths
paths.ensure_dirs()

# ═══════════════════════════════════════════════════════════════════════
# ПРОВЕРКА КОДА АКТИВАЦИИ
# ═══════════════════════════════════════════════════════════════════════
# Код: 8 символов, 2-й = R или B, последний = 7 или 4
# Получить код: @SealPlayerokBot команда /code (нужна подписка на канал)

import json
import string as str_module

def validate_activation_code(code: str) -> bool:
    """Проверяет код активации по паттерну"""
    if not code or len(code) != 8:
        return False
    code = code.upper()
    if code[1] not in ['R', 'B']:
        return False
    if code[7] not in ['7', '4']:
        return False
    for c in code:
        if c not in str_module.ascii_uppercase + str_module.digits:
            return False
    return True


def check_activation_code():
    """Проверяет код активации при первом запуске"""
    config_path = paths.CONFIG_FILE
    settings_dir = paths.BOT_SETTINGS_DIR
    
    # Проверяем существует ли конфиг
    if not os.path.exists(config_path):
        os.makedirs(settings_dir, exist_ok=True)
        # Конфиг создастся позже, но код нужен сейчас
        saved_code = ""
    else:
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            saved_code = config.get("activation_code", "")
        except:
            saved_code = ""
    
    # Если код уже есть и валиден — пропускаем
    if validate_activation_code(saved_code):
        return True
    
    # Запрашиваем код
    print("\n" + "=" * 60)
    print("🦭 АКТИВАЦИЯ SEAL PLAYEROK BOT")
    print("=" * 60)
    print("\nДля использования бота нужен код активации.")
    print("\n📋 Как получить код:")
    print("   1. Подпишись на канал @SealPlayerok")
    print("   2. Напиши боту @SealPlayerokBot")
    print("   3. Введи команду /code")
    print("   4. Скопируй полученный код")
    print("\n" + "=" * 60)
    
    while True:
        code = input("\n🔑 Введи код активации: ").strip().upper()
        
        if validate_activation_code(code):
            # Сохраняем код в конфиг
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                except:
                    config = {}
            else:
                config = {}
            
            config["activation_code"] = code
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            
            print("\n✅ Код принят! Бот активирован.")
            print("🐚 Добро пожаловать в SealPlayerok Bot!\n")
            return True
        else:
            print("❌ Неверный код! Попробуй ещё раз.")
            print("   Код должен быть 8 символов.")


# Проверяем код при запуске
check_activation_code()

# ═══════════════════════════════════════════════════════════════════════

import asyncio
import re
import string
import requests
import traceback
import base64
import time
from colorama import Fore, init as init_colorama
from logging import getLogger

from playerokapi.account import Account
from playerokapi.exceptions import CloudflareDetectedException

from __init__ import ACCENT_COLOR, VERSION, SECONDARY_COLOR, HIGHLIGHT_COLOR, SUCCESS_COLOR
from settings import Settings as sett
from core.utils import (
    set_title, 
    setup_logger, 
    patch_requests, 
    init_main_loop, 
    run_async_in_thread
)
from core.plugins import (
    load_plugins, 
    set_plugins, 
    connect_plugins
)
from core.handlers import call_bot_event
from core.proxy_utils import normalize_proxy, validate_proxy
from updater import check_for_updates


logger = getLogger("seal")

main_loop = asyncio.new_event_loop()
asyncio.set_event_loop(main_loop)

init_colorama()
init_main_loop(main_loop)



async def start_telegram_bot():
    from tgbot.telegrambot import TelegramBot
    run_async_in_thread(TelegramBot().run_bot)


async def start_playerok_bot():
    from plbot.playerokbot import PlayerokBot
    await PlayerokBot().run_bot()


def check_permissions():
    """Проверяет права доступа к файлам настроек и исправляет их при необходимости."""
    import stat
    try:
        import pwd
    except Exception as e:
        logger.info('Запуск на Windows, не проверяем права доступа')
        return True
    from pathlib import Path
    from colorama import Fore
    
    settings_dir = Path("bot_settings").resolve()
    current_user = pwd.getpwuid(os.getuid()).pw_name
    
    if not settings_dir.exists():
        settings_dir.mkdir(parents=True, exist_ok=True)
        print(f"{Fore.GREEN}[OK] Создана директория настроек: {settings_dir}{Fore.RESET}")
    
    if not os.access(settings_dir, os.W_OK):
        print(f"{Fore.RED}❌ Нет прав на запись в {settings_dir}{Fore.RESET}")
        print(f"{Fore.YELLOW}Выполните: sudo chown -R {current_user}:{current_user} {settings_dir}{Fore.RESET}")
        return False

    fixed_files = []
    problem_files = []
    
    for json_file in settings_dir.glob("*.json"):
        if not os.access(json_file, os.W_OK):
            file_stat = os.stat(json_file)
            current_uid = os.getuid()
            
            if file_stat.st_uid != current_uid:
                problem_files.append((json_file, f"Владелец: uid={file_stat.st_uid}, текущий пользователь: uid={current_uid}"))
            else:
                try:
                    os.chmod(json_file, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
                    fixed_files.append(json_file.name)
                except Exception as e:
                    problem_files.append((json_file, str(e)))
    
    if fixed_files:
        print(f"{Fore.GREEN}✅ Исправлены права для файлов: {', '.join(fixed_files)}{Fore.RESET}")
    
    if problem_files:
        print(f"\n{Fore.RED}❌ Не удалось исправить права для файлов:{Fore.RESET}")
        for file_path, error in problem_files:
            print(f"{Fore.RED}   - {file_path.name}: {error}{Fore.RESET}")
        print(f"\n{Fore.YELLOW}Файлы принадлежат другому пользователю (возможно root).{Fore.RESET}")
        print(f"{Fore.YELLOW}Выполните команду для исправления:{Fore.RESET}")
        for file_path, _ in problem_files:
            print(f"{Fore.CYAN}   sudo chown {current_user}:{current_user} {file_path}{Fore.RESET}")
        print()
        return False
    
    return True

def check_and_configure_config():
    import sys
    config = sett.get("config")
    
    # Проверяем, нужна ли интерактивная настройка
    needs_config = (
        not config["playerok"]["api"]["token"] or
        not config["telegram"]["api"]["token"] or
        not config["telegram"]["bot"]["password"]
    )
    
    # Если нет TTY (запуск через systemd) и конфиг не настроен - выходим с ошибкой
    if needs_config and not sys.stdin.isatty():
        print("")
        print("=" * 60)
        print("    ТРЕБУЕТСЯ РУЧНАЯ НАСТРОЙКА")
        print("=" * 60)
        print("")
        print("  Бот запущен в фоновом режиме, но конфигурация")
        print("  не завершена. Интерактивный ввод невозможен.")
        print("")
        print("  Отсутствуют:")
        if not config["playerok"]["api"]["token"]:
            print("    - Токен Playerok")
        if not config["telegram"]["api"]["token"]:
            print("    - Токен Telegram бота")
        if not config["telegram"]["bot"]["password"]:
            print("    - Пароль для Telegram бота")
        print("")
        print("=" * 60)
        sys.exit(1)

    def is_token_valid(token: str) -> bool:
        if not re.match(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$", token):
            return False
        try:
            header, payload, signature = token.split('.')
            for part in (header, payload, signature):
                padding = '=' * (-len(part) % 4)
                base64.urlsafe_b64decode(part + padding)
            return True
        except Exception:
            return False
    
    def is_pl_account_working() -> bool:
        try:
            Account(
                token=config["playerok"]["api"]["token"],
                user_agent=config["playerok"]["api"]["user_agent"],
                requests_timeout=config["playerok"]["api"]["requests_timeout"],
                proxy=config["playerok"]["api"]["proxy"] or None
            ).get()
            return True
        except:
            return False
    
    def is_pl_account_banned() -> bool:
        try:
            acc = Account(
                token=config["playerok"]["api"]["token"],
                user_agent=config["playerok"]["api"]["user_agent"],
                requests_timeout=config["playerok"]["api"]["requests_timeout"],
                proxy=config["playerok"]["api"]["proxy"] or None
            ).get()
            return acc.profile.is_blocked
        except:
            return False

    def is_user_agent_valid(ua: str) -> bool:
        if not ua or not (10 <= len(ua) <= 512):
            return False
        allowed_chars = string.ascii_letters + string.digits + string.punctuation + ' '
        return all(c in allowed_chars for c in ua)

    # Используем глобальную функцию normalize_proxy из core.proxy_utils
    # вместо локальной для единообразия
    
    def is_proxy_valid(proxy: str) -> bool:
        """Проверяет валидность прокси через глобальную функцию validate_proxy"""
        try:
            validate_proxy(proxy)
            return True
        except (ValueError, Exception):
            return False
    
    def is_proxy_working(proxy: str, timeout: int = 10, max_retries: int = 3) -> bool:
        """Проверка прокси через playerok.com. Принимает УЖЕ нормализованный прокси!
        Делает до max_retries попыток. Если хотя бы одна успешна - сразу возвращает True."""
        # Для SOCKS5/SOCKS4 сохраняем протокол, для остальных добавляем http://
        if proxy.startswith(('socks5://', 'socks4://')):
            proxy_string = proxy
        else:
            proxy_string = f"http://{proxy}"
            

        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"{Fore.CYAN}Проверка прокси (макс. {max_retries} попыток):")
        print(f"{Fore.WHITE}  Исходный формат: {Fore.LIGHTWHITE_EX}{proxy}")
        print(f"{Fore.WHITE}  Финальный формат: {Fore.LIGHTWHITE_EX}{proxy_string}")
        print(f"{Fore.WHITE}  URL для теста: {Fore.LIGHTWHITE_EX}https://playerok.com")
        print(f"{Fore.WHITE}  Timeout: {Fore.LIGHTWHITE_EX}{timeout} сек")
        print(f"{Fore.CYAN}{'='*60}")
        
        proxies = {
            "http": proxy_string,
            "https": proxy_string,
        }
        test_url = "https://playerok.com"
        
        for attempt in range(1, max_retries + 1):
            try:
                print(f"{Fore.CYAN}  Попытка {attempt}/{max_retries}...", end=" ")
                response = requests.get(test_url, proxies=proxies, timeout=timeout)
                if response.status_code in [200, 403]:
                    print(f"{Fore.GREEN}✓ Успешно (код {response.status_code})")
                    print(f"{Fore.CYAN}{'='*60}")
                    print(f"{Fore.GREEN}✓ Прокси работает!")
                    print(f"{Fore.CYAN}{'='*60}")
                    return True
                else:
                    print(f"{Fore.YELLOW}⚠ Код {response.status_code}")
            except ImportError:
                print(f"{Fore.YELLOW}✗ Ошибка ImportError")
                print(f"{Fore.YELLOW}⚠ Для работы SOCKS прокси нужен пакет PySocks")
                print(f"{Fore.WHITE}  Установите его: {Fore.LIGHTWHITE_EX}pip install PySocks")
                print(f"{Fore.CYAN}{'='*60}")
                return False
            except Exception as e:
                error_msg = str(e)
                print(f"{Fore.YELLOW}✗ Ошибка: {error_msg[:50]}...")
                
                # Различаем типы ошибок для более информативных сообщений
                if attempt == max_retries:  # Показываем детали только на последней попытке
                    if "SOCKS" in error_msg:
                        print(f"{Fore.WHITE}  Возможные причины:")
                        print(f"    · Прокси-сервер не отвечает")
                        print(f"    · Неверные учетные данные (логин/пароль)")
                        print(f"    · Прокси-сервер заблокирован или не работает")
                    elif "timeout" in error_msg.lower():
                        print(f"{Fore.WHITE}  Прокси не ответил вовремя (таймаут)")
                    elif "Connection" in error_msg:
                        print(f"{Fore.WHITE}  Не удалось подключиться к прокси-серверу")
        
        # Если ни одна попытка не удалась
        print(f"{Fore.CYAN}{'='*60}")
        print(f"{Fore.YELLOW}⚠ Прокси не работает (все {max_retries} попыток неудачны)")
        print(f"{Fore.CYAN}  Примечание: Бот попытается использовать прокси при запуске.")
        print(f"{Fore.CYAN}{'='*60}")
        
        return False
    
    def is_tg_token_valid(token: str) -> bool:
        pattern = r'^\d{7,12}:[A-Za-z0-9_-]{35}$'
        return bool(re.match(pattern, token))
    
    def is_tg_bot_exists() -> tuple[bool, str | None]:
        """Проверяет Telegram бота. Возвращает (успех, username)."""
        max_retries = 3
        base_delay = 1
        for attempt in range(1, max_retries + 1):
            try:
                response = requests.get(
                    f"https://api.telegram.org/bot{config['telegram']['api']['token']}/getMe",
                    timeout=10
                )
                data = response.json()
                
                if data.get("ok", False) is True and data.get("result", {}).get("is_bot", False) is True:
                    username = data.get("result", {}).get("username", "")
                    return True, username
                
                error_msg = data.get('description', 'Неизвестная ошибка')
                if attempt < max_retries:
                    print(f"{Fore.YELLOW}! Ошибка проверки токена: {error_msg}. Повтор...")
                
            except requests.exceptions.RequestException as e:
                if attempt < max_retries:
                    print(f"{Fore.YELLOW}! Сетевая ошибка: {str(e)[:50]}. Повтор...")
            except Exception as e:
                if attempt < max_retries:
                    print(f"{Fore.YELLOW}! Ошибка: {str(e)[:50]}. Повтор...")
            
            if attempt < max_retries:
                time.sleep(base_delay)
        
        return False, None
        
    def is_password_valid(password: str) -> bool:
        if len(password) < 6 or len(password) > 64:
            return False
        common_passwords = {
            "123456", "1234567", "12345678", "123456789", "password", "qwerty",
            "admin", "123123", "111111", "abc123", "letmein", "welcome",
            "monkey", "login", "root", "pass", "test", "000000", "user",
            "qwerty123", "iloveyou"
        }
        if password.lower() in common_passwords:
            return False
        return True
    
    while not config["playerok"]["api"]["token"]:
        while not config["playerok"]["api"]["token"]:
            print(f"\n{Fore.WHITE}Введите {Fore.LIGHTBLUE_EX}токен {Fore.WHITE}вашего Playerok аккаунта. Его можно узнать из Cookie-данных, воспользуйтесь расширением Cookie-Editor."
                f"\n  {Fore.WHITE}· Пример: eyJhbGciOiJIUzI1NiIsInR5cCI1IkpXVCJ9.eyJzdWIiOiIxZWUxMzg0Ni...")
            token = input(f"  {Fore.WHITE}> {Fore.LIGHTWHITE_EX}").strip()
            if is_token_valid(token):
                config["playerok"]["api"]["token"] = token
                sett.set("config", config)
                print(f"\n{Fore.GREEN}Токен успешно сохранён в конфиг.")
            else:
                print(f"\n{Fore.LIGHTRED_EX}Похоже, что вы ввели некорректный токен. Убедитесь, что он соответствует формату и попробуйте ещё раз.")

        while not config["playerok"]["api"]["user_agent"]:
            print(f"\n{Fore.WHITE}Введите {Fore.LIGHTMAGENTA_EX}User Agent {Fore.WHITE}вашего браузера. Его можно скопировать на сайте {Fore.LIGHTWHITE_EX}https://whatmyuseragent.com. Или вы можете пропустить этот параметр, нажав Enter."
                f"\n  {Fore.WHITE}· Пример: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
            user_agent = input(f"  {Fore.WHITE}> {Fore.LIGHTWHITE_EX}").strip()
            if not user_agent:
                print(f"\n{Fore.YELLOW}Вы пропустили ввод User Agent. Учтите, что в таком случае бот может работать нестабильно.")
                break
            if is_user_agent_valid(user_agent):
                config["playerok"]["api"]["user_agent"] = user_agent
                sett.set("config", config)
                print(f"\n{Fore.GREEN}User Agent успешно сохранён в конфиг.")
            else:
                print(f"\n{Fore.LIGHTRED_EX}Похоже, что вы ввели некорректный User Agent. Убедитесь, что в нём нет русских символов и попробуйте ещё раз.")
        
        while not config["playerok"]["api"]["proxy"]:
            print(f"\n{Fore.WHITE}Введите {Fore.LIGHTBLUE_EX}Прокси {Fore.WHITE}в одном из форматов:")
            print(f"  {Fore.LIGHTGREEN_EX}HTTP/HTTPS:{Fore.WHITE}")
            print(f"    · ip:port:user:password")
            print(f"    · user:password@ip:port")
            print(f"    · ip:port (без авторизации)")
            print(f"  {Fore.LIGHTMAGENTA_EX}SOCKS5:{Fore.WHITE}")
            print(f"    · socks5://user:password@ip:port")
            print(f"    · socks5://ip:port (без авторизации)")
            print(f"\n  {Fore.WHITE}Пример HTTP: {Fore.LIGHTWHITE_EX}91.221.39.249:63880:KSbmS3e4:PXHYZPbB")
            print(f"  {Fore.WHITE}Пример SOCKS5: {Fore.LIGHTWHITE_EX}socks5://KSbmS3e4:PXHYZPbB@91.221.39.249:63880")
            print(f"\n  {Fore.YELLOW}Если не хотите использовать прокси - нажмите Enter.")
            proxy = input(f"\n  {Fore.WHITE}> {Fore.LIGHTWHITE_EX}").strip()
            if not proxy:
                print(f"\n{Fore.WHITE}Вы пропустили ввод прокси.")
                break
            if is_proxy_valid(proxy):
                normalized = normalize_proxy(proxy)
                config["playerok"]["api"]["proxy"] = normalized
                sett.set("config", config)
                print(f"\n{Fore.GREEN}Прокси успешно сохранён в конфиг.")
                
                # Проверяем прокси сразу после ввода
                proxy_works = is_proxy_working(normalized)
                
                if not proxy_works:
                    print(f"\n{Fore.WHITE}Хотите:")
                    print(f"  1 - Использовать этот прокси (может быть медленный, но рабочий)")
                    print(f"  2 - Ввести другой прокси")
                    print(f"  3 - Продолжить без прокси")
                    choice = input(f"\n  {Fore.WHITE}> Ваш выбор (1/2/3): {Fore.LIGHTWHITE_EX}").strip()
                    
                    if choice == "1":
                        print(f"\n{Fore.GREEN}Прокси будет использован в работе бота.")
                        break  # Выходим из цикла ввода прокси
                    elif choice == "2":
                        # Очищаем прокси и продолжаем цикл для нового ввода
                        config["playerok"]["api"]["proxy"] = ""
                        sett.set("config", config)
                        continue
                    elif choice == "3":
                        config["playerok"]["api"]["proxy"] = ""
                        sett.set("config", config)
                        print(f"\n{Fore.WHITE}Продолжаем без прокси.")
                        break
                    else:
                        print(f"\n{Fore.LIGHTRED_EX}Неверный выбор. Используем текущий прокси.")
                        break
                else:
                    break  # Прокси работает, выходим из цикла
            else:
                print(f"\n{Fore.LIGHTRED_EX}Похоже, что вы ввели некорректный Прокси. Убедитесь, что он соответствует формату и попробуйте ещё раз.")

    # Проверка Telegram бота только при первичном вводе токена
    tg_token_is_new = not config["telegram"]["api"]["token"]
    
    while not config["telegram"]["api"]["token"]:
        print(f"\n{Fore.WHITE}Введите {Fore.CYAN}токен вашего Telegram бота{Fore.WHITE}. Бота нужно создать у @BotFather."
              f"\n  {Fore.WHITE}· Пример: 7257913369:AAG2KjLL3-zvvfSQFSVhaTb4w7tR2iXsJXM")
        token = input(f"  {Fore.WHITE}> {Fore.LIGHTWHITE_EX}").strip()
        if is_tg_token_valid(token):
            # Проверяем бота сразу при вводе токена
            config["telegram"]["api"]["token"] = token
            tg_ok, tg_username = is_tg_bot_exists()
            if tg_ok:
                sett.set("config", config)
                print(f"\n{Fore.GREEN}Telegram бот подключен: {Fore.LIGHTCYAN_EX}@{tg_username}")
            else:
                config["telegram"]["api"]["token"] = ""
                print(f"\n{Fore.LIGHTRED_EX}Не удалось подключиться к боту. Проверьте токен и попробуйте снова.")
        else:
            print(f"\n{Fore.LIGHTRED_EX}Похоже, что вы ввели некорректный токен. Убедитесь, что он соответствует формату и попробуйте ещё раз.")

    while not config["telegram"]["bot"]["password"]:
        print(f"\n{Fore.WHITE}Придумайте и введите {Fore.YELLOW}пароль для вашего Telegram бота{Fore.WHITE}. Бот будет запрашивать этот пароль при каждой новой попытке взаимодействия чужого пользователя с вашим Telegram ботом."
              f"\n  {Fore.WHITE}· Пароль должен быть сложным, длиной не менее 6 и не более 64 символов.")
        password = input(f"  {Fore.WHITE}> {Fore.LIGHTWHITE_EX}").strip()
        if is_password_valid(password):
            config["telegram"]["bot"]["password"] = password
            sett.set("config", config)
            print(f"\n{Fore.GREEN}Пароль успешно сохранён в конфиг.")
        else:
            print(f"\n{Fore.LIGHTRED_EX}Ваш пароль не подходит. Убедитесь, что он соответствует формату и не является лёгким и попробуйте ещё раз.")

    if not is_pl_account_working():
        print(f"\n{Fore.LIGHTRED_EX}Не удалось подключиться к вашему Playerok аккаунту.")
        print(f"{Fore.YELLOW}Бот продолжит работу. Измените настройки через Telegram бота если нужно.")
        logger.warning(f"{Fore.YELLOW}Проверка Playerok аккаунта не прошла, но продолжаем запуск...")
    else:
        logger.info(f"{Fore.WHITE}Playerok аккаунт успешно авторизован.")

    # if is_pl_account_banned():
    #     print(f"{Fore.LIGHTRED_EX}\nВаш Playerok аккаунт забанен! Увы, я не могу запустить бота на заблокированном аккаунте...")
    #     config["playerok"]["api"]["token"] = ""
    #     config["playerok"]["api"]["user_agent"] = ""
    #     config["playerok"]["api"]["proxy"] = ""
    #     sett.set("config", config)
    #     return check_and_configure_config()

    # Telegram бот уже проверен при вводе токена, дополнительная проверка не нужна


if __name__ == "__main__":
    try:
        # Зависимости уже установлены в начале файла (_early_install_requirements)
        patch_requests()
        setup_logger()
        
        set_title(f"Seal Playerok Bot v{VERSION}")
        # Красивый объёмный заголовок с морской окантовкой
        print(f"""
{Fore.CYAN}    ～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～
{Fore.LIGHTCYAN_EX}   ╔═════════════════════════════════════════════════════════════════════════════╗
{Fore.LIGHTCYAN_EX}   ║  {Fore.LIGHTMAGENTA_EX}🦭{Fore.CYAN}                                                                     {Fore.LIGHTMAGENTA_EX}🦭  {Fore.LIGHTCYAN_EX}  ║
{Fore.LIGHTCYAN_EX}   ║                                                                             ║
{Fore.LIGHTCYAN_EX}   ║  {Fore.LIGHTWHITE_EX}███████{Fore.WHITE}╗{Fore.LIGHTWHITE_EX}███████{Fore.WHITE}╗ {Fore.LIGHTWHITE_EX}█████{Fore.WHITE}╗ {Fore.LIGHTWHITE_EX}██{Fore.WHITE}╗         {Fore.LIGHTWHITE_EX}██████{Fore.WHITE}╗  {Fore.LIGHTWHITE_EX}██████{Fore.WHITE}╗ {Fore.LIGHTWHITE_EX}████████{Fore.WHITE}╗        {Fore.LIGHTCYAN_EX}     ║
{Fore.LIGHTCYAN_EX}   ║  {Fore.LIGHTWHITE_EX}██{Fore.WHITE}╔════╝{Fore.LIGHTWHITE_EX}██{Fore.WHITE}╔════╝{Fore.LIGHTWHITE_EX}██{Fore.WHITE}╔══{Fore.LIGHTWHITE_EX}██{Fore.WHITE}╗{Fore.LIGHTWHITE_EX}██{Fore.WHITE}║         {Fore.LIGHTWHITE_EX}██{Fore.WHITE}╔══{Fore.LIGHTWHITE_EX}██{Fore.WHITE}╗{Fore.LIGHTWHITE_EX}██{Fore.WHITE}╔═══{Fore.LIGHTWHITE_EX}██{Fore.WHITE}╗╚══{Fore.LIGHTWHITE_EX}██{Fore.WHITE}╔══╝        {Fore.LIGHTCYAN_EX}     ║
{Fore.LIGHTCYAN_EX}   ║  {Fore.LIGHTWHITE_EX}███████{Fore.WHITE}╗{Fore.LIGHTWHITE_EX}█████{Fore.WHITE}╗  {Fore.LIGHTWHITE_EX}███████{Fore.WHITE}║{Fore.LIGHTWHITE_EX}██{Fore.WHITE}║         {Fore.LIGHTWHITE_EX}██████{Fore.WHITE}╔╝{Fore.LIGHTWHITE_EX}██{Fore.WHITE}║   {Fore.LIGHTWHITE_EX}██{Fore.WHITE}║   {Fore.LIGHTWHITE_EX}██{Fore.WHITE}║           {Fore.LIGHTCYAN_EX}     ║
{Fore.LIGHTCYAN_EX}   ║  {Fore.WHITE}╚════{Fore.LIGHTWHITE_EX}██{Fore.WHITE}║{Fore.LIGHTWHITE_EX}██{Fore.WHITE}╔══╝  {Fore.LIGHTWHITE_EX}██{Fore.WHITE}╔══{Fore.LIGHTWHITE_EX}██{Fore.WHITE}║{Fore.LIGHTWHITE_EX}██{Fore.WHITE}║         {Fore.LIGHTWHITE_EX}██{Fore.WHITE}╔══{Fore.LIGHTWHITE_EX}██{Fore.WHITE}╗{Fore.LIGHTWHITE_EX}██{Fore.WHITE}║   {Fore.LIGHTWHITE_EX}██{Fore.WHITE}║   {Fore.LIGHTWHITE_EX}██{Fore.WHITE} ║           {Fore.LIGHTCYAN_EX}    ║
{Fore.LIGHTCYAN_EX}   ║  {Fore.LIGHTWHITE_EX}███████{Fore.WHITE}║{Fore.LIGHTWHITE_EX}███████{Fore.WHITE}╗{Fore.LIGHTWHITE_EX}██{Fore.WHITE}║  {Fore.LIGHTWHITE_EX}██{Fore.WHITE}║{Fore.LIGHTWHITE_EX}███████{Fore.WHITE}╗    {Fore.LIGHTWHITE_EX}██████{Fore.WHITE}╔╝╚{Fore.LIGHTWHITE_EX}██████{Fore.WHITE}╔╝   {Fore.LIGHTWHITE_EX}██{Fore.WHITE}║           {Fore.LIGHTCYAN_EX}     ║
{Fore.LIGHTCYAN_EX}   ║  {Fore.WHITE}╚══════╝╚══════╝╚═╝  ╚═╝╚══════╝    ╚═════╝  ╚═════╝    ╚═╝           {Fore.LIGHTCYAN_EX}     ║
{Fore.LIGHTCYAN_EX}   ║                                                                             ║
{Fore.LIGHTCYAN_EX}   ║  {Fore.LIGHTWHITE_EX}██████{Fore.WHITE}╗ {Fore.LIGHTWHITE_EX}██{Fore.WHITE}╗      {Fore.LIGHTWHITE_EX}█████{Fore.WHITE}╗ {Fore.LIGHTWHITE_EX}██{Fore.WHITE}╗   {Fore.LIGHTWHITE_EX}██{Fore.WHITE}╗{Fore.LIGHTWHITE_EX}███████{Fore.WHITE}╗{Fore.LIGHTWHITE_EX}██████{Fore.WHITE}╗  {Fore.LIGHTWHITE_EX}██████{Fore.WHITE}╗ {Fore.LIGHTWHITE_EX}██{Fore.WHITE}╗  {Fore.LIGHTWHITE_EX}██{Fore.WHITE}╗       {Fore.LIGHTCYAN_EX}  ║
{Fore.LIGHTCYAN_EX}   ║  {Fore.LIGHTWHITE_EX}██{Fore.WHITE}╔══{Fore.LIGHTWHITE_EX}██{Fore.WHITE}╗{Fore.LIGHTWHITE_EX}██{Fore.WHITE}║     {Fore.LIGHTWHITE_EX}██{Fore.WHITE}╔══{Fore.LIGHTWHITE_EX}██{Fore.WHITE}╗╚{Fore.LIGHTWHITE_EX}██{Fore.WHITE}╗ {Fore.LIGHTWHITE_EX}██{Fore.WHITE}╔╝{Fore.LIGHTWHITE_EX}██{Fore.WHITE}╔════╝{Fore.LIGHTWHITE_EX}██{Fore.WHITE}╔══{Fore.LIGHTWHITE_EX}██{Fore.WHITE}╗{Fore.LIGHTWHITE_EX}██{Fore.WHITE}╔═══{Fore.LIGHTWHITE_EX}██{Fore.WHITE}╗{Fore.LIGHTWHITE_EX}██{Fore.WHITE}║ {Fore.LIGHTWHITE_EX}██{Fore.WHITE}╔╝       {Fore.LIGHTCYAN_EX}  ║
{Fore.LIGHTCYAN_EX}   ║  {Fore.LIGHTWHITE_EX}██████{Fore.WHITE}╔╝{Fore.LIGHTWHITE_EX}██{Fore.WHITE}║     {Fore.LIGHTWHITE_EX}███████{Fore.WHITE}║ ╚{Fore.LIGHTWHITE_EX}████{Fore.WHITE}╔╝ {Fore.LIGHTWHITE_EX}█████{Fore.WHITE}╗  {Fore.LIGHTWHITE_EX}██████{Fore.WHITE}╔╝{Fore.LIGHTWHITE_EX}██{Fore.WHITE}║   {Fore.LIGHTWHITE_EX}██{Fore.WHITE}║{Fore.LIGHTWHITE_EX}█████{Fore.WHITE}╔╝        {Fore.LIGHTCYAN_EX}  ║
{Fore.LIGHTCYAN_EX}   ║  {Fore.LIGHTWHITE_EX}██{Fore.WHITE}╔═══╝ {Fore.LIGHTWHITE_EX}██{Fore.WHITE}║     {Fore.LIGHTWHITE_EX}██{Fore.WHITE}╔══{Fore.LIGHTWHITE_EX}██{Fore.WHITE}║  ╚{Fore.LIGHTWHITE_EX}██{Fore.WHITE}╔╝  {Fore.LIGHTWHITE_EX}██{Fore.WHITE}╔══╝  {Fore.LIGHTWHITE_EX}██{Fore.WHITE}╔══{Fore.LIGHTWHITE_EX}██{Fore.WHITE}╗{Fore.LIGHTWHITE_EX}██{Fore.WHITE}║   {Fore.LIGHTWHITE_EX}██{Fore.WHITE}║{Fore.LIGHTWHITE_EX}██{Fore.WHITE}╔═{Fore.LIGHTWHITE_EX}██{Fore.WHITE}╗        {Fore.LIGHTCYAN_EX}  ║
{Fore.LIGHTCYAN_EX}   ║  {Fore.LIGHTWHITE_EX}██{Fore.WHITE}║     {Fore.LIGHTWHITE_EX}███████{Fore.WHITE}╗{Fore.LIGHTWHITE_EX}██{Fore.WHITE}║  {Fore.LIGHTWHITE_EX}██{Fore.WHITE}║   {Fore.LIGHTWHITE_EX}██{Fore.WHITE}║   {Fore.LIGHTWHITE_EX}███████{Fore.WHITE}╗{Fore.LIGHTWHITE_EX}██{Fore.WHITE}║  {Fore.LIGHTWHITE_EX}██{Fore.WHITE}║╚{Fore.LIGHTWHITE_EX}██████{Fore.WHITE}╔╝{Fore.LIGHTWHITE_EX}██{Fore.WHITE}║  {Fore.LIGHTWHITE_EX}██{Fore.WHITE}╗       {Fore.LIGHTCYAN_EX}  ║
{Fore.LIGHTCYAN_EX}   ║  {Fore.WHITE}╚═╝     ╚══════╝╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝         {Fore.LIGHTCYAN_EX}║
{Fore.LIGHTCYAN_EX}   ║                                                                             ║
{Fore.LIGHTCYAN_EX}   ║              {Fore.LIGHTMAGENTA_EX}🐚 {Fore.WHITE}Милый помощник для Playerok {Fore.LIGHTMAGENTA_EX}v{VERSION}  🐚{Fore.LIGHTCYAN_EX}                     ║
{Fore.LIGHTCYAN_EX}   ║  {Fore.LIGHTMAGENTA_EX}🦭{Fore.CYAN}                                                                     {Fore.LIGHTMAGENTA_EX}🦭  {Fore.LIGHTCYAN_EX}  ║
{Fore.LIGHTCYAN_EX}   ╚═════════════════════════════════════════════════════════════════════════════╝
{Fore.CYAN}    ～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～{Fore.RESET}
""")
        # Информация о проекте
        print(f"""
{Fore.CYAN}   ┌──────────────────────────────────────────────────────────────────────────────
   │  {Fore.LIGHTWHITE_EX}📢 Канал:{Fore.WHITE}  https://t.me/SealPlayerok                                       {Fore.CYAN}
   │  {Fore.LIGHTWHITE_EX}💬 Чат:{Fore.WHITE}    https://t.me/SealPlayerokChat                                   {Fore.CYAN}
   │  {Fore.LIGHTWHITE_EX}🤖 Бот:{Fore.WHITE}    https://t.me/SealPlayerokBot                                    {Fore.CYAN}
   │  {Fore.LIGHTWHITE_EX}📦 GitHub:{Fore.WHITE} https://github.com/leizov/Seal-Playerok-Bot                     {Fore.CYAN}
   │  {Fore.LIGHTWHITE_EX}👨‍💻 Автор:{Fore.WHITE}  @leizov                                                         {Fore.CYAN}
   └──────────────────────────────────────────────────────────────────────────────{Fore.RESET}
""")
        check_for_updates()

        from datetime import datetime as datetime_time
        try:
            local_time = datetime.datetime.now()
            logger.info(f'Часовой пояс устройства: {local_time.astimezone().tzinfo}')
            # logger.info(f'Смещение от UTC: {local_time.utcoffset().total_seconds() // 3600} часов')
        except Exception as e:
            logger.error(f'Ошибка при получении часового пояса устройства: {e}')

        if not check_permissions():
            print(f"\n{Fore.RED}Не удалось запустить бот из-за проблем с правами доступа.{Fore.RESET}")
            print(f"{Fore.YELLOW}Исправьте права и запустите бот снова.{Fore.RESET}\n")
            sys.exit(1)
        
        check_and_configure_config()
        
        # Загружаем плагины
        plugins = load_plugins()
        set_plugins(plugins)
        
        # Вызываем INIT перед инициализацией
        # print(f"{Fore.CYAN}Инициализация системы...{Fore.RESET}")
        main_loop.run_until_complete(call_bot_event("INIT", []))
        
        # Подключаем плагины
        # print(f"{Fore.CYAN}Подключение плагинов...{Fore.RESET}")
        main_loop.run_until_complete(connect_plugins(plugins))
        
        # Запускаем Telegram бота
        # print(f"\n{Fore.CYAN}Запуск Telegram бота...{Fore.RESET}")
        main_loop.run_until_complete(start_telegram_bot())
        
        # Запускаем PlayerOk бота
        # print(f"{Fore.CYAN}Инициализация аккаунта PlayerOk...{Fore.RESET}")
        try:
            main_loop.run_until_complete(start_playerok_bot())
        except Exception as e:
            logger.error(f"{Fore.LIGHTRED_EX}Ошибка при запуске Playerok бота: {e}")
            logger.warning(f"{Fore.YELLOW}Бот продолжит работу без Playerok функционала")
        
        # Вызываем POST_INIT после полной инициализации
        # print(f"{Fore.CYAN}Завершение инициализации...{Fore.RESET}")
        # ВАЖНО: используем main_loop, а не asyncio.run(), чтобы tasks плагинов
        # (process_queue, check_status) работали в том же event loop
        main_loop.run_until_complete(call_bot_event("POST_INIT", []))
        
        main_loop.run_forever()
    except KeyboardInterrupt:
        # Пользователь нажал Ctrl+C - нормальный выход
        logger.info(f"{Fore.LIGHTCYAN_EX}🦭 Бот остановлен пользователем. До свидания! 🌊")
        raise SystemExit(0)  # Нормальный выход (код 0)
    
    except CloudflareDetectedException as e:
        # ═════════════════════════════════════════════════════════════════════
        # CLOUDFLARE ЗАБЛОКИРОВАЛ ЗАПРОСЫ
        # НЕ сбрасываем конфиг, а отправляем уведомления и останавливаем бот
        # ═════════════════════════════════════════════════════════════════════
        logger.error(f"{Fore.LIGHTRED_EX}❌ Cloudflare заблокировал запросы к API!")
        logger.error(f"{Fore.YELLOW}Требуется смена токена, прокси или user-agent.")
        
        # Отправляем уведомление в Telegram
        try:
            from tgbot.telegrambot import get_telegram_bot
            tg_bot = get_telegram_bot()
            config = sett.get("config")
            
            if tg_bot and config["telegram"]["api"]["token"]:
                notification_text = (
                    "🚨 <b>CLOUDFLARE ЗАБЛОКИРОВАЛ ЗАПРОСЫ!</b>\n\n"
                    "❌ Бот не может выполнять запросы к Playerok API.\n\n"
                    "🛠 <b>Инструкция по исправлению:</b>\n"
                    "1\ufe0f⃣ Перезайдите на playerok.com в браузере\n"
                    "2\ufe0f⃣ Скопируйте новый токен (Cookie: token=...)\n"
                    "3\ufe0f⃣ Смените токен через этот бот:\n"
                    "   • 🔧 <b>Настройки</b> → <b>🔑 Аккаунт</b> → <b>🎫 Токен</b>\n"
                    "4\ufe0f⃣ При необходимости смените прокси и user-agent\n"
                    "5\ufe0f⃣ Перезапустите бота\n\n"
                    "⚠️ <b>Бот остановлен.</b> Настройки сохранены.\n"
                    "Измените данные через этот бот и перезапустите."
                )
                
                signed_users = config["telegram"]["bot"].get("signed_users", [])
                for user_id in signed_users:
                    try:
                        asyncio.run(tg_bot.bot.send_message(
                            chat_id=user_id,
                            text=notification_text,
                            parse_mode="HTML"
                        ))
                        logger.info(f"📨 Уведомление Cloudflare отправлено пользователю {user_id}")
                    except Exception as notify_err:
                        logger.warning(f"Не удалось отправить уведомление {user_id}: {notify_err}")
        except Exception as tg_err:
            logger.warning(f"Не удалось отправить уведомления в Telegram: {tg_err}")
        
        # Выводим инструкцию в консоль
        print(f"\n{Fore.LIGHTRED_EX}{'='*60}")
        print(f"{Fore.LIGHTRED_EX}❌ CLOUDFLARE ЗАБЛОКИРОВАЛ ЗАПРОСЫ!")
        print(f"{Fore.LIGHTRED_EX}{'='*60}")
        print(f"\n{Fore.YELLOW}Требуется смена данных для доступа к API:")
        print(f"{Fore.WHITE}  1. Перезайдите на playerok.com в браузере")
        print(f"{Fore.WHITE}  2. Скопируйте новый токен (Cookie: token=...)")
        print(f"{Fore.WHITE}  3. Смените токен через Telegram бот:")
        print(f"{Fore.LIGHTWHITE_EX}     🔧 Настройки → 🔑 Аккаунт → 🎫 Токен")
        print(f"{Fore.WHITE}  4. При необходимости смените прокси и user-agent")
        print(f"{Fore.WHITE}  5. Перезапустите бота")
        print(f"\n{Fore.GREEN}✅ Настройки сохранены. Измените через TG и перезапустите.")
        print(f"{Fore.LIGHTRED_EX}{'='*60}\n")
        
        raise SystemExit(2)  # Выход с кодом 2 (требуется смена данных)
    
    except Exception as e:
        traceback.print_exc()
        print(
            f"\n{Fore.LIGHTRED_EX}Ваш бот словил непредвиденную ошибку и был выключен."
            f"\n\n{Fore.WHITE}Можете обратиться в наш чат за помощью.",
            f"Чат: {Fore.LIGHTWHITE_EX}https://t.me/SealPlayerokChat {Fore.WHITE}(CTRL + Клик ЛКМ)\n"
        )
        raise SystemExit(1)  # Выход с ошибкой (код 1)
    
    # Если run_forever() остановился через shutdown() - нормальный выход
    logger.info(f"{Fore.LIGHTCYAN_EX}🦭 Бот корректно завершил работу. 🌊")
    raise SystemExit(0)  # Нормальный выход (код 0)