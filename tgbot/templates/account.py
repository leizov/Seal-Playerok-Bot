import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from settings import Settings as sett
from .. import callback_datas as calls


def account_text():
    config = sett.get("config")
    
    # Токен с маскировкой
    token = config["playerok"]["api"]["token"]
    token_display = f"{token[:5]}{'*' * (len(token) - 5) if len(token) > 5 else ''}" if token else "❌ Не задан"
    
    # User-Agent
    user_agent = config["playerok"]["api"]["user_agent"] or "❌ Не задан"
    
    # Прокси
    proxy = config["playerok"]["api"].get("proxy") or "❌ Не задан"
    
    # Таймаут
    timeout = config["playerok"]["api"].get("requests_timeout", 30)
    
    txt = textwrap.dedent(f"""
        👤 <b>Управление аккаунтом</b>

        <b>Текущие настройки:</b>
        ┣ Токен: <code>{token_display}</code>
        ┣ User-Agent: <code>{user_agent}</code>
        ┣ Прокси: <code>{proxy}</code>
        ┗ Таймаут запросов: <b>{timeout} сек</b>

        Выберите параметр для изменения ↓
    """)
    return txt


def account_kb():
    rows = [
        [
            InlineKeyboardButton(
                text="🔑 Изменить токен",
                callback_data=calls.AccountAction(action="change_token").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="🔄 Изменить User-Agent",
                callback_data=calls.AccountAction(action="change_user_agent").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="🔌 Настроить прокси",
                callback_data=calls.AccountAction(action="setup_proxy").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="⏱ Изменить таймаут",
                callback_data=calls.AccountAction(action="change_timeout").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="📊 Информация о профиле",
                callback_data=calls.AccountAction(action="profile_info").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=calls.MenuNavigation(to="main").pack()
            ),
            InlineKeyboardButton(
                text="🔄 Обновить",
                callback_data=calls.MenuNavigation(to="account").pack()
            )
        ]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb
