from __future__ import annotations
import asyncio
import textwrap
import logging
import random
from colorama import Fore
from aiogram import Bot, Dispatcher, F
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import BotCommand, InlineKeyboardMarkup
from aiogram.exceptions import TelegramRetryAfter, TelegramNetworkError, TelegramForbiddenError, TelegramAPIError
import re

from __init__ import ACCENT_COLOR, VERSION, DEVELOPER, REPOSITORY, TELEGRAM_CHANNEL, TELEGRAM_CHAT, TELEGRAM_BOT
from settings import Settings as sett
from core.proxy_utils import normalize_proxy, validate_proxy
from core.plugins import get_plugins
from core.handlers import call_bot_event

from . import router as main_router
from . import templates as templ


logger = logging.getLogger("seal.telegram")

TG_PROXY_HELP_TEXT = (
    "Если вы из RU региона, Telegram может работать нестабильно без прокси. "
    "Добавьте прокси не RU региона в bot_settings/config.json (telegram.api.proxy). "
    "Купить: https://proxylin.net?ref=448587"
)


def _build_tg_proxy_url(raw_proxy: str | None) -> tuple[str | None, str | None]:
    """
    Возвращает прокси для aiogram и нормализованное значение для config.
    """
    proxy = (raw_proxy or "").strip()
    if not proxy:
        return None, None

    validate_proxy(proxy)
    normalized_proxy = normalize_proxy(proxy)

    if normalized_proxy.startswith(("socks5://", "socks4://", "http://", "https://")):
        return normalized_proxy, normalized_proxy

    # По умолчанию для TG-прокси без схемы используем HTTP.
    return f"http://{normalized_proxy}", normalized_proxy


class TelegramFetchUpdatesHintHandler(logging.Handler):
    def emit(self, record: logging.LogRecord):
        try:
            message = record.getMessage()
        except Exception:
            return

        if "Failed to fetch updates" in message and "TelegramNetworkError" in message:
            logger.warning(
                "Если Telegram работает нестабильно, добавьте прокси не RU региона "
                "в bot_settings/config.json (telegram.api.proxy). "
                "Купить: https://proxylin.net?ref=448587"
            )


def get_telegram_bot() -> TelegramBot | None:
    if hasattr(TelegramBot, "instance"):
        return getattr(TelegramBot, "instance")


def get_telegram_bot_loop() -> asyncio.AbstractEventLoop | None:
    if hasattr(get_telegram_bot(), "loop"):
        return getattr(get_telegram_bot(), "loop")


class TelegramBot:
    def __new__(cls, *args, **kwargs) -> TelegramBot:
        if not hasattr(cls, "instance"):
            cls.instance = super(TelegramBot, cls).__new__(cls)
        return getattr(cls, "instance")

    def __init__(self):
        logging.getLogger("aiogram").setLevel(logging.ERROR)
        logging.getLogger("aiogram.event").setLevel(logging.ERROR)
        dispatcher_logger = logging.getLogger("aiogram.dispatcher")
        dispatcher_logger.setLevel(logging.ERROR)
        if not any(isinstance(handler, TelegramFetchUpdatesHintHandler) for handler in dispatcher_logger.handlers):
            dispatcher_logger.addHandler(TelegramFetchUpdatesHintHandler())

        config = sett.get("config")
        self.bot = self._build_bot_from_config(config)
        self.dp = Dispatcher()

        # Добавляем middleware для проверки авторизации и статуса плагинов
        from .middleware import AuthMiddleware, PluginStateMiddleware, ErrorMiddleware
        
        # ErrorMiddleware должен быть первым, чтобы перехватывать все ошибки
        self.dp.message.middleware(ErrorMiddleware())
        self.dp.callback_query.middleware(ErrorMiddleware())
        
        self.dp.message.middleware(PluginStateMiddleware())
        self.dp.callback_query.middleware(PluginStateMiddleware())
        self.dp.message.middleware(AuthMiddleware())
        self.dp.callback_query.middleware(AuthMiddleware())

        for plugin in get_plugins():
            try:
                logger.info(
                    f"Регистрация TG-роутеров плагина {plugin.meta.name}: {len(plugin.telegram_bot_routers)}"
                )
                for router in plugin.telegram_bot_routers:
                    main_router.include_router(router)
                # Помечаем, что роутеры уже зарегистрированы
                plugin._routers_registered = True
            except Exception as e:
                logger.error(f"✗ Ошибка при регистрации роутеров плагина {plugin.meta.name}: {e}")
                logger.info(f"Бот продолжит работу без роутеров плагина {plugin.meta.name}")
        self.dp.include_router(main_router)

    def _build_bot_from_config(self, config: dict | None = None) -> Bot:
        config = config or sett.get("config")
        token = config["telegram"]["api"]["token"]
        raw_proxy = (config["telegram"]["api"].get("proxy") or "").strip()

        if not raw_proxy:
            return Bot(token=token)

        try:
            proxy_url, normalized_proxy = _build_tg_proxy_url(raw_proxy)

            if normalized_proxy and normalized_proxy != raw_proxy:
                config["telegram"]["api"]["proxy"] = normalized_proxy
                sett.set("config", config)

            logger.info("TG-прокси применен ко всем запросам Telegram API.")
            return Bot(token=token, session=AiohttpSession(proxy=proxy_url))
        except Exception as proxy_error:
            logger.warning(
                f"Некорректный TG-прокси в bot_settings/config.json (telegram.api.proxy): {proxy_error}. "
                f"Telegram будет запущен без прокси."
            )
            logger.warning(TG_PROXY_HELP_TEXT)
            return Bot(token=token)


    async def _update_bot_commands(self):
        """
        Обновляет список команд бота, добавляя команды из плагинов.
          
        Метод собирает команды из всех загруженных плагинов, которые имеют команды,
        и добавляет их в список команд бота. Это позволяет плагинам добавлять свои
        команды в автодополнение Telegram.
        
        Обрабатывает ошибки для каждого плагина отдельно, чтобы сбой одного плагина
        не влиял на работу остальных.
        """
        try:
            config = sett.get("config")
            # Стандартные команды бота
            commands = [
                BotCommand(command="start", description="🦭 Главное меню"),
            ]
            
            # Команды администратора (добавляются только если пользователь авторизован)
            commands.extend([
                BotCommand(command="profile", description="🏠 Профиль Playerok"),
                BotCommand(command="deals", description="🧾 Поиск сделок"),
                BotCommand(command="restart", description="🔄 Перезагрузить бота"),
                BotCommand(command="update", description="⬆️ Обновить бота"),
                BotCommand(command="playerok_status", description="🔰 Проверить авторизацию в аккаунте"),
                # BotCommand(command="power_off", description="⚡ Выключить бота"), #todo продумать логику при автозапуске, пока спряу
                BotCommand(command="logs", description="📜 Показать логи"),
                BotCommand(command="error", description="🛑 Показать последнюю ошибку"),
                BotCommand(command="sys", description="🧪 Диагностика системы"),
                BotCommand(command="watermark", description="©️ Водяной знак"),
                BotCommand(command="fingerprint", description="🧑‍💻 Фингерпринт устройства"),
                BotCommand(command="config_backup", description="💾 Backup конфига"),

            ])
            
            def _normalize_command(raw: str) -> str | None:
                cmd = (raw or "").strip()
                if cmd.startswith("/"):
                    cmd = cmd[1:]
                cmd = cmd.strip().lower()
                if not cmd:
                    return None
                if not re.fullmatch(r"[a-z0-9_]{1,32}", cmd):
                    return None
                return cmd
            
            # Добавляем команды из плагинов
            for plugin in get_plugins():
                if hasattr(plugin, 'bot_commands') and plugin.bot_commands:
                    try:
                        plugin_cmds = plugin.bot_commands
                        if callable(plugin_cmds):
                            plugin_cmds = plugin_cmds()
                        if asyncio.iscoroutine(plugin_cmds):
                            plugin_cmds = await plugin_cmds
                        if not isinstance(plugin_cmds, (list, tuple)):
                            raise TypeError(
                                f"BOT_COMMANDS must be list/tuple, got {type(plugin_cmds).__name__}"
                            )
 
                        added = 0
                        
                        for cmd in plugin_cmds:
                            # Конвертируем tuple/list в BotCommand
                            if isinstance(cmd, (tuple, list)) and len(cmd) >= 2:
                                normalized = _normalize_command(str(cmd[0]))
                                if not normalized:
                                    logger.warning(
                                        f"Команда плагина {plugin.meta.name} пропущена (invalid): {cmd[0]!r}"
                                    )
                                    continue
                                commands.append(BotCommand(
                                    command=normalized,
                                    description=cmd[1]
                                ))
                                added += 1
                            elif isinstance(cmd, BotCommand):
                                normalized = _normalize_command(cmd.command)
                                if not normalized:
                                    logger.warning(
                                        f"Команда плагина {plugin.meta.name} пропущена (invalid): {cmd.command!r}"
                                    )
                                    continue
                                commands.append(
                                    BotCommand(command=normalized, description=cmd.description)
                                )
                                added += 1

                        logger.info(
                            f"Команды плагина {plugin.meta.name} добавлены: {added}"
                        )
                    except Exception as e:
                        logger.error(f"Ошибка получения команд из плагина {plugin.meta.name}: {e}")
            
            # Устанавливаем обновленный список команд
            await self.bot.set_my_commands(commands)
            logger.info(f"set_my_commands: установлено команд = {len(commands)}")
            
        except Exception as e:
            logger.error(f"Ошибка при обновлении команд бота: {e}")
    
    async def _set_main_menu(self):

        await self._update_bot_commands()

    async def _set_short_description(self):
        """Устанавливает короткое описание бота (раздел Bio в Telegram)."""
        try:
            short_description = (
                "📢 Канал: @SealPlayerok\n"
                "💬 Чат: @SealPlayerokChat\n"
                "🤖 Бот: @SealPlayerokBot"
            )
            # Очищаем и заново выставляем short description для default/ru/en,
            # чтобы убрать остатки старых значений в разных локалях Telegram-клиента.
            for lang in (None, "ru", "en"):
                clear_kwargs = {"short_description": ""}
                set_kwargs = {"short_description": short_description}
                if lang:
                    clear_kwargs["language_code"] = lang
                    set_kwargs["language_code"] = lang
                await self.bot.set_my_short_description(**clear_kwargs)
                await self.bot.set_my_short_description(**set_kwargs)
        except Exception:
            pass

    async def _set_description(self):
        """Устанавливает полное описание бота с короткими ссылками."""
        try:
            description = textwrap.dedent(f"""
🦭 SealPlayerokBot v{VERSION}

Бот-помощник для автоматизации работы с маркетплейсом Playerok.com

✨ Возможности:
• Вечный онлайн
• Авто-восстановление товаров
• Авто-выдача
• Авто-ответ
• Уведомления о сделках
• Вызов продавца в чат
• И многое другое

🔗 Ссылки:
• Канал: @SealPlayerok
• Чат: @SealPlayerokChat
• Бот: @SealPlayerokBot
• GitHub: github.com/leizov/Seal-Playerok-Bot

🦭 Разработчик: {DEVELOPER}
            """).strip()
            await self.bot.set_my_description(description=description)
        except Exception:
            pass
    

    async def run_bot(self):
        # Миграция старого прокси в новую систему (выполняется один раз)
        from core.proxy_migration import migrate_old_proxy_to_new_system
        migrate_old_proxy_to_new_system()
        
        self.loop = asyncio.get_running_loop()
        max_retries = 5  # Максимальное количество попыток подключения
        base_delay = 5  # Базовая задержка в секундах
        
        for attempt in range(1, max_retries + 1):
            try:
                # Проверяем соединение с Telegram API
                me = await self.bot.get_me()
                logger.info(f"{ACCENT_COLOR}Успешное подключение к Telegram API как @{me.username}")
                
                # Обновляем команды и настройки бота
                await self._update_bot_commands()
                await self._set_short_description()
                await self._set_description()
                
                await call_bot_event("ON_TELEGRAM_BOT_INIT", [self])
                
                logger.info(f"{ACCENT_COLOR}Telegram бот {Fore.LIGHTCYAN_EX}@{me.username} {ACCENT_COLOR}запущен и активен")
                
                # Отправляем уведомление о запуске
                await self.send_startup_notification()
                
                # Запускаем систему объявлений
                try:
                    from announcements import start_announcements_loop
                    await start_announcements_loop(self)
                except Exception as e:
                    logger.warning(f"Не удалось запустить систему объявлений: {e}")
                
                # Запускаем бота с обработкой ошибок
                try:
                    await self.dp.start_polling(self.bot, skip_updates=True, handle_signals=False)
                    break  # Выходим из цикла при успешном запуске
                except (TelegramNetworkError, TelegramAPIError) as e:
                    if attempt == max_retries:
                        raise  # Пробрасываем исключение, если попытки исчерпаны
                    logger.warning(f"Ошибка сети/API при запуске бота: {e}")
                    logger.warning(TG_PROXY_HELP_TEXT)
                
            except Exception as e:
                if attempt == max_retries:
                    logger.error(f"{Fore.RED}Не удалось подключиться к Telegram API после {max_retries} попыток. Завершение работы.")
                    logger.error(TG_PROXY_HELP_TEXT)
                    raise  # Пробрасываем исключение, если попытки исчерпаны
                
                # Вычисляем экспоненциальную задержку с джиттером
                delay = min(base_delay * (2 ** (attempt - 1)) + random.uniform(0, 1), 60)
                logger.warning(
                    f"{Fore.YELLOW}Ошибка подключения к Telegram API (попытка {attempt}/{max_retries}): {e}"
                    f"{Fore.WHITE} Повторная попытка через {delay:.1f} секунд..."
                )
                logger.warning(TG_PROXY_HELP_TEXT)
                await asyncio.sleep(delay)
                
                # Обновляем токен бота перед следующей попыткой
                if attempt % 3 == 0:  # Обновляем токен каждые 3 попытки
                    try:
                        config = sett.get("config")
                        self.bot = self._build_bot_from_config(config)
                        logger.info("Обновлен токен бота")
                    except Exception as token_error:
                        logger.error(f"Ошибка при обновлении токена бота: {token_error}")
        

    async def call_seller(self, calling_name: str, chat_id: int | str):
        """
        Пишет админу в Telegram с просьбой о помощи от заказчика.
                
        :param calling_name: Никнейм покупателя.
        :type calling_name: `str`

        :param chat_id: ID чата с заказчиком.
        :type chat_id: `int` or `str`
        """
        config = sett.get("config")
        for user_id in config["telegram"]["bot"]["signed_users"]:
            await self.bot.send_message(
                chat_id=user_id, 
                text=templ.call_seller_text(calling_name, f"https://playerok.com/chats/{chat_id}"),
                reply_markup=templ.destroy_kb(),
                parse_mode="HTML"
            )
        
    async def send_startup_notification(self):
        """
        Отправляет уведомление администратору о запуске бота.
        """
        try:
            config = sett.get("config")
            me = await self.bot.get_me()
            
            # Получаем информацию о системе
            import platform
            import socket
            import datetime
            
            hostname = socket.gethostname()
            ip_address = socket.gethostbyname(hostname)
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            message = (
                f"🦭 <b>Seal Playerok Bot v{VERSION} активен!</b>\n\n"
                f"• <b>Бот:</b> @{me.username}\n"
                f"• <b>Версия:</b> {VERSION}\n"
                f"• <b>Разработчик:</b> {DEVELOPER}\n"
                f"• <b>Репозиторий:</b> <a href=\"{REPOSITORY}\">GitHub</a>\n"
                f"• <b>Время запуска:</b> {current_time}\n"
                f"• <b>Сервер:</b> {hostname}\n"
                f"• <b>ОС:</b> {platform.system()} {platform.release()}\n\n"
                f"🥰 Милый помощник готов к работе!"
            )
            
            # Отправляем уведомление всем администраторам
            for admin_id in config["telegram"]["bot"].get("signed_users", []):
                try:
                    await self.bot.send_message(
                        chat_id=admin_id,
                        text=message,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Не удалось отправить уведомление администратору {admin_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления о запуске: {e}")

    async def log_event(self, text: str, kb: InlineKeyboardMarkup | None = None):
        """
        Логирует событие в чат TG бота.
                
        :param text: Текст лога.
        :type text: `str`
                
        :param kb: Клавиатура с кнопками.
        :type kb: `aiogram.types.InlineKeyboardMarkup` or `None`
        """
        try:
            config = sett.get("config")
            chat_id = config["playerok"]["tg_logging"]["chat_id"]
            if not chat_id:
                signed_users = config["telegram"]["bot"]["signed_users"]
                logger.info(f"Отправка уведомления {len(signed_users)} пользователям: {signed_users}")
                for user_id in signed_users:
                    try:
                        await self.bot.send_message(
                            chat_id=user_id, 
                            text=text, 
                            reply_markup=kb, 
                            parse_mode="HTML"
                        )
                        logger.info(f"Уведомление успешно отправлено пользователю {user_id}")
                    except TelegramForbiddenError:
                        logger.warning(f"Не удалось отправить уведомление пользователю {user_id}: бот заблокирован")
                    except Exception as e:
                        logger.error(f"Ошибка при отправке уведомления пользователю {user_id}: {e}")
            else:
                logger.info(f"Отправка уведомления в чат {chat_id}")
                try:
                    await self.bot.send_message(
                        chat_id=chat_id, 
                        text=f'{text}\n<span class="tg-spoiler">Переключите чат логов на чат с ботом, чтобы отображалась меню с действиями</span>', 
                        reply_markup=None, 
                        parse_mode="HTML"
                    )
                    logger.info(f"Уведомление успешно отправлено в чат {chat_id}")
                except TelegramForbiddenError:
                    logger.warning(f"Не удалось отправить уведомление в чат {chat_id}: бот заблокирован")
                except Exception as e:
                    logger.error(f"Ошибка при отправке уведомления в чат {chat_id}: {e}")
        except Exception as e:
            logger.error(f"Критическая ошибка в log_event: {e}")
