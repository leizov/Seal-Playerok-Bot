from __future__ import annotations

import logging

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from playerokapi.enums import ItemStatuses, PriorityTypes

from .. import callback_datas as calls
from .. import states
from .. import templates as templ
from ..helpful import get_playerok_bot, throw_float_message
from ..utils.item_formatter import format_item_card_payload


router = Router()
logger = logging.getLogger("seal.telegram.items")

MAX_ITEMS_TO_LOAD = 70
API_ITEMS_PAGE_SIZE = 24
MENU_ITEMS_PAGE_SIZE = 10

ALLOWED_STATUS_PRESETS = {
    "PREMIUM",
    "APPROVED",
    "MODERATION",
    "SOLD",
    "BLOCKED_DECLINED",
    "DRAFT",
}
ALLOWED_SORT_ORDER = {"ASC", "DESC"}
ALLOWED_UI_SCREENS = {"list", "filter"}


def _get_playerok_account():
    playerok_bot = get_playerok_bot()
    if playerok_bot is None:
        return None
    return getattr(playerok_bot, "account", None) or getattr(playerok_bot, "playerok_account", None)


def _default_filters() -> dict:
    return {
        "status_presets": [],
        "sort_order": "DESC",
        "name_query": "",
    }


def _copy_filters(filters: dict) -> dict:
    normalized = _normalize_filters(filters)
    return {
        "status_presets": list(normalized.get("status_presets") or []),
        "sort_order": normalized.get("sort_order", "DESC"),
        "name_query": normalized.get("name_query", ""),
    }


def _default_ui_state() -> dict:
    return {
        "screen": "list",
        "page": 0,
    }


def _normalize_filters(raw_filters: dict | None) -> dict:
    filters = _default_filters()
    if isinstance(raw_filters, dict):
        filters.update(raw_filters)

    presets = []
    for preset in filters.get("status_presets", []):
        preset_name = str(preset or "").upper().strip()
        if preset_name in ALLOWED_STATUS_PRESETS and preset_name not in presets:
            presets.append(preset_name)
    filters["status_presets"] = presets

    sort_order = str(filters.get("sort_order", "DESC")).upper()
    filters["sort_order"] = sort_order if sort_order in ALLOWED_SORT_ORDER else "DESC"
    filters["name_query"] = str(filters.get("name_query") or "").strip()
    return filters


def _normalize_ui_state(raw_ui_state: dict | None) -> dict:
    ui_state = _default_ui_state()
    if isinstance(raw_ui_state, dict):
        ui_state.update(raw_ui_state)

    screen = str(ui_state.get("screen", "list")).lower()
    ui_state["screen"] = screen if screen in ALLOWED_UI_SCREENS else "list"

    try:
        ui_state["page"] = max(0, int(ui_state.get("page", 0)))
    except Exception:
        ui_state["page"] = 0
    return ui_state


def _enum_name(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, "name"):
        return str(getattr(value, "name"))
    return str(value)


def _to_float(value, fallback: float = 0.0) -> float:
    if value is None:
        return fallback
    try:
        return float(value)
    except Exception:
        return fallback


def _item_to_dict(item, seq: int = 0) -> dict:
    user = getattr(item, "user", None)
    return {
        "id": str(getattr(item, "id", "")),
        "slug": getattr(item, "slug", None),
        "name": getattr(item, "name", None),
        "status": _enum_name(getattr(item, "status", None)),
        "priority": _enum_name(getattr(item, "priority", None)),
        "price": getattr(item, "price", None),
        "raw_price": getattr(item, "raw_price", None),
        "status_description": getattr(item, "status_description", None),
        "status_expiration_date": getattr(item, "status_expiration_date", None),
        "views_counter": getattr(item, "views_counter", None),
        "approval_date": getattr(item, "approval_date", None),
        "created_at": getattr(item, "created_at", None),
        "user_username": getattr(user, "username", None),
        "user_id": getattr(user, "id", None),
        "_seq": seq,
    }


def _resolve_api_statuses(status_presets: list[str]) -> list[ItemStatuses] | None:
    selected = set(status_presets or [])
    selected.discard("PREMIUM")

    statuses: list[ItemStatuses] = []

    def add(status: ItemStatuses):
        if status not in statuses:
            statuses.append(status)

    if "APPROVED" in selected:
        add(ItemStatuses.APPROVED)
    if "MODERATION" in selected:
        add(ItemStatuses.PENDING_APPROVAL)
        add(ItemStatuses.PENDING_MODERATION)
    if "SOLD" in selected:
        add(ItemStatuses.SOLD)
    if "BLOCKED_DECLINED" in selected:
        add(ItemStatuses.BLOCKED)
        add(ItemStatuses.DECLINED)
    if "DRAFT" in selected:
        add(ItemStatuses.DRAFT)

    return statuses or None


def _load_latest_items(account, filters: dict, max_count: int = MAX_ITEMS_TO_LOAD) -> list[dict]:
    account_id = getattr(account, "id", None)
    if not account_id:
        account.get()
        account_id = getattr(account, "id", None)
    if not account_id:
        raise Exception("Could not resolve Playerok account ID")

    user = account.get_user(id=str(account_id))
    if user is None:
        raise Exception("Could not fetch Playerok profile")

    api_statuses = _resolve_api_statuses(filters.get("status_presets", []))
    loaded_items: list[dict] = []
    after_cursor = None

    while len(loaded_items) < max_count:
        request_count = min(API_ITEMS_PAGE_SIZE, max_count - len(loaded_items))
        items_page = user.get_items(count=request_count, statuses=api_statuses, after_cursor=after_cursor)
        current_items = list(getattr(items_page, "items", []) or [])
        if not current_items:
            break

        for item in current_items:
            if getattr(item, "id", None) is None:
                continue
            loaded_items.append(_item_to_dict(item, seq=len(loaded_items)))

        page_info = getattr(items_page, "page_info", None)
        has_next_page = bool(getattr(page_info, "has_next_page", False)) if page_info else False
        after_cursor = getattr(page_info, "end_cursor", None) if page_info else None
        if not has_next_page or not after_cursor:
            break

    return loaded_items[:max_count]


def _status_matches(item_status: str, selected_status_presets: set[str]) -> bool:
    if "APPROVED" in selected_status_presets and item_status == "APPROVED":
        return True
    if "MODERATION" in selected_status_presets and item_status in {"PENDING_APPROVAL", "PENDING_MODERATION"}:
        return True
    if "SOLD" in selected_status_presets and item_status == "SOLD":
        return True
    if "BLOCKED_DECLINED" in selected_status_presets and item_status in {"BLOCKED", "DECLINED"}:
        return True
    if "DRAFT" in selected_status_presets and item_status == "DRAFT":
        return True
    return False


def _apply_filters(all_items: list[dict], filters: dict) -> list[dict]:
    filtered = list(all_items)

    for idx, item in enumerate(filtered):
        if isinstance(item, dict) and "_seq" not in item:
            item["_seq"] = idx

    selected_presets = [str(v).upper() for v in (filters.get("status_presets") or [])]
    selected_set = set(selected_presets)
    has_premium = "PREMIUM" in selected_set
    status_selected = set(selected_set)
    status_selected.discard("PREMIUM")

    if status_selected:
        filtered = [
            item
            for item in filtered
            if _status_matches(str(item.get("status") or "").upper(), status_selected)
        ]

    if has_premium:
        filtered = [item for item in filtered if str(item.get("priority") or "").upper() == "PREMIUM"]

    query = str(filters.get("name_query") or "").strip().lower()
    if query:
        filtered = [item for item in filtered if query in str(item.get("name") or "").lower()]

    reverse = filters.get("sort_order", "DESC") == "DESC"
    filtered.sort(key=lambda item: _to_float(item.get("price"), fallback=-1.0), reverse=reverse)
    return filtered


def _slice_page(filtered_items: list[dict], page: int) -> tuple[list[dict], int, int]:
    total_found = len(filtered_items)
    total_pages = max(1, (total_found + MENU_ITEMS_PAGE_SIZE - 1) // MENU_ITEMS_PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))

    start_ix = page * MENU_ITEMS_PAGE_SIZE
    end_ix = start_ix + MENU_ITEMS_PAGE_SIZE
    return filtered_items[start_ix:end_ix], page, total_pages


def _fmt_price(value) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.2f} RUB"
    except Exception:
        return str(value)


def _item_price_for_priority(item) -> int:
    raw_price = getattr(item, "price", None)
    if raw_price is None:
        raw_price = getattr(item, "raw_price", None)
    try:
        return int(float(raw_price))
    except Exception:
        return 0


def _pick_publish_priority_status(priority_statuses):
    statuses = list(priority_statuses or [])
    result = {"DEFAULT": None, "PREMIUM": None}

    for status in statuses:
        status_type = getattr(status, "type", None)
        if status_type == PriorityTypes.DEFAULT and result["DEFAULT"] is None:
            result["DEFAULT"] = status
        elif status_type == PriorityTypes.PREMIUM and result["PREMIUM"] is None:
            result["PREMIUM"] = status

    if result["DEFAULT"] is None:
        for status in statuses:
            try:
                if float(getattr(status, "price", 0) or 0) == 0:
                    result["DEFAULT"] = status
                    break
            except Exception:
                continue

    if result["DEFAULT"] is None and statuses and result["PREMIUM"] is None:
        result["DEFAULT"] = statuses[0]

    return result


async def _render_item_card(
    message: Message,
    state: FSMContext,
    account,
    item_id: str,
    callback: CallbackQuery | None = None,
    item=None,
    allow_owner_actions: bool = True,
):
    full_item = item if item is not None else account.get_item(id=item_id)
    payload = format_item_card_payload(item=full_item, account=account)
    is_owner = bool(payload.get("is_owner")) and allow_owner_actions

    await state.update_data(
        items_item_ctx={
            "item_id": str(payload.get("item_id") or ""),
            "item_slug": payload.get("item_slug"),
            "item_url": payload.get("item_url"),
            "is_owner": is_owner,
            "item_status": payload.get("item_status"),
            "item_name": getattr(full_item, "name", None),
        },
        items_item_action=None,
    )

    await throw_float_message(
        state=state,
        message=message,
        text=payload.get("text", "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043e\u0442\u0440\u0438\u0441\u043e\u0432\u0430\u0442\u044c \u043a\u0430\u0440\u0442\u043e\u0447\u043a\u0443 \u0442\u043e\u0432\u0430\u0440\u0430"),
        reply_markup=templ.item_card_kb(
            back_cb=calls.ItemsAction(action="open").pack(),
            item_url=payload.get("item_url") or "https://playerok.com/products/",
            is_owner=is_owner,
            item_status=payload.get("item_status"),
        ),
        callback=callback,
    )


async def show_items_filter_menu(
    message: Message,
    state: FSMContext,
    callback: CallbackQuery | None = None,
):
    await state.set_state(None)
    data = await state.get_data()
    filters = _normalize_filters(data.get("items_filters"))
    ui_state = _normalize_ui_state(data.get("items_ui"))
    draft_filters = (
        _normalize_filters(ui_state.get("draft_filters"))
        if isinstance(ui_state.get("draft_filters"), dict)
        else _copy_filters(filters)
    )
    ui_state["screen"] = "filter"
    ui_state["draft_filters"] = _copy_filters(draft_filters)
    await state.update_data(items_filters=filters, items_ui=ui_state)

    await throw_float_message(
        state=state,
        message=message,
        text=templ.items_filter_text(draft_filters),
        reply_markup=templ.items_filter_kb(draft_filters),
        callback=callback,
    )


async def show_items_menu(
    message: Message,
    state: FSMContext,
    callback: CallbackQuery | None = None,
    reset: bool = False,
    force_reload: bool = False,
):
    await state.set_state(None)

    account = _get_playerok_account()
    data = await state.get_data()
    filters = _default_filters() if reset else _normalize_filters(data.get("items_filters"))
    ui_state = _default_ui_state() if reset else _normalize_ui_state(data.get("items_ui"))

    cached_items = data.get("items_cached")
    if force_reload or not isinstance(cached_items, list):
        loading_message = message
        loading_callback = callback
        loading_text = "\u23F3 \u0417\u0430\u0433\u0440\u0443\u0436\u0430\u044e \u0442\u043e\u0432\u0430\u0440\u044b, \u043f\u043e\u0434\u043e\u0436\u0434\u0438\u0442\u0435..."

        if callback is not None:
            await throw_float_message(
                state=state,
                message=message,
                text=loading_text,
                callback=callback,
            )
            loading_callback = None
        elif getattr(message, "text", None) and str(getattr(message, "text", "")).startswith("/"):
            loading_message = await throw_float_message(
                state=state,
                message=message,
                text=loading_text,
                send=True,
            ) or message

        if account is None:
            await throw_float_message(
                state=state,
                message=loading_message,
                text=templ.do_action_text("\u274C \u041D\u0435\u0442 \u043F\u043E\u0434\u043A\u043B\u044E\u0447\u0435\u043D\u0438\u044F \u043A Playerok"),
                reply_markup=templ.back_kb(calls.ItemsAction(action="open").pack()),
                callback=loading_callback,
            )
            return
        try:
            cached_items = _load_latest_items(account, filters=filters, max_count=MAX_ITEMS_TO_LOAD)
        except Exception as e:
            await throw_float_message(
                state=state,
                message=loading_message,
                text=templ.do_action_text(f"\u274C \u041D\u0435 \u0443\u0434\u0430\u043B\u043E\u0441\u044C \u0437\u0430\u0433\u0440\u0443\u0437\u0438\u0442\u044C \u0442\u043E\u0432\u0430\u0440\u044B: {e}"),
                reply_markup=templ.back_kb(calls.ItemsAction(action="open").pack()),
                callback=loading_callback,
            )
            return

        await state.update_data(items_cached=cached_items)
        message = loading_message
        callback = loading_callback
    else:
        cached_items = [item for item in cached_items if isinstance(item, dict)]

    filtered_items = _apply_filters(cached_items, filters)
    page_items, page, total_pages = _slice_page(filtered_items, ui_state.get("page", 0))

    ui_state.pop("draft_filters", None)
    ui_state["page"] = page
    ui_state["screen"] = "list"
    await state.update_data(
        items_filters=filters,
        items_ui=ui_state,
        items_cached=cached_items,
        items_total_loaded=len(cached_items),
        items_item_ctx=None,
        items_item_action=None,
    )

    await throw_float_message(
        state=state,
        message=message,
        text=templ.items_menu_text(
            filters=filters,
            page=page,
            total_pages=total_pages,
            total_found=len(filtered_items),
            total_loaded=len(cached_items),
        ),
        reply_markup=templ.items_menu_kb(
            filters=filters,
            page_items=page_items,
            page=page,
            total_pages=total_pages,
        ),
        callback=callback,
    )


@router.callback_query(calls.ItemsAction.filter())
async def callback_items_actions(
    callback: CallbackQuery,
    callback_data: calls.ItemsAction,
    state: FSMContext,
):
    action = callback_data.action
    value = callback_data.value

    if action == "noop":
        await callback.answer()
        return

    data = await state.get_data()
    filters = _normalize_filters(data.get("items_filters"))
    ui_state = _normalize_ui_state(data.get("items_ui"))
    draft_filters = (
        _normalize_filters(ui_state.get("draft_filters"))
        if isinstance(ui_state.get("draft_filters"), dict)
        else _copy_filters(filters)
    )
    item_ctx = data.get("items_item_ctx") if isinstance(data.get("items_item_ctx"), dict) else {}
    item_action = data.get("items_item_action") if isinstance(data.get("items_item_action"), dict) else {}
    force_reload = False

    account = _get_playerok_account()

    if action == "item_action_cancel":
        await state.update_data(items_item_action=None)
        item_id = str(item_ctx.get("item_id") or "")
        if not item_id or account is None:
            await show_items_menu(callback.message, state, callback=callback)
            return

        try:
            await _render_item_card(
                message=callback.message,
                state=state,
                account=account,
                item_id=item_id,
                callback=callback,
            )
        except Exception as e:
            await callback.answer(f"\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043e\u0442\u043a\u0440\u044b\u0442\u044c \u0442\u043e\u0432\u0430\u0440: {e}", show_alert=True)
        return

    if action == "item_raise_prompt":
        item_id = str(item_ctx.get("item_id") or "")
        if account is None or not item_id:
            await callback.answer("\u041a\u0430\u0440\u0442\u043e\u0447\u043a\u0430 \u0442\u043e\u0432\u0430\u0440\u0430 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u0430", show_alert=True)
            return

        try:
            full_item = account.get_item(id=item_id)
            card_payload = format_item_card_payload(item=full_item, account=account)
            if not card_payload.get("is_owner"):
                await callback.answer("\u041f\u043e\u0434\u043d\u0438\u043c\u0430\u0442\u044c \u0442\u043e\u0432\u0430\u0440 \u043c\u043e\u0436\u0435\u0442 \u0442\u043e\u043b\u044c\u043a\u043e \u0432\u043b\u0430\u0434\u0435\u043b\u0435\u0446", show_alert=True)
                return

            price_value = _item_price_for_priority(full_item)
            priority_statuses = account.get_item_priority_statuses(item_id, price_value)
            premium_status = None
            for status in priority_statuses or []:
                if getattr(status, "type", None) == PriorityTypes.PREMIUM:
                    premium_status = status
                    break

            if premium_status is None:
                await callback.answer("\u041d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u044b\u0439 \u0441\u0442\u0430\u0442\u0443\u0441 \u0434\u043b\u044f \u043f\u043e\u0434\u043d\u044f\u0442\u0438\u044f \u0442\u043e\u0432\u0430\u0440\u0430", show_alert=True)
                return

            await state.update_data(
                items_item_action={
                    "kind": "raise",
                    "item_id": item_id,
                    "priority_status_id": str(getattr(premium_status, "id", "")),
                    "price": getattr(premium_status, "price", None),
                    "item_name": getattr(full_item, "name", None),
                }
            )

            await throw_float_message(
                state=state,
                message=callback.message,
                text=templ.do_action_text(
                    f"\U0001F4C8 \u041f\u043e\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u0435 \u043f\u043e\u0434\u043d\u044f\u0442\u0438\u0435 \u0442\u043e\u0432\u0430\u0440\u0430 <b>{getattr(full_item, 'name', '\u0411\u0435\u0437 \u043d\u0430\u0437\u0432\u0430\u043d\u0438\u044f')}</b>\n"
                    f"\U0001F4B0 \u0421\u0442\u043e\u0438\u043c\u043e\u0441\u0442\u044c: <b>{_fmt_price(getattr(premium_status, 'price', None))}</b>"
                ),
                reply_markup=templ.item_card_confirm_kb(confirm_action="item_raise_confirm"),
                callback=callback,
            )
        except Exception as e:
            await callback.answer(f"\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043f\u043e\u0434\u0433\u043e\u0442\u043e\u0432\u0438\u0442\u044c \u043f\u043e\u0434\u043d\u044f\u0442\u0438\u0435 \u0442\u043e\u0432\u0430\u0440\u0430: {e}", show_alert=True)
        return

    if action == "item_raise_confirm":
        if account is None:
            await callback.answer("\u041d\u0435\u0442 \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u044f \u043a Playerok", show_alert=True)
            return
        if item_action.get("kind") != "raise":
            await callback.answer("\u0414\u0435\u0439\u0441\u0442\u0432\u0438\u0435 \u0443\u0441\u0442\u0430\u0440\u0435\u043b\u043e", show_alert=True)
            return

        item_id = str(item_action.get("item_id") or "")
        priority_status_id = str(item_action.get("priority_status_id") or "")
        if not item_id or not priority_status_id:
            await callback.answer("\u041d\u0435\u0434\u043e\u0441\u0442\u0430\u0442\u043e\u0447\u043d\u043e \u0434\u0430\u043d\u043d\u044b\u0445 \u0434\u043b\u044f \u043f\u043e\u0434\u043d\u044f\u0442\u0438\u044f \u0442\u043e\u0432\u0430\u0440\u0430", show_alert=True)
            return

        try:
            account.increase_item_priority_status(item_id, priority_status_id)
            item_name = str(item_action.get("item_name") or item_ctx.get("item_name") or "\u0411\u0435\u0437 \u043d\u0430\u0437\u0432\u0430\u043d\u0438\u044f")
            await state.update_data(items_item_action=None)
            await _render_item_card(
                message=callback.message,
                state=state,
                account=account,
                item_id=item_id,
                callback=callback,
            )
            if callback.message is not None:
                await callback.message.answer(f"\u2705 \u0422\u043e\u0432\u0430\u0440 \u0443\u0441\u043f\u0435\u0448\u043d\u043e \u043f\u043e\u0434\u043d\u044f\u0442: {item_name}")
        except Exception as e:
            await callback.answer(f"\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043f\u043e\u0434\u043d\u044f\u0442\u044c \u0442\u043e\u0432\u0430\u0440: {e}", show_alert=True)
        return

    if action == "item_publish_prompt":
        item_id = str(item_ctx.get("item_id") or "")
        if account is None or not item_id:
            await callback.answer("\u041a\u0430\u0440\u0442\u043e\u0447\u043a\u0430 \u0442\u043e\u0432\u0430\u0440\u0430 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u0430", show_alert=True)
            return

        try:
            full_item = account.get_item(id=item_id)
            card_payload = format_item_card_payload(item=full_item, account=account)
            if not card_payload.get("is_owner"):
                await callback.answer("\u041f\u0443\u0431\u043b\u0438\u043a\u043e\u0432\u0430\u0442\u044c \u0442\u043e\u0432\u0430\u0440 \u043c\u043e\u0436\u0435\u0442 \u0442\u043e\u043b\u044c\u043a\u043e \u0432\u043b\u0430\u0434\u0435\u043b\u0435\u0446", show_alert=True)
                return
            if str(card_payload.get("item_status") or "").upper() not in {"DRAFT", "EXPIRED"}:
                await callback.answer("\u041f\u0443\u0431\u043b\u0438\u043a\u0430\u0446\u0438\u044f \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u0430 \u0442\u043e\u043b\u044c\u043a\u043e \u0434\u043b\u044f \u0447\u0435\u0440\u043d\u043e\u0432\u0438\u043a\u043e\u0432 \u0438 \u0438\u0441\u0442\u0451\u043a\u0448\u0438\u0445 \u0442\u043e\u0432\u0430\u0440\u043e\u0432", show_alert=True)
                return

            price_value = _item_price_for_priority(full_item)
            priority_statuses = account.get_item_priority_statuses(item_id, price_value)
            publish_variants = _pick_publish_priority_status(priority_statuses)
            default_status = publish_variants.get("DEFAULT")
            premium_status = publish_variants.get("PREMIUM")

            if default_status is None and premium_status is None:
                await callback.answer("\u041d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u044b \u0432\u0430\u0440\u0438\u0430\u043d\u0442\u044b \u043f\u0443\u0431\u043b\u0438\u043a\u0430\u0446\u0438\u0438", show_alert=True)
                return

            await state.update_data(
                items_item_action={
                    "kind": "publish",
                    "item_id": item_id,
                    "item_name": getattr(full_item, "name", None),
                    "variants": {
                        "DEFAULT": {
                            "priority_status_id": str(getattr(default_status, "id", "")) if default_status else "",
                            "price": getattr(default_status, "price", None) if default_status else None,
                        },
                        "PREMIUM": {
                            "priority_status_id": str(getattr(premium_status, "id", "")) if premium_status else "",
                            "price": getattr(premium_status, "price", None) if premium_status else None,
                        },
                    },
                }
            )

            await throw_float_message(
                state=state,
                message=callback.message,
                text=templ.do_action_text(
                    f"\U0001F4E4 \u041f\u043e\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u0435 \u043f\u0443\u0431\u043b\u0438\u043a\u0430\u0446\u0438\u044e \u0442\u043e\u0432\u0430\u0440\u0430 <b>{getattr(full_item, 'name', '\u0411\u0435\u0437 \u043d\u0430\u0437\u0432\u0430\u043d\u0438\u044f')}</b>\n"
                    "\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0442\u0438\u043f \u043f\u0443\u0431\u043b\u0438\u043a\u0430\u0446\u0438\u0438 \u043d\u0438\u0436\u0435:"
                ),
                reply_markup=templ.item_publish_confirm_kb(
                    has_default=default_status is not None,
                    has_premium=premium_status is not None,
                    default_price=getattr(default_status, "price", None) if default_status else None,
                    premium_price=getattr(premium_status, "price", None) if premium_status else None,
                ),
                callback=callback,
            )
        except Exception as e:
            await callback.answer(f"\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043f\u043e\u0434\u0433\u043e\u0442\u043e\u0432\u0438\u0442\u044c \u043f\u0443\u0431\u043b\u0438\u043a\u0430\u0446\u0438\u044e \u0442\u043e\u0432\u0430\u0440\u0430: {e}", show_alert=True)
        return

    if action == "item_publish_confirm":
        if account is None:
            await callback.answer("\u041d\u0435\u0442 \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u044f \u043a Playerok", show_alert=True)
            return
        if item_action.get("kind") != "publish":
            await callback.answer("\u0414\u0435\u0439\u0441\u0442\u0432\u0438\u0435 \u0443\u0441\u0442\u0430\u0440\u0435\u043b\u043e", show_alert=True)
            return

        item_id = str(item_action.get("item_id") or "")
        variants = item_action.get("variants") if isinstance(item_action.get("variants"), dict) else {}
        selected_variant = str(value or "DEFAULT").upper()
        variant_payload = variants.get(selected_variant)
        if not isinstance(variant_payload, dict):
            variant_payload = variants.get("DEFAULT") or variants.get("PREMIUM")

        priority_status_id = str((variant_payload or {}).get("priority_status_id") or "")
        if not item_id or not priority_status_id:
            await callback.answer("\u041d\u0435\u0434\u043e\u0441\u0442\u0430\u0442\u043e\u0447\u043d\u043e \u0434\u0430\u043d\u043d\u044b\u0445 \u0434\u043b\u044f \u043f\u0443\u0431\u043b\u0438\u043a\u0430\u0446\u0438\u0438 \u0442\u043e\u0432\u0430\u0440\u0430", show_alert=True)
            return

        try:
            account.publish_item(item_id=item_id, priority_status_id=priority_status_id)
            item_name = str(item_action.get("item_name") or item_ctx.get("item_name") or "\u0411\u0435\u0437 \u043d\u0430\u0437\u0432\u0430\u043d\u0438\u044f")
            logger.info(
                "\u0423\u0441\u043f\u0435\u0448\u043d\u0430\u044f \u043f\u0443\u0431\u043b\u0438\u043a\u0430\u0446\u0438\u044f \u0442\u043e\u0432\u0430\u0440\u0430 \u0438\u0437 /items: id=%s, priority=%s, name=%s",
                item_id,
                selected_variant,
                item_name,
            )
            await state.update_data(items_item_action=None)
            await _render_item_card(
                message=callback.message,
                state=state,
                account=account,
                item_id=item_id,
                callback=callback,
            )
            if callback.message is not None:
                await callback.message.answer(f"\u2705 \u0422\u043e\u0432\u0430\u0440 \u0443\u0441\u043f\u0435\u0448\u043d\u043e \u043e\u043f\u0443\u0431\u043b\u0438\u043a\u043e\u0432\u0430\u043d: {item_name}")
        except Exception as e:
            await callback.answer(f"\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043e\u043f\u0443\u0431\u043b\u0438\u043a\u043e\u0432\u0430\u0442\u044c \u0442\u043e\u0432\u0430\u0440: {e}", show_alert=True)
        return

    if action == "item_delete_prompt":
        item_id = str(item_ctx.get("item_id") or "")
        if account is None or not item_id:
            await callback.answer("\u041a\u0430\u0440\u0442\u043e\u0447\u043a\u0430 \u0442\u043e\u0432\u0430\u0440\u0430 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u0430", show_alert=True)
            return

        try:
            full_item = account.get_item(id=item_id)
            card_payload = format_item_card_payload(item=full_item, account=account)
            if not card_payload.get("is_owner"):
                await callback.answer("\u0423\u0434\u0430\u043b\u044f\u0442\u044c \u0442\u043e\u0432\u0430\u0440 \u043c\u043e\u0436\u0435\u0442 \u0442\u043e\u043b\u044c\u043a\u043e \u0432\u043b\u0430\u0434\u0435\u043b\u0435\u0446", show_alert=True)
                return

            await state.update_data(
                items_item_action={
                    "kind": "delete",
                    "item_id": item_id,
                    "item_name": getattr(full_item, "name", None),
                }
            )
            await throw_float_message(
                state=state,
                message=callback.message,
                text=templ.do_action_text(
                    f"\U0001F5D1 \u041f\u043e\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u0435 \u0443\u0434\u0430\u043b\u0435\u043d\u0438\u0435 \u0442\u043e\u0432\u0430\u0440\u0430 <b>{getattr(full_item, 'name', '\u0411\u0435\u0437 \u043d\u0430\u0437\u0432\u0430\u043d\u0438\u044f')}</b>\n"
                    "\u0414\u0435\u0439\u0441\u0442\u0432\u0438\u0435 \u043d\u0435\u043b\u044c\u0437\u044f \u043e\u0442\u043c\u0435\u043d\u0438\u0442\u044c."
                ),
                reply_markup=templ.item_card_confirm_kb(confirm_action="item_delete_confirm"),
                callback=callback,
            )
        except Exception as e:
            await callback.answer(f"\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043f\u043e\u0434\u0433\u043e\u0442\u043e\u0432\u0438\u0442\u044c \u0443\u0434\u0430\u043b\u0435\u043d\u0438\u0435 \u0442\u043e\u0432\u0430\u0440\u0430: {e}", show_alert=True)
        return

    if action == "item_delete_confirm":
        if account is None:
            await callback.answer("\u041d\u0435\u0442 \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u044f \u043a Playerok", show_alert=True)
            return
        if item_action.get("kind") != "delete":
            await callback.answer("\u0414\u0435\u0439\u0441\u0442\u0432\u0438\u0435 \u0443\u0441\u0442\u0430\u0440\u0435\u043b\u043e", show_alert=True)
            return

        item_id = str(item_action.get("item_id") or "")
        if not item_id:
            await callback.answer("\u041d\u0435\u0434\u043e\u0441\u0442\u0430\u0442\u043e\u0447\u043d\u043e \u0434\u0430\u043d\u043d\u044b\u0445 \u0434\u043b\u044f \u0443\u0434\u0430\u043b\u0435\u043d\u0438\u044f \u0442\u043e\u0432\u0430\u0440\u0430", show_alert=True)
            return

        try:
            account.remove_item(item_id)
            item_name = str(item_action.get("item_name") or item_ctx.get("item_name") or "\u0411\u0435\u0437 \u043d\u0430\u0437\u0432\u0430\u043d\u0438\u044f")
            logger.info(
                "\u0423\u0441\u043f\u0435\u0448\u043d\u043e\u0435 \u0443\u0434\u0430\u043b\u0435\u043d\u0438\u0435 \u0442\u043e\u0432\u0430\u0440\u0430 \u0438\u0437 /items: id=%s, name=%s",
                item_id,
                item_name,
            )
            await state.update_data(items_item_action=None, items_cached=None)
            await show_items_menu(
                message=callback.message,
                state=state,
                callback=callback,
                force_reload=True,
            )

            if callback.message is not None:
                await callback.message.answer(f"\u2705 \u0422\u043e\u0432\u0430\u0440 \u0443\u0441\u043f\u0435\u0448\u043d\u043e \u0443\u0434\u0430\u043b\u0451\u043d: {item_name}")
        except Exception as e:
            await callback.answer(f"\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0443\u0434\u0430\u043b\u0438\u0442\u044c \u0442\u043e\u0432\u0430\u0440: {e}", show_alert=True)
        return

    if action == "open":
        ui_state["screen"] = "list"
    elif action == "page":
        try:
            ui_state["page"] = max(0, int(value or 0))
        except Exception:
            ui_state["page"] = 0
        ui_state["screen"] = "list"
    elif action == "open_filter":
        ui_state["screen"] = "filter"
    elif action == "close_filter":
        ui_state["screen"] = "list"
    elif action == "toggle_preset":
        preset = str(value or "").upper()
        if preset in ALLOWED_STATUS_PRESETS:
            presets = list(draft_filters.get("status_presets") or [])
            if preset in presets:
                presets.remove(preset)
            else:
                presets.append(preset)
            draft_filters["status_presets"] = presets
        ui_state["screen"] = "filter"
    elif action == "sort_toggle":
        draft_filters["sort_order"] = "ASC" if draft_filters.get("sort_order", "DESC") == "DESC" else "DESC"
        ui_state["screen"] = "filter"
    elif action == "apply":
        filters = _copy_filters(draft_filters)
        ui_state["screen"] = "list"
        ui_state["page"] = 0
        force_reload = True
    elif action == "reset":
        name_query = str(filters.get("name_query") or "").strip()
        draft_filters = _default_filters()
        draft_filters["name_query"] = name_query
        ui_state["screen"] = "filter"
        ui_state["page"] = 0
    elif action == "refresh":
        ui_state["screen"] = "list"
        ui_state["page"] = 0
        force_reload = True
    elif action == "search_enter":
        await state.update_data(items_filters=filters, items_ui=ui_state)
        await state.set_state(states.ItemsStates.waiting_for_name_query)
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.do_action_text("Enter item name or part of it for search:"),
            reply_markup=templ.back_kb(calls.ItemsAction(action="open").pack()),
            callback=callback,
            send=True,
        )
        return
    elif action == "search_clear":
        filters["name_query"] = ""
        ui_state["screen"] = "list"
        ui_state["page"] = 0
        force_reload = True
    else:
        await callback.answer("Unknown action", show_alert=False)
        return

    if ui_state.get("screen") == "filter":
        ui_state["draft_filters"] = _copy_filters(draft_filters)
    else:
        ui_state.pop("draft_filters", None)

    await state.update_data(items_filters=filters, items_ui=ui_state, items_item_ctx=None, items_item_action=None)

    if ui_state.get("screen") == "filter":
        await show_items_filter_menu(
            message=callback.message,
            state=state,
            callback=callback,
        )
        return

    await show_items_menu(
        message=callback.message,
        state=state,
        callback=callback,
        force_reload=force_reload,
    )


@router.callback_query(calls.ItemViewFromItems.filter())
async def callback_item_view_from_items(
    callback: CallbackQuery,
    callback_data: calls.ItemViewFromItems,
    state: FSMContext,
):
    await state.set_state(None)

    account = _get_playerok_account()
    if account is None:
        await callback.answer("No connection to Playerok", show_alert=True)
        return

    item_id = callback_data.it_id
    try:
        await _render_item_card(
            message=callback.message,
            state=state,
            account=account,
            item_id=item_id,
            callback=callback,
        )
    except Exception as e:
        await callback.answer(f"Could not open item: {e}", show_alert=True)


