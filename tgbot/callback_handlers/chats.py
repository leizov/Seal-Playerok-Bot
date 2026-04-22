from __future__ import annotations

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from playerokapi.enums import ChatTypes

from .. import callback_datas as calls
from .. import templates as templ
from ..helpful import get_playerok_bot, throw_float_message


router = Router()

MAX_CHATS_TO_LOAD = 70
API_CHATS_PAGE_SIZE = 24
MENU_CHATS_PAGE_SIZE = 24


def _get_playerok_account():
    playerok_bot = get_playerok_bot()
    if playerok_bot is None:
        return None
    return getattr(playerok_bot, "account", None) or getattr(playerok_bot, "playerok_account", None)


def _default_ui_state() -> dict:
    return {
        "page": 0,
    }


def _normalize_ui_state(raw_ui_state: dict | None) -> dict:
    ui_state = _default_ui_state()
    if isinstance(raw_ui_state, dict):
        ui_state.update(raw_ui_state)

    try:
        ui_state["page"] = max(0, int(ui_state.get("page", 0)))
    except Exception:
        ui_state["page"] = 0
    return ui_state


def _to_int(value, fallback: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return fallback


def _resolve_interlocutor(chat, account_id: str | None):
    users = list(getattr(chat, "users", []) or [])
    if not users:
        return None

    for user in users:
        user_id = str(getattr(user, "id", "") or "")
        if account_id and user_id and user_id == account_id:
            continue
        return user

    return users[0]


def _chat_to_dict(chat, seq: int, account_id: str | None, support_chat_id: str | None, system_chat_id: str | None) -> dict:
    chat_id = str(getattr(chat, "id", "") or "")
    chat_type = getattr(chat, "type", None)
    chat_type_name = getattr(chat_type, "name", str(chat_type) if chat_type is not None else "")

    interlocutor = _resolve_interlocutor(chat, account_id)
    username = str(getattr(interlocutor, "username", "") or "").strip()
    username_lower = username.lower()
    is_online = bool(getattr(interlocutor, "is_online", False))
    is_blocked = bool(getattr(interlocutor, "is_blocked", False))
    unread_messages_counter = max(0, _to_int(getattr(chat, "unread_messages_counter", 0), 0))

    is_notifications_chat = chat_type == ChatTypes.NOTIFICATIONS or chat_type_name == "NOTIFICATIONS"
    is_support_chat = chat_type == ChatTypes.SUPPORT or chat_type_name == "SUPPORT"
    is_system_chat = False
    if system_chat_id and chat_id and chat_id == system_chat_id:
        is_system_chat = True
    elif username_lower in {"playerok.com", "playerok"}:
        is_system_chat = True

    if support_chat_id and chat_id and chat_id == support_chat_id:
        is_support_chat = True

    special_emoji = ""
    display_name = username or "Без имени"

    if is_notifications_chat:
        special_emoji = "🔔"
        display_name = "Уведомления"
    elif is_system_chat:
        special_emoji = "🔔"
        display_name = "Playerok"
    elif is_support_chat:
        special_emoji = "🔰"
        display_name = username or "Поддержка"

    if is_blocked:
        status_emoji = "⛔"
    elif is_online:
        status_emoji = "🟢"
    else:
        status_emoji = "⚪"

    # Для чатов поддержки и уведомлений не показываем онлайн/оффлайн статус в кнопке.
    if is_notifications_chat or is_support_chat:
        status_emoji = ""

    return {
        "id": chat_id,
        "type": chat_type_name,
        "display_name": display_name,
        "status_emoji": status_emoji,
        "special_emoji": special_emoji,
        "unread_messages_counter": unread_messages_counter,
        "is_online": is_online,
        "is_blocked": is_blocked,
        "_seq": seq,
    }


def _load_latest_chats(account, max_count: int = MAX_CHATS_TO_LOAD) -> list[dict]:
    if not getattr(account, "id", None):
        account.get()

    account_id = str(getattr(account, "id", "") or "") or None
    support_chat_id = str(getattr(account, "support_chat_id", "") or "") or None
    system_chat_id = str(getattr(account, "system_chat_id", "") or "") or None

    loaded_chats: list[dict] = []
    after_cursor = None

    while len(loaded_chats) < max_count:
        request_count = min(API_CHATS_PAGE_SIZE, max_count - len(loaded_chats))
        chats_page = account.get_chats(count=request_count, after_cursor=after_cursor)
        current_chats = list(getattr(chats_page, "chats", []) or [])
        if not current_chats:
            break

        for chat in current_chats:
            if not getattr(chat, "id", None):
                continue
            loaded_chats.append(
                _chat_to_dict(
                    chat=chat,
                    seq=len(loaded_chats),
                    account_id=account_id,
                    support_chat_id=support_chat_id,
                    system_chat_id=system_chat_id,
                )
            )

        page_info = getattr(chats_page, "page_info", None)
        has_next_page = bool(getattr(page_info, "has_next_page", False)) if page_info else False
        after_cursor = getattr(page_info, "end_cursor", None) if page_info else None
        if not has_next_page or not after_cursor:
            break

    return loaded_chats[:max_count]


def _slice_page(cached_chats: list[dict], page: int) -> tuple[list[dict], int, int]:
    total_found = len(cached_chats)
    total_pages = max(1, (total_found + MENU_CHATS_PAGE_SIZE - 1) // MENU_CHATS_PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))

    start_ix = page * MENU_CHATS_PAGE_SIZE
    end_ix = start_ix + MENU_CHATS_PAGE_SIZE
    return cached_chats[start_ix:end_ix], page, total_pages


async def show_chats_menu(
    message: Message,
    state: FSMContext,
    callback: CallbackQuery | None = None,
    reset: bool = False,
    force_reload: bool = False,
):
    await state.set_state(None)

    account = _get_playerok_account()

    data = await state.get_data()
    ui_state = _default_ui_state() if reset else _normalize_ui_state(data.get("chats_ui"))
    cached_chats = data.get("chats_cached")

    if force_reload or not isinstance(cached_chats, list):
        loading_message = message
        loading_callback = callback
        loading_text = "⏳ Загружаю чаты..."

        if callback is not None:
            await throw_float_message(
                state=state,
                message=message,
                text=loading_text,
                callback=callback,
            )
            loading_callback = None
        else:
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
                text=templ.do_action_text("❌ Нет подключения к Playerok"),
                reply_markup=templ.back_kb(calls.ChatsAction(action="open").pack()),
                callback=loading_callback,
            )
            return

        try:
            cached_chats = _load_latest_chats(account=account, max_count=MAX_CHATS_TO_LOAD)
        except Exception as e:
            await throw_float_message(
                state=state,
                message=loading_message,
                text=templ.do_action_text(f"❌ Не удалось загрузить чаты: {e}"),
                reply_markup=templ.back_kb(calls.ChatsAction(action="open").pack()),
                callback=loading_callback,
            )
            return

        await state.update_data(chats_cached=cached_chats)
        message = loading_message
        callback = loading_callback
    else:
        cached_chats = [chat for chat in cached_chats if isinstance(chat, dict)]

    page_chats, page, total_pages = _slice_page(cached_chats, ui_state.get("page", 0))
    ui_state["page"] = page

    await state.update_data(
        chats_ui=ui_state,
        chats_cached=cached_chats,
        chats_total_loaded=len(cached_chats),
    )

    await throw_float_message(
        state=state,
        message=message,
        text=templ.chats_menu_text(
            page=page,
            total_pages=total_pages,
            total_loaded=len(cached_chats),
            total_found=len(cached_chats),
        ),
        reply_markup=templ.chats_menu_kb(
            page_chats=page_chats,
            page=page,
            total_pages=total_pages,
        ),
        callback=callback,
    )


@router.callback_query(calls.ChatsAction.filter())
async def callback_chats_actions(
    callback: CallbackQuery,
    callback_data: calls.ChatsAction,
    state: FSMContext,
):
    action = callback_data.action
    value = callback_data.value

    if action == "noop":
        await callback.answer()
        return

    data = await state.get_data()
    ui_state = _normalize_ui_state(data.get("chats_ui"))
    force_reload = False

    if action == "open":
        pass
    elif action == "page":
        try:
            ui_state["page"] = max(0, int(value or 0))
        except Exception:
            ui_state["page"] = 0
    elif action == "refresh":
        ui_state["page"] = 0
        force_reload = True
    else:
        await callback.answer("Unknown action", show_alert=False)
        return

    await state.update_data(chats_ui=ui_state)
    await show_chats_menu(
        message=callback.message,
        state=state,
        callback=callback,
        force_reload=force_reload,
    )
