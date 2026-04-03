import html
import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from settings import Settings as sett
from plbot.auto_reminder import (
    DEFAULT_MESSAGE_TEXT,
    LEGACY_DEFAULT_MESSAGE_TEXT,
    get_monitoring_stats,
)

from .. import callback_datas as calls


def _get_config_values() -> tuple[bool, float, int, str]:
    config = sett.get("config")
    auto_reminder = config.get("playerok", {}).get("auto_reminder", {})

    enabled = bool(auto_reminder.get("enabled", False))

    try:
        interval_hours = float(auto_reminder.get("interval_hours", 24.0))
    except Exception:
        interval_hours = 24.0
    if interval_hours <= 0:
        interval_hours = 24.0

    try:
        max_reminders = int(auto_reminder.get("max_reminders", 3))
    except Exception:
        max_reminders = 3
    if max_reminders < 0:
        max_reminders = 0

    message_text = str(auto_reminder.get("message_text") or "").strip()
    if not message_text or message_text == LEGACY_DEFAULT_MESSAGE_TEXT:
        message_text = DEFAULT_MESSAGE_TEXT

    return enabled, interval_hours, max_reminders, message_text


def settings_auto_reminder_text():
    enabled, interval_hours, max_reminders, message_text = _get_config_values()
    status = "🟢 Включено" if enabled else "🔴 Выключено"
    limit_text = "♾ Без лимита" if max_reminders == 0 else str(max_reminders)

    total_deals = 0
    try:
        stats = get_monitoring_stats()
        total_deals = int(stats.get("total", 0))
    except Exception:
        total_deals = 0

    safe_message_text = html.escape(message_text)

    txt = textwrap.dedent(f"""
⏰ <b>Настройки → Авто-Напоминание</b>

<b>Статус:</b> {status}
<b>Интервал напоминаний:</b> {interval_hours:g} ч.
<b>Лимит напоминаний:</b> {limit_text}
<b>Сделок в памяти:</b> {total_deals}

<b>Текст напоминания:</b>
<blockquote>{safe_message_text}</blockquote>

<b>Доступные теги:</b>
• <code>{"{deal_link}"}</code> — ссылка на сделку
• <code>{"{buyer_name}"}</code> — имя покупателя

Используйте кнопки ниже для управления ↓
    """)
    return txt


def settings_auto_reminder_kb():
    enabled, interval_hours, max_reminders, _ = _get_config_values()

    toggle_text = "🟢 Авто-напоминание включено" if enabled else "🔴 Авто-напоминание выключено"
    limit_text = "♾ Без лимита" if max_reminders == 0 else f"{max_reminders}"

    rows = [
        [InlineKeyboardButton(text=toggle_text, callback_data="switch_auto_reminder_enabled")],
        [InlineKeyboardButton(text=f"⏱ Интервал: {interval_hours:g} ч.", callback_data="set_auto_reminder_interval")],
        [InlineKeyboardButton(text=f"🔢 Лимит: {limit_text}", callback_data="set_auto_reminder_max_reminders")],
        [InlineKeyboardButton(text="✏️ Изменить текст напоминания", callback_data="set_auto_reminder_message_text")],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.MenuPagination(page=1).pack()),
            InlineKeyboardButton(text="🔄 Обновить", callback_data=calls.SettingsNavigation(to="auto_reminder").pack()),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_auto_reminder_float_text(placeholder: str):
    txt = textwrap.dedent(f"""
        ⏰ <b>Настройки → Авто-Напоминание</b>
        \n{placeholder}
    """)
    return txt
