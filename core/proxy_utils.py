"""
Модуль для работы с прокси.
Включает функции проверки, валидации и управления списком прокси.
"""

import re
import requests
from typing import Tuple, Optional
from logging import getLogger
from colorama import Fore

logger = getLogger("proxy_utils")


def validate_proxy(proxy: str) -> Tuple[str, str, str, str]:
    """
    Проверяет прокси на соответствие формату и возвращает компоненты.
    
    :param proxy: Прокси строка
    :return: (login, password, ip, port)
    :raises ValueError: Если формат прокси некорректен
    """
    try:
        # Убираем протокол для валидации
        clean_proxy = proxy
        if proxy.startswith('socks5://') or proxy.startswith('socks4://'):
            clean_proxy = proxy.split('://', 1)[1]
        elif proxy.startswith('http://') or proxy.startswith('https://'):
            clean_proxy = proxy.replace('http://', '').replace('https://', '')
        
        # Формат: user:password@ip:port
        if "@" in clean_proxy:
            login_password, ip_port = clean_proxy.split("@")
            login, password = login_password.split(":")
            ip, port = ip_port.split(":")
        # Формат: ip:port:user:password
        elif clean_proxy.count(":") == 3:
            parts = clean_proxy.split(":")
            ip, port, login, password = parts[0], parts[1], parts[2], parts[3]
        # Формат: ip:port (без авторизации)
        elif clean_proxy.count(":") == 1:
            login, password = "", ""
            ip, port = clean_proxy.split(":")
        else:
            raise ValueError("Неверный формат прокси")
        
        # Валидация IP
        ip_parts = ip.split(".")
        if len(ip_parts) != 4:
            raise ValueError("Неверный формат IP адреса")
        if not all(0 <= int(part) <= 255 for part in ip_parts):
            raise ValueError("Неверный формат IP адреса")
        
        # Валидация порта
        if not 0 <= int(port) <= 65535:
            raise ValueError("Порт должен быть в диапазоне 0-65535")
            
    except Exception as e:
        raise ValueError(f"Некорректный формат прокси: {str(e)}")
    
    return login, password, ip, port


def normalize_proxy(proxy: str) -> str:
    """
    Нормализует прокси в единый формат.
    Для SOCKS сохраняет протокол, для HTTP/HTTPS убирает.
    
    :param proxy: Исходная прокси строка
    :return: Нормализованная прокси строка
    """
    # Сохраняем протокол SOCKS
    if proxy.startswith('socks5://') or proxy.startswith('socks4://'):
        return proxy
    
    # Убираем HTTP/HTTPS протокол
    clean_proxy = proxy.replace('http://', '').replace('https://', '')
    
    # Парсим компоненты
    login, password, ip, port = validate_proxy(clean_proxy)
    
    # Формат: ip:port:user:password -> user:password@ip:port
    if login and password:
        return f"{login}:{password}@{ip}:{port}"
    else:
        return f"{ip}:{port}"


def check_proxy(proxy: str, timeout: int = 10, test_url: str = "https://playerok.com", max_retries: int = 3) -> bool:
    """
    Проверяет работоспособность прокси.
    Делает до max_retries попыток. Если хотя бы одна успешна - сразу возвращает True.
    
    :param proxy: Нормализованная прокси строка
    :param timeout: Таймаут запроса в секундах
    :param test_url: URL для тестирования прокси
    :param max_retries: Максимальное количество попыток
    :return: True если прокси работает, иначе False
    """
    # Подготавливаем прокси строку
    if proxy.startswith(('socks5://', 'socks4://')):
        proxy_string = proxy
    else:
        proxy_string = f"http://{proxy}"
    
    logger.info(f"Проверка прокси (макс. {max_retries} попыток): {proxy_string}")
    
    proxies = {
        "http": proxy_string,
        "https": proxy_string,
    }
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"  Попытка {attempt}/{max_retries}...")
            response = requests.get(test_url, proxies=proxies, timeout=timeout)
            
            if response.status_code in [200, 403]:
                logger.info(f"  ✓ Успешно (код {response.status_code})")
                logger.info("✓ Прокси работает!")
                return True
            else:
                logger.warning(f"  ⚠ Прокси вернул код {response.status_code}")
                
        except ImportError:
            logger.error("⚠ Для работы SOCKS прокси нужен пакет PySocks")
            return False
        except requests.exceptions.Timeout:
            logger.warning(f"  ✗ Прокси не ответил за {timeout} секунд (timeout)")
        except requests.exceptions.ProxyError as e:
            logger.warning(f"  ✗ Ошибка прокси: {str(e)}")
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"  ✗ Ошибка соединения: {str(e)}")
        except Exception as e:
            logger.error(f"  ✗ Неизвестная ошибка: {str(e)}")
    
    # Если ни одна попытка не удалась
    logger.warning(f"⚠ Прокси не работает (все {max_retries} попыток неудачны)")
    return False


def format_proxy_display(proxy: str, max_length: int = 40) -> str:
    """
    Форматирует прокси для отображения в UI (скрывает пароль).
    
    :param proxy: Прокси строка
    :param max_length: Максимальная длина строки
    :return: Форматированная строка для отображения
    """
    try:
        login, password, ip, port = validate_proxy(proxy)
        
        if login and password:
            # Скрываем пароль
            hidden_pass = "*" * min(len(password), 4)
            display = f"{login}:{hidden_pass}@{ip}:{port}"
        else:
            display = f"{ip}:{port}"
        
        # Обрезаем если слишком длинный
        if len(display) > max_length:
            display = display[:max_length-3] + "..."
            
        return display
    except:
        return proxy[:max_length]


def get_proxy_string_for_request(proxy: str) -> str:
    """
    Преобразует прокси в формат для использования в requests.
    
    :param proxy: Нормализованная прокси строка
    :return: Прокси строка с протоколом
    """
    if proxy.startswith(('socks5://', 'socks4://', 'http://', 'https://')):
        return proxy
    else:
        return f"http://{proxy}"
