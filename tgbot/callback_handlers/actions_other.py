from aiogram import F, Router
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramAPIError

from playerokapi.enums import ItemDealStatuses
from settings import Settings as sett

from .. import templates as templ
from .. import callback_datas as calls
from .. import states
from ..helpful import throw_float_message
from ..utils.deal_formatter import format_deal_card_text
from .navigation import *
from .pagination import (
    callback_included_restore_items_pagination, 
    callback_excluded_restore_items_pagination,
    callback_included_raise_items_pagination,
    callback_excluded_raise_items_pagination
)
from .page import callback_plugin_page


router = Router()


@router.callback_query(F.data == "destroy")
async def callback_back(callback: CallbackQuery, state: FSMContext):
    await state.set_state(None)
    await callback.message.delete()


@router.callback_query(calls.DeleteIncludedRestoreItem.filter())
async def callback_delete_included_restore_item(callback: CallbackQuery, callback_data: calls.DeleteIncludedRestoreItem, state: FSMContext):
    try:
        await state.set_state(None)
        index = callback_data.index
        if index is None:
            raise Exception("❌ Включенный предмет не был найден, повторите процесс с самого начала")
        
        auto_restore_items = sett.get("auto_restore_items")
        auto_restore_items["included"].pop(index)
        sett.set("auto_restore_items", auto_restore_items)

        data = await state.get_data()
        last_page = data.get("last_page", 0)
        return await callback_excluded_restore_items_pagination(callback, calls.ExcludedRestoreItemsPagination(page=last_page), state)
    except Exception as e:
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.settings_restore_excluded_float_text(e), 
            reply_markup=templ.back_kb(calls.ExcludedRestoreItemsPagination(page=last_page).pack())
        )


@router.callback_query(calls.DeleteExcludedRestoreItem.filter())
async def callback_delete_excluded_restore_item(callback: CallbackQuery, callback_data: calls.DeleteExcludedRestoreItem, state: FSMContext):
    try:
        await state.set_state(None)
        index = callback_data.index
        if index is None:
            raise Exception("❌ Исключенный предмет не был найден, повторите процесс с самого начала")
        
        auto_restore_items = sett.get("auto_restore_items")
        auto_restore_items["excluded"].pop(index)
        sett.set("auto_restore_items", auto_restore_items)

        data = await state.get_data()
        last_page = data.get("last_page", 0)
        return await callback_excluded_restore_items_pagination(callback, calls.ExcludedRestoreItemsPagination(page=last_page), state)
    except Exception as e:
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.settings_restore_included_float_text(e), 
            reply_markup=templ.back_kb(calls.IncludedRestoreItemsPagination(page=last_page).pack())
        )


@router.callback_query(calls.RememberUsername.filter(F.do == "send_mess"))
async def callback_remember_username(callback: CallbackQuery, callback_data: calls.RememberUsername, state: FSMContext):
    await state.set_state(None)
    username = callback_data.name
    await state.update_data(username=username)
    await state.set_state(states.ActionsStates.waiting_for_message_text)
    prompt_message = await throw_float_message(
        state=state, 
        message=callback.message, 
        text=templ.do_action_text(f"💬 Введите <b>сообщение</b> для отправки <b>{username}</b> ↓"), 
        reply_markup=templ.destroy_kb(),
        callback=callback,
        send=True
    )
    if prompt_message:
        await state.update_data(accent_message_id=prompt_message.message_id, write_prompt_message_id=prompt_message.message_id)


@router.callback_query(calls.RememberDealId.filter())
async def callback_remember_deal_id(callback: CallbackQuery, callback_data: calls.RememberDealId, state: FSMContext):
    await state.set_state(None)
    deal_id = callback_data.de_id
    do = callback_data.do
    await state.update_data(deal_id=deal_id)
    if do == "refund":
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.do_action_text(f'📦✔️ Подтвердите <b>возврат</b> <a href="https://playerok.com/deal/{deal_id}">сделки</a> ↓'), 
            reply_markup=templ.confirm_kb(confirm_cb="refund_deal", cancel_cb="destroy"),
            callback=callback,
            send=True
        )
    if do == "complete":
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.do_action_text(f'☑️✔️ Подтвердите <b>выполнение</b> <a href="https://playerok.com/deal/{deal_id}">сделки</a> ↓'), 
            reply_markup=templ.confirm_kb(confirm_cb="complete_deal", cancel_cb="destroy"),
            callback=callback,
            send=True
        )
        

@router.callback_query(calls.DealView.filter())
async def callback_deal_view(callback: CallbackQuery, callback_data: calls.DealView, state: FSMContext):
    from plbot.playerokbot import get_playerok_bot

    await state.set_state(None)
    plbot = get_playerok_bot()
    if not plbot or not plbot.playerok_account:
        await callback.answer("❌ Нет подключения к Playerok", show_alert=True)
        return

    deal_id = callback_data.de_id
    try:
        full_deal = plbot.playerok_account.get_deal(deal_id)
        username = getattr(getattr(full_deal, "user", None), "username", None)
        chat_id = getattr(getattr(full_deal, "chat", None), "id", None)
        chat_id = str(chat_id) if chat_id is not None else None
        text = format_deal_card_text(full_deal)
        reply_markup = templ.deal_view_kb(
            username=username,
            deal_id=deal_id,
            deal_status=getattr(full_deal, "status", None),
            chat_id=chat_id,
        )

        try:
            await callback.message.edit_text(
                text,
                reply_markup=reply_markup,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        except TelegramAPIError as e:
            err_msg = str(e).lower()
            if "message is too long" in err_msg:
                trimmed_text = text[:3900] + "\n\n<i>⚠️ Карточка сокращена из-за лимита Telegram.</i>"
                await callback.message.edit_text(
                    trimmed_text,
                    reply_markup=reply_markup,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
            elif "message is not modified" in err_msg:
                pass
            else:
                raise
        await callback.answer()
    except Exception as e:
        await callback.answer(f"❌ Не удалось открыть сделку: {e}", show_alert=True)


@router.callback_query(F.data == "refund_deal")
async def callback_refund_deal(callback: CallbackQuery, state: FSMContext):
    from plbot.playerokbot import get_playerok_bot
    await state.set_state(None)
    plbot = get_playerok_bot()
    data = await state.get_data()
    deal_id = data.get("deal_id")
    plbot.playerok_account.update_deal(deal_id, ItemDealStatuses.ROLLED_BACK)
    await throw_float_message(
        state=state, 
        message=callback.message, 
        text=templ.do_action_text(f"✅ По сделке <b>https://playerok.com/deal/{deal_id}</b> был оформлен возврат"), 
        reply_markup=templ.destroy_kb()
    )
        

@router.callback_query(F.data == "complete_deal")
async def callback_complete_deal(callback: CallbackQuery, state: FSMContext):
    from plbot.playerokbot import get_playerok_bot
    await state.set_state(None)
    plbot = get_playerok_bot()
    data = await state.get_data()
    deal_id = data.get("deal_id")
    plbot.playerok_account.update_deal(deal_id, ItemDealStatuses.SENT)
    await throw_float_message(
        state=state, 
        message=callback.message, 
        text=templ.do_action_text(f"✅ Сделка <b>https://playerok.com/deal/{deal_id}</b> была помечена вами, как выполненная"), 
        reply_markup=templ.destroy_kb()
    )


# Старый обработчик удаления прокси - теперь используется новая система управления прокси
# См. tgbot/callback_handlers/proxy_management.py
# @router.callback_query(F.data == "clean_proxy")
# async def callback_clean_proxy(callback: CallbackQuery, state: FSMContext):
#     await state.set_state(None)
#     config = sett.get("config")
#     proxy = config["playerok"]["api"]["proxy"] = ""
#     sett.set("config", config)
#     await throw_float_message(
#         state=state, 
#         message=callback.message, 
#         text=templ.settings_account_float_text(f"✅ Прокси был <b>убран</b>"), 
#         reply_markup=templ.back_kb(calls.SettingsNavigation(to="account").pack())
#     )

@router.callback_query(F.data == "clean_tg_logging_chat_id")
async def callback_clean_tg_logging_chat_id(callback: CallbackQuery, state: FSMContext):
    await state.set_state(None)
    config = sett.get("config")
    config["playerok"]["tg_logging"]["chat_id"] = ""
    sett.set("config", config)
    return await callback_settings_navigation(callback, calls.SettingsNavigation(to="notifications"), state)


@router.callback_query(F.data == "send_new_included_restore_items_keyphrases_file")
async def callback_send_new_included_restore_items_keyphrases_file(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    last_page = data.get("last_page", 0)
    await state.set_state(states.RestoreItemsStates.waiting_for_new_included_restore_items_keyphrases_file)
    await throw_float_message(
        state=state, 
        message=callback.message, 
        text=templ.settings_new_restore_included_float_text(f"📄 Отправьте <b>.txt</b> файл с <b>ключевыми фразами</b>, по одной записи в строке (для каждого товара указываются через запятую, например, \"samp аккаунт, со всеми данными\")"), 
        reply_markup=templ.back_kb(calls.IncludedRestoreItemsPagination(page=last_page).pack())
    )


@router.callback_query(F.data == "send_new_excluded_restore_items_keyphrases_file")
async def callback_send_new_excluded_restore_items_keyphrases_file(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    last_page = data.get("last_page", 0)
    await state.set_state(states.RestoreItemsStates.waiting_for_new_excluded_restore_items_keyphrases_file)
    await throw_float_message(
        state=state, 
        message=callback.message, 
        text=templ.settings_new_restore_excluded_float_text(f"📄 Отправьте <b>.txt</b> файл с <b>ключевыми фразами</b>, по одной записи в строке (для каждого товара указываются через запятую, например, \"samp аккаунт, со всеми данными\")"), 
        reply_markup=templ.back_kb(calls.ExcludedRestoreItemsPagination(page=last_page).pack())
    )


@router.callback_query(F.data == "add_new_custom_command")
async def callback_add_new_custom_command(callback: CallbackQuery, state: FSMContext):
    try:
        await state.set_state(None)
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        custom_commands = sett.get("custom_commands")
        new_custom_command = data.get("new_custom_command")
        new_custom_command_answer = data.get("new_custom_command_answer")
        if not new_custom_command:
            raise Exception("❌ Новая пользовательская команда не была найдена, повторите процесс с самого начала")
        if not new_custom_command_answer:
            raise Exception("❌ Ответ на новую пользовательскую команду не был найден, повторите процесс с самого начала")

        custom_commands[new_custom_command] = new_custom_command_answer.splitlines()
        sett.set("custom_commands", custom_commands)
        last_page = data.get("last_page", 0)
        
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.settings_new_comm_float_text(f"✅ <b>Пользовательская команда</b> <code>{new_custom_command}</code> была добавлена"), 
            reply_markup=templ.back_kb(calls.CustomCommandsPagination(page=last_page).pack())
        )
    except Exception as e:
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.settings_new_comm_float_text(e), 
            reply_markup=templ.back_kb(calls.CustomCommandsPagination(page=last_page).pack())
        )


@router.callback_query(F.data == "confirm_deleting_custom_command")
async def callback_confirm_deleting_custom_command(callback: CallbackQuery, state: FSMContext):
    try:
        await state.set_state(None)
        data = await state.get_data()
        custom_command = data.get("custom_command")
        if not custom_command:
            raise Exception("❌ Пользовательская команда не была найдена, повторите процесс с самого начала")
        
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.settings_comm_page_float_text(f"🗑️ Подтвердите <b>удаление пользовательской команды</b> <code>{custom_command}</code>"), 
            reply_markup=templ.confirm_kb(confirm_cb="delete_custom_command", cancel_cb=calls.CustomCommandPage(command=custom_command).pack())
        )
    except Exception as e:
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.settings_comm_page_float_text(e), 
            reply_markup=templ.back_kb(calls.CustomCommandsPagination(page=last_page).pack())
        )


@router.callback_query(F.data == "delete_custom_command")
async def callback_delete_custom_command(callback: CallbackQuery, state: FSMContext):
    try:
        await state.set_state(None)
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        custom_commands = sett.get("custom_commands")
        custom_command = data.get("custom_command")
        if not custom_command:
            raise Exception("❌ Пользовательская команда не была найдена, повторите процесс с самого начала")
        
        del custom_commands[custom_command]
        sett.set("custom_commands", custom_commands)
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.settings_comm_page_float_text(f"✅ <b>Пользовательская команда</b> <code>{custom_command}</code> была удалена"), 
            reply_markup=templ.back_kb(calls.CustomCommandsPagination(page=last_page).pack())
        )
    except Exception as e:
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.settings_comm_page_float_text(e), 
            reply_markup=templ.back_kb(calls.CustomCommandsPagination(page=last_page).pack())
        )


@router.callback_query(F.data == "add_new_auto_delivery")
async def callback_add_new_auto_delivery(callback: CallbackQuery, state: FSMContext):
    try:
        await state.set_state(None)
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        auto_deliveries = sett.get("auto_deliveries")
        new_auto_delivery_keyphrases = data.get("new_auto_delivery_keyphrases")
        new_auto_delivery_message = data.get("new_auto_delivery_message")
        if not new_auto_delivery_keyphrases:
            raise Exception("❌ Ключевые фразы авто-выдачи не были найдены, повторите процесс с самого начала")
        if not new_auto_delivery_message:
            raise Exception("❌ Сообщение авто-выдачи не было найдено, повторите процесс с самого начала")
        
        auto_deliveries.append({"keyphrases": new_auto_delivery_keyphrases, "message": new_auto_delivery_message.splitlines()})
        sett.set("auto_deliveries", auto_deliveries)
        
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.settings_new_deliv_float_text(f"✅ <b>Авто-выдача</b> была добавлена"), 
            reply_markup=templ.back_kb(calls.AutoDeliveriesPagination(page=last_page).pack())
        )
    except Exception as e:
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.settings_new_deliv_float_text(e), 
            reply_markup=templ.back_kb(calls.AutoDeliveriesPagination(page=last_page).pack())
        )



@router.callback_query(F.data == "confirm_deleting_auto_delivery")
async def callback_confirm_deleting_auto_delivery(callback: CallbackQuery, state: FSMContext):
    try:
        await state.set_state(None)
        data = await state.get_data()
        auto_delivery_index = data.get("auto_delivery_index")
        if auto_delivery_index is None:
            raise Exception("❌ Авто-выдача не была найдена, повторите процесс с самого начала")
        

        auto_deliveries = sett.get("auto_deliveries")
        auto_delivery_keyphrases = "</code>, <code>".join(auto_deliveries[auto_delivery_index]["keyphrases"]) or "❌ Не задано"
       
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.settings_deliv_page_float_text(f"🗑️ Подтвердите <b>удаление пользовательской авто-выдачи</b> для ключевых фраз <code>{auto_delivery_keyphrases}</code>"), 
            reply_markup=templ.confirm_kb(confirm_cb="delete_auto_delivery", cancel_cb=calls.AutoDeliveryPage(index=auto_delivery_index).pack())
        )
    except Exception as e:
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.settings_deliv_page_float_text(e), 
            reply_markup=templ.back_kb(calls.AutoDeliveriesPagination(page=last_page).pack())
        )


@router.callback_query(F.data == "delete_auto_delivery")
async def callback_delete_auto_delivery(callback: CallbackQuery, state: FSMContext):
    try:
        await state.set_state(None)
        data = await state.get_data()
        auto_delivery_index = data.get("auto_delivery_index")
        if auto_delivery_index is None:
            raise Exception("❌ Авто-выдача не была найдена, повторите процесс с самого начала")
        
        auto_deliveries = sett.get("auto_deliveries")
        del auto_deliveries[auto_delivery_index]
        sett.set("auto_deliveries", auto_deliveries)
        last_page = data.get("last_page", 0)
        
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.settings_deliv_page_float_text(f"✅ <b>Авто-выдача</b> была удалена"), 
            reply_markup=templ.back_kb(calls.AutoDeliveriesPagination(page=last_page).pack())
        )
    except Exception as e:
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.settings_deliv_page_float_text(e), 
            reply_markup=templ.back_kb(calls.AutoDeliveriesPagination(page=last_page).pack())
        )



@router.callback_query(F.data == "reload_plugin")
async def callback_reload_plugin(callback: CallbackQuery, state: FSMContext):
    from core.plugins import reload_plugin
    try:
        await state.set_state(None)
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        plugin_uuid = data.get("plugin_uuid")
        if not plugin_uuid:
            raise Exception("❌ UUID плагина не был найден, повторите процесс с самого начала")
        
        await reload_plugin(plugin_uuid)
        return await callback_plugin_page(callback, calls.PluginPage(uuid=plugin_uuid), state)
    except Exception as e:
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.plugin_page_float_text(e), 
            reply_markup=templ.back_kb(calls.PluginsPagination(page=last_page).pack())
        )



@router.callback_query(calls.DeleteIncludedRaiseItem.filter())
async def callback_delete_included_raise_item(callback: CallbackQuery, callback_data: calls.DeleteIncludedRaiseItem, state: FSMContext):
    try:
        await state.set_state(None)
        index = callback_data.index
        if index is None:
            raise Exception("❌ Включенный товар не был найден, повторите процесс с самого начала")
        
        auto_raise_items = sett.get("auto_raise_items")
        auto_raise_items["included"].pop(index)
        sett.set("auto_raise_items", auto_raise_items)

        data = await state.get_data()
        last_page = data.get("last_page", 0)
        return await callback_included_raise_items_pagination(callback, calls.IncludedRaiseItemsPagination(page=last_page), state)
    except Exception as e:
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.settings_raise_included_float_text(e), 
            reply_markup=templ.back_kb(calls.IncludedRaiseItemsPagination(page=last_page).pack())
        )


@router.callback_query(calls.DeleteExcludedRaiseItem.filter())
async def callback_delete_excluded_raise_item(callback: CallbackQuery, callback_data: calls.DeleteExcludedRaiseItem, state: FSMContext):
    try:
        await state.set_state(None)
        index = callback_data.index
        if index is None:
            raise Exception("❌ Исключенный товар не был найден, повторите процесс с самого начала")
        
        auto_raise_items = sett.get("auto_raise_items")
        auto_raise_items["excluded"].pop(index)
        sett.set("auto_raise_items", auto_raise_items)

        data = await state.get_data()
        last_page = data.get("last_page", 0)
        return await callback_excluded_raise_items_pagination(callback, calls.ExcludedRaiseItemsPagination(page=last_page), state)
    except Exception as e:
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.settings_raise_excluded_float_text(e), 
            reply_markup=templ.back_kb(calls.ExcludedRaiseItemsPagination(page=last_page).pack())
        )


@router.callback_query(F.data == "send_new_included_raise_items_keyphrases_file")
async def callback_send_new_included_raise_items_keyphrases_file(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    last_page = data.get("last_page", 0)
    await state.set_state(states.RaiseItemsStates.waiting_for_new_included_raise_items_keyphrases_file)
    await throw_float_message(
        state=state, 
        message=callback.message, 
        text=templ.settings_new_raise_included_float_text(f"📄 Отправьте <b>.txt</b> файл с <b>ключевыми фразами</b>, по одной записи в строке (для каждого товара указываются через запятую, например, \"samp аккаунт, со всеми данными\")"), 
        reply_markup=templ.back_kb(calls.IncludedRaiseItemsPagination(page=last_page).pack())
    )


@router.callback_query(F.data == "send_new_excluded_raise_items_keyphrases_file")
async def callback_send_new_excluded_raise_items_keyphrases_file(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    last_page = data.get("last_page", 0)
    await state.set_state(states.RaiseItemsStates.waiting_for_new_excluded_raise_items_keyphrases_file)
    await throw_float_message(
        state=state, 
        message=callback.message, 
        text=templ.settings_new_raise_excluded_float_text(f"📄 Отправьте <b>.txt</b> файл с <b>ключевыми фразами</b>, по одной записи в строке (для каждого товара указываются через запятую, например, \"samp аккаунт, со всеми данными\")"), 
        reply_markup=templ.back_kb(calls.ExcludedRaiseItemsPagination(page=last_page).pack())
    )



@router.callback_query(F.data == "add_included_raise_item")
async def callback_add_included_raise_item(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    last_page = data.get("last_page", 0)
    await state.set_state(states.RaiseItemsStates.waiting_for_new_included_raise_item_keyphrases)
    await throw_float_message(
        state=state, 
        message=callback.message, 
        text=templ.settings_new_raise_included_float_text(f"✏️ Введите <b>ключевые фразы</b> для товара через запятую (например, \"samp аккаунт, со всеми данными\") ↓"), 
        reply_markup=templ.back_kb(calls.IncludedRaiseItemsPagination(page=last_page).pack())
    )


@router.callback_query(F.data == "add_included_raise_items_from_file")
async def callback_add_included_raise_items_from_file(callback: CallbackQuery, state: FSMContext):
    return await callback_send_new_included_raise_items_keyphrases_file(callback, state)


@router.callback_query(F.data == "add_excluded_raise_item")
async def callback_add_excluded_raise_item(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    last_page = data.get("last_page", 0)
    await state.set_state(states.RaiseItemsStates.waiting_for_new_excluded_raise_item_keyphrases)
    await throw_float_message(
        state=state, 
        message=callback.message, 
        text=templ.settings_new_raise_excluded_float_text(f"✏️ Введите <b>ключевые фразы</b> для товара через запятую (например, \"samp аккаунт, со всеми данными\") ↓"), 
        reply_markup=templ.back_kb(calls.ExcludedRaiseItemsPagination(page=last_page).pack())
    )


@router.callback_query(F.data == "add_excluded_raise_items_from_file")
async def callback_add_excluded_raise_items_from_file(callback: CallbackQuery, state: FSMContext):
    return await callback_send_new_excluded_raise_items_keyphrases_file(callback, state)
