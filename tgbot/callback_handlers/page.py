from aiogram import Router
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from .. import templates as templ
from .. import callback_datas as calls
from ..helpful import throw_float_message


router = Router()


@router.callback_query(calls.CustomCommandPage.filter())
async def callback_custom_command_page(callback: CallbackQuery, callback_data: calls.CustomCommandPage, state: FSMContext):
    await state.set_state(None)
    command = callback_data.command
    data = await state.get_data()
    await state.update_data(custom_command=command)
    last_page = data.get("last_page", 0)
    await throw_float_message(state, callback.message, templ.settings_comm_page_text(command), templ.settings_comm_page_kb(command, last_page), callback)


@router.callback_query(calls.AutoDeliveryPage.filter())
async def callback_custom_command_page(callback: CallbackQuery, callback_data: calls.AutoDeliveryPage, state: FSMContext):
    await state.set_state(None)
    index = callback_data.index
    data = await state.get_data()
    await state.update_data(auto_delivery_index=index)
    last_page = data.get("last_page", 0)
    await throw_float_message(state, callback.message, templ.settings_deliv_page_text(index), templ.settings_deliv_page_kb(index, last_page), callback)


@router.callback_query(calls.PluginPage.filter())
async def callback_plugin_page(callback: CallbackQuery, callback_data: calls.PluginPage, state: FSMContext):
    await state.set_state(None)
    plugin_uuid = callback_data.uuid
    data = await state.get_data()
    await state.update_data(plugin_uuid=plugin_uuid)
    last_page = data.get("last_page", 0)
    await throw_float_message(state, callback.message, templ.plugin_page_text(plugin_uuid), templ.plugin_page_kb(plugin_uuid, last_page), callback)


@router.callback_query(calls.PluginCommands.filter())
async def callback_plugin_commands(callback: CallbackQuery, callback_data: calls.PluginCommands, state: FSMContext):
    try:
        await state.set_state(None)
        plugin_uuid = callback_data.uuid
        await state.update_data(plugin_uuid=plugin_uuid)
        
        text = templ.plugin_commands_text(plugin_uuid)
        keyboard = templ.plugin_commands_kb(plugin_uuid)
        
        await throw_float_message(
            state=state,
            message=callback.message,
            text=text,
            reply_markup=keyboard,
            callback=callback
        )
    except Exception as e:
        await callback.answer("❌ Ошибка при загрузке команд плагина", show_alert=True)