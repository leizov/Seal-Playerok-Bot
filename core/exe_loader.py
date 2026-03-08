"""
PYD Plugin Loader
==================
Загрузчик скомпилированных .pyd плагинов из папки plugins/

.pyd - это Python extension modules, скомпилированные через Nuitka --module.
Они импортируются как обычные Python модули, поэтому:
- Роутеры aiogram работают ✅
- Обработчики событий Playerok работают ✅
- bot.send_message() работает ✅

ВАЖНО: .exe через subprocess НЕ ПОДХОДИТ для плагинов, потому что:
- subprocess = отдельный процесс
- Нет доступа к объектам бота (dispatcher, bot instance)
- Роутеры не зарегистрируются
- События не придут
"""

import os
import sys
import importlib.util
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from logging import getLogger

logger = getLogger("seal.pyd_loader")


@dataclass
class PydPluginInfo:
    """Информация о загруженном .pyd плагине"""
    name: str
    path: Path
    module: Optional[Any]  # Загруженный Python модуль
    status: str  # 'loaded', 'error', 'unloaded'
    loaded_at: Optional[float]
    error_message: Optional[str] = None
    
    # Экспорты плагина
    telegram_bot_routers: List = field(default_factory=list)
    playerok_event_handlers: Dict = field(default_factory=dict)
    bot_event_handlers: Dict = field(default_factory=dict)
    bot_commands: List = field(default_factory=list)
    meta: Dict = field(default_factory=dict)


class PydPluginLoader:
    """
    Загрузчик .pyd плагинов (Python extension modules)
    
    .pyd создаются через: python -m nuitka --module plugin.py
    
    Usage:
        loader = PydPluginLoader(plugins_dir="./plugins")
        plugins = loader.load_all()
        
        for plugin in plugins.values():
            # Регистрируем роутеры в диспетчере
            for router in plugin.telegram_bot_routers:
                dp.include_router(router)
    """
    
    # Поддерживаемые расширения
    EXTENSIONS = ['.pyd', '.so', '.cpython-312-x86_64-linux-gnu.so']
    
    def __init__(self, plugins_dir: Path = None):
        """
        Args:
            plugins_dir: Директория с .pyd плагинами
        """
        self.plugins_dir = Path(plugins_dir) if plugins_dir else Path("plugins")
        self.plugins_dir.mkdir(exist_ok=True)
        
        self._plugins: Dict[str, PydPluginInfo] = {}
    
    def discover(self) -> List[Path]:
        """Поиск .pyd/.so плагинов в папке"""
        plugins = []
        
        for file in self.plugins_dir.iterdir():
            if file.is_file():
                # Проверяем расширения
                if file.suffix.lower() == '.pyd':
                    plugins.append(file)
                elif '.cpython-' in file.name and file.suffix == '.so':
                    plugins.append(file)
                elif file.suffix.lower() == '.so' and sys.platform != 'win32':
                    plugins.append(file)
        
        return sorted(plugins)
    
    def get_plugin_name(self, path: Path) -> str:
        """Извлечение имени плагина из пути
        
        Примеры:
            steam_points_plugin.cp312-win_amd64.pyd -> steam_points_plugin
            steam_points_plugin_0e43a519.cp312-win_amd64.pyd -> steam_points_plugin
            my_plugin.cpython-312-x86_64-linux-gnu.so -> my_plugin
        """
        import re
        name = path.stem
        
        # Убираем .cpXXX-win_amd64 и .cpython-XXX-... суффиксы
        # Паттерн: .cp312-win_amd64 или .cpython-312-x86_64-linux-gnu
        name = re.sub(r'\.cp\d+-.*$', '', name)
        name = re.sub(r'\.cpython-\d+-.*$', '', name)
        
        # Убираем суффикс HWID (последние 8 символов после _)
        parts = name.rsplit('_', 1)
        if len(parts) == 2 and len(parts[1]) == 8 and parts[1].isalnum():
            return parts[0]
        
        return name
    
    def get_module_name(self, path: Path) -> str:
        """Получение имени модуля для импорта (с суффиксом HWID, без .cpXXX)
        
        Для импорта нужно точное имя модуля как в PyInit_XXX
        steam_points_plugin_0e43a519.cp312-win_amd64.pyd -> steam_points_plugin_0e43a519
        """
        import re
        name = path.stem
        
        # Убираем только .cpXXX-win_amd64 суффикс, оставляем HWID
        name = re.sub(r'\.cp\d+-.*$', '', name)
        name = re.sub(r'\.cpython-\d+-.*$', '', name)
        
        return name
    
    def load_all(self) -> Dict[str, PydPluginInfo]:
        """Загрузка всех .pyd плагинов из папки"""
        plugins = self.discover()
        
        if not plugins:
            logger.debug("Скомпилированные .pyd плагины не найдены")
            return {}
        
        logger.info(f"Найдено {len(plugins)} .pyd плагин(ов)")
        
        for plugin_path in plugins:
            self.load(plugin_path)
        
        loaded_count = len([p for p in self._plugins.values() if p.status == 'loaded'])
        if loaded_count > 0:
            logger.info(f"Загружено {loaded_count} .pyd плагин(ов)")
        
        return self._plugins
    
    def load(self, plugin_path: Path) -> Optional[PydPluginInfo]:
        """
        Загрузка одного .pyd плагина
        
        Импортирует .pyd как Python модуль и извлекает:
        - TELEGRAM_BOT_ROUTERS
        - PLAYEROK_EVENT_HANDLERS
        - BOT_EVENT_HANDLERS
        - BOT_COMMANDS
        - PREFIX, VERSION, NAME, DESCRIPTION, AUTHORS, LINKS
        """
        display_name = self.get_plugin_name(plugin_path)  # Для отображения (без HWID)
        module_name = self.get_module_name(plugin_path)   # Для импорта (с HWID)
        
        if display_name in self._plugins and self._plugins[display_name].status == 'loaded':
            logger.warning(f"Плагин '{display_name}' уже загружен")
            return self._plugins[display_name]
        
        logger.info(f"Загрузка .pyd плагина: {display_name}")
        
        try:
            # Загружаем модуль (используем module_name для импорта!)
            spec = importlib.util.spec_from_file_location(module_name, plugin_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"Не удалось загрузить spec из {plugin_path}")
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            
            # Извлекаем экспорты
            info = PydPluginInfo(
                name=display_name,
                path=plugin_path,
                module=module,
                status='loaded',
                loaded_at=time.time()
            )
            
            # Роутеры Telegram
            if hasattr(module, 'TELEGRAM_BOT_ROUTERS'):
                info.telegram_bot_routers = list(module.TELEGRAM_BOT_ROUTERS)
                logger.debug(f"  Роутеров: {len(info.telegram_bot_routers)}")
            
            # Обработчики Playerok
            if hasattr(module, 'PLAYEROK_EVENT_HANDLERS'):
                info.playerok_event_handlers = dict(module.PLAYEROK_EVENT_HANDLERS)
                logger.debug(f"  Обработчиков Playerok: {len(info.playerok_event_handlers)}")
            
            # Обработчики бота
            if hasattr(module, 'BOT_EVENT_HANDLERS'):
                info.bot_event_handlers = dict(module.BOT_EVENT_HANDLERS)
            
            # Команды
            if hasattr(module, 'BOT_COMMANDS'):
                if callable(module.BOT_COMMANDS):
                    info.bot_commands = module.BOT_COMMANDS()
                else:
                    info.bot_commands = list(module.BOT_COMMANDS)
            elif hasattr(module, 'get_commands'):
                info.bot_commands = module.get_commands()

            try:
                _has_routers = hasattr(module, 'TELEGRAM_BOT_ROUTERS')
                _has_playerok = hasattr(module, 'PLAYEROK_EVENT_HANDLERS')
                _has_bot_events = hasattr(module, 'BOT_EVENT_HANDLERS')
                _has_cmds = hasattr(module, 'BOT_COMMANDS') or hasattr(module, 'get_commands')

                _playerok_events = len(info.playerok_event_handlers or {})
                _playerok_handlers = sum(len(v or []) for v in (info.playerok_event_handlers or {}).values())
                _playerok_key_types = sorted({type(k).__name__ for k in (info.playerok_event_handlers or {}).keys()})
                _init_count = len((info.bot_event_handlers or {}).get('INIT', []) or [])
                _post_init_count = len((info.bot_event_handlers or {}).get('POST_INIT', []) or [])

                # logger.info(
                #     f".pyd exports {display_name}: "
                #     f"routers={_has_routers}({len(info.telegram_bot_routers)}), "
                #     f"playerok={_has_playerok}({ _playerok_events } events/{ _playerok_handlers } handlers, key_types={_playerok_key_types}), "
                #     f"bot_events={_has_bot_events}(INIT={_init_count},POST_INIT={_post_init_count}), "
                #     f"commands={_has_cmds}({len(info.bot_commands)})"
                # )
            except Exception:
                pass
            
            # Метаданные
            for attr in ['PREFIX', 'VERSION', 'NAME', 'DESCRIPTION', 'AUTHORS', 'LINKS']:
                if hasattr(module, attr):
                    info.meta[attr.lower()] = getattr(module, attr)
            
            self._plugins[display_name] = info
            
            plugin_version = info.meta.get('version', '?')
            logger.info(f"✓ Плагин '{display_name}' v{plugin_version} загружен")
            
            return info
            
        except Exception as e:
            import traceback
            info = PydPluginInfo(
                name=display_name,
                path=plugin_path,
                module=None,
                status='error',
                loaded_at=None,
                error_message=str(e)
            )
            self._plugins[display_name] = info
            logger.error(f"✗ Ошибка загрузки плагина '{display_name}': {e}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return info
    
    def unload(self, name: str) -> bool:
        """Выгрузка плагина (удаление из sys.modules)"""
        if name not in self._plugins:
            return False
        
        info = self._plugins[name]
        module_name = self.get_module_name(info.path)
        
        # Удаляем из sys.modules
        if module_name in sys.modules:
            del sys.modules[module_name]
        
        info.status = 'unloaded'
        info.module = None
        
        logger.info(f"Плагин '{name}' выгружен")
        return True
    
    def reload(self, name: str) -> Optional[PydPluginInfo]:
        """Перезагрузка плагина"""
        if name not in self._plugins:
            return None
        
        path = self._plugins[name].path
        self.unload(name)
        return self.load(path)
    
    def get_all_routers(self) -> List:
        """Получить все роутеры из всех плагинов"""
        routers = []
        for plugin in self._plugins.values():
            if plugin.status == 'loaded':
                routers.extend(plugin.telegram_bot_routers)
        return routers
    
    def get_all_playerok_handlers(self) -> Dict:
        """Получить все обработчики Playerok"""
        handlers = {}
        for plugin in self._plugins.values():
            if plugin.status == 'loaded':
                for event, funcs in plugin.playerok_event_handlers.items():
                    handlers.setdefault(event, []).extend(funcs)
        return handlers
    
    def get_status(self) -> Dict[str, dict]:
        """Статус всех плагинов"""
        result = {}
        
        for name, info in self._plugins.items():
            result[name] = {
                'name': info.name,
                'path': str(info.path),
                'status': info.status,
                'loaded_at': info.loaded_at,
                'meta': info.meta,
                'routers': len(info.telegram_bot_routers),
                'playerok_handlers': len(info.playerok_event_handlers),
                'commands': len(info.bot_commands),
                'error': info.error_message
            }
        
        return result


# Singleton instance
pyd_loader: Optional[PydPluginLoader] = None


def get_pyd_loader() -> PydPluginLoader:
    """Получить экземпляр загрузчика"""
    global pyd_loader
    if pyd_loader is None:
        pyd_loader = PydPluginLoader()
    return pyd_loader


# Алиасы для совместимости
ExePluginLoader = PydPluginLoader  # deprecated
get_exe_loader = get_pyd_loader  # deprecated
