import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from settings import Settings as sett
from .. import callback_datas as calls


def notifications_text():
    config = sett.get("config")
    tg_logging = config["playerok"]["tg_logging"]
    
    # Статус уведомлений
    status = "🟢 Включены" if tg_logging["enabled"] else "🔴 Выключены"
    chat_id = tg_logging["chat_id"] or "❌ Не задан"
    
    # События
    events = tg_logging["events"]
    
    txt = textwrap.dedent(f"""
        🔔 <b>Управление уведомлениями</b>

        <b>Общий статус:</b> {status}
        <b>Чат для уведомлений:</b> <code>{chat_id}</code>

        <b>Уведомления о событиях:</b>
        ┣ {"✅" if events["new_user_message"] else "❌"} Новые сообщения от пользователей
        ┣ {"✅" if events["new_system_message"] else "❌"} Системные уведомления
        ┣ {"✅" if events["new_deal"] else "❌"} Новые сделки
        ┣ {"✅" if events["new_review"] else "❌"} Новые отзывы
        ┣ {"✅" if events["new_problem"] else "❌"} Проблемы в сделках
        ┗ {"✅" if events["deal_status_changed"] else "❌"} Изменения статуса сделок

        Выберите параметр для изменения ↓
    """)
    return txt


def notifications_kb():
    config = sett.get("config")
    tg_logging = config["playerok"]["tg_logging"]
    
    rows = [
        [
            InlineKeyboardButton(
                text=f"🔔 {'Выключить' if tg_logging['enabled'] else 'Включить'} уведомления",
                callback_data="toggle_notifications"
            )
        ],
        [
            InlineKeyboardButton(
                text="💬 Настроить чат для уведомлений",
                callback_data="set_notification_chat"
            )
        ],
        [
            InlineKeyboardButton(
                text="⚙️ Настроить события",
                callback_data="configure_events"
            )
        ],
        [
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=calls.MenuNavigation(to="main").pack()
            ),
            InlineKeyboardButton(
                text="🔄 Обновить",
                callback_data=calls.SettingsNavigation(to="notifications").pack()
            )
        ]
    ]
    
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb
