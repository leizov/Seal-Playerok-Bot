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

from __init__ import ACCENT_COLOR, VERSION, SECONDARY_COLOR, HIGHLIGHT_COLOR, SUCCESS_COLOR
from settings import Settings as sett
from core.utils import (
    set_title, 
    setup_logger, 
    install_requirements, 
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


def check_and_configure_config():
    config = sett.get("config")

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
    
    def is_tg_bot_exists() -> bool:
        max_retries = 5
        base_delay = 3        
        for attempt in range(1, max_retries + 1):
            try:
                response = requests.get(
                    f"https://api.telegram.org/bot{config['telegram']['api']['token']}/getMe",
                    timeout=5
                )
                data = response.json()
                
                if data.get("ok", False) is True and data.get("result", {}).get("is_bot", False) is True:
                    # print(f"{Fore.GREEN}✓ Успешная проверка токена Telegram (попытка {attempt}/{max_retries})")
                    return True
                
                error_msg = data.get('description', 'Неизвестная ошибка')
                print(f"{Fore.YELLOW}⚠ Ошибка проверки токена (попытка {attempt}/{max_retries}): {error_msg}")
                
            except requests.exceptions.RequestException as e:
                print(f"{Fore.YELLOW}⚠ Сетевая ошибка при проверке токена (попытка {attempt}/{max_retries}): {str(e)}")
            except Exception as e:
                print(f"{Fore.YELLOW}⚠ Неизвестная ошибка при проверке токена (попытка {attempt}/{max_retries}): {str(e)}")
            
            # Если это не последняя попытка, ждем перед повторной проверкой
            if attempt < max_retries:
                print(f"{Fore.WHITE}-_- Повторная попытка через {base_delay} сек...")
                import time
                time.sleep(base_delay)
        
        print(f"{Fore.RED}✗ Не удалось проверить токен после {max_retries} попыток")
        return False
        
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
            token = input(f"  {Fore.WHITE}↳ {Fore.LIGHTWHITE_EX}").strip()
            if is_token_valid(token):
                config["playerok"]["api"]["token"] = token
                sett.set("config", config)
                print(f"\n{Fore.GREEN}Токен успешно сохранён в конфиг.")
            else:
                print(f"\n{Fore.LIGHTRED_EX}Похоже, что вы ввели некорректный токен. Убедитесь, что он соответствует формату и попробуйте ещё раз.")

        while not config["playerok"]["api"]["user_agent"]:
            print(f"\n{Fore.WHITE}Введите {Fore.LIGHTMAGENTA_EX}User Agent {Fore.WHITE}вашего браузера. Его можно скопировать на сайте {Fore.LIGHTWHITE_EX}https://whatmyuseragent.com. Или вы можете пропустить этот параметр, нажав Enter."
                f"\n  {Fore.WHITE}· Пример: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
            user_agent = input(f"  {Fore.WHITE}↳ {Fore.LIGHTWHITE_EX}").strip()
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
            proxy = input(f"\n  {Fore.WHITE}↳ {Fore.LIGHTWHITE_EX}").strip()
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
                    choice = input(f"\n  {Fore.WHITE}↳ Ваш выбор (1/2/3): {Fore.LIGHTWHITE_EX}").strip()
                    
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

    while not config["telegram"]["api"]["token"]:
        print(f"\n{Fore.WHITE}Введите {Fore.CYAN}токен вашего Telegram бота{Fore.WHITE}. Бота нужно создать у @BotFather."
              f"\n  {Fore.WHITE}· Пример: 7257913369:AAG2KjLL3-zvvfSQFSVhaTb4w7tR2iXsJXM")
        token = input(f"  {Fore.WHITE}↳ {Fore.LIGHTWHITE_EX}").strip()
        if is_tg_token_valid(token):
            config["telegram"]["api"]["token"] = token
            sett.set("config", config)
            print(f"\n{Fore.GREEN}Токен Telegram бота успешно сохранён в конфиг.")
        else:
            print(f"\n{Fore.LIGHTRED_EX}Похоже, что вы ввели некорректный токен. Убедитесь, что он соответствует формату и попробуйте ещё раз.")

    while not config["telegram"]["bot"]["password"]:
        print(f"\n{Fore.WHITE}Придумайте и введите {Fore.YELLOW}пароль для вашего Telegram бота{Fore.WHITE}. Бот будет запрашивать этот пароль при каждой новой попытке взаимодействия чужого пользователя с вашим Telegram ботом."
              f"\n  {Fore.WHITE}· Пароль должен быть сложным, длиной не менее 6 и не более 64 символов.")
        password = input(f"  {Fore.WHITE}↳ {Fore.LIGHTWHITE_EX}").strip()
        if is_password_valid(password):
            config["telegram"]["bot"]["password"] = password
            sett.set("config", config)
            print(f"\n{Fore.GREEN}Пароль успешно сохранён в конфиг.")
        else:
            print(f"\n{Fore.LIGHTRED_EX}Ваш пароль не подходит. Убедитесь, что он соответствует формату и не является лёгким и попробуйте ещё раз.")

    # Проверка прокси (если был введён)
    if config["playerok"]["api"]["proxy"]:
        proxy_works = is_proxy_working(config["playerok"]["api"]["proxy"])
        
        if not proxy_works:
            print(f"\n{Fore.WHITE}Хотите:")
            print(f"  1 - Использовать этот прокси")
            print(f"  2 - Ввести другой прокси")
            print(f"  3 - Продолжить без прокси")
            choice = input(f"\n  {Fore.WHITE}↳ Ваш выбор (1/2/3): {Fore.LIGHTWHITE_EX}").strip()
            
            proxy_check_passed = False
            
            if choice == "1":
                print(f"\n{Fore.GREEN}Прокси будет использован в работе бота.")
                logger.info(f"Прокси {config['playerok']['api']['proxy']} принят пользователем")
            elif choice == "2":
                # Очищаем прокси и возвращаемся к вводу
                config["playerok"]["api"]["proxy"] = ""
                sett.set("config", config)
                # Переходим к вводу нового прокси
                while True:
                    print(f"\n{Fore.WHITE}Введите {Fore.LIGHTBLUE_EX}Прокси {Fore.WHITE}в одном из форматов:")
                    print(f"  {Fore.LIGHTGREEN_EX}HTTP/HTTPS:{Fore.WHITE}")
                    print(f"    · ip:port:user:password")
                    print(f"    · user:password@ip:port")
                    print(f"    · ip:port (без авторизации)")
                    print(f"  {Fore.LIGHTMAGENTA_EX}SOCKS5:{Fore.WHITE}")
                    print(f"    · socks5://user:password@ip:port")
                    print(f"    · socks5://ip:port")
                    print(f"\n  {Fore.WHITE}Пример HTTP: {Fore.LIGHTWHITE_EX}91.221.39.249:63880:KSbmS3e4:PXHYZPbB")
                    print(f"  {Fore.WHITE}Пример SOCKS5: {Fore.LIGHTWHITE_EX}socks5://KSbmS3e4:PXHYZPbB@91.221.39.249:63880")
                    print(f"\n  {Fore.YELLOW}Если не хотите использовать прокси - нажмите Enter.")
                    proxy = input(f"\n  {Fore.WHITE}↳ {Fore.LIGHTWHITE_EX}").strip()
                    if not proxy:
                        print(f"\n{Fore.WHITE}Вы пропустили ввод прокси.")
                        config["playerok"]["api"]["proxy"] = ""
                        sett.set("config", config)
                        break
                    if is_proxy_valid(proxy):
                        normalized = normalize_proxy(proxy)
                        config["playerok"]["api"]["proxy"] = normalized
                        sett.set("config", config)
                        print(f"\n{Fore.GREEN}Прокси успешно сохранён в конфиг.")
                        # Повторная проверка
                        proxy_works = is_proxy_working(normalized)
                        if proxy_works:
                            print(f"\n{Fore.GREEN}Прокси работает отлично!")
                        break
                    else:
                        print(f"\n{Fore.LIGHTRED_EX}Похоже, что вы ввели некорректный Прокси. Убедитесь, что он соответствует формату и попробуйте ещё раз.")
            elif choice == "3":
                config["playerok"]["api"]["proxy"] = ""
                sett.set("config", config)
                print(f"\n{Fore.WHITE}Продолжаем без прокси.")
            else:
                print(f"\n{Fore.LIGHTRED_EX}Неверный выбор. Используем текущий прокси.")
        else:
            logger.info(f"{Fore.GREEN}Прокси успешно работает!")

    if not is_pl_account_working():
        print(f"\n{Fore.LIGHTRED_EX}Не удалось подключиться к вашему Playerok аккаунту.")
        
        # Если используется прокси, возможно проблема в нём
        if config["playerok"]["api"]["proxy"]:
            print(f"\n{Fore.YELLOW}У вас настроен прокси. Возможно, проблема в прокси, а не в токене.")
            print(f"{Fore.WHITE}Что сделать?")
            print(f"  1 - Отключить прокси и попробовать без него")
            print(f"  2 - Ввести новый прокси")
            print(f"  3 - Ввести новый токен и User-Agent")
            print(f"  4 - Попытаться запустить бота с текущими настройками (может не работать)")
            choice = input(f"\n  {Fore.WHITE}↳ Ваш выбор (1/2/3/4): {Fore.LIGHTWHITE_EX}").strip()
            
            if choice == "1":
                config["playerok"]["api"]["proxy"] = ""
                sett.set("config", config)
                print(f"\n{Fore.GREEN}Прокси отключен. Пробуем подключиться...")
                return check_and_configure_config()
            elif choice == "2":
                config["playerok"]["api"]["proxy"] = ""
                sett.set("config", config)
                return check_and_configure_config()
            elif choice == "3":
                config["playerok"]["api"]["token"] = ""
                config["playerok"]["api"]["user_agent"] = ""
                config["playerok"]["api"]["proxy"] = ""
                sett.set("config", config)
                return check_and_configure_config()
            elif choice == "4":
                print(f"\n{Fore.YELLOW}Пытаемся запустить бота с текущими настройками...")
                logger.warning(f"{Fore.YELLOW}Проверка Playerok аккаунта не прошла, но продолжаем запуск...")
            else:
                print(f"\n{Fore.LIGHTRED_EX}Неверный выбор. Запрашиваем настройки заново.")
                config["playerok"]["api"]["token"] = ""
                config["playerok"]["api"]["user_agent"] = ""
                config["playerok"]["api"]["proxy"] = ""
                sett.set("config", config)
                return check_and_configure_config()
        else:
            print(f"{Fore.WHITE}Пожалуйста, убедитесь, что у вас указан верный токен и введите его снова.")
            config["playerok"]["api"]["token"] = ""
            config["playerok"]["api"]["user_agent"] = ""
            sett.set("config", config)
            return check_and_configure_config()
    else:
        logger.info(f"{Fore.WHITE}Playerok аккаунт успешно авторизован.")

    if is_pl_account_banned():
        print(f"{Fore.LIGHTRED_EX}\nВаш Playerok аккаунт забанен! Увы, я не могу запустить бота на заблокированном аккаунте...")
        config["playerok"]["api"]["token"] = ""
        config["playerok"]["api"]["user_agent"] = ""
        config["playerok"]["api"]["proxy"] = ""
        sett.set("config", config)
        return check_and_configure_config()

    if not is_tg_bot_exists():
        print(f"\n{Fore.LIGHTRED_EX}Не удалось подключиться к вашему Telegram боту. Пожалуйста, убедитесь, что у вас указан верный токен и введите его снова.")
        config["telegram"]["api"]["token"] = ""
        sett.set("config", config)
        return check_and_configure_config()
    else:
        logger.info(f"{Fore.WHITE}Telegram бот успешно работает.")


if __name__ == "__main__":
    try:
        install_requirements("requirements.txt") # установка недостающих зависимостей, если таковые есть
        patch_requests()
        setup_logger()
        
        set_title(f"Seal Playerok Bot v{VERSION}")
        # Красивый объёмный заголовок с морской окантовкой
        print(f"""
{Fore.CYAN}    ～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～
{Fore.LIGHTCYAN_EX}   ╔═════════════════════════════════════════════════════════════════════════════╗
{Fore.LIGHTCYAN_EX}   ║  {Fore.LIGHTMAGENTA_EX}🦭{Fore.CYAN}                                                                     {Fore.LIGHTMAGENTA_EX}🦭  {Fore.LIGHTCYAN_EX}║
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
{Fore.LIGHTCYAN_EX}   ║              {Fore.LIGHTMAGENTA_EX}🐚 {Fore.WHITE}Милый помощник для Playerok {Fore.LIGHTMAGENTA_EX}v{VERSION}  🐚{Fore.LIGHTCYAN_EX}                    ║
{Fore.LIGHTCYAN_EX}   ║  {Fore.LIGHTMAGENTA_EX}🦭{Fore.CYAN}                                                                     {Fore.LIGHTMAGENTA_EX}🦭  {Fore.LIGHTCYAN_EX}║
{Fore.LIGHTCYAN_EX}   ╚═════════════════════════════════════════════════════════════════════════════╝
{Fore.CYAN}    ～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～{Fore.RESET}
""")
        # check_for_updates()
        check_and_configure_config()
        
        # Загружаем плагины
        plugins = load_plugins()
        set_plugins(plugins)
        
        # Вызываем INIT перед инициализацией
        # print(f"{Fore.CYAN}Инициализация системы...{Fore.RESET}")
        asyncio.run(call_bot_event("INIT", []))
        
        # Подключаем плагины
        # print(f"{Fore.CYAN}Подключение плагинов...{Fore.RESET}")
        asyncio.run(connect_plugins(plugins))
        
        # Запускаем Telegram бота
        # print(f"\n{Fore.CYAN}Запуск Telegram бота...{Fore.RESET}")
        main_loop.run_until_complete(start_telegram_bot())
        
        # Запускаем PlayerOk бота
        # print(f"{Fore.CYAN}Инициализация аккаунта PlayerOk...{Fore.RESET}")
        main_loop.run_until_complete(start_playerok_bot())
        
        # Вызываем POST_INIT после полной инициализации
        # print(f"{Fore.CYAN}Завершение инициализации...{Fore.RESET}")
        asyncio.run(call_bot_event("POST_INIT", []))
        
        main_loop.run_forever()
    except KeyboardInterrupt:
        # Пользователь нажал Ctrl+C - нормальный выход
        logger.info(f"{Fore.LIGHTCYAN_EX}🦭 Бот остановлен пользователем. До свидания! 🌊")
        raise SystemExit(0)  # Нормальный выход (код 0)
    except Exception as e:
        traceback.print_exc()
        print(
            f"\n{Fore.LIGHTRED_EX}Ваш бот словил непредвиденную ошибку и был выключен."
            f"\n\n{Fore.WHITE}Пожалуйста, попробуйте найти свою проблему в нашей статье, в которой собраны все самые частые ошибки.",
            f"\nСтатья: {Fore.LIGHTWHITE_EX}https://telegra.ph/FunPay-Universal--chastye-oshibki-i-ih-resheniya-08-26 {Fore.WHITE}(CTRL + Клик ЛКМ)\n"
        )
        raise SystemExit(1)  # Выход с ошибкой (код 1)
    
    # Если run_forever() остановился через shutdown() - нормальный выход
    logger.info(f"{Fore.LIGHTCYAN_EX}🦭 Бот корректно завершил работу. 🌊")
    raise SystemExit(0)  # Нормальный выход (код 0)