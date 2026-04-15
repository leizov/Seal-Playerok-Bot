from __future__ import annotations

import time

import asyncio

from datetime import datetime
from html import escape

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
from core.auto_deliveries import AUTO_DELIVERY_KIND_MULTI, match_auto_delivery_keyphrase, normalize_auto_deliveries
from core.utils import set_title, shutdown, run_async_in_thread
from core.handlers import add_bot_event_handler, add_playerok_event_handler, call_bot_event, call_playerok_event
from core.error_stats import get_playerok_connection_health, mark_playerok_startup_fatal_incident
from settings import DATA, Settings as sett
from logging import getLogger
from data import Data as data
from tgbot.telegrambot import get_telegram_bot, get_telegram_bot_loop
from tgbot.templates import log_text, log_new_mess_kb, log_new_deal_kb
from tgbot.utils.message_formatter import format_system_message

from .stats import get_stats, load_stats, record_new_deal, record_raise, record_refund, record_review, set_stats
from .raise_times import (
    cleanup_completed_timings,
    get_msk_now,
    get_raise_times,
    is_timing_completed,
    load_raise_times,
    mark_timing_completed,
    set_last_raise_time,
    set_raise_times,
    should_raise_item,
)
from .auto_reminder import (
    add_deal_to_monitor as add_deal_to_auto_reminder,
    remove_deal_from_monitor as remove_deal_from_auto_reminder,
    check_auto_reminders_task,
)


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
        self.auto_deliveries = normalize_auto_deliveries(sett.get("auto_deliveries") or [])
        self.auto_restore_items = sett.get("auto_restore_items")
        self.auto_raise_items = sett.get("auto_raise_items")
        self.auto_complete_items = sett.get("auto_complete_items")

        load_stats()
        self.stats = get_stats()

        load_raise_times()
        self.raise_times = get_raise_times()

        self.is_connected = False
        self.connection_error = None
        self.account = None
        self.playerok_account = None
        self._listener_task = None
        self._auto_raise_items_task = None
        self._auto_reminder_task = None

        self._try_connect()

        self.__saved_chats: dict[str, Chat] = {}

    def _deal_amount(self, deal: types.ItemDeal) -> float:
        """
        Возвращает сумму сделки по правилу:
        transaction.value -> item.price -> 0.0
        """
        full_deal = deal
        deal_id = getattr(deal, "id", None)

        # Приоритетно пытаемся получить "полную" сделку с transaction.value.
        for attempt in range(1, 6):
            try:
                if self.is_connected and self.account is not None and deal_id:
                    fetched_deal = self.account.get_deal(deal_id)
                    if fetched_deal is not None:
                        full_deal = fetched_deal

                if getattr(full_deal, "transaction", None):
                    val = getattr(full_deal.transaction, "value", None)
                    if val is not None:
                        return round(float(val), 2)
            except Exception as e:
                self.logger.warning(
                    f"Не удалось получить transaction.value для сделки {deal_id} "
                    f"(попытка {attempt}/5): {e}"
                )

            if attempt < 5:
                time.sleep(4)

        try:
            price = getattr(getattr(full_deal, "item", None), "price", None)
            if price is not None:
                return round(float(price), 2)
        except Exception:
            pass

        return 0.0

    def _try_connect(self) -> bool:
        try:
            self.account = Account(
                token=self.config["playerok"]["api"]["token"],
                user_agent=self.config["playerok"]["api"]["user_agent"],
                requests_timeout=self.config["playerok"]["api"]["requests_timeout"],
                proxy=self.config["playerok"]["api"]["proxy"] or None
            ).get()
            self.playerok_account = self.account
            self.is_connected = True
            self.connection_error = None
            proxy_status = "с прокси" if self.config["playerok"]["api"]["proxy"] else "без прокси"
            self.logger.info(f"{Fore.GREEN}✅ Подключено к Playerok ({proxy_status})")
            return True
        except Exception as e:
            self.logger.error(f"{Fore.LIGHTRED_EX}❌ Не удалось подключиться к Playerok: {e}")
            self.connection_error = str(e)
            self.is_connected = False
            self.account = None
            self.playerok_account = None
            return False

    def get_chat_by_id(self, chat_id: str) -> Chat:
        if not self.is_connected or self.account is None:
            return None
        if chat_id in self.__saved_chats:
            return self.__saved_chats[chat_id]
        self.__saved_chats[chat_id] = self.account.get_chat(chat_id)
        return self.__saved_chats[chat_id]

    def get_chat_by_username(self, username: str) -> Chat:
        if not self.is_connected or self.account is None:
            return None
        if username in self.__saved_chats:
            return self.__saved_chats[username]
        self.__saved_chats[username] = self.account.get_chat_by_username(username)
        return self.__saved_chats[username]

    def reconnect(self) -> tuple[bool, str]:
        self.logger.info(f"{Fore.CYAN}🔄 Попытка переподключения к Playerok...")

        self.config = sett.get("config")

        if self._listener_task:
            try:
                self._listener_task.cancel()
            except:
                pass

        if self._auto_raise_items_task:
            try:
                self._auto_raise_items_task.cancel()
            except:
                pass

        if self._auto_reminder_task:
            try:
                self._auto_reminder_task.cancel()
            except:
                pass

        success = self._try_connect()

        if success:
            self._start_listener()
            return True, f"✅ Успешно переподключено к аккаунту {self.account.username}"
        else:
            return False, f"❌ Не удалось переподключиться: {self.connection_error}"

    def _start_listener(self):
        async def listener_loop():
            listener = None
            while True:
                try:
                    if not self.is_connected or self.account is None:
                        restored = self._try_connect()
                        if not restored or self.account is None:
                            await asyncio.sleep(5)
                            continue
                        self.logger.info("✅ Слушатель восстановил подключение к Playerok и продолжает работу")
                        listener = None

                    current_account = self.account
                    if current_account is None:
                        await asyncio.sleep(3)
                        continue

                    if listener is None or listener.account is not current_account:
                        listener = EventListener(current_account)

                    for event in listener.listen(
                        requests_delay=self.config["playerok"]["api"]["listener_requests_delay"]
                    ):
                        await call_playerok_event(event.type, [self, event])
                except Exception as e:
                    self.logger.warning(f"Слушатель событий перезапускается после ошибки: {e}")
                    await asyncio.sleep(3)
                    listener = None

        async def auto_raise_items_loop():
            """Цикл автоподнятия товаров."""

            def _normalize_mode(raw_mode: str | None) -> str:
                mode_value = str(raw_mode or "interval").strip().lower()
                if mode_value not in {"interval", "timing"}:
                    return "interval"
                return mode_value

            def _parse_timing_slots(raw_timings: list[str] | None) -> list[tuple[str, int]]:
                if not isinstance(raw_timings, list):
                    return []
                unique_slots: dict[str, int] = {}
                for raw_timing in raw_timings or []:
                    timing = str(raw_timing or "").strip()
                    parts = timing.split(":")
                    if len(parts) != 2:
                        continue
                    if not parts[0].isdigit() or not parts[1].isdigit():
                        continue
                    hour = int(parts[0])
                    minute = int(parts[1])
                    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                        continue
                    normalized = f"{hour:02d}:{minute:02d}"
                    unique_slots[normalized] = hour * 60 + minute
                return sorted(unique_slots.items(), key=lambda item: item[1])

            while True:
                try:
                    auto_raise_config = self.config["playerok"]["auto_raise_items"]

                    # Проверяем включено ли автоподнятие
                    if not auto_raise_config["enabled"]:
                        await asyncio.sleep(60)
                        continue

                    # Получаем настройки
                    mode = _normalize_mode(auto_raise_config.get("mode"))
                    interval_hours = auto_raise_config.get("interval_hours", 24.0)
                    raise_all = auto_raise_config.get("all", True)
                    current_msk_date = None
                    active_timing_slot = None

                    if mode == "timing":
                        timing_slots = _parse_timing_slots(auto_raise_config.get("timings", []))
                        if not timing_slots:
                            await asyncio.sleep(60)
                            continue

                        now_msk = get_msk_now()
                        current_msk_date = now_msk.strftime("%Y-%m-%d")
                        cleanup_completed_timings(current_msk_date)

                        now_minutes = now_msk.hour * 60 + now_msk.minute
                        active_timing_slot, active_timing_minutes = min(
                            timing_slots,
                            key=lambda slot: abs(now_minutes - slot[1]),
                        )

                        # Проверяем окно +-5 минут относительно ближайшего тайминга.
                        if abs(now_minutes - active_timing_minutes) > 5:
                            await asyncio.sleep(60)
                            continue

                        # Если этот слот уже выполнен сегодня (по МСК), пропускаем.
                        if is_timing_completed(current_msk_date, active_timing_slot):
                            await asyncio.sleep(60)
                            continue

                    # Получаем все активные товары с премиум статусом
                    my_items = self.get_my_items(statuses=[ItemStatuses.APPROVED])
                    for item in my_items:
                        try:
                            # Проверяем что товар имеет премиум статус (priority != None)
                            if not item.priority or item.priority == "DEFAULT":
                                continue

                            # Проверяем включения/исключения
                            item_name_lower = item.name.lower()

                            # Проверяем исключения
                            is_excluded = False
                            for excluded_keyphrases in self.auto_raise_items.get("excluded", []):
                                if any(
                                        phrase.lower() in item_name_lower
                                        or item_name_lower == phrase.lower()
                                        for phrase in excluded_keyphrases
                                ):
                                    is_excluded = True
                                    break

                            if is_excluded:
                                continue

                            # Проверяем включения (если не режим "все")
                            if not raise_all:
                                is_included = False
                                for included_keyphrases in self.auto_raise_items.get("included", []):
                                    if any(
                                            phrase.lower() in item_name_lower
                                            or item_name_lower == phrase.lower()
                                            for phrase in included_keyphrases
                                    ):
                                        is_included = True
                                        break

                                if not is_included:
                                    continue

                            should_raise = mode == "timing" or should_raise_item(item.id, interval_hours)

                            # Проверяем нужно ли поднимать.
                            if should_raise:
                                self.logger.info(f"{Fore.CYAN}🔄 Поднимаю товар «{item.name}»...")
                                self.raise_item(item)

                                # Небольшая задержка между поднятиями
                                await asyncio.sleep(2)

                        except Exception as e:
                            self.logger.error(f"{Fore.LIGHTRED_EX}Ошибка при обработке товара «{item.name}»: {Fore.WHITE}{e}", exc_info=True)

                    if mode == "timing" and active_timing_slot and current_msk_date:
                        mark_timing_completed(current_msk_date, active_timing_slot)

                    # Ждём минуту перед следующей проверкой
                    await asyncio.sleep(60)

                except Exception as e:
                    self.logger.error(f"{Fore.LIGHTRED_EX}Ошибка в цикле автоподнятия товаров: {Fore.WHITE}{e}", exc_info=True)
                    await asyncio.sleep(60)

        async def auto_reminder_loop():
            await check_auto_reminders_task(
                account=self.account,
                send_message_callback=self.send_message,
                get_config_callback=lambda: self.config
            )

        run_async_in_thread(self.playerok_bot_start)
        self._listener_task = run_async_in_thread(listener_loop)
        self._auto_raise_items_task = run_async_in_thread(auto_raise_items_loop)
        self._auto_reminder_task = run_async_in_thread(auto_reminder_loop)

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

                # Проверяем наличие user перед доступом к id
                # (системные сообщения могут не иметь поля user)
                if not msg.user:
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
            elif isinstance(msg_time, str):
                # ISO строка формата '2026-01-26T16:23:22.208Z'
                try:
                    dt = datetime.fromisoformat(msg_time.replace('Z', '+00:00'))
                    time_diff = time.time() - dt.timestamp()
                except:
                    return False
            else:
                # Числовой timestamp
                time_diff = time.time() - float(msg_time)

            # Если прошло больше cooldown - отправляем приветствие
            return time_diff >= cooldown_seconds

        except Exception as e:
            self.logger.warning(f"Ошибка при проверке истории чата для приветствия: {e}")
            # При ошибке лучше не отправлять, чтобы не спамить
            return False

    def _should_send_greeting_with_deal(self, chat_id: str, event: NewDealEvent) -> bool:
        """
        Проверяет, нужно ли отправлять приветственное сообщение при получении новой сделки.

        :param chat_id: ID чата.
        :param event: ивент сделки.
        :return: True если нужно отправить приветствие, False если нет.
        """


        # Проверяем, включены ли приветствия
        first_message_config = self.messages.get("first_message", {})
        if not first_message_config.get("enabled", True):
            return False
        else:
            #todo возможно починить и вренуть логику с кулдауном
            return True

        # Получаем cooldown в днях
        cooldown_days = first_message_config.get("cooldown_days", 7)
        cooldown_seconds = cooldown_days * 24 * 60 * 60

        try:
            # Получаем последние сообщения чата (достаточно небольшого количества)
            messages_list = self.account.get_chat_messages(chat_id, count=10)

            if not messages_list or len(messages_list.messages) <= 1:
                # в чате только увед о сделке
                return True

            # Ищем предыдущее сообщение от пользователя
            for msg in messages_list.messages:
                # Пропускаем текущее сообщение
                msg_time = datetime.fromisoformat(msg.created_at.replace("Z", "+00:00"))
                deal_time = datetime.fromisoformat(event.deal.created_at.replace("Z", "+00:00"))

                if deal_time > msg_time:
                    # мы поймали самое последнее сообщение до сделки
                    time_diff = deal_time - msg_time
                    if time_diff.total_seconds() > cooldown_seconds:
                        return True
                    else:
                        return False
            return True

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
        if not self.is_connected or self.account is None:
            return
        self.account = self.playerok_account = self.account.get()

    def check_banned(self):
        if not self.is_connected or self.account is None:
            return
        user = self.account.get_user(self.account.id)
        if user.is_blocked:
            self.logger.critical(f"")
            self.logger.critical(f"{Fore.LIGHTRED_EX}Ваш Playerok аккаунт был заблокирован! К сожалению, я не могу продолжать работу на заблокированном аккаунте...")
            self.logger.critical(f"Напишите в тех. поддержку Playerok, чтобы узнать причину бана и как можно быстрее решить эту проблему.")
            self.logger.critical(f"")
            shutdown()

    def send_message(self, chat_id: str, text: str | None = None, photo_file_path: str | None = None,
                     mark_chat_as_read: bool = None, exclude_watermark: bool = False, max_attempts: int = 3) -> types.ChatMessage:
        if not self.is_connected or self.account is None:
            return None
        if not text and not photo_file_path:
            return None
        text = text if text else ''
        # Определяем нужно ли помечать чат как прочитанный
        should_mark_as_read = (self.config["playerok"]["read_chat"]["enabled"] or False) if mark_chat_as_read is None else mark_chat_as_read

        # Помечаем чат как прочитанный ПЕРЕД отправкой сообщения (если включено)
        if should_mark_as_read:
            try:
                self.account.mark_chat_as_read(chat_id)
            except Exception as e:
                self.logger.warning(f"Не удалось пометить чат {chat_id} как прочитанный: {e}")

        for ix in range(max_attempts):
            try:
                if (
                    text
                    and self.config["playerok"]["watermark"]["enabled"]
                    and self.config["playerok"]["watermark"]["value"]
                    and not exclude_watermark
                ):
                    text = f"{self.config['playerok']['watermark']['value']}\n\n{text}"
                # Передаем mark_chat_as_read=False т.к. уже пометили выше
                mess = self.account.send_message(chat_id, text, photo_file_path, mark_chat_as_read=False)
                return mess
            except plapi_exceptions.RequestFailedError as e:
                self.logger.error(f'Ошибка при отправке соощения\n{e}\n{ix+1}/{max_attempts} попытка')
                time.sleep(4)
                continue
            except Exception as e:
                text = text.replace('\n', '').strip() if text else 'БЕЗ ТЕКСТА'
                self.logger.error(f"{Fore.LIGHTRED_EX}Ошибка при отправке сообщения {Fore.LIGHTWHITE_EX}«{text}» {Fore.LIGHTRED_EX}в чат {Fore.LIGHTWHITE_EX}{chat_id} {Fore.LIGHTRED_EX}: {Fore.WHITE}{e}")
                return
        text = text.replace('\n', '').strip() if text else "БЕЗ ТЕКСТА"
        self.logger.error(f"{Fore.LIGHTRED_EX}Не удалось отправить сообщение {Fore.LIGHTWHITE_EX}«{text}» {Fore.LIGHTRED_EX}в чат {Fore.LIGHTWHITE_EX}{chat_id}")

    def _is_item_in_restore_scope(self, item_name: str | None) -> bool:
        item_name_lower = str(item_name or "").strip().lower()
        if not item_name_lower:
            return False

        auto_restore_items = self.auto_restore_items if isinstance(self.auto_restore_items, dict) else {}

        included = any(
            any(
                phrase_lower in item_name_lower or item_name_lower == phrase_lower
                for phrase_lower in (
                    str(phrase).strip().lower()
                    for phrase in included_item
                )
                if phrase_lower
            )
            for included_item in auto_restore_items.get("included", [])
            if isinstance(included_item, list)
        )
        excluded = any(
            any(
                phrase_lower in item_name_lower or item_name_lower == phrase_lower
                for phrase_lower in (
                    str(phrase).strip().lower()
                    for phrase in excluded_item
                )
                if phrase_lower
            )
            for excluded_item in auto_restore_items.get("excluded", [])
            if isinstance(excluded_item, list)
        )

        auto_restore_cfg = self.config.get("playerok", {}).get("auto_restore_items", {})
        all_mode = bool(auto_restore_cfg.get("all", True))

        return (all_mode and not excluded) or ((not all_mode) and included)

    def restore_item(self, item: Item | types.MyItem | types.ItemProfile) -> bool:
        if not self.is_connected or self.account is None:
            return False

        item_name = str(getattr(item, "name", "") or "")
        if not self._is_item_in_restore_scope(item_name):
            return False

        try:
            try:
                full_item: types.MyItem = self.account.get_item(item.id)
            except Exception:
                full_item = item

            time.sleep(1)
            item_price = getattr(full_item, "raw_price", None)
            if item_price is None:
                item_price = getattr(full_item, "price", None)
            if item_price is None:
                item_price = 0

            priority_statuses = self.account.get_item_priority_statuses(full_item.id, item_price)
            if not priority_statuses:
                raise Exception("Нету статусов приоритета у предмета!")

            try:
                priority_status = [status for status in priority_statuses if status.type is PriorityTypes.DEFAULT or status.price == 0][0]
            except IndexError:
                priority_status = priority_statuses[0]

            time.sleep(1)
            new_item = self.account.publish_item(full_item.id, priority_status.id)

            if new_item.status is ItemStatuses.PENDING_APPROVAL or new_item.status is ItemStatuses.APPROVED:
                self.logger.info(f"{Fore.LIGHTWHITE_EX}«{item_name or full_item.id}» {Fore.WHITE}— {Fore.YELLOW}товар восстановлен")
                if getattr(priority_status, "price", None) is not None:
                    record_raise(priority_status.price)
                return True

            self.logger.error(
                f"{Fore.LIGHTRED_EX}Не удалось восстановить предмет «{item_name or full_item.id}». "
                f"Его статус: {Fore.WHITE}{new_item.status.name}"
            )
            return False
        except Exception as e:
            self.logger.error(
                f"{Fore.LIGHTRED_EX}При восстановлении предмета «{item_name or getattr(item, 'id', '?')}» "
                f"произошла ошибка: {Fore.WHITE}{e}"
            )
            return False

    def restore_expired_items(self):
        if not self.is_connected or self.account is None:
            return

        try:
            restored_item_ids: set[str] = set()
            expired_items = self.get_my_items(statuses=[ItemStatuses.EXPIRED])

            for item in expired_items:
                item_id = str(getattr(item, "id", "") or "")
                if not item_id or item_id in restored_item_ids:
                    continue

                restored_item_ids.add(item_id)
                self.restore_item(item)
                time.sleep(0.5)
        except Exception as e:
            self.logger.error(f"{Fore.LIGHTRED_EX}Ошибка при восстановлении истёкших предметов: {Fore.WHITE}{e}")

    def restore_last_sold_item(self, item: Item):
        """
        Восстанавливает последний проданный предмет.

        :param item: Объект предмета, который нужно восстановить.
        :type item: `playerokapi.types.Item`
        """
        if not self.is_connected or self.account is None:
            return
        try:
            for i in range(5):
                try:
                    profile = self.account.get_user(id=self.account.id)
                except Exception as e:
                    if i-1 == 5:
                        raise e
                    time.sleep(3)

            attempts = 4
            attempts_delay = 4
            _item = []
            for i in range(attempts):
                items = profile.get_items(count=24, statuses=[ItemStatuses.SOLD]).items
                _item = [profile_item for profile_item in items if profile_item.name == item.name]
                if _item:
                    break
                self.logger.warning(f'Не нашёл товар {item.name} для востановления на нашём аккаунте\nПопытка {i}/{attempts}')
                time.sleep((i+1) * attempts_delay)

            if len(_item) <= 0:
                self.logger.error(f'Не нашёл товар {item.name} для востановления на нашём аккаунте')
                return
            try:
                item: types.MyItem = self.account.get_item(_item[0].id)
            except:
                item = _item[0]


            for i in range(5):
                try:
                    priority_statuses = self.account.get_item_priority_statuses(item.id, item.price)
                except Exception as e:
                    if i-1 == 5:
                        raise e
                    time.sleep(3)

            if not priority_statuses:
                raise Exception('Нету статусов приоритета у предмета!')

            try: priority_status = [status for status in priority_statuses if status.type is PriorityTypes.DEFAULT or status.price == 0][0]
            except IndexError: priority_status = [status for status in priority_statuses][0]

            publish_attempts = 2
            publish_delay = 3
            for i in range(publish_attempts):
                try:
                    new_item = self.account.publish_item(item.id, priority_status.id)
                    if new_item:
                        break
                    time.sleep(publish_delay)
                except Exception as e:
                    self.logger.error(
                        f"{Fore.LIGHTRED_EX}Неудачная попытка востановления предмета {i+1}/{publish_attempts} «{item.name}» произошла ошибка: {Fore.WHITE}{e}")
                    return

            if new_item.status is ItemStatuses.PENDING_APPROVAL or new_item.status is ItemStatuses.APPROVED:
                self.logger.info(f"{Fore.LIGHTWHITE_EX}«{item.name}» {Fore.WHITE}— {Fore.YELLOW}товар восстановлен")
                # Учитываем стоимость автовосстановления (если цена статуса доступна).
                if getattr(priority_status, "price", None) is not None:
                    record_raise(priority_status.price)
            else:
                self.logger.error(f"{Fore.LIGHTRED_EX}Не удалось восстановить предмет «{new_item.name}». Его статус: {Fore.WHITE}{new_item.status.name}")
        except Exception as e:
            self.logger.error(f"{Fore.LIGHTRED_EX}При восстановлении предмета «{item.name}» произошла ошибка: {Fore.WHITE}{e}")

    def raise_item(self, item: types.ItemProfile) -> bool:
        """
        Поднимает товар (повышает приоритет).

        :param item: Объект товара, который нужно поднять.
        :type item: `playerokapi.types.ItemProfile`
        :return: True если поднятие успешно, False если нет.
        :rtype: `bool`
        """
        if not self.is_connected or self.account is None:
            return False

        try:
            # Получаем полный объект товара
            try:
                full_item: types.MyItem = self.account.get_item(item.id)
            except:
                full_item = item

            get_attempts = 5
            get_delay = 3
            last_error = None
            priority_statuses = []
            for attempt in range(get_attempts):
                try:
                    # Получаем статусы приоритета
                    priority_statuses = self.account.get_item_priority_statuses(full_item.id, full_item.price)
                except Exception as e:
                    last_error = e
                    time.sleep(get_delay)

            if not priority_statuses and last_error:
                self.logger.error(
                    f"{Fore.LIGHTRED_EX}Не удалось поднять товар «{full_item.name}» после {get_attempts} попыток")
                set_last_raise_time(full_item.id)
                return False

            # Ищем текущий премиум статус (PriorityTypes.PREMIUM)
            current_priority_status = None
            for status in priority_statuses:
                if status.type == PriorityTypes.PREMIUM:
                    current_priority_status = status
                    break

            if not current_priority_status:
                self.logger.warning(f"{Fore.YELLOW}Не найден премиум статус для товара «{full_item.name}»")
                return False

            # Поднимаем товар
            publish_attempts = 5
            publish_delay = 3
            for attempt in range(publish_attempts):
                try:
                    raised_item = self.account.increase_item_priority_status(
                        full_item.id,
                        current_priority_status.id
                    )

                    if raised_item:
                        self.logger.info(f"{Fore.LIGHTWHITE_EX}«{full_item.name}» {Fore.WHITE}— {Fore.GREEN}товар поднят")
                        # Учитываем стоимость поднятия (если цена статуса доступна).
                        if getattr(current_priority_status, "price", None) is not None:
                            record_raise(current_priority_status.price)

                        # Обновляем время последнего поднятия
                        set_last_raise_time(full_item.id)

                        # Отправляем уведомление в Telegram если включено
                        if (
                            self.config["playerok"]["tg_logging"]["enabled"]
                            and self.config["playerok"]["tg_logging"].get("events", {}).get("item_raised", False)
                        ):
                            asyncio.run_coroutine_threadsafe(
                                get_telegram_bot().log_event(
                                    text=log_text(
                                        title=f'📈 Товар поднят',
                                        text=f"<b>Название:</b> {full_item.name}\n<b>Цена:</b> {full_item.price}₽\n<b>Статус:</b> {current_priority_status.name}"
                                    )
                                ),
                                get_telegram_bot_loop()
                            )

                        return True

                    time.sleep((attempt+1) * publish_delay)

                except Exception as e:
                    self.logger.error(
                        f"{Fore.LIGHTRED_EX}Неудачная попытка поднятия товара {attempt+1}/2 «{full_item.name}»: {Fore.WHITE}{e}",
                        exc_info=True
                    )
                    if attempt != publish_attempts-1:  # Если это не последняя попытка
                        time.sleep((attempt+1) * publish_delay)

            # Если все попытки неудачны - обновляем время чтобы не пытаться снова сразу
            self.logger.error(f"{Fore.LIGHTRED_EX}Не удалось поднять товар «{full_item.name}» после {publish_attempts} попыток")
            set_last_raise_time(full_item.id)
            return False

        except Exception as e:
            self.logger.error(f"{Fore.LIGHTRED_EX}При поднятии товара «{item.name}» произошла ошибка: {Fore.WHITE}{e}", exc_info=True)
            # Обновляем время чтобы не пытаться снова сразу
            set_last_raise_time(item.id)
            return False

    def get_my_items(self, statuses: list[ItemStatuses] | None = None) -> list[types.ItemProfile]:
        """
        Получает все предметы аккаунта.

        :param statuses: Статусы, с которыми нужно получать предметы, _опционально_.
        :type statuses: `list[playerokapi.enums.ItemStatuses]` or `None`

        :return: Массив предметов профиля.
        :rtype: `list` of `playerokapi.types.ItemProfile`
        """
        if not self.is_connected or self.account is None:
            return []
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
        if not plbot or not plbot.is_connected or not plbot.account:
            chat_user = message.user.username
        else:
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
                        title=f'✨ Новый отзыв по <a href="https://playerok.com/deal/{deal.id}">сделке</a>',
                        text=f"<b>Оценка:</b> {'⭐' * deal.review.rating}\n<b>Оставил:</b> {deal.review.creator.username}\n<b>Текст:</b> {deal.review.text}\n<b>Дата:</b> {datetime.fromisoformat(deal.review.created_at).strftime('%d.%m.%Y %H:%M:%S')}"
                    ),
                    kb=log_new_review_kb(deal.user.username, deal.id, chat_id)
                ),
                get_telegram_bot_loop()
            )
        except Exception as e:
            self.logger.error(f"Ошибка отправки уведомления о новом отзыве в Telegram: {e}")

    # old
    def log_deal_status_changed(self, deal: types.ItemDeal, status_frmtd: str = "Неизвестный"):
        self.logger.info(f"{SECONDARY_COLOR}🌊〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰🌊")
        self.logger.info(f"{SECONDARY_COLOR}🔄 Статус сделки {HIGHLIGHT_COLOR}{deal.id} {SECONDARY_COLOR}изменился")
        self.logger.info(f"{ACCENT_COLOR} • {Fore.WHITE}Статус: {HIGHLIGHT_COLOR}{status_frmtd}")
        self.logger.info(f"{ACCENT_COLOR} • {Fore.WHITE}Покупатель: {Fore.LIGHTWHITE_EX}{deal.user.username}")
        self.logger.info(f"{ACCENT_COLOR} • {Fore.WHITE}Товар: {Fore.LIGHTWHITE_EX}{deal.item.name}")
        self.logger.info(f"{ACCENT_COLOR} • {Fore.WHITE}Сумма: {SUCCESS_COLOR}{deal.item.price}₽")
        self.logger.info(f"{SECONDARY_COLOR}🌊〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰🌊")

    def log_deal_confirm(self, deal: types.ItemDeal,):
        self.logger.info(f"{SECONDARY_COLOR}🌊〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰🌊")
        self.logger.info(f"{SECONDARY_COLOR}✅ Покупатель подтвердил сделку {HIGHLIGHT_COLOR}{deal.id}{SECONDARY_COLOR}")
        self.logger.info(f"{ACCENT_COLOR} • {Fore.WHITE}Покупатель: {Fore.LIGHTWHITE_EX}{deal.user.username}")
        self.logger.info(f"{ACCENT_COLOR} • {Fore.WHITE}Товар: {Fore.LIGHTWHITE_EX}{deal.item.name}")
        self.logger.info(f"{ACCENT_COLOR} • {Fore.WHITE}Сумма: {SUCCESS_COLOR}{deal.item.price}₽")
        self.logger.info(f"{SECONDARY_COLOR}🌊〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰🌊")

    def log_deal_rolled_back(self, deal: types.ItemDeal):
        self.logger.info(f"{SECONDARY_COLOR}🌊〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰🌊")
        self.logger.info(f"{SECONDARY_COLOR}❌ Произошёл возврат для сделки {HIGHLIGHT_COLOR}{deal.id}{SECONDARY_COLOR}")
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

    def log_problem_resolved(self, deal: types.ItemDeal):
        self.logger.info(f"{HIGHLIGHT_COLOR}🌊〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰🌊")
        self.logger.info(f"{HIGHLIGHT_COLOR}🥰 Проблема в сделке {Fore.LIGHTWHITE_EX}{deal.id} разрешена!")
        self.logger.info(f"{SECONDARY_COLOR} • {Fore.WHITE}Покупатель: {Fore.LIGHTWHITE_EX}{deal.user.username}")
        self.logger.info(f"{SECONDARY_COLOR} • {Fore.WHITE}Товар: {Fore.LIGHTWHITE_EX}{deal.item.name}")
        self.logger.info(f"{SECONDARY_COLOR} • {Fore.WHITE}Сумма: {SUCCESS_COLOR}{deal.item.price}₽")
        self.logger.info(f"{HIGHLIGHT_COLOR}🌊〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰🌊")

    async def playerok_bot_start(self):
        # Устанавливаем время первого запуска только если его еще нет
        if self.stats.bot_launch_time is None:
            self.stats.bot_launch_time = datetime.now()
            set_stats(self.stats)  # Сохраняем время первого запуска

        def refresh_loop():
            last_token = self.config["playerok"]["api"]["token"]
            last_proxy = self.config["playerok"]["api"]["proxy"]
            last_ua = self.config["playerok"]["api"]["user_agent"]
            last_incident_active = None

            self.logger.info(f'Реврешер запущен!')

            def _safe_int(value, default=0):
                try:
                    return int(value)
                except Exception:
                    return default

            def _health_circles(level: int) -> str:
                normalized = max(1, min(5, _safe_int(level, 5)))
                if normalized >= 5:
                    filled = "\U0001F7E2"  # green
                elif normalized >= 3:
                    filled = "\U0001F7E0"  # orange
                else:
                    filled = "\U0001F534"  # red
                return (filled * normalized) + ("\u26AA" * (5 - normalized))

            def _read_health_snapshot() -> dict:
                try:
                    health = get_playerok_connection_health()
                    if isinstance(health, dict):
                        return health
                except Exception as e:
                    self.logger.debug(f"Не удалось прочитать health-снимок Playerok: {e}")
                return {
                    "window_minutes": 10,
                    "errors_10m": 0,
                    "fatal_streak": 0,
                    "incident_active": False,
                    "level": 5,
                    "circles": _health_circles(5),
                }

            async def _notify_signed_users(text: str) -> None:
                tg_bot = get_telegram_bot()
                if tg_bot is None or not getattr(tg_bot, "bot", None):
                    return

                signed_users = self.config.get("telegram", {}).get("bot", {}).get("signed_users", [])
                if not isinstance(signed_users, list):
                    return

                for user_id in signed_users:
                    try:
                        await tg_bot.bot.send_message(
                            chat_id=user_id,
                            text=text,
                            parse_mode="HTML",
                        )
                    except Exception as e:
                        self.logger.warning(f"Не удалось отправить health-уведомление пользователю {user_id}: {e}")

            def _schedule_signed_users_notification(text: str) -> None:
                loop_obj = get_telegram_bot_loop()
                if loop_obj is None:
                    self.logger.debug("Telegram loop недоступен: пропускаю health-уведомление")
                    return
                try:
                    asyncio.run_coroutine_threadsafe(_notify_signed_users(text), loop_obj)
                except Exception as e:
                    self.logger.error(f"Ошибка при постановке health-уведомления: {e}")

            while True:
                if self.account and self.account.profile.balance:
                    balance = self.account.profile.balance.value
                else:
                    balance = "?"

                username = self.account.username if self.account else "Не подключен"
                set_title(f"Seal Playerok Bot v{VERSION} | {username}: {balance}₽")

                new_config = sett.get("config")
                if new_config != self.config:
                    self.config = new_config

                    token_changed = self.config["playerok"]["api"]["token"] != last_token
                    proxy_changed = self.config["playerok"]["api"]["proxy"] != last_proxy
                    ua_changed = self.config["playerok"]["api"]["user_agent"] != last_ua

                    if token_changed or proxy_changed or ua_changed:
                        self.logger.info(f"{Fore.CYAN}🔄 Обнаружены изменения настроек, переподключаемся...")

                        success, msg = self.reconnect()

                        try:
                            tg_bot = get_telegram_bot()
                            if tg_bot:
                                emoji = "✅" if success else "❌"
                                asyncio.run_coroutine_threadsafe(
                                    tg_bot.log_event(
                                        text=log_text(
                                            title=f"{emoji} Переподключение к Playerok",
                                            text=msg
                                        )
                                    ),
                                    get_telegram_bot_loop()
                                )
                        except Exception as e:
                            self.logger.error(f"Ошибка отправки уведомления: {e}")

                        last_token = self.config["playerok"]["api"]["token"]
                        last_proxy = self.config["playerok"]["api"]["proxy"]
                        last_ua = self.config["playerok"]["api"]["user_agent"]

                if sett.get("messages") != self.messages:
                    self.messages = sett.get("messages")
                if sett.get("custom_commands") != self.custom_commands:
                    self.custom_commands = sett.get("custom_commands")
                new_auto_deliveries = normalize_auto_deliveries(sett.get("auto_deliveries") or [])
                if new_auto_deliveries != self.auto_deliveries:
                    self.auto_deliveries = new_auto_deliveries
                if sett.get("auto_restore_items") != self.auto_restore_items:
                    self.auto_restore_items = sett.get("auto_restore_items")
                if sett.get("auto_raise_items") != self.auto_raise_items:
                    self.auto_raise_items = sett.get("auto_raise_items")
                if sett.get("auto_complete_items") != self.auto_complete_items:
                    self.auto_complete_items = sett.get("auto_complete_items")

                health = _read_health_snapshot()
                incident_active = bool(health.get("incident_active"))
                if last_incident_active is None:
                    last_incident_active = incident_active
                elif not last_incident_active and incident_active:
                    level = max(1, min(5, _safe_int(health.get("level"), 1)))
                    circles = str(health.get("circles") or _health_circles(level))
                    errors_10m = max(0, _safe_int(health.get("errors_10m"), 0))
                    fatal_streak = max(0, _safe_int(health.get("fatal_streak"), 0))
                    window_minutes = max(1, _safe_int(health.get("window_minutes"), 10))

                    alert_text = (
                        "⚠️ <b>Проблемы с подключением к Playerok</b>\n\n"
                        "Бот фиксирует серию фатальных ошибок запросов.\n"
                        "Возможны проблемы на стороне Playerok или с вашим токеном/прокси.\n\n"
                        f"<b>Стабильность за {window_minutes} минут:</b> {escape(circles)} <b>{level}/5</b>\n"
                        f"<b>Ошибки:</b> {errors_10m}\n"
                        f"<b>Фатальный стрик:</b> {fatal_streak}"
                    )
                    _schedule_signed_users_notification(alert_text)
                    last_incident_active = True
                elif last_incident_active and not incident_active:
                    level = max(1, min(5, _safe_int(health.get("level"), 5)))
                    circles = str(health.get("circles") or _health_circles(level))
                    errors_10m = max(0, _safe_int(health.get("errors_10m"), 0))
                    fatal_streak = max(0, _safe_int(health.get("fatal_streak"), 0))
                    window_minutes = max(1, _safe_int(health.get("window_minutes"), 10))

                    alert_text = (
                        "✅ <b>Подключение к Playerok восстановилось</b>\n\n"
                        "Серия фатальных ошибок прервалась, запросы снова проходят.\n\n"
                        f"<b>Стабильность за {window_minutes} минут:</b> {escape(circles)} <b>{level}/5</b>\n"
                        f"<b>Ошибки:</b> {errors_10m}\n"
                        f"<b>Фатальный стрик:</b> {fatal_streak}"
                    )
                    _schedule_signed_users_notification(alert_text)
                    last_incident_active = False

                time.sleep(5)

        def refresh_account_loop():
            while True:
                time.sleep(900)
                self.refresh_account()

        def check_banned_loop():
            while True:
                self.check_banned()
                time.sleep(900)

        def restore_expired_items_loop():
            while True:
                try:
                    auto_restore_cfg = self.config.get("playerok", {}).get("auto_restore_items", {})
                    if bool(auto_restore_cfg.get("expired", False)):
                        self.restore_expired_items()
                except Exception as e:
                    self.logger.error(f"{Fore.LIGHTRED_EX}Ошибка в цикле восстановления истёкших предметов: {Fore.WHITE}{e}")

                time.sleep(45)

        Thread(target=refresh_loop, daemon=True).start()
        Thread(target=refresh_account_loop, daemon=True).start()
        Thread(target=check_banned_loop, daemon=True).start()
        Thread(target=restore_expired_items_loop, daemon=True).start()


    async def _on_new_message(self, event: NewMessageEvent):
        if not self.is_connected or self.account is None:
            return
        if not event.message.user or not event.message.user.username:
            return
        self.log_new_message(event.message, event.chat)
        if event.message.user.id == self.account.id:
            return

        msg_text = event.message.text if event.message.text else ""

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
                emoji, formatted_msg = format_system_message(msg_text, event.message.deal)

                if formatted_msg:
                    # Системное сообщение о событии (оплата, подтверждение и т.д.)
                    title_emoji = emoji
                    text = formatted_msg
                else:
                    # Обычное сообщение или сообщение поддержки
                    title_emoji = "🆘" if is_system_user else "💌"
                    user_emoji = "🆘" if is_system_user else "👤"
                    text = f"{user_emoji} <b>{event.message.user.username}:</b> "
                    text += msg_text
                    text += f'<b><a href="{event.message.file.url}">{event.message.file.filename}</a></b>' if event.message.file else ""

                if event.message.images:
                    for ix, image in enumerate(event.message.images.image_list):
                        text += f'\n<a href="{image.url}">Приложенное фото {ix+1}</a>'

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
            # миграция в new deal обработчик
            # if self._should_send_greeting(event.chat.id, event.message.id):
            #     greeting_msg = self.msg("first_message", username=event.message.user.username)
            #     if greeting_msg:
            #         self.send_message(event.chat.id, greeting_msg)


            if msg_text.lower() in ["!продавец", "!seller"]:
                asyncio.run_coroutine_threadsafe(
                    get_telegram_bot().call_seller(event.message.user.username, event.chat.id),
                    get_telegram_bot_loop()
                )
                self.send_message(event.chat.id, self.msg("cmd_seller"))

            # todo мб сделать возможность регистрации плагинами своих команд
            elif (
                    msg_text.lower() in ["!команды", "!commands"]
                    and self.config["playerok"]["custom_commands"]["enabled"]
            ):
                commands = [command for command in self.custom_commands.keys()]
                commands_row = '!продавец\n' + '\n'.join(commands)
                text = f'⌨️ Список доступных команд:\n<b>{commands_row}</b>'
                self.send_message(event.chat.id, text)


            elif self.config["playerok"]["custom_commands"]["enabled"]:
                command_answer = None
                commands_keys = [key for key in self.custom_commands.keys()]
                for msg_part in msg_text.split():
                    for command_key in commands_keys:
                        if msg_part == command_key or msg_part.lower() == command_key.lower():
                            command_answer = self.custom_commands[command_key]

                if command_answer:
                    msg = "\n".join(command_answer)
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
                                    text=f"<b>🤖 Команда:</b> {msg_text}\n"
                                         f"<b>👤 Пользователь:</b> {event.message.user.username}"
                                )
                            ),
                            get_telegram_bot_loop()
                        )


    async def _on_new_problem(self, event: DealHasProblemEvent):
        if not self.is_connected or self.account is None:
            return
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
                        text=f"<b>👤 Покупатель:</b> {event.deal.user.username}\n"
                             f"<b>📦 Товар:</b> {event.deal.item.name}\n"
                             f"<b>💰 Сумма:</b> {event.deal.item.price or '?'}₽"
                    ),
                    kb=log_new_deal_kb(event.deal.user.username, event.deal.id, event.chat.id)
                ),
                get_telegram_bot_loop()
            )

        self.send_message(
            event.chat.id,
            self.msg(
                "deal_has_problem",
                deal_id=event.deal.id,
                deal_item_name=event.deal.item.name,
                deal_item_price=event.deal.item.price
            )
        )

    async def _on_deal_problem_resolved(self, event: DealProblemResolvedEvent):
        if not self.is_connected or self.account is None:
            return
        if event.deal.user.id == self.account.id:
            return

        self.log_problem_resolved(event.deal)
        if (
                self.config["playerok"]["tg_logging"]["enabled"]
                and self.config["playerok"]["tg_logging"].get("events", {}).get("new_problem", True)
        ):
            asyncio.run_coroutine_threadsafe(
                get_telegram_bot().log_event(
                    text=log_text(
                        title=f'🥰 Проблема <a href="https://playerok.com/deal/{event.deal.id}">сделке #{event.deal.id}</a> разрешена!',
                        text=f"<b>👤 Покупатель:</b> {event.deal.user.username}\n"
                             f"<b>📦 Товар:</b> {event.deal.item.name}\n"
                             f"<b>💰 Сумма:</b> {event.deal.item.price or '?'}₽"
                    ),
                    kb=log_new_deal_kb(event.deal.user.username, event.deal.id, event.chat.id)
                ),
                get_telegram_bot_loop()
            )

        self.send_message(
            event.chat.id,
            self.msg(
                "deal_problem_resolved",
                deal_id=event.deal.id,
                deal_item_name=event.deal.item.name,
                deal_item_price=event.deal.item.price
            )
        )

    async def _on_new_deal(self, event: NewDealEvent):
        if not self.is_connected or self.account is None:
            return
        if event.deal.user.id == self.account.id:
            return

        self.log_new_deal(event.deal)
        record_new_deal(self._deal_amount(event.deal))
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
                            text=f"<b>👤 Покупатель:</b> {event.deal.user.username}\n"
                                 f"<b>📦 Товар:</b> {event.deal.item.name}\n"
                                 f"<b>💰 Сумма:</b> {event.deal.item.price or '?'}₽"
                        ),
                        kb=log_new_deal_kb(event.deal.user.username, event.deal.id, event.chat.id)
                    ),
                    tg_loop
                )
            except Exception as e:
                self.logger.error(f"Ошибка при попытке отправить уведомление о новой сделке: {e}")

        # Проверяем, нужно ли отправить приветственное сообщение (по истории чата)
        if self._should_send_greeting_with_deal(event.chat.id, event):
            greeting_msg = self.msg("first_message", username=event.deal.user.username)
            if greeting_msg:  # Отправляем только если сообщение включено
                self.send_message(event.chat.id, greeting_msg)
                self.logger.info(f'Отправил приветственное сообщение для {event.deal.user.username}')

        if self.config["playerok"]["auto_deliveries"]["enabled"]:
            auto_deliveries = normalize_auto_deliveries(self.auto_deliveries)
            matched_delivery_index = None
            matched_phrase = None

            for idx, auto_delivery in enumerate(auto_deliveries):
                if not auto_delivery.get("enabled", True):
                    continue
                phrase = match_auto_delivery_keyphrase(event.deal.item.name, auto_delivery.get("keyphrases", []))
                if phrase:
                    matched_delivery_index = idx
                    matched_phrase = phrase
                    break

            if matched_delivery_index is not None:
                matched_delivery = auto_deliveries[matched_delivery_index]

                if matched_delivery.get("kind") == AUTO_DELIVERY_KIND_MULTI:
                    items = matched_delivery.get("items", [])

                    if items:
                        issued_item = items.pop(0)
                        matched_delivery["issued_total"] = int(matched_delivery.get("issued_total", 0)) + 1
                        matched_delivery["issued_current_batch"] = int(matched_delivery.get("issued_current_batch", 0)) + 1
                        remaining = len(items)

                        self.auto_deliveries = auto_deliveries
                        sett.set("auto_deliveries", auto_deliveries)

                        self.send_message(event.chat.id, issued_item)
                        self.logger.info(f'Выдал товар из мультивыдачи для {event.deal.id}')

                        if (
                            self.config["playerok"]["tg_logging"]["enabled"]
                            and self.config["playerok"]["tg_logging"].get("events", {}).get("auto_delivery", True)
                        ):
                            safe_issued_item = escape(issued_item)
                            asyncio.run_coroutine_threadsafe(
                                get_telegram_bot().log_event(
                                    text=log_text(
                                        title=f'🚀📦 Выдан товар из мультивыдачи в <a href="https://playerok.com/deal/{event.deal.id}">сделке</a>',
                                        text=(
                                            f"<b>Товар:</b> {event.deal.item.name}\n"
                                            f"<b>Покупатель:</b> {event.deal.user.username}\n"
                                            f"<b>Сумма:</b> {event.deal.item.price or '?'}₽\n"
                                            f"<b>Ключевая фраза:</b> {matched_phrase}\n"
                                            f"<b>Выданная строка:</b> <tg-spoiler>{safe_issued_item}</tg-spoiler>\n"
                                            f"<b>Осталось:</b> {remaining}"
                                        )
                                    )
                                ),
                                get_telegram_bot_loop()
                            )

                        if (
                            remaining == 0
                            and self.config["playerok"]["tg_logging"]["enabled"]
                            and self.config["playerok"]["tg_logging"].get("events", {}).get("auto_delivery", True)
                        ):
                            asyncio.run_coroutine_threadsafe(
                                get_telegram_bot().log_event(
                                    text=log_text(
                                        title=f'⚠️ Последний товар мультивыдачи выдан в <a href="https://playerok.com/deal/{event.deal.id}">сделке</a>',
                                        text=(
                                            f"<b>Товар:</b> {event.deal.item.name}\n"
                                            f"<b>Покупатель:</b> {event.deal.user.username}\n"
                                            f"<b>Ключевая фраза:</b> {matched_phrase}\n"
                                            f"<b>Остаток:</b> 0"
                                        )
                                    )
                                ),
                                get_telegram_bot_loop()
                            )
                    else:
                        out_of_stock_message = "❌ Товар закончился. Напишите продавцу в чат."
                        self.send_message(event.chat.id, out_of_stock_message)
                        self.logger.warning(f'Мультивыдача пуста для сделки {event.deal.id}')

                        if (
                            self.config["playerok"]["tg_logging"]["enabled"]
                            and self.config["playerok"]["tg_logging"].get("events", {}).get("auto_delivery", True)
                        ):
                            asyncio.run_coroutine_threadsafe(
                                get_telegram_bot().log_event(
                                    text=log_text(
                                        title=f'⚠️ Остаток мультивыдачи пуст в <a href="https://playerok.com/deal/{event.deal.id}">сделке</a>',
                                        text=(
                                            f"<b>Товар:</b> {event.deal.item.name}\n"
                                            f"<b>Покупатель:</b> {event.deal.user.username}\n"
                                            f"<b>Ключевая фраза:</b> {matched_phrase}"
                                        )
                                    )
                                ),
                                get_telegram_bot_loop()
                            )
                else:
                    static_message = "\n".join(matched_delivery.get("message", []))
                    if static_message:
                        self.send_message(event.chat.id, static_message)
                    self.logger.info(f'Выдал товар из автовыдачи для {event.deal.id}')

                    if (
                        self.config["playerok"]["tg_logging"]["enabled"]
                        and self.config["playerok"]["tg_logging"].get("events", {}).get("auto_delivery", True)
                    ):
                        asyncio.run_coroutine_threadsafe(
                            get_telegram_bot().log_event(
                                text=log_text(
                                    title=f'🚀📦 Выдан товар из автовыдачи в <a href="https://playerok.com/deal/{event.deal.id}">сделке</a>',
                                    text=(
                                        f"<b>Товар:</b> {event.deal.item.name}\n"
                                        f"<b>Покупатель:</b> {event.deal.user.username}\n"
                                        f"<b>Сумма:</b> {event.deal.item.price or '?'}₽\n"
                                        f"<b>Ключевая фраза:</b> {matched_phrase}"
                                    )
                                )
                            ),
                            get_telegram_bot_loop()
                        )
        auto_complete_config = self.config["playerok"].get("auto_complete_deals", {})
        if auto_complete_config.get("enabled"):
            auto_complete_items = self.auto_complete_items or {}
            should_complete_deal = bool(auto_complete_config.get("all", True))
            item_name_lower = str(getattr(event.deal.item, "name", "") or "").lower()

            is_excluded = False
            for excluded_keyphrases in auto_complete_items.get("excluded", []):
                if not isinstance(excluded_keyphrases, list):
                    continue
                if any(
                    str(phrase).strip().lower() in item_name_lower
                    or item_name_lower == str(phrase).strip().lower()
                    for phrase in excluded_keyphrases
                    if str(phrase).strip()
                ):
                    is_excluded = True
                    break

            if is_excluded:
                should_complete_deal = False
            elif not should_complete_deal:
                for included_keyphrases in auto_complete_items.get("included", []):
                    if not isinstance(included_keyphrases, list):
                        continue
                    if any(
                        str(phrase).strip().lower() in item_name_lower
                        or item_name_lower == str(phrase).strip().lower()
                        for phrase in included_keyphrases
                        if str(phrase).strip()
                    ):
                        should_complete_deal = True
                        break

            if should_complete_deal:
                success = False
                attempts = 3
                delay = 3

                for attempt in range(attempts):
                    try:
                        self.account.update_deal(event.deal.id, ItemDealStatuses.SENT)
                        success = True
                        break
                    except Exception as e:
                        self.logger.warning(f'Неудачная попытка ({attempt+1}/{attempts}) подтвердить сделку {event.deal.id}:\n{e}')
                        time.sleep(delay)

                if success:
                    self.logger.info(f'Автоматически подтвердил сделку {event.deal.id}')
                else:
                    self.logger.error(f'Автоматически подтверждение не сработало {event.deal.id}\nПричина: сайт хуйни')

    async def _on_item_paid(self, event: ItemPaidEvent):
        if not self.is_connected or self.account is None:
            return
        if event.deal.user.id == self.account.id:
            return
        elif not self.config["playerok"]["auto_restore_items"]["enabled"]:
            return

        if self._is_item_in_restore_scope(event.deal.item.name):
            self.restore_last_sold_item(event.deal.item)

    async def _on_item_sent(self, event: ItemSentEvent):
        if not self.is_connected or self.account is None:
            return
        if event.deal.user.id == self.account.id:
            return

        first_message_config = self.messages.get("deal_sent", {})
        if first_message_config.get("enabled", True):
            self.send_message(event.chat.id,
                          self.msg("deal_sent", deal_id=event.deal.id, deal_item_name=event.deal.item.name,
                                   deal_item_price=event.deal.item.price))
            self.logger.info('Отправил сообщение после нашего подтверждения')
        # возьми телефон детка я знаю ты хочешь позвонить
        # if (
        #     self.config["playerok"]["tg_logging"]["enabled"]
        #     and self.config["playerok"]["tg_logging"].get("events", {}).get("deal_status_changed", True)
        # ):
        #     asyncio.run_coroutine_threadsafe(
        #         get_telegram_bot().log_event(
        #             text=log_text(
        #                 title=f'✅ Мы подтвердили заказ <a href="https://playerok.com/deal/{event.deal.id}/">сделки #{event.deal.id}</a>',
        #                 text=f"<b>👤 Покупатель:</b> {event.deal.user.username}\n"
        #                      f"<b>📦 Товар:</b> {event.deal.item.name}\n"
        #                      f"<b>💰 Сумма:</b> {event.deal.item.price or '?'}₽"
        #             ),
        #             kb=log_new_deal_kb(event.deal.user.username, event.deal.id, event.chat.id)
        #         ),
        #         get_telegram_bot_loop()
        #     )

        try:
            auto_reminder_config = self.config.get("playerok", {}).get("auto_reminder", {})
            if auto_reminder_config.get("enabled", False):
                add_deal_to_auto_reminder(event.deal, event.chat.id)
        except Exception as e:
            self.logger.error(f"Не удалось добавить сделку {event.deal.id} в авто-напоминания: {e}")


    async def _on_deal_confirmed(self, event: DealConfirmedEvent):
        if not self.is_connected or self.account is None:
            return
        if event.deal.user.id == self.account.id:
            return

        remove_deal_from_auto_reminder(event.deal.id)

        self.log_deal_confirm(event.deal)
        if (
            self.config["playerok"]["tg_logging"]["enabled"]
            and self.config["playerok"]["tg_logging"].get("events", {}).get("deal_status_changed", True)
        ):
            asyncio.run_coroutine_threadsafe(
                get_telegram_bot().log_event(
                    text=log_text(
                        title=f'✅ Покупатель подтвердил <a href="https://playerok.com/deal/{event.deal.id}/">сделку #{event.deal.id}</a>',
                        text=f"<b>👤 Покупатель:</b> {event.deal.user.username}\n"
                             f"<b>📦 Товар:</b> {event.deal.item.name}\n"
                             f"<b>💰 Сумма:</b> {event.deal.item.price or '?'}₽"
                    ),
                    kb=log_new_deal_kb(event.deal.user.username, event.deal.id, event.chat.id)
                ),
                get_telegram_bot_loop()
            )

        self.send_message(event.chat.id,
                          self.msg("deal_confirmed", deal_id=event.deal.id, deal_item_name=event.deal.item.name,
                                   deal_item_price=event.deal.item.price))

    async def _on_deal_rolled_back(self, event: DealConfirmedEvent):
        if not self.is_connected or self.account is None:
            return
        if event.deal.user.id == self.account.id:
            return

        remove_deal_from_auto_reminder(event.deal.id)

        self.log_deal_rolled_back(event.deal)
        if (
                self.config["playerok"]["tg_logging"]["enabled"]
                and self.config["playerok"]["tg_logging"].get("events", {}).get("deal_status_changed", True)
        ):
            asyncio.run_coroutine_threadsafe(
                get_telegram_bot().log_event(
                    text=log_text(
                        title=f'❌ Произошёл возврат для <a href="https://playerok.com/deal/{event.deal.id}/">сделки #{event.deal.id}</a>',
                        text=f"<b>👤 Покупатель:</b> {event.deal.user.username}\n"
                             f"<b>📦 Товар:</b> {event.deal.item.name}\n"
                             f"<b>💰 Сумма:</b> {event.deal.item.price or '?'}₽"
                    ),
                    kb=log_new_deal_kb(event.deal.user.username, event.deal.id, event.chat.id)
                ),
                get_telegram_bot_loop()
            )

        self.send_message(event.chat.id,
                          self.msg("deal_refunded", deal_id=event.deal.id, deal_item_name=event.deal.item.name,
                                   deal_item_price=event.deal.item.price))
        record_refund(self._deal_amount(event.deal))


    async def _on_deal_confirmed_automatically(self, event: DealConfirmedEvent):
        if not self.is_connected or self.account is None:
            return
        if event.deal.user.id == self.account.id:
            return

        remove_deal_from_auto_reminder(event.deal.id)

        self.log_deal_confirm(event.deal)
        if (
            self.config["playerok"]["tg_logging"]["enabled"]
            and self.config["playerok"]["tg_logging"].get("events", {}).get("deal_status_changed", True)
        ):
            asyncio.run_coroutine_threadsafe(
                get_telegram_bot().log_event(
                    text=log_text(
                        title=f'✅ Автоматически подтверждена сделка <a href="https://playerok.com/deal/{event.deal.id}/">сделку #{event.deal.id}</a>',
                        text=f"<b>👤 Покупатель:</b> {event.deal.user.username}\n"
                             f"<b>📦 Товар:</b> {event.deal.item.name}\n"
                             f"<b>💰 Сумма:</b> {event.deal.item.price or '?'}₽"
                    ),
                    kb=log_new_deal_kb(event.deal.user.username, event.deal.id, event.chat.id)
                ),
                get_telegram_bot_loop()
            )

        self.send_message(event.chat.id,
                          self.msg("deal_confirmed", deal_id=event.deal.id, deal_item_name=event.deal.item.name,
                                   deal_item_price=event.deal.item.price))

    async def _on_new_review(self, event: NewReviewEvent):
        if not self.is_connected or self.account is None:
            return
        if event.deal.user.id == self.account.id:
            return

        await self.send_new_review_notification(event.deal, event.chat.id)

        response_text = self.msg(
            "new_review_response",
            username=event.deal.user.username,
            deal_id=event.deal.id,
            deal_item_name=event.deal.item.name,
            deal_item_price=event.deal.item.price,
        )
        if response_text:
            self.send_message(event.chat.id, response_text)

        record_review()


    #old handler
    async def _on_deal_status_changed(self, event: DealStatusChangedEvent):
        if not self.is_connected or self.account is None:
            return
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
                        title=f'📋 Статус <a href="https://playerok.com/deal/{event.deal.id}/">сделки #{event.deal.id}</a> изменился',
                        text=f"<b>Новый статус:</b> {status_frmtd}\n<b>Товар:</b> {event.deal.item.name}\n<b>Покупатель:</b> {event.deal.user.username}\n<b>Сумма:</b> {event.deal.item.price or '?'}₽"
                    ),
                    kb=log_new_deal_kb(event.deal.user.username, event.deal.id, event.chat.id)
                ),
                get_telegram_bot_loop()
            )

        # if event.deal.status is ItemDealStatuses.PENDING:
        #     self.send_message(event.chat.id, self.msg("deal_pending", deal_id=event.deal.id, deal_item_name=event.deal.item.name, deal_item_price=event.deal.item.price))
        # if event.deal.status is ItemDealStatuses.SENT:
        #     self.send_message(event.chat.id, self.msg("deal_sent", deal_id=event.deal.id, deal_item_name=event.deal.item.name, deal_item_price=event.deal.item.price))
        if event.deal.status is ItemDealStatuses.CONFIRMED:
            self.send_message(event.chat.id, self.msg("deal_confirmed", deal_id=event.deal.id, deal_item_name=event.deal.item.name, deal_item_price=event.deal.item.price))
        elif event.deal.status is ItemDealStatuses.ROLLED_BACK:
            self.send_message(event.chat.id, self.msg("deal_refunded", deal_id=event.deal.id, deal_item_name=event.deal.item.name, deal_item_price=event.deal.item.price))



    async def run_bot(self):
        started_in_recovery_mode = False

        if not self.is_connected or self.account is None or self.playerok_account is None:
            started_in_recovery_mode = True
            self.logger.warning(f"{Fore.YELLOW}⚠️ Не удалось подключиться к Playerok аккаунту при запуске")
            self.logger.warning(f"{Fore.YELLOW}⚠️ Запускаю слушатель в режиме восстановления")
            self.logger.warning(f"{Fore.YELLOW}⚠️ После восстановления доступа события начнут обрабатываться автоматически")

            try:
                mark_playerok_startup_fatal_incident()
            except Exception as e:
                self.logger.debug(f"Не удалось установить стартовый фатальный маркер health: {e}")

            try:
                tg_bot = get_telegram_bot()
                if tg_bot:
                    asyncio.run_coroutine_threadsafe(
                        tg_bot.log_event(
                            text=log_text(
                                title="⚠️ Бот запущен, но Playerok пока недоступен",
                                text=(
                                    "Не удалось подключиться к Playerok аккаунту на старте.\n"
                                    "Слушатель запущен в режиме восстановления и будет продолжать попытки подключения.\n"
                                    "После восстановления доступности Playerok/токена работа продолжится автоматически.\n"
                                    "Когда подключение будет восстановлено, вам придёт уведомление.\n\n"
                                    "Проверьте текущий статус командой:\n"
                                    "/playerok_status\n\n"
                                    "Проверьте токен/прокси/user-agent в:\n"
                                    "⚙️ Настройки → 🔑 Аккаунт"
                                ),
                            )
                        ),
                        get_telegram_bot_loop(),
                    )
            except Exception:
                pass
        else:
            self.logger.info(f"{ACCENT_COLOR}───────────────────────────────────────")
            self.logger.info(f"{ACCENT_COLOR}Информация об аккаунте:")
            self.logger.info(f" · ID: {Fore.LIGHTWHITE_EX}{self.account.id}")
            self.logger.info(f" · Никнейм: {Fore.LIGHTWHITE_EX}{self.account.username}")
            if self.playerok_account.profile.balance:
                self.logger.info(f" · Баланс: {Fore.LIGHTWHITE_EX}{self.account.profile.balance.value}₽")
                self.logger.info(f"   · Доступно: {Fore.LIGHTWHITE_EX}{self.account.profile.balance.available}₽")
                self.logger.info(f"   · В ожидании: {Fore.LIGHTWHITE_EX}{self.account.profile.balance.pending_income}₽")
                self.logger.info(f"   · Заморожено: {Fore.LIGHTWHITE_EX}{self.account.profile.balance.frozen}₽")
            self.logger.info(
                f" · Активные продажи: {Fore.LIGHTWHITE_EX}"
                f"{self.account.profile.stats.deals.outgoing.total - self.account.profile.stats.deals.outgoing.finished}"
            )
            self.logger.info(
                f" · Активные покупки: {Fore.LIGHTWHITE_EX}"
                f"{self.account.profile.stats.deals.incoming.total - self.account.profile.stats.deals.incoming.finished}"
            )
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
        add_playerok_event_handler(EventTypes.NEW_REVIEW, PlayerokBot._on_new_review, 0)
        add_playerok_event_handler(EventTypes.ITEM_PAID, PlayerokBot._on_item_paid, 0)
        # add_playerok_event_handler(EventTypes.DEAL_STATUS_CHANGED, PlayerokBot._on_deal_status_changed, 0)
        add_playerok_event_handler(EventTypes.DEAL_CONFIRMED, PlayerokBot._on_deal_confirmed, 0)
        add_playerok_event_handler(EventTypes.DEAL_ROLLED_BACK, PlayerokBot._on_deal_rolled_back, 0)
        add_playerok_event_handler(EventTypes.DEAL_PROBLEM_RESOLVED, PlayerokBot._on_deal_problem_resolved, 0)
        add_playerok_event_handler(EventTypes.ITEM_SENT, PlayerokBot._on_item_sent, 0)
        add_playerok_event_handler(EventTypes.DEAL_CONFIRMED_AUTOMATICALLY, PlayerokBot._on_deal_confirmed_automatically, 0)

        self._start_listener()

        if started_in_recovery_mode:
            self.logger.warning(f"{Fore.YELLOW}⚠️ Фоновые задачи запущены в режиме восстановления: listener")
        else:
            self.logger.info(f"{SUCCESS_COLOR}✅ Фоновые задачи запущены: listener")
