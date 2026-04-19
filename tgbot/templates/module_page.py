import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from uuid import UUID

from core.plugins import Plugin, get_plugin_by_uuid

from .. import callback_datas as calls


def plugin_page_text(plugin_uuid: UUID):
    plugin: Plugin = get_plugin_by_uuid(plugin_uuid)
    if not plugin: raise Exception("Не удалось найти плагин")
    txt = textwrap.dedent(f"""
        🔧 <b>Управление плагином</b>

        <b>Плагин</b> <code>{plugin.meta.name}</code>:          
        ┣ UUID: <b>{plugin.uuid}</b>
        ┣ Версия: <b>{plugin.meta.version}</b>
        ┣ Описание: <blockquote>{plugin.meta.description}</blockquote>
        ┣ Авторы: <b>{plugin.meta.authors}</b>
        ┗ Ссылки: <b>{plugin.meta.links}</b>

        🔌 <b>Состояние:</b> {'🟢 Включен' if plugin.enabled else '🔴 Выключен'}

        Выберите действие для управления ↓
    """)
    return txt


def plugin_page_kb(plugin_uuid: UUID, page: int = 0):
    plugin: Plugin = get_plugin_by_uuid(plugin_uuid)
    if not plugin: raise Exception("Не удалось найти плагин")
    rows = [
        [InlineKeyboardButton(text="🔴 Деактивировать плагин" if plugin.enabled else "🟢 Активировать плагин", callback_data="switch_plugin_enabled")],
        [InlineKeyboardButton(text="📋 Команды плагина", callback_data=calls.PluginCommands(uuid=plugin_uuid).pack())],
        [
            InlineKeyboardButton(text="📤 Выгрузить плагин", callback_data="plugin_export"),
            InlineKeyboardButton(text="🗑 Удалить плагин", callback_data="plugin_delete_ask")
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.PluginsPagination(page=page).pack())]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def plugin_page_float_text(placeholder: str):
    txt = textwrap.dedent(f"""
        🔧 <b>Управление плагином</b>
        \n{placeholder}
    """)
    return txt


def plugin_commands_text(plugin_uuid: UUID):
    plugin: Plugin = get_plugin_by_uuid(plugin_uuid)
    if not plugin: raise Exception("Не удалось найти плагин")
    
    txt = textwrap.dedent(f"""
        📋 <b>Команды плагина {plugin.meta.name}</b>
        
    """)
    
    if not plugin.bot_commands or len(plugin.bot_commands) == 0:
        txt += "❌ <i>Этот плагин не имеет команд</i>\n"
    else:
        txt += f"<b>Всего команд:</b> {len(plugin.bot_commands)}\n\n"
        for idx, command in enumerate(plugin.bot_commands, 1):
            if hasattr(command, 'command'):
                command_name = command.command
                description = command.description if hasattr(command, 'description') else 'Описание отсутствует'
            else:
                command_name = command.get('command', 'N/A')
                description = command.get('description', 'Описание отсутствует')
            txt += f"<b>{idx}.</b> /{command_name}\n"
            txt += f"   └ <i>{description}</i>\n\n"
    
    return txt


def plugin_commands_kb(plugin_uuid: UUID):
    plugin: Plugin = get_plugin_by_uuid(plugin_uuid)
    if not plugin: raise Exception("Не удалось найти плагин")
    
    rows = [
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.PluginPage(uuid=plugin_uuid).pack())]
    ]
    
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb
