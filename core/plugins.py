import os
import sys
import importlib
import uuid
from uuid import UUID
from pathlib import Path
from colorama import Fore
from dataclasses import dataclass
from logging import getLogger

# Импорт путей из центрального модуля
import paths

from __init__ import ACCENT_COLOR
from core.handlers import (
    register_playerok_event_handlers, 
    remove_playerok_event_handlers, 
    call_bot_event
)
from core.utils import install_requirements
from core.exe_loader import PydPluginLoader


logger = getLogger("seal.plugins")


@dataclass
class PluginMeta:
    prefix: str
    version: str
    name: str
    description: str
    authors: str
    links: str

@dataclass
class Plugin:
    uuid: UUID
    enabled: bool
    meta: PluginMeta
    playerok_event_handlers: dict
    telegram_bot_routers: list
    bot_commands: list
    _dir_name: str
    _routers_registered: bool = False  # Флаг, указывающий зарегистрированы ли роутеры в диспетчере


loaded_plugins: list[Plugin] = []


def get_plugins():
    """
    Возвращает загруженные плагины.

    :return: Загруженные плагины
    :rtype: `list` of `core.plugins.Plugin`
    """
    return loaded_plugins


def set_plugins(plugins: list[Plugin]):
    """
    Устанавливает загруженные плагины.

    :param plugins: Новые загруженные плагины
    :type plugins: `list` of `core.plugins.Plugin`
    """
    global loaded_plugins
    loaded_plugins = plugins


def get_plugin_by_uuid(plugin_uuid: UUID) -> Plugin | None:
    """ 
    Получает плагин по UUID.
    
    :param plugin_uuid: UUID плагина.
    :type plugin_uuid: `uuid.UUID`

    :return: Объект плагина.
    :rtype: `core.plugins.Plugin` or `None`
    """
    try: 
        return [plugin for plugin in loaded_plugins if plugin.uuid == plugin_uuid][0]
    except: 
        return None


async def _activate_plugin(plugin: Plugin) -> bool:
    """
    Активирует плагин: регистрирует обработчики событий Playerok.
    
    :param plugin: Плагин для активации
    :type plugin: `core.plugins.Plugin`
    
    Примечание: Роутеры Telegram уже зарегистрированы при инициализации бота.
    Middleware контролирует их активность через флаг enabled.
    """
    global loaded_plugins

    # Регистрируем обработчики событий Playerok
    register_playerok_event_handlers(plugin.playerok_event_handlers)

    try:
        playerok_events = len(plugin.playerok_event_handlers or {})
        playerok_handlers = sum(len(v or []) for v in (plugin.playerok_event_handlers or {}).values())
        tg_routers = len(plugin.telegram_bot_routers or [])
        bot_commands = len(plugin.bot_commands or [])
        # logger.info(
        #     f"Плагин активирован: {plugin.meta.name} | "
        #     f"PlayerOK events={playerok_events}, handlers={playerok_handlers} | "
        #     f"TG routers={tg_routers} | commands={bot_commands}"
        # )
    except Exception:
        pass

    # Помечаем плагин как активный
    # Роутеры уже зарегистрированы при инициализации бота,
    # middleware будет контролировать их выполнение
    plugin.enabled = True
    loaded_plugins[loaded_plugins.index(plugin)] = plugin


async def activate_plugin(plugin_uuid: UUID) -> bool:
    """
    Активирует плагин и добавляет его обработчики.

    :param plugin_uuid: UUID плагина.
    :type plugin_uuid: `uuid.UUID`

    :return: True, если плагин был активирован. False, если не был активирован.
    :rtype: `bool`
    """
    try:
        plugin = get_plugin_by_uuid(plugin_uuid)
        if not plugin:
            logger.error(f"{Fore.LIGHTRED_EX}Плагин с UUID {plugin_uuid} не найден")
            return False
    
        await _activate_plugin(plugin)
        logger.info(f"Плагин {Fore.LIGHTWHITE_EX}{plugin.meta.name} {Fore.WHITE}активирован")
        
        return True
    except Exception as e:
        logger.error(f"{Fore.LIGHTRED_EX}Ошибка при активации плагина {plugin_uuid}: {Fore.WHITE}{e}")
        return False


async def _deactivate_plugin(plugin: Plugin) -> bool:
    """
    Деактивирует плагин: удаляет обработчики и роутеры.
    
    :param plugin: Плагин для деактивации
    :type plugin: `core.plugins.Plugin`
    
    Примечание: Роутеры остаются зарегистрированными в диспетчере,
    но плагин помечается как неактивный. Middleware будет блокировать
    выполнение обработчиков неактивных плагинов.
    """
    global loaded_plugins

    # Удаляем обработчики событий Playerok
    remove_playerok_event_handlers(plugin.playerok_event_handlers)

    # Помечаем плагин как неактивный
    # Роутеры остаются в диспетчере, но middleware будет их блокировать
    plugin.enabled = False
    loaded_plugins[loaded_plugins.index(plugin)] = plugin


async def deactivate_plugin(plugin_uuid: UUID) -> bool:
    """ 
    Деактивирует плагин и удаляет его обработчики.
    
    :param plugin_uuid: UUID плагина.
    :type plugin_uuid: `uuid.UUID`

    :return: True, если плагин был деактивирован. False, если не был деактивирован.
    :rtype: `bool`
    """
    try:
        plugin = get_plugin_by_uuid(plugin_uuid)
        if not plugin:
            logger.error(f"{Fore.LIGHTRED_EX}Плагин с UUID {plugin_uuid} не найден")
            return False
    
        await _deactivate_plugin(plugin)
        logger.info(f"Плагин {Fore.LIGHTWHITE_EX}{plugin.meta.name} {Fore.WHITE}деактивирован")
        
        return True
    except Exception as e:
        logger.error(f"{Fore.LIGHTRED_EX}Ошибка при деактивации плагина {plugin_uuid}: {Fore.WHITE}{e}")
        return False


async def reload_plugin(plugin_uuid: UUID) -> bool:
    """
    Перезагружает плагин (деактивирует и импортирует снова).
    
    :param plugin_uuid: UUID плагина.
    :type plugin_uuid: `uuid.UUID`

    :return: True, если плагин был перезагружен. False, если не был перезагружен.
    :rtype: `bool`
    
    ВНИМАНИЕ: Эта функция может вызывать проблемы с дублированием роутеров.
    Рекомендуется использовать полный перезапуск бота через /restart для обновления плагинов.
    """
    try:
        plugin = get_plugin_by_uuid(plugin_uuid)
        if not plugin:
            logger.error(f"{Fore.LIGHTRED_EX}Плагин с UUID {plugin_uuid} не найден")
            return False
        
        # Деактивируем плагин
        await _deactivate_plugin(plugin)
        
        # Удаляем модуль из sys.modules
        module_name = f"plugins.{plugin._dir_name}"
        if module_name in sys.modules:
            del sys.modules[module_name]
        
        # Импортируем модуль заново
        importlib.import_module(module_name)
        
        # Обновляем данные плагина из перезагруженного модуля
        module = sys.modules[module_name]
        if hasattr(module, "PLAYEROK_EVENT_HANDLERS"):
            plugin.playerok_event_handlers = {}
            for key, funcs in module.PLAYEROK_EVENT_HANDLERS.items():
                plugin.playerok_event_handlers.setdefault(key, []).extend(funcs)
        if hasattr(module, "TELEGRAM_BOT_ROUTERS"):
            plugin.telegram_bot_routers = list(module.TELEGRAM_BOT_ROUTERS)
        
        # Активируем плагин заново
        await _activate_plugin(plugin)

        logger.info(f"Плагин {Fore.LIGHTWHITE_EX}{plugin.meta.name} {Fore.WHITE}перезагружен")
        return True
    except Exception as e:
        logger.error(f"{Fore.LIGHTRED_EX}Ошибка при перезагрузке плагина {plugin_uuid}: {Fore.WHITE}{e}")
        return False


def load_plugins() -> list[Plugin]:
    """Загружает все плагины из папки plugins (папки с __init__.py, одиночные .py файлы и .pyd файлы)."""
    global loaded_plugins
    
    plugins = []
    plugins_path = paths.PLUGINS_DIR
    os.makedirs(plugins_path, exist_ok=True)

    # ═══════════════════════════════════════════════════════════════
    # 1. Загрузка обычных плагинов (папки с __init__.py и одиночные .py файлы)
    # ═══════════════════════════════════════════════════════════════
    for name in os.listdir(plugins_path):
        playerok_event_handlers = {}
        telegram_bot_routers = []
        plugin_path = os.path.join(plugins_path, name)
        
        if os.path.isdir(plugin_path) and "__init__.py" in os.listdir(plugin_path):
            try:
                install_requirements(os.path.join(plugin_path, "requirements.txt"))
                plugin_module = importlib.import_module(f"plugins.{name}")
                
                # Регистрируем обработчики событий бота (INIT и POST_INIT)
                if hasattr(plugin_module, "BOT_EVENT_HANDLERS"):
                    try:
                        _init_count = len((plugin_module.BOT_EVENT_HANDLERS or {}).get("INIT", []) or [])
                        _post_init_count = len((plugin_module.BOT_EVENT_HANDLERS or {}).get("POST_INIT", []) or [])
                        if _init_count or _post_init_count:
                            logger.info(
                                f"Регистрация BOT_EVENT_HANDLERS плагина {name}: "
                                f"INIT={_init_count}, POST_INIT={_post_init_count}"
                            )
                    except Exception:
                        pass
                    for event_type, funcs in plugin_module.BOT_EVENT_HANDLERS.items():
                        if event_type in ["INIT", "POST_INIT"]:
                            from core.handlers import add_bot_event_handler
                            for func in funcs:
                                add_bot_event_handler(event_type, func)
                
                if hasattr(plugin_module, "PLAYEROK_EVENT_HANDLERS"):
                    for key, funcs in plugin_module.PLAYEROK_EVENT_HANDLERS.items():
                        playerok_event_handlers.setdefault(key, []).extend(funcs)
                        
                if hasattr(plugin_module, "TELEGRAM_BOT_ROUTERS"):
                    telegram_bot_routers.extend(plugin_module.TELEGRAM_BOT_ROUTERS)

                bot_commands = []
                if hasattr(plugin_module, "BOT_COMMANDS"):
                    if callable(plugin_module.BOT_COMMANDS):
                        bot_commands = plugin_module.BOT_COMMANDS()
                    elif isinstance(plugin_module.BOT_COMMANDS, list):
                        bot_commands = plugin_module.BOT_COMMANDS
                elif hasattr(plugin_module, "get_commands"):
                    bot_commands = plugin_module.get_commands()

                plugin_data = Plugin(
                    uuid.uuid5(uuid.NAMESPACE_DNS, name),
                    enabled=False,
                    meta=PluginMeta(
                        plugin_module.PREFIX,
                        plugin_module.VERSION,
                        plugin_module.NAME,
                        plugin_module.DESCRIPTION,
                        plugin_module.AUTHORS,
                        plugin_module.LINKS
                    ),
                    playerok_event_handlers=playerok_event_handlers,
                    telegram_bot_routers=telegram_bot_routers,
                    bot_commands=bot_commands,
                    _dir_name=name,
                    _routers_registered=False
                )
                plugins.append(plugin_data)
            except Exception as e:
                import traceback
                logger.error(f"{Fore.LIGHTRED_EX}✗ Ошибка при загрузке плагина {name}: {Fore.WHITE}{e}")
                logger.debug(f"{Fore.LIGHTRED_EX}Traceback:\n{traceback.format_exc()}")
                logger.info(f"{Fore.YELLOW}Бот продолжит работу без плагина {name}")
        
        # Вариант 2: Одиночный .py файл
        elif name.endswith('.py') and name not in ['__init__.py']:
            try:
                module_name = name[:-3]
                plugin_module = importlib.import_module(f"plugins.{module_name}")
                
                playerok_event_handlers = {}
                telegram_bot_routers = []
                
                # Регистрируем обработчики событий бота (INIT и POST_INIT)
                if hasattr(plugin_module, "BOT_EVENT_HANDLERS"):
                    try:
                        _init_count = len((plugin_module.BOT_EVENT_HANDLERS or {}).get("INIT", []) or [])
                        _post_init_count = len((plugin_module.BOT_EVENT_HANDLERS or {}).get("POST_INIT", []) or [])
                        if _init_count or _post_init_count:
                            logger.info(
                                f"Регистрация BOT_EVENT_HANDLERS плагина {module_name}: "
                                f"INIT={_init_count}, POST_INIT={_post_init_count}"
                            )
                    except Exception:
                        pass
                    for event_type, funcs in plugin_module.BOT_EVENT_HANDLERS.items():
                        if event_type in ["INIT", "POST_INIT"]:
                            from core.handlers import add_bot_event_handler
                            for func in funcs:
                                add_bot_event_handler(event_type, func)
                
                if hasattr(plugin_module, "PLAYEROK_EVENT_HANDLERS"):
                    for key, funcs in plugin_module.PLAYEROK_EVENT_HANDLERS.items():
                        playerok_event_handlers.setdefault(key, []).extend(funcs)
                        
                if hasattr(plugin_module, "TELEGRAM_BOT_ROUTERS"):
                    telegram_bot_routers.extend(plugin_module.TELEGRAM_BOT_ROUTERS)

                bot_commands = []
                if hasattr(plugin_module, "BOT_COMMANDS"):
                    if callable(plugin_module.BOT_COMMANDS):
                        bot_commands = plugin_module.BOT_COMMANDS()
                    elif isinstance(plugin_module.BOT_COMMANDS, list):
                        bot_commands = plugin_module.BOT_COMMANDS
                elif hasattr(plugin_module, "get_commands"):
                    bot_commands = plugin_module.get_commands()

                plugin_data = Plugin(
                    uuid.uuid5(uuid.NAMESPACE_DNS, module_name),
                    enabled=False,
                    meta=PluginMeta(
                        plugin_module.PREFIX,
                        plugin_module.VERSION,
                        plugin_module.NAME,
                        plugin_module.DESCRIPTION,
                        plugin_module.AUTHORS,
                        plugin_module.LINKS
                    ),
                    playerok_event_handlers=playerok_event_handlers,
                    telegram_bot_routers=telegram_bot_routers,
                    bot_commands=bot_commands,
                    _dir_name=module_name,
                    _routers_registered=False
                )
                plugins.append(plugin_data)
                logger.info(f"{Fore.LIGHTGREEN_EX}✓ Загружен .py плагин: {module_name}")
            except Exception as e:
                import traceback
                logger.error(f"{Fore.LIGHTRED_EX}✗ Ошибка при загрузке .py плагина {name}: {Fore.WHITE}{e}")
                logger.debug(f"{Fore.LIGHTRED_EX}Traceback:\n{traceback.format_exc()}")
                logger.info(f"{Fore.YELLOW}Бот продолжит работу без плагина {name}")
    
    # ═══════════════════════════════════════════════════════════════
    # 2. Загрузка скомпилированных .pyd плагинов
    # ═══════════════════════════════════════════════════════════════
    try:
        pyd_loader = PydPluginLoader(plugins_dir=Path(plugins_path))
        pyd_plugins = pyd_loader.load_all()
        
        for pyd_name, pyd_info in pyd_plugins.items():
            if pyd_info.status != 'loaded':
                continue
            
            try:
                # Регистрируем обработчики событий бота (INIT и POST_INIT)
                if pyd_info.bot_event_handlers:
                    try:
                        _init_count = len((pyd_info.bot_event_handlers or {}).get("INIT", []) or [])
                        _post_init_count = len((pyd_info.bot_event_handlers or {}).get("POST_INIT", []) or [])
                        if _init_count or _post_init_count:
                            logger.info(
                                f"Регистрация BOT_EVENT_HANDLERS плагина {pyd_name}: "
                                f"INIT={_init_count}, POST_INIT={_post_init_count}"
                            )
                    except Exception:
                        pass
                    for event_type, funcs in pyd_info.bot_event_handlers.items():
                        if event_type in ["INIT", "POST_INIT"]:
                            from core.handlers import add_bot_event_handler
                            for func in funcs:
                                add_bot_event_handler(event_type, func)
                
                # Конвертируем PydPluginInfo в Plugin
                plugin_data = Plugin(
                    uuid.uuid5(uuid.NAMESPACE_DNS, f"pyd_{pyd_name}"),
                    enabled=False,
                    meta=PluginMeta(
                        pyd_info.meta.get('prefix', f'[{pyd_name}]'),
                        pyd_info.meta.get('version', '1.0.0'),
                        pyd_info.meta.get('name', pyd_name),
                        pyd_info.meta.get('description', 'Compiled .pyd plugin'),
                        pyd_info.meta.get('authors', 'Unknown'),
                        pyd_info.meta.get('links', '')
                    ),
                    playerok_event_handlers=pyd_info.playerok_event_handlers,
                    telegram_bot_routers=pyd_info.telegram_bot_routers,
                    bot_commands=pyd_info.bot_commands,
                    _dir_name=f"pyd_{pyd_name}",
                    _routers_registered=False
                )
                plugins.append(plugin_data)
                logger.info(f"{Fore.LIGHTGREEN_EX}✓ Загружен .pyd плагин: {pyd_name}")
            except Exception as e:
                import traceback
                logger.error(f"{Fore.LIGHTRED_EX}✗ Ошибка при обработке .pyd плагина {pyd_name}: {Fore.WHITE}{e}")
                logger.debug(f"{Fore.LIGHTRED_EX}Traceback:\n{traceback.format_exc()}")
    except Exception as e:
        import traceback
        logger.error(f"{Fore.LIGHTRED_EX}✗ Ошибка при загрузке .pyd плагинов: {Fore.WHITE}{e}")
        logger.debug(f"{Fore.LIGHTRED_EX}Traceback:\n{traceback.format_exc()}")
    
    return plugins


def _format_string(count: int):
    last_num = int(str(count)[-1])
    if last_num == 1: 
        return f"Подключен {Fore.LIGHTCYAN_EX}{count} плагин"
    elif 2 <= last_num <= 4: 
        return f"Подключено {Fore.LIGHTCYAN_EX}{count} плагина"
    elif 5 <= last_num <= 9 or last_num == 0: 
        return f"Подключено {Fore.LIGHTCYAN_EX}{count} плагинов"


async def connect_plugins(plugins: list[Plugin]):
    """
    Подключает загруженные плагины.
    
    :param plugins: Загруженные плагины
    :type plugins: `list` of `core.plugins.Plugin`
    """
    global loaded_plugins

    for plugin in plugins:
        try:
            await _activate_plugin(plugin)
        except Exception as e:
            import traceback
            logger.error(f"{Fore.LIGHTRED_EX}✗ Ошибка при подключении плагина {plugin.meta.name}: {Fore.WHITE}{e}")
            logger.debug(f"{Fore.LIGHTRED_EX}Traceback:\n{traceback.format_exc()}")
            logger.info(f"{Fore.YELLOW}Бот продолжит работу без плагина {plugin.meta.name}")
    
    connected_plugins = [plugin for plugin in loaded_plugins if plugin.enabled]
    names = [f"{Fore.YELLOW}{plugin.meta.name} {Fore.LIGHTWHITE_EX}{plugin.meta.version}" for plugin in connected_plugins]
    if names:
        logger.info(f'{ACCENT_COLOR}{_format_string(len(connected_plugins))}: {f"{Fore.WHITE}, ".join(names)}')

