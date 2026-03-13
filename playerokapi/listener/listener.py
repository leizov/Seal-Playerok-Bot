from typing import Generator
from logging import getLogger
from datetime import datetime, timezone
import asyncio
import time
import traceback
import threading
import queue

from ..account import Account
from ..types import ChatList, ChatMessage, Chat
from .events import *


class EventListener:
    """
    Слушатель событий с Playerok.com.

    :param account: Объект аккаунта.
    :type account: `playerokapi.account.Account`
    """

    def __init__(self, account: Account):
        self.account: Account = account
        """ Объект аккаунта. """

        self.__logger = getLogger("playerokapi.listener")
        self.__last_message_times: dict[str, str] = {} # {chat_id: last_processed_message_created_at}
        self.__last_message_ids: dict[str, str] = {} # {chat_id: last_processed_message_id}
        self.__startup_time: str | None = None # Время запуска текущей сессии (ISO 8601)
        self.__state_lock = threading.Lock()
        self.__pending_new_deal_chats: set[str] = set()
        self.__deal_search_queue: queue.Queue[Chat] = queue.Queue()
        self.__async_events_queue: queue.Queue[list] = queue.Queue()
        self.__deal_search_worker: threading.Thread | None = None
        self.__stop_worker = threading.Event()

    def _get_last_message_id(self, chat_id: str) -> str | None:
        with self.__state_lock:
            return self.__last_message_ids.get(chat_id)

    def _get_last_message_time(self, chat_id: str) -> str | None:
        with self.__state_lock:
            return self.__last_message_times.get(chat_id)

    def _set_last_message_checkpoint(self, chat_id: str, message_id: str | None, created_at: str | None):
        with self.__state_lock:
            if message_id:
                self.__last_message_ids[chat_id] = message_id
            if created_at:
                self.__last_message_times[chat_id] = created_at

    def _is_pending_new_chat(self, chat_id: str) -> bool:
        with self.__state_lock:
            return chat_id in self.__pending_new_deal_chats

    def _enqueue_new_chat_search(self, chat: Chat) -> bool:
        with self.__state_lock:
            if chat.id in self.__pending_new_deal_chats:
                return False
            self.__pending_new_deal_chats.add(chat.id)
        self.__deal_search_queue.put(chat)
        return True

    def _finish_pending_new_chat(self, chat_id: str):
        with self.__state_lock:
            self.__pending_new_deal_chats.discard(chat_id)

    def _start_workers(self):
        if self.__deal_search_worker and self.__deal_search_worker.is_alive():
            return
        self.__stop_worker.clear()
        self.__deal_search_worker = threading.Thread(
            target=self._deal_search_worker_loop,
            daemon=True,
            name="playerok-deal-search-worker",
        )
        self.__deal_search_worker.start()

    def _stop_workers(self):
        self.__stop_worker.set()

    def _deal_search_worker_loop(self):
        while not self.__stop_worker.is_set():
            try:
                chat = self.__deal_search_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            chat_id = chat.id
            try:
                attempts = 3
                delay = 4
                has_new_deal = False
                new_msgs: list[ChatMessage] = []
                msg_list = None

                for attempt in range(1, attempts + 1):
                    msg_list = self.account.get_chat_messages(chat_id, 24)
                    current_msgs = []
                    for msg in msg_list.messages:
                        # В фоне также фильтруем сообщения до старта сессии.
                        if self.__startup_time and msg.created_at < self.__startup_time:
                            continue

                        if msg.text == "{{ITEM_PAID}}" and msg.deal is not None:
                            has_new_deal = True
                            self.__logger.info(
                                f'Для нахождения сделки {msg.deal.id} пришлось произвести повторный поиск'
                                f', задержка слушателя - {4 + (attempt - 1) * (delay + 1)} секунд'
                            )
                        current_msgs.append(msg)

                    new_msgs = current_msgs
                    if has_new_deal:
                        break

                    if attempt < attempts:
                        self.__logger.debug(
                            f'Не удалось найти сделку для нового чата {chat_id}. Попытка {attempt}/{attempts}'
                        )
                        time.sleep(delay)

                if not has_new_deal:
                    self.__logger.error(f'Не удалось найти сделку для нового чата, id: {chat_id}')

                events = []
                for msg in reversed(new_msgs):
                    events.extend(self.parse_message_event(msg, chat))
                if events:
                    self.__async_events_queue.put(events)

                if msg_list and msg_list.messages:
                    latest_msg = msg_list.messages[0]
                    self._set_last_message_checkpoint(chat_id, latest_msg.id, latest_msg.created_at)
                elif chat.last_message:
                    self._set_last_message_checkpoint(chat_id, chat.last_message.id, chat.last_message.created_at)
            except Exception as e:
                self.__logger.warning(f'Ошибка фонового поиска сделки для чата {chat_id}: {e}')
                self.__logger.debug(f"Traceback ошибки в worker:\n{traceback.format_exc()}")
            finally:
                self._finish_pending_new_chat(chat_id)
                self.__deal_search_queue.task_done()

    def _drain_async_events(self) -> list:
        events = []
        while True:
            try:
                events_batch = self.__async_events_queue.get_nowait()
                events.extend(events_batch)
            except queue.Empty:
                break
        return events


    def parse_chat_event(
        self, chat: Chat
    ) -> list[ChatInitializedEvent]:
        """
        Получает ивент с чата.

        :param chat: Объект чата.
        :type chat: `playerokapi.types.Chat`

        :return: Массив ивентов.
        :rtype: `list` of
        `playerokapi.listener.events.ChatInitializedEvent`
        """

        if chat:
            return [ChatInitializedEvent(chat)]
        return []

    def initialize_chats(
        self, chats: ChatList
    ) -> list[ChatInitializedEvent]:
        """
        Инициализирует чаты при первой загрузке.

        :param chats: Страница чатов.
        :type chats: `playerokapi.types.ChatList`

        :return: Массив ивентов инициализации чатов.
        :rtype: `list` of
        `playerokapi.listener.events.ChatInitializedEvent`
        """

        events = []
        for chat in chats.chats:
            this_events = self.parse_chat_event(chat=chat)
            for event in this_events:
                events.append(event)
        return events

    def _bootstrap_checkpoints_from_chats(self, chats: ChatList):
        """
        Заполняет checkpoints по last_message из get_chats на первом проходе.
        Это позволяет не делать лишний догон всех чатов сразу после инициализации.
        """
        filled = 0
        for chat in chats.chats:
            if not chat or not chat.last_message:
                continue
            self._set_last_message_checkpoint(
                chat.id,
                chat.last_message.id,
                chat.last_message.created_at
            )
            filled += 1
        self.__logger.debug(f"Инициализировано checkpoint'ов чатов: {filled}")

    def parse_message_event(
            self, message: ChatMessage, chat: Chat
    ) -> list[
        NewMessageEvent
        | NewDealEvent
        | ItemPaidEvent
        | ItemSentEvent
        | DealConfirmedEvent
        | DealRolledBackEvent
        | DealHasProblemEvent
        | DealProblemResolvedEvent
        | DealStatusChangedEvent
        | DealConfirmedAutomatically
    ]:
        """
        Получает ивент с сообщения.

        :param message: Объект сообщения.
        :type message: `playerokapi.types.ChatMessage`

        :return: Массив ивентов.
        :rtype: `list` of
        `playerokapi.listener.events.ChatInitializedEvent` \
        _or_ `playerokapi.listener.events.NewMessageEvent` \
        _or_ `playerokapi.listener.events.NewDealEvent` \
        _or_ `playerokapi.listener.events.ItemPaidEvent` \
        _or_ `playerokapi.listener.events.ItemSentEvent` \
        _or_ `playerokapi.listener.events.DealConfirmedEvent` \
        _or_ `playerokapi.listener.events.DealRolledBackEvent` \
        _or_ `playerokapi.listener.events.DealHasProblemEvent` \
        _or_ `playerokapi.listener.events.DealProblemResolvedEvent` \
        _or_ `playerokapi.listener.events.DealStatusChangedEvent(message.deal)`
        """

        if not message:
            return []
        if message.text == "{{ITEM_PAID}}" and message.deal is not None:
            return [NewDealEvent(message.deal, chat), ItemPaidEvent(message.deal, chat)]
        elif message.text == "{{ITEM_SENT}}" and message.deal is not None:
            return [ItemSentEvent(message.deal, chat)]
        elif message.text == "{{DEAL_CONFIRMED}}" and message.deal is not None:
            return [
                DealConfirmedEvent(message.deal, chat),
                # DealStatusChangedEvent(message.deal, chat),
            ]
        elif message.text == "{{DEAL_ROLLED_BACK}}" and message.deal is not None:
            return [
                DealRolledBackEvent(message.deal, chat),
                # DealStatusChangedEvent(message.deal, chat),
            ]
        elif message.text == "{{DEAL_HAS_PROBLEM}}" and message.deal is not None:
            return [
                DealHasProblemEvent(message.deal, chat),
                # DealStatusChangedEvent(message.deal, chat),
            ]
        elif message.text == "{{DEAL_PROBLEM_RESOLVED}}" and message.deal is not None:
            return [
                DealProblemResolvedEvent(message.deal, chat),
                # DealStatusChangedEvent(message.deal, chat),
            ]
        elif message.text == "{{DEAL_CONFIRMED_AUTOMATICALLY}}" and message.deal is not None:
            return [
                DealConfirmedAutomatically(message.deal, chat),
            ]

        return [NewMessageEvent(message, chat)]

    def get_message_events(
        self, new_chats: ChatList
    ) -> list[
        NewMessageEvent
        | NewDealEvent
        | ItemPaidEvent
        | ItemSentEvent
        | DealConfirmedEvent
        | DealRolledBackEvent
        | DealHasProblemEvent
        | DealProblemResolvedEvent
        | DealStatusChangedEvent
        | DealConfirmedAutomatically
    ]:
        """
        Получает новые ивенты сообщений из чатов.

        :param new_chats: Чаты для проверки.
        :type new_chats: `playerokapi.types.ChatList`

        :return: Массив новых ивентов.
        :rtype: `list` of
        `playerokapi.listener.events.ChatInitializedEvent` \
        _or_ `playerokapi.listener.events.NewMessageEvent` \
        _or_ `playerokapi.listener.events.NewDealEvent` \
        _or_ `playerokapi.listener.events.ItemPaidEvent` \
        _or_ `playerokapi.listener.events.ItemSentEvent` \
        _or_ `playerokapi.listener.events.DealConfirmedEvent` \
        _or_ `playerokapi.listener.events.DealRolledBackEvent` \
        _or_ `playerokapi.listener.events.DealHasProblemEvent` \
        _or_ `playerokapi.listener.events.DealProblemResolvedEvent` \
        _or_ `playerokapi.listener.events.DealStatusChangedEvent(message.deal)`
        """

        events = []

        for new_chat in new_chats.chats:
            try:
                if not new_chat.last_message:
                    # self.__logger.info(f'Пропускаю чат {new_chat.id} - нет last_message')
                    continue

                # Получаем ID последнего обработанного сообщения для этого чата
                last_msg = new_chat.last_message
                last_known_id = self._get_last_message_id(new_chat.id)
                # если чат не изменился
                if last_msg.id == last_known_id:
                    continue

                if self._is_pending_new_chat(new_chat.id):
                    # Для новых чатов с фоновой ретрай-обработкой пропускаем цикл.
                    continue

                # Если это новый чат (нет сохраненного ID)
                if not last_known_id:
                    # Получаем всю историю сообщений для нового чата

                    msg_list = self.account.get_chat_messages(new_chat.id, 24)
                    new_msgs = []

                    is_old_chat = False
                    has_new_deal = False

                    for msg in msg_list.messages:
                        if self.__startup_time and msg.created_at < self.__startup_time:
                            # пропускаем сообщения до запуска и маркируем чат как старый
                            is_old_chat = True
                            continue

                        if msg.text == "{{ITEM_PAID}}" and msg.deal is not None:
                            has_new_deal = True

                        new_msgs.append(msg)

                    if not is_old_chat and not has_new_deal:
                        # Переносим ретраи в фон, чтобы не блокировать основной polling-цикл.
                        if self._enqueue_new_chat_search(new_chat):
                            self.__logger.info(
                                f'Поймал абсолютно новый чат без сделки, отправляю в фоновый ретрай: {new_chat.id}'
                            )
                        continue

                    # Обрабатываем в хронологическом порядке (от старых к новым)
                    for msg in reversed(new_msgs):
                        events.extend(self.parse_message_event(msg, new_chat))

                    # Сохраняем ID и время для будущих проверок
                    self._set_last_message_checkpoint(
                        new_chat.id,
                        new_chat.last_message.id,
                        new_chat.last_message.created_at
                    )

                    continue

                # Оптимизация: если ID последнего сообщения не изменился - пропускаем
                if new_chat.last_message.id == last_known_id:
                    continue

                # Получаем историю сообщений для существующего чата
                try:
                    msg_list = self.account.get_chat_messages(new_chat.id, 24)
                except Exception as e:
                    self.__logger.warning(f"Ошибка при получении чата: {e}\n(чат будет обработан при следующем запросе)")
                    last_traceback = traceback.format_exc()
                    self.__logger.debug(f"Traceback ошибки в listener:\n{last_traceback}")
                    continue
                new_msgs = []

                # Получаем время последнего обработанного сообщения для дополнительной фильтрации
                last_known_time = self._get_last_message_time(new_chat.id)

                for msg in msg_list.messages:
                    # Основная проверка: по сохраненному ID
                    if msg.id == last_known_id:
                        break
                    # Дополнительная проверка по времени (защита от рассинхронизации)
                    if last_known_time and msg.created_at < last_known_time:
                        break
                    new_msgs.append(msg)

                # Обрабатываем новые сообщения в хронологическом порядке
                for msg in reversed(new_msgs):
                    # Пропускаем сообщения, созданные до запуска бота
                    if self.__startup_time and msg.created_at < self.__startup_time:
                        self.__logger.debug(
                            f"Чат {new_chat.id}: пропуск сообщения {msg.id}, "
                            f"созданного до первого запуска ({msg.created_at} < {self.__startup_time})"
                        )
                        continue

                    events.extend(self.parse_message_event(msg, new_chat))

                # Обновляем ID и время последнего обработанного сообщения
                if new_msgs:
                    latest_msg = new_msgs[0]
                    self._set_last_message_checkpoint(new_chat.id, latest_msg.id, latest_msg.created_at)

                    self.__logger.debug(
                        f"Чат {new_chat.id}: обработано {len(new_msgs)} сообщений, "
                        f"последнее время={latest_msg.created_at}, id={latest_msg.id}"
                    )
            except Exception as e:
                self.__logger.warning(f"Ошибка при получении чата: {e}\n(чат будет обработан при следующем запросе)")
                last_traceback = traceback.format_exc()
                self.__logger.debug(f"Traceback ошибки в listener:\n{last_traceback}")
                continue

        return events

    def listen(
        self, requests_delay: int | float = 4
    ) -> Generator[
        ChatInitializedEvent
        | NewMessageEvent
        | NewDealEvent
        | ItemPaidEvent
        | ItemSentEvent
        | DealConfirmedEvent
        | DealRolledBackEvent
        | DealHasProblemEvent
        | DealProblemResolvedEvent
        | DealConfirmedAutomatically
        | DealStatusChangedEvent,
        None,
        None,
    ]:
        """
        "Слушает" события в чатах.
        Бесконечно отправляет запросы, узнавая новые события из чатов.

        :param requests_delay: Периодичность отправления запросов (в секундах).
        :type requests_delay: `int` or `float`

        :return: Полученный ивент.
        :rtype: `Generator` of
        `playerokapi.listener.events.ChatInitializedEvent` \
        _or_ `playerokapi.listener.events.NewMessageEvent` \
        _or_ `playerokapi.listener.events.NewDealEvent` \
        _or_ `playerokapi.listener.events.ItemPaidEvent` \
        _or_ `playerokapi.listener.events.ItemSentEvent` \
        _or_ `playerokapi.listener.events.DealConfirmedEvent` \
        _or_ `playerokapi.listener.events.DealRolledBackEvent` \
        _or_ `playerokapi.listener.events.DealHasProblemEvent` \
        _or_ `playerokapi.listener.events.DealProblemResolvedEvent` \
        _or_ `playerokapi.listener.events.DealStatusChangedEvent(message.deal)`
        """



        # self.__logger.info(f"Слушатель событий запущен. Время старта: {self.__startup_time}")
        # self.__logger.info(f"При первом проходе события будут сохранены, но не обработаны")

        init_chats: ChatList | None = None
        last_errors_count = 0
        try:
            # Устанавливаем время запуска текущей сессии
            self.__startup_time = datetime.now(timezone.utc).isoformat()
            self.__logger.info(f'Время запуска слушателя событий: {self.__startup_time} ')
            self._start_workers()
            while True:
                try:

                    if last_errors_count >= 3:
                        error_delay = (last_errors_count - 2) * 10
                        error_log = f'Мы попали под шквал ошибок, ставлю слушатель на паузу на {error_delay} секунд'
                        if last_errors_count > 7:
                            error_log += '\n Проверь токен аккаунта и прокси, попробуй перезагрузить бота'
                        self.__logger.warning(error_log)
                        time.sleep(error_delay)

                    next_chats = self.account.get_chats(24)
                    if not init_chats:
                        # Первый запуск - инициализируем чаты
                        events = self.initialize_chats(next_chats)
                        self._bootstrap_checkpoints_from_chats(next_chats)
                        for event in events:
                            yield event
                        # self.__logger.info(
                        #     f"Инициализация завершена. Обнаружено {len(next_chats.chats)} чатов. "
                        #     f"Далее будут обрабатываться только новые сообщения."
                        # )
                        init_chats = next_chats
                    else:
                        # Последующие запуски - проверяем изменения
                        events = self.get_message_events(next_chats)
                        for event in events:
                            yield event

                    async_events = self._drain_async_events()
                    for event in async_events:
                        yield event

                    last_errors_count = 0
                except Exception as e:
                    self.__logger.warning(f"Ошибка при получении ивентов: {e}\n(не критично, если возникает редко)")
                    last_traceback = traceback.format_exc()
                    self.__logger.debug(f"Traceback ошибки в listener:\n{last_traceback}")
                    last_errors_count += 1

                time.sleep(requests_delay)

        except KeyboardInterrupt:
            self.__logger.info("Получен сигнал остановки")
            raise
        except Exception as e:
            self.__logger.error(f"Критическая ошибка в listen: {e}")
            raise
        finally:
            self._stop_workers()
