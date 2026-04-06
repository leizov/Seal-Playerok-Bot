import textwrap

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from settings import Settings as sett

from .. import callback_datas as calls


def settings_auto_complete_included_text():
    included_items = (sett.get("auto_complete_items") or {}).get("included", [])
    txt = textwrap.dedent(
f"""
<b>✅ Авто-подтверждение → ➕ Включённые</b>

Здесь вы можете добавить ключевые фразы товаров для режима «Только включённые».
Если название товара совпадёт с одной из фраз, сделка будет подтверждена автоматически.

<b>Всего включено:</b> {len(included_items)}
"""
    )
    return txt


def settings_auto_complete_included_kb(page: int = 0):
    included_items: list[list] = (sett.get("auto_complete_items") or {}).get("included", [])
    rows = []
    items_per_page = 7

    if page < 0:
        page = 0

    start = page * items_per_page
    end = start + items_per_page
    if start >= len(included_items) and page > 0:
        page = max((len(included_items) - 1) // items_per_page, 0)
        start = page * items_per_page
        end = start + items_per_page

    for i, keyphrases in enumerate(included_items[start:end], start=start):
        keyphrases_str = ", ".join(keyphrases) if isinstance(keyphrases, list) else str(keyphrases)
        rows.append([
            InlineKeyboardButton(
                text=f"🗑 {keyphrases_str[:30]}{'...' if len(keyphrases_str) > 30 else ''}",
                callback_data=calls.DeleteIncludedAutoCompleteItem(index=i).pack(),
            )
        ])

    rows.append([InlineKeyboardButton(text="➡ Добавить", callback_data="add_included_auto_complete_item")])
    rows.append([InlineKeyboardButton(text="📄 Добавить из файла", callback_data="add_included_auto_complete_items_from_file")])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=calls.IncludedAutoCompleteItemsPagination(page=page - 1).pack()))

    total_pages = (len(included_items) + items_per_page - 1) // items_per_page
    if total_pages > 0:
        nav_row.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="page_info"))

    if end < len(included_items):
        nav_row.append(InlineKeyboardButton(text="➡️", callback_data=calls.IncludedAutoCompleteItemsPagination(page=page + 1).pack()))

    if nav_row:
        rows.append(nav_row)

    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.SettingsNavigation(to="auto_complete").pack())])

    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def settings_auto_complete_included_float_text(placeholder: str):
    txt = textwrap.dedent(
        f"""
        <b>✅ Авто-подтверждение → ➕ Включённые</b>
        \n{placeholder}
    """
    )
    return txt


def settings_new_auto_complete_included_float_text(placeholder: str):
    txt = textwrap.dedent(
        f"""
        <b>✅ Авто-подтверждение → ➕ Включённые → ➕ Добавить</b>
        \n{placeholder}
    """
    )
    return txt
