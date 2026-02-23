"""Обработчики для управления мониторингом отзывов"""

from aiogram import Router
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from settings import Settings as sett
from .. import templates as templ
from .. import callback_datas as calls
from ..helpful import throw_float_message
from ..states.all import ReviewMonitorStates

router = Router()


@router.callback_query(calls.ReviewMonitorToggle.filter())
async def callback_review_monitor_toggle(callback: CallbackQuery, state: FSMContext):
    """Переключение включения/выключения мониторинга отзывов"""
    try:
        config = sett.get("config")
        review_config = config.get("playerok", {}).get("review_monitoring", {})
        
        # Переключаем состояние
        current_state = review_config.get("enabled", False)
        review_config["enabled"] = not current_state
        
        config["playerok"]["review_monitoring"] = review_config
        sett.set("config", config)
        
        status = "включен" if review_config["enabled"] else "выключен"
        await callback.answer(f"✅ Мониторинг отзывов {status}", show_alert=False)
        
        # Обновляем меню
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.review_monitor_text(),
            reply_markup=templ.review_monitor_kb(),
            callback=callback
        )
        
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(calls.ReviewMonitorAction.filter())
async def callback_review_monitor_action(callback: CallbackQuery, callback_data: calls.ReviewMonitorAction, state: FSMContext):
    """Обработка действий с мониторингом отзывов"""
    try:
        action = callback_data.action
        
        if action == "set_interval":
            # Запрашиваем ввод интервала в минутах
            await state.set_state(ReviewMonitorStates.waiting_for_days)
            await callback.message.answer(
                "⏱️ <b>Изменение времени ожидания отзыва</b>\n\n"
                "Введите число минут, в течение которых бот будет ожидать отзыв после подтверждения сделки.\n\n"
                "<i>Например: 10</i>",
                parse_mode="HTML"
            )
            await callback.answer()
        else:
            await callback.answer("❌ Неизвестное действие", show_alert=True)
            
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)
