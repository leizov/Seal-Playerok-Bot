import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from settings import Settings as sett
from .. import callback_datas as calls
#old
def autoresponse_return_text():
    config = sett.get("config")
    enabled = config.get("autoresponse", {}).get("return", {}).get("enabled", False)
    text = config.get("autoresponse", {}).get("return", {}).get("text", "Не задано")
    
    status = "✅ Включено" if enabled else "❌ Выключено"
    
    txt = textwrap.dedent(f"""
        🔄 <b>Сообщение при возврате</b>

        <b>Статус:</b> {status}
        <b>Текст сообщения:</b>
        <code>{text}</code>

        Используйте кнопки ниже для настройки:
    """)
    return txt

def autoresponse_return_kb():
    config = sett.get("config")
    enabled = config.get("autoresponse", {}).get("return", {}).get("enabled", False)
    
    rows = [
        [InlineKeyboardButton(
            text=f"{'❌ Выключить' if enabled else '✅ Включить'}",
            callback_data="toggle_return"
        )],
        [InlineKeyboardButton(
            text="✏️ Изменить текст",
            callback_data="edit_return_text"
        )],
        [
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=calls.SettingsNavigation(to="autoresponse").pack()
            ),
            InlineKeyboardButton(
                text="🔄 Обновить",
                callback_data=calls.SettingsNavigation(to="autoresponse_return").pack()
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
