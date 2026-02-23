from typing import Generator
from logging import getLogger
from datetime import datetime, timezone
import asyncio
import time
import traceback

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
                DealStatusChangedEvent(message.deal, chat),
            ]
        elif message.text == "{{DEAL_ROLLED_BACK}}" and message.deal is not None:
            return [
                DealRolledBackEvent(message.deal, chat),
                DealStatusChangedEvent(message.deal, chat),
            ]
        elif message.text == "{{DEAL_HAS_PROBLEM}}" and message.deal is not None:
            return [
                DealHasProblemEvent(message.deal, chat),
                DealStatusChangedEvent(message.deal, chat),
            ]
        elif message.text == "{{DEAL_PROBLEM_RESOLVED}}" and message.deal is not None:
            return [
                DealProblemResolvedEvent(message.deal, chat),
                DealStatusChangedEvent(message.deal, chat),
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
        | DealStatusChangedEvent,
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
            if not new_chat.last_message:
                # self.__logger.info(f'Пропускаю чат {new_chat.id} - нет last_message')
                continue
            
            # Получаем ID последнего обработанного сообщения для этого чата
            last_msg = new_chat.last_message
            last_known_id = self.__last_message_ids.get(new_chat.id)
            
            # Если это новый чат (нет сохраненного ID)
            if not last_known_id:
                time.sleep(3)
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
                    # тут короче супер костыль - мы поймали абсолютно новый чат, но без новой сделки,
                    # а такого быть не может, пробуем найти новую сделку
                    self.__logger.info(f'Поймал абсолютно новый чат, но в нём нету сделки, произвожу повторный поиск ')
                    time.sleep(4)

                    attempts = 3
                    delay = 4
                    for attempt in range(attempts):

                        msg_list = self.account.get_chat_messages(new_chat.id, 10)
                        new_msgs = []

                        for msg in msg_list.messages:
                            if msg.text == "{{ITEM_PAID}}" and msg.deal is not None:
                                has_new_deal = True
                                self.__logger.info(f'Для нахождения сделки {msg.deal.id} пришлось произвести повторный поиск'
                                                   f', задержка слушателя - {4 + attempt * (delay + 1)} секунд')
                            new_msgs.append(msg)
                        if has_new_deal:

                            break

                        time.sleep(delay)
                    else:
                        self.__logger.error(f'Не удалось найти сделку для нового чата, id: {new_chat.id}')

                # Обрабатываем в хронологическом порядке (от старых к новым)
                for msg in reversed(new_msgs):
                    events.extend(self.parse_message_event(msg, new_chat))
                
                # Сохраняем ID и время для будущих проверок
                self.__last_message_ids[new_chat.id] = new_chat.last_message.id
                self.__last_message_times[new_chat.id] = new_chat.last_message.created_at
                
                continue
            
            # Оптимизация: если ID последнего сообщения не изменился - пропускаем
            if new_chat.last_message.id == last_known_id:
                continue
            
            # Получаем историю сообщений для существующего чата
            msg_list = self.account.get_chat_messages(new_chat.id, 24)
            new_msgs = []
            
            # Получаем время последнего обработанного сообщения для дополнительной фильтрации
            last_known_time = self.__last_message_times.get(new_chat.id)
            
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
                self.__last_message_ids[new_chat.id] = latest_msg.id
                self.__last_message_times[new_chat.id] = latest_msg.created_at
                
                self.__logger.debug(
                    f"Чат {new_chat.id}: обработано {len(new_msgs)} сообщений, "
                    f"последнее время={latest_msg.created_at}, id={latest_msg.id}"
                )
        
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

        chats: ChatList = None
        last_errors_count = 0
        try:
            # Устанавливаем время запуска текущей сессии
            self.__startup_time = datetime.now(timezone.utc).isoformat()
            self.__logger.info(f'Время запуска слушателя событий: {self.__startup_time} ')
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
                    if not chats:
                        # Первый запуск - инициализируем чаты
                        events = self.initialize_chats(next_chats)
                        for event in events:
                            yield event
                        # self.__logger.info(
                        #     f"Инициализация завершена. Обнаружено {len(next_chats.chats)} чатов. "
                        #     f"Далее будут обрабатываться только новые сообщения."
                        # )
                    elif chats != next_chats:
                        # Последующие запуски - проверяем изменения
                        events = self.get_message_events(next_chats)
                        for event in events:
                            yield event

                    chats = next_chats
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
