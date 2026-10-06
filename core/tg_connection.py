"""
Способы подключения к Telegram Bot API и их проверка.

Способы (маршруты):
    direct  — напрямую к api.telegram.org;
    worker  — через собственный Cloudflare Worker (telegram.api.custom_api_url);
    proxy   — через HTTP/SOCKS-прокси (telegram.api.proxy).

Основной способ хранится в telegram.api.mode. Если он перестаёт работать,
бот пробует остальные настроенные способы в порядке FALLBACK_ORDER:
прокси → воркер → напрямую.
"""
from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from typing import Callable, Optional
from urllib.parse import urlsplit, urlunsplit

from core.proxy_utils import normalize_proxy, validate_proxy, format_proxy_display


ROUTE_DIRECT = "direct"
ROUTE_WORKER = "worker"
ROUTE_PROXY = "proxy"
ROUTES = (ROUTE_DIRECT, ROUTE_WORKER, ROUTE_PROXY)

# Порядок запасных способов при сбое основного.
FALLBACK_ORDER = (ROUTE_PROXY, ROUTE_WORKER, ROUTE_DIRECT)

ROUTE_TITLES = {
    ROUTE_DIRECT: "напрямую",
    ROUTE_WORKER: "через Cloudflare Worker",
    ROUTE_PROXY: "через прокси",
}

ROUTE_EMOJI = {
    ROUTE_DIRECT: "🌍",
    ROUTE_WORKER: "☁️",
    ROUTE_PROXY: "🌐",
}

PROXY_SHOP_URL = "https://proxylin.net?ref=448587"
CLOUDFLARE_DASHBOARD_URL = "https://dash.cloudflare.com"

WORKER_CODE = """export default {
  async fetch(request) {
    const url = new URL(request.url);
    const tgUrl = `https://api.telegram.org${url.pathname}${url.search}`;
    const headers = new Headers(request.headers);
    headers.set('Host', 'api.telegram.org');
    return fetch(new Request(tgUrl, {
      method: request.method, headers, body: request.body
    }));
  }
}"""

DEFAULT_PROBE_TIMEOUT = 15


# ─────────────────────────────── конфиг ───────────────────────────────

def get_api_cfg(config: dict | None) -> dict:
    cfg = config or {}
    return cfg.get("telegram", {}).get("api", {}) or {}


def normalize_worker_url(raw: str | None) -> str:
    """
    Приводит адрес воркера к виду https://host[/path] без завершающего слеша.

    :raises ValueError: если адрес некорректен.
    """
    value = str(raw or "").strip().strip("\"'").strip()
    if not value:
        raise ValueError("адрес пустой")
    if any(ch.isspace() for ch in value):
        raise ValueError("в адресе не должно быть пробелов")
    if "://" not in value:
        value = "https://" + value

    parts = urlsplit(value)
    scheme = (parts.scheme or "").lower()
    host = (parts.hostname or "").lower()
    if scheme not in ("https", "http"):
        raise ValueError("адрес должен начинаться с https://")
    if not host or "." not in host and host != "localhost":
        raise ValueError("не удалось распознать домен воркера")
    if parts.username or parts.password:
        raise ValueError("в адресе не должно быть логина и пароля")
    if scheme == "http" and host not in ("localhost", "127.0.0.1"):
        raise ValueError("используйте https:// — по http токен бота уйдёт в открытом виде")
    if parts.query or parts.fragment:
        raise ValueError("укажите адрес без ?параметров и #якорей")

    path = (parts.path or "").rstrip("/")
    if re.search(r"/bot\d+:", path) or re.search(r"/bot\d+:", value):
        raise ValueError("укажите только адрес воркера, без /bot<токен>/...")
    if path.endswith("/getMe") or path.endswith("/getme"):
        raise ValueError("укажите только адрес воркера, без метода API")

    return urlunsplit((scheme, parts.netloc.lower(), path, "", ""))


def build_proxy_url(raw: str | None) -> tuple[str, str]:
    """
    Возвращает (адрес для aiohttp, нормализованное значение для config).

    :raises ValueError: если формат прокси некорректен.
    """
    proxy = str(raw or "").strip()
    if not proxy:
        raise ValueError("прокси не задан")
    validate_proxy(proxy)
    normalized = normalize_proxy(proxy)
    if normalized.startswith(("socks5://", "socks4://", "http://", "https://")):
        return normalized, normalized
    return f"http://{normalized}", normalized


def worker_url_from_config(config: dict | None) -> str | None:
    raw = str(get_api_cfg(config).get("custom_api_url") or "").strip()
    if not raw:
        return None
    try:
        return normalize_worker_url(raw)
    except ValueError:
        return None


def proxy_from_config(config: dict | None) -> str | None:
    raw = str(get_api_cfg(config).get("proxy") or "").strip()
    if not raw:
        return None
    try:
        build_proxy_url(raw)
        return raw
    except Exception:
        return None


def is_route_configured(route: str, config: dict | None) -> bool:
    if route == ROUTE_DIRECT:
        return True
    if route == ROUTE_WORKER:
        return worker_url_from_config(config) is not None
    if route == ROUTE_PROXY:
        return proxy_from_config(config) is not None
    return False


def preferred_route(config: dict | None) -> str:
    """Основной способ: из telegram.api.mode, иначе — по тому, что настроено."""
    mode = str(get_api_cfg(config).get("mode") or "").strip().lower()
    if mode in ROUTES and is_route_configured(mode, config):
        return mode
    if is_route_configured(ROUTE_PROXY, config):
        return ROUTE_PROXY
    if is_route_configured(ROUTE_WORKER, config):
        return ROUTE_WORKER
    return ROUTE_DIRECT


def route_chain(config: dict | None, preferred: str | None = None) -> list[str]:
    """Основной способ + запасные (только настроенные) в порядке FALLBACK_ORDER."""
    first = preferred if preferred in ROUTES and is_route_configured(preferred, config) else preferred_route(config)
    chain = [first]
    for route in FALLBACK_ORDER:
        if route not in chain and is_route_configured(route, config):
            chain.append(route)
    return chain


def describe_route(route: str, config: dict | None = None, *, worker_url: str | None = None,
                   proxy: str | None = None) -> str:
    title = ROUTE_TITLES.get(route, route)
    if route == ROUTE_WORKER:
        url = worker_url or worker_url_from_config(config)
        if url:
            return f"{title} ({urlsplit(url).netloc})"
    if route == ROUTE_PROXY:
        value = proxy or proxy_from_config(config)
        if value:
            return f"{title} ({format_proxy_display(value)})"
    return title


# ─────────────────────────────── сессии ───────────────────────────────

class ConnectionTracker:
    """Счётчик удачных/неудачных запросов к Telegram для сторожа подключения."""

    def __init__(self):
        self.last_ok: float = 0.0
        self.last_fail: float = 0.0
        self.consecutive_failures: int = 0

    def ok(self):
        self.last_ok = time.monotonic()
        self.consecutive_failures = 0

    def fail(self):
        self.last_fail = time.monotonic()
        self.consecutive_failures += 1

    def reset(self):
        self.last_ok = time.monotonic()
        self.consecutive_failures = 0


def _tracked_session_class():
    from aiogram.client.session.aiohttp import AiohttpSession
    from aiogram.exceptions import ClientDecodeError, TelegramNetworkError, TelegramServerError

    class TrackedAiohttpSession(AiohttpSession):
        def __init__(self, *args, tracker: ConnectionTracker | None = None, **kwargs):
            super().__init__(*args, **kwargs)
            self.tracker = tracker

        async def make_request(self, bot, method, timeout=None):
            try:
                result = await super().make_request(bot, method, timeout)
            except (TelegramNetworkError, TelegramServerError, ClientDecodeError):
                if self.tracker:
                    self.tracker.fail()
                raise
            except Exception:
                # Telegram ответил (например, ошибкой запроса) — значит связь есть.
                if self.tracker:
                    self.tracker.ok()
                raise
            if self.tracker:
                self.tracker.ok()
            return result

    return TrackedAiohttpSession


def build_session(route: str, config: dict | None = None, *, worker_url: str | None = None,
                  proxy: str | None = None, tracker: ConnectionTracker | None = None):
    """
    Создаёт aiohttp-сессию aiogram для выбранного способа.

    :raises ValueError: если для способа не хватает настроек.
    """
    from aiogram.client.telegram import TelegramAPIServer

    session_cls = _tracked_session_class()
    if route == ROUTE_DIRECT:
        return session_cls(tracker=tracker)
    if route == ROUTE_WORKER:
        url = normalize_worker_url(worker_url) if worker_url else worker_url_from_config(config)
        if not url:
            raise ValueError("адрес воркера не задан")
        return session_cls(api=TelegramAPIServer.from_base(url), tracker=tracker)
    if route == ROUTE_PROXY:
        raw = proxy if proxy else proxy_from_config(config)
        if not raw:
            raise ValueError("прокси не задан")
        proxy_url, _ = build_proxy_url(raw)
        return session_cls(proxy=proxy_url, tracker=tracker)
    raise ValueError(f"неизвестный способ подключения: {route}")


# ─────────────────────────────── проверка ───────────────────────────────

@dataclass
class ProbeResult:
    ok: bool
    route: str
    username: str | None = None
    reason: str | None = None
    retry_after: int | None = None
    error: str | None = None


REASON_TEXTS = {
    "invalid_token": "Telegram ответил, что токен бота неверный или отозван",
    "network": "нет связи с Telegram (таймаут или соединение сброшено)",
    "rate_limit": "Telegram временно ограничил запросы",
    "bad_endpoint": "по этому адресу отвечает не Telegram — проверьте адрес и код воркера",
    "proxy_dependency_missing": "для SOCKS-прокси не установлен пакет aiohttp-socks",
    "bad_config": "некорректные настройки способа подключения",
    "api_error": "Telegram вернул неожиданную ошибку",
}


def describe_reason(reason: str | None) -> str:
    return REASON_TEXTS.get(reason or "", REASON_TEXTS["api_error"])


async def probe_route(token: str, route: str, config: dict | None = None, *,
                      worker_url: str | None = None, proxy: str | None = None,
                      timeout: int = DEFAULT_PROBE_TIMEOUT) -> ProbeResult:
    """Один запрос getMe через указанный способ. Ничего не сохраняет."""
    from aiogram import Bot
    from aiogram.exceptions import (
        ClientDecodeError,
        TelegramAPIError,
        TelegramBadRequest,
        TelegramNetworkError,
        TelegramNotFound,
        TelegramRetryAfter,
        TelegramServerError,
        TelegramUnauthorizedError,
    )

    bot = None
    try:
        try:
            session = build_session(route, config, worker_url=worker_url, proxy=proxy)
        except RuntimeError as exc:
            if "aiohttp-socks" in str(exc).lower():
                return ProbeResult(False, route, reason="proxy_dependency_missing", error=str(exc))
            return ProbeResult(False, route, reason="bad_config", error=str(exc))
        except Exception as exc:
            return ProbeResult(False, route, reason="bad_config", error=str(exc))

        bot = Bot(token=token, session=session)
        me = await asyncio.wait_for(bot.get_me(request_timeout=timeout), timeout=timeout + 5)
        if me and me.is_bot:
            return ProbeResult(True, route, username=me.username or "")
        return ProbeResult(False, route, reason="api_error")
    except TelegramUnauthorizedError as exc:
        return ProbeResult(False, route, reason="invalid_token", error=str(exc))
    except TelegramNotFound as exc:
        # Через воркер 404 чаще значит неверный адрес/код воркера, а не токен.
        reason = "bad_endpoint" if route == ROUTE_WORKER else "invalid_token"
        return ProbeResult(False, route, reason=reason, error=str(exc))
    except TelegramRetryAfter as exc:
        retry_after = min(int(getattr(exc, "retry_after", 1) or 1), 10)
        return ProbeResult(False, route, reason="rate_limit", retry_after=retry_after, error=str(exc))
    except ClientDecodeError as exc:
        return ProbeResult(False, route, reason="bad_endpoint", error=str(exc)[:300])
    except (TelegramNetworkError, TelegramServerError, asyncio.TimeoutError, TimeoutError) as exc:
        return ProbeResult(False, route, reason="network", error=str(exc)[:300])
    except TelegramBadRequest as exc:
        return ProbeResult(False, route, reason="api_error", error=str(exc)[:300])
    except TelegramAPIError as exc:
        return ProbeResult(False, route, reason="api_error", error=str(exc)[:300])
    except RuntimeError as exc:
        if "aiohttp-socks" in str(exc).lower():
            return ProbeResult(False, route, reason="proxy_dependency_missing", error=str(exc))
        return ProbeResult(False, route, reason="api_error", error=str(exc)[:300])
    except Exception as exc:
        return ProbeResult(False, route, reason="network", error=f"{type(exc).__name__}: {exc}"[:300])
    finally:
        if bot is not None:
            try:
                await bot.session.close()
            except Exception:
                pass


# Причины, при которых повторять проверку бессмысленно.
FINAL_REASONS = {"invalid_token", "bad_config", "proxy_dependency_missing"}


async def probe_route_with_retries(token: str, route: str, config: dict | None = None, *,
                                   worker_url: str | None = None, proxy: str | None = None,
                                   attempts: int = 3, timeout: int = DEFAULT_PROBE_TIMEOUT,
                                   on_attempt: Optional[Callable[[int, int, ProbeResult | None], None]] = None,
                                   ) -> ProbeResult:
    """
    Несколько попыток getMe. on_attempt(номер, всего, результат|None) вызывается
    до попытки (результат None) и после неё.
    """
    result = ProbeResult(False, route, reason="network")
    for attempt in range(1, attempts + 1):
        if on_attempt:
            on_attempt(attempt, attempts, None)
        result = await probe_route(token, route, config, worker_url=worker_url, proxy=proxy, timeout=timeout)
        if on_attempt:
            on_attempt(attempt, attempts, result)
        if result.ok or result.reason in FINAL_REASONS:
            return result
        if attempt < attempts:
            delay = result.retry_after if result.reason == "rate_limit" and result.retry_after else min(attempt, 3)
            await asyncio.sleep(delay)
    return result


async def find_working_route(token: str, config: dict | None, *, preferred: str | None = None,
                             attempts_per_route: int = 1, timeout: int = DEFAULT_PROBE_TIMEOUT,
                             ) -> tuple[ProbeResult | None, list[ProbeResult]]:
    """Перебирает основной и запасные способы. Возвращает (первый рабочий|None, все результаты)."""
    results: list[ProbeResult] = []
    for route in route_chain(config, preferred):
        result = await probe_route_with_retries(
            token, route, config, attempts=attempts_per_route, timeout=timeout
        )
        results.append(result)
        if result.ok:
            return result, results
        if result.reason == "invalid_token" and route != ROUTE_WORKER:
            # Токен неверный — другие способы не помогут.
            return None, results
    return None, results
