from __future__ import annotations

from datetime import datetime, timezone

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .. import callback_datas as calls
from .. import templates as templ
from ..helpful import get_playerok_bot, throw_float_message


router = Router()

MAX_DEALS_TO_LOAD = 70
API_DEALS_PAGE_SIZE = 24
MENU_DEALS_PAGE_SIZE = 10

ALLOWED_STATUSES = {"ALL", "PAID", "SENT", "CONFIRMED", "ROLLED_BACK"}
ALLOWED_SORT_BY = {"TIME", "PRICE"}
ALLOWED_SORT_ORDER = {"ASC", "DESC"}


def _default_filters() -> dict:
    return {
        "status": "ALL",
        "only_problem": False,
        "sort_by": "TIME",
        "sort_order": "DESC",
        "page": 0,
    }


def _normalize_filters(raw_filters: dict | None) -> dict:
    filters = _default_filters()
    if isinstance(raw_filters, dict):
        filters.update(raw_filters)

    status = str(filters.get("status", "ALL")).upper()
    filters["status"] = status if status in ALLOWED_STATUSES else "ALL"

    sort_by = str(filters.get("sort_by", "TIME")).upper()
    filters["sort_by"] = sort_by if sort_by in ALLOWED_SORT_BY else "TIME"

    sort_order = str(filters.get("sort_order", "DESC")).upper()
    filters["sort_order"] = sort_order if sort_order in ALLOWED_SORT_ORDER else "DESC"

    filters["only_problem"] = bool(filters.get("only_problem"))
    try:
        filters["page"] = max(0, int(filters.get("page", 0)))
    except Exception:
        filters["page"] = 0
    return filters


def _enum_name(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, "name"):
        return str(getattr(value, "name"))
    return str(value)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None

    if isinstance(value, datetime):
        dt = value
    else:
        raw = str(value).strip()
        if not raw:
            return None

        candidates = [raw]
        candidates.append(raw.replace("Z", "+00:00"))
        if raw.endswith("[UTC]"):
            trimmed = raw[:-5]
            candidates.append(trimmed)
            candidates.append(trimmed.replace("Z", "+00:00"))

        dt = None
        for candidate in candidates:
            try:
                dt = datetime.fromisoformat(candidate)
                break
            except Exception:
                continue
        if dt is None:
            return None

    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _time_sort_key(deal: dict) -> tuple[int, float]:
    dt = _parse_dt(deal.get("created_at"))
    if dt is not None:
        return 1, dt.timestamp()

    seq = deal.get("_seq", 0)
    try:
        seq = int(seq)
    except Exception:
        seq = 0
    return 0, float(-seq)


def _to_float(value, fallback: float = 0.0) -> float:
    if value is None:
        return fallback
    try:
        return float(value)
    except Exception:
        return fallback


def _deal_to_dict(deal, seq: int = 0) -> dict:
    user = getattr(deal, "user", None)
    item = getattr(deal, "item", None)
    chat = getattr(deal, "chat", None)
    tx = getattr(deal, "transaction", None)

    deal_price = getattr(deal, "price", None)
    if deal_price is None:
        deal_price = getattr(item, "price", None)

    chat_id = getattr(chat, "id", None)
    if chat_id is not None:
        chat_id = str(chat_id)

    return {
        "id": str(getattr(deal, "id", "")),
        "status": _enum_name(getattr(deal, "status", None)),
        "has_problem": bool(getattr(deal, "has_problem", False)),
        "created_at": getattr(deal, "created_at", None),
        "buyer": getattr(user, "username", None),
        "item_name": getattr(item, "name", None),
        "price": deal_price,
        "revenue": getattr(tx, "value", None),
        "chat_id": chat_id,
        "_seq": seq,
    }


def _load_latest_deals(account, max_count: int = MAX_DEALS_TO_LOAD) -> list[dict]:
    loaded_deals: list[dict] = []
    after_cursor = None

    while len(loaded_deals) < max_count:
        request_count = min(API_DEALS_PAGE_SIZE, max_count - len(loaded_deals))
        deals_page = account.get_deals(count=request_count, after_cursor=after_cursor)
        current_deals = list(getattr(deals_page, "deals", []) or [])
        if not current_deals:
            break

        for deal in current_deals:
            if getattr(deal, "id", None) is None:
                continue
            loaded_deals.append(_deal_to_dict(deal, seq=len(loaded_deals)))

        page_info = getattr(deals_page, "page_info", None)
        has_next_page = bool(getattr(page_info, "has_next_page", False)) if page_info else False
        after_cursor = getattr(page_info, "end_cursor", None) if page_info else None
        if not has_next_page or not after_cursor:
            break

    return loaded_deals[:max_count]


def _apply_filters(all_deals: list[dict], filters: dict) -> list[dict]:
    filtered = list(all_deals)

    # Backward compatibility with already cached data in FSM:
    # older cache entries may not contain "_seq".
    for idx, deal in enumerate(filtered):
        if isinstance(deal, dict) and "_seq" not in deal:
            deal["_seq"] = idx

    status = filters.get("status", "ALL")
    if status != "ALL":
        filtered = [deal for deal in filtered if str(deal.get("status")) == status]

    if filters.get("only_problem"):
        filtered = [deal for deal in filtered if deal.get("has_problem")]

    sort_by = filters.get("sort_by", "TIME")
    reverse = filters.get("sort_order", "DESC") == "DESC"

    if sort_by == "PRICE":
        filtered.sort(key=lambda d: _to_float(d.get("price"), fallback=-1.0), reverse=reverse)
    else:
        filtered.sort(key=_time_sort_key, reverse=reverse)

    return filtered


def _slice_page(filtered_deals: list[dict], page: int) -> tuple[list[dict], int, int]:
    total_found = len(filtered_deals)
    total_pages = max(1, (total_found + MENU_DEALS_PAGE_SIZE - 1) // MENU_DEALS_PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))

    start_ix = page * MENU_DEALS_PAGE_SIZE
    end_ix = start_ix + MENU_DEALS_PAGE_SIZE
    return filtered_deals[start_ix:end_ix], page, total_pages


async def show_deals_menu(
    message: Message,
    state: FSMContext,
    callback: CallbackQuery | None = None,
    reset: bool = False,
    force_reload: bool = False,
):
    await state.set_state(None)

    playerok_bot = get_playerok_bot()
    account = None
    if playerok_bot is not None:
        account = getattr(playerok_bot, "account", None) or getattr(playerok_bot, "playerok_account", None)

    data = await state.get_data()
    filters = _default_filters() if reset else _normalize_filters(data.get("deals_filters"))

    cached_deals = data.get("deals_cached")
    if force_reload or not isinstance(cached_deals, list):
        if account is None:
            await throw_float_message(
                state=state,
                message=message,
                text=templ.do_action_text("❌ Нет подключения к Playerok"),
                reply_markup=templ.back_kb(calls.DealsAction(action="open").pack()),
                callback=callback,
            )
            return

        try:
            cached_deals = _load_latest_deals(account, max_count=MAX_DEALS_TO_LOAD)
        except Exception as e:
            await throw_float_message(
                state=state,
                message=message,
                text=templ.do_action_text(f"❌ Не удалось загрузить сделки: {e}"),
                reply_markup=templ.back_kb(calls.DealsAction(action="open").pack()),
                callback=callback,
            )
            return

        await state.update_data(deals_cached=cached_deals)
    else:
        cached_deals = [deal for deal in cached_deals if isinstance(deal, dict)]

    filtered_deals = _apply_filters(cached_deals, filters)
    page_deals, page, total_pages = _slice_page(filtered_deals, filters.get("page", 0))
    filters["page"] = page

    await state.update_data(
        deals_filters=filters,
        deals_cached=cached_deals,
        deals_total_loaded=len(cached_deals),
    )

    text = templ.deals_search_text(
        filters=filters,
        page_deals=page_deals,
        page=page,
        total_pages=total_pages,
        total_found=len(filtered_deals),
        total_loaded=len(cached_deals),
    )
    kb = templ.deals_search_kb(filters, page_deals, page, total_pages)

    await throw_float_message(
        state=state,
        message=message,
        text=text,
        reply_markup=kb,
        callback=callback,
    )


@router.callback_query(calls.DealsAction.filter())
async def callback_deals_actions(
    callback: CallbackQuery,
    callback_data: calls.DealsAction,
    state: FSMContext,
):
    action = callback_data.action
    value = callback_data.value

    if action == "noop":
        await callback.answer()
        return

    data = await state.get_data()
    filters = _normalize_filters(data.get("deals_filters"))
    reset = False
    force_reload = False

    if action == "open":
        pass
    elif action == "page":
        try:
            filters["page"] = max(0, int(value or 0))
        except Exception:
            filters["page"] = 0
    elif action == "status":
        status = str(value or "").upper()
        if status in ALLOWED_STATUSES:
            filters["status"] = status
            filters["page"] = 0
    elif action == "problem":
        filters["only_problem"] = not bool(filters.get("only_problem"))
        filters["page"] = 0
    elif action == "sort_by":
        sort_by = str(value or "").upper()
        if sort_by in ALLOWED_SORT_BY:
            filters["sort_by"] = sort_by
            filters["page"] = 0
    elif action == "sort_toggle":
        filters["sort_order"] = "DESC" if filters.get("sort_order", "DESC") == "ASC" else "ASC"
        filters["page"] = 0
    elif action == "sort_order":
        # Legacy callbacks from old messages with two order buttons.
        sort_order = str(value or "").upper()
        if sort_order in ALLOWED_SORT_ORDER:
            filters["sort_order"] = sort_order
            filters["page"] = 0
    elif action == "reset":
        reset = True
    elif action == "refresh":
        force_reload = True
    elif action in {"time", "time_custom", "price", "price_custom"}:
        # Legacy callbacks from old messages.
        pass
    else:
        await callback.answer("Неизвестное действие", show_alert=False)
        return

    if reset:
        await state.update_data(deals_filters=_default_filters())
    else:
        await state.update_data(deals_filters=filters)

    await show_deals_menu(
        message=callback.message,
        state=state,
        callback=callback,
        reset=reset,
        force_reload=force_reload,
    )
