import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from settings import Settings as sett

from .. import callback_datas as calls


def settings_notifications_text():
    config = sett.get("config")
    tg_logging_chat_id = config["playerok"]["tg_logging"]["chat_id"] or "✔️ Ваш чат с ботом"
    tg_logging_events = config["playerok"]["tg_logging"]["events"] or {}
    event_new_user_message = "🔔" if tg_logging_events.get("new_user_message", True) else "🔕"
    event_new_system_message = "🔔" if tg_logging_events.get("new_system_message", True) else "🔕"
    event_new_deal = "🔔" if tg_logging_events.get("new_deal", True) else "🔕"
    event_new_review = "🔔" if tg_logging_events.get("new_review", True) else "🔕"
    event_new_problem = "🔔" if tg_logging_events.get("new_problem", True) else "🔕"
    event_deal_status_changed = "🔔" if tg_logging_events.get("deal_status_changed", True) else "🔕"
    event_command_received = "🔔" if tg_logging_events.get("command_received", True) else "🔕"
    event_auto_delivery = "🔔" if tg_logging_events.get("auto_delivery", True) else "🔕"
    event_item_raised = "🔔" if tg_logging_events.get("item_raised", False) else "🔕"
    txt = textwrap.dedent(f"""
        ⚙️ <b>Настройки → 🔔 Уведомления</b>

        💬 <b>ID чата для уведомлений:</b> <b>{tg_logging_chat_id}</b>
        📢 <b>Типы уведомлений:</b>
        ┣ {event_new_user_message} <b>Новое сообщение от пользователя</b>
        ┣ {event_new_system_message} <b>Новое системное сообщение</b>
        ┣ {event_command_received} <b>Получена команда</b>
        ┣ {event_new_deal} <b>Новая сделка</b>
        ┣ {event_auto_delivery} <b>Выдача товара из автовыдачи</b>
        ┣ {event_item_raised} <b>Товар поднят</b>
        ┣ {event_new_review} <b>Новый отзыв</b>
        ┣ {event_new_problem} <b>Новая жалоба в сделке</b>
        ┗ {event_deal_status_changed} <b>Статус сделки изменился</b>
        
        Выберите параметр для изменения ↓
    """)
    return txt


def settings_notifications_kb():
    config = sett.get("config")
    # tg_logging_chat_id = config["playerok"]["tg_logging"]["chat_id"] or "✔️ Ваш чат с ботом"
    tg_logging_events = config["playerok"]["tg_logging"]["events"] or {}
    event_new_user_message = "🔔" if tg_logging_events.get("new_user_message", True) else "🔕"
    event_new_system_message = "🔔" if tg_logging_events.get("new_system_message", True) else "🔕"
    event_command_received = "🔔" if tg_logging_events.get("command_received", True) else "🔕"
    event_new_deal = "🔔" if tg_logging_events.get("new_deal", True) else "🔕"
    event_auto_delivery = "🔔" if tg_logging_events.get("auto_delivery", True) else "🔕"
    event_item_raised = "🔔" if tg_logging_events.get("item_raised", False) else "🔕"
    event_new_review = "🔔" if tg_logging_events.get("new_review", True) else "🔕"
    event_new_problem = "🔔" if tg_logging_events.get("new_problem", True) else "🔕"
    event_deal_status_changed = "🔔" if tg_logging_events.get("deal_status_changed", True) else "🔕"
    rows = [
        # [InlineKeyboardButton(text=f"💬 ID чата для уведомлений: {tg_logging_chat_id}", callback_data="enter_tg_logging_chat_id")],
        [
            InlineKeyboardButton(text=f"{event_new_user_message} Новое сообщение от пользователя", callback_data="switch_tg_logging_event_new_user_message"),
            InlineKeyboardButton(text=f"{event_new_system_message} Новое системное сообщение", callback_data="switch_tg_logging_event_new_system_message")
        ],
        [
            InlineKeyboardButton(text=f"{event_command_received} Получена команда", callback_data="switch_tg_logging_event_command_received")
        ],
        [
            InlineKeyboardButton(text=f"{event_new_deal} Новая сделка", callback_data="switch_tg_logging_event_new_deal"),
            InlineKeyboardButton(text=f"{event_auto_delivery} Выдача товара из автовыдачи", callback_data="switch_tg_logging_event_auto_delivery")
        ],
        [
            InlineKeyboardButton(text=f"{event_item_raised} Товар поднят", callback_data="switch_tg_logging_event_item_raised")
        ],
        [
            InlineKeyboardButton(text=f"{event_new_review} Новый отзыв", callback_data="switch_tg_logging_event_new_review"),
            InlineKeyboardButton(text=f"{event_new_problem} Новая жалоба в сделке", callback_data="switch_tg_logging_event_new_problem")
        ],
        [InlineKeyboardButton(text=f"{event_deal_status_changed} Статус сделки изменился", callback_data="switch_tg_logging_event_deal_status_changed")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.MenuPagination(page=0).pack())]
    ]
    if config["playerok"]["tg_logging"]["chat_id"]:
        rows[0].append(InlineKeyboardButton(text=f"❌💬 Очистить", callback_data="clean_tg_logging_chat_id"))
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def settings_notifications_float_text(placeholder: str):
    txt = textwrap.dedent(f"""
        ⚙️ <b>Настройки → 🔔 Уведомления</b>
        \n{placeholder}
    """)
    return txt