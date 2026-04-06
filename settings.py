import os
import json
import copy
from dataclasses import dataclass

# Импорт путей из центрального модуля
import paths


@dataclass
class SettingsFile:
    name: str
    path: str
    need_restore: bool
    default: list | dict

CONFIG = SettingsFile(
    name="config",
    path=paths.CONFIG_FILE,
    need_restore=True,
    default={
        "activation_code": "",  # Код активации из бота @SealPlayerokBot
        "playerok": {
            "api": {
                "token": "",
                "user_agent": "",
                "proxy": "",
                "requests_timeout": 10,
                "listener_requests_delay": 4
            },
            "watermark": {
                "enabled": True,
                "value": "🦭 𝗦𝗲𝗮𝗹 𝗣𝗹𝗮𝘆𝗲𝗿𝗼𝗸 𝗕𝗼𝘁 🦭"
            },
            "read_chat": {
                "enabled": True
            },
            "first_message": {
                "enabled": False
            },
            "custom_commands": {
                "enabled": True
            },
            "auto_deliveries": {
                "enabled": True
            },
            "auto_restore_items": {
                "enabled": False,
                "all": True
            },
            "auto_raise_items": {
                "enabled": False,
                "mode": "interval",
                "interval_hours": 24.0,
                "timings": [],
                "all": True
            },
            "auto_complete_deals": {
                "enabled": False,
                "all": True
            },
            "auto_reminder": {
                "enabled": False,
                "interval_hours": 24.0,
                "max_reminders": 3,
                "message_text": "⏰ Пожалуйста, подтвердите сделку, вы уже получили свой товар!\n🔗 {deal_link}"
            },
            "review_monitoring": {
                "enabled": True,
                "wait_minutes": 10,
                "check_interval": 30
            },
            "tg_logging": {
                "enabled": True,
                "chat_id": "",
                "events": {
                    "new_user_message": True,
                    "new_system_message": True,
                    "new_deal": True,
                    "new_review": True,
                    "new_problem": True,
                    "deal_status_changed": True,
                    "item_raised": True,
                }
            },
        },
        "telegram": {
            "api": {
                "token": "",
                "proxy": ""
            },
            "bot": {
                "password": "",
                "password_auth_enabled": True,
                "signed_users": []
            }
        }
    }
)
MESSAGES = SettingsFile(
    name="messages",
    path=paths.MESSAGES_FILE,
    need_restore=True,
    default={
        "first_message": {
            "enabled": False,
            "cooldown_days": 7,  # Количество дней до повторной отправки приветствия
            "text": [
                "🦭 Привет, {username}!",
            ]
        },
        "cmd_error": {
            "enabled": True,
            "text": [
                "❌ При вводе команды произошла ошибка: {error}"
            ]
        },
        "cmd_commands": {
            "enabled": True,
            "text": [
                "🕹️ Основные команды:",
                "・ !продавец — уведомить и позвать продавца в этот чат"
            ]
        },
        "cmd_seller": {
            "enabled": True,
            "text": [
                "💬 Продавец был вызван в этот чат. Ожидайте, пока он подключиться к диалогу..."
            ]
        },
        "new_deal": {
            "enabled": False,
            "text": [
                "📋 Спасибо за покупку «{deal_item_name}» в количестве {deal_amount} шт.",
                ""
                "Продавца сейчас может не быть на месте, чтобы позвать его, используйте команду !продавец."
            ]
        },
        "deal_pending": {
            "enabled": False,
            "text": [
                "⌛ Отправьте нужные данные, чтобы я смог выполнить ваш заказ"
            ]
        },
        "deal_sent": {
            "enabled": False,
            "text": [
                "✅ Я подтвердил выполнение вашего заказа! Если вы не получили купленный товар - напишите это в чате"
            ]
        },
        "deal_confirmed": {
            "enabled": False,
            "text": [
                "🌟 Спасибо за успешную сделку. Буду рад, если оставите отзыв. Жду вас в своём магазине в следующий раз, удачи!"
            ]
        },
        "deal_refunded": {
            "enabled": False,
            "text": [
                "📦 Заказ был возвращён. Надеюсь эта сделка не принесла вам неудобств. Жду вас в своём магазине в следующий раз, удачи!"
            ]
        },
        "deal_has_problem": {
            "enabled": False,
            "text": [
                "Пожалуйста, опишите детали своей претензии в чате, чтобы мы быстрее её решили."
            ]
        },
        "deal_problem_resolved": {
            "enabled": False,
            "text": [
                "Если остались вопросы, напишите в чат."
            ]
        },
        "new_review_response": {
            "enabled": False,
            "text": [
                "⭐ Большое спасибо за отзыв! Ваше мнение очень важно для нас."
            ]
        }
    }
)
CUSTOM_COMMANDS = SettingsFile(
    name="custom_commands",
    path=paths.CUSTOM_COMMANDS_FILE,
    need_restore=False,
    default={}
)
AUTO_DELIVERIES = SettingsFile(
    name="auto_deliveries",
    path=paths.AUTO_DELIVERIES_FILE,
    need_restore=False,
    default=[]
)
AUTO_RESTORE_ITEMS = SettingsFile(
    name="auto_restore_items",
    path=paths.AUTO_RESTORE_ITEMS_FILE,
    need_restore=False,
    default={
        "included": [],
        "excluded": []
    }
)
AUTO_RAISE_ITEMS = SettingsFile(
    name="auto_raise_items",
    path=paths.AUTO_RAISE_ITEMS_FILE,
    need_restore=False,
    default={
        "included": [],
        "excluded": []
    }
)
AUTO_COMPLETE_ITEMS = SettingsFile(
    name="auto_complete_items",
    path=paths.AUTO_COMPLETE_ITEMS_FILE,
    need_restore=False,
    default={
        "included": [],
        "excluded": []
    }
)
QUICK_REPLIES = SettingsFile(
    name="quick_replies",
    path=paths.QUICK_REPLIES_FILE,
    need_restore=False,
    default={
        "Ожидание": "Отвечу чуть позже, пожалуйста подождите.",
        "Спасибо": "Спасибо за покупку! Буду рад видеть вас снова!"
    }
)
PROXY_LIST = SettingsFile(
    name="proxy_list",
    path=paths.PROXY_LIST_FILE,
    need_restore=False,
    default={}  # {id: proxy_string}
)
DATA = [
    CONFIG,
    MESSAGES,
    CUSTOM_COMMANDS,
    AUTO_DELIVERIES,
    AUTO_RESTORE_ITEMS,
    AUTO_RAISE_ITEMS,
    AUTO_COMPLETE_ITEMS,
    QUICK_REPLIES,
    PROXY_LIST,
]


def validate_config(config, default):
    """
    Проверяет структуру конфига на соответствие стандартному шаблону.

    :param config: Текущий конфиг.
    :type config: `dict`

    :param default: Стандартный шаблон конфига.
    :type default: `dict`

    :return: True если структура валидна, иначе False.
    :rtype: bool
    """
    for key, value in default.items():
        if key not in config:
            return False
        if type(config[key]) is not type(value):
            return False
        if isinstance(value, dict) and isinstance(config[key], dict):
            if not validate_config(config[key], value):
                return False
    return True


def restore_config(config: dict, default: dict):
    """
    Восстанавливает недостающие параметры в конфиге из стандартного шаблона.
    И удаляет параметры из конфига, которых нету в стандартном шаблоне.

    :param config: Текущий конфиг.
    :type config: `dict`

    :param default: Стандартный шаблон конфига.
    :type default: `dict`

    :return: Восстановленный конфиг.
    :rtype: `dict`
    """
    config = copy.deepcopy(config)

    def check_default(config, default):
        for key, value in dict(default).items():
            if key not in config:
                config[key] = value
            elif type(value) is not type(config[key]):
                try:
                    equal = value == config[key]
                    if equal:
                        pass
                except:
                    config[key] = value
            elif isinstance(value, dict) and isinstance(config[key], dict):
                check_default(config[key], value)
        return config

    config = check_default(config, default)
    return config


def get_json(path: str, default: dict, need_restore: bool = True) -> dict:
    """
    Получает данные файла настроек.
    Создаёт файл настроек, если его нет.
    Добавляет новые данные, если такие есть.

    :param path: Путь к json файлу.
    :type path: `str`

    :param default: Стандартный шаблон файла.
    :type default: `dict`

    :param need_restore: Нужно ли сделать проверку на целостность конфига.
    :type need_restore: `bool`
    """
    folder_path = os.path.dirname(path)
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        if need_restore:
            new_config = restore_config(config, default)
            if config != new_config:
                config = new_config
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=4, ensure_ascii=False)
    except:
        config = default
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    finally:
        return config


def set_json(path: str, new: dict):
    """
    Устанавливает новые данные в файл настроек.

    :param path: Путь к json файлу.
    :type path: `str`

    :param new: Новые данные.
    :type new: `dict`
    """
    import stat
    from logging import getLogger
    logger = getLogger("settings")

    try:
        logger.debug(f"[set_json] Начало записи в {path}")

        if os.path.exists(path):
            if not os.access(path, os.W_OK):
                logger.warning(f"[set_json] Файл {path} недоступен для записи, пытаюсь исправить права")
                try:
                    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
                    logger.info(f"[set_json] Права исправлены для {path}")
                except Exception as e:
                    logger.error(f"[set_json] Не удалось исправить права: {e}")
                    dir_path = os.path.dirname(path)
                    raise PermissionError(
                        f"Нет прав на запись в {path}.\n"
                        f"Выполните: sudo chown -R $USER:$USER {dir_path}"
                    )

        logger.debug(f"[set_json] Данные для записи: {json.dumps(new, ensure_ascii=False)[:200]}...")

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(new, f, indent=4, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        try:
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
        except:
            pass
        logger.debug(f"[set_json] Запись завершена, файл синхронизирован")

        with open(path, 'r', encoding='utf-8') as f:
            verify = json.load(f)

        logger.debug(f"[set_json] Проверка: данные прочитаны обратно из файла")

        if verify != new:
            logger.error(f"[set_json] ОШИБКА! Данные в файле не совпадают с записанными!")
            logger.error(f"[set_json] Ожидалось: {json.dumps(new, ensure_ascii=False)[:200]}...")
            logger.error(f"[set_json] Получено: {json.dumps(verify, ensure_ascii=False)[:200]}...")
        else:
            logger.debug(f"[set_json] Проверка пройдена: данные совпадают")

    except PermissionError as e:
        logger.error(f"[set_json] ОШИБКА ПРАВ ДОСТУПА: {e}")
        raise
    except IOError as e:
        logger.error(f"[set_json] ОШИБКА ВВОДА-ВЫВОДА: {e}")
        raise
    except Exception as e:
        logger.error(f"[set_json] НЕОЖИДАННАЯ ОШИБКА: {e}")
        raise


class Settings:

    @staticmethod
    def get(name: str, data: list[SettingsFile] = DATA) -> dict | None:
        try:
            file = [file for file in data if file.name == name][0]
            return get_json(file.path, file.default, file.need_restore)
        except Exception as e:
            from logging import getLogger
            getLogger("settings").error(f"Ошибка чтения настроек '{name}': {e}")
            return None

    @staticmethod
    def set(name: str, new: list | dict, data: list[SettingsFile] = DATA):
        try:
            file = [file for file in data if file.name == name][0]
            set_json(file.path, new)
            from logging import getLogger
            getLogger("settings").debug(f"Настройки '{name}' сохранены в {file.path}")
        except Exception as e:
            from logging import getLogger
            getLogger("settings").error(f"Ошибка сохранения настроек '{name}': {e}", exc_info=True)
