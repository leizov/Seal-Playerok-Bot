import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from settings import Settings as sett

from .. import callback_datas as calls


def settings_deliv_page_text(index: int):
    auto_deliveries = sett.get("auto_deliveries")
    keyphrases = "</code>, <code>".join(auto_deliveries[index].get("keyphrases")) or "❌ Не задано"
    message = "\n".join(auto_deliveries[index].get("message")) or "❌ Не задано"
    txt = textwrap.dedent(f"""
        ✏️ <b>Редактирование авто-выдачи</b>

        🔑 <b>Ключевые фразы:</b> <code>{keyphrases}</code>
        💬 <b>Сообщение:</b> <blockquote>{message}</blockquote>

        Выберите параметр для изменения ↓
    """)
    return txt


def settings_deliv_page_kb(index: int, page: int = 0):
    auto_deliveries = sett.get("auto_deliveries")
    keyphrases = ", ".join(auto_deliveries[index].get("keyphrases")) or "❌ Не задано"
    message = "\n".join(auto_deliveries[index].get("message")) or "❌ Не задано"
    rows = [
        [InlineKeyboardButton(text=f"🔑 Ключевые фразы: {keyphrases}", callback_data="enter_auto_delivery_keyphrases")],
        [InlineKeyboardButton(text=f"💬 Сообщение: {message}", callback_data="enter_auto_delivery_message")],
        [InlineKeyboardButton(text="🗑️ Удалить авто-выдачу", callback_data="confirm_deleting_auto_delivery")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.AutoDeliveriesPagination(page=page).pack())]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def settings_deliv_page_float_text(placeholder: str):
    txt = textwrap.dedent(f"""
        ✏️ <b>Редактирование авто-выдачи</b>
        \n{placeholder}
    """)
    return txt