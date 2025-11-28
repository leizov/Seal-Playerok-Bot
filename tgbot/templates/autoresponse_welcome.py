import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from settings import Settings as sett
from .. import callback_datas as calls

def autoresponse_welcome_text():
    config = sett.get("config")
    enabled = config.get("autoresponse", {}).get("welcome", {}).get("enabled", False)
    text = config.get("autoresponse", {}).get("welcome", {}).get("text", "Не задано")
    
    status = "✅ Включено" if enabled else "❌ Выключено"
    
    txt = textwrap.dedent(f"""
        👋 <b>Приветственное сообщение</b>

        <b>Статус:</b> {status}
        <b>Текст сообщения:</b>
        <code>{text}</code>

        Используйте кнопки ниже для настройки:
    """)
    return txt

def autoresponse_welcome_kb():
    config = sett.get("config")
    enabled = config.get("autoresponse", {}).get("welcome", {}).get("enabled", False)
    
    rows = [
        [InlineKeyboardButton(
            text=f"{'❌ Выключить' if enabled else '✅ Включить'}",
            callback_data="toggle_welcome"
        )],
        [InlineKeyboardButton(
            text="✏️ Изменить текст",
            callback_data="edit_welcome_text"
        )],
        [
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=calls.SettingsNavigation(to="autoresponse").pack()
            ),
            InlineKeyboardButton(
                text="🔄 Обновить",
                callback_data=calls.SettingsNavigation(to="autoresponse_welcome").pack()
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
