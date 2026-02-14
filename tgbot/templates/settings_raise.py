import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from settings import Settings as sett

from .. import callback_datas as calls


def settings_raise_text():
    config = sett.get("config")
    auto_raise_items_all = "Все предметы" if config["playerok"]["auto_raise_items"]["all"] else "Указанные предметы"
    auto_raise_items = sett.get("auto_raise_items")
    auto_raise_items_included = len(auto_raise_items["included"])
    auto_raise_items_excluded = len(auto_raise_items["excluded"])
    interval_hours = config["playerok"]["auto_raise_items"].get("interval_hours", 24)

    txt = textwrap.dedent(f"""
        ⚙️ <b>Настройки → 📈 Автоподнятие</b>

        📦 <b>Поднимать:</b> {auto_raise_items_all}
        ⏱ <b>Интервал:</b> {interval_hours} ч

        ➕ <b>Включенные:</b> {auto_raise_items_included}
        ➖ <b>Исключенные:</b> {auto_raise_items_excluded}

        <b>Что такое автоматическое поднятие товаров?</b>
        Бот автоматически поднимает ваши товары с премиум статусом через заданный интервал времени, чтобы они оставались в топе.

        <b>Как это работает?</b>
        • Бот проверяет товары каждую минуту
        • Поднимает только активные товары с премиум статусом
        • Для каждого товара запоминает время последнего поднятия
        • Поднимает товар только если прошёл заданный интервал

        Выберите действие ↓
    """)
    return txt


def settings_raise_kb():
    config = sett.get("config")
    auto_raise_items_all = "Все предметы" if config["playerok"]["auto_raise_items"]["all"] else "Указанные предметы"
    auto_raise_items = sett.get("auto_raise_items")
    auto_raise_items_included = len(auto_raise_items["included"])
    auto_raise_items_excluded = len(auto_raise_items["excluded"])
    interval_hours = config["playerok"]["auto_raise_items"].get("interval_hours", 24)

    rows = [
        [InlineKeyboardButton(text=f"📦 Поднимать: {auto_raise_items_all}", callback_data="switch_auto_raise_items_all")],
        [InlineKeyboardButton(text=f"⏱ Интервал: {interval_hours} ч", callback_data="set_auto_raise_items_interval")],
        [
        InlineKeyboardButton(text=f"➕ Включенные: {auto_raise_items_included}", callback_data=calls.IncludedRaiseItemsPagination(page=0).pack()),
        InlineKeyboardButton(text=f"➖ Исключенные: {auto_raise_items_excluded}", callback_data=calls.ExcludedRaiseItemsPagination(page=0).pack())
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.MenuPagination(page=0).pack())]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def settings_raise_float_text(placeholder: str):
    txt = textwrap.dedent(f"""
        ⚙️ <b>Настройки → 📈 Автоподнятие</b>
        \n{placeholder}
    """)
    return txt
