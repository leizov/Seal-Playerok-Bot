import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from settings import Settings as sett

from .. import callback_datas as calls


def settings_users_text():
    config = sett.get("config")
    password_auth_enabled = config["telegram"]["bot"].get("password_auth_enabled", True)
    users = config["telegram"]["bot"].get("signed_users", [])

    # Собираем построчно: textwrap.dedent ломался, когда список пользователей
    # был многострочным (строки списка без отступа -> весь текст сдвигался).
    lines = [
        "👥 <b>Пользователи</b>",
        "",
        f"🔐 <b>Вход по паролю:</b> {'🟢 включён' if password_auth_enabled else '🔴 выключен'}",
        "",
        f"<b>Авторизованные пользователи ({len(users)}):</b>",
    ]
    if users:
        for index, user_id in enumerate(users):
            branch = "┗" if index == len(users) - 1 else "┣"
            lines.append(f"{branch} 👤 <code>{user_id}</code>")
    else:
        lines.append("❌ Нет авторизованных пользователей")
    lines += ["", "Выберите действие ↓"]
    return "\n".join(lines)


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
