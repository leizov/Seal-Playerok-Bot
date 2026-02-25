import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from .. import callback_datas as calls


def error_text(placeholder: str):
    txt = textwrap.dedent(f"""
        <b>❌ Возникла ошибка </b>

        <blockquote>{placeholder}</blockquote>
    """)
    return txt


def back_kb(cb: str):
    rows = [[InlineKeyboardButton(text="⬅️ Назад", callback_data=cb)]]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_kb(confirm_cb: str, cancel_cb: str):
    rows = [[
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=confirm_cb),
        InlineKeyboardButton(text="❌ Отменить", callback_data=cancel_cb)
    ]]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def destroy_kb():

    rows = [[InlineKeyboardButton(text="❌ Закрыть", callback_data="destroy")]]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def do_action_text(placeholder: str):
    txt = textwrap.dedent(f"""
        🧩 <b>Действие</b>
        \n{placeholder}
    """)
    return txt


def log_text(title: str, text: str, by: str = None):
    # Убираем dedent для корректного отображения отступов в Telegram
    txt = f"<b>{title}</b>\n\n{text}"
    if by:
        txt += f"\n\n<i>{by}</i>"
    return txt


def log_new_mess_kb(username: str, chat_id: str = None):
    rows = [
        [InlineKeyboardButton(text="💬 Написать", callback_data=calls.RememberUsername(name=username, do="send_mess").pack())],
        [InlineKeyboardButton(text="📋 Заготовки", callback_data=calls.RememberUsername(name=username, do="quick_reply").pack())]
    ]
    if chat_id:
        rows.append([InlineKeyboardButton(text="📜 Больше", callback_data=calls.ChatHistory(chat_id=chat_id).pack())])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def log_new_deal_kb(username: str, deal_id: str, chat_id: str = None):
    rows = [
        [InlineKeyboardButton(text="💬 Написать", callback_data=calls.RememberUsername(name=username, do="send_mess").pack())],
        [InlineKeyboardButton(text="🔗 Ссылка", url=f"https://playerok.com/deal/{deal_id}/")]
    ]
    if chat_id:
        rows.append([InlineKeyboardButton(text="📜 Больше", callback_data=calls.ChatHistory(chat_id=chat_id).pack())])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def log_new_review_kb(username: str, deal_id: str, chat_id: str = None):
    rows = [
        # [InlineKeyboardButton(text="💬🌟 Ответить на отзыв", callback_data=calls.RememberDealId(de_id=deal_id, do="answer_rev").pack())],
        [InlineKeyboardButton(text="💬 Написать", callback_data=calls.RememberUsername(name=username, do="send_mess").pack())],
        [InlineKeyboardButton(text="📋 Заготовки", callback_data=calls.RememberUsername(name=username, do="quick_reply").pack())]
    ]
    if chat_id:
        rows.append([InlineKeyboardButton(text="📜 Больше", callback_data=calls.ChatHistory(chat_id=chat_id).pack())])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def sign_text(placeholder: str):
    txt = textwrap.dedent(f"""
        🔐 <b>Авторизация</b>
        \n{placeholder}
    """)
    return txt


def call_seller_text(calling_name, chat_link):
    txt = textwrap.dedent(f"""
        🆘 <b>{calling_name}</b> требуется ваша помощь!
        {chat_link}
    """)
    return txt