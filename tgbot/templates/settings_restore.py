import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from settings import Settings as sett

from .. import callback_datas as calls


def settings_restore_text():
    config = sett.get("config")
    is_all_mode = bool(config["playerok"]["auto_restore_items"]["all"])
    auto_restore_items_expired = "🟢 Включено" if bool(config["playerok"]["auto_restore_items"].get("expired", False)) else "🔴 Выключено"
    auto_restore_items_all = "Все предметы" if is_all_mode else "Указанные предметы"
    auto_restore_items = sett.get("auto_restore_items")
    auto_restore_items_included = len(auto_restore_items["included"])
    auto_restore_items_excluded = len(auto_restore_items["excluded"])
    items_line = (
        f"➖ <b>Исключенные:</b> {auto_restore_items_excluded}"
        if is_all_mode
        else f"➕ <b>Включенные:</b> {auto_restore_items_included}"
    )
    txt = textwrap.dedent(f"""
        ⚙️ <b>Настройки → ♻️ Восстановление</b>

        <b>⏰ Истёкшие:</b> {auto_restore_items_expired}
        📦 <b>Восстанавливать:</b> {auto_restore_items_all}

        {items_line}

        <b>Что такое автоматическое восстановление предметов?</b>
        На Playerok как только ваш товар покупают - он исчезает из продажи. Эта функция позволит автоматически восстанавливать (заново выставлять) предмет, который только что купили, чтобы он снова был на продаже. Предмет будет выставлен с тем же статусом приоритета, что и был раньше.

        <b>Примечание:</b>
        Если вы выберете "Все предметы", то будут восстанавливаться все товары, кроме тех, что указаны в исключениях. Если вы выберете "Указанные предметы", то будут восстанавливаться только те товары, которые вы добавите во включенные.
        
        Выберите параметр для изменения ↓
    """)
    return txt


def settings_restore_kb():
    config = sett.get("config")
    is_all_mode = bool(config["playerok"]["auto_restore_items"]["all"])
    auto_restore_items_expired = "🟢 Включено" if bool(config["playerok"]["auto_restore_items"].get("expired", False)) else "🔴 Выключено"
    auto_restore_items_all = "Все предметы" if is_all_mode else "Указанные предметы"
    auto_restore_items = sett.get("auto_restore_items")
    auto_restore_items_included = len(auto_restore_items["included"])
    auto_restore_items_excluded = len(auto_restore_items["excluded"])

    rows = [
        [InlineKeyboardButton(text=f"⏰ Истёкшие: {auto_restore_items_expired}", callback_data="switch_auto_restore_items_expired")],
        [InlineKeyboardButton(text=f"📦 Восстанавливать: {auto_restore_items_all}", callback_data="switch_auto_restore_items_all")],
    ]

    if is_all_mode:
        rows.append([
            InlineKeyboardButton(
                text=f"➖ Исключенные: {auto_restore_items_excluded}",
                callback_data=calls.ExcludedRestoreItemsPagination(page=0).pack(),
            )
        ])
    else:
        rows.append([
            InlineKeyboardButton(
                text=f"➕ Включенные: {auto_restore_items_included}",
                callback_data=calls.IncludedRestoreItemsPagination(page=0).pack(),
            )
        ])

    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.MenuPagination(page=0).pack())])

    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def settings_restore_float_text(placeholder: str):
    txt = textwrap.dedent(f"""
        ⚙️ <b>Настройки → ♻️ Восстановление</b>
        \n{placeholder}
    """)
    return txt
