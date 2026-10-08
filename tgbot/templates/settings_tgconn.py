import html

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from settings import Settings as sett
from core import tg_connection as tgc
from core.proxy_utils import format_proxy_display

from .. import callback_datas as calls

TITLE = "📡 <b>Подключение к Telegram</b>"
# Откуда открывают меню: раздел «Аккаунт» (там же прокси для Playerok).
BACK_CB = calls.SettingsNavigation(to="account").pack()


def _status() -> dict:
    try:
        from ..telegrambot import get_telegram_bot
        tg_bot = get_telegram_bot()
        if tg_bot is not None:
            return tg_bot.get_connection_status()
    except Exception:
        pass
    config = sett.get("config")
    preferred = tgc.preferred_route(config)
    return {"active": preferred, "preferred": preferred, "is_fallback": False, "failures": 0}


def _route_name(route: str) -> str:
    """«Напрямую» / «Через прокси» — с заглавной буквы для отдельной строки."""
    title = tgc.ROUTE_TITLES.get(route, route)
    return title[:1].upper() + title[1:]


def tgconn_short_status() -> str:
    """Одна строка о текущем способе — для других меню (например, «Аккаунт»)."""
    status = _status()
    text = f"{tgc.ROUTE_EMOJI[status['active']]} {_route_name(status['active'])}"
    if status["is_fallback"]:
        text += " (запасной)"
    return text


def settings_tgconn_text():
    config = sett.get("config")
    api = tgc.get_api_cfg(config)
    status = _status()
    worker = tgc.worker_url_from_config(config)
    proxy = tgc.proxy_from_config(config)
    auto_fallback = api.get("auto_fallback", True)
    active = status["active"]
    preferred = status["preferred"]

    lines = [
        TITLE,
        "",
        f"<b>Сейчас:</b> {tgc.ROUTE_EMOJI[active]} <b>{html.escape(tgc.describe_route(active, config))}</b>",
    ]
    if status["is_fallback"]:
        lines.append(
            f"⚠️ Это запасной способ: основной (<b>{tgc.ROUTE_TITLES[preferred]}</b>) сейчас не отвечает. "
            f"Бот периодически проверяет его и вернётся сам."
        )
    lines += [
        "",
        "<b>Способы:</b>",
        f"┣ 🌍 Напрямую: <b>{'⭐ основной' if preferred == tgc.ROUTE_DIRECT else 'доступен'}</b>",
        f"┣ ☁️ Cloudflare Worker: <b>"
        + (html.escape(worker) + (" — ⭐ основной" if preferred == tgc.ROUTE_WORKER else "") if worker else "не настроен")
        + "</b>",
        f"┗ 🌐 Прокси: <b>"
        + (html.escape(format_proxy_display(proxy)) + (" — ⭐ основной" if preferred == tgc.ROUTE_PROXY else "") if proxy else "не настроен")
        + "</b>",
        "",
        f"🛟 <b>Автопереключение при сбое:</b> {'✅ включено' if auto_fallback else '❌ выключено'}",
        f"Порядок: {html.escape(' → '.join(tgc.ROUTE_TITLES[r] for r in tgc.route_chain(config)))}",
        "",
        "<b>Как это работает</b>",
        "· <b>Напрямую</b> — бот сам обращается к api.telegram.org.",
        "· <b>Cloudflare Worker</b> — бесплатный личный посредник на серверах Cloudflare. "
        "Используйте только свой воркер: через него проходит токен бота.",
        "· <b>Прокси</b> — платный сервер в другой стране. Это прокси только для Telegram, "
        "прокси для Playerok настраивается в «🌐 Управление прокси».",
        "",
        "Если основной способ перестанет отвечать, бот сам перейдёт на запасной "
        "и вернётся, когда основной заработает.",
        "",
        "Чтобы сменить способ, нажмите на него ниже: бот проверит, отвечает ли через него Telegram, "
        "и попросит подтвердить переключение.",
    ]
    return "\n".join(lines)


def settings_tgconn_kb():
    config = sett.get("config")
    status = _status()
    api = tgc.get_api_cfg(config)
    worker = tgc.worker_url_from_config(config)
    proxy = tgc.proxy_from_config(config)

    def label(route: str, text: str) -> str:
        if route == status["active"]:
            return f"✅ {text} (сейчас)"
        return text

    rows = [
        [InlineKeyboardButton(text=label(tgc.ROUTE_DIRECT, "🌍 Напрямую"), callback_data="tgconn:use:direct")],
        [InlineKeyboardButton(
            text=label(tgc.ROUTE_WORKER, "☁️ Через Cloudflare Worker") if worker else "➕ Настроить Cloudflare Worker",
            callback_data="tgconn:use:worker" if worker else "tgconn:set:worker",
        )],
        [InlineKeyboardButton(
            text=label(tgc.ROUTE_PROXY, "🌐 Через прокси") if proxy else "➕ Настроить прокси для Telegram",
            callback_data="tgconn:use:proxy" if proxy else "tgconn:set:proxy",
        )],
    ]
    if worker:
        rows.append([
            InlineKeyboardButton(text="✏️ Воркер", callback_data="tgconn:set:worker"),
            InlineKeyboardButton(text="🗑 Удалить воркер", callback_data="tgconn:del:worker"),
        ])
    if proxy:
        rows.append([
            InlineKeyboardButton(text="✏️ Прокси", callback_data="tgconn:set:proxy"),
            InlineKeyboardButton(text="🗑 Удалить прокси", callback_data="tgconn:del:proxy"),
        ])
    rows.append([InlineKeyboardButton(text="🩺 Проверить все способы", callback_data="tgconn:check")])
    rows.append([InlineKeyboardButton(
        text=f"🛟 Автопереключение: {'✅' if api.get('auto_fallback', True) else '❌'}",
        callback_data="tgconn:toggle_fallback",
    )])
    rows.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data=BACK_CB),
        InlineKeyboardButton(text="🔄️ Обновить", callback_data=calls.SettingsNavigation(to="tgconn").pack()),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_tgconn_float_text(placeholder: str):
    return f"{TITLE}\n\n{placeholder}"


def tgconn_confirm_text(route: str, username: str | None, current: str) -> str:
    config = sett.get("config")
    lines = [
        f"✅ <b>Проверка пройдена:</b> Telegram отвечает {html.escape(tgc.describe_route(route, config))}"
        + (f" (бот @{html.escape(username)})." if username else "."),
        "",
        f"Сейчас: {tgc.ROUTE_EMOJI[current]} <b>{html.escape(tgc.describe_route(current, config))}</b>",
        f"Будет: {tgc.ROUTE_EMOJI[route]} <b>{html.escape(tgc.describe_route(route, config))}</b> — станет основным способом.",
        "",
        "Переключить?",
    ]
    return settings_tgconn_float_text("\n".join(lines))


def tgconn_confirm_kb(route: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Переключить", callback_data=f"tgconn:confirm:{route}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=calls.SettingsNavigation(to="tgconn").pack())],
    ])


def tgconn_worker_instruction_text():
    code = html.escape(tgc.WORKER_CODE)
    return settings_tgconn_float_text(
        "☁️ <b>Cloudflare Worker — бесплатно, ~5 минут</b>\n\n"
        "1. Откройте https://dash.cloudflare.com и зарегистрируйтесь (почта + пароль).\n"
        "2. <b>Workers &amp; Pages</b> → <b>Create</b> → <b>Create Worker</b> (или «Start with Hello World»).\n"
        "3. Придумайте имя, например <code>tg-proxy</code>, нажмите <b>Deploy</b>.\n"
        "4. <b>Edit code</b> → полностью удалите шаблон и вставьте код (нажмите, чтобы скопировать):\n"
        f"<pre>{code}</pre>\n"
        "5. Снова нажмите <b>Deploy</b>.\n"
        "6. Скопируйте адрес вида <code>https://tg-proxy.ваш-поддомен.workers.dev</code> и отправьте его сюда.\n\n"
        "⚠️ Используйте только свой воркер: через него проходит токен бота.\n"
        "Перед сохранением бот проверит, что через воркер отвечает Telegram."
    )


def tgconn_proxy_instruction_text():
    return settings_tgconn_float_text(
        "🌐 <b>Прокси для Telegram</b>\n\n"
        "Нужен IPv4-прокси НЕ из России (лучше Нидерланды/Германия), HTTP(S) или SOCKS5.\n"
        f"Купить: {tgc.PROXY_SHOP_URL}\n\n"
        "Форматы:\n"
        "· <code>ip:port</code>\n"
        "· <code>user:pass@ip:port</code> или <code>ip:port:user:pass</code>\n"
        "· <code>socks5://user:pass@ip:port</code> (для SOCKS5 приставка обязательна)\n\n"
        "Это прокси только для Telegram — Playerok он не затрагивает.\n"
        "Перед сохранением бот проверит, что через прокси отвечает Telegram."
    )


def tgconn_back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.SettingsNavigation(to="tgconn").pack())
    ]])
