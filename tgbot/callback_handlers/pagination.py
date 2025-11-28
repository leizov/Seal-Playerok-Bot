from aiogram import Router
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from .. import templates as templ
from .. import callback_datas as calls
from ..helpful import throw_float_message


router = Router()


@router.callback_query(calls.IncludedRestoreItemsPagination.filter())
async def callback_included_restore_items_pagination(callback: CallbackQuery, callback_data: calls.IncludedRestoreItemsPagination, state: FSMContext):
    await state.set_state(None)
    page = callback_data.page
    await state.update_data(last_page=page)
    await throw_float_message(state, callback.message, templ.settings_restore_included_text(), templ.settings_restore_included_kb(page), callback)


@router.callback_query(calls.ExcludedRestoreItemsPagination.filter())
async def callback_excluded_restore_items_pagination(callback: CallbackQuery, callback_data: calls.ExcludedRestoreItemsPagination, state: FSMContext):
    await state.set_state(None)
    page = callback_data.page
    await state.update_data(last_page=page)
    await throw_float_message(state, callback.message, templ.settings_restore_excluded_text(), templ.settings_restore_excluded_kb(page), callback)


@router.callback_query(calls.CustomCommandsPagination.filter())
async def callback_custom_commands_pagination(callback: CallbackQuery, callback_data: calls.CustomCommandsPagination, state: FSMContext):
    await state.set_state(None)
    page = callback_data.page
    await state.update_data(last_page=page)
    await throw_float_message(state, callback.message, templ.settings_comms_text(), templ.settings_comms_kb(page), callback)


@router.callback_query(calls.AutoDeliveriesPagination.filter())
async def callback_auto_delivery_pagination(callback: CallbackQuery, callback_data: calls.AutoDeliveriesPagination, state: FSMContext):
    await state.set_state(None)
    page = callback_data.page
    await state.update_data(last_page=page)
    await throw_float_message(state, callback.message, templ.settings_delivs_text(), templ.settings_delivs_kb(page), callback)


@router.callback_query(calls.PluginsPagination.filter())
async def callback_plugins_pagination(callback: CallbackQuery, callback_data: calls.PluginsPagination, state: FSMContext):
    try:
        await state.set_state(None)
        page = callback_data.page
        await state.update_data(last_page=page)
        await throw_float_message(state, callback.message, templ.plugins_text(), templ.plugins_kb(page), callback)
    except Exception as e:
        await callback.answer("❌ Ошибка при загрузке списка плагинов", show_alert=True)

@router.callback_query(calls.PluginPage.filter())
async def callback_plugin_page(callback: CallbackQuery, callback_data: calls.PluginPage, state: FSMContext):
    try:
        await state.set_state(None)
        plugin_uuid = callback_data.uuid
        await state.update_data(plugin_uuid=plugin_uuid)
        
        text = templ.plugin_page_text(plugin_uuid)
        keyboard = templ.plugin_page_kb(plugin_uuid, 0)
        
        await throw_float_message(
            state=state,
            message=callback.message,
            text=text,
            reply_markup=keyboard,
            callback=callback
        )
    except Exception as e:
        await callback.answer("❌ Ошибка при загрузке страницы плагина", show_alert=True)