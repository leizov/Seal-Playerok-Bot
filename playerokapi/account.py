from __future__ import annotations
from typing import *
from logging import getLogger
from typing import Literal
import json
import random
import time

from curl_cffi.requests import Session as CurlSession, Response as CurlResponse

from .misc import *

from . import types
from .exceptions import *
from .parser import *
from .enums import *



def get_account() -> Account | None:
    if hasattr(Account, "instance"):
        return getattr(Account, "instance")


class Account:
    """
    Класс, описывающий данные и методы Playerok аккаунта.

    :param token: Токен аккаунта.
    :type token: `str`

    :param user_agent: Юзер-агент браузера.
    :type user_agent: `str`

    :param proxy: Прокси в форматах: `ip:port:user:password`, `user:pass@ip:port`, `ip:port`, `socks5://user:pass@ip:port` или `socks5://ip:port`, _опционально_.
    :type proxy: `str` or `None`

    :param requests_timeout: Таймаут ожидания ответов на запросы.
    :type requests_timeout: `int`

    :param request_max_retries: Максимальное количество повторных попыток отправки запроса, если была обнаружена CloudFlare защита.
    :type request_max_retries: `int`
    """

    def __new__(cls, *args, **kwargs) -> Account:
        if not hasattr(cls, "instance"):
            cls.instance = super(Account, cls).__new__(cls)
        return getattr(cls, "instance")

    def __init__(
            self,
            token: str,
            user_agent: str = "",
            proxy: str = None,
            requests_timeout: int = 15,
            request_max_retries: int = 7,
            auid: str = None
        ):
        if hasattr(self, '_initialized'):
            return
            
        self.token = token
        self._initialized = True
        """ Токен сессии аккаунта. """
        self.user_agent = user_agent
        """ Юзер-агент браузера. """
        self.auid = auid
        self.requests_timeout = requests_timeout
        """ Таймаут ожидания ответов на запросы. """
        self.proxy = proxy
        """ Прокси. """
        # Обработка разных типов прокси
        if self.proxy:
            if self.proxy.startswith('socks5://') or self.proxy.startswith('socks4://'):
                # SOCKS прокси оставляем как есть
                self.__proxy_string = self.proxy
            else:
                # HTTP/HTTPS прокси - добавляем префикс http://
                clean_proxy = self.proxy.replace('https://', '').replace('http://', '')
                self.__proxy_string = f"http://{clean_proxy}"
        else:
            self.__proxy_string = None
        """ Строка прокси. """
        self.request_max_retries = request_max_retries
        """ Максимальное количество повторных попыток отправки запроса. """

        self.base_url = "https://playerok.com"
        """ Базовый URL для всех запросов. """

        self.id: str | None = None
        """ ID аккаунта. \n\n_Заполняется при первом использовании get()_ """
        self.username: str | None = None
        """ Никнейм аккаунта. \n\n_Заполняется при первом использовании get()_ """
        self.email: str | None = None
        """ Email почта аккаунта. \n\n_Заполняется при первом использовании get()_ """
        self.role: str | None = None
        """ Роль аккаунта. \n\n_Заполняется при первом использовании get()_ """
        self.support_chat_id: str | None = None
        """ ID чата поддержки. \n\n_Заполняется при первом использовании get()_ """
        self.system_chat_id: str | None = None
        """ ID системного чата. \n\n_Заполняется при первом использовании get()_ """
        self.unread_chats_counter: int | None = None
        """ Количество непрочитанных чатов. \n\n_Заполняется при первом использовании get()_ """
        self.is_blocked: bool | None = None
        """ Заблокирован ли аккаунт. \n\n_Заполняется при первом использовании get()_ """
        self.is_blocked_for: str | None = None
        """ Причина блокировки аккаунта. \n\n_Заполняется при первом использовании get()_ """
        self.created_at: str | None = None
        """ Дата создания аккаунта. \n\n_Заполняется при первом использовании get()_ """
        self.last_item_created_at: str | None = None
        """ Дата создания последнего предмета. \n\n_Заполняется при первом использовании get()_ """
        self.has_frozen_balance: bool | None = None
        """ Заморожен ли баланс аккаунта. \n\n_Заполняется при первом использовании get()_ """
        self.has_confirmed_phone_number: bool | None = None
        """ Подтверждён ли номер телефона. \n\n_Заполняется при первом использовании get()_ """
        self.can_publish_items: bool | None = None
        """ Может ли продавать предметы. \n\n_Заполняется при первом использовании get()_ """
        self.profile: AccountProfile | None = None
        """ Профиль аккаунта (не путать с профилем пользователя). \n\n_Заполняется при первом использовании get()_ """

        self.interlocutor_ids: dict[str, str] = {}
        """ Кэш: {chat_id: user_id_собеседника}. Заполняется автоматически при получении чатов. """

        self._refresh_clients()
        self.__logger = getLogger("playerokapi")

    def _refresh_clients(self):
        """Cоздаёт/пересоздаёт curl-cffi сессию с актуальными настройками."""
        # Закрываем старую сессию если есть
        if hasattr(self, '_Account__curl_session') and self.__curl_session:
            try:
                self.__curl_session.close()
            except:
                pass
        
        # Создаём новую сессию с имперсонацией Chrome
        self.__curl_session = CurlSession(
            impersonate="chrome120",
            proxy=self.__proxy_string,
            timeout=self.requests_timeout
        )

    def update_proxy(self, proxy: str | None):
        """
        Обновляет прокси без перезапуска бота (hot-reload).
        
        :param proxy: Новая прокси строка или None для отключения.
        """
        self.proxy = proxy
        
        if self.proxy:
            if self.proxy.startswith('socks5://') or self.proxy.startswith('socks4://'):
                self.__proxy_string = self.proxy
            else:
                clean_proxy = self.proxy.replace('https://', '').replace('http://', '')
                self.__proxy_string = f"http://{clean_proxy}"
        else:
            self.__proxy_string = None
        
        # Пересоздаём клиенты с новым прокси
        self._refresh_clients()
        self.__logger.info(f"Прокси обновлён: {self.__proxy_string or 'отключён'}")

    def request(self, method: Literal["get", "post"], url: str, headers: dict[str, str], 
                payload: dict[str, str] | None = None, files: dict | None = None) -> CurlResponse:
        """
        Отправляет запрос на сервер playerok.com.

        :param method: Метод запроса: post, get.
        :type method: `str`

        :param url: URL запроса.
        :type url: `str`

        :param headers: Заголовки запроса.
        :type headers: `dict[str, str]`
        
        :param payload: Payload запроса.
        :type payload: `dict[str, str]` or `None`
        
        :param files: Файлы запроса.
        :type files: `dict` or `None`

        :return: Ответ запроса.
        :rtype: `curl_cffi.requests.Response`
        """

        agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
        ]

        user_agent = self.user_agent if self.user_agent else random.choice(agents)

        chrome_version = "140.0.0.0"  # По умолчанию
        if "Chrome/" in user_agent:
            try:
                chrome_version = user_agent.split("Chrome/")[1].split(" ")[0]
            except:
                pass

        _headers = {
            "accept": "*/*",
            "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "apollo-require-preflight": "true",
            "apollographql-client-name": "web",
            "content-type": "application/json",
            "origin": "https://playerok.com",
            "priority": "u=1, i",
            "referer": "https://playerok.com/",
            "sec-ch-ua": f'"Chromium";v="{chrome_version}", "Not=A?Brand";v="24", "Google Chrome";v="{chrome_version}"',
            "sec-ch-ua-arch": '"x86"',
            "sec-ch-ua-bitness": '"64"',
            "sec-ch-ua-full-version": f'"{chrome_version}"',
            "sec-ch-ua-full-version-list": f'"Chromium";v="{chrome_version}", "Not=A?Brand";v="24.0.0.0", "Google Chrome";v="{chrome_version}"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-model": '""',
            "sec-ch-ua-platform": '"Windows"',
            "sec-ch-ua-platform-version": '"15.0.0"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "x-gql-op": "viewer",
            "x-timezone-offset": "-180"
        }

        headers["cookie"] = f"token={self.token}"
        # if self.auid:
        #     headers['cookie'] += f'; auid={self.auid}'
        headers["user-agent"] = user_agent
        headers = {**_headers, **headers}

        def make_req():
            if method == "get":
                r = self.__curl_session.get(
                    url=url, 
                    params=payload, 
                    headers=headers
                )
            elif method == "post":
                if files:
                    # Для запросов с файлами убираем content-type (будет multipart)
                    headers_no_ct = {k: v for k, v in headers.items() if k.lower() != 'content-type'}
                    r = self.__curl_session.post(
                        url=url,
                        data=payload,
                        headers=headers_no_ct,
                        files=files
                    )
                else:
                    r = self.__curl_session.post(
                        url=url, 
                        json=payload,
                        headers=headers
                    )
            return r

        cloudflare_signatures = [
            "<title>Just a moment...</title>",
            "window._cf_chl_opt",
            "Enable JavaScript and cookies to continue",
            "Checking your browser before accessing",
            "cf-browser-verification",
            "Cloudflare Ray ID"
        ]
        # Прогрессивные задержки: 1, 2, 3, 3, 3, 3, 3 секунды (max 3 сек)
        max_delay = 3.0
        for attempt in range(self.request_max_retries):
            resp = make_req()
            if not any(sig in resp.text for sig in cloudflare_signatures):
                break
            # Прогрессивная задержка: 1, 2, 3, 3, 3...
            delay = min(max_delay, float(attempt + 1))
            self.__logger.warning(
                f"⚠️ Cloudflare Detected (попытка {attempt + 1}/{self.request_max_retries}), "
                f"повтор через {delay:.0f} сек..."
            )
            time.sleep(delay)
            self._refresh_clients()
        else:
            self.__logger.error(
                f"❌ Cloudflare заблокировал все {self.request_max_retries} попыток! "
                f"Требуется смена токена/прокси/user-agent."
            )
            raise CloudflareDetectedException(resp)
        try:
            if "errors" in resp.json():
                raise RequestError(resp)
        except:
            pass
        if resp.status_code != 200:
           raise RequestFailedError(resp)
        return resp
    
    def get(self) -> Account:
        """
        Получает/обновляет данные об аккаунте.

        :return: Объект аккаунта с обновлёнными данными.
        :rtype: `playerokapi.account.Account`
        """
        headers = {"accept": "*/*"}
        payload = {
            "operationName": "viewer",
            "query": QUERIES.get("viewer"),
            "variables": {}
        }
        r = self.request("post", f"{self.base_url}/graphql", headers, payload)
        rjson = r.json()
        data: dict = rjson["data"]["viewer"]
        if data is None:
            raise UnauthorizedError()
        
        self.id = data.get("id")
        self.username = data.get("username")
        self.email = data.get("email")
        self.role = data.get("role")
        self.has_frozen_balance = data.get("hasFrozenBalance")
        self.support_chat_id = data.get("supportChatId")
        self.system_chat_id = data.get("systemChatId")
        self.unread_chats_counter = data.get("unreadChatsCounter")
        self.is_blocked = data.get("isBlocked")
        self.is_blocked_for = data.get("isBlockedFor")
        self.created_at = data.get("createdAt")
        self.last_item_created_at = data.get("lastItemCreatedAt")
        self.has_confirmed_phone_number = data.get("hasConfirmedPhoneNumber")
        self.can_publish_items = data.get("canPublishItems")
        
        headers = {"accept": "*/*"}
        payload = {
            "operationName": "user",
            "variables": json.dumps({"username": self.username, "hasSupportAccess": False}, ensure_ascii=False),
            "extensions": json.dumps({"persistedQuery": {"version": 1, "sha256Hash": PERSISTED_QUERIES.get("user")}}, ensure_ascii=False)
        }
        r = self.request("get", f"{self.base_url}/graphql", headers, payload).json()
        data: dict = r["data"]["user"]
        if data.get("__typename") == "User": self.profile = account_profile(data)
        return self
    
    def get_user(self, id: str | None = None, username: str | None = None) -> types.UserProfile:
        """
        Получает профиль пользователя.\n
        Можно получить по любому из двух параметров:

        :param id: ID пользователя, _опционально_.
        :type id: `str` or `None`

        :param username: Никнейм пользователя, _опционально_.
        :type username: `str` or `None`

        :return: Объект профиля пользователя.
        :rtype: `playerokapi.types.UserProfile`
        """
        headers = {"accept": "*/*"}
        payload = {
            "operationName": "user",
            "variables": json.dumps({"id": id, "username": username, "hasSupportAccess": False}, ensure_ascii=False),
            "extensions": json.dumps({"persistedQuery": {"version": 1, "sha256Hash": PERSISTED_QUERIES.get("user")}}, ensure_ascii=False)
        }
        r = self.request("get", f"{self.base_url}/graphql", headers, payload).json()
        data: dict = r["data"]["user"]
        if data.get("__typename") == "UserFragment": profile = data
        elif data.get("__typename") == "User": profile = data.get("profile")
        else: profile = None
        return user_profile(profile)

    def get_deals(self, count: int = 24, statuses: list[ItemDealStatuses] | None = None, 
                  direction: ItemDealDirections | None = None, after_cursor: str = None) -> types.ItemDealList:
        """
        Получает сделки аккаунта.

        :param count: Кол-во сделок, которые нужно получить (не более 24 за один запрос).
        :type count: `int`

        :param statuses: Статусы заявок, которые нужно получать, _опционально_.
        :type statuses: `list[playerokapi.enums.ItemDealsStatuses]` or `None`

        :param direction: Направление сделок, _опционально_.
        :type direction: `playerokapi.enums.ItemDealsDirections` or `None`

        :param after_cursor: Курсор, с которого будет идти парсинг (если нету - ищет с самого начала страницы), _опционально_.
        :type after_cursor: `str`
        
        :return: Страница сделок.
        :rtype: `playerokapi.types.ItemDealList`
        """
        str_statuses = [status.name for status in statuses] if statuses else None
        str_direction = direction.name if direction else None
        headers = {"accept": "*/*"}
        payload = {
            "operationName": "deals",
            "variables": json.dumps({"pagination": {"first": count, "after": after_cursor}, "filter": {"userId": self.id, "direction": str_direction, "status": str_statuses}, "showForbiddenImage": True}, ensure_ascii=False),
            "extensions": json.dumps({"persistedQuery": {"version": 1, "sha256Hash": PERSISTED_QUERIES.get("deals")}}, ensure_ascii=False)
        }
        r = self.request("get", f"{self.base_url}/graphql", headers, payload).json()
        return item_deal_list(r["data"]["deals"])

    def get_deal(self, deal_id: str) -> types.ItemDeal:
        """
        Получает сделку.

        :param deal_id: ID сделки.
        :type deal_id: `str`
        
        :return: Объект сделки.
        :rtype: `playerokapi.types.ItemDeal`
        """
        headers = {"accept": "*/*"}
        payload = {
            "operationName": "deal",
            "variables": json.dumps({"id": deal_id, "hasSupportAccess": False, "showForbiddenImage": True}, ensure_ascii=False),
            "extensions": json.dumps({"persistedQuery": {"version": 1, "sha256Hash": PERSISTED_QUERIES.get("deal")}}, ensure_ascii=False)
        }
        r = self.request("get", f"{self.base_url}/graphql", headers, payload).json()
        return item_deal(r["data"]["deal"])
    
    def update_deal(self, deal_id: str, new_status: ItemDealStatuses) -> types.ItemDeal:
        """
        Обновляет статус сделки
        (используется, чтобы подтвердить, оформить возврат и т.д).

        :param deal_id: ID сделки.
        :type deal_id: `str`

        :param new_status: Новый статус сделки.
        :type new_status: `playerokapi.enums.ItemDealStatuses`
        
        :return: Объект обновлённой сделки.
        :rtype: `playerokapi.types.ItemDeal`
        """
        headers = {"accept": "*/*"}
        payload = {
            "operationName": "updateDeal",
            "variables": {
                "input": {
                    "id": deal_id,
                    "status": new_status.name
                }
            },
            "query": QUERIES.get("updateDeal")
        }

        r = self.request("post", f"{self.base_url}/graphql", headers, payload).json()
        return item_deal(r["data"]["updateDeal"])

    def get_games(self, count: int = 24, type: GameTypes | None = None, 
                  after_cursor: str = None) -> types.GameList:
        """
        Получает все игры или/и приложения.

        :param count: Кол-во игр, которые нужно получить (не более 24 за один запрос).
        :type count: `int`

        :param type: Тип игр, которые нужно получать. По умолчанию не указано, значит будут все сразу, _опционально_.
        :type type: `playerokapi.enums.GameTypes` or `None`

        :param after_cursor: Курсор, с которого будет идти парсинг (если нету - ищет с самого начала страницы), _опционально_.
        :type after_cursor: `str`
        
        :return: Страница игр.
        :rtype: `playerokapi.types.GameList`
        """
        headers = {"accept": "*/*"}
        payload = {
            "operationName": "games",
            "variables": json.dumps({"pagination": {"first": count, "after": after_cursor}, "filter": {"type": type.name} if type else {}}, ensure_ascii=False),
            "extensions": json.dumps({"persistedQuery": {"version": 1, "sha256Hash": PERSISTED_QUERIES.get("games")}}, ensure_ascii=False)
        }
        r = self.request("get", f"{self.base_url}/graphql", headers, payload).json()
        return game_list(r["data"]["games"])
    
    def get_game(self, id: str | None = None, slug: str | None = None) -> types.Game:
        """
        Получает игру/приложение.\n
        Можно получить по любому из двух параметров:

        :param id: ID игры/приложения, _опционально_.
        :type id: `str` or `None`

        :param slug: Имя страницы игры/приложения, _опционально_.
        :type slug: `str` or `None`
        
        :return: Объект игры.
        :rtype: `playerokapi.types.Game`
        """
        headers = {"accept": "*/*"}
        payload = {
            "operationName": "GamePage",
            "variables": json.dumps({"id": id, "slug": slug}, ensure_ascii=False),
            "extensions": json.dumps({"persistedQuery": {"version": 1, "sha256Hash": PERSISTED_QUERIES.get("GamePage")}}, ensure_ascii=False)
        }
        r = self.request("get", f"{self.base_url}/graphql", headers, payload).json()
        return game(r["data"]["game"])

    def get_game_category(self, id: str | None = None, game_id: str | None = None,
                          slug: str | None = None) -> types.GameCategory:
        """
        Получает категорию игры/приложения.\n
        Можно получить параметру `id` или по связке параметров `game_id` и `slug`

        :param id: ID категории, _опционально_.
        :type id: `str` or `None`

        :param game_id: ID игры категории (лучше указывать в связке со slug, чтобы находить точную категорию), _опционально_.
        :type game_id: `str` or `None`

        :param slug: Имя страницы категории, _опционально_.
        :type slug: `str` or `None`
        
        :return: Объект категории игры.
        :rtype: `playerokapi.types.GameCategory`
        """
        headers = {"accept": "*/*"}
        payload = {
            "operationName": "GamePageCategory",
            "variables": json.dumps({"id": id, "gameId": game_id, "slug": slug}, ensure_ascii=False),
            "extensions": json.dumps({"persistedQuery": {"version": 1, "sha256Hash": PERSISTED_QUERIES.get("GamePageCategory")}}, ensure_ascii=False)
        }
        r = self.request("get", f"{self.base_url}/graphql", headers, payload).json()
        return game_category(r["data"]["gameCategory"])
    
    def get_game_category_agreements(self, game_category_id: str, user_id: str | None = None,
                                     count: int = 24, after_cursor: str | None = None) -> types.GameCategoryAgreementList:
        """
        Получает соглашения пользователя на продажу предметов в категории (если пользователь уже принял эти соглашения - список будет пуст).

        :param game_category_id: ID категории игры.
        :type game_category_id: `str`

        :param user_id: ID пользователя, чьи соглашения нужно получить. Если не указан, будет получать по ID вашего аккаунта, _опционально_.
        :type user_id: `str` or `None`

        :param count: Кол-во соглашений, которые нужно получить (не более 24 за один запрос).
        :type count: `int`
        
        :param after_cursor: Курсор, с которого будет идти парсинг (если нету - ищет с самого начала страницы), _опционально_.
        :type after_cursor: `str` or `None`
        
        :return: Страница соглашений.
        :rtype: `playerokapi.types.GameCategoryAgreementList`
        """
        headers = {"accept": "*/*"}
        payload = {
            "operationName": "gameCategoryAgreements",
            "variables": json.dumps({"pagination": {"first": count, "after": after_cursor}, "filter": {"gameCategoryId": game_category_id, "userId": user_id if user_id else self.id}}, ensure_ascii=False),
            "extensions": json.dumps({"persistedQuery": {"version": 1, "sha256Hash": PERSISTED_QUERIES.get("gameCategoryAgreements")}}, ensure_ascii=False)
        }
        r = self.request("get", f"{self.base_url}/graphql", headers, payload).json()
        return game_category_agreement_list(r["data"]["gameCategoryAgreements"])
    
    def get_game_category_obtaining_types(self, game_category_id: str, count: int = 24,
                                          after_cursor: str | None = None) -> types.GameCategoryObtainingTypeList:
        """
        Получает типы (способы) получения предмета в категории.
        
        :param game_category_id: ID категории игры.
        :type game_category_id: `str`

        :param count: Кол-во соглашений, которые нужно получить (не более 24 за один запрос).
        :type count: `int`
        
        :param after_cursor: Курсор, с которого будет идти парсинг (если нету - ищет с самого начала страницы), _опционально_.
        :type after_cursor: `str` or `None`
        
        :return: Страница соглашений.
        :rtype: `playerokapi.types.GameCategoryAgreementList`
        """
        headers = {"accept": "*/*"}
        payload = {
            "operationName": "gameCategoryObtainingTypes",
            "variables": json.dumps({"pagination": {"first": count, "after": after_cursor}, "filter": {"gameCategoryId": game_category_id}}, ensure_ascii=False),
            "extensions": json.dumps({"persistedQuery": {"version": 1, "sha256Hash": PERSISTED_QUERIES.get("gameCategoryObtainingTypes")}}, ensure_ascii=False)
        }
        r = self.request("get", f"{self.base_url}/graphql", headers, payload).json()
        return game_category_obtaining_type_list(r["data"]["gameCategoryObtainingTypes"])
    
    def get_game_category_instructions(self, game_category_id: str, obtaining_type_id: str, count: int = 24,
                                       type: GameCategoryInstructionTypes | None = None, after_cursor: str | None = None) -> types.GameCategoryInstructionList:
        """
        Получает инструкции по продаже/покупке в категории.
        
        :param game_category_id: ID категории игры.
        :type game_category_id: `str`
        
        :param obtaining_type_id: ID типа (способа) получения предмета.
        :type obtaining_type_id: `str`

        :param count: Кол-во инструкций, которые нужно получить (не более 24 за один запрос).
        :type count: `int`
        
        :param type: Тип инструкции: для продавца или для покупателя, _опционально_.
        :type type: `enums.GameCategoryInstructionTypes` or `None`

        :param after_cursor: Курсор, с которого будет идти парсинг (если нету - ищет с самого начала страницы), _опционально_.
        :type after_cursor: `str` or `None`
        
        :return: Страница инструкий.
        :rtype: `playerokapi.types.GameCategoryInstructionList`
        """
        headers = {"accept": "*/*"}
        payload = {
            "operationName": "gameCategoryInstructions",
            "variables": json.dumps({"pagination": {"first": count, "after": after_cursor}, "filter": {"gameCategoryId": game_category_id, "obtainingTypeId": obtaining_type_id, "type": type.name if type else None}}, ensure_ascii=False),
            "extensions": json.dumps({"persistedQuery": {"version": 1, "sha256Hash": PERSISTED_QUERIES.get("gameCategoryInstructions")}}, ensure_ascii=False)
        }
        r = self.request("get", f"{self.base_url}/graphql", headers, payload).json()
        return game_category_instruction_list(r["data"]["gameCategoryInstructions"])

    def get_game_category_data_fields(self, game_category_id: str, obtaining_type_id: str, count: int = 24,
                                      type: GameCategoryDataFieldTypes | None = None, after_cursor: str | None = None) -> types.GameCategoryDataFieldList:
        """
        Получает поля с данными категории (которые отправляются после покупки).
        
        :param game_category_id: ID категории игры.
        :type game_category_id: `str`
        
        :param obtaining_type_id: ID типа (способа) получения предмета.
        :type obtaining_type_id: `str`

        :param count: Кол-во инструкций, которые нужно получить (не более 24 за один запрос).
        :type count: `int`
        
        :param type: Тип полей с данными, _опционально_.
        :type type: `enums.GameCategoryDataFieldTypes` or `None`

        :param after_cursor: Курсор, с которого будет идти парсинг (если нету - ищет с самого начала страницы), _опционально_.
        :type after_cursor: `str` or `None`
        
        :return: Страница полей с данными.
        :rtype: `playerokapi.types.GameCategoryDataFieldList`
        """
        headers = {"accept": "*/*"}
        payload = {
            "operationName": "gameCategoryDataFields",
            "variables": json.dumps({"pagination": {"first": count, "after": after_cursor}, "filter": {"gameCategoryId": game_category_id, "obtainingTypeId": obtaining_type_id, "type": type.name if type else None}}, ensure_ascii=False),
            "extensions": json.dumps({"persistedQuery": {"version": 1, "sha256Hash": PERSISTED_QUERIES.get("gameCategoryDataFields")}}, ensure_ascii=False)
        }
        r = self.request("get", f"{self.base_url}/graphql", headers, payload).json()
        return game_category_data_field_list(r["data"]["gameCategoryDataFields"])
    
    def get_chats(self, count: int = 24, type: ChatTypes | None = None,
                  status: ChatStatuses | None = None, after_cursor: str | None = None) -> types.ChatList:
        """
        Получает все чаты аккаунта.

        :param count: Кол-во чатов, которые нужно получить (не более 24 за один запрос).
        :type count: `int`

        :param type: Тип чатов, которые нужно получать. По умолчанию не указано, значит будут все сразу, _опционально_.
        :type type: `playerokapi.enums.ChatTypes` or `None`

        :param status: Статус чатов, которые нужно получать. По умолчанию не указано, значит будут любые, _опционально_.
        :type status: `playerokapi.enums.ChatStatuses` or `None`
        
        :param after_cursor: Курсор, с которого будет идти парсинг (если нету - ищет с самого начала страницы), _опционально_.
        :type after_cursor: `str` or `None`
        
        :return: Страница чатов.
        :rtype: `playerokapi.types.ChatList`
        """
        headers = {"accept": "*/*"}
        payload = {
            "operationName": "userChats",
            "variables": json.dumps({"pagination": {"first": count, "after": after_cursor}, "filter": {"userId": self.id, "type": type.name if type else None, "status": status.name if status else None}, "hasSupportAccess": False}, ensure_ascii=False),
            "extensions": json.dumps({"persistedQuery": {"version": 1, "sha256Hash": PERSISTED_QUERIES.get("userChats")}}, ensure_ascii=False)
        }
        r = self.request("get", f"{self.base_url}/graphql", headers, payload).json()
        chat_list_obj = chat_list(r["data"]["chats"])
        
        # Автоматически кэшируем interlocutor_ids для полученных чатов
        for chat in chat_list_obj.chats:
            self._cache_interlocutor(chat)
        
        return chat_list_obj
    
    def get_chat(self, chat_id: str) -> types.Chat:
        """
        Получает чат.

        :param chat_id: ID чата.
        :type chat_id: `str`
        
        :return: Объект чата.
        :rtype: `playerokapi.types.Chat`
        """
        headers = {"accept": "*/*"}
        payload = {
            "operationName": "chat",
            "variables": json.dumps({"id": chat_id, "hasSupportAccess": False}, ensure_ascii=False),
            "extensions": json.dumps({"persistedQuery": {"version": 1, "sha256Hash": PERSISTED_QUERIES.get("chat")}}, ensure_ascii=False)
        }
        r = self.request("get", f"{self.base_url}/graphql", headers, payload).json()
        chat_obj = chat(r["data"]["chat"])
        
        # Автоматически кэшируем interlocutor_id для полученного чата
        self._cache_interlocutor(chat_obj)
        
        return chat_obj
    
    def get_chat_by_username(self, username: str) -> types.Chat | None:
        """
        Получает чат по никнейму собеседника.

        :param username: Никнейм собеседника.
        :type username: `str`

        :return: Объект чата.
        :rtype: `playerokapi.types.Chat` or `None`
        """
        next_cursor = None
        while True:
            chats = self.get_chats(count=24, after_cursor=next_cursor)
            for chat in chats.chats:
                if any(user for user in chat.users if user.username.lower() == username.lower()):
                    return chat
            if not chats.page_info.has_next_page:
                break
            next_cursor = chats.page_info.end_cursor
    
    def get_chat_messages(self, chat_id: str, count: int = 24,
                          after_cursor: str | None = None) -> types.ChatMessageList:
        """
        Получает сообщения чата.

        :param chat_id: ID чата.
        :type chat_id: `str`

        :param count: Кол-во сообщений, которые нужно получить (не более 24 за один запрос).
        :type count: `int`

        :param after_cursor: Курсор, с которого будет идти парсинг (если нету - ищет с самого начала страницы), _опционально_.
        :type after_cursor: `str` or `None`
        
        :return: Страница сообщений.
        :rtype: `playerokapi.types.ChatMessageList`
        """
        headers = {"accept": "*/*"}
        payload = {
            "operationName": "chatMessages",
            "variables": json.dumps({"pagination": {"first": count, "after": after_cursor}, "filter": {"chatId": chat_id}, "hasSupportAccess": False, "showForbiddenImage": True}, ensure_ascii=False),
            "extensions": json.dumps({"persistedQuery": {"version": 1, "sha256Hash": PERSISTED_QUERIES.get("chatMessages")}}, ensure_ascii=False)
        }
        r = self.request("get", f"{self.base_url}/graphql", headers, payload).json()
        return chat_message_list(r["data"]["chatMessages"])

    def mark_chat_as_read(self, chat_id: str) -> types.Chat:
        """
        Помечает чат как прочитанный (все сообщения).

        :param chat_id: ID чата.
        :type chat_id: `str`

        :return: Объект чата с обновлёнными данными.
        :rtype: `playerokapi.types.Chat`
        """
        headers = {"accept": "*/*"}
        payload = {
            "operationName": "markChatAsRead",
            "query": QUERIES.get("markChatAsRead"),
            "variables": {
                "input": {
                    "chatId": chat_id
                }
            }
        }
        r = self.request("post", f"{self.base_url}/graphql", headers, payload).json()
        return chat(r["data"]["markChatAsRead"])
    
    def send_message(self, chat_id: str, text: str | None = None,
                     photo_file_path: str | None = None, mark_chat_as_read: bool = False) -> types.ChatMessage:
        """
        Отправляет сообщение в чат.\n
        Можно отправить текстовое сообщение `text` или фотографию `photo_file_path`.

        :param chat_id: ID чата, в который нужно отправить сообщение.
        :type chat_id: `str`

        :param text: Текст сообщения, _опционально_.
        :type text: `str` or `None`

        :param photo_file_path: Путь к файлу фотографии, _опционально_.
        :type photo_file_path: `str` or `None`

        :param mark_chat_as_read: Пометить чат, как прочитанный перед отправкой, _опционально_.
        :type mark_chat_as_read: `bool`

        :return: Объект отправленного сообщения.
        :rtype: `playerokapi.types.ChatMessage`
        """
        if mark_chat_as_read:
            self.mark_chat_as_read(chat_id=chat_id)
        headers = {"accept": "*/*"}
        if photo_file_path: query = QUERIES.get("createChatMessageWithFile")
        elif text: query = QUERIES.get("createChatMessage")
        operations = {
            "operationName": "createChatMessage",
            "query": query,
            "variables": {
                "input": {
                    "chatId": chat_id
                }
            }
        }
        if photo_file_path:
            operations["variables"]["file"] = None
        elif text:
            operations["variables"]["input"]["text"] = text
        
        files = None
        try:
            if photo_file_path:
                files = {"1": open(photo_file_path, "rb")}
                map = {"1":["variables.file"]}
                payload = {"operations": json.dumps(operations), "map": json.dumps(map)}
            else:
                payload = operations
            r = self.request("post", f"{self.base_url}/graphql", headers, payload, files).json()
            return chat_message(r["data"]["createChatMessage"])
        finally:
            if files:
                for file_obj in files.values():
                    file_obj.close()

    def create_item(self, game_category_id: str, obtaining_type_id: str, name: str, price: int, 
                    description: str, options: list[GameCategoryOption], data_fields: list[GameCategoryDataField],
                    attachments: list[str]) -> types.Item:
        """
        Создаёт предмет (после создания помещается в черновик, а не сразу выставляется на продажу).

        :param game_category_id: ID категории игры, в которой необходимо создать предмет.
        :type game_category_id: `str`

        :param obtaining_type_id: ID типа получения предмета.
        :type obtaining_type_id: `str`

        :param name: Название предмета.
        :type name: `str`

        :param price: Цена предмета.
        :type price: `int` or `str`

        :param description: Описание предмета.
        :type description: `str`

        :param options: Массив **выбранных** опций (аттрибутов) предмета.
        :type options: `list[playerokapi.types.GameCategoryOption]`

        :param data_fields: Массив полей с данными предмета. \n
            !!! Должны быть заполнены данные с типом поля `ITEM_DATA`, то есть те данные, которые указываются при заполнении информации о товаре.
            Поля с типом `OBTAINING_DATA` **заполнять и передавать не нужно**, так как эти данные будет указывать сам покупатель при оформлении предмета.
        :type data_fields: `list[playerokapi.types.GameCategoryDataField]`

        :param attachments: Массив файлов-приложений предмета. Указываются пути к файлам.
        :type attachments: `list[str]`

        :return: Объект созданного предмета.
        :rtype: `playerokapi.types.Item`
        """
        payload_attributes = {option.field: option.value for option in options}
        payload_data_fields = [{"fieldId": field.id, "value": field.value} for field in data_fields]
        headers = {"accept": "*/*"}
        operations = {
            "operationName": "createItem",
            "query": QUERIES.get("createItem"),
            "variables": {
                "input": {
                    "gameCategoryId": game_category_id,
                    "obtainingTypeId": obtaining_type_id,
                    "name": name,
                    "price": int(price),
                    "description": description,
                    "attributes": payload_attributes,
                    "dataFields": payload_data_fields
                },
                "attachments": [None] * len(attachments)
            }
        }
        map = {}
        files = {}
        try:
            i=0
            for att in attachments:
                i+=1
                map[str(i)] = [f"variables.attachments.{i-1}"]
                files[str(i)] = open(att, "rb")
            payload = {
                "operations": json.dumps(operations),
                "map": json.dumps(map)
            }

            r = self.request("post", f"{self.base_url}/graphql", headers, payload, files).json()
            return item(r["data"]["createItem"])
        finally:
            for file_obj in files.values():
                file_obj.close()
    
    def update_item(self, id: str, name: str | None = None, price: int | None = None, description: str | None = None, 
                    options: list[GameCategoryOption] | None = None, data_fields: list[GameCategoryDataField] | None = None, 
                    remove_attachments: list[str] | None = None, add_attachments: list[str] | None = None) -> types.Item:
        """
        Обновляет предмет аккаунта.

        :param id: ID предмета.
        :type id: `str`

        :param name: Название предмета.
        :type name: `str` or `None`

        :param price: Цена предмета.
        :type price: `int` or `str` or `None`

        :param description: Описание предмета.
        :type description: `str` or `None`

        :param options: Массив **выбранных** опций (аттрибутов) предмета.
        :type options: `list[playerokapi.types.GameCategoryOption]` or `None`

        :param data_fields: Массив полей с данными предмета. \n
            !!! Должны быть заполнены данные с типом поля `ITEM_DATA`, то есть те данные, которые указываются при заполнении информации о товаре.
            Поля с типом `OBTAINING_DATA` **заполнять и передавать не нужно**, так как эти данные будет указывать сам покупатель при оформлении предмета.
        :type data_fields: `list[playerokapi.types.GameCategoryDataField]` or `None`

        :param remove_attachments: Массив ID файлов-приложений предмета, которые нужно удалить.
        :type remove_attachments: `list[str]` or `None`

        :param add_attachments: Массив файлов-приложений предмета, которые нужно добавить. Указываются пути к файлам.
        :type add_attachments: `list[str]` or `None`

        :return: Объект обновлённого предмета.
        :rtype: `playerokapi.types.Item`
        """
        payload_attributes = {option.field: option.value for option in options} if options is not None else None
        payload_data_fields = [{"fieldId": field.id, "value": field.value} for field in data_fields] if data_fields is not None else None
        headers = {"accept": "*/*"}
        operations = {
            "operationName": "updateItem",
            "query": QUERIES.get("updateItem"),
            "variables": {
                "input": {
                    "id": id
                },
                "addedAttachments": [None] * len(add_attachments) if add_attachments else None
            }
        }
        if name: operations["variables"]["input"]["name"] = name
        if price: operations["variables"]["input"]["price"] = int(price)
        if description: operations["variables"]["input"]["description"] = description
        if options: operations["variables"]["input"]["attributes"] = payload_attributes
        if data_fields: operations["variables"]["input"]["dataFields"] = payload_data_fields
        if remove_attachments: operations["variables"]["input"]["removedAttachments"] = remove_attachments

        map = {}
        files = {}
        try:
            if add_attachments:
                i=0
                for att in add_attachments:
                    i+=1
                    map[str(i)] = [f"variables.addedAttachments.{i-1}"]
                    files[str(i)] = open(att, "rb")
            payload = {
                "operations": json.dumps(operations),
                "map": json.dumps(map)
            }
            r = self.request("post", f"{self.base_url}/graphql", headers, payload if files else operations, files if files else None).json()
            return item(r["data"]["updateItem"])
        finally:
            for file_obj in files.values():
                file_obj.close()

    def remove_item(self, id: str) -> bool:
        """
        Полностью удаляет предмет вашего аккаунта.

        :param id: ID предмета.
        :type id: `str`
        """
        headers = {"accept": "*/*"}
        payload = {
            "operationName": "removeItem",
            "query": QUERIES.get("removeItem"),
            "variables": {
                "id": id,
            }
        }
        self.request("post", f"{self.base_url}/graphql", headers, payload)
        return True
    
    def publish_item(self, item_id: str, priority_status_id: str, 
                     transaction_provider_id: TransactionProviderIds = TransactionProviderIds.LOCAL) -> types.Item:
        """
        Выставляет предмет на продажу.

        :param item_id: ID предмета.
        :type item_id: `str`

        :param priority_status_id: ID статуса приоритета предмета, под которым его нужно выставить на продажу.
        :type priority_status_id: `str`

        :param transaction_provider_id: ID провайдера транзакции.
        :type transaction_provider_id: `playerokapi.types.TransactionProviderIds`

        :return: Объект опубликованного предмета.
        :rtype: `playerokapi.types.Item`
        """
        headers = {"accept": "*/*"}
        payload = {
            "operationName": "publishItem",
            "query": QUERIES.get("publishItem"),
            "variables": {
                "input": {
                    "transactionProviderId": transaction_provider_id.name,
                    "priorityStatuses": [priority_status_id],
                    "itemId": item_id
                }
            }
        }
        r = self.request("post", f"{self.base_url}/graphql", headers, payload).json()
        return item(r["data"]["publishItem"])

    def get_items(self, game_id: str | None = None, category_id: str | None = None, count: int = 24,
                  status: ItemStatuses = ItemStatuses.APPROVED, after_cursor: str | None = None) -> types.ItemProfileList:
        """
        Получает предметы игры/приложения.\n
        Можно получить по любому из двух параметров: `game_id`, `category_id`.

        :param game_id: ID игры/приложения, _опционально_.
        :type game_id: `str` or `None`

        :param category_id: ID категории игры/приложения, _опционально_.
        :type category_id: `str` or `None`

        :param count: Кол-во предеметов, которые нужно получить (не более 24 за один запрос).
        :type count: `int`

        :param status: Тип предметов, которые нужно получать: активные или проданные. По умолчанию активные.
        :type status: `playerokapi.enums.ItemStatuses`

        :param after_cursor: Курсор, с которого будет идти парсинг (если нету - ищет с самого начала страницы), _опционально_.
        :type after_cursor: `str` or `None`
        
        :return: Страница профилей предметов.
        :rtype: `playerokapi.types.ItemProfileList`
        """
        headers = {"accept": "*/*"}
        filter = {"gameId": game_id, "status": [status.name] if status else None} if not category_id else {"gameCategoryId": category_id, "status": [status.name] if status else None}
        payload = {
            "operationName": "items",
            "variables": json.dumps({"pagination": {"first": count, "after": after_cursor}, "filter": filter}, ensure_ascii=False),
            "extensions": json.dumps({"persistedQuery": {"version": 1, "sha256Hash": PERSISTED_QUERIES.get("items")}}, ensure_ascii=False)
        }
        r = self.request("get", f"{self.base_url}/graphql", headers, payload).json()
        return item_profile_list(r["data"]["items"])

    def get_item(self, id: str | None = None, slug: str | None = None) -> types.MyItem | types.Item | types.ItemProfile:
        """
        Получает предмет (товар).\n
        Можно получить по любому из двух параметров:

        :param id: ID предмета, _опционально_.
        :type id: `str` or `None`

        :param slug: Имя страницы предмета, _опционально_.
        :type slug: `str` or `None`
        
        :return: Объект предмета.
        :rtype: `playerokapi.types.MyItem` or `playerokapi.types.Item` or `playerokapi.types.ItemProfile`
        """
        headers = {"accept": "*/*"}
        payload = {
            "operationName": "item",
            "variables": json.dumps({"id": id, "slug": slug, "hasSupportAccess": False, "showForbiddenImage": True}, ensure_ascii=False),
            "extensions": json.dumps({"persistedQuery": {"version": 1, "sha256Hash": PERSISTED_QUERIES.get("item")}}, ensure_ascii=False)
        }
        r = self.request("get", f"{self.base_url}/graphql", headers, payload).json()
        data: dict = r["data"]["item"]
        if data["__typename"] == "MyItem": _item = my_item(data)
        elif data["__typename"] == "ItemProfile": _item = item_profile(data)
        elif data["__typename"] in ["Item", "ForeignItem"]: _item = item(data)
        else: _item = None
        return _item

    def get_item_priority_statuses(self, item_id: str, item_price: str) -> list[types.ItemPriorityStatus]:
        """
        Получает статусы приоритетов для предмета.

        :param item_id: ID предмета.
        :type item_id: `str`

        :param item_price: Цена предмета.
        :type item_price: `int` or `str`
        
        :return: Массив статусов приоритета предмета.
        :rtype: `list[playerokapi.types.ItemPriorityStatus]`
        """
        headers = {"accept": "*/*"}
        payload = {
            "operationName": "itemPriorityStatuses",
            "variables": json.dumps({"itemId": item_id, "price": int(item_price)}, ensure_ascii=False),
            "extensions": json.dumps({"persistedQuery": {"version": 1, "sha256Hash": PERSISTED_QUERIES.get("itemPriorityStatuses")}}, ensure_ascii=False)
        }
        r = self.request("get", f"{self.base_url}/graphql", headers, payload).json()
        return [item_priority_status(status) for status in r["data"]["itemPriorityStatuses"]]

    def increase_item_priority_status(self, item_id: str, priority_status_id: str, payment_method_id: TransactionPaymentMethodIds | None = None, 
                                      transaction_provider_id: TransactionProviderIds = TransactionProviderIds.LOCAL) -> types.Item:
        """
        Повышает статус приоритета предмета.

        :param item_id: ID предмета.
        :type item_id: `str`

        :param priority_status_id: ID статуса приоритета, на который нужно изменить.
        :type priority_status_id: `int` or `str`

        :param payment_method_id: Метод оплаты, _опционально_.
        :type payment_method_id: `playerokapi.enums.TransactionPaymentMethodIds` or `None`

        :param transaction_provider_id: ID провайдера транзакции (LOCAL - с баланса кошелька на сайте).
        :type transaction_provider_id: `playerokapi.enums.TransactionProviderIds`
        
        :return: Объект обновлённого предмета.
        :rtype: `playerokapi.types.Item`
        """
        headers = {"accept": "*/*"}
        payload = {
            "operationName": "increaseItemPriorityStatus",
            "query": "mutation increaseItemPriorityStatus($input: PublishItemInput!) {\n  increaseItemPriorityStatus(input: $input) {\n    ...RegularItem\n    __typename\n  }\n}\n\nfragment RegularItem on Item {\n  ...RegularMyItem\n  ...RegularForeignItem\n  __typename\n}\n\nfragment RegularMyItem on MyItem {\n  ...ItemFields\n  prevPrice\n  priority\n  sequence\n  priorityPrice\n  statusExpirationDate\n  comment\n  viewsCounter\n  statusDescription\n  editable\n  statusPayment {\n    ...StatusPaymentTransaction\n    __typename\n  }\n  moderator {\n    id\n    username\n    __typename\n  }\n  approvalDate\n  deletedAt\n  createdAt\n  updatedAt\n  mayBePublished\n  prevFeeMultiplier\n  sellerNotifiedAboutFeeChange\n  __typename\n}\n\nfragment ItemFields on Item {\n  id\n  slug\n  name\n  description\n  rawPrice\n  price\n  attributes\n  status\n  priorityPosition\n  sellerType\n  feeMultiplier\n  user {\n    ...ItemUser\n    __typename\n  }\n  buyer {\n    ...ItemUser\n    __typename\n  }\n  attachments {\n    ...PartialFile\n    __typename\n  }\n  category {\n    ...RegularGameCategory\n    __typename\n  }\n  game {\n    ...RegularGameProfile\n    __typename\n  }\n  comment\n  dataFields {\n    ...GameCategoryDataFieldWithValue\n    __typename\n  }\n  obtainingType {\n    ...GameCategoryObtainingType\n    __typename\n  }\n  __typename\n}\n\nfragment ItemUser on UserFragment {\n  ...UserEdgeNode\n  __typename\n}\n\nfragment UserEdgeNode on UserFragment {\n  ...RegularUserFragment\n  __typename\n}\n\nfragment RegularUserFragment on UserFragment {\n  id\n  username\n  role\n  avatarURL\n  isOnline\n  isBlocked\n  rating\n  testimonialCounter\n  createdAt\n  supportChatId\n  systemChatId\n  __typename\n}\n\nfragment PartialFile on File {\n  id\n  url\n  __typename\n}\n\nfragment RegularGameCategory on GameCategory {\n  id\n  slug\n  name\n  categoryId\n  gameId\n  obtaining\n  options {\n    ...RegularGameCategoryOption\n    __typename\n  }\n  props {\n    ...GameCategoryProps\n    __typename\n  }\n  noCommentFromBuyer\n  instructionForBuyer\n  instructionForSeller\n  useCustomObtaining\n  autoConfirmPeriod\n  autoModerationMode\n  agreements {\n    ...RegularGameCategoryAgreement\n    __typename\n  }\n  feeMultiplier\n  __typename\n}\n\nfragment RegularGameCategoryOption on GameCategoryOption {\n  id\n  group\n  label\n  type\n  field\n  value\n  valueRangeLimit {\n    min\n    max\n    __typename\n  }\n  __typename\n}\n\nfragment GameCategoryProps on GameCategoryPropsObjectType {\n  minTestimonials\n  minTestimonialsForSeller\n  __typename\n}\n\nfragment RegularGameCategoryAgreement on GameCategoryAgreement {\n  description\n  gameCategoryId\n  gameCategoryObtainingTypeId\n  iconType\n  id\n  sequence\n  __typename\n}\n\nfragment RegularGameProfile on GameProfile {\n  id\n  name\n  type\n  slug\n  logo {\n    ...PartialFile\n    __typename\n  }\n  __typename\n}\n\nfragment GameCategoryDataFieldWithValue on GameCategoryDataFieldWithValue {\n  id\n  label\n  type\n  inputType\n  copyable\n  hidden\n  required\n  value\n  __typename\n}\n\nfragment GameCategoryObtainingType on GameCategoryObtainingType {\n  id\n  name\n  description\n  gameCategoryId\n  noCommentFromBuyer\n  instructionForBuyer\n  instructionForSeller\n  sequence\n  feeMultiplier\n  agreements {\n    ...MinimalGameCategoryAgreement\n    __typename\n  }\n  props {\n    minTestimonialsForSeller\n    __typename\n  }\n  __typename\n}\n\nfragment MinimalGameCategoryAgreement on GameCategoryAgreement {\n  description\n  iconType\n  id\n  sequence\n  __typename\n}\n\nfragment StatusPaymentTransaction on Transaction {\n  id\n  operation\n  direction\n  providerId\n  status\n  statusDescription\n  statusExpirationDate\n  value\n  props {\n    paymentURL\n    __typename\n  }\n  __typename\n}\n\nfragment RegularForeignItem on ForeignItem {\n  ...ItemFields\n  __typename\n}",
            "variables": {
                "input": {
                    "itemId": item_id,
                    "priorityStatuses": [priority_status_id],
                    "transactionProviderData": {
                        "paymentMethodId": payment_method_id.name if payment_method_id else None
                    },
                    "transactionProviderId": transaction_provider_id.name
                }
            }
        }
        r = self.request("post", f"{self.base_url}/graphql", headers, payload).json()
        return item(r["data"]["increaseItemPriorityStatus"])

    def get_transaction_providers(self, direction: TransactionProviderDirections = TransactionProviderDirections.IN) -> list[types.TransactionProvider]:
        """
        Получает все провайдеры транзакций.

        :param direction: Направление транзакций (пополнение/вывод).
        :type direction: `playerokapi.enums.TransactionProviderDirections`
        
        :return: Список провайдеров транзакий.
        :rtype: `list` of `playerokapi.types.TransactionProvider`
        """
        headers = {"accept": "*/*"}
        payload = {
            "operationName": "transactionProviders",
            "variables": json.dumps({"filter": {"direction": direction.name if direction else None}}, ensure_ascii=False),
            "extensions": json.dumps({"persistedQuery": {"version": 1, "sha256Hash": PERSISTED_QUERIES.get("transactionProviders")}}, ensure_ascii=False)
        }
        r = self.request("get", f"{self.base_url}/graphql", headers, payload).json()
        return [transaction_provider(provider) for provider in r["data"]["transactionProviders"]]

    def get_transactions(self, count: int = 24, operation: TransactionOperations | None = None, min_value: int | None = None,
                         max_value: int | None = None, provider_id: TransactionProviderIds | None = None, status: TransactionStatuses | None = None,
                         after_cursor: str | None = None) -> TransactionList:
        """
        Получает все транзакции аккаунта.

        :param count: Кол-во транзакциий которые нужно получить (не более 24 за один запрос).
        :type count: `int`

        :param operation: Операция транзакции, _опционально_.
        :type operation: `playerokapi.enums.TransactionOperations` or `None`

        :param min_value: Минимальная сумма транзакции, _опционально_.
        :type min_value: `int` or `None`

        :param max_value: Максимальная сумма транзакции, _опционально_.
        :type max_value: `int` or `None`

        :param provider_id: ID провайдера транзакции, _опционально_.
        :type provider_id: `playerokapi.enums.TransactionProviderIds` or `None`

        :param status: Статус транзакции, _опционально_.
        :type status: `playerokapi.enums.TransactionStatuses` or `None`

        :param after_cursor: Курсор, с которого будет идти парсинг (если нету - ищет с самого начала страницы), _опционально_.
        :type after_cursor: `str` or `None`
        
        :return: Страница транзакций.
        :rtype: `playerokapi.types.TransactionList`
        """
        headers = {"accept": "*/*"}
        payload = {
            "operationName": "transactions",
            "variables": {"pagination": {"first": count, "after": after_cursor}, "filter": {"userId": self.id}, "hasSupportAccess": False},
            "extensions": json.dumps({"persistedQuery": {"version": 1, "sha256Hash": PERSISTED_QUERIES.get("transactions")}}, ensure_ascii=False)
        }
        if operation: payload["variables"]["filter"]["operation"] = [operation.name]
        if min_value or max_value:
            payload["variables"]["filter"]["value"] = {}
            if min_value: payload["variables"]["filter"]["value"]["min"] = str(min_value)
            if max_value: payload["variables"]["filter"]["value"]["max"] = str(max_value)
        if provider_id: payload["variables"]["filter"]["providerId"] = [provider_id.name]
        if status: payload["variables"]["filter"]["status"] = [status.name]
        payload["variables"] = json.dumps(payload["variables"], ensure_ascii=False),
        r = self.request("get", f"{self.base_url}/graphql", headers, payload).json()
        return transaction_list(r["data"]["transactions"])
    
    def get_sbp_bank_members(self) -> list[SBPBankMember]:
        """
        Получает всех членов банка СБП.

        :return: Объект провайдера транзакции.
        :rtype: `list` of `playerokapi.types.SBPBankMember`
        """
        headers = {"accept": "*/*"}
        payload = {
            "operationName": "SbpBankMembers",
            "variables": json.dumps({}, ensure_ascii=False),
            "extensions": json.dumps({"persistedQuery": {"version": 1, "sha256Hash": PERSISTED_QUERIES.get("SbpBankMembers")}}, ensure_ascii=False)
        }
        r = self.request("get", f"{self.base_url}/graphql", headers, payload).json()
        return [sbp_bank_member(member) for member in r["data"]["sbpBankMembers"]]
    
    def get_verified_cards(self, count: int = 24, after_cursor: str | None = None,
                           direction: SortDirections = SortDirections.ASC) -> types.UserBankCardList:
        """
        Получает верифицированные карты аккаунта.

        :param count: Кол-во банковских карт, которые нужно получить (не более 24 за один запрос).
        :type count: `int`

        :param after_cursor: Курсор, с которого будет идти парсинг (если нету - ищет с самого начала страницы), _опционально_.
        :type after_cursor: `str` or `None`

        :param direction: Тип сортировки банковских карт.
        :type direction: `playerokapi.enums.SortDirections`
        
        :return: Страница банковских карт пользователя.
        :rtype: `playerokapi.types.UserBankCardList`
        """
        headers = {"accept": "*/*"}
        payload = {
            "operationName": "verifiedCards",
            "variables": json.dumps({"pagination": {"first": count, "after": after_cursor}, "sort": {"direction": direction.name}, "field": "createdAt"}, ensure_ascii=False),
            "extensions": json.dumps({"persistedQuery": {"version": 1, "sha256Hash": PERSISTED_QUERIES.get("verifiedCards")}}, ensure_ascii=False)
        }
        r = self.request("get", f"{self.base_url}/graphql", headers, payload).json()
        return user_bank_card_list(r["data"]["verifiedCards"])
    
    def delete_card(self, card_id: str) -> bool:
        """
        Удаляет карту из сохранённых в аккаунте.

        :param card_id: ID банковской карты.
        :type card_id: `str`
        
        :return: True, если карта удалилась, иначе False
        :rtype: `bool`
        """
        headers = {"accept": "*/*"}
        payload = {
            "operationName": "deleteCard",
            "query": QUERIES.get("deleteCard"),
            "variables": {
                "input": {
                    "cardId": card_id
                }
            }
        }
        r = self.request("post", f"{self.base_url}/graphql", headers, payload).json()
        return r["data"]["deleteCard"]
    
    def request_withdrawal(self, provider: TransactionProviderIds, account: str, value: int,
                           payment_method_id: TransactionPaymentMethodIds | None = None,
                           sbp_bank_member_id: str | None = None) -> types.Transaction:
        """
        Отправляет запрос на вывод средств с баланса аккаунта.

        :param provider: Провайдер транзакции.
        :type provider: `playerokapi.enums.TransactionProviderIds`

        :param account: ID добавленной карты или номер телефона, если провайдер СБП, на которые нужно совершить вывод.
        :type account: `str`

        :param value: Сумма вывода.
        :type value: `int`

        :param payment_method_id: ID платёжного метода, _опционально_.
        :type payment_method_id: `playerokapi.enums.TransactionPaymentMethodIds` or `None`

        :param sbp_bank_member_id: ID члена банка СБП (только если указан провайдер СБП), _опционально_.
        :type sbp_bank_member_id: `str` or `None`
        
        :return: Объект транзакции вывода.
        :rtype: `playerokapi.types.Transaction`
        """
        headers = {"accept": "*/*"}
        payload = {
            "operationName": "requestWithdrawal",
            "query": QUERIES.get("requestWithdrawal"),
            "variables": {
                "input": {
                    "provider": provider.name,
                    "account": account,
                    "value": value,
                    "providerData": {
                        "paymentMethodId": payment_method_id.name if payment_method_id else None,
                        "sbpBankMemberId": sbp_bank_member_id if sbp_bank_member_id else None
                    }
                }
            }
        }
        r = self.request("post", f"{self.base_url}/graphql", headers, payload).json()
        return transaction(r["data"]["requestWithdrawal"])
    
    def remove_transaction(self, transaction_id: str) -> types.Transaction:
        """
        Удаляет транзакцию (например, можно отменить вывод).

        :param transaction_id: ID транзакции.
        :type transaction_id: `str`
        
        :return: Объект отменённой транзакции.
        :rtype: `playerokapi.types.Transaction`
        """
        headers = {"accept": "*/*"}
        payload = {
            "operationName": "removeTransaction",
            "query": QUERIES.get("removeTransaction"),
            "variables": {
                "id": transaction_id
            }
        }
        r = self.request("post", f"{self.base_url}/graphql", headers, payload).json()
        return transaction(r["data"]["removeTransaction"])
    
    ###

    def _cache_interlocutor(self, chat: types.Chat) -> None:
        """
        Кэширует ID собеседника для чата.
        Автоматически вызывается при получении чатов через get_chats() и get_chat().
        
        :param chat: Объект чата.
        :type chat: `playerokapi.types.Chat`
        """
        if chat.id in self.interlocutor_ids:
            return  # Уже закэширован
        
        # Ищем собеседника среди участников чата
        if not chat.users:
            return
        
        for user in chat.users:
            if user.id != self.id:
                # Нашли собеседника (не наш ID)
                self.interlocutor_ids[chat.id] = user.id
                self.__logger.debug(
                    f"Закэширован interlocutor для чата {chat.id}: "
                    f"user_id={user.id}, username={user.username}"
                )
                return
    
    def get_interlocutor_id(self, chat_id: str) -> str | None:
        """
        Быстро получает ID собеседника из кэша по ID чата.
        
        :param chat_id: ID чата.
        :type chat_id: `str`
        
        :return: ID собеседника или None, если чат не найден в кэше.
        :rtype: `str` or `None`
        """
        return self.interlocutor_ids.get(chat_id)
    
    def get_interlocutor_profile(self, chat_id: str) -> types.UserProfile | None:
        """
        Получает полный профиль собеседника по ID чата.
        
        :param chat_id: ID чата.
        :type chat_id: `str`
        
        :return: Профиль собеседника или None.
        :rtype: `playerokapi.types.UserProfile` or `None`
        """
        user_id = self.get_interlocutor_id(chat_id)
        if not user_id:
            self.__logger.warning(
                f"Не удалось найти interlocutor_id для чата {chat_id}. "
                f"Возможно, чат еще не был получен через get_chats() или get_chat()."
            )
            return None
        
        return self.get_user_profile(user_id)
    
    def get_chats_with_user(self, user_id: str) -> list[str]:
        """
        Находит все чаты с конкретным пользователем в кэше.
        
        :param user_id: ID пользователя.
        :type user_id: `str`
        
        :return: Список chat_id, в которых участвует данный пользователь.
        :rtype: `list[str]`
        """
        return [
            chat_id 
            for chat_id, cached_user_id in self.interlocutor_ids.items() 
            if cached_user_id == user_id
        ]
    
    def get_chat_by_interlocutor_id(self, user_id: str) -> types.Chat | None:
        """
        Получает чат по ID собеседника (обратное к get_interlocutor_id).
        Возвращает первый найденный чат с этим пользователем из кэша.
        
        :param user_id: ID пользователя (собеседника).
        :type user_id: `str`
        
        :return: Объект чата или None, если чат не найден в кэше.
        :rtype: `playerokapi.types.Chat` or `None`
        
        Примечание:
            Если с пользователем несколько чатов, вернется первый найденный.
            Используйте get_chats_with_user() для получения всех чатов.
        """
        # Ищем chat_id в кэше
        chat_id = None
        for cid, uid in self.interlocutor_ids.items():
            if uid == user_id:
                chat_id = cid
                break
        
        if not chat_id:
            self.__logger.warning(
                f"Чат с пользователем {user_id} не найден в кэше. "
                f"Попробуйте использовать get_chat_by_username() или загрузите чаты через get_chats()."
            )
            return None
        
        # Получаем полный объект чата
        return self.get_chat(chat_id)
    
    def get_chat_objects_with_user(self, user_id: str) -> list[types.Chat]:
        """
        Получает все объекты чатов с конкретным пользователем.
        
        :param user_id: ID пользователя (собеседника).
        :type user_id: `str`
        
        :return: Список объектов Chat с этим пользователем.
        :rtype: `list[playerokapi.types.Chat]`
        
        Примечание:
            Делает HTTP запрос для каждого чата. Для больших списков может быть медленным.
        """
        chat_ids = self.get_chats_with_user(user_id)
        
        if not chat_ids:
            self.__logger.info(f"Чатов с пользователем {user_id} не найдено в кэше")
            return []
        
        chats = []
        for chat_id in chat_ids:
            try:
                chat = self.get_chat(chat_id)
                chats.append(chat)
            except Exception as e:
                self.__logger.error(f"Ошибка получения чата {chat_id}: {e}")
        
        return chats
    
    def clear_interlocutor_cache(self, chat_id: str | None = None) -> None:
        """
        Очищает кэш interlocutor_ids.
        
        :param chat_id: ID конкретного чата для очистки. Если None - очищает весь кэш.
        :type chat_id: `str` or `None`
        """
        if chat_id:
            if chat_id in self.interlocutor_ids:
                del self.interlocutor_ids[chat_id]
                self.__logger.debug(f"Очищен кэш interlocutor для чата {chat_id}")
        else:
            self.interlocutor_ids.clear()
            self.__logger.debug("Очищен весь кэш interlocutor_ids")
    
    # ========================================================================
    # Методы для работы напрямую с user_id (обертки над методами с chat_id)
    # ========================================================================
    
    def send_message_to_user(self, user_id: str, text: str | None = None,
                            photo_file_path: str | None = None, 
                            mark_chat_as_read: bool = False) -> types.ChatMessage | None:
        """
        Отправляет сообщение пользователю по его ID (в первый найденный чат).
        
        :param user_id: ID пользователя (собеседника).
        :type user_id: `str`
        
        :param text: Текст сообщения, _опционально_.
        :type text: `str` or `None`
        
        :param photo_file_path: Путь к файлу фотографии, _опционально_.
        :type photo_file_path: `str` or `None`
        
        :param mark_chat_as_read: Пометить чат как прочитанный перед отправкой, _опционально_.
        :type mark_chat_as_read: `bool`
        
        :return: Объект отправленного сообщения или None, если чат не найден.
        :rtype: `playerokapi.types.ChatMessage` or `None`
        
        Примечание:
            Если с пользователем несколько чатов, отправится в первый найденный.
            Используйте send_message_to_user_all_chats() для отправки во все чаты.
        """
        chat = self.get_chat_by_interlocutor_id(user_id)
        
        if not chat:
            self.__logger.warning(f"Не удалось отправить сообщение пользователю {user_id}: чат не найден")
            return None
        
        return self.send_message(chat.id, text, photo_file_path, mark_chat_as_read)
    
    def send_message_to_user_all_chats(self, user_id: str, text: str | None = None,
                                      photo_file_path: str | None = None,
                                      mark_chat_as_read: bool = False) -> list[types.ChatMessage]:
        """
        Отправляет сообщение пользователю во ВСЕ его чаты.
        
        :param user_id: ID пользователя (собеседника).
        :type user_id: `str`
        
        :param text: Текст сообщения, _опционально_.
        :type text: `str` or `None`
        
        :param photo_file_path: Путь к файлу фотографии, _опционально_.
        :type photo_file_path: `str` or `None`
        
        :param mark_chat_as_read: Пометить чаты как прочитанные перед отправкой, _опционально_.
        :type mark_chat_as_read: `bool`
        
        :return: Список объектов отправленных сообщений.
        :rtype: `list[playerokapi.types.ChatMessage]`
        
        Примечание:
            Полезно для массовой рассылки одному клиенту по всем его сделкам.
        """
        chat_ids = self.get_chats_with_user(user_id)
        
        if not chat_ids:
            self.__logger.warning(f"Не удалось отправить сообщения пользователю {user_id}: чаты не найдены")
            return []
        
        messages = []
        for chat_id in chat_ids:
            try:
                msg = self.send_message(chat_id, text, photo_file_path, mark_chat_as_read)
                messages.append(msg)
                self.__logger.debug(f"Сообщение отправлено пользователю {user_id} в чат {chat_id}")
            except Exception as e:
                self.__logger.error(f"Ошибка отправки сообщения в чат {chat_id}: {e}")
        
        return messages
    
    def get_user_messages(self, user_id: str, count: int = 24,
                         after_cursor: str | None = None) -> types.ChatMessageList | None:
        """
        Получает сообщения из чата с пользователем по его ID.
        
        :param user_id: ID пользователя (собеседника).
        :type user_id: `str`
        
        :param count: Количество сообщений для получения (не более 24 за запрос).
        :type count: `int`
        
        :param after_cursor: Курсор для пагинации, _опционально_.
        :type after_cursor: `str` or `None`
        
        :return: Страница сообщений или None, если чат не найден.
        :rtype: `playerokapi.types.ChatMessageList` or `None`
        
        Примечание:
            Если с пользователем несколько чатов, вернутся сообщения из первого.
        """
        chat = self.get_chat_by_interlocutor_id(user_id)
        
        if not chat:
            self.__logger.warning(f"Не удалось получить сообщения с пользователем {user_id}: чат не найден")
            return None
        
        return self.get_chat_messages(chat.id, count, after_cursor)
    
    def mark_user_chat_as_read(self, user_id: str, all_chats: bool = False) -> bool:
        """
        Помечает чат(ы) с пользователем как прочитанные.
        
        :param user_id: ID пользователя (собеседника).
        :type user_id: `str`
        
        :param all_chats: Пометить все чаты с пользователем или только первый.
        :type all_chats: `bool`
        
        :return: True если хотя бы один чат помечен, False если чаты не найдены.
        :rtype: `bool`
        """
        if all_chats:
            chat_ids = self.get_chats_with_user(user_id)
            if not chat_ids:
                self.__logger.warning(f"Чаты с пользователем {user_id} не найдены")
                return False
            
            success = False
            for chat_id in chat_ids:
                try:
                    self.mark_chat_as_read(chat_id)
                    success = True
                except Exception as e:
                    self.__logger.error(f"Ошибка при пометке чата {chat_id} как прочитанного: {e}")
            
            return success
        else:
            chat = self.get_chat_by_interlocutor_id(user_id)
            if not chat:
                self.__logger.warning(f"Чат с пользователем {user_id} не найден")
                return False
            
            try:
                self.mark_chat_as_read(chat.id)
                return True
            except Exception as e:
                self.__logger.error(f"Ошибка при пометке чата как прочитанного: {e}")
                return False