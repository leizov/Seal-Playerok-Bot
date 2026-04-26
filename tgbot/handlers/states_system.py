from __future__ import annotations

import asyncio
import html
import json
import logging
import random
from datetime import datetime

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from core.proxy_utils import normalize_proxy, validate_proxy
from core.security import hash_password, is_password_hashed, verify_password
from settings import Settings as sett

from .. import states
from .. import templates as templ
from ..cookie_guide import build_cookie_collection_instruction, build_cookie_parse_error_text
from ..helpful import throw_float_message


router = Router()
logger = logging.getLogger("seal.auth")


ONBOARDING_CANCEL_CB = "playerok_onboarding_cancel"
ONBOARDING_ENTER_PROXY_CB = "playerok_onboarding_enter_proxy"
ONBOARDING_SKIP_PROXY_CB = "playerok_onboarding_skip_proxy"
ONBOARDING_ENTER_UA_CB = "playerok_onboarding_enter_ua"
ONBOARDING_SKIP_UA_CB = "playerok_onboarding_skip_ua"

RECOVERY_OPEN_CB = "playerok_recovery_open"
RECOVERY_CANCEL_CB = "playerok_recovery_cancel"
RECOVERY_ENTER_UA_CB = "playerok_recovery_enter_ua"
RECOVERY_SKIP_UA_CB = "playerok_recovery_skip_ua"

_SET_COOKIE_ATTRS = {
    "path",
    "domain",
    "expires",
    "max-age",
    "secure",
    "httponly",
    "samesite",
    "priority",
    "partitioned",
}


def _onboarding_required(config: dict | None) -> bool:
    cfg = config or {}
    api_cfg = cfg.get("playerok", {}).get("api", {})
    cookies = str(api_cfg.get("cookies") or "").strip()
    user_agent = str(api_cfg.get("user_agent") or "").strip()
    return not cookies or not user_agent


def _is_valid_user_agent(user_agent: str) -> bool:
    value = str(user_agent or "").strip()
    return 10 <= len(value) <= 512


def _pick_random_user_agent() -> str:
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    ]
    return random.choice(user_agents)


def _parse_cookie_header(cookie_header: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    raw = str(cookie_header or "").strip()
    if not raw:
        return parsed

    if raw.lower().startswith("cookie:"):
        raw = raw.split(":", 1)[1].strip()

    for separator in ("\n", "\r", "\t"):
        raw = raw.replace(separator, ";")

    for part in raw.split(";"):
        chunk = part.strip()
        if not chunk or "=" not in chunk:
            continue
        key, value = chunk.split("=", 1)
        key = key.strip()
        if not key:
            continue
        if key.lower() in _SET_COOKIE_ATTRS:
            continue
        parsed[key] = value.strip()
    return parsed


def _parse_cookie_json_payload(payload: object) -> dict[str, str]:
    parsed: dict[str, str] = {}

    def _add_cookie(name: object, value: object) -> None:
        key = str(name or "").strip()
        if not key:
            return
        if key.lower() in _SET_COOKIE_ATTRS:
            return
        parsed[key] = str(value or "").strip()

    def _walk(node: object) -> None:
        if node is None:
            return

        if isinstance(node, str):
            header_map = _parse_cookie_header(node)
            for key, value in header_map.items():
                _add_cookie(key, value)
            return

        if isinstance(node, dict):
            name = node.get("name")
            if name is not None and "value" in node:
                _add_cookie(name, node.get("value"))

            for container_key in ("cookies", "cookie", "items", "data", "result"):
                if container_key in node:
                    _walk(node.get(container_key))

            # Fallback: плоский map вида {"token":"...", "__ddg5_":"..."}.
            for key, value in node.items():
                if isinstance(value, (dict, list, tuple, set)):
                    continue
                if str(key or "").strip().lower() in _SET_COOKIE_ATTRS:
                    continue
                if str(key or "").strip().lower() in {"name", "value"}:
                    continue
                _add_cookie(key, value)

            for value in node.values():
                if isinstance(value, (dict, list, tuple)):
                    _walk(value)
            return

        if isinstance(node, (list, tuple, set)):
            for item in node:
                _walk(item)

    _walk(payload)
    return parsed


def _decode_file_bytes(raw_bytes: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            return raw_bytes.decode(encoding)
        except Exception:
            continue
    return raw_bytes.decode("utf-8", errors="replace")


async def _extract_cookie_map_from_message(message: types.Message) -> tuple[dict[str, str], str]:
    if message.text:
        cookie_map = _parse_cookie_header(message.text)
        if cookie_map:
            return cookie_map, ""
        return {}, "Не удалось распознать cookies из текста."

    document = message.document
    if document is None:
        return {}, "Отправьте cookies текстом, .txt или .json файлом."

    file_name = str(document.file_name or "").strip()
    file_name_l = file_name.lower()
    is_txt_file = bool(file_name_l) and file_name_l.endswith(".txt")
    is_json_file = bool(file_name_l) and file_name_l.endswith(".json")
    if file_name and not (is_json_file or is_txt_file):
        return {}, "Поддерживаются только .txt и .json файлы с cookies."

    file_size = int(document.file_size or 0)
    if file_size > 2 * 1024 * 1024:
        return {}, "Файл с cookies слишком большой (максимум 2 МБ)."

    try:
        file_info = await message.bot.get_file(document.file_id)
        downloaded_file = await message.bot.download_file(file_info.file_path)
        if isinstance(downloaded_file, bytes):
            raw_bytes = downloaded_file
        else:
            raw_bytes = downloaded_file.read()
    except Exception:
        return {}, "Не удалось скачать файл с cookies."

    try:
        payload_text = _decode_file_bytes(raw_bytes)
    except Exception:
        return {}, "Не удалось прочитать файл с cookies."

    if is_txt_file:
        cookie_map = _parse_cookie_header(payload_text)
        if cookie_map:
            return cookie_map, ""
        return {}, "В .txt файле не найдено валидных cookies."

    cookie_map: dict[str, str] = {}
    try:
        parsed_payload = json.loads(payload_text)
        cookie_map = _parse_cookie_json_payload(parsed_payload)
    except Exception:
        cookie_map = {}

    if not cookie_map:
        # Fallback: иногда в .json отправляют просто header-string.
        cookie_map = _parse_cookie_header(payload_text)

    if cookie_map:
        return cookie_map, ""

    return {}, "В .json файле не найдено валидных cookies."


def _serialize_cookie_map(cookie_map: dict[str, str]) -> str:
    if not cookie_map:
        return ""
    ordered_keys: list[str] = []
    if "token" in cookie_map:
        ordered_keys.append("token")
    if "auid" in cookie_map and "auid" not in ordered_keys:
        ordered_keys.append("auid")
    for key in sorted(cookie_map.keys()):
        if key not in ordered_keys:
            ordered_keys.append(key)
    return "; ".join(f"{key}={cookie_map[key]}" for key in ordered_keys)


def _extract_token_for_probe(cookie_map: dict[str, str], fallback_token: str) -> str:
    token_from_cookie = str(cookie_map.get("token") or "").strip()
    if token_from_cookie:
        return token_from_cookie
    return str(fallback_token or "").strip()


def _onboarding_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data=ONBOARDING_CANCEL_CB)],
        ]
    )


def _onboarding_proxy_choice_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🌐 Указать прокси", callback_data=ONBOARDING_ENTER_PROXY_CB)],
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data=ONBOARDING_SKIP_PROXY_CB)],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=ONBOARDING_CANCEL_CB)],
        ]
    )


def _onboarding_ua_choice_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎩 Ввести User-Agent", callback_data=ONBOARDING_ENTER_UA_CB)],
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data=ONBOARDING_SKIP_UA_CB)],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=ONBOARDING_CANCEL_CB)],
        ]
    )


def _recovery_start_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📥 Отправить cookies", callback_data=RECOVERY_OPEN_CB)],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=RECOVERY_CANCEL_CB)],
        ]
    )


def _recovery_ua_choice_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎩 Ввести User-Agent", callback_data=RECOVERY_ENTER_UA_CB)],
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data=RECOVERY_SKIP_UA_CB)],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=RECOVERY_CANCEL_CB)],
        ]
    )


def _recovery_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data=RECOVERY_CANCEL_CB)],
        ]
    )


def _recovery_instruction_text() -> str:
    return build_cookie_collection_instruction("🛡 <b>Нужны новые cookies от аккаунта Playerok</b>")


def _onboarding_cookies_instruction_text() -> str:
    return (
        build_cookie_collection_instruction(
            "🧭 <b>Пошаговый мастер активации Playerok</b>\n\n"
            "Шаг 1/3: отправьте <b>cookies</b>."
        )
        + "\n\nПосле cookies я предложу шаг с User-Agent и проверю авторизацию тестовым запросом."
    )


async def _sync_startup_status_for_user(user_id: int) -> None:
    from ..telegrambot import get_telegram_bot

    tg_bot = get_telegram_bot()
    if tg_bot is None:
        return
    try:
        await tg_bot.ensure_startup_status_for_user(user_id)
    except Exception as e:
        logger.debug(f"Не удалось обновить startup-статус для user_id={user_id}: {e}")


def _set_recovery_dialog_active(user_id: int, active: bool) -> None:
    from ..telegrambot import get_telegram_bot

    tg_bot = get_telegram_bot()
    if tg_bot is None:
        return
    try:
        tg_bot.set_playerok_recovery_dialog_active(user_id=user_id, active=active)
    except Exception as e:
        logger.debug(f"Не удалось обновить флаг recovery-диалога user_id={user_id}: {e}")


async def _attempt_playerok_reconnect() -> tuple[bool, str]:
    from plbot.playerokbot import get_playerok_bot

    pl_bot = get_playerok_bot()
    if pl_bot is None:
        return False, "Экземпляр Playerok бота ещё не готов. Повторите попытку через несколько секунд."

    try:
        reconnect_result = await asyncio.to_thread(pl_bot.reconnect)
        if isinstance(reconnect_result, tuple) and len(reconnect_result) == 2:
            return bool(reconnect_result[0]), str(reconnect_result[1] or "")
        return False, "Неожиданный ответ от процедуры переподключения."
    except Exception as e:
        return False, f"Ошибка переподключения: {e}"


async def _probe_playerok_credentials(
        *,
        cookie_header: str,
        cookie_map: dict[str, str],
        user_agent: str,
        proxy: str,
        fallback_token: str,
        requests_timeout: int,
) -> tuple[bool, str]:
    from playerokapi.account import Account

    token_for_probe = _extract_token_for_probe(cookie_map, fallback_token)
    if not token_for_probe:
        return False, "В cookies не найден token, а в текущем конфиге token пустой."

    def _worker() -> tuple[bool, str]:
        account = Account(
            token=token_for_probe,
            cookies=cookie_header,
            user_agent=user_agent,
            requests_timeout=requests_timeout,
            proxy=proxy or None,
        ).get()
        username = str(getattr(account, "username", "") or "").strip()
        if username:
            return True, f"Авторизация подтверждена: @{username}"
        return True, "Авторизация подтверждена тестовым запросом."

    try:
        return await asyncio.to_thread(_worker)
    except Exception as e:
        return False, str(e)


def _build_probe_error_text(reason: str) -> str:
    safe_reason = html.escape(reason or "неизвестно")
    return (
        "❌ <b>Cookies не прошли тестовую проверку</b>\n\n"
        "Конфиг не изменён. Отправьте новые cookies.\n\n"
        f"Техническая причина: <code>{safe_reason}</code>\n\n"
        f"{build_cookie_collection_instruction()}"
    )


async def _start_playerok_onboarding(message: types.Message, state: FSMContext) -> None:
    _set_recovery_dialog_active(message.from_user.id, True)
    await state.set_state(states.SystemStates.waiting_for_playerok_onboarding_cookies)
    await state.set_data({})
    await throw_float_message(
        state=state,
        message=message,
        text=_onboarding_cookies_instruction_text(),
        reply_markup=_onboarding_cancel_kb(),
    )


async def _finalize_onboarding(message: types.Message, state: FSMContext, actor_user_id: int) -> None:
    await state.set_state(None)
    await throw_float_message(
        state=state,
        message=message,
        text="⏳ Проверяю авторизацию в Playerok с новыми параметрами...",
        reply_markup=templ.destroy_kb(),
    )

    success, reconnect_message = await _attempt_playerok_reconnect()
    if success:
        _set_recovery_dialog_active(actor_user_id, False)
        await _sync_startup_status_for_user(actor_user_id)
        await throw_float_message(
            state=state,
            message=message,
            text=templ.menu_text(),
            reply_markup=templ.menu_kb(page=0),
        )
        return

    fail_text = (
        "⚠️ <b>Активация Playerok пока не удалась</b>\n\n"
        f"{html.escape(reconnect_message or 'Неизвестная ошибка')}\n\n"
        "Можно сразу запустить recovery через cookies:"
    )
    await throw_float_message(
        state=state,
        message=message,
        text=fail_text,
        reply_markup=_recovery_start_kb(),
    )


async def _run_onboarding_probe_and_continue(
        message: types.Message,
        state: FSMContext,
        chosen_user_agent: str | None,
        prefer_random_user_agent: bool = False,
) -> None:
    state_data = await state.get_data()
    cookie_header = str(state_data.get("onboarding_cookie_header") or "").strip()
    if not cookie_header:
        await state.set_state(states.SystemStates.waiting_for_playerok_onboarding_cookies)
        await throw_float_message(
            state=state,
            message=message,
            text=build_cookie_collection_instruction("⚠️ Не найдены cookies для проверки. Отправьте их снова."),
            reply_markup=_onboarding_cancel_kb(),
        )
        return

    config = sett.get("config")
    api_cfg = config["playerok"]["api"]
    cookie_map = _parse_cookie_header(cookie_header)
    fallback_token = str(api_cfg.get("token") or "").strip()

    candidate_user_agent = str(chosen_user_agent or "").strip()
    configured_user_agent = str(api_cfg.get("user_agent") or "").strip()
    if prefer_random_user_agent:
        candidate_user_agent = _pick_random_user_agent()
    elif not candidate_user_agent:
        if _is_valid_user_agent(configured_user_agent):
            candidate_user_agent = configured_user_agent
        else:
            candidate_user_agent = _pick_random_user_agent()

    if not _is_valid_user_agent(candidate_user_agent):
        candidate_user_agent = _pick_random_user_agent()

    requests_timeout = int(api_cfg.get("requests_timeout") or 10)
    proxy_value = ""

    await throw_float_message(
        state=state,
        message=message,
        text="⏳ Проверяю cookies тестовым запросом...",
        reply_markup=templ.destroy_kb(),
    )

    probe_ok, probe_message = await _probe_playerok_credentials(
        cookie_header=cookie_header,
        cookie_map=cookie_map,
        user_agent=candidate_user_agent,
        proxy=proxy_value,
        fallback_token=fallback_token,
        requests_timeout=requests_timeout,
    )
    if not probe_ok:
        await state.set_state(states.SystemStates.waiting_for_playerok_onboarding_cookies)
        await state.set_data({})
        await throw_float_message(
            state=state,
            message=message,
            text=_build_probe_error_text(probe_message),
            reply_markup=_onboarding_cancel_kb(),
        )
        return

    api_cfg["cookies"] = cookie_header
    token_from_cookie = str(cookie_map.get("token") or "").strip()
    if token_from_cookie:
        api_cfg["token"] = token_from_cookie
    api_cfg["user_agent"] = candidate_user_agent
    sett.set("config", config)

    await state.set_data({})
    await state.set_state(states.SystemStates.waiting_for_playerok_onboarding_proxy)
    await throw_float_message(
        state=state,
        message=message,
        text=(
            f"✅ <b>{html.escape(probe_message)}</b>\n\n"
            "Шаг 3/3: хотите добавить прокси для Playerok?\n"
            "Этот шаг можно пропустить."
        ),
        reply_markup=_onboarding_proxy_choice_kb(),
    )


async def _run_recovery_auth_attempt(
        message: types.Message,
        state: FSMContext,
        chosen_user_agent: str | None,
        actor_user_id: int,
) -> None:
    state_data = await state.get_data()
    cookie_header = str(state_data.get("recovery_cookie_header") or "").strip()
    if not cookie_header:
        await state.set_state(states.SystemStates.waiting_for_playerok_recovery_cookies)
        await throw_float_message(
            state=state,
            message=message,
            text=build_cookie_collection_instruction("⚠️ Не найдены cookies для проверки. Отправьте их снова."),
            reply_markup=_recovery_cancel_kb(),
        )
        return

    config = sett.get("config")
    api_cfg = config["playerok"]["api"]
    cookie_map = _parse_cookie_header(cookie_header)
    fallback_token = str(api_cfg.get("token") or "").strip()

    candidate_user_agent = str(chosen_user_agent or "").strip()
    if not candidate_user_agent:
        configured_user_agent = str(api_cfg.get("user_agent") or "").strip()
        if _is_valid_user_agent(configured_user_agent):
            candidate_user_agent = configured_user_agent
        else:
            candidate_user_agent = _pick_random_user_agent()

    if not _is_valid_user_agent(candidate_user_agent):
        candidate_user_agent = _pick_random_user_agent()

    requests_timeout = int(api_cfg.get("requests_timeout") or 10)
    proxy_value = str(api_cfg.get("proxy") or "").strip()

    await throw_float_message(
        state=state,
        message=message,
        text="⏳ Проверяю авторизацию с новыми cookies...",
        reply_markup=templ.destroy_kb(),
    )

    probe_ok, probe_message = await _probe_playerok_credentials(
        cookie_header=cookie_header,
        cookie_map=cookie_map,
        user_agent=candidate_user_agent,
        proxy=proxy_value,
        fallback_token=fallback_token,
        requests_timeout=requests_timeout,
    )
    if not probe_ok:
        await state.set_state(states.SystemStates.waiting_for_playerok_recovery_cookies)
        await throw_float_message(
            state=state,
            message=message,
            text=_build_probe_error_text(probe_message),
            reply_markup=_recovery_cancel_kb(),
        )
        return

    api_cfg["cookies"] = cookie_header
    token_from_cookie = str(cookie_map.get("token") or "").strip()
    if token_from_cookie:
        api_cfg["token"] = token_from_cookie
    api_cfg["user_agent"] = candidate_user_agent
    sett.set("config", config)

    await state.set_state(None)
    await throw_float_message(
        state=state,
        message=message,
        text="✅ Cookies валидны. Выполняю переподключение...",
        reply_markup=templ.destroy_kb(),
    )

    success, reconnect_message = await _attempt_playerok_reconnect()
    if success:
        _set_recovery_dialog_active(actor_user_id, False)
        await _sync_startup_status_for_user(actor_user_id)
        await throw_float_message(
            state=state,
            message=message,
            text=templ.menu_text(),
            reply_markup=templ.menu_kb(page=0),
        )
        return

    await state.set_state(states.SystemStates.waiting_for_playerok_recovery_cookies)
    fail_text = (
        "❌ <b>Переподключение пока не удалось</b>\n\n"
        f"{html.escape(reconnect_message or 'Неизвестная ошибка')}\n\n"
        f"{build_cookie_collection_instruction('Отправьте новые cookies ещё раз.')}"
    )
    await throw_float_message(
        state=state,
        message=message,
        text=fail_text,
        reply_markup=_recovery_cancel_kb(),
    )


async def notify_auth_event(user: types.User, event_type: str, success: bool):
    """
    Уведомляет всех пользователей о событии авторизации.

    :param user: пользователь, который пытается войти
    :param event_type: тип события (login/register)
    :param success: успешно ли
    """
    from ..telegrambot import get_telegram_bot

    tg_bot = get_telegram_bot()
    if not tg_bot:
        return

    config = sett.get("config")
    signed_users = config["telegram"]["bot"].get("signed_users", [])

    user_info = f"@{user.username}" if user.username else f"ID: {user.id}"
    user_full = f"{user.full_name} ({user_info})"
    time_str = datetime.now().strftime("%H:%M:%S")

    if success:
        if event_type == "register":
            text = (
                f"🆕 <b>Новая регистрация в боте!</b>\n\n"
                f"👤 <b>Пользователь:</b> {user_full}\n"
                f"🆔 <b>ID:</b> <code>{user.id}</code>\n"
                f"🕐 <b>Время:</b> {time_str}"
            )
        else:
            text = (
                f"🔓 <b>Авторизация в боте</b>\n\n"
                f"👤 <b>Пользователь:</b> {user_full}\n"
                f"🆔 <b>ID:</b> <code>{user.id}</code>\n"
                f"🕐 <b>Время:</b> {time_str}"
            )

        for uid in signed_users:
            if uid != user.id:
                try:
                    await tg_bot.bot.send_message(uid, text, parse_mode="HTML")
                except Exception as e:
                    logger.warning(f"Не удалось отправить уведомление пользователю {uid}: {e}")


@router.message(states.SystemStates.waiting_for_password, F.text)
async def handler_waiting_for_password(message: types.Message, state: FSMContext):
    try:
        await state.set_state(None)
        config = sett.get("config")
        stored_password = config["telegram"]["bot"]["password"]
        entered_password = message.text.strip()
        user = message.from_user

        user_info = f"@{user.username}" if user.username else f"ID: {user.id}"

        password_valid = False
        need_hash_migration = False
        if is_password_hashed(stored_password):
            password_valid = verify_password(entered_password, stored_password)
        else:
            password_valid = entered_password == stored_password
            need_hash_migration = password_valid

        if not password_valid:
            logger.warning(f"⚠️ Неудачная попытка входа: {user.full_name} ({user_info}) - ID: {user.id}")
            raise Exception("❌ Неверный ключ-пароль.")

        raw_signed_users = config["telegram"]["bot"].get("signed_users", [])
        normalized_signed_users: list[int] = []
        seen_signed_users: set[int] = set()
        if isinstance(raw_signed_users, list):
            for raw_uid in raw_signed_users:
                try:
                    uid = int(raw_uid)
                except Exception:
                    continue
                if uid in seen_signed_users:
                    continue
                seen_signed_users.add(uid)
                normalized_signed_users.append(uid)
        config["telegram"]["bot"]["signed_users"] = normalized_signed_users

        is_new_user = user.id not in seen_signed_users
        if is_new_user:
            config["telegram"]["bot"]["signed_users"].append(user.id)
            logger.info(f"✅ Новый пользователь зарегистрирован: {user.full_name} ({user_info}) - ID: {user.id}")
        else:
            logger.info(f"✅ Пользователь авторизован: {user.full_name} ({user_info}) - ID: {user.id}")

        if need_hash_migration:
            config["telegram"]["bot"]["password"] = hash_password(stored_password)

        sett.set("config", config)
        await notify_auth_event(user, "register" if is_new_user else "login", success=True)
        await _sync_startup_status_for_user(user.id)

        fresh_config = sett.get("config")
        if _onboarding_required(fresh_config):
            await _start_playerok_onboarding(message=message, state=state)
            return

        _set_recovery_dialog_active(user.id, False)

        await throw_float_message(
            state=state,
            message=message,
            text=templ.menu_text(),
            reply_markup=templ.menu_kb(page=0),
        )
    except Exception as e:
        await throw_float_message(
            state=state,
            message=message,
            text=templ.sign_text(e),
            reply_markup=templ.destroy_kb(),
        )


@router.callback_query(F.data == ONBOARDING_CANCEL_CB)
async def callback_onboarding_cancel(callback: types.CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    onboarding_ua_choice_states = {
        states.SystemStates.waiting_for_playerok_onboarding_choose_user_agent.state,
        states.SystemStates.waiting_for_playerok_onboarding_user_agent.state,
        states.SystemStates.waiting_for_playerok_onboarding_proxy.state,
    }
    if current_state in onboarding_ua_choice_states:
        await state.set_state(states.SystemStates.waiting_for_playerok_onboarding_choose_user_agent)
        _set_recovery_dialog_active(callback.from_user.id, True)
        await throw_float_message(
            state=state,
            message=callback.message,
            callback=callback,
            text=(
                "✅ Cookies получены.\n\n"
                "Шаг 2/3: хотите ввести User-Agent вручную?"
            ),
            reply_markup=_onboarding_ua_choice_kb(),
        )
        return

    await state.set_state(None)
    await state.set_data({})
    _set_recovery_dialog_active(callback.from_user.id, False)
    await throw_float_message(
        state=state,
        message=callback.message,
        callback=callback,
        text=templ.menu_text(),
        reply_markup=templ.menu_kb(page=0),
    )


async def _handle_onboarding_cookies_input(message: types.Message, state: FSMContext) -> None:
    cookie_map, parse_error = await _extract_cookie_map_from_message(message)
    cookie_header = _serialize_cookie_map(cookie_map)
    if not cookie_map or not cookie_header:
        safe_parse_error = html.escape(parse_error or "Проверьте формат данных и попробуйте снова.")
        await throw_float_message(
            state=state,
            message=message,
            text=build_cookie_parse_error_text(safe_parse_error),
            reply_markup=_onboarding_cancel_kb(),
        )
        return

    await state.update_data(
        onboarding_cookie_header=cookie_header,
    )
    await state.set_state(states.SystemStates.waiting_for_playerok_onboarding_choose_user_agent)
    await throw_float_message(
        state=state,
        message=message,
        text=(
            "✅ Cookies получены.\n\n"
            "Шаг 2/3: хотите ввести User-Agent вручную?"
        ),
        reply_markup=_onboarding_ua_choice_kb(),
    )


@router.message(states.SystemStates.waiting_for_playerok_onboarding_cookies, F.text)
async def handler_onboarding_cookies_text(message: types.Message, state: FSMContext):
    await _handle_onboarding_cookies_input(message, state)


@router.message(states.SystemStates.waiting_for_playerok_onboarding_cookies, F.document)
async def handler_onboarding_cookies_document(message: types.Message, state: FSMContext):
    await _handle_onboarding_cookies_input(message, state)


@router.callback_query(
    states.SystemStates.waiting_for_playerok_onboarding_choose_user_agent,
    F.data == ONBOARDING_ENTER_UA_CB,
)
async def callback_onboarding_enter_ua(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(states.SystemStates.waiting_for_playerok_onboarding_user_agent)
    await throw_float_message(
        state=state,
        message=callback.message,
        callback=callback,
        text="🎩 Отправьте User-Agent вашего браузера.",
        reply_markup=_onboarding_cancel_kb(),
    )


@router.callback_query(
    states.SystemStates.waiting_for_playerok_onboarding_choose_user_agent,
    F.data == ONBOARDING_SKIP_UA_CB,
)
async def callback_onboarding_skip_ua(callback: types.CallbackQuery, state: FSMContext):
    await throw_float_message(
        state=state,
        message=callback.message,
        callback=callback,
        text="⏭ Подставляю случайный User-Agent.",
        reply_markup=templ.destroy_kb(),
    )
    await _run_onboarding_probe_and_continue(
        message=callback.message,
        state=state,
        chosen_user_agent=None,
        prefer_random_user_agent=True,
    )


@router.message(states.SystemStates.waiting_for_playerok_onboarding_user_agent, F.text)
async def handler_onboarding_user_agent(message: types.Message, state: FSMContext):
    user_agent = message.text.strip()
    if not _is_valid_user_agent(user_agent):
        await throw_float_message(
            state=state,
            message=message,
            text="❌ Невалидный User-Agent. Отправьте корректное значение ещё раз.",
            reply_markup=_onboarding_cancel_kb(),
        )
        return

    await _run_onboarding_probe_and_continue(
        message=message,
        state=state,
        chosen_user_agent=user_agent,
    )


@router.callback_query(
    states.SystemStates.waiting_for_playerok_onboarding_proxy,
    F.data == ONBOARDING_ENTER_PROXY_CB,
)
async def callback_onboarding_enter_proxy(callback: types.CallbackQuery, state: FSMContext):
    await throw_float_message(
        state=state,
        message=callback.message,
        callback=callback,
        text=(
            "🌐 Отправьте прокси для Playerok.\n\n"
            "Поддерживаемые форматы:\n"
            "• <code>ip:port</code>\n"
            "• <code>user:pass@ip:port</code>\n"
            "• <code>socks5://user:pass@ip:port</code>\n\n"
            "Если хотите пропустить, отправьте <code>-</code>."
        ),
        reply_markup=_onboarding_cancel_kb(),
    )


@router.callback_query(
    states.SystemStates.waiting_for_playerok_onboarding_proxy,
    F.data == ONBOARDING_SKIP_PROXY_CB,
)
async def callback_onboarding_skip_proxy(callback: types.CallbackQuery, state: FSMContext):
    config = sett.get("config")
    config["playerok"]["api"]["proxy"] = ""
    sett.set("config", config)

    await throw_float_message(
        state=state,
        message=callback.message,
        callback=callback,
        text="⏭ Шаг с прокси пропущен. Прокси отключён.",
        reply_markup=templ.destroy_kb(),
    )
    await _finalize_onboarding(
        message=callback.message,
        state=state,
        actor_user_id=callback.from_user.id,
    )


@router.message(states.SystemStates.waiting_for_playerok_onboarding_proxy, F.text)
async def handler_onboarding_proxy(message: types.Message, state: FSMContext):
    proxy_value = message.text.strip()
    if not proxy_value or proxy_value in {"-", "skip", "пропустить", "Пропустить"}:
        config = sett.get("config")
        config["playerok"]["api"]["proxy"] = ""
        sett.set("config", config)
        await _finalize_onboarding(
            message=message,
            state=state,
            actor_user_id=message.from_user.id,
        )
        return

    try:
        validate_proxy(proxy_value)
        normalized_proxy = normalize_proxy(proxy_value)
    except Exception as e:
        await throw_float_message(
            state=state,
            message=message,
            text=f"❌ Некорректный прокси: {html.escape(str(e))}",
            reply_markup=_onboarding_cancel_kb(),
        )
        return

    config = sett.get("config")
    config["playerok"]["api"]["proxy"] = normalized_proxy
    sett.set("config", config)
    await _finalize_onboarding(
        message=message,
        state=state,
        actor_user_id=message.from_user.id,
    )


@router.callback_query(F.data == RECOVERY_OPEN_CB)
async def callback_recovery_open(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(states.SystemStates.waiting_for_playerok_recovery_cookies)
    await state.set_data({})
    _set_recovery_dialog_active(callback.from_user.id, True)
    await throw_float_message(
        state=state,
        message=callback.message,
        callback=callback,
        text=_recovery_instruction_text(),
        reply_markup=_recovery_cancel_kb(),
    )


@router.callback_query(F.data == RECOVERY_CANCEL_CB)
async def callback_recovery_cancel(callback: types.CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    recovery_ua_choice_states = {
        states.SystemStates.waiting_for_playerok_recovery_choose_user_agent.state,
        states.SystemStates.waiting_for_playerok_recovery_user_agent.state,
    }
    if current_state in recovery_ua_choice_states:
        await state.set_state(states.SystemStates.waiting_for_playerok_recovery_choose_user_agent)
        _set_recovery_dialog_active(callback.from_user.id, True)
        await throw_float_message(
            state=state,
            message=callback.message,
            callback=callback,
            text=(
                "✅ Cookies получены.\n\n"
                "Хотите ввести User-Agent перед повторной авторизацией?"
            ),
            reply_markup=_recovery_ua_choice_kb(),
        )
        return

    await state.set_state(None)
    await state.set_data({})
    _set_recovery_dialog_active(callback.from_user.id, False)
    await throw_float_message(
        state=state,
        message=callback.message,
        callback=callback,
        text=templ.menu_text(),
        reply_markup=templ.menu_kb(page=0),
    )


async def _handle_recovery_cookies_input(message: types.Message, state: FSMContext) -> None:
    cookie_map, parse_error = await _extract_cookie_map_from_message(message)
    if not cookie_map:
        safe_parse_error = html.escape(parse_error or "Проверьте формат данных и попробуйте снова.")
        await throw_float_message(
            state=state,
            message=message,
            text=build_cookie_parse_error_text(safe_parse_error),
            reply_markup=_recovery_cancel_kb(),
        )
        return

    cookie_header = _serialize_cookie_map(cookie_map)
    if not cookie_header:
        await throw_float_message(
            state=state,
            message=message,
            text="❌ После парсинга не осталось валидных cookies. Попробуйте снова.",
            reply_markup=_recovery_cancel_kb(),
        )
        return

    await state.update_data(
        recovery_cookie_header=cookie_header,
    )
    await state.set_state(states.SystemStates.waiting_for_playerok_recovery_choose_user_agent)
    await throw_float_message(
        state=state,
        message=message,
        text=(
            "✅ Cookies получены.\n\n"
            "Хотите ввести User-Agent перед повторной авторизацией?"
        ),
        reply_markup=_recovery_ua_choice_kb(),
    )


@router.message(states.SystemStates.waiting_for_playerok_recovery_cookies, F.text)
async def handler_recovery_cookies_text(message: types.Message, state: FSMContext):
    await _handle_recovery_cookies_input(message, state)


@router.message(states.SystemStates.waiting_for_playerok_recovery_cookies, F.document)
async def handler_recovery_cookies_document(message: types.Message, state: FSMContext):
    await _handle_recovery_cookies_input(message, state)


@router.callback_query(
    states.SystemStates.waiting_for_playerok_recovery_choose_user_agent,
    F.data == RECOVERY_ENTER_UA_CB,
)
async def callback_recovery_enter_ua(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(states.SystemStates.waiting_for_playerok_recovery_user_agent)
    await throw_float_message(
        state=state,
        message=callback.message,
        callback=callback,
        text="🎩 Отправьте новый User-Agent для Playerok.",
        reply_markup=_recovery_cancel_kb(),
    )


@router.callback_query(
    states.SystemStates.waiting_for_playerok_recovery_choose_user_agent,
    F.data == RECOVERY_SKIP_UA_CB,
)
async def callback_recovery_skip_ua(callback: types.CallbackQuery, state: FSMContext):
    await throw_float_message(
        state=state,
        message=callback.message,
        callback=callback,
        text="⏭ Использую текущий User-Agent, а если он пустой — подставлю случайный.",
        reply_markup=templ.destroy_kb(),
    )
    await _run_recovery_auth_attempt(
        message=callback.message,
        state=state,
        chosen_user_agent=None,
        actor_user_id=callback.from_user.id,
    )


@router.message(states.SystemStates.waiting_for_playerok_recovery_user_agent, F.text)
async def handler_recovery_user_agent(message: types.Message, state: FSMContext):
    user_agent = message.text.strip()
    if not _is_valid_user_agent(user_agent):
        await throw_float_message(
            state=state,
            message=message,
            text="❌ Невалидный User-Agent. Отправьте корректное значение ещё раз.",
            reply_markup=_recovery_cancel_kb(),
        )
        return

    await _run_recovery_auth_attempt(
        message=message,
        state=state,
        chosen_user_agent=user_agent,
        actor_user_id=message.from_user.id,
    )
