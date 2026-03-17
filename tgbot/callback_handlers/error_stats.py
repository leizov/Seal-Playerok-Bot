import logging

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from .. import callback_datas as calls
from .. import templates as templ
from ..helpful import throw_float_message


router = Router()
logger = logging.getLogger("tgbot")


async def _render_error_stats_page(
    *,
    callback: CallbackQuery,
    state: FSMContext,
    text: str,
    reply_markup,
    log_context: str,
) -> None:
    try:
        await throw_float_message(
            state=state,
            message=callback.message,
            text=text,
            reply_markup=reply_markup,
            callback=callback,
        )
        return
    except Exception:
        logger.error("[ErrorStats] throw_float_message failed (%s)", log_context, exc_info=True)

    message = callback.message
    if message is None:
        await callback.answer("❌ Ошибка при загрузке статистики ошибок.", show_alert=True)
        return

    try:
        await message.edit_text(text=text, reply_markup=reply_markup, parse_mode="HTML")
        await callback.answer(cache_time=0)
        return
    except Exception:
        logger.error("[ErrorStats] direct edit failed (%s)", log_context, exc_info=True)

    try:
        await message.answer(text=text, reply_markup=reply_markup, parse_mode="HTML")
        await callback.answer(cache_time=0)
        return
    except Exception:
        logger.error("[ErrorStats] direct send failed (%s)", log_context, exc_info=True)

    await callback.answer("❌ Ошибка при загрузке статистики ошибок.", show_alert=True)


@router.callback_query(calls.ErrorStatsNavigation.filter())
async def callback_error_stats_navigation(callback: CallbackQuery, callback_data: calls.ErrorStatsNavigation, state: FSMContext):
    try:
        await state.set_state(None)
        if callback_data.to not in ("default", "main"):
            await callback.answer("❌ Неизвестный раздел статистики ошибок.", show_alert=True)
            return

        text = templ.error_stats_text()
        kb = templ.error_stats_kb()
        await _render_error_stats_page(
            callback=callback,
            state=state,
            text=text,
            reply_markup=kb,
            log_context=f"navigation:{callback_data.to}",
        )
    except Exception:
        logger.error("[ErrorStats] navigation handler failed", exc_info=True)
        await callback.answer("❌ Ошибка при загрузке статистики ошибок.", show_alert=True)


@router.callback_query(calls.ErrorStatsDay.filter())
async def callback_error_stats_day(callback: CallbackQuery, callback_data: calls.ErrorStatsDay, state: FSMContext):
    try:
        await state.set_state(None)
        day = callback_data.day
        text = templ.error_stats_day_text(day)
        kb = templ.error_stats_day_kb(day)
        await _render_error_stats_page(
            callback=callback,
            state=state,
            text=text,
            reply_markup=kb,
            log_context=f"day:{day}",
        )
    except Exception:
        logger.error("[ErrorStats] day handler failed", exc_info=True)
        await callback.answer("❌ Ошибка при открытии статистики за дату.", show_alert=True)
