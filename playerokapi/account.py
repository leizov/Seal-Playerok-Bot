from __future__ import annotations
from typing import *
from logging import getLogger
from typing import Literal
import json
import random
import time
import email.utils
import tempfile
import shutil
import hashlib
import re
import uuid
from urllib.parse import urlsplit
from datetime import datetime
from curl_cffi.requests import Session as CurlSession, Response as CurlResponse, exceptions as curl_exceptions
from curl_cffi import CurlMime
from .misc import *
import os
from . import types
from .exceptions import *
from .parser import *
from .enums import *
import websocket

try:
    from core.error_stats import (
        record_playerok_request_error as _record_playerok_request_error,
        record_playerok_request_success as _record_playerok_request_success,
    )
except Exception:
    _record_playerok_request_error = None
    _record_playerok_request_success = None


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

    def _resolve_runtime_cert_dir(self) -> str:
        return os.path.join(
            tempfile.gettempdir(),
            "sealplayerokbot",
            "certs",
            self._build_bot_identity_digest(),
        )

    def _build_bot_identity_digest(self) -> str:
        identity_parts: list[str] = []
        try:
            import paths as app_paths

            root_dir = getattr(app_paths, "ROOT_DIR", None)
            if root_dir:
                identity_parts.append(os.path.abspath(str(root_dir)))
        except Exception:
            pass

        if not identity_parts:
            identity_parts.append(os.path.abspath(os.getcwd()))

        identity_parts.append(os.path.abspath(os.path.dirname(__file__)))

        try:
            user_identity = str(os.getuid())
        except Exception:
            user_identity = os.environ.get("USERNAME") or os.environ.get("USER") or "unknown-user"

        identity_parts.append(user_identity)
        identity_seed = "|".join(identity_parts)
        return hashlib.sha256(identity_seed.encode("utf-8", errors="ignore")).hexdigest()[:16]

    def _build_bot_cert_name(self) -> str:
        return f"cacert-{self._build_bot_identity_digest()}.pem"

    def _is_usable_cert(self, cert_path: str) -> bool:
        if not cert_path:
            return False
        try:
            if not os.path.isfile(cert_path):
                return False
            if os.path.getsize(cert_path) <= 0:
                return False
            with open(cert_path, "rb") as cert_file:
                return bool(cert_file.read(1))
        except PermissionError:
            return False
        except Exception:
            return False

    def _list_temp_cert_candidates(self, include_global_fallback: bool = True) -> list[str]:
        temp_root = tempfile.gettempdir()
        runtime_cert_dir = self._resolve_runtime_cert_dir()
        preferred_cert_path = os.path.join(runtime_cert_dir, self._build_bot_cert_name())
        preferred_norm = os.path.normcase(os.path.abspath(preferred_cert_path))
        runtime_dir_norm = os.path.normcase(os.path.abspath(runtime_cert_dir))

        candidates: list[str] = []
        seen_paths: set[str] = set()

        def _add_candidate(path: str) -> None:
            if not path:
                return
            abs_path = os.path.abspath(path)
            normalized = os.path.normcase(abs_path)
            if normalized in seen_paths:
                return
            seen_paths.add(normalized)
            if self._is_usable_cert(abs_path):
                candidates.append(abs_path)

        def _candidate_sort_key(path: str) -> tuple[int, int, float]:
            normalized = os.path.normcase(os.path.abspath(path))
            is_preferred = 1 if normalized == preferred_norm else 0
            in_runtime_dir = 1 if os.path.normcase(os.path.dirname(os.path.abspath(path))) == runtime_dir_norm else 0
            try:
                mtime = os.path.getmtime(path)
            except Exception:
                mtime = 0.0
            return (is_preferred, in_runtime_dir, mtime)

        _add_candidate(preferred_cert_path)

        try:
            if os.path.isdir(runtime_cert_dir):
                for entry in os.scandir(runtime_cert_dir):
                    try:
                        if not entry.is_file():
                            continue
                    except Exception:
                        continue
                    name_lower = entry.name.lower()
                    if not name_lower.endswith(".pem"):
                        continue
                    if "cert" not in name_lower and "ca" not in name_lower:
                        continue
                    _add_candidate(entry.path)
        except Exception:
            pass

        if not candidates and include_global_fallback:
            def _walk_error(_err: OSError) -> None:
                return

            try:
                for root, _, files in os.walk(temp_root, onerror=_walk_error):
                    for file_name in files:
                        file_name_lower = file_name.lower()
                        if not file_name_lower.endswith(".pem"):
                            continue
                        if "cert" not in file_name_lower and "ca" not in file_name_lower:
                            continue
                        _add_candidate(os.path.join(root, file_name))
            except Exception:
                pass

        candidates.sort(key=_candidate_sort_key, reverse=True)
        return candidates

    def _copy_cert_to_runtime_path(self, target_path: str, _attempt_label: str) -> bool:
        tmp_copy_path = f"{target_path}.tmp-{os.getpid()}-{int(time.time() * 1000)}"
        try:
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            shutil.copyfile(self._cert_path, tmp_copy_path)
            try:
                os.chmod(tmp_copy_path, 0o600)
            except Exception:
                pass
            os.replace(tmp_copy_path, target_path)
            try:
                os.chmod(target_path, 0o600)
            except Exception:
                pass
            self._runtime_cert_path = target_path
            return True
        except Exception:
            try:
                if os.path.exists(tmp_copy_path):
                    os.remove(tmp_copy_path)
            except Exception:
                pass
            return False

    def _build_verify_candidates(self) -> list[str]:
        candidates: list[str] = []
        seen_paths: set[str] = set()

        def _append_candidate(path: str | None) -> None:
            if not path:
                return
            abs_path = os.path.abspath(path)
            normalized = os.path.normcase(abs_path)
            if normalized in seen_paths:
                return
            seen_paths.add(normalized)
            candidates.append(abs_path)

        _append_candidate(getattr(self, "_runtime_cert_path", None))
        for temp_candidate in self._list_temp_cert_candidates(include_global_fallback=True):
            _append_candidate(temp_candidate)
        _append_candidate(getattr(self, "_cert_path", None))
        return candidates

    def _prepare_runtime_cert_file(self) -> None:
        self._cert_path = os.path.join(os.path.dirname(__file__), "cacert.pem")
        runtime_cert_dir = self._resolve_runtime_cert_dir()
        runtime_cert_path = os.path.join(runtime_cert_dir, self._build_bot_cert_name())

        if self._is_usable_cert(runtime_cert_path):
            self._runtime_cert_path = runtime_cert_path
            return

        if self._copy_cert_to_runtime_path(runtime_cert_path, "primary"):
            return

        fallback_candidates = self._list_temp_cert_candidates(include_global_fallback=True)
        if fallback_candidates:
            self._runtime_cert_path = fallback_candidates[0]
            return

        if self._copy_cert_to_runtime_path(runtime_cert_path, "retry"):
            return

        self._runtime_cert_path = self._cert_path

    def __init__(
            self,
            token: str,
            user_agent: str = "",
            proxy: str = None,
            requests_timeout: int = 10,
            request_max_retries: int = 7,
            auid: str = None,
            cookies: str = "",
            cookie_persist_debounce_seconds: int = 30,
        ):
        if hasattr(self, "_initialized"):
            # Singleton Account может остаться в полусозданном состоянии
            # (например, если инициализация оборвалась до создания curl-сессии).
            # Повторный вызов __init__ должен уметь восстановить рабочее состояние.
            self.token = token
            self.user_agent = user_agent
            self.auid = auid
            self.cookie_persist_debounce_seconds = max(5, int(cookie_persist_debounce_seconds or 30))
            self.requests_timeout = requests_timeout
            self.proxy = proxy
            self.base_url = "https://playerok.com"
            if not hasattr(self, "_cookie_header"):
                self._cookie_header = ""
            if not hasattr(self, "cookies"):
                self.cookies = {}
            if not hasattr(self, "_last_cookie_persist_ts"):
                self._last_cookie_persist_ts = 0.0
            if not hasattr(self, "_last_persisted_cookie_header"):
                self._last_persisted_cookie_header = ""

            if self.proxy:
                if self.proxy.startswith("socks5://") or self.proxy.startswith("socks4://"):
                    self.__proxy_string = self.proxy
                else:
                    clean_proxy = self.proxy.replace("https://", "").replace("http://", "")
                    self.__proxy_string = f"http://{clean_proxy}"
            else:
                self.__proxy_string = None

            self._prepare_playwright_runtime_paths()
            self.request_max_retries = request_max_retries
            if not hasattr(self, "id"):
                self.id = None
            if not hasattr(self, "username"):
                self.username = None
            if not hasattr(self, "profile"):
                self.profile = None
            if not hasattr(self, "interlocutor_ids"):
                self.interlocutor_ids = {}
            if not hasattr(self, "_Account__curl_session"):
                self.__curl_session = None

            if not hasattr(self, "_Account__logger"):
                self.__logger = getLogger("playerokapi")
            self._apply_cookie_header(cookies, persist=False)
            self._prepare_runtime_cert_file()

            try:
                self._refresh_clients()
            except Exception:
                try:
                    delattr(self, "_initialized")
                except Exception:
                    pass
                raise
            return

        self.token = token
        """ Токен сессии аккаунта. """
        self.user_agent = user_agent
        """ Юзер-агент браузера. """
        self.auid = auid
        self.cookie_persist_debounce_seconds = max(5, int(cookie_persist_debounce_seconds or 30))
        self.requests_timeout = requests_timeout
        """ Таймаут ожидания ответов на запросы. """
        self.proxy = proxy
        """ Прокси. """
        self.base_url = "https://playerok.com"
        self._cookie_header = ""
        self.cookies: dict[str, str] = {}
        self._last_cookie_persist_ts = 0.0
        self._last_persisted_cookie_header = ""
        """ Базовый URL для всех запросов. """
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

        self._prepare_playwright_runtime_paths()
        self._apply_cookie_header(cookies, persist=False)
        self.request_max_retries = request_max_retries
        """ Максимальное количество повторных попыток отправки запроса. """

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

        self.__logger = getLogger("playerokapi")
        self._prepare_runtime_cert_file()
        self.__curl_session = None

        self._refresh_clients()
        self._initialized = True

    def _refresh_clients(self):
        """Cоздаёт/пересоздаёт curl-cffi сессию с актуальными настройками."""
        # Закрываем старую сессию если есть
        if hasattr(self, '_Account__curl_session') and self.__curl_session:
            try:
                self.__curl_session.close()
            except:
                pass

        verify_candidates = self._build_verify_candidates()
        last_session_error: Exception | None = None

        for verify_path in verify_candidates:
            try:
                self.__curl_session = CurlSession(
                    impersonate="chrome120",
                    proxy=self.__proxy_string,
                    timeout=self.requests_timeout,
                    verify=verify_path,
                )
                self._runtime_cert_path = verify_path
                try:
                    self._apply_cookie_header(self._build_default_cookie_header(), persist=False)
                except Exception:
                    pass
                return
            except Exception as session_error:
                last_session_error = session_error

        if last_session_error is not None:
            raise last_session_error

        # Крайний fallback: системная верификация без явного cert-файла.
        self.__curl_session = CurlSession(
            impersonate="chrome120",
            proxy=self.__proxy_string,
            timeout=self.requests_timeout,
        )

        try:
            self._apply_cookie_header(self._build_default_cookie_header(), persist=False)
        except Exception:
            pass

    @staticmethod
    def _parse_cookie_header(cookie_header: str | None) -> dict[str, str]:
        parsed: dict[str, str] = {}
        raw = str(cookie_header or "").strip()
        if not raw:
            return parsed

        for part in raw.split(";"):
            chunk = part.strip()
            if not chunk or "=" not in chunk:
                continue
            key, value = chunk.split("=", 1)
            key = key.strip()
            if not key:
                continue
            parsed[key] = value.strip()
        return parsed

    @staticmethod
    def _normalize_cookie_map(cookie_map: Mapping[str, Any] | None) -> dict[str, str]:
        normalized: dict[str, str] = {}
        if not isinstance(cookie_map, Mapping):
            return normalized
        for key, value in cookie_map.items():
            cookie_key = str(key or "").strip()
            if not cookie_key:
                continue
            normalized[cookie_key] = str(value or "").strip()
        return normalized

    def _serialize_cookie_map(self, cookie_map: Mapping[str, Any] | None) -> str:
        normalized = self._normalize_cookie_map(cookie_map)
        if not normalized:
            return ""

        ordered_keys: list[str] = []
        if "token" in normalized:
            ordered_keys.append("token")
        if "auid" in normalized and "auid" not in ordered_keys:
            ordered_keys.append("auid")

        for key in sorted(normalized.keys()):
            if key not in ordered_keys:
                ordered_keys.append(key)

        return "; ".join(f"{key}={normalized[key]}" for key in ordered_keys)

    def _build_default_cookie_header(self) -> str:
        cookie_map = self._normalize_cookie_map(getattr(self, "cookies", None))
        if self.token and not cookie_map.get("token"):
            cookie_map["token"] = str(self.token)
        if self.auid and not cookie_map.get("auid"):
            cookie_map["auid"] = str(self.auid)
        return self._serialize_cookie_map(cookie_map)

    def _persist_cookie_state_if_needed(self, force: bool = False) -> None:
        cookie_header = self._build_default_cookie_header()
        if not cookie_header:
            return

        now_ts = time.time()
        if not force:
            if cookie_header == str(getattr(self, "_last_persisted_cookie_header", "") or ""):
                return
            debounce_seconds = max(5, int(getattr(self, "cookie_persist_debounce_seconds", 30) or 30))
            last_ts = float(getattr(self, "_last_cookie_persist_ts", 0.0) or 0.0)
            if now_ts - last_ts < debounce_seconds:
                return

        try:
            from settings import Settings as sett

            config = sett.get("config") or {}
            playerok_cfg = config.setdefault("playerok", {})
            api_cfg = playerok_cfg.setdefault("api", {})

            changed = False
            if str(api_cfg.get("cookies") or "") != cookie_header:
                api_cfg["cookies"] = cookie_header
                changed = True

            token_value = str(self.token or "").strip()
            if token_value and str(api_cfg.get("token") or "") != token_value:
                api_cfg["token"] = token_value
                changed = True

            if changed:
                sett.set("config", config)
                self._last_cookie_persist_ts = now_ts
                self._last_persisted_cookie_header = cookie_header
        except Exception as persist_error:
            self.__logger.debug(f"Не удалось сохранить cookies в config: {persist_error}")

    def _apply_cookie_header(self, cookie_header: str | None, persist: bool = False) -> None:
        parsed = self._parse_cookie_header(cookie_header)
        if self.token and not parsed.get("token"):
            parsed["token"] = str(self.token)
        if self.auid and not parsed.get("auid"):
            parsed["auid"] = str(self.auid)

        self.cookies = parsed
        self._cookie_header = self._serialize_cookie_map(parsed)

        token_value = str(parsed.get("token") or "").strip()
        if token_value:
            self.token = token_value

        auid_value = str(parsed.get("auid") or "").strip()
        if auid_value:
            self.auid = auid_value

        session_obj = getattr(self, "_Account__curl_session", None)
        cookie_jar = getattr(session_obj, "cookies", None)
        if cookie_jar is not None:
            for key, value in parsed.items():
                if not value:
                    continue
                try:
                    cookie_jar.set(key, value, domain=".playerok.com", path="/")
                except Exception:
                    try:
                        cookie_jar.set(key, value)
                    except Exception:
                        pass

        if persist:
            self._persist_cookie_state_if_needed(force=True)

    def apply_external_cookie_header(self, cookie_header: str) -> None:
        """
        Применяет cookies, синхронизирует token/auid и сохраняет изменения в config.
        """
        self._apply_cookie_header(cookie_header, persist=True)

    def _sync_cookies_from_response(self, response: CurlResponse | None) -> None:
        merged = self._normalize_cookie_map(getattr(self, "cookies", None))

        def _merge_cookie_container(container: Any) -> None:
            if container is None:
                return
            try:
                iterator = iter(container)
            except Exception:
                iterator = []
            for cookie in iterator:
                name = str(getattr(cookie, "name", "") or "").strip()
                if not name:
                    continue
                value = str(getattr(cookie, "value", "") or "").strip()
                if not value:
                    continue
                merged[name] = value

        try:
            _merge_cookie_container(getattr(response, "cookies", None))
        except Exception:
            pass

        try:
            session_obj = getattr(self, "_Account__curl_session", None)
            _merge_cookie_container(getattr(session_obj, "cookies", None))
        except Exception:
            pass

        if self.token and not merged.get("token"):
            merged["token"] = str(self.token)
        if self.auid and not merged.get("auid"):
            merged["auid"] = str(self.auid)

        new_cookie_header = self._serialize_cookie_map(merged)
        if not new_cookie_header:
            return

        if new_cookie_header != str(getattr(self, "_cookie_header", "") or ""):
            self.cookies = merged
            self._cookie_header = new_cookie_header
            if merged.get("token"):
                self.token = str(merged["token"])
            if merged.get("auid"):
                self.auid = str(merged["auid"])

        self._persist_cookie_state_if_needed(force=False)

    def _prepare_playwright_runtime_paths(self) -> None:
        auid_seed = str(self.auid or "")
        ua_seed = str(self.user_agent or "")
        proxy_seed = str(getattr(self, "_Account__proxy_string", "") or "")
        identity_seed = f"{auid_seed}|{ua_seed}|{proxy_seed}|{self.base_url}"
        digest = hashlib.sha256(identity_seed.encode("utf-8", errors="ignore")).hexdigest()[:16]

        runtime_dir = os.path.join(tempfile.gettempdir(), "sealplayerokbot", "playwright", digest)
        self.playwright_runtime_dir = runtime_dir
        self.user_data_dir = os.path.join(runtime_dir, "user-data")
        self.storage_state_path = os.path.join(runtime_dir, "storage-state.json")

        try:
            os.makedirs(self.user_data_dir, exist_ok=True)
        except Exception:
            pass

    def request_email_auth_code(self, email: str) -> bool:
        email_value = str(email or "").strip()
        if not email_value:
            raise ValueError("auth email is empty")

        payload = {
            "operationName": "getEmailAuthCode",
            "variables": {"email": email_value},
            "query": QUERIES.get("getEmailAuthCode"),
        }
        response = self.request(
            "post",
            f"{self.base_url}/graphql",
            {"accept": "*/*"},
            payload,
        )
        response_json = response.json() or {}
        return bool((response_json.get("data") or {}).get("getEmailAuthCode"))

    def verify_email_auth_code(self, email: str, code: str) -> dict[str, Any]:
        email_value = str(email or "").strip()
        code_value = re.sub(r"\D+", "", str(code or ""))
        if not email_value:
            raise ValueError("auth email is empty")
        if not code_value:
            raise ValueError("otp code is empty")

        payload = {
            "operationName": "checkEmailAuthCode",
            "variables": {"input": {"email": email_value, "code": code_value}},
            "query": QUERIES.get("checkEmailAuthCode"),
        }
        response = self.request(
            "post",
            f"{self.base_url}/graphql",
            {"accept": "*/*"},
            payload,
        )
        response_json = response.json() or {}
        viewer_data = (response_json.get("data") or {}).get("checkEmailAuthCode")
        if not isinstance(viewer_data, dict):
            raise UnauthorizedError()
        return viewer_data

    @staticmethod
    def _detect_antibot_vendor_from_html(text: str | None) -> str | None:
        if not text:
            return None
        text_l = text.lower()

        ddos_guard_signatures = (
            "<title>ddos-guard</title>",
            "/.well-known/ddos-guard/js-challenge/",
            "check.ddos-guard.net/check.js",
            "подождите несколько секунд",
        )
        cloudflare_signatures = (
            "<title>just a moment...</title>",
            "window._cf_chl_opt",
            "cf-browser-verification",
            "cloudflare ray id",
            "enable javascript and cookies to continue",
        )

        if any(sig in text_l for sig in ddos_guard_signatures):
            return "ddos_guard"
        if any(sig in text_l for sig in cloudflare_signatures):
            return "cloudflare"
        return None

    def _build_playwright_proxy_config(self) -> dict[str, str] | None:
        proxy_string = str(self.__proxy_string or "").strip()
        if not proxy_string:
            return None
        try:
            parsed = urlsplit(proxy_string)
            if not parsed.scheme or not parsed.hostname:
                return {"server": proxy_string}

            server = f"{parsed.scheme}://{parsed.hostname}"
            if parsed.port:
                server = f"{server}:{parsed.port}"

            proxy_cfg: dict[str, str] = {"server": server}
            if parsed.username:
                proxy_cfg["username"] = parsed.username
            if parsed.password:
                proxy_cfg["password"] = parsed.password
            return proxy_cfg
        except Exception:
            return {"server": proxy_string}

    def fetch_browser_snapshot_via_playwright(
        self,
        url: str | None = None,
        wait_seconds: float = 3.0,
        timeout_seconds: float = 45.0,
        force_disable_proxy: bool = False,
        fallback_without_proxy: bool = False,
        ignore_https_errors: bool = False,
        storage_state_path: str | None = None,
        user_data_dir: str | None = None,
        use_persistent_context: bool = True,
        persist_state: bool = True,
        return_empty_on_antibot: bool = False,
        max_antibot_checks: int = 10,
    ) -> dict[str, Any]:
        """
        Запускает Chromium через Playwright и возвращает снимок страницы:
        запрос, ответ, cookies и HTML.
        """
        target_url = str(url or self.base_url).strip() or self.base_url
        wait_ms = max(0, int(float(wait_seconds) * 1000))
        timeout_ms = max(1000, int(float(timeout_seconds) * 1000))
        antibot_checks = max(1, int(max_antibot_checks))

        effective_storage_state_path = str(
            storage_state_path or getattr(self, "storage_state_path", "") or ""
        ).strip()
        effective_user_data_dir = str(
            user_data_dir or getattr(self, "user_data_dir", "") or ""
        ).strip()
        if not effective_user_data_dir:
            effective_user_data_dir = os.path.join(
                tempfile.gettempdir(),
                "sealplayerokbot",
                "playwright",
                "default-user-data",
            )

        self.__logger.info(
            "Playwright: запускаю браузер для получения cookies "
            f"(mode={'persistent' if use_persistent_context else 'ephemeral'}, "
            f"proxy_disabled={force_disable_proxy}, ignore_https_errors={ignore_https_errors})."
        )

        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except Exception as import_error:
            self.__logger.warning(f"Playwright: модуль недоступен ({import_error}).")
            return {
                "ok": False,
                "reason": "playwright_import_error",
                "vendor": None,
                "error": str(import_error),
                "url": {"requested": target_url, "final": ""},
                "title": "",
                "response": {"headers": {}, "text": ""},
                "cookies": {"list": [], "map": {}, "header": ""},
                "meta": {
                    "user_agent": self.user_agent or "",
                    "proxy": "" if force_disable_proxy else (self.__proxy_string or ""),
                    "proxy_disabled": bool(force_disable_proxy),
                    "ignore_https_errors": bool(ignore_https_errors),
                    "context_mode": "persistent" if use_persistent_context else "ephemeral",
                    "user_data_dir": effective_user_data_dir if use_persistent_context else "",
                    "storage_state_path": effective_storage_state_path,
                    "timestamp": int(time.time()),
                },
            }

        browser = None
        context = None
        page = None

        try:
            with sync_playwright() as playwright:
                proxy_cfg = None if force_disable_proxy else self._build_playwright_proxy_config()

                if use_persistent_context:
                    try:
                        os.makedirs(effective_user_data_dir, exist_ok=True)
                    except Exception:
                        pass

                    persistent_kwargs: dict[str, Any] = {
                        "user_data_dir": effective_user_data_dir,
                        "headless": False,
                        "channel": "chromium",
                        "ignore_https_errors": ignore_https_errors,
                        "locale": "ru-RU",
                        "timezone_id": "Europe/Moscow",
                        "viewport": {"width": 1366, "height": 768},
                    }
                    if self.user_agent:
                        persistent_kwargs["user_agent"] = self.user_agent
                    if proxy_cfg:
                        persistent_kwargs["proxy"] = proxy_cfg

                    context = playwright.chromium.launch_persistent_context(**persistent_kwargs)
                    page = context.pages[0] if context.pages else context.new_page()
                else:
                    launch_kwargs: dict[str, Any] = {
                        "headless": False,
                        "channel": "chromium",
                    }
                    if proxy_cfg:
                        launch_kwargs["proxy"] = proxy_cfg
                    browser = playwright.chromium.launch(**launch_kwargs)

                    context_kwargs: dict[str, Any] = {
                        "ignore_https_errors": ignore_https_errors,
                        "locale": "ru-RU",
                        "timezone_id": "Europe/Moscow",
                        "viewport": {"width": 1366, "height": 768},
                    }
                    if self.user_agent:
                        context_kwargs["user_agent"] = self.user_agent
                    if effective_storage_state_path and os.path.exists(effective_storage_state_path):
                        context_kwargs["storage_state"] = effective_storage_state_path

                    context = browser.new_context(**context_kwargs)
                    page = context.new_page()

                initial_cookies: list[dict[str, Any]] = []
                if self.token:
                    initial_cookies.append({
                        "name": "token",
                        "value": str(self.token),
                        "domain": ".playerok.com",
                        "path": "/",
                        "httpOnly": True,
                        "secure": True,
                        "sameSite": "Lax",
                    })
                if self.auid:
                    initial_cookies.append({
                        "name": "auid",
                        "value": str(self.auid),
                        "domain": ".playerok.com",
                        "path": "/",
                        "secure": True,
                        "sameSite": "Lax",
                    })
                if initial_cookies:
                    try:
                        context.add_cookies(initial_cookies)
                    except Exception:
                        pass

                latest_main_response: dict[str, Any] = {}

                def _extract_headers(obj: Any) -> dict[str, str]:
                    try:
                        return dict(obj.all_headers() or {})
                    except Exception:
                        return dict(getattr(obj, "headers", {}) or {})

                def _remember_main_document_response(resp_obj: Any) -> None:
                    try:
                        req_obj = getattr(resp_obj, "request", None)
                        if req_obj is None:
                            return

                        req_resource_type = str(
                            getattr(req_obj, "resource_type", "") or ""
                        ).lower()
                        if req_resource_type != "document":
                            return

                        req_frame = getattr(req_obj, "frame", None)
                        try:
                            main_frame = page.main_frame if page is not None else None
                        except Exception:
                            main_frame = None
                        if req_frame is not None and main_frame is not None and req_frame != main_frame:
                            return

                        latest_main_response["status"] = int(
                            getattr(resp_obj, "status", 0) or 0
                        ) or None
                        latest_main_response["url"] = str(
                            getattr(resp_obj, "url", "") or ""
                        )
                        latest_main_response["headers"] = _extract_headers(resp_obj)
                        latest_main_response["request"] = {
                            "url": str(getattr(req_obj, "url", "") or target_url),
                            "method": str(getattr(req_obj, "method", "GET") or "GET"),
                            "headers": _extract_headers(req_obj),
                            "post_data": getattr(req_obj, "post_data", None),
                            "resource_type": str(
                                getattr(req_obj, "resource_type", "") or "document"
                            ),
                        }
                    except Exception:
                        return

                page.on("response", _remember_main_document_response)

                navigation_response = page.goto(
                    target_url,
                    wait_until="domcontentloaded",
                    timeout=timeout_ms,
                )
                if navigation_response is not None:
                    _remember_main_document_response(navigation_response)
                if wait_ms > 0:
                    page.wait_for_timeout(wait_ms)

                page_html = ""
                antibot_vendor: str | None = None
                for attempt in range(1, antibot_checks + 1):
                    page_html = page.content()
                    antibot_vendor = self._detect_antibot_vendor_from_html(page_html)
                    if antibot_vendor is None:
                        break
                    vendor_title = "DDoS-Guard" if antibot_vendor == "ddos_guard" else "Cloudflare"
                    self.__logger.warning(
                        f"Playwright: обнаружена антибот-страница {vendor_title}. "
                        f"Попытка {attempt}/{antibot_checks}."
                    )
                    if attempt < antibot_checks:
                        page.wait_for_timeout(2000)

                request_info: dict[str, Any] = {
                    "url": target_url,
                    "method": "GET",
                    "headers": {},
                    "post_data": None,
                    "resource_type": "document",
                }
                response_headers: dict[str, str] = dict(
                    latest_main_response.get("headers", {}) or {}
                )
                response_status: int | None = latest_main_response.get("status")
                response_url = str(latest_main_response.get("url") or page.url)

                if isinstance(latest_main_response.get("request"), dict):
                    request_info = dict(latest_main_response.get("request") or request_info)

                browser_cookies = context.cookies()
                cookies_map: dict[str, str] = {}
                for cookie in browser_cookies:
                    name = str(cookie.get("name") or "")
                    if not name:
                        continue
                    cookies_map[name] = str(cookie.get("value") or "")

                try:
                    page_title = page.title()
                except Exception:
                    page_title = ""

                cookie_header = "; ".join(f"{k}={v}" for k, v in cookies_map.items())
                ok = antibot_vendor is None
                reason = None if ok else "antibot_detected"

                if persist_state and effective_storage_state_path:
                    try:
                        os.makedirs(os.path.dirname(effective_storage_state_path), exist_ok=True)
                        context.storage_state(path=effective_storage_state_path)
                    except Exception as save_state_error:
                        self.__logger.warning(
                            f"Playwright: не удалось сохранить storage_state ({save_state_error})."
                        )

                result: dict[str, Any] = {
                    "ok": ok,
                    "reason": reason,
                    "vendor": antibot_vendor,
                    "url": {
                        "requested": target_url,
                        "final": response_url,
                    },
                    "status_code": response_status,
                    "title": page_title,
                    "request": request_info,
                    "response": {
                        "headers": response_headers,
                        "text": page_html,
                    },
                    "cookies": {
                        "list": browser_cookies,
                        "map": cookies_map,
                        "header": cookie_header,
                    },
                    "meta": {
                        "user_agent": self.user_agent or "",
                        "proxy": "" if force_disable_proxy else (self.__proxy_string or ""),
                        "proxy_disabled": bool(force_disable_proxy),
                        "ignore_https_errors": bool(ignore_https_errors),
                        "context_mode": "persistent" if use_persistent_context else "ephemeral",
                        "user_data_dir": effective_user_data_dir if use_persistent_context else "",
                        "storage_state_path": effective_storage_state_path,
                        "timestamp": int(time.time()),
                    },
                }

                if not ok and return_empty_on_antibot:
                    return {}
                self.__logger.info(
                    f"Playwright: данные страницы получены, cookies={len(browser_cookies)}, ok={ok}."
                )
                return result

        except PlaywrightTimeoutError:
            self.__logger.warning("Playwright: таймаут при открытии страницы.")
            return {
                "ok": False,
                "reason": "timeout",
                "vendor": None,
                "url": {"requested": target_url, "final": ""},
                "title": "",
                "response": {"headers": {}, "text": ""},
                "cookies": {"list": [], "map": {}, "header": ""},
                "meta": {
                    "user_agent": self.user_agent or "",
                    "proxy": "" if force_disable_proxy else (self.__proxy_string or ""),
                    "proxy_disabled": bool(force_disable_proxy),
                    "ignore_https_errors": bool(ignore_https_errors),
                    "context_mode": "persistent" if use_persistent_context else "ephemeral",
                    "user_data_dir": effective_user_data_dir if use_persistent_context else "",
                    "storage_state_path": effective_storage_state_path,
                    "timestamp": int(time.time()),
                },
            }
        except Exception as browser_error:
            error_text = str(browser_error or "")
            low_error = error_text.lower()
            can_fallback_without_proxy = (
                fallback_without_proxy
                and not force_disable_proxy
                and bool(self.__proxy_string)
                and (
                    "err_connection_closed" in low_error
                    or "err_tunnel_connection_failed" in low_error
                    or "err_proxy_connection_failed" in low_error
                )
            )

            if can_fallback_without_proxy:
                self.__logger.warning("Playwright: ошибка через прокси, повторяю попытку без прокси.")
                return self.fetch_browser_snapshot_via_playwright(
                    url=target_url,
                    wait_seconds=wait_seconds,
                    timeout_seconds=timeout_seconds,
                    force_disable_proxy=True,
                    fallback_without_proxy=False,
                    ignore_https_errors=ignore_https_errors,
                    storage_state_path=effective_storage_state_path,
                    user_data_dir=effective_user_data_dir,
                    use_persistent_context=use_persistent_context,
                    persist_state=persist_state,
                    return_empty_on_antibot=return_empty_on_antibot,
                    max_antibot_checks=antibot_checks,
                )

            self.__logger.warning(f"Playwright: ошибка браузера ({browser_error}).")
            return {
                "ok": False,
                "reason": "browser_error",
                "vendor": None,
                "error": error_text,
                "url": {"requested": target_url, "final": ""},
                "title": "",
                "response": {"headers": {}, "text": ""},
                "cookies": {"list": [], "map": {}, "header": ""},
                "meta": {
                    "user_agent": self.user_agent or "",
                    "proxy": "" if force_disable_proxy else (self.__proxy_string or ""),
                    "proxy_disabled": bool(force_disable_proxy),
                    "ignore_https_errors": bool(ignore_https_errors),
                    "context_mode": "persistent" if use_persistent_context else "ephemeral",
                    "user_data_dir": effective_user_data_dir if use_persistent_context else "",
                    "storage_state_path": effective_storage_state_path,
                    "timestamp": int(time.time()),
                },
            }
        finally:
            try:
                if page is not None and not page.is_closed():
                    page.close()
            except Exception:
                pass
            try:
                if context is not None:
                    context.close()
            except Exception:
                pass
            try:
                if browser is not None:
                    browser.close()
            except Exception:
                pass

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

        self._prepare_playwright_runtime_paths()
        # Пересоздаём клиенты с новым прокси
        self._refresh_clients()
        self.__logger.info(f"Прокси обновлён: {self.__proxy_string or 'отключён'}")

    @staticmethod
    def _build_ws_subscription_id(subscription_id: str | None = None) -> str:
        prepared_id = str(subscription_id or "").strip()
        return prepared_id if prepared_id else str(uuid.uuid4())

    @staticmethod
    def _normalize_ws_path(path: str) -> str:
        prepared = str(path or "").strip()
        if not prepared:
            return "/"
        if not prepared.startswith("/"):
            return f"/{prepared}"
        return prepared

    def _resolve_ws_user_id(self, user_id: str | None = None) -> str:
        resolved_user_id = str(user_id or self.id or "").strip()
        if not resolved_user_id:
            raise ValueError("Websocket Data: требуется user_id.")
        return resolved_user_id

    @staticmethod
    def _resolve_ws_chat_id(chat_id: str | None = None) -> str:
        resolved_chat_id = str(chat_id or "").strip()
        if not resolved_chat_id:
            raise ValueError("Websocket Data: требуется chat_id.")
        return resolved_chat_id

    def build_ws_connection_init_data(
        self,
        gql_path: str | None = None,
        profile_username: str | None = None,
        timezone_offset: int = -180,
    ) -> dict[str, Any]:
        """
        Собирает payload websocket-пакета `connection_init`.

        Если `gql_path` не указан, путь формируется автоматически:
        `/profile/<username>/products`, когда известен username, иначе `/`.
        """
        resolved_path = str(gql_path or "").strip()
        if not resolved_path:
            resolved_username = str(profile_username or self.username or "").strip()
            if resolved_username:
                resolved_path = f"/profile/{resolved_username}/products"
            else:
                resolved_path = "/"

        return {
            "type": "connection_init",
            "payload": {
                "x-gql-op": "ws-subscription",
                "x-gql-path": self._normalize_ws_path(resolved_path),
                "x-timezone-offset": int(timezone_offset),
            },
        }

    def build_ws_subscribe_data(
        self,
        operation_name: str,
        variables: dict[str, Any] | None = None,
        subscription_id: str | None = None,
        query: str | None = None,
    ) -> dict[str, Any]:
        """
        Собирает универсальный websocket-пакет `subscribe`
        для GraphQL-подписок.
        """
        prepared_operation = str(operation_name or "").strip()
        if not prepared_operation:
            raise ValueError("Websocket Data: требуется operation_name.")

        resolved_query = str(query or QUERIES.get(prepared_operation) or "").strip()
        if not resolved_query:
            raise ValueError(
                f"Websocket Data: отсутствует GraphQL query для операции '{prepared_operation}'."
            )

        return {
            "id": self._build_ws_subscription_id(subscription_id),
            "type": "subscribe",
            "payload": {
                "variables": variables or {},
                "extensions": {},
                "operationName": prepared_operation,
                "query": resolved_query,
            },
        }

    def build_ws_chat_updated_data(
        self,
        user_id: str | None = None,
        subscription_id: str | None = None,
        show_forbidden_image: bool = True,
    ) -> dict[str, Any]:
        """
        Собирает Data-пакет подписки `chatUpdated`.
        """
        resolved_user_id = self._resolve_ws_user_id(user_id)
        return self.build_ws_subscribe_data(
            operation_name="chatUpdated",
            variables={
                "filter": {"userId": resolved_user_id},
                "showForbiddenImage": bool(show_forbidden_image),
            },
            subscription_id=subscription_id,
        )

    def build_ws_chat_marked_as_read_data(
        self,
        user_id: str | None = None,
        subscription_id: str | None = None,
        show_forbidden_image: bool = True,
    ) -> dict[str, Any]:
        """
        Собирает Data-пакет подписки `chatMarkedAsRead`.
        """
        resolved_user_id = self._resolve_ws_user_id(user_id)
        return self.build_ws_subscribe_data(
            operation_name="chatMarkedAsRead",
            variables={
                "filter": {"userId": resolved_user_id},
                "showForbiddenImage": bool(show_forbidden_image),
            },
            subscription_id=subscription_id,
        )

    def build_ws_user_updated_data(
        self,
        user_id: str | None = None,
        subscription_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Собирает Data-пакет подписки `userUpdated`.
        """
        resolved_user_id = self._resolve_ws_user_id(user_id)
        return self.build_ws_subscribe_data(
            operation_name="userUpdated",
            variables={"userId": resolved_user_id},
            subscription_id=subscription_id,
        )

    def build_ws_chat_message_created_data(
        self,
        chat_id: str,
        subscription_id: str | None = None,
        show_forbidden_image: bool = True,
    ) -> dict[str, Any]:
        """
        Собирает Data-пакет подписки `chatMessageCreated`.
        """
        resolved_chat_id = self._resolve_ws_chat_id(chat_id)
        return self.build_ws_subscribe_data(
            operation_name="chatMessageCreated",
            variables={
                "filter": {"chatId": resolved_chat_id},
                "showForbiddenImage": bool(show_forbidden_image),
            },
            subscription_id=subscription_id,
        )

    def build_ws_default_data(
        self,
        user_id: str | None = None,
        chat_id: str | None = None,
        profile_username: str | None = None,
        timezone_offset: int = -180,
        show_forbidden_image: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Собирает базовый набор websocket Data-пакетов:
        - connection_init
        - chatUpdated
        - chatMarkedAsRead
        - userUpdated
        - опционально chatMessageCreated (если передан chat_id)
        """
        packets: list[dict[str, Any]] = [
            self.build_ws_connection_init_data(
                profile_username=profile_username,
                timezone_offset=timezone_offset,
            ),
            self.build_ws_chat_updated_data(
                user_id=user_id,
                show_forbidden_image=show_forbidden_image,
            ),
            self.build_ws_chat_marked_as_read_data(
                user_id=user_id,
                show_forbidden_image=show_forbidden_image,
            ),
            self.build_ws_user_updated_data(user_id=user_id),
        ]

        if chat_id:
            packets.append(
                self.build_ws_chat_message_created_data(
                    chat_id=chat_id,
                    show_forbidden_image=show_forbidden_image,
                )
            )

        return packets

    def _resolve_websocket_cookie_header(self) -> str:
        request_cookie_override = str(getattr(self, "_request_cookie_override", "") or "").strip()
        if request_cookie_override:
            return request_cookie_override
        return self._build_default_cookie_header()

    def _build_websocket_headers(self, extra_headers: dict[str, str] | None = None) -> list[str]:
        headers = {
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "cache-control": "no-cache",
            "connection": "Upgrade",
            "origin": "https://playerok.com",
            "pragma": "no-cache",
            "sec-websocket-extensions": "permessage-deflate; client_max_window_bits",
            "cookie": self._resolve_websocket_cookie_header(),
            "user-agent": self.user_agent or "",
        }
        if extra_headers:
            headers.update(extra_headers)

        return [f"{k}: {v}" for k, v in headers.items() if str(v).strip()]

    def _build_websocket_proxy_kwargs(self) -> dict[str, Any]:
        proxy_raw = str(self.proxy or "").strip()
        if not proxy_raw:
            return {}

        proxy_type = "http"
        proxy_host = ""
        proxy_port: int | str | None = None
        proxy_auth: tuple[str, str] | None = None

        try:
            if "://" in proxy_raw:
                parsed = urlsplit(proxy_raw)
                proxy_host = str(parsed.hostname or "").strip()
                proxy_port = parsed.port
                scheme = str(parsed.scheme or "").lower()
                if scheme.startswith("socks5"):
                    proxy_type = "socks5"
                elif scheme.startswith("socks4"):
                    proxy_type = "socks4"
                else:
                    proxy_type = "http"

                if parsed.username:
                    proxy_auth = (str(parsed.username), str(parsed.password or ""))
            elif "@" in proxy_raw:
                auth_part, host_part = proxy_raw.rsplit("@", 1)
                host_chunks = host_part.split(":")
                if len(host_chunks) >= 2:
                    proxy_host = str(host_chunks[0]).strip()
                    port_raw = str(host_chunks[1]).strip()
                    proxy_port = int(port_raw) if port_raw.isdigit() else port_raw

                if ":" in auth_part:
                    proxy_user, proxy_pass = auth_part.split(":", 1)
                    proxy_auth = (str(proxy_user), str(proxy_pass))
                else:
                    proxy_auth = (str(auth_part), "")
            else:
                chunks = proxy_raw.split(":")
                if len(chunks) == 4:
                    proxy_host, port_raw, proxy_user, proxy_pass = chunks
                    proxy_port = int(port_raw) if str(port_raw).isdigit() else str(port_raw)
                    proxy_auth = (str(proxy_user), str(proxy_pass))
                elif len(chunks) >= 2:
                    proxy_host, port_raw = chunks[0], chunks[1]
                    proxy_port = int(port_raw) if str(port_raw).isdigit() else str(port_raw)
        except Exception:
            return {}

        if not proxy_host or proxy_port is None:
            return {}

        proxy_kwargs: dict[str, Any] = {
            "http_proxy_host": proxy_host,
            "http_proxy_port": proxy_port,
            "proxy_type": proxy_type,
        }
        if proxy_auth:
            proxy_kwargs["http_proxy_auth"] = proxy_auth
        return proxy_kwargs

    def create_webhook_connection(
        self,
        ws_url: str = "wss://ws.playerok.com/graphql",
        timeout: float = 20.0,
        extra_headers: dict[str, str] | None = None,
        subprotocols: list[str] | None = None,
    ) -> websocket.WebSocket:
        """
        Создаёт websocket-подключение к Playerok для webhook-подписок.
        """
        sslopt: dict[str, Any] = {}
        try:
            verify_candidates = self._build_verify_candidates()
        except Exception:
            verify_candidates = []

        for cert_path in verify_candidates:
            if self._is_usable_cert(cert_path):
                sslopt["ca_certs"] = cert_path
                break

        ws = websocket.WebSocket(sslopt=sslopt) if sslopt else websocket.WebSocket()

        connect_kwargs: dict[str, Any] = {
            "url": str(ws_url).strip(),
            "header": self._build_websocket_headers(extra_headers=extra_headers),
            "subprotocols": subprotocols or ["graphql-transport-ws"],
            "timeout": max(1.0, float(timeout)),
        }
        connect_kwargs.update(self._build_websocket_proxy_kwargs())

        ws.connect(**connect_kwargs)
        return ws

    def wait_webhook_connection_ack(
        self,
        ws: websocket.WebSocket,
        timeout: float = 15.0,
    ) -> dict[str, Any]:
        """
        Ожидает `connection_ack` после отправки `connection_init`.
        """
        timeout_seconds = max(1.0, float(timeout))
        deadline = time.time() + timeout_seconds

        original_timeout = None
        try:
            original_timeout = ws.gettimeout()
        except Exception:
            original_timeout = None

        try:
            while time.time() < deadline:
                remaining = max(0.2, deadline - time.time())
                try:
                    ws.settimeout(remaining)
                except Exception:
                    pass

                raw_msg = ws.recv()
                if raw_msg is None:
                    continue

                try:
                    msg_data = json.loads(raw_msg)
                except Exception:
                    continue

                msg_type = str(msg_data.get("type") or "").strip()
                if msg_type == "connection_ack":
                    return msg_data
                if msg_type == "ping":
                    try:
                        ws.send(json.dumps({"type": "pong"}, ensure_ascii=False))
                    except Exception:
                        pass
                    continue
                if msg_type == "connection_error":
                    raise RuntimeError(f"Websocket Data: сервер вернул connection_error: {msg_data}")

            raise TimeoutError("Websocket Data: не дождались connection_ack.")
        finally:
            try:
                ws.settimeout(original_timeout)
            except Exception:
                pass

    def init_webhook_connection(
        self,
        ws: websocket.WebSocket,
        gql_path: str | None = None,
        profile_username: str | None = None,
        timezone_offset: int = -180,
        wait_connection_ack: bool = True,
        ack_timeout: float = 15.0,
    ) -> dict[str, Any] | None:
        """
        Отправляет `connection_init` и, при необходимости, ждёт `connection_ack`.
        """
        init_data = self.build_ws_connection_init_data(
            gql_path=gql_path,
            profile_username=profile_username,
            timezone_offset=timezone_offset,
        )
        ws.send(json.dumps(init_data, ensure_ascii=False))

        if not wait_connection_ack:
            return None
        return self.wait_webhook_connection_ack(ws=ws, timeout=ack_timeout)

    def subscribe_webhook_chat_updated(
        self,
        ws: websocket.WebSocket,
        user_id: str | None = None,
        subscription_id: str | None = None,
        show_forbidden_image: bool = True,
    ) -> str:
        """
        Создаёт подписку webhook `chatUpdated` и возвращает её `id`.
        """
        payload = self.build_ws_chat_updated_data(
            user_id=user_id,
            subscription_id=subscription_id,
            show_forbidden_image=show_forbidden_image,
        )
        ws.send(json.dumps(payload, ensure_ascii=False))
        return str(payload["id"])

    def subscribe_webhook_chat_marked_as_read(
        self,
        ws: websocket.WebSocket,
        user_id: str | None = None,
        subscription_id: str | None = None,
        show_forbidden_image: bool = True,
    ) -> str:
        """
        Создаёт подписку webhook `chatMarkedAsRead` и возвращает её `id`.
        """
        payload = self.build_ws_chat_marked_as_read_data(
            user_id=user_id,
            subscription_id=subscription_id,
            show_forbidden_image=show_forbidden_image,
        )
        ws.send(json.dumps(payload, ensure_ascii=False))
        return str(payload["id"])

    def subscribe_webhook_user_updated(
        self,
        ws: websocket.WebSocket,
        user_id: str | None = None,
        subscription_id: str | None = None,
    ) -> str:
        """
        Создаёт подписку webhook `userUpdated` и возвращает её `id`.
        """
        payload = self.build_ws_user_updated_data(
            user_id=user_id,
            subscription_id=subscription_id,
        )
        ws.send(json.dumps(payload, ensure_ascii=False))
        return str(payload["id"])

    def subscribe_webhook_chat_message_created(
        self,
        ws: websocket.WebSocket,
        chat_id: str,
        subscription_id: str | None = None,
        show_forbidden_image: bool = True,
    ) -> str:
        """
        Создаёт подписку webhook `chatMessageCreated` и возвращает её `id`.
        """
        payload = self.build_ws_chat_message_created_data(
            chat_id=chat_id,
            subscription_id=subscription_id,
            show_forbidden_image=show_forbidden_image,
        )
        ws.send(json.dumps(payload, ensure_ascii=False))
        return str(payload["id"])

    def create_default_webhooks(
        self,
        ws: websocket.WebSocket,
        user_id: str | None = None,
        chat_id: str | None = None,
        show_forbidden_image: bool = True,
    ) -> dict[str, str]:
        """
        Создаёт базовые webhook-подписки и возвращает карту
        `{operationName: subscription_id}`.
        """
        subscription_ids: dict[str, str] = {
            "chatUpdated": self.subscribe_webhook_chat_updated(
                ws=ws,
                user_id=user_id,
                show_forbidden_image=show_forbidden_image,
            ),
            "chatMarkedAsRead": self.subscribe_webhook_chat_marked_as_read(
                ws=ws,
                user_id=user_id,
                show_forbidden_image=show_forbidden_image,
            ),
            "userUpdated": self.subscribe_webhook_user_updated(
                ws=ws,
                user_id=user_id,
            ),
        }

        if chat_id:
            subscription_ids["chatMessageCreated"] = self.subscribe_webhook_chat_message_created(
                ws=ws,
                chat_id=chat_id,
                show_forbidden_image=show_forbidden_image,
            )

        return subscription_ids

    def open_webhook_session(
        self,
        ws_url: str = "wss://ws.playerok.com/graphql",
        user_id: str | None = None,
        chat_id: str | None = None,
        gql_path: str | None = None,
        profile_username: str | None = None,
        timezone_offset: int = -180,
        show_forbidden_image: bool = True,
        connect_timeout: float = 20.0,
        ack_timeout: float = 15.0,
    ) -> tuple[websocket.WebSocket, dict[str, Any], dict[str, str]]:
        """
        Полный цикл инициализации webhook-сессии:
        1. websocket connect
        2. connection_init + connection_ack
        3. создание базовых подписок
        """
        ws = self.create_webhook_connection(
            ws_url=ws_url,
            timeout=connect_timeout,
        )
        ack_data = self.init_webhook_connection(
            ws=ws,
            gql_path=gql_path,
            profile_username=profile_username,
            timezone_offset=timezone_offset,
            wait_connection_ack=True,
            ack_timeout=ack_timeout,
        ) or {}

        subscription_ids = self.create_default_webhooks(
            ws=ws,
            user_id=user_id,
            chat_id=chat_id,
            show_forbidden_image=show_forbidden_image,
        )
        return ws, ack_data, subscription_ids

    @staticmethod
    def recv_webhook_message(
        ws: websocket.WebSocket,
        timeout: float | None = None,
    ) -> dict[str, Any] | None:
        """
        Получает одно websocket-сообщение и пытается распарсить JSON.
        """
        original_timeout = None
        try:
            original_timeout = ws.gettimeout()
        except Exception:
            original_timeout = None

        try:
            if timeout is not None:
                try:
                    ws.settimeout(max(0.1, float(timeout)))
                except Exception:
                    pass

            raw_msg = ws.recv()
            if raw_msg is None:
                return None
            try:
                return json.loads(raw_msg)
            except Exception:
                return {"type": "raw", "raw": raw_msg}
        finally:
            try:
                ws.settimeout(original_timeout)
            except Exception:
                pass

    @staticmethod
    def close_webhook_connection(ws: websocket.WebSocket | None) -> None:
        """
        Закрывает websocket-подключение webhook.
        """
        if ws is None:
            return
        try:
            ws.close()
        except Exception:
            pass

    def request(self, method: Literal["get", "post"], url: str, headers: dict[str, str],
                payload: dict[str, str] | None = None, files: dict | None = None,
                multipart: CurlMime | None = None) -> CurlResponse:
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

        :param multipart: Мультипарт для отправки фото.
        :type multipart: `CurlMime` or `None`

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

        try:
            x_gql_op = payload.get("operationName", "viewer")
        except:
            x_gql_op = "viewer"
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
            "x-gql-op": x_gql_op,
            "x-gql-path": "/",
            "x-apollo-operation-name": x_gql_op,
            "x-timezone-offset": "-180",
        }

        request_cookie_override = str(getattr(self, "_request_cookie_override", "") or "").strip()
        if request_cookie_override:
            headers["cookie"] = request_cookie_override
        else:
            resolved_cookie_header = self._build_default_cookie_header()
            if resolved_cookie_header:
                headers["cookie"] = resolved_cookie_header
            elif self.token:
                headers["cookie"] = f"token={self.token}"
        # if self.auid:
        #     headers['cookie'] += f'; auid={self.auid}'
        headers["user-agent"] = user_agent
        headers = {**_headers, **headers}

        def make_req():
            if not hasattr(self, "_Account__curl_session") or self.__curl_session is None:
                self._refresh_clients()

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
                        files=files,
                    )

                elif multipart:
                    headers_no_ct = {k: v for k, v in headers.items() if k.lower() != 'content-type'}
                    r = self.__curl_session.post(
                        url=url,
                        data=payload,
                        headers=headers_no_ct,
                        multipart=multipart
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
            "Cloudflare Ray ID",
        ]
        ddos_guard_signatures = [
            "<title>DDoS-Guard</title>",
            "/.well-known/ddos-guard/js-challenge/",
            "check.ddos-guard.net/check.js",
            'data-ddg-origin="true"',
            'data-ddg-l10n="true"',
        ]

        def _detect_antibot_vendor(text: str | None) -> str | None:
            if not text:
                return None
            if any(sig in text for sig in ddos_guard_signatures):
                return "ddos_guard"
            if any(sig in text for sig in cloudflare_signatures):
                return "cloudflare"
            return None

        max_delay = 3.0
        max_attempts = max(1, int(self.request_max_retries))
        session_refresh_attempts = {2, 4, 7}

        timeout_exception_types = (
            curl_exceptions.Timeout,
            curl_exceptions.ConnectTimeout,
            curl_exceptions.ReadTimeout,
        )
        retriable_network_exceptions = (
            curl_exceptions.Timeout,
            curl_exceptions.ConnectTimeout,
            curl_exceptions.ReadTimeout,
            curl_exceptions.ConnectionError,
            curl_exceptions.ProxyError,
            curl_exceptions.SSLError,
            curl_exceptions.DNSError,
            curl_exceptions.RequestException,
            curl_exceptions.SessionClosed,
        )

        def _parse_retry_after(value: str | None) -> float | None:
            if not value:
                return None
            raw = value.strip()
            if not raw:
                return None
            if raw.isdigit():
                return max(0.0, float(int(raw)))
            try:
                dt = email.utils.parsedate_to_datetime(raw)
                if dt is None:
                    return None
                if dt.tzinfo is not None:
                    now_ts = datetime.now(dt.tzinfo)
                else:
                    now_ts = datetime.now()
                return max(0.0, (dt - now_ts).total_seconds())
            except Exception:
                return None

        def _retry_delay(attempt: int, retry_after: str | None = None) -> float:
            retry_after_seconds = _parse_retry_after(retry_after)
            if retry_after_seconds is not None:
                return min(30.0, max(0.5, retry_after_seconds))
            return min(max_delay, float(attempt))

        def _to_int(value: Any) -> int | None:
            try:
                return int(value) if value is not None else None
            except Exception:
                return None

        def _record_error(
            *,
            kind: str,
            error_text: str,
            status_code: int | None = None,
            error_code: str | None = None,
            attempt: int,
            retryable: bool,
            retry_exhausted: bool,
            session_recreated: bool,
        ) -> None:
            if _record_playerok_request_error is None:
                return
            _record_playerok_request_error(
                kind=kind,
                error_text=error_text,
                method=method.upper(),
                url=url,
                status_code=status_code,
                error_code=error_code,
                attempt=attempt,
                max_attempts=max_attempts,
                retryable=retryable,
                retry_exhausted=retry_exhausted,
                session_recreated=session_recreated,
            )

        def _record_success() -> None:
            if _record_playerok_request_success is None:
                return
            _record_playerok_request_success()

        last_timeout_exc: Exception | None = None
        last_network_exc: Exception | None = None
        last_request_error: RequestError | None = None
        last_failed_response: CurlResponse | None = None
        last_cloudflare_response: CurlResponse | None = None

        for attempt in range(1, max_attempts + 1):
            session_recreated = False
            if attempt in session_refresh_attempts:
                try:
                    self._refresh_clients()
                    session_recreated = True
                except Exception as refresh_error:
                    self.__logger.warning(
                        f"⚠️ Не удалось пересоздать curl-сессию перед попыткой {attempt}/{max_attempts}: {refresh_error}"
                    )

            try:
                resp = make_req()
            except retriable_network_exceptions as network_error:
                is_timeout = isinstance(network_error, timeout_exception_types)
                kind = "timeout" if is_timeout else "other"
                last_network_exc = network_error
                if is_timeout:
                    last_timeout_exc = network_error

                retry_exhausted = attempt >= max_attempts
                _record_error(
                    kind=kind,
                    error_text=str(network_error),
                    status_code=None,
                    error_code=type(network_error).__name__,
                    attempt=attempt,
                    retryable=True,
                    retry_exhausted=retry_exhausted,
                    session_recreated=session_recreated,
                )

                if retry_exhausted:
                    if is_timeout:
                        self.__logger.error(
                            f"❌ Timeout при запросе к Playerok после {max_attempts} попыток."
                        )
                        raise CurlTimeoutError(url, self.requests_timeout, network_error) from network_error
                    self.__logger.error(
                        f"❌ Ошибка сети при запросе к Playerok после {max_attempts} попыток: {network_error}"
                    )
                    raise network_error

                delay = _retry_delay(attempt)
                self.__logger.warning(
                    f"⚠️ Сетевая ошибка при запросе к Playerok: {url} "
                    f"(попытка {attempt}/{max_attempts}, retryable=true), "
                    f"повтор через {delay:.1f} сек..."
                )
                time.sleep(delay)
                continue

            antibot_vendor = _detect_antibot_vendor(resp.text)
            if antibot_vendor is not None:
                last_cloudflare_response = resp
                vendor_title = "DDoS-Guard" if antibot_vendor == "ddos_guard" else "Cloudflare"
                error_code = "DDOS_GUARD" if antibot_vendor == "ddos_guard" else "CLOUDFLARE"
                retry_exhausted = attempt >= max_attempts
                _record_error(
                    kind="cloudflare",
                    error_text=f"{vendor_title} challenge detected",
                    status_code=_to_int(resp.status_code),
                    error_code=error_code,
                    attempt=attempt,
                    retryable=True,
                    retry_exhausted=retry_exhausted,
                    session_recreated=session_recreated,
                )

                if retry_exhausted:
                    self.__logger.error(
                        f"❌ {vendor_title} заблокировал все {max_attempts} попыток! "
                        f"Требуется смена токена/прокси/user-agent."
                    )
                    raise CloudflareDetectedException(resp)

                delay = _retry_delay(attempt)
                self.__logger.warning(
                    f"⚠️ {vendor_title} challenge detected (попытка {attempt}/{max_attempts}), "
                    f"повтор через {delay:.1f} сек..."
                )
                time.sleep(delay)
                continue

            response_json: dict[str, Any] | None = None
            try:
                parsed_json = resp.json()
                if isinstance(parsed_json, dict):
                    response_json = parsed_json
            except Exception:
                response_json = None

            if response_json and isinstance(response_json.get("errors"), list) and response_json["errors"]:
                first_error = response_json["errors"][0] if isinstance(response_json["errors"][0], dict) else {}
                extensions = first_error.get("extensions", {}) if isinstance(first_error, dict) else {}
                graphql_status = _to_int(extensions.get("statusCode")) if isinstance(extensions, dict) else None
                graphql_code = ""
                if isinstance(extensions, dict):
                    graphql_code = str(extensions.get("code") or "")
                if not graphql_code and isinstance(first_error, dict):
                    graphql_code = str(first_error.get("code") or "")
                graphql_message = str(first_error.get("message") or "GraphQL error") if isinstance(first_error, dict) else "GraphQL error"
                graphql_message_l = graphql_message.lower()
                graphql_code_u = graphql_code.upper()

                is_rate_limit = (
                    graphql_status == 429
                    or graphql_code_u == "TOO_MANY_REQUESTS"
                    or "too many" in graphql_message_l
                    or "слишком много попыток" in graphql_message_l
                )
                is_internal_server_error = (
                    graphql_code_u == "INTERNAL_SERVER_ERROR"
                    or "internal server error" in graphql_message_l
                )
                is_server_error = (
                    (graphql_status is not None and 500 <= graphql_status <= 599)
                    or is_internal_server_error
                )
                retriable_graphql = is_rate_limit or is_server_error
                retry_exhausted = attempt >= max_attempts or not retriable_graphql

                if is_rate_limit:
                    graphql_kind = "graphql_429"
                elif is_server_error:
                    graphql_kind = "graphql_5xx"
                else:
                    graphql_kind = "other"

                try:
                    request_error = RequestError(resp)
                except Exception:
                    request_error = None

                if request_error is not None:
                    last_request_error = request_error

                _record_error(
                    kind=graphql_kind,
                    error_text=graphql_message,
                    status_code=graphql_status or _to_int(resp.status_code),
                    error_code=graphql_code or "GRAPHQL_ERROR",
                    attempt=attempt,
                    retryable=retriable_graphql,
                    retry_exhausted=retry_exhausted,
                    session_recreated=session_recreated,
                )

                if retriable_graphql and attempt < max_attempts:
                    delay = _retry_delay(attempt, resp.headers.get("Retry-After") if is_rate_limit else None)
                    self.__logger.warning(
                        f"⚠️ GraphQL retryable error ({graphql_kind}) "
                        f"(попытка {attempt}/{max_attempts}), повтор через {delay:.1f} сек..."
                    )
                    time.sleep(delay)
                    continue

                if request_error is not None:
                    raise request_error
                raise RequestError(resp)

            if resp.status_code != 200:
                status_code = _to_int(resp.status_code) or 0
                retriable_http = status_code == 429 or 500 <= status_code <= 599
                retry_exhausted = attempt >= max_attempts or not retriable_http
                last_failed_response = resp

                if status_code == 429:
                    http_kind = "http_429"
                elif 500 <= status_code <= 599:
                    http_kind = "http_5xx"
                else:
                    http_kind = "other"

                _record_error(
                    kind=http_kind,
                    error_text=resp.text[:300],
                    status_code=status_code,
                    error_code=str(status_code),
                    attempt=attempt,
                    retryable=retriable_http,
                    retry_exhausted=retry_exhausted,
                    session_recreated=session_recreated,
                )

                if retriable_http and attempt < max_attempts:
                    delay = _retry_delay(attempt, resp.headers.get("Retry-After") if status_code == 429 else None)
                    self.__logger.warning(
                        f"⚠️ HTTP retryable error ({status_code}) "
                        f"(попытка {attempt}/{max_attempts}), повтор через {delay:.1f} сек..."
                    )
                    time.sleep(delay)
                    continue

                raise RequestFailedError(resp)

            if attempt > 1:
                self.__logger.info(
                    f"✅ Запрос восстановлен после ретраев (recovered=true, attempt={attempt}/{max_attempts}, url={url})"
                )
            try:
                self._sync_cookies_from_response(resp)
            except Exception as cookie_sync_error:
                self.__logger.debug(f"Не удалось синхронизировать cookies после успешного запроса: {cookie_sync_error}")
            _record_success()
            return resp

        if last_request_error is not None:
            raise last_request_error
        if last_failed_response is not None:
            raise RequestFailedError(last_failed_response)
        if last_cloudflare_response is not None:
            raise CloudflareDetectedException(last_cloudflare_response)
        if last_timeout_exc is not None:
            raise CurlTimeoutError(url, self.requests_timeout, last_timeout_exc) from last_timeout_exc
        if last_network_exc is not None:
            raise last_network_exc
        raise RuntimeError(f"Request to {url} failed with unknown reason")

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
        headers = {
            "accept": "*/*",
        }

        if photo_file_path:
            query = QUERIES.get("createChatMessageWithFile")

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
        mp = None
        try:
            if photo_file_path:
                # files = {"1": open(photo_file_path, "rb")}
                map = {"1": ["variables.file"]}
                mp = CurlMime()
                mp.addpart(name="operations", data=json.dumps(operations))
                mp.addpart(name="map", data=json.dumps(map))
                mp.addpart(
                    name="1",
                    filename=os.path.basename(photo_file_path),
                    content_type="image/jpeg",
                    local_path=photo_file_path

                )

                payload = {"operations": json.dumps(operations), "map": json.dumps(map)}
            else:
                payload = operations
            r = self.request("post", f"{self.base_url}/graphql", headers, payload, multipart=mp).json()
            return chat_message(r["data"]["createChatMessage"])
        finally:
            if files:
                for file_obj in files.values():
                    file_obj.close()

    def upload_image(self, chat_id: str, bytes: str) -> types.UploadImage:
        """
        Публикует изображение (чтобы потом его отправить используя полученный url)

        :param chat_id: id чата для публикации
        :type chat_id: `str`

        :param bytes: Абсолютный путь к изображению
        :type bytes: `str`
        """
        headers = {
            "accept": "*/*",
            "referer": f"https://playerok.com/chats/{chat_id}"
        }
        file = {'image': bytes}
        r = self.request("post", f"{self.base_url}/graphql", headers, files=file).json()
        return upload_image(r)


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
