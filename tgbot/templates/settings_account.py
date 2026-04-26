import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from settings import Settings as sett

from .. import callback_datas as calls


def _get_connected_playerok_username() -> str:
    try:
        from ..helpful import get_playerok_bot

        pb = get_playerok_bot()
        account = getattr(pb, "account", None) if pb else None
        username = str(getattr(account, "username", "") or "").strip()
        if username:
            return f"@{username}"
    except Exception:
        pass
    return "❌ Не выполнен вход"


def settings_account_text():
    config = sett.get("config")
    token_raw = str(config["playerok"]["api"].get("token") or "").strip()
    cookies_raw = str(config["playerok"]["api"].get("cookies") or "").strip()
    if cookies_raw:
        cookies_status = "Привязаны"
    else:
        cookies_status = "Отсутствуют"
    token_status = "Привязан" if token_raw else "Отсутствует"

    user_agent = config["playerok"]["api"]["user_agent"] or "❌ Не задан"
    proxy = config["playerok"]["api"]["proxy"] or "❌ Не задан"
    connected_username = _get_connected_playerok_username()
    
    txt = textwrap.dedent(f"""
        👤 <b>Аккаунт</b>

        <b>Авторизация:</b>
        ┣ 🍪 Cookies: <b>{cookies_status}</b>
        ┣ 🔐 Токен: <b>{token_status}</b>
        ┣ 🪪 Ник аккаунта: <b>{connected_username}</b>
        ┗ 🎩 User-Agent: <b>{user_agent}</b>

        <b>Соединение:</b>
        ┗ 🌐 Прокси: <b>{proxy}</b>

        Выберите параметр для изменения ↓
    """)
    return txt


def settings_account_kb():
    config = sett.get("config")
    
    rows = [
        [InlineKeyboardButton(text="🍪 Изменить cookies", callback_data="enter_token")],
        [InlineKeyboardButton(text="🎩 Изменить User-Agent", callback_data="enter_user_agent")],
    ]
    
    # Кнопка управления прокси
    rows.append([InlineKeyboardButton(text="🌐 Управление прокси", callback_data=calls.ProxyListPagination(page=0).pack())])
    
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.MenuPagination(page=0).pack())])
    
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def settings_account_float_text(placeholder: str):
    txt = textwrap.dedent(f"""
        👤 <b>Аккаунт</b>
        \n{placeholder}
    """)
    return txt
