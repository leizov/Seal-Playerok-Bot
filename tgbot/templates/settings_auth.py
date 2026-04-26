import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from settings import Settings as sett

from .. import callback_datas as calls


def settings_auth_text():
    config = sett.get("config")
    token_raw = str(config["playerok"]["api"].get("token") or "")
    token = token_raw[:5] + ("*" * 10) if token_raw else "❌ Не задано"
    cookies_status = "Привязаны" if str(config["playerok"]["api"].get("cookies") or "").strip() else "❌ Не заданы"
    user_agent = config["playerok"]["api"]["user_agent"] or "❌ Не задано"
    txt = textwrap.dedent(f"""
        ⚙️ <b>Настройки → 🔑 Авторизация</b>

        🍪 <b>Cookies:</b> {cookies_status}
        🔐 <b>Токен:</b> {token}
        🎩 <b>User-Agent:</b> {user_agent}

        Выберите параметр для изменения ↓
    """)
    return txt


def settings_auth_kb():
    config = sett.get("config")
    token_raw = str(config["playerok"]["api"].get("token") or "")
    token = token_raw[:5] + ("*" * 10) if token_raw else "❌ Не задано"
    cookies_status = "Привязаны" if str(config["playerok"]["api"].get("cookies") or "").strip() else "❌ Не заданы"
    user_agent = config["playerok"]["api"]["user_agent"] or "❌ Не задано"
    rows = [
        [InlineKeyboardButton(text=f"🍪 Cookies: {cookies_status}", callback_data="enter_token")],
        [InlineKeyboardButton(text=f"🎩 User-Agent: {user_agent}", callback_data="enter_user_agent")],
        [
        InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.SettingsNavigation(to="default").pack()),
        InlineKeyboardButton(text="🔄️ Обновить", callback_data=calls.SettingsNavigation(to="auth").pack())
        ]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def settings_auth_float_text(placeholder: str):
    txt = textwrap.dedent(f"""
        ⚙️ <b>Настройки → 🔑 Авторизация</b>
        \n{placeholder}
    """)
    return txt
