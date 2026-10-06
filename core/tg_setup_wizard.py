"""
Консольный мастер настройки подключения к Telegram при первом запуске.

Порядок:
1. Проверяем токен напрямую к api.telegram.org (3 попытки).
2. Если напрямую работает — предлагаем: 1) без прокси, 2) Cloudflare Worker, 3) свой прокси.
   Если не работает — только 1) Cloudflare Worker, 2) свой прокси.
3. Выбранный способ проверяется перед сохранением. После настройки можно добавить
   запасной способ (воркер/прокси), он включится автоматически при сбое основного.
"""
from __future__ import annotations

import asyncio
from typing import Callable

from colorama import Fore

from core import tg_connection as tgc


InputFn = Callable[[str], str]
PrintFn = Callable[..., None]

PROBE_ATTEMPTS = 3

RESULT_OK = "ok"
RESULT_INVALID_TOKEN = "invalid_token"
RESULT_RATE_LIMIT = "rate_limit"
RESULT_DEPENDENCY = "proxy_dependency_missing"


class _Ui:
    def __init__(self, input_fn: InputFn, print_fn: PrintFn):
        self.input = input_fn
        self.print = print_fn

    def line(self, text: str = ""):
        self.print(text)

    def title(self, text: str):
        self.print(f"\n{Fore.CYAN}{'═' * 64}")
        self.print(f"{Fore.CYAN}  {text}")
        self.print(f"{Fore.CYAN}{'═' * 64}")

    def ask(self, prompt: str = "") -> str:
        if prompt:
            self.print(prompt)
        return (self.input(f"  {Fore.WHITE}> {Fore.LIGHTWHITE_EX}") or "").strip()


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _probe(ui: _Ui, token: str, route: str, *, worker_url: str | None = None,
           proxy: str | None = None, attempts: int = PROBE_ATTEMPTS) -> tgc.ProbeResult:
    def on_attempt(attempt: int, total: int, result):
        if result is None:
            ui.print(f"{Fore.WHITE}  Попытка {attempt}/{total}...", end=" ", flush=True)
            return
        if result.ok:
            ui.print(f"{Fore.GREEN}OK")
        else:
            ui.print(f"{Fore.YELLOW}не удалось — {tgc.describe_reason(result.reason)}")

    return _run(tgc.probe_route_with_retries(
        token, route, None, worker_url=worker_url, proxy=proxy,
        attempts=attempts, on_attempt=on_attempt,
    ))


def _print_failure_hint(ui: _Ui, route: str, result: tgc.ProbeResult):
    if result.reason == "invalid_token":
        return
    if route == tgc.ROUTE_WORKER:
        ui.line(f"{Fore.YELLOW}  Что проверить:")
        ui.line(f"{Fore.WHITE}   · адрес скопирован целиком, вида https://имя.ваш-поддомен.workers.dev")
        ui.line(f"{Fore.WHITE}   · в воркере вставлен код из инструкции и нажата кнопка Deploy")
        ui.line(f"{Fore.WHITE}   · адрес воркера открывается в браузере на этом устройстве")
        ui.line(f"{Fore.WHITE}   · домен workers.dev может быть недоступен у вашего провайдера —")
        ui.line(f"{Fore.WHITE}     тогда используйте прокси")
    elif route == tgc.ROUTE_PROXY:
        if result.reason == "proxy_dependency_missing":
            ui.line(f"{Fore.YELLOW}  Для SOCKS-прокси нужен пакет aiohttp-socks: pip install aiohttp-socks")
            return
        ui.line(f"{Fore.YELLOW}  Что проверить:")
        ui.line(f"{Fore.WHITE}   · прокси не просрочен и логин/пароль введены без ошибок")
        ui.line(f"{Fore.WHITE}   · регион прокси не RU (например, Нидерланды)")
        ui.line(f"{Fore.WHITE}   · тип прокси: для SOCKS5 обязательно укажите socks5:// в начале")
    if result.error:
        ui.line(f"{Fore.LIGHTBLACK_EX}  Техническая причина: {result.error[:200]}")


def _setup_worker(ui: _Ui, token: str) -> tuple[str | None, tgc.ProbeResult | None]:
    """Возвращает (адрес воркера, результат проверки) или (None, None), если пользователь вернулся назад."""
    ui.title("☁️  Подключение через Cloudflare Worker (бесплатно)")
    ui.line(f"{Fore.WHITE}Что это: ваш личный «посредник» на серверах Cloudflare. Бот отправляет")
    ui.line(f"{Fore.WHITE}запросы на адрес воркера, а воркер пересылает их в Telegram. Это бесплатно")
    ui.line(f"{Fore.WHITE}(до 100 000 запросов в сутки — для бота с запасом), карта не нужна.")
    ui.line("")
    ui.line(f"{Fore.YELLOW}Безопасность: через воркер проходит токен вашего бота. Используйте ТОЛЬКО")
    ui.line(f"{Fore.YELLOW}свой воркер — владелец чужого адреса сможет управлять вашим ботом.")
    ui.line("")
    ui.line(f"{Fore.CYAN}Как создать (около 5 минут):")
    ui.line(f"{Fore.WHITE}  1. Откройте {Fore.LIGHTWHITE_EX}{tgc.CLOUDFLARE_DASHBOARD_URL}{Fore.WHITE} и зарегистрируйтесь (почта + пароль).")
    ui.line(f"{Fore.WHITE}  2. В меню слева: {Fore.LIGHTWHITE_EX}Workers & Pages{Fore.WHITE} → {Fore.LIGHTWHITE_EX}Create{Fore.WHITE} → {Fore.LIGHTWHITE_EX}Create Worker{Fore.WHITE}")
    ui.line(f"{Fore.WHITE}     (может называться «Start with Hello World»).")
    ui.line(f"{Fore.WHITE}  3. Придумайте имя, например {Fore.LIGHTWHITE_EX}tg-proxy{Fore.WHITE}, и нажмите {Fore.LIGHTWHITE_EX}Deploy{Fore.WHITE}.")
    ui.line(f"{Fore.WHITE}  4. Нажмите {Fore.LIGHTWHITE_EX}Edit code{Fore.WHITE}, ПОЛНОСТЬЮ удалите шаблонный код и вставьте этот:")
    ui.line("")
    for code_line in tgc.WORKER_CODE.splitlines():
        ui.line(f"{Fore.LIGHTGREEN_EX}    {code_line}")
    ui.line("")
    ui.line(f"{Fore.WHITE}  5. Нажмите {Fore.LIGHTWHITE_EX}Deploy{Fore.WHITE} ещё раз.")
    ui.line(f"{Fore.WHITE}  6. Скопируйте адрес воркера, он выглядит так:")
    ui.line(f"{Fore.LIGHTWHITE_EX}     https://tg-proxy.ваш-поддомен.workers.dev")
    ui.line("")
    ui.line(f"{Fore.WHITE}Названия кнопок на сайте Cloudflare иногда меняются — ищите по смыслу.")
    ui.line(f"{Fore.WHITE}Подробная инструкция с картинками — в README, раздел «Подключение к Telegram».")

    while True:
        url_raw = ui.ask(
            f"\n{Fore.WHITE}Вставьте адрес воркера (можно без https://)."
            f"\n{Fore.YELLOW}  Пустой Enter — вернуться к выбору способа."
        )
        if not url_raw:
            return None, None
        try:
            url = tgc.normalize_worker_url(url_raw)
        except ValueError as exc:
            ui.line(f"{Fore.LIGHTRED_EX}  Адрес не подходит: {exc}. Попробуйте ещё раз.")
            continue

        ui.line(f"\n{Fore.CYAN}Проверяю подключение к Telegram через воркер {url} ...")
        result = _probe(ui, token, tgc.ROUTE_WORKER, worker_url=url)
        if result.ok:
            ui.line(f"{Fore.GREEN}✓ Воркер работает: Telegram отвечает, бот @{result.username}")
            return url, result
        if result.reason == "invalid_token":
            return url, result
        ui.line(f"{Fore.LIGHTRED_EX}✗ Через воркер подключиться не удалось: {tgc.describe_reason(result.reason)}.")
        _print_failure_hint(ui, tgc.ROUTE_WORKER, result)


def _setup_proxy(ui: _Ui, token: str) -> tuple[str | None, tgc.ProbeResult | None]:
    """Возвращает (нормализованный прокси, результат проверки) или (None, None) — назад."""
    ui.title("🌐  Подключение через свой прокси")
    ui.line(f"{Fore.WHITE}Что это: платный сервер-посредник в другой стране. Все запросы бота к")
    ui.line(f"{Fore.WHITE}Telegram пойдут через него. Этот прокси используется ТОЛЬКО для Telegram,")
    ui.line(f"{Fore.WHITE}прокси для Playerok настраивается отдельно.")
    ui.line("")
    ui.line(f"{Fore.CYAN}Какой нужен:")
    ui.line(f"{Fore.WHITE}  · IPv4, регион НЕ Россия (лучше Нидерланды/Германия)")
    ui.line(f"{Fore.WHITE}  · HTTP(S) или SOCKS5")
    ui.line(f"{Fore.WHITE}  · где купить: {Fore.LIGHTWHITE_EX}{tgc.PROXY_SHOP_URL}")
    ui.line("")
    ui.line(f"{Fore.CYAN}Форматы ввода:")
    ui.line(f"{Fore.WHITE}  · {Fore.LIGHTWHITE_EX}ip:port")
    ui.line(f"{Fore.WHITE}  · {Fore.LIGHTWHITE_EX}user:pass@ip:port{Fore.WHITE}  или  {Fore.LIGHTWHITE_EX}ip:port:user:pass")
    ui.line(f"{Fore.WHITE}  · {Fore.LIGHTWHITE_EX}socks5://user:pass@ip:port{Fore.WHITE}  (для SOCKS5 приставка обязательна)")

    while True:
        raw = ui.ask(
            f"\n{Fore.WHITE}Введите прокси для Telegram."
            f"\n{Fore.YELLOW}  Пустой Enter — вернуться к выбору способа."
        )
        if not raw:
            return None, None
        try:
            _, normalized = tgc.build_proxy_url(raw)
        except Exception as exc:
            ui.line(f"{Fore.LIGHTRED_EX}  Неверный формат прокси: {exc}. Попробуйте ещё раз.")
            continue

        ui.line(f"\n{Fore.CYAN}Проверяю подключение к Telegram через прокси ...")
        result = _probe(ui, token, tgc.ROUTE_PROXY, proxy=normalized)
        if result.ok:
            ui.line(f"{Fore.GREEN}✓ Прокси работает: Telegram отвечает, бот @{result.username}")
            return normalized, result
        if result.reason == "invalid_token":
            return normalized, result
        ui.line(f"{Fore.LIGHTRED_EX}✗ Через прокси подключиться не удалось: {tgc.describe_reason(result.reason)}.")
        _print_failure_hint(ui, tgc.ROUTE_PROXY, result)


def _choose(ui: _Ui, options: dict[str, str]) -> str:
    while True:
        answer = ui.ask()
        if answer in options:
            return answer
        ui.line(f"{Fore.LIGHTRED_EX}  Введите номер: {', '.join(options)}.")


def _offer_backup(ui: _Ui, token: str, api: dict, main_route: str):
    """После настройки воркера/прокси предлагает добавить второй способ как запасной."""
    other = tgc.ROUTE_PROXY if main_route == tgc.ROUTE_WORKER else tgc.ROUTE_WORKER
    other_title = "свой прокси" if other == tgc.ROUTE_PROXY else "Cloudflare Worker"
    ui.title("🛟  Запасной способ подключения (необязательно)")
    ui.line(f"{Fore.WHITE}Если основной способ перестанет работать, бот сам попробует запасные")
    ui.line(f"{Fore.WHITE}в порядке: прокси → воркер → напрямую, и вернётся на основной, когда он оживёт.")
    ui.line(f"{Fore.WHITE}Сейчас можно добавить {other_title} как запасной вариант.")
    ui.line(f"\n{Fore.WHITE}  1 — добавить {other_title}")
    ui.line(f"{Fore.WHITE}  Enter — пропустить (можно добавить позже в боте: Настройки → 📡 Подключение к Telegram)")
    answer = ui.ask()
    if answer != "1":
        return
    if other == tgc.ROUTE_WORKER:
        url, result = _setup_worker(ui, token)
        if url and result and result.ok:
            api["custom_api_url"] = url
            ui.line(f"{Fore.GREEN}Воркер сохранён как запасной способ.")
    else:
        proxy, result = _setup_proxy(ui, token)
        if proxy and result and result.ok:
            api["proxy"] = proxy
            ui.line(f"{Fore.GREEN}Прокси сохранён как запасной способ.")


def configure_telegram_connection(config: dict, token: str, *, input_fn: InputFn = input,
                                  print_fn: PrintFn = print) -> tuple[str, str | None]:
    """
    Проводит пользователя через настройку подключения.

    Изменяет config["telegram"]["api"] (token, mode, custom_api_url, proxy), но не сохраняет файл.
    Возвращает (RESULT_*, username).
    """
    ui = _Ui(input_fn, print_fn)
    api = config.setdefault("telegram", {}).setdefault("api", {})

    ui.title("📡  Проверка подключения к Telegram")
    ui.line(f"{Fore.WHITE}Сначала проверю, открывается ли Telegram напрямую — без прокси и воркера.")
    ui.line(f"{Fore.WHITE}Бот сделает до {PROBE_ATTEMPTS} попыток по ~15 сек; при плохой сети это может занять до минуты.")
    direct = _probe(ui, token, tgc.ROUTE_DIRECT)

    if direct.reason == "invalid_token":
        return RESULT_INVALID_TOKEN, None
    if direct.reason == "rate_limit" and not direct.ok:
        return RESULT_RATE_LIMIT, None

    direct_ok = direct.ok
    username = direct.username

    while True:
        if direct_ok:
            ui.line(f"\n{Fore.GREEN}✓ Telegram доступен напрямую. Бот @{username} найден.")
            ui.line(f"{Fore.WHITE}Выберите, как боту подключаться к Telegram:")
            ui.line(f"{Fore.WHITE}  {Fore.LIGHTWHITE_EX}1{Fore.WHITE} — напрямую, без прокси {Fore.GREEN}(рекомендуется: уже работает, ничего настраивать не нужно)")
            ui.line(f"{Fore.WHITE}  {Fore.LIGHTWHITE_EX}2{Fore.WHITE} — через Cloudflare Worker (бесплатно; если у вас Telegram периодически пропадает)")
            ui.line(f"{Fore.WHITE}  {Fore.LIGHTWHITE_EX}3{Fore.WHITE} — через свой прокси (платно; если у вас уже есть прокси)")
            ui.line(f"{Fore.LIGHTBLACK_EX}  Способ можно поменять позже в боте: Настройки → 📡 Подключение к Telegram.")
            choice = _choose(ui, {"1": "direct", "2": "worker", "3": "proxy"})
            route = {"1": tgc.ROUTE_DIRECT, "2": tgc.ROUTE_WORKER, "3": tgc.ROUTE_PROXY}[choice]
        else:
            ui.line(f"\n{Fore.LIGHTRED_EX}✗ Напрямую Telegram недоступен: {tgc.describe_reason(direct.reason)}.")
            ui.line(f"{Fore.WHITE}Скорее всего, Telegram блокируется провайдером или в вашем регионе.")
            ui.line(f"{Fore.WHITE}Без посредника бот работать не сможет — выберите один из способов:")
            ui.line(f"{Fore.WHITE}  {Fore.LIGHTWHITE_EX}1{Fore.WHITE} — Cloudflare Worker {Fore.GREEN}(бесплатно, ~5 минут, нужна только почта)")
            ui.line(f"{Fore.WHITE}  {Fore.LIGHTWHITE_EX}2{Fore.WHITE} — свой прокси (платно, не RU регион)")
            choice = _choose(ui, {"1": "worker", "2": "proxy"})
            route = {"1": tgc.ROUTE_WORKER, "2": tgc.ROUTE_PROXY}[choice]

        if route == tgc.ROUTE_DIRECT:
            api["mode"] = tgc.ROUTE_DIRECT
            ui.line(f"\n{Fore.GREEN}Выбрано подключение напрямую.")
            return RESULT_OK, username

        if route == tgc.ROUTE_WORKER:
            value, result = _setup_worker(ui, token)
        else:
            value, result = _setup_proxy(ui, token)

        if value is None or result is None:
            continue  # пользователь вернулся к выбору
        if result.reason == "invalid_token":
            return RESULT_INVALID_TOKEN, None
        if not result.ok:
            continue

        if route == tgc.ROUTE_WORKER:
            api["custom_api_url"] = value
        else:
            api["proxy"] = value
        api["mode"] = route
        username = result.username or username
        ui.line(f"\n{Fore.GREEN}Основной способ подключения: {tgc.ROUTE_TITLES[route]}.")
        if direct_ok:
            ui.line(f"{Fore.WHITE}Если он перестанет работать, бот попробует подключиться напрямую.")
        _offer_backup(ui, token, api, route)
        return RESULT_OK, username
