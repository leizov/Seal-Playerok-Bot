import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from settings import Settings as sett
from .. import callback_datas as calls

def autoresponse_confirm_text():
    config = sett.get("config")
    enabled = config.get("autoresponse", {}).get("confirm", {}).get("enabled", False)
    text = config.get("autoresponse", {}).get("confirm", {}).get("text", "Не задано")
    
    status = "✅ Включено" if enabled else "❌ Выключено"
    
    txt = textwrap.dedent(f"""
        ✨ <b>Сообщение при подтверждении</b>

        <b>Статус:</b> {status}
        <b>Текст сообщения:</b>
        <code>{text}</code>

        Используйте кнопки ниже для настройки:
    """)
    return txt

def autoresponse_confirm_kb():
    config = sett.get("config")
    enabled = config.get("autoresponse", {}).get("confirm", {}).get("enabled", False)
    
    rows = [
        [InlineKeyboardButton(
            text=f"{'❌ Выключить' if enabled else '✅ Включить'}",
            callback_data="toggle_confirm"
        )],
        [InlineKeyboardButton(
            text="✏️ Изменить текст",
            callback_data="edit_confirm_text"
        )],
        [
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=calls.SettingsNavigation(to="autoresponse").pack()
            ),
            InlineKeyboardButton(
                text="🔄 Обновить",
                callback_data=calls.SettingsNavigation(to="autoresponse_confirm").pack()
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
