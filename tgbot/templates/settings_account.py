import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from settings import Settings as sett

from .. import callback_datas as calls


def settings_account_text():
    config = sett.get("config")
    token_raw = config["playerok"]["api"]["token"]
    if token_raw:
        token_status = 'Привязан'
    else:
        token_status = 'Отсутствует'

    user_agent = config["playerok"]["api"]["user_agent"] or "❌ Не задан"
    proxy = config["playerok"]["api"]["proxy"] or "❌ Не задан"
    
    txt = textwrap.dedent(f"""
        👤 <b>Аккаунт</b>

        <b>Авторизация:</b>
        ┣ 🔐 Токен: <b>{token_status}</b>
        ┗ 🎩 User-Agent: <b>{user_agent}</b>

        <b>Соединение:</b>
        ┗ 🌐 Прокси: <b>{proxy}</b>

        Выберите параметр для изменения ↓
    """)
    return txt


def settings_account_kb():
    config = sett.get("config")
    
    rows = [
        [InlineKeyboardButton(text="🔐 Изменить токен", callback_data="enter_token")],
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
