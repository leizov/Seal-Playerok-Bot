import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from settings import Settings as sett

from .. import callback_datas as calls


def settings_users_text():
    config = sett.get("config")
    password_auth_enabled = "🟢 Включена" if config["telegram"]["bot"].get("password_auth_enabled", True) else "🔴 Выключена"
    
    # Get list of authorized users
    users = config["telegram"]["bot"].get("signed_users", [])
    users_list = ""
    
    if not users:
        users_list = "❌ Нет авторизованных пользователей"
    else:
        users_list = "\n".join([f"👤 <code>{user_id}</code>" for user_id in users])
    
    txt = textwrap.dedent(f"""
        ⚙️ <b>Настройки → 👥 Управление пользователями</b>

        🔐 <b>Блокировка входа по паролю:</b> {password_auth_enabled}
        
        <b>Авторизованные пользователи:</b>
        {users_list}
        
        Выберите действие ↓
    """)
    return txt


def settings_users_kb():
    config = sett.get("config")
    password_auth_enabled = config["telegram"]["bot"].get("password_auth_enabled", True)
    users = config["telegram"]["bot"].get("signed_users", [])
    
    builder = InlineKeyboardBuilder()
    
    # Add password auth toggle
    password_status = "🟢 Включен" if password_auth_enabled else "🔴 Выключен"
    builder.row(
        InlineKeyboardButton(
            text=f"🔐 Вход по паролю: {password_status}", 
            callback_data="switch_password_auth_enabled"
        )
    )
    
    # Add user management buttons
    if users:
        for user_id in users:
            builder.row(
                InlineKeyboardButton(
                    text=f"❌ Удалить пользователя {user_id}",
                    callback_data=f"remove_user:{user_id}"
                )
            )
    
    # Add navigation buttons
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=calls.MenuPagination(page=1).pack()
        )
    )
    
    return builder.as_markup()


def settings_users_float_text(placeholder: str):
    return textwrap.dedent(f"""
        ⚙️ <b>Настройки → 👥 Управление пользователями</b>
        \n{placeholder}
    """)
