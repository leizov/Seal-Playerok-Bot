import textwrap

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from settings import Settings as sett

from .. import callback_datas as calls


def settings_auto_complete_excluded_text():
    excluded_items = (sett.get("auto_complete_items") or {}).get("excluded", [])
    txt = textwrap.dedent(
f"""
<b>✅ Авто-подтверждение → ➖ Исключённые</b>

Здесь вы можете добавить ключевые фразы лотов, которые не будут подтверждаться автоматически.

<b>Всего исключено:</b> {len(excluded_items)}
"""
    )
    return txt


def settings_auto_complete_excluded_kb(page: int = 0):
    excluded_items: list[list] = (sett.get("auto_complete_items") or {}).get("excluded", [])
    rows = []
    items_per_page = 7

    if page < 0:
        page = 0

    start = page * items_per_page
    end = start + items_per_page
    if start >= len(excluded_items) and page > 0:
        page = max((len(excluded_items) - 1) // items_per_page, 0)
        start = page * items_per_page
        end = start + items_per_page

    for i, keyphrases in enumerate(excluded_items[start:end], start=start):
        keyphrases_str = ", ".join(keyphrases) if isinstance(keyphrases, list) else str(keyphrases)
        rows.append([
            InlineKeyboardButton(
                text=f"🗑 {keyphrases_str[:30]}{'...' if len(keyphrases_str) > 30 else ''}",
                callback_data=calls.DeleteExcludedAutoCompleteItem(index=i).pack(),
            )
        ])

    rows.append([InlineKeyboardButton(text="➡ Добавить", callback_data="add_excluded_auto_complete_item")])
    rows.append([InlineKeyboardButton(text="📄 Добавить из файла", callback_data="add_excluded_auto_complete_items_from_file")])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=calls.ExcludedAutoCompleteItemsPagination(page=page - 1).pack()))

    total_pages = (len(excluded_items) + items_per_page - 1) // items_per_page
    if total_pages > 0:
        nav_row.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="page_info"))

    if end < len(excluded_items):
        nav_row.append(InlineKeyboardButton(text="➡️", callback_data=calls.ExcludedAutoCompleteItemsPagination(page=page + 1).pack()))

    if nav_row:
        rows.append(nav_row)

    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.SettingsNavigation(to="auto_complete").pack())])

    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def settings_auto_complete_excluded_float_text(placeholder: str):
    txt = textwrap.dedent(
        f"""
        <b>✅ Авто-подтверждение → ➖ Исключённые</b>
        \n{placeholder}
    """
    )
    return txt


def settings_new_auto_complete_excluded_float_text(placeholder: str):
    txt = textwrap.dedent(
        f"""
        <b>✅ Авто-подтверждение → ➖ Исключённые → ➕ Добавить</b>
        \n{placeholder}
    """
    )
    return txt
