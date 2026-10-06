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

API_REVIEWS_PAGE_SIZE = 24  # лимит Playerok на один запрос


def _get_account():
    plbot = get_playerok_bot()
    if not plbot:
        return None
    return getattr(plbot, "account", None) or getattr(plbot, "playerok_account", None)


def _load_reviews(account, max_count: int = templ.MAX_REVIEWS_TO_LOAD) -> tuple[list[dict], int | None]:
    """Загружает последние отзывы постранично (по курсору). Возвращает (отзывы, totalCount)."""
    profile = account.get_user(id=account.id)
    loaded: list[dict] = []
    seen: set[str] = set()
    total_count = None
    after_cursor = None

    while len(loaded) < max_count:
        count = min(API_REVIEWS_PAGE_SIZE, max_count - len(loaded))
        # comment_required=None: иначе API отфильтрует отзывы по hasComment=false.
        page = profile.get_reviews(count=count, comment_required=None, after_cursor=after_cursor)
        if page is None:
            break
        if page.total_count is not None:
            total_count = page.total_count
        for review in page.reviews or []:
            if review is None:
                continue
            data = templ.review_to_dict(review)
            if not data["id"] or data["id"] in seen:
                continue
            seen.add(data["id"])
            loaded.append(data)

        info = page.page_info
        after_cursor = getattr(info, "end_cursor", None) if info else None
        if not page.reviews or not info or not info.has_next_page or not after_cursor:
            break

    return loaded[:max_count], total_count


def _slice_page(reviews: list[dict], page: int) -> tuple[list[dict], int, int]:
    size = templ.REVIEWS_PAGE_SIZE
    total_pages = max(1, (len(reviews) + size - 1) // size)
    page = max(0, min(page, total_pages - 1))
    return reviews[page * size:(page + 1) * size], page, total_pages


async def show_reviews(
    message: Message,
    state: FSMContext,
    callback: CallbackQuery | None = None,
    force_reload: bool = True,
    page: int | None = None,
):
    await state.set_state(None)
    data = await state.get_data()
    cached = data.get("reviews_cached")
    total_count = data.get("reviews_total_count")
    if page is None:
        page = int(data.get("reviews_page") or 0) if not force_reload else 0

    if force_reload or not isinstance(cached, list):
        loading_text = "⏳ Загрузка отзывов..."
        if callback is not None:
            await throw_float_message(state=state, message=message, text=loading_text, callback=callback)
            callback = None
        else:
            message = await throw_float_message(state=state, message=message, text=loading_text, send=True) or message

        account = _get_account()
        if account is None:
            await throw_float_message(
                state=state,
                message=message,
                text=templ.do_action_text("❌ Нет подключения к Playerok"),
                reply_markup=templ.back_kb(calls.ProfileNavigation(to="main").pack()),
            )
            return
        try:
            cached, total_count = await asyncio.to_thread(_load_reviews, account)
        except Exception as e:
            logger.warning("Не удалось загрузить отзывы: %s", e)
            await throw_float_message(
                state=state,
                message=message,
                text=templ.do_action_text(f"❌ Не удалось загрузить отзывы: {e}"),
                reply_markup=templ.reviews_list_kb([], 0, 1),
            )
            return

    cached = [r for r in cached if isinstance(r, dict)]
    page_reviews, page, total_pages = _slice_page(cached, page)
    await state.update_data(reviews_cached=cached, reviews_total_count=total_count, reviews_page=page)

    await throw_float_message(
        state=state,
        message=message,
        text=templ.reviews_list_text(page_reviews, page, total_pages, len(cached), total_count),
        reply_markup=templ.reviews_list_kb(page_reviews, page, total_pages),
        callback=callback,
    )


async def _find_cached_review(state: FSMContext, rv_id: str) -> dict | None:
    data = await state.get_data()
    for review in data.get("reviews_cached") or []:
        if isinstance(review, dict) and str(review.get("id")) == str(rv_id):
            return review
    return None


@router.callback_query(calls.ReviewsAction.filter())
async def callback_reviews_action(callback: CallbackQuery, callback_data: calls.ReviewsAction, state: FSMContext):
    action = callback_data.action
    if action == "refresh":
        await show_reviews(callback.message, state, callback=callback, force_reload=True)
    elif action == "open":
        await show_reviews(callback.message, state, callback=callback, force_reload=False)
    else:
        await callback.answer()


@router.callback_query(calls.ReviewsPage.filter())
async def callback_reviews_page(callback: CallbackQuery, callback_data: calls.ReviewsPage, state: FSMContext):
    await show_reviews(callback.message, state, callback=callback, force_reload=False, page=callback_data.page)


@router.callback_query(calls.ReviewView.filter())
async def callback_review_view(callback: CallbackQuery, callback_data: calls.ReviewView, state: FSMContext):
    await state.set_state(None)
    review = await _find_cached_review(state, callback_data.rv_id)
    if review is None:
        await callback.answer("Список отзывов устарел — обновляю", show_alert=False)
        await show_reviews(callback.message, state, force_reload=True)
        return
    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.review_card_text(review),
        reply_markup=templ.review_card_kb(review),
        callback=callback,
    )


@router.callback_query(calls.ReviewDeal.filter())
async def callback_review_deal(callback: CallbackQuery, callback_data: calls.ReviewDeal, state: FSMContext):
    review = await _find_cached_review(state, callback_data.rv_id)
    deal_id = (review or {}).get("deal_id")
    if not deal_id:
        await callback.answer("❌ Сделка для отзыва не найдена", show_alert=True)
        return
    from .actions_other import _render_deal_view

    await _render_deal_view(
        callback=callback,
        state=state,
        deal_id=deal_id,
        back_cb=calls.ReviewView(rv_id=callback_data.rv_id).pack(),
    )


def _resolve_chat_id(account, review: dict) -> str | None:
    deal_id = review.get("deal_id")
    if deal_id:
        try:
            deal = account.get_deal(deal_id)
            chat_id = getattr(getattr(deal, "chat", None), "id", None)
            if chat_id:
                return str(chat_id)
        except Exception as e:
            logger.debug("Не удалось получить чат из сделки %s: %s", deal_id, e)
    buyer = review.get("buyer")
    if buyer:
        chat = account.get_chat_by_username(buyer)
        if chat is not None and getattr(chat, "id", None):
            return str(chat.id)
    return None


@router.callback_query(calls.ReviewChat.filter())
async def callback_review_chat(callback: CallbackQuery, callback_data: calls.ReviewChat, state: FSMContext):
    review = await _find_cached_review(state, callback_data.rv_id)
    account = _get_account()
    if review is None:
        await callback.answer("Список отзывов устарел — откройте его заново", show_alert=True)
        return
    if account is None:
        await callback.answer("❌ Нет подключения к Playerok", show_alert=True)
        return
    try:
        chat_id = await asyncio.to_thread(_resolve_chat_id, account, review)
    except Exception as e:
        await callback.answer(f"❌ Не удалось найти чат: {e}", show_alert=True)
        return
    if not chat_id:
        await callback.answer("❌ Чат с покупателем не найден", show_alert=True)
        return

    from .chat_history import callback_show_chat_history

    await callback_show_chat_history(callback, calls.ChatHistory(chat_id=chat_id), state)
