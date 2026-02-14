"""
Модуль для миграции старого формата хранения прокси в новый.
"""

from settings import Settings as sett
from logging import getLogger

logger = getLogger("proxy_migration")


def migrate_old_proxy_to_new_system():
    """
    Мигрирует старый прокси из config.json в новую систему proxy_list.json.
    Эта функция должна вызываться один раз при первом запуске с новой системой.
    """
    config = sett.get("config")
    proxy_list = sett.get("proxy_list") or {}
    
    # Получаем старый прокси из конфига
    old_proxy = config.get("playerok", {}).get("api", {}).get("proxy", "")
    
    # Если старый прокси существует и список прокси пуст - мигрируем
    if old_proxy and not proxy_list:
        logger.info("Обнаружен старый прокси, выполняю миграцию...")
        
        # Добавляем старый прокси в новый список с ID 1
        proxy_list["1"] = old_proxy
        sett.set("proxy_list", proxy_list)
        
        logger.info(f"Миграция выполнена. Прокси добавлен в список с ID: 1")
        logger.info(f"Активный прокси остался: {old_proxy}")
        
        return True
    
    return False
