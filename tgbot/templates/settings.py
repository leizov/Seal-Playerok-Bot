import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from settings import Settings as sett

from .. import callback_datas as calls


def settings_text():
    config = sett.get("config")
    token_raw = str(config["playerok"]["api"].get("token") or "")
    token = token_raw[:5] + ("*" * 10) if token_raw else "❌ Не задано"
    cookies_status = "Привязаны" if str(config["playerok"]["api"].get("cookies") or "").strip() else "❌ Не заданы"
    user_agent = config["playerok"]["api"]["user_agent"] or "❌ Не задано"
    txt = textwrap.dedent(f"""
        ⚙️ <b>Настройки</b>

        <b>Основные настройки:</b>
        ┣ Cookies: <b>{cookies_status}</b>
        ┣ Токен: <b>{token}</b>
        ┗ User-Agent: <b>{user_agent}</b>

        Перемещайтесь по разделам ниже, чтобы изменить значения параметров ↓
    """)
    return txt


def settings_kb():
    rows = [
        [InlineKeyboardButton(text="🔑 Авторизация", callback_data=calls.SettingsNavigation(to="auth").pack())],
        [InlineKeyboardButton(text="📶 Соединение", callback_data=calls.SettingsNavigation(to="conn").pack())],
        [InlineKeyboardButton(text="♻️ Восстановление", callback_data=calls.SettingsNavigation(to="restore").pack())],
        [InlineKeyboardButton(text="⌨️ Команды", callback_data=calls.CustomCommandsPagination(page=0).pack())],
        [InlineKeyboardButton(text="🚀 Авто-выдача", callback_data=calls.AutoDeliveriesPagination(page=0).pack())],
        [InlineKeyboardButton(text="🔔 Настройки Уведомлений", callback_data=calls.SettingsNavigation(to="notifications").pack())],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data=calls.SettingsNavigation(to="users").pack())],
        [
        InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.MenuPagination(page=0).pack()),
        InlineKeyboardButton(text="🔄️ Обновить", callback_data=calls.SettingsNavigation(to="default").pack())
        ]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb
