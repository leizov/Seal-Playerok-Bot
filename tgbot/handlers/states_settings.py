import re
import asyncio
import json
from logging import getLogger
from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from settings import Settings as sett
from core.utils import restart

from .. import templates as templ
from .. import states
from .. import callback_datas as calls
from ..cookie_guide import build_cookie_parse_error_text
from ..helpful import throw_float_message

logger = getLogger("seal.settings")


router = Router()

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


def is_eng_str(str: str):
    pattern = r'^[a-zA-Z0-9!@#$%^&*()_+\-=\[\]{};:\'",.<>/?\\|`~ ]+$'
    return bool(re.match(pattern, str))


def normalize_proxy_format(proxy: str) -> str:
    """
    Нормализует прокси в формат user:password@ip:port.
    Поддерживаемые форматы:
    - ip:port → ip:port (без изменений)
    - user:password@ip:port → user:password@ip:port (без изменений)
    - ip:port:user:password в†’ user:password@ip:port
    """
    ip_pattern = r'(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)'
    # Формат: ip:port:user:password
    pattern_new_format = re.compile(
        rf'^({ip_pattern}\.{ip_pattern}\.{ip_pattern}\.{ip_pattern}):(\d+):([^:]+):([^:]+)$'
    )
    match = pattern_new_format.match(proxy)
    if match:
        ip = match.group(1)
        port = match.group(2)
        user = match.group(3)
        password = match.group(4)
        return f"{user}:{password}@{ip}:{port}"
    return proxy


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
            for key, value in _parse_cookie_header(node).items():
                _add_cookie(key, value)
            return

        if isinstance(node, dict):
            name = node.get("name")
            if name is not None and "value" in node:
                _add_cookie(name, node.get("value"))

            for container_key in ("cookies", "cookie", "items", "data", "result"):
                if container_key in node:
                    _walk(node.get(container_key))

            for key, value in node.items():
                if isinstance(value, (dict, list, tuple, set)):
                    continue
                key_l = str(key or "").strip().lower()
                if key_l in _SET_COOKIE_ATTRS or key_l in {"name", "value"}:
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
        raw_value = message.text.strip()
        if len(raw_value) <= 3 or len(raw_value) >= 20000:
            return {}, "❌ Слишком короткое или длинное значение"
        parsed = _parse_cookie_header(raw_value)
        if parsed:
            return parsed, ""
        return {}, ""

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
        payload = json.loads(payload_text)
        cookie_map = _parse_cookie_json_payload(payload)
    except Exception:
        cookie_map = {}

    if not cookie_map:
        cookie_map = _parse_cookie_header(payload_text)

    if cookie_map:
        return cookie_map, ""
    return {}, "В .json файле не найдено валидных cookies."


async def _handle_waiting_for_token_input(message: types.Message, state: FSMContext):
    raw_value = message.text.strip() if message.text else ""
    cookie_map, parse_error = await _extract_cookie_map_from_message(message)
    if parse_error and not raw_value:
        raise Exception(build_cookie_parse_error_text(parse_error))

    config = sett.get("config")
    api_cfg = config["playerok"]["api"]

    if cookie_map:
        cookie_header = _serialize_cookie_map(cookie_map)
        if not cookie_header:
            raise Exception("❌ Не удалось извлечь валидные cookies из данных.")

        api_cfg["cookies"] = cookie_header
        token_from_cookie = str(cookie_map.get("token") or "").strip()
        token_hint = "🔐 Токен взят из cookies и синхронизирован."
        if token_from_cookie:
            api_cfg["token"] = token_from_cookie
        else:
            token_hint = "ℹ️ В cookies не найден token, оставил текущее значение token из конфига."

        sett.set("config", config)
        logger.info("🍪 Cookies изменены через Telegram")

        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_account_float_text(
                "✅ <b>Cookies</b> успешно обновлены!\n\n"
                f"{token_hint}\n\n"
                "⏳ Применяется автоматически через 3 секунды..."
            ),
            reply_markup=templ.back_kb(calls.SettingsNavigation(to="account").pack())
        )
        return

    if len(raw_value) <= 3 or len(raw_value) >= 20000:
        raise Exception("❌ Слишком короткое или длинное значение")

    api_cfg["token"] = raw_value
    sett.set("config", config)
    logger.info("🎫 Токен изменён через Telegram")

    await throw_float_message(
        state=state,
        message=message,
        text=templ.settings_account_float_text(
            "✅ <b>Токен</b> успешно изменён!\n\n"
            "ℹ️ Можно отправлять cookies текстом, .txt файлом или .json файлом.\n\n"
            "⏳ Применяется автоматически через 3 секунды..."
        ),
        reply_markup=templ.back_kb(calls.SettingsNavigation(to="account").pack())
    )


@router.message(states.SettingsStates.waiting_for_token, F.text)
@router.message(states.SettingsStates.waiting_for_token, F.document)
async def handler_waiting_for_token(message: types.Message, state: FSMContext):
    try:
        await state.set_state(None)
        await _handle_waiting_for_token_input(message, state)
    except Exception as e:
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_account_float_text(e),
            reply_markup=templ.back_kb(calls.SettingsNavigation(to="account").pack())
        )


@router.message(states.SettingsStates.waiting_for_user_agent, F.text)
async def handler_waiting_for_user_agent(message: types.Message, state: FSMContext):
    try:
        await state.set_state(None)
        if len(message.text.strip()) <= 3:
            raise Exception("❌ Слишком короткое значение")

        config = sett.get("config")
        config["playerok"]["api"]["user_agent"] = message.text.strip()
        sett.set("config", config)
        
        logger.info(f"🎩 User-Agent изменён через Telegram")

        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_account_float_text(
                f"✅ <b>User-Agent</b> успешно изменён!\n\n"
                f"⏳ Применяется автоматически через 3 секунды..."
            ),
            reply_markup=templ.back_kb(calls.SettingsNavigation(to="account").pack())
        )
    except Exception as e:
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_account_float_text(e), 
            reply_markup=templ.back_kb(calls.SettingsNavigation(to="account").pack())
        )


# Старый обработчик изменения прокси - теперь используется новая система управления прокси
# См. tgbot/callback_handlers/proxy_management.py
# @router.message(states.SettingsStates.waiting_for_proxy, F.text)
# async def handler_waiting_for_proxy(message: types.Message, state: FSMContext):
#     try:
#         await state.set_state(None)
#         if len(message.text.strip()) <= 3:
#             raise Exception("❌ Слишком короткое значение")
#         if not is_eng_str(message.text.strip()):
#             raise Exception("❌ Некорректный прокси")
#
#         # Нормализуем прокси (конвертируем ip:port:user:password в user:password@ip:port)
#         proxy_input = message.text.strip()
#         normalized_proxy = normalize_proxy_format(proxy_input)
#
#         config = sett.get("config")
#         config["playerok"]["api"]["proxy"] = normalized_proxy
#         sett.set("config", config)
#
#         await throw_float_message(
#             state=state,
#             message=message,
#             text=templ.settings_account_float_text(f"✅ <b>Прокси</b> был успешно изменён\n\n<i>Формат: {normalized_proxy}</i>"),
#             reply_markup=templ.back_kb(calls.SettingsNavigation(to="account").pack())
#         )
#     except Exception as e:
#         await throw_float_message(
#             state=state,
#             message=message,
#             text=templ.settings_account_float_text(e), 
#             reply_markup=templ.back_kb(calls.SettingsNavigation(to="account").pack())
#         )


@router.message(states.SettingsStates.waiting_for_requests_timeout, F.text)
async def handler_waiting_for_requests_timeout(message: types.Message, state: FSMContext):
    try:
        await state.set_state(None)
        if not message.text.strip().isdigit():
            raise Exception("❌ Вы должны ввести числовое значение")       
        if int(message.text.strip()) < 0:
            raise Exception("❌ Слишком низкое значение")

        config = sett.get("config")
        config["playerok"]["api"]["requests_timeout"] = int(message.text.strip())
        sett.set("config", config)

        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_developer_float_text(f"✅ <b>Таймаут запросов</b> был успешно изменён на <b>{message.text.strip()}</b>"),
            reply_markup=templ.back_kb(calls.SettingsNavigation(to="developer").pack())
        )
    except Exception as e:
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_developer_float_text(e), 
            reply_markup=templ.back_kb(calls.SettingsNavigation(to="developer").pack())
        )


@router.message(states.SettingsStates.waiting_for_listener_requests_delay, F.text)
async def handler_waiting_for_listener_requests_delay(message: types.Message, state: FSMContext):
    try:
        await state.set_state(None)
        if not message.text.strip().isdigit():
            raise Exception("❌ Вы должны ввести числовое значение")
        if int(message.text.strip()) < 0:
            raise Exception("❌ Слишком низкое значение")

        config = sett.get("config")
        config["playerok"]["api"]["listener_requests_delay"] = int(message.text.strip())
        sett.set("config", config)

        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_developer_float_text(f"✅ <b>Периодичность запросов</b> была успешна изменена на <b>{message.text.strip()}</b>"),
            reply_markup=templ.back_kb(calls.SettingsNavigation(to="developer").pack())
        )
    except Exception as e:
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_developer_float_text(e), 
            reply_markup=templ.back_kb(calls.SettingsNavigation(to="developer").pack())
        )


@router.message(states.SettingsStates.waiting_for_tg_logging_chat_id, F.text)
async def handler_waiting_for_tg_logging_chat_id(message: types.Message, state: FSMContext):
    try:
        await state.set_state(None) 
        if len(message.text.strip()) < 0:
            raise Exception("❌ Слишком низкое значение")
        
        if message.text.strip().isdigit(): 
            chat_id = "-100" + str(message.text.strip()).replace("-100", "")
        else: 
            chat_id = "@" + str(message.text.strip()).replace("@", "")
        
        config = sett.get("config")
        config["playerok"]["tg_logging"]["chat_id"] = chat_id
        sett.set("config", config)

        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_notifications_float_text(f"✅ <b>ID чата для уведомлений</b> было успешно изменено на <b>{chat_id}</b>"),
            reply_markup=templ.back_kb(calls.SettingsNavigation(to="notifications").pack())
        )
    except Exception as e:
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_notifications_float_text(e), 
            reply_markup=templ.back_kb(calls.SettingsNavigation(to="notifications").pack())
        )
            

@router.message(states.SettingsStates.waiting_for_watermark_value, F.text)
async def handler_waiting_for_watermark_value(message: types.Message, state: FSMContext):
    try:
        await state.set_state(None)
        data = await state.get_data()
        if len(message.text.strip()) <= 0 or len(message.text.strip()) >= 150:
            raise Exception("❌ Слишком короткое или длинное значение")

        config = sett.get("config")
        config["playerok"]["watermark"]["value"] = message.text.strip()
        sett.set("config", config)
        
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_watermark_float_text(f"✅ <b>Водяной знак сообщений</b> был успешно изменён на <b>{message.text.strip()}</b>"),
            reply_markup=templ.back_kb(calls.SettingsNavigation(to="watermark").pack())
        )
    except Exception as e:
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_watermark_float_text(e), 
            reply_markup=templ.back_kb(calls.SettingsNavigation(to="watermark").pack())
        )


# в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
# ОБРАБОТЧИК ПЕРЕЗАПУСКА БОТА
# в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ

@router.callback_query(F.data == "restart_bot_confirm")
async def callback_restart_bot(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик подтверждения перезапуска бота."""
    try:
        logger.info(f"🔄 Перезапуск бота инициирован пользователем {callback.from_user.id}")
        
        await callback.message.edit_text(
            "🔄 <b>Перезапуск бота...</b>\n\n"
            "⏳ Бот перезапускается для применения новых настроек.\n"
            "Это займёт несколько секунд.",
            parse_mode="HTML"
        )
        await callback.answer("🔄 Перезапуск бота...")
        
        # Небольшая задержка для отправки сообщения
        await asyncio.sleep(1)
        
        # Перезапускаем бота
        restart()
        
    except Exception as e:
        logger.error(f"Ошибка при перезапуске бота: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

