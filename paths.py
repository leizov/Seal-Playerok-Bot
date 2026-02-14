"""
Центральный модуль для всех путей в проекте.
Все пути вычисляются относительно расположения этого файла,
что гарантирует правильную работу независимо от текущей рабочей директории.
"""
import os

# Корневая директория проекта (где лежит этот файл)
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# ═══════════════════════════════════════════════════════════════════════════════
# ДИРЕКТОРИИ
# ═══════════════════════════════════════════════════════════════════════════════

# Директория настроек бота
BOT_SETTINGS_DIR = os.path.join(ROOT_DIR, "bot_settings")

# Директория данных бота
BOT_DATA_DIR = os.path.join(ROOT_DIR, "bot_data")

# Директория логов
LOGS_DIR = os.path.join(ROOT_DIR, "logs")

# Директория плагинов
PLUGINS_DIR = os.path.join(ROOT_DIR, "plugins")

# Директория хранилища (кэш и т.д.)
STORAGE_DIR = os.path.join(ROOT_DIR, "storage")
CACHE_DIR = os.path.join(STORAGE_DIR, "cache")

# ═══════════════════════════════════════════════════════════════════════════════
# ФАЙЛЫ НАСТРОЕК (bot_settings/)
# ═══════════════════════════════════════════════════════════════════════════════

CONFIG_FILE = os.path.join(BOT_SETTINGS_DIR, "config.json")
MESSAGES_FILE = os.path.join(BOT_SETTINGS_DIR, "messages.json")
CUSTOM_COMMANDS_FILE = os.path.join(BOT_SETTINGS_DIR, "custom_commands.json")
AUTO_DELIVERIES_FILE = os.path.join(BOT_SETTINGS_DIR, "auto_deliveries.json")
AUTO_RESTORE_ITEMS_FILE = os.path.join(BOT_SETTINGS_DIR, "auto_restore_items.json")
AUTO_RAISE_ITEMS_FILE = os.path.join(BOT_SETTINGS_DIR, "auto_raise_items.json")
QUICK_REPLIES_FILE = os.path.join(BOT_SETTINGS_DIR, "quick_replies.json")
PROXY_LIST_FILE = os.path.join(BOT_SETTINGS_DIR, "proxy_list.json")

# ═══════════════════════════════════════════════════════════════════════════════
# ФАЙЛЫ ДАННЫХ (bot_data/)
# ═══════════════════════════════════════════════════════════════════════════════

SALT_FILE = os.path.join(BOT_DATA_DIR, ".salt")
STATS_FILE = os.path.join(BOT_DATA_DIR, "stats.json")
DEALS_MONITOR_FILE = os.path.join(BOT_DATA_DIR, "deals_to_monitor.json")
INITIALIZED_USERS_FILE = os.path.join(BOT_DATA_DIR, "initialized_users.json")
AUTO_RAISE_ITEMS_TIMES_FILE = os.path.join(BOT_DATA_DIR, "auto_raise_items_times.json")

# ═══════════════════════════════════════════════════════════════════════════════
# ФАЙЛЫ ЛОГОВ (logs/)
# ═══════════════════════════════════════════════════════════════════════════════

LATEST_LOG_FILE = os.path.join(LOGS_DIR, "latest.log")

# ═══════════════════════════════════════════════════════════════════════════════
# ФАЙЛЫ КЭША (storage/cache/)
# ═══════════════════════════════════════════════════════════════════════════════

ANNOUNCEMENT_TAG_FILE = os.path.join(CACHE_DIR, "announcement_tag.txt")


# ═══════════════════════════════════════════════════════════════════════════════
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ═══════════════════════════════════════════════════════════════════════════════

def ensure_dirs():
    """Создаёт все необходимые директории, если они не существуют."""
    dirs = [
        BOT_SETTINGS_DIR,
        BOT_DATA_DIR,
        LOGS_DIR,
        PLUGINS_DIR,
        STORAGE_DIR,
        CACHE_DIR,
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)


def get_path(*parts) -> str:
    """
    Возвращает абсолютный путь относительно корня проекта.
    
    :param parts: Части пути
    :return: Абсолютный путь
    """
    return os.path.join(ROOT_DIR, *parts)
