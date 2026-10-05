from __future__ import annotations

import asyncio
import logging

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .. import callback_datas as calls
from .. import templates as templ
from ..helpful import get_playerok_bot, throw_float_message


router = Router()
logger = logging.getLogger("seal.telegram.reviews")


def _load_reviews(account):
    profile = account.get_user(id=account.id)
    # comment_required=None: иначе API отфильтрует отзывы по hasComment=false.
    return profile.get_reviews(count=templ.REVIEWS_SHOW_COUNT, comment_required=None)


async def show_reviews(message: Message, state: FSMContext, callback: CallbackQuery | None = None):
    await state.set_state(None)
    plbot = get_playerok_bot()
    account = (getattr(plbot, "account", None) or getattr(plbot, "playerok_account", None)) if plbot else None
    if account is None:
        text = templ.do_action_text("❌ Нет подключения к Playerok")
        reply_markup = None
    else:
        try:
            review_list = await asyncio.to_thread(_load_reviews, account)
            text = templ.reviews_text(
                reviews=list(getattr(review_list, "reviews", None) or []),
                total_count=getattr(review_list, "total_count", None),
            )
        except Exception as e:
            logger.warning("Не удалось загрузить отзывы: %s", e)
            text = templ.do_action_text(f"❌ Не удалось загрузить отзывы: {e}")
        reply_markup = templ.reviews_kb()

    await throw_float_message(
        state=state,
        message=message,
        text=text,
        reply_markup=reply_markup,
        callback=callback,
        send=callback is None,
    )


@router.callback_query(calls.ReviewsAction.filter())
async def callback_reviews_action(callback: CallbackQuery, callback_data: calls.ReviewsAction, state: FSMContext):
    if callback_data.action == "refresh":
        await show_reviews(callback.message, state, callback=callback)
        return
    await callback.answer()
