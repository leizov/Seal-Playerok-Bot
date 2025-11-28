import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from settings import Settings as sett
from .. import callback_datas as calls

def autoresponse_text():
    config = sett.get("config")
    welcome_enabled = "✅ Включено" if config.get("autoresponse", {}).get("welcome", {}).get("enabled", False) else "❌ Выключено"
    confirm_enabled = "✅ Включено" if config.get("autoresponse", {}).get("confirm", {}).get("enabled", False) else "❌ Выключено"
    return_enabled = "✅ Включено" if config.get("autoresponse", {}).get("return", {}).get("enabled", False) else "❌ Выключено"
    
    txt = textwrap.dedent(f"""
        💬 <b>Управление автоответами</b>

        Выберите тип сообщения для настройки:
        
        👋 <b>Приветственное сообщение</b> - {welcome_enabled}
        ✨ <b>Сообщение при подтверждении</b> - {confirm_enabled}
        🔄 <b>Сообщение при возврате</b> - {return_enabled}
    """)
    return txt

def autoresponse_kb():
    rows = [
        [InlineKeyboardButton(
            text="👋 Приветственное сообщение",
            callback_data=calls.SettingsNavigation(to="autoresponse_welcome").pack()
        )],
        [InlineKeyboardButton(
            text="✨ Сообщение при подтверждении",
            callback_data=calls.SettingsNavigation(to="autoresponse_confirm").pack()
        )],
        [InlineKeyboardButton(
            text="🔄 Сообщение при возврате",
            callback_data=calls.SettingsNavigation(to="autoresponse_return").pack()
        )],
        [
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=calls.MenuPagination(page=0).pack()
            ),
            InlineKeyboardButton(
                text="🔄 Обновить",
                callback_data=calls.SettingsNavigation(to="autoresponse").pack()
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
