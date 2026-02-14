from aiogram import Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext

from .. import templates as templ
from .. import callback_datas as calls
from ..helpful import throw_float_message

router = Router()

@router.callback_query(calls.MenuNavigation.filter())
async def callback_menu_navigation(callback: CallbackQuery, callback_data: calls.MenuNavigation, state: FSMContext):
    try:
        await state.set_state(None)
        to = callback_data.to
        
        if to in ["default", "main"]:
            await throw_float_message(
                state=state,
                message=callback.message,
                text=templ.menu_text(),
                reply_markup=templ.menu_kb(page=0),
                callback=callback
            )
        else:
            await callback.answer("❌ Неизвестный раздел меню.", show_alert=True)
            
    except Exception as e:
        await callback.answer("❌ Произошла ошибка при загрузке меню.", show_alert=True)

@router.callback_query(calls.MenuPagination.filter())
async def callback_menu_pagination(callback: CallbackQuery, callback_data: calls.MenuPagination, state: FSMContext):
    try:
        await state.set_state(None)
        page = callback_data.page
        
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.menu_text(),
            reply_markup=templ.menu_kb(page=page),
            callback=callback
        )
    except Exception as e:
        await callback.answer("❌ Произошла ошибка при переключении страницы.", show_alert=True)

@router.callback_query(calls.InstructionNavigation.filter())
async def callback_instruction_navigation(callback: CallbackQuery, callback_data: calls.InstructionNavigation, state: FSMContext):
    try:
        await state.set_state(None)
        to = callback_data.to
        
        if to in ["default", "main"]:
            await throw_float_message(
                state=state,
                message=callback.message,
                text=templ.instruction_text(),
                reply_markup=templ.instruction_kb(),
                callback=callback
            )
        elif to == "commands":
            await throw_float_message(
                state=state,
                message=callback.message,
                text=templ.instruction_comms_text(),
                reply_markup=templ.instruction_comms_kb(),
                callback=callback
            )
        else:
            await callback.answer("❌ Неизвестный раздел инструкций.", show_alert=True)
            
    except Exception as e:
        await callback.answer("❌ Произошла ошибка при загрузке инструкций.", show_alert=True)

@router.callback_query(calls.SettingsNavigation.filter())
async def callback_settings_navigation(callback: CallbackQuery, callback_data: calls.SettingsNavigation, state: FSMContext):
    try:
        await state.set_state(None)
        to = callback_data.to
        
        # Сохраняем текущее меню в state для правильного возврата после переключения
        await state.update_data(from_menu=to)
        
        if to in ["default", "main"]:
            await throw_float_message(
                state=state,
                message=callback.message,
                text=templ.settings_text(),
                reply_markup=templ.settings_kb(),
                callback=callback
            )
        elif to == "raise":
            try:
                text = templ.settings_raise_text()
                kb = templ.settings_raise_kb()
                await throw_float_message(
                    state=state,
                    message=callback.message,
                    text=text,
                    reply_markup=kb,
                    callback=callback
                )
            except Exception as e:
                import traceback
                from logging import getLogger
                getLogger("tgbot").error(f"Ошибка при загрузке настроек автоподнятия: {e}", exc_info=True)
                await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)
        else:
            text_func = getattr(templ, f'settings_{to}_text', None)
            kb_func = getattr(templ, f'settings_{to}_kb', None)
            
            if text_func and kb_func:
                try:
                    text = text_func()
                    kb = kb_func()
                    
                    if not isinstance(text, str):
                        text = ""
                        
                    if not isinstance(kb, InlineKeyboardMarkup):
                        kb = None
                    
                    await throw_float_message(
                        state=state,
                        message=callback.message,
                        text=text,
                        reply_markup=kb,
                        callback=callback
                    )
                    
                except Exception as e:
                    await callback.answer("❌ Ошибка при загрузке раздела настроек.", show_alert=True)
            else:
                await callback.answer("❌ Этот раздел настроек временно недоступен.", show_alert=True)
                
    except Exception as e:
        await callback.answer("❌ Произошла критическая ошибка при загрузке настроек.", show_alert=True)


@router.callback_query(calls.ProfileNavigation.filter())
async def callback_profile_navigation(callback: CallbackQuery, callback_data: calls.ProfileNavigation, state: FSMContext):
    try:
        await state.set_state(None)
        to = callback_data.to
        
        if to in ["default", "main"]:
            await throw_float_message(
                state=state,
                message=callback.message,
                text=templ.profile_text(),
                reply_markup=templ.profile_kb(),
                callback=callback
            )
        else:
            await callback.answer("❌ Неизвестный раздел профиля.", show_alert=True)
            
    except Exception as e:
        await callback.answer("❌ Произошла ошибка при загрузке профиля.", show_alert=True)


@router.callback_query(calls.StatsNavigation.filter())
async def callback_stats_navigation(callback: CallbackQuery, callback_data: calls.StatsNavigation, state: FSMContext):
    try:
        await state.set_state(None)
        to = callback_data.to
        
        if to in ["default", "main"]:
            await throw_float_message(
                state=state,
                message=callback.message,
                text=templ.stats_text(),
                reply_markup=templ.stats_kb(),
                callback=callback
            )
        else:
            await callback.answer("❌ Неизвестный раздел статистики.", show_alert=True)
            
    except Exception as e:
        await callback.answer("❌ Произошла ошибка при загрузке статистики.", show_alert=True)


@router.callback_query(calls.MessagesNavigation.filter())
async def callback_messages_navigation(callback: CallbackQuery, callback_data: calls.MessagesNavigation, state: FSMContext):
    try:
        await state.set_state(None)
        to = callback_data.to
        
        if to in ["default", "main"]:
            await throw_float_message(
                state=state,
                message=callback.message,
                text=templ.messages_text(),
                reply_markup=templ.messages_kb(),
                callback=callback
            )
        elif to == "greeting":
            await throw_float_message(
                state=state,
                message=callback.message,
                text=templ.messages_greeting_text(),
                reply_markup=templ.messages_greeting_kb(),
                callback=callback
            )
        elif to == "confirmation_seller":
            await throw_float_message(
                state=state,
                message=callback.message,
                text=templ.messages_confirmation_seller_text(),
                reply_markup=templ.messages_confirmation_seller_kb(),
                callback=callback
            )
        elif to == "confirmation_buyer":
            await throw_float_message(
                state=state,
                message=callback.message,
                text=templ.messages_confirmation_buyer_text(),
                reply_markup=templ.messages_confirmation_buyer_kb(),
                callback=callback
            )
        elif to == "review":
            await throw_float_message(
                state=state,
                message=callback.message,
                text=templ.messages_review_text(),
                reply_markup=templ.messages_review_kb(),
                callback=callback
            )
        else:
            await callback.answer("❌ Неизвестный раздел автоответов.", show_alert=True)
            
    except Exception as e:
        await callback.answer("❌ Произошла ошибка при загрузке раздела автоответов.", show_alert=True)


@router.callback_query(calls.LogsNavigation.filter())
async def callback_logs_navigation(callback: CallbackQuery, callback_data: calls.LogsNavigation, state: FSMContext):
    try:
        await state.set_state(None)
        to = callback_data.to
        
        if to in ["default", "main"]:
            await throw_float_message(
                state=state,
                message=callback.message,
                text=templ.logs_text(),
                reply_markup=templ.logs_kb(),
                callback=callback
            )
        else:
            await callback.answer("❌ Неизвестный раздел логов.", show_alert=True)
            
    except Exception as e:
        await callback.answer("❌ Произошла ошибка при загрузке логов.", show_alert=True)


@router.callback_query(calls.ReviewMonitorNavigation.filter())
async def callback_review_monitor_navigation(callback: CallbackQuery, callback_data: calls.ReviewMonitorNavigation, state: FSMContext):
    try:
        await state.set_state(None)
        to = callback_data.to
        
        if to in ["default", "main"]:
            await throw_float_message(
                state=state,
                message=callback.message,
                text=templ.review_monitor_text(),
                reply_markup=templ.review_monitor_kb(),
                callback=callback
            )
        else:
            await callback.answer("❌ Неизвестный раздел мониторинга отзывов.", show_alert=True)
            
    except Exception as e:
        await callback.answer("❌ Произошла ошибка при загрузке мониторинга отзывов.", show_alert=True)