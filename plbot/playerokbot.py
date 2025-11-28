from __future__ import annotations
import asyncio
import time
from datetime import datetime
import time
from threading import Thread
import textwrap
import shutil
from colorama import Fore

from playerokapi.account import Account
from playerokapi import exceptions as plapi_exceptions
from playerokapi.enums import *
from playerokapi.listener.events import *
from playerokapi.listener.listener import EventListener
from playerokapi.types import Chat, Item

from __init__ import ACCENT_COLOR, VERSION, DEVELOPER, REPOSITORY, SECONDARY_COLOR, HIGHLIGHT_COLOR, SUCCESS_COLOR
from core.utils import set_title, shutdown, run_async_in_thread
from core.handlers import add_bot_event_handler, add_playerok_event_handler, call_bot_event, call_playerok_event
from settings import DATA, Settings as sett
from logging import getLogger
from data import Data as data
from tgbot.telegrambot import get_telegram_bot, get_telegram_bot_loop
from tgbot.templates import log_text, log_new_mess_kb, log_new_deal_kb
from tgbot.utils.message_formatter import format_system_message

from .stats import get_stats, set_stats, load_stats


def get_playerok_bot() -> PlayerokBot | None:
    if hasattr(PlayerokBot, "instance"):
        return getattr(PlayerokBot, "instance")


class PlayerokBot:
    def __new__(cls, *args, **kwargs) -> PlayerokBot:
        if not hasattr(cls, "instance"):
            cls.instance = super(PlayerokBot, cls).__new__(cls)
        return getattr(cls, "instance")

    def __init__(self):
        self.logger = getLogger("seal.playerok")

        self.config = sett.get("config")
        self.messages = sett.get("messages")
        self.custom_commands = sett.get("custom_commands")
        self.auto_deliveries = sett.get("auto_deliveries")
        self.auto_restore_items = sett.get("auto_restore_items")

        # Загружаем статистику из файла при инициализации
        load_stats()
        self.stats = get_stats()

        # Инициализация аккаунта происходит здесь
        self.account = self.playerok_account = Account(
            token=self.config["playerok"]["api"]["token"],
            user_agent=self.config["playerok"]["api"]["user_agent"],
            requests_timeout=self.config["playerok"]["api"]["requests_timeout"],
            proxy=self.config["playerok"]["api"]["proxy"] or None
        ).get()
        
        # POST_INIT будет вызван в bot.py после полной инициализации

        self.__saved_chats: dict[str, Chat] = {}
        """Словарь последних запомненных чатов.\nВ формате: {`chat_id` _or_ `username`: `chat_obj`, ...}"""

    def get_chat_by_id(self, chat_id: str) -> Chat:
        """ 
        Получает чат с пользователем из запомненных чатов по его ID.
        Запоминает и получает чат, если он не запомнен.
        
        :param chat_id: ID чата.
        :type chat_id: `str`
        
        :return: Объект чата.
        :rtype: `playerokapi.types.Chat`
        """
        if chat_id in self.__saved_chats:
            return self.__saved_chats[chat_id]
        self.__saved_chats[chat_id] = self.account.get_chat(chat_id)
        return self.get_chat_by_id(chat_id)

    def get_chat_by_username(self, username: str) -> Chat:
        """ 
        Получает чат с пользователем из запомненных чатов по никнейму собеседника.
        Запоминает и получает чат, если он не запомнен.
        
        :param username: Юзернейм собеседника чата.
        :type username: `str`
        
        :return: Объект чата.
        :rtype: `playerokapi.types.Chat`
        """
        if username in self.__saved_chats:
            return self.__saved_chats[username]
        self.__saved_chats[username] = self.account.get_chat_by_username(username)
        return self.get_chat_by_username(username)
    
    def _should_send_greeting(self, chat_id: str, current_message_id: str = None) -> bool:
        """
        Проверяет, нужно ли отправлять приветственное сообщение, 
        анализируя историю чата.
        
        :param chat_id: ID чата.
        :param current_message_id: ID текущего сообщения (исключается из проверки).
        :return: True если нужно отправить приветствие, False если нет.
        """
        import time
        from datetime import datetime
        
        # Проверяем, включены ли приветствия
        first_message_config = self.messages.get("first_message", {})
        if not first_message_config.get("enabled", True):
            return False
        
        # Получаем cooldown в днях
        cooldown_days = first_message_config.get("cooldown_days", 7)
        cooldown_seconds = cooldown_days * 24 * 60 * 60
        
        try:
            # Получаем последние сообщения чата (достаточно небольшого количества)
            messages_list = self.account.get_chat_messages(chat_id, count=10)
            
            if not messages_list or not messages_list.messages:
                # Нет истории - первое сообщение, отправляем приветствие
                return True
            
            # Ищем предыдущее сообщение от пользователя (не от нас и не текущее)
            previous_user_message = None
            for msg in messages_list.messages:
                # Пропускаем текущее сообщение
                if current_message_id and msg.id == current_message_id:
                    continue
                # Ищем сообщение НЕ от нас (от покупателя)
                if msg.user.id != self.account.id:
                    previous_user_message = msg
                    break
            
            if not previous_user_message:
                # Нет предыдущих сообщений от пользователя - отправляем приветствие
                return True
            
            # Проверяем, сколько времени прошло с предыдущего сообщения
            msg_time = previous_user_message.created_at
            if isinstance(msg_time, datetime):
                time_diff = time.time() - msg_time.timestamp()
            else:
                # Если это уже timestamp
                time_diff = time.time() - float(msg_time)
            
            # Если прошло больше cooldown - отправляем приветствие
            return time_diff >= cooldown_seconds
            
        except Exception as e:
            self.logger.warning(f"Ошибка при проверке истории чата для приветствия: {e}")
            # При ошибке лучше не отправлять, чтобы не спамить
            return False
    
    def msg(self, message_name: str, messages_config_name: str = "messages", 
            messages_data: dict = DATA, **kwargs) -> str | None:
        """ 
        Получает отформатированное сообщение из словаря сообщений.

        :param message_name: Наименование сообщения в словаре сообщений (ID).
        :type message_name: `str`

        :param messages_config_name: Имя файла конфигурации сообщений.
        :type messages_config_name: `str`

        :param messages_data: Словарь данных конфигурационных файлов.
        :type messages_data: `dict` or `None`

        :return: Отформатированное сообщение или None, если сообщение выключено.
        :rtype: `str` or `None`
        """
        class Format(dict):
            def __missing__(self, key):
                return "{" + key + "}"

        # Проверяем глобальный переключатель автоответа
        if not self.config["playerok"].get("auto_response_enabled", True):
            return None

        messages = sett.get(messages_config_name, messages_data) or {}
        mess = messages.get(message_name, {})
        if not mess.get("enabled"):
            return None
        message_lines: list[str] = mess.get("text", [])
        if not message_lines:
            self.logger.warning(f"Сообщение {message_name} пустое")
            return None
        try:
            msg = "\n".join([line.format_map(Format(**kwargs)) for line in message_lines])
            return msg
        except Exception as e:
            self.logger.error(f"Не удалось отформатировать сообщение {message_name}: {e}")
            return None
    

    def refresh_account(self):
        """Обновляет данные об аккаунте Playerok."""
        self.account = self.playerok_account = self.account.get()

    def check_banned(self):
        """
        Проверяет, забанен ли аккаунт Playerok.
        Если аккаунт забанен, заканчивает работу бота.
        """
        user = self.account.get_user(self.account.id)
        if user.is_blocked:
            self.logger.critical(f"")
            self.logger.critical(f"{Fore.LIGHTRED_EX}Ваш Playerok аккаунт был заблокирован! К сожалению, я не могу продолжать работу на заблокированном аккаунте...")
            self.logger.critical(f"Напишите в тех. поддержку Playerok, чтобы узнать причину бана и как можно быстрее решить эту проблему.")
            self.logger.critical(f"")
            shutdown()

    def send_message(self, chat_id: str, text: str | None = None, photo_file_path: str | None = None,
                     mark_chat_as_read: bool = None, exclude_watermark: bool = False, max_attempts: int = 3) -> types.ChatMessage:
        """
        Кастомный метод отправки сообщения в чат Playerok.
        Пытается отправить за 3 попытки, если не удалось - выдаёт ошибку в консоль.\n
        Можно отправить текстовое сообщение `text` или фотографию `photo_file_path`.

        :param chat_id: ID чата, в который нужно отправить сообщение.
        :type chat_id: `str`

        :param text: Текст сообщения, _опционально_.
        :type text: `str` or `None`

        :param photo_file_path: Путь к файлу фотографии, _опционально_.
        :type photo_file_path: `str` or `None`

        :param mark_chat_as_read: Пометить чат, как прочитанный перед отправкой, _опционально_.
        :type mark_chat_as_read: `bool`

        :param exclude_watermark: Пропустить и не использовать водяной знак под сообщением?
        :type exclude_watermark: `bool`

        :return: Объект отправленного сообщения.
        :rtype: `PlayerokAPI.types.ChatMessage`
        """
        if not text and not photo_file_path:
            return None
        for _ in range(max_attempts):
            try:
                if (
                    text
                    and self.config["playerok"]["watermark"]["enabled"]
                    and self.config["playerok"]["watermark"]["value"]
                    and not exclude_watermark
                ):
                    text = f"{self.config['playerok']['watermark']['value']}\n\n{text}"
                mark_chat_as_read = (self.config["playerok"]["read_chat"]["enabled"] or False) if mark_chat_as_read is None else mark_chat_as_read
                mess = self.account.send_message(chat_id, text, photo_file_path, mark_chat_as_read)
                return mess
            except plapi_exceptions.RequestFailedError:
                continue
            except Exception as e:
                text = text.replace('\n', '').strip()
                self.logger.error(f"{Fore.LIGHTRED_EX}Ошибка при отправке сообщения {Fore.LIGHTWHITE_EX}«{text}» {Fore.LIGHTRED_EX}в чат {Fore.LIGHTWHITE_EX}{chat_id} {Fore.LIGHTRED_EX}: {Fore.WHITE}{e}")
                return
        text = text.replace('\n', '').strip()
        self.logger.error(f"{Fore.LIGHTRED_EX}Не удалось отправить сообщение {Fore.LIGHTWHITE_EX}«{text}» {Fore.LIGHTRED_EX}в чат {Fore.LIGHTWHITE_EX}{chat_id}")

    def restore_last_sold_item(self, item: Item):
        """ 
        Восстанавливает последний проданный предмет. 
        
        :param item: Объект предмета, который нужно восстановить.
        :type item: `playerokapi.types.Item`
        """
        try:
            profile = self.account.get_user(id=self.account.id)
            items = profile.get_items(count=24, statuses=[ItemStatuses.SOLD]).items
            _item = [profile_item for profile_item in items if profile_item.name == item.name]
            if len(_item) <= 0: return
            try: item: types.MyItem = self.account.get_item(_item[0].id)
            except: item = _item[0]

            priority_statuses = self.account.get_item_priority_statuses(item.id, item.price)
            try: priority_status = [status for status in priority_statuses if status.type is PriorityTypes.DEFAULT or status.price == 0][0]
            except IndexError: priority_status = [status for status in priority_statuses][0]

            new_item = self.account.publish_item(item.id, priority_status.id)
            if new_item.status is ItemStatuses.PENDING_APPROVAL or new_item.status is ItemStatuses.APPROVED:
                self.logger.info(f"{Fore.LIGHTWHITE_EX}«{item.name}» {Fore.WHITE}— {Fore.YELLOW}товар восстановлен")
            else:
                self.logger.error(f"{Fore.LIGHTRED_EX}Не удалось восстановить предмет «{new_item.name}». Его статус: {Fore.WHITE}{new_item.status.name}")
        except Exception as e:
            self.logger.error(f"{Fore.LIGHTRED_EX}При восстановлении предмета «{item.name}» произошла ошибка: {Fore.WHITE}{e}")

    def get_my_items(self, statuses: list[ItemStatuses] | None = None) -> list[types.ItemProfile]:
        """
        Получает все предметы аккаунта.

        :param statuses: Статусы, с которыми нужно получать предметы, _опционально_.
        :type statuses: `list[playerokapi.enums.ItemStatuses]` or `None`

        :return: Массив предметов профиля.
        :rtype: `list` of `playerokapi.types.ItemProfile`
        """
        user = self.account.get_user(self.account.id)
        my_items: list[types.ItemProfile] = []
        next_cursor = None
        while True:
            _items = user.get_items(statuses=statuses, after_cursor=next_cursor)
            for _item in _items.items:
                if _item.id not in [item.id for item in my_items]:
                    my_items.append(_item)
            if not _items.page_info.has_next_page:
                break
            next_cursor = _items.page_info.end_cursor
            time.sleep(0.3)
        return my_items


    def log_new_message(self, message: types.ChatMessage, chat: types.Chat):
        plbot = get_playerok_bot()
        try: chat_user = [user.username for user in chat.users if user.id != plbot.account.id][0]
        except: chat_user = message.user.username
        ch_header = f"💬 Новое сообщение в чате с {chat_user}"
        self.logger.info(f"{ACCENT_COLOR}{ch_header.replace(chat_user, f'{HIGHLIGHT_COLOR}{chat_user}{ACCENT_COLOR}')}")
        self.logger.info(f"{ACCENT_COLOR}│ {Fore.LIGHTWHITE_EX}{message.user.username}:")
        max_width = shutil.get_terminal_size((80, 20)).columns - 40
        longest_line_len = 0
        text = ""
        if message.text is not None: text = message.text
        elif message.file is not None: text = f"{Fore.LIGHTMAGENTA_EX}Изображение {Fore.WHITE}({message.file.url})"
        for raw_line in text.split("\n"):
            if not raw_line.strip():
                self.logger.info(f"{ACCENT_COLOR}│")
                continue
            wrapped_lines = textwrap.wrap(raw_line, width=max_width)
            for wrapped in wrapped_lines:
                self.logger.info(f"{ACCENT_COLOR}│ {Fore.WHITE}{wrapped}")
                longest_line_len = max(longest_line_len, len(wrapped.strip()))
        underline_len = max(len(ch_header)-3, longest_line_len+2)
        self.logger.info(f"{ACCENT_COLOR}└{'─'*underline_len}")

    def log_new_deal(self, deal: types.ItemDeal):
        self.logger.info(f"{ACCENT_COLOR}🌊~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~🌊")
        self.logger.info(f"{ACCENT_COLOR}💰 Новая сделка {HIGHLIGHT_COLOR}{deal.id}")
        self.logger.info(f"{SECONDARY_COLOR} • {Fore.WHITE}Покупатель: {Fore.LIGHTWHITE_EX}{deal.user.username}")
        self.logger.info(f"{SECONDARY_COLOR} • {Fore.WHITE}Товар: {Fore.LIGHTWHITE_EX}{deal.item.name}")
        self.logger.info(f"{SECONDARY_COLOR} • {Fore.WHITE}Сумма: {SUCCESS_COLOR}{deal.item.price}₽")
        self.logger.info(f"{ACCENT_COLOR}🌊~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~🌊")

    def log_new_review(self, deal: types.ItemDeal):
        self.logger.info(f"{ACCENT_COLOR}🌊≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈🌊")
        self.logger.info(f"{ACCENT_COLOR}⭐ Новый отзыв по сделке {HIGHLIGHT_COLOR}{deal.id}")
        self.logger.info(f"{SECONDARY_COLOR} • {Fore.WHITE}Оценка: {Fore.LIGHTYELLOW_EX}{'★' * deal.review.rating or 5} {HIGHLIGHT_COLOR}({deal.review.rating or 5})")
        self.logger.info(f"{SECONDARY_COLOR} • {Fore.WHITE}Текст: {Fore.LIGHTWHITE_EX}{deal.review.text}")
        self.logger.info(f"{SECONDARY_COLOR} • {Fore.WHITE}Оставил: {Fore.LIGHTWHITE_EX}{deal.review.user.username}")
        self.logger.info(f"{SECONDARY_COLOR} • {Fore.WHITE}Дата: {Fore.LIGHTWHITE_EX}{datetime.fromisoformat(deal.review.created_at).strftime('%d.%m.%Y %H:%M:%S')}")
        self.logger.info(f"{ACCENT_COLOR}🌊≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈🌊")

    async def send_new_review_notification(self, deal: types.ItemDeal, chat_id: str):
        """
        Отправляет уведомление о новом отзыве в Telegram.
        Вызывается из системы мониторинга отзывов.
        
        :param deal: Объект сделки с отзывом
        :param chat_id: ID чата
        """
        # Логируем отзыв в консоль
        self.log_new_review(deal)
        
        # Проверяем, включены ли уведомления в Telegram
        if not (
            self.config["playerok"]["tg_logging"]["enabled"] 
            and self.config["playerok"]["tg_logging"].get("events", {}).get("new_review", True)
        ):
            return
        
        # Отправляем уведомление в Telegram
        try:
            from tgbot.templates import log_text, log_new_review_kb
            
            asyncio.run_coroutine_threadsafe(
                get_telegram_bot().log_event(
                    text=log_text(
                        title=f'💬✨ Новый отзыв по <a href="https://playerok.com/deal/{deal.id}">сделке</a>', 
                        text=f"<b>Оценка:</b> {'⭐' * deal.review.rating}\n<b>Оставил:</b> {deal.review.creator.username}\n<b>Текст:</b> {deal.review.text}\n<b>Дата:</b> {datetime.fromisoformat(deal.review.created_at).strftime('%d.%m.%Y %H:%M:%S')}"
                    ),
                    kb=log_new_review_kb(deal.user.username, deal.id, chat_id)
                ), 
                get_telegram_bot_loop()
            )
        except Exception as e:
            self.logger.error(f"Ошибка отправки уведомления о новом отзыве в Telegram: {e}")

    def log_deal_status_changed(self, deal: types.ItemDeal, status_frmtd: str = "Неизвестный"):
        self.logger.info(f"{SECONDARY_COLOR}🌊〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰🌊")
        self.logger.info(f"{SECONDARY_COLOR}🔄 Статус сделки {HIGHLIGHT_COLOR}{deal.id} {SECONDARY_COLOR}изменился")
        self.logger.info(f"{ACCENT_COLOR} • {Fore.WHITE}Статус: {HIGHLIGHT_COLOR}{status_frmtd}")
        self.logger.info(f"{ACCENT_COLOR} • {Fore.WHITE}Покупатель: {Fore.LIGHTWHITE_EX}{deal.user.username}")
        self.logger.info(f"{ACCENT_COLOR} • {Fore.WHITE}Товар: {Fore.LIGHTWHITE_EX}{deal.item.name}")
        self.logger.info(f"{ACCENT_COLOR} • {Fore.WHITE}Сумма: {SUCCESS_COLOR}{deal.item.price}₽")
        self.logger.info(f"{SECONDARY_COLOR}🌊〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰🌊")

    def log_new_problem(self, deal: types.ItemDeal):
        self.logger.info(f"{HIGHLIGHT_COLOR}🆘 🆘 🆘 🆘 🆘 🆘 🆘 🆘 🆘 🆘 🆘 🆘")
        self.logger.info(f"{HIGHLIGHT_COLOR}⚠️ Новая жалоба в сделке {Fore.LIGHTWHITE_EX}{deal.id}")
        self.logger.info(f"{SECONDARY_COLOR} • {Fore.WHITE}Оставил: {Fore.LIGHTWHITE_EX}{deal.user.username}")
        self.logger.info(f"{SECONDARY_COLOR} • {Fore.WHITE}Товар: {Fore.LIGHTWHITE_EX}{deal.item.name}")
        self.logger.info(f"{SECONDARY_COLOR} • {Fore.WHITE}Сумма: {SUCCESS_COLOR}{deal.item.price}₽")
        self.logger.info(f"{HIGHLIGHT_COLOR}🆘 🆘 🆘 🆘 🆘 🆘 🆘 🆘 🆘 🆘 🆘 🆘")


    async def _on_playerok_bot_init(self):
        # Устанавливаем время первого запуска только если его еще нет
        if self.stats.bot_launch_time is None:
            self.stats.bot_launch_time = datetime.now()
            set_stats(self.stats)  # Сохраняем время первого запуска

        def endless_loop():
            while True:
                balance = self.account.profile.balance.value if self.account.profile.balance is not None else "?"
                set_title(f"Seal Playerok Bot v{VERSION} | {self.account.username}: {balance}₽")
                if self.stats != get_stats(): set_stats(self.stats)
                if sett.get("config") != self.config: self.config = sett.get("config")
                if sett.get("messages") != self.messages: self.messages = sett.get("messages")
                if sett.get("custom_commands") != self.custom_commands: self.custom_commands = sett.get("custom_commands")
                if sett.get("auto_deliveries") != self.auto_deliveries: self.auto_deliveries = sett.get("auto_deliveries")
                if sett.get("auto_restore_items") != self.auto_restore_items: self.auto_restore_items = sett.get("auto_restore_items")
                time.sleep(3)

        def refresh_account_loop():
            while True:
                time.sleep(1)
                self.refresh_account()

        def check_banned_loop():
            while True:
                self.check_banned()
                time.sleep(900)

        Thread(target=endless_loop, daemon=True).start()
        Thread(target=refresh_account_loop, daemon=True).start()
        Thread(target=check_banned_loop, daemon=True).start()

    async def _on_new_message(self, event: NewMessageEvent):
        if not event.message.user or not event.message.user.username:
            return
        self.log_new_message(event.message, event.chat)
        if event.message.user.id == self.account.id:
            return

        tg_logging_events = self.config["playerok"]["tg_logging"].get("events", {})
        if (
            self.config["playerok"]["tg_logging"]["enabled"]
            and (tg_logging_events.get("new_user_message", True) 
            or tg_logging_events.get("new_system_message", True))
        ):
            do = False
            is_system_user = event.message.user.username in ["Playerok.com", "Поддержка"]
            
            if tg_logging_events.get("new_user_message", True) and not is_system_user:
                do = True
            if tg_logging_events.get("new_system_message", True) and is_system_user:
                do = True
            
            if do:
                # Проверяем, является ли сообщение системным (оплата, подтверждение и т.д.)
                emoji, formatted_msg = format_system_message(event.message.text, event.message.deal)
                
                if formatted_msg:
                    # Системное сообщение о событии (оплата, подтверждение и т.д.)
                    title_emoji = emoji
                    text = formatted_msg
                else:
                    # Обычное сообщение или сообщение поддержки
                    title_emoji = "🆘" if is_system_user else "💬"
                    user_emoji = "🆘" if is_system_user else "💬"
                    text = f"{user_emoji} <b>{event.message.user.username}:</b> "
                    text += event.message.text or ""
                    text += f'<b><a href="{event.message.file.url}">{event.message.file.filename}</a></b>' if event.message.file else ""
                
                asyncio.run_coroutine_threadsafe(
                    get_telegram_bot().log_event(
                        text=log_text(
                            title=f'{title_emoji} Новое сообщение в <a href="https://playerok.com/chats/{event.chat.id}">чате</a>', 
                            text=text.strip()
                        ),
                        kb=log_new_mess_kb(event.message.user.username, event.chat.id)
                    ), 
                    get_telegram_bot_loop()
                )

        if event.chat.id not in [self.account.system_chat_id, self.account.support_chat_id]:
            # Проверяем, нужно ли отправить приветственное сообщение (по истории чата)
            if self._should_send_greeting(event.chat.id, event.message.id):
                greeting_msg = self.msg("first_message", username=event.message.user.username)
                if greeting_msg:  # Отправляем только если сообщение включено
                    self.send_message(event.chat.id, greeting_msg)
            
            if str(event.message.text).lower() in ["!команды", "!commands"]:
                self.send_message(event.chat.id, self.msg("cmd_commands"))
            elif str(event.message.text).lower() in ["!продавец", "!seller"]:
                asyncio.run_coroutine_threadsafe(
                    get_telegram_bot().call_seller(event.message.user.username, event.chat.id), 
                    get_telegram_bot_loop()
                )
                self.send_message(event.chat.id, self.msg("cmd_seller"))
            elif self.config["playerok"]["custom_commands"]["enabled"]:
                if event.message.text.lower() in [key.lower() for key in self.custom_commands.keys()]:
                    msg = "\n".join(self.custom_commands[event.message.text])
                    self.send_message(event.chat.id, msg)
                    
                    # Отправка уведомления о получении команды
                    if (
                        self.config["playerok"]["tg_logging"]["enabled"]
                        and self.config["playerok"]["tg_logging"]["events"].get("command_received", True)
                    ):
                        asyncio.run_coroutine_threadsafe(
                            get_telegram_bot().log_event(
                                text=log_text(
                                    title=f'⌨️ Получена команда в <a href="https://playerok.com/chats/{event.chat.id}">чате</a>',
                                    text=f"<b>Команда:</b> {event.message.text}\n<b>От пользователя:</b> {event.message.user.username}"
                                )
                            ),
                            get_telegram_bot_loop()
                        )


    async def _on_new_problem(self, event: ItemPaidEvent):
        if event.deal.user.id == self.account.id:
            return

        self.log_new_problem(event.deal)
        if (
            self.config["playerok"]["tg_logging"]["enabled"] 
            and self.config["playerok"]["tg_logging"].get("events", {}).get("new_problem", True)
        ):
            asyncio.run_coroutine_threadsafe(
                get_telegram_bot().log_event(
                    text=log_text(
                        title=f'🤬 Новая жалоба в <a href="https://playerok.com/deal/{event.deal.id}">сделке #{event.deal.id}</a>', 
                        text=f"<b>Покупатель:</b> {event.deal.user.username}\n<b>Предмет:</b> {event.deal.item.name}\n<b>Сумма:</b> {event.deal.item.price or '?'}₽"
                    ),
                    kb=log_new_deal_kb(event.deal.user.username, event.deal.id, event.chat.id)
                ), 
                get_telegram_bot_loop()
            )

    async def _on_new_deal(self, event: NewDealEvent):
        if event.deal.user.id == self.account.id:
            return
        
        self.log_new_deal(event.deal)
        if (
            self.config["playerok"]["tg_logging"]["enabled"] 
            and self.config["playerok"]["tg_logging"].get("events", {}).get("new_deal", True)
        ):
            try:
                tg_bot = get_telegram_bot()
                tg_loop = get_telegram_bot_loop()
                
                if not tg_bot:
                    self.logger.error("Не удалось получить экземпляр Telegram бота для отправки уведомления")
                    return
                
                if not tg_loop:
                    self.logger.error("Не удалось получить event loop Telegram бота для отправки уведомления")
                    return
                
                self.logger.info(f"Отправка уведомления о новой сделке {event.deal.id} в Telegram")
                asyncio.run_coroutine_threadsafe(
                    tg_bot.log_event(
                        text=log_text(
                            title=f'📋 Новая <a href="https://playerok.com/deal/{event.deal.id}">сделка</a>', 
                            text=f"<b>Покупатель:</b> {event.deal.user.username}\n<b>Предмет:</b> {event.deal.item.name}\n<b>Сумма:</b> {event.deal.item.price or '?'}₽"
                        ),
                        kb=log_new_deal_kb(event.deal.user.username, event.deal.id, event.chat.id)
                    ), 
                    tg_loop
                )
            except Exception as e:
                self.logger.error(f"Ошибка при попытке отправить уведомление о новой сделке: {e}")

        self.send_message(event.chat.id, self.msg("new_deal", deal_item_name=event.deal.item.name, deal_item_price=event.deal.item.price))
        if self.config["playerok"]["auto_deliveries"]["enabled"]:
            for auto_delivery in self.auto_deliveries:
                for phrase in auto_delivery["keyphrases"]:
                    if phrase.lower() in event.deal.item.name.lower() or event.deal.item.name.lower() == phrase.lower():
                        self.send_message(event.chat.id, "\n".join(auto_delivery["message"]))
                        
                        # Отправка уведомления об автовыдаче
                        if (
                            self.config["playerok"]["tg_logging"]["enabled"]
                            and self.config["playerok"]["tg_logging"]["events"].get("auto_delivery", True)
                        ):
                            asyncio.run_coroutine_threadsafe(
                                get_telegram_bot().log_event(
                                    text=log_text(
                                        title=f'🚀📦 Выдан товар из автовыдачи в <a href="https://playerok.com/deal/{event.deal.id}">сделке</a>',
                                        text=f"<b>Товар:</b> {event.deal.item.name}\n<b>Покупатель:</b> {event.deal.user.username}\n<b>Сумма:</b> {event.deal.item.price or '?'}₽\n<b>Ключевая фраза:</b> {phrase}"
                                    )
                                ),
                                get_telegram_bot_loop()
                            )
                        break
        if self.config["playerok"]["auto_complete_deals"]["enabled"]:
            self.account.update_deal(event.deal.id, ItemDealStatuses.SENT)

    async def _on_item_paid(self, event: ItemPaidEvent):
        if event.deal.user.id == self.account.id:
            return
        elif not self.config["playerok"]["auto_restore_items"]["enabled"]:
            return
        
        included = False
        excluded = False
        for included_item in self.auto_restore_items["included"]:
            for keyphrases in included_item:
                if any(
                    phrase.lower() in event.deal.item.name.lower() 
                    or event.deal.item.name.lower() == phrase.lower() 
                    for phrase in keyphrases
                ):
                    included = True
                    break
            if included: break
        for excluded_item in self.auto_restore_items["excluded"]:
            for keyphrases in excluded_item:
                if any(
                    phrase.lower() in event.deal.item.name.lower() 
                    or event.deal.item.name.lower() == phrase.lower() 
                    for phrase in keyphrases
                ):
                    excluded = True
                    break
            if excluded: break

        if (
            self.config["playerok"]["auto_restore_items"]["all"]
            and not excluded
        ) or (
            not self.config["playerok"]["auto_restore_items"]["all"]
            and included
        ):
            self.restore_last_sold_item(event.deal.item)
        

    async def _on_deal_status_changed(self, event: DealStatusChangedEvent):
        if event.deal.user.id == self.account.id:
            return
        
        status_frmtd = "Неизвестный"
        if event.deal.status is ItemDealStatuses.PAID: status_frmtd = "Оплачен"
        elif event.deal.status is ItemDealStatuses.PENDING: status_frmtd = "В ожидании отправки"
        elif event.deal.status is ItemDealStatuses.SENT: status_frmtd = "Продавец подтвердил выполнение"
        elif event.deal.status is ItemDealStatuses.CONFIRMED: status_frmtd = "Покупатель подтвердил сделку"
        elif event.deal.status is ItemDealStatuses.ROLLED_BACK: status_frmtd = "Возврат"

        self.log_deal_status_changed(event.deal, status_frmtd)
        if (
            self.config["playerok"]["tg_logging"]["enabled"] 
            and self.config["playerok"]["tg_logging"].get("events", {}).get("deal_status_changed", True)
        ):
            asyncio.run_coroutine_threadsafe(
                get_telegram_bot().log_event(
                    text=log_text(
                        title=f'🔄️📋 Статус <a href="https://playerok.com/deal/{event.deal.id}/">сделки #{event.deal.id}</a> изменился', 
                        text=f"<b>Новый статус:</b> {status_frmtd}\n<b>Товар:</b> {event.deal.item.name}\n<b>Покупатель:</b> {event.deal.user.username}\n<b>Сумма:</b> {event.deal.item.price or '?'}₽"
                    ),
                    kb=log_new_deal_kb(event.deal.user.username, event.deal.id, event.chat.id)
                ), 
                get_telegram_bot_loop()
            )

        if event.deal.status is ItemDealStatuses.PENDING:
            self.send_message(event.chat.id, self.msg("deal_pending", deal_id=event.deal.id, deal_item_name=event.deal.item.name, deal_item_price=event.deal.item.price))
        if event.deal.status is ItemDealStatuses.SENT:
            self.send_message(event.chat.id, self.msg("deal_sent", deal_id=event.deal.id, deal_item_name=event.deal.item.name, deal_item_price=event.deal.item.price))
        if event.deal.status is ItemDealStatuses.CONFIRMED:
            self.send_message(event.chat.id, self.msg("deal_confirmed", deal_id=event.deal.id, deal_item_name=event.deal.item.name, deal_item_price=event.deal.item.price))
            self.stats.deals_completed += 1
            if not event.deal.transaction:
                event.deal = self.account.get_deal(event.deal.id)
            self.stats.earned_money += round(getattr(event.deal.transaction, "value") or 0, 2)
            
            # Добавляем сделку в мониторинг отзывов, если функция включена
            review_config = self.config.get("playerok", {}).get("review_monitoring", {})
            if review_config.get("enabled", False):
                from plbot.review_monitor import add_deal_to_monitor
                add_deal_to_monitor(event.deal, event.chat.id)
                self.logger.info(f"Сделка {event.deal.id} добавлена в мониторинг отзывов")
        elif event.deal.status is ItemDealStatuses.ROLLED_BACK:
            self.send_message(event.chat.id, self.msg("deal_refunded", deal_id=event.deal.id, deal_item_name=event.deal.item.name, deal_item_price=event.deal.item.price))
            # Добавляем сумму возврата
            if not event.deal.transaction:
                event.deal = self.account.get_deal(event.deal.id)
            self.stats.refunded_money += round(getattr(event.deal.transaction, "value") or 0, 2)


    async def run_bot(self):
        self.logger.info(f"{SUCCESS_COLOR}🦭 Милый помощник готов к работе! 🌊")
        self.logger.info("")
        self.logger.info(f"{ACCENT_COLOR}───────────────────────────────────────")
        self.logger.info(f"{ACCENT_COLOR}Seal Playerok Bot v{VERSION}")
        self.logger.info(f" · Разработчик: {Fore.LIGHTWHITE_EX}{DEVELOPER}")
        self.logger.info(f" · GitHub: {Fore.LIGHTWHITE_EX}{REPOSITORY}")
        self.logger.info(f"{ACCENT_COLOR}───────────────────────────────────────")
        self.logger.info("")
        self.logger.info(f"{ACCENT_COLOR}───────────────────────────────────────")
        self.logger.info(f"{ACCENT_COLOR}Информация об аккаунте:")
        self.logger.info(f" · ID: {Fore.LIGHTWHITE_EX}{self.account.id}")
        self.logger.info(f" · Никнейм: {Fore.LIGHTWHITE_EX}{self.account.username}")
        if self.playerok_account.profile.balance:
            self.logger.info(f" · Баланс: {Fore.LIGHTWHITE_EX}{self.account.profile.balance.value}₽")
            self.logger.info(f"   · Доступно: {Fore.LIGHTWHITE_EX}{self.account.profile.balance.available}₽")
            self.logger.info(f"   · В ожидании: {Fore.LIGHTWHITE_EX}{self.account.profile.balance.pending_income}₽")
            self.logger.info(f"   · Заморожено: {Fore.LIGHTWHITE_EX}{self.account.profile.balance.frozen}₽")
        self.logger.info(f" · Активные продажи: {Fore.LIGHTWHITE_EX}{self.account.profile.stats.deals.outgoing.total - self.account.profile.stats.deals.outgoing.finished}")
        self.logger.info(f" · Активные покупки: {Fore.LIGHTWHITE_EX}{self.account.profile.stats.deals.incoming.total - self.account.profile.stats.deals.incoming.finished}")
        self.logger.info(f"{ACCENT_COLOR}───────────────────────────────────────")
        self.logger.info("")
        if self.config["playerok"]["api"]["proxy"]:
            try:
                proxy_str = self.config["playerok"]["api"]["proxy"]
                
                # Удаляем протокол (socks5://, socks4://, http://, https://)
                if "://" in proxy_str:
                    protocol, proxy_str = proxy_str.split("://", 1)
                
                if "@" in proxy_str:
                    # Формат: user:password@host:port
                    auth_part, server_part = proxy_str.split("@", 1)
                    auth_parts = auth_part.split(":", 1)
                    user = auth_parts[0] if len(auth_parts) > 0 else "Без авторизации"
                    password = auth_parts[1] if len(auth_parts) > 1 else "Без авторизации"
                    
                    server_parts = server_part.rsplit(":", 1)
                    ip = server_parts[0] if len(server_parts) > 0 else "unknown"
                    port = server_parts[1] if len(server_parts) > 1 else "unknown"
                else:
                    # Формат: host:port (без авторизации)
                    user = "Без авторизации"
                    password = "Без авторизации"
                    server_parts = proxy_str.rsplit(":", 1)
                    ip = server_parts[0] if len(server_parts) > 0 else "unknown"
                    port = server_parts[1] if len(server_parts) > 1 else "unknown"
                
                # Маскируем IP
                if "." in ip:
                    ip = ".".join([("*" * len(nums)) if i >= 3 else nums for i, nums in enumerate(ip.split("."), start=1)])
                else:
                    ip = f"{ip[:3]}***" if len(ip) > 3 else ip
                
                # Маскируем данные
                port = f"{port[:3]}**" if len(str(port)) > 3 else str(port)
                user = f"{user[:3]}*****" if user != "Без авторизации" and len(user) > 3 else user
                password = f"{password[:3]}*****" if password != "Без авторизации" and len(password) > 3 else password
                
                self.logger.info(f"{ACCENT_COLOR}───────────────────────────────────────")
                self.logger.info(f"{ACCENT_COLOR}Информация о прокси:")
                self.logger.info(f" · IP: {Fore.LIGHTWHITE_EX}{ip}:{port}")
                self.logger.info(f" · Юзер: {Fore.LIGHTWHITE_EX}{user}")
                self.logger.info(f" · Пароль: {Fore.LIGHTWHITE_EX}{password}")
                self.logger.info(f"{ACCENT_COLOR}───────────────────────────────────────")
                self.logger.info("")
            except Exception as e:
                self.logger.warning(f"{Fore.YELLOW}Не удалось распарсить информацию о прокси: {e}")

        add_playerok_event_handler(EventTypes.NEW_MESSAGE, PlayerokBot._on_new_message, 0)
        add_playerok_event_handler(EventTypes.DEAL_HAS_PROBLEM, PlayerokBot._on_new_problem, 0)
        add_playerok_event_handler(EventTypes.NEW_DEAL, PlayerokBot._on_new_deal, 0)
        add_playerok_event_handler(EventTypes.ITEM_PAID, PlayerokBot._on_item_paid, 0)
        add_playerok_event_handler(EventTypes.DEAL_STATUS_CHANGED, PlayerokBot._on_deal_status_changed, 0)

        async def listener_loop():
            listener = EventListener(self.account)
            for event in listener.listen(requests_delay=self.config["playerok"]["api"]["listener_requests_delay"]):
                await call_playerok_event(event.type, [self, event])

        # Запуск фоновой задачи мониторинга отзывов
        async def review_monitor_loop():
            from plbot.review_monitor import check_reviews_task
            await check_reviews_task(
                account=self.account,
                send_message_callback=self.send_message,
                msg_callback=self.msg,
                config=self.config,
                log_new_review_callback=self.send_new_review_notification
            )

        run_async_in_thread(listener_loop)
        run_async_in_thread(review_monitor_loop)
        
        self.logger.info(f"{SUCCESS_COLOR}✅ Фоновые задачи запущены: listener, review_monitor")
        # self.logger.info(f"Слушатель событий запущен")