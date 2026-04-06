import textwrap

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from settings import Settings as sett

from .. import callback_datas as calls


def settings_auto_complete_text():
    config = sett.get("config")
    auto_complete_config = config["playerok"]["auto_complete_deals"]
    auto_complete_items = sett.get("auto_complete_items")

    confirm_all = bool(auto_complete_config.get("all", True))
    confirm_mode = "Все лоты" if confirm_all else "Только включённые"
    included_count = len((auto_complete_items or {}).get("included", []))
    excluded_count = len((auto_complete_items or {}).get("excluded", []))
    items_line = (
        f"➖ <b>Исключённые:</b> {excluded_count}"
        if confirm_all
        else f"➕ <b>Включённые:</b> {included_count}"
    )

    if confirm_all:
        mode_instruction = textwrap.dedent(
            """
            <b>Как работает режим «Все лоты»?</b>
            Бот автоматически подтверждает каждую оплаченную сделку,
            кроме лотов из списка исключённых.
            """
        ).strip()
    else:
        mode_instruction = textwrap.dedent(
            """
            <b>Как работает режим «Только включённые»?</b>
            Бот подтверждает только те сделки, где название товара совпадает
            с ключевыми фразами из включённых, и не совпадает с исключёнными.
            """
        ).strip()

    txt = textwrap.dedent(
f"""
⚙️ <b>Настройки → ✅ Авто-подтверждение</b>

📦 <b>Подтверждать:</b> {confirm_mode}
{items_line}

<b>Что такое Авто-подтверждение?</b>
Бот может автоматически переводить оплаченные сделки в статус «выполнено».

{mode_instruction}

Выберите параметр для изменения ↓
"""
    )
    return txt


def settings_auto_complete_kb():
    config = sett.get("config")
    auto_complete_config = config["playerok"]["auto_complete_deals"]
    auto_complete_items = sett.get("auto_complete_items")

    confirm_all = bool(auto_complete_config.get("all", True))
    confirm_mode = "Все лоты" if confirm_all else "Только включённые"
    included_count = len((auto_complete_items or {}).get("included", []))
    excluded_count = len((auto_complete_items or {}).get("excluded", []))

    rows = [[InlineKeyboardButton(text=f"📦 Подтверждать: {confirm_mode}", callback_data="switch_auto_complete_deals_all")]]

    if confirm_all:
        rows.append([
            InlineKeyboardButton(
                text=f"➖ Исключённые: {excluded_count}",
                callback_data=calls.ExcludedAutoCompleteItemsPagination(page=0).pack(),
            )
        ])
    else:
        rows.append([
            InlineKeyboardButton(
                text=f"➕ Включённые: {included_count}",
                callback_data=calls.IncludedAutoCompleteItemsPagination(page=0).pack(),
            )
        ])

    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.MenuPagination(page=0).pack())])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def settings_auto_complete_float_text(placeholder: str):
    txt = textwrap.dedent(
        f"""
        ⚙️ <b>Настройки → ✅ Авто-подтверждение</b>
        \n{placeholder}
    """
    )
    return txt
