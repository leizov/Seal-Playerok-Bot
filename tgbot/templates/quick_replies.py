import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from settings import Settings as sett
from .. import callback_datas as calls


def settings_quick_replies_text():
    quick_replies = sett.get("quick_replies")
    
    if not quick_replies:
        replies_list = "└ <i>Заготовки отсутствуют</i>"
    else:
        items = list(quick_replies.items())
        replies_list = []
        for i, (name, text) in enumerate(items):
            prefix = "└" if i == len(items) - 1 else "├"
            replies_list.append(f"{prefix} <b>{name}</b>: {text[:50]}{'...' if len(text) > 50 else ''}")
        replies_list = "\n".join(replies_list)
    
    txt = f"""
⚙️ <b>Настройки → 📋 Заготовки ответов</b>
<b>Быстрые заготовки для ответов пользователям</b>

{replies_list}

Выберите действие ↓
"""
    return txt


def settings_quick_replies_kb():
    rows = [
        [InlineKeyboardButton(text="➕ Добавить заготовку", callback_data=calls.QuickReplyAction(action="add").pack())],
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data=calls.QuickReplyAction(action="edit").pack())],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=calls.QuickReplyAction(action="delete").pack())],
        [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data=calls.MenuPagination(page=0).pack())]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def quick_reply_select_kb(username: str):
    quick_replies = sett.get("quick_replies")
    
    rows = []
    if quick_replies:
        for name in quick_replies.keys():
            rows.append([InlineKeyboardButton(
                text=f"📋 {name}", 
                callback_data=calls.QuickReplySelect(username=username, reply_name=name).pack()
            )])
    
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="destroy")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def quick_reply_delete_kb():
    quick_replies = sett.get("quick_replies")
    
    rows = []
    if quick_replies:
        for name in quick_replies.keys():
            rows.append([InlineKeyboardButton(
                text=f"🗑 {name}", 
                callback_data=calls.QuickReplyAction(action="confirm_delete", reply_name=name).pack()
            )])
    
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.SettingsNavigation(to="quick_replies").pack())])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def quick_reply_edit_kb():
    quick_replies = sett.get("quick_replies")
    
    rows = []
    if quick_replies:
        for name in quick_replies.keys():
            rows.append([InlineKeyboardButton(
                text=f"✏️ {name}", 
                callback_data=calls.QuickReplyAction(action="confirm_edit", reply_name=name).pack()
            )])
    
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.SettingsNavigation(to="quick_replies").pack())])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb
