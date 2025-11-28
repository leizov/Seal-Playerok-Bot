import math
import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from core.plugins import get_plugins

from .. import callback_datas as calls

                    
def plugins_text():
    plugins = get_plugins()
    txt = textwrap.dedent(f"""
        🔌 <b>Плагины</b>
        Всего <b>{len(plugins)}</b> загруженных плагинов

        Перемещайтесь по разделам ниже. Нажмите на название плагина, чтобы перейти в его управление ↓
        
        💡 <i>Для обновления кода плагинов используйте команду /restart</i>
    """)
    return txt


def plugins_kb(page: int = 0):
    plugins = get_plugins()
    rows = []
    items_per_page = 7
    total_pages = math.ceil(len(plugins) / items_per_page)
    total_pages = total_pages if total_pages > 0 else 1

    if page < 0: page = 0
    elif page >= total_pages: page = total_pages - 1

    start_offset = page * items_per_page
    end_offset = start_offset + items_per_page

    for plugin in list(plugins)[start_offset:end_offset]:
        rows.append([InlineKeyboardButton(text=plugin.meta.name, callback_data=calls.PluginPage(uuid=plugin.uuid).pack())])

    if total_pages > 1:
        buttons_row = []
        btn_back = InlineKeyboardButton(text="←", callback_data=calls.PluginsPagination(page=page - 1).pack()) if page > 0 else InlineKeyboardButton(text="🛑", callback_data="123")
        buttons_row.append(btn_back)

        btn_pages = InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="enter_plugin_page")
        buttons_row.append(btn_pages)

        btn_next = InlineKeyboardButton(text="→", callback_data=calls.PluginsPagination(page=page+1).pack()) if page < total_pages - 1 else InlineKeyboardButton(text="🛑", callback_data="123")
        buttons_row.append(btn_next)
        rows.append(buttons_row)

    rows.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.MenuPagination(page=0).pack())
    ])

    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb