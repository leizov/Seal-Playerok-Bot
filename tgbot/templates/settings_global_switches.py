import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from settings import Settings as sett

from .. import callback_datas as calls


def settings_global_switches_text():
    config = sett.get("config")
    messages = sett.get("messages")

    # Проверяем, есть ли хоть одно включенное сообщение для автоответа
    auto_response_active = any(msg.get("enabled", False) for msg in messages.values())
    auto_response_global = "💚" if config["playerok"].get("auto_response_enabled", True) else "💔"

    tg_logging_enabled = "💚" if config["playerok"]["tg_logging"]["enabled"] else "💔"
    auto_restore_items_enabled = "💚" if config["playerok"]["auto_restore_items"]["enabled"] else "💔"
    auto_raise_items_enabled = "💚" if config["playerok"]["auto_raise_items"]["enabled"] else "💔"
    auto_deliveries_enabled = "💚" if config["playerok"]["auto_deliveries"]["enabled"] else "💔"
    read_chat_enabled = "💚" if config["playerok"]["read_chat"]["enabled"] else "💔"
    auto_complete_deals_enabled = "💚" if config["playerok"]["auto_complete_deals"]["enabled"] else "💔"
    custom_commands_enabled = "💚" if config["playerok"]["custom_commands"]["enabled"] else "💔"

    txt = textwrap.dedent(f"""
        ⚙️ <b>Настройки → 🎛 Глобальные Переключатели</b>

        Здесь вы можете быстро включить или выключить основные функции бота.

        {auto_response_global} <b>Автоответ</b> {'(настроено: ' + str(len([m for m in messages.values() if m.get("enabled", False)])) + ')' if auto_response_active else '(не настроено)'}
        {tg_logging_enabled} <b>Уведомления в Telegram</b>
        {auto_restore_items_enabled} <b>Автовыставление товаров</b>
        {auto_raise_items_enabled} <b>Автоподнятие товаров</b>
        {auto_deliveries_enabled} <b>Автовыдача товаров</b>
        {read_chat_enabled} <b>Чтение чата перед отправкой</b>
        {auto_complete_deals_enabled} <b>Авто-подтверждение заказов</b>
        <i>(режим списка лотов настраивается в разделе «Авто-подтверждение»)</i>
        {custom_commands_enabled} <b>Пользовательские команды</b>

        Выберите переключатель ↓
    """)
    return txt


def settings_global_switches_kb():
    config = sett.get("config")

    auto_response_global = "💚" if config["playerok"].get("auto_response_enabled", True) else "💔"
    tg_logging_enabled = "💚" if config["playerok"]["tg_logging"]["enabled"] else "💔"
    auto_restore_items_enabled = "💚" if config["playerok"]["auto_restore_items"]["enabled"] else "💔"
    auto_raise_items_enabled = "💚" if config["playerok"]["auto_raise_items"]["enabled"] else "💔"
    auto_deliveries_enabled = "💚" if config["playerok"]["auto_deliveries"]["enabled"] else "💔"
    read_chat_enabled = "💚" if config["playerok"]["read_chat"]["enabled"] else "💔"
    auto_complete_deals_enabled = "💚" if config["playerok"]["auto_complete_deals"]["enabled"] else "💔"
    custom_commands_enabled = "💚" if config["playerok"]["custom_commands"]["enabled"] else "💔"

    rows = [
        [InlineKeyboardButton(text=f"{auto_response_global} Автоответ", callback_data="switch_auto_response_enabled")],
        [InlineKeyboardButton(text=f"{tg_logging_enabled} Уведомления в Telegram", callback_data="switch_tg_logging_enabled")],
        [InlineKeyboardButton(text=f"{auto_restore_items_enabled} Автовыставление товаров", callback_data="switch_auto_restore_items_enabled")],
        [InlineKeyboardButton(text=f"{auto_raise_items_enabled} Автоподнятие товаров", callback_data="switch_auto_raise_items_enabled")],
        [InlineKeyboardButton(text=f"{auto_deliveries_enabled} Автовыдача товаров", callback_data="switch_auto_deliveries_enabled")],
        [InlineKeyboardButton(text=f"{read_chat_enabled} Чтение чата перед отправкой", callback_data="switch_read_chat_enabled")],
        [InlineKeyboardButton(text=f"{auto_complete_deals_enabled} Авто-подтверждение заказов", callback_data="switch_auto_complete_deals_enabled")],
        [InlineKeyboardButton(text=f"{custom_commands_enabled} Пользовательские команды", callback_data="switch_custom_commands_enabled")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.MenuPagination(page=0).pack())]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def settings_global_switches_float_text(placeholder: str):
    txt = textwrap.dedent(f"""
        ⚙️ <b>Настройки → 🎛 Глобальные Переключатели</b>
        \n{placeholder}
    """)
    return txt
