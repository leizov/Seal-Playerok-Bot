import re
from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext

from settings import Settings as sett

from .. import templates as templ
from .. import states
from .. import callback_datas as calls
from ..helpful import throw_float_message


router = Router()


def is_eng_str(str: str):
    pattern = r'^[a-zA-Z0-9!@#$%^&*()_+\-=\[\]{};:\'",.<>/?\\|`~ ]+$'
    return bool(re.match(pattern, str))


def normalize_proxy_format(proxy: str) -> str:
    """
    Нормализует прокси в формат user:password@ip:port.
    Поддерживаемые форматы:
    - ip:port → ip:port (без изменений)
    - user:password@ip:port → user:password@ip:port (без изменений)
    - ip:port:user:password → user:password@ip:port
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


@router.message(states.SettingsStates.waiting_for_token, F.text)
async def handler_waiting_for_token(message: types.Message, state: FSMContext):
    try:
        await state.set_state(None)
        if len(message.text.strip()) <= 3 or len(message.text.strip()) >= 500:
            raise Exception("❌ Слишком короткое или длинное значение")

        config = sett.get("config")
        config["playerok"]["api"]["token"] = message.text.strip()
        sett.set("config", config)

        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_account_float_text(f"✅ <b>Токен</b> был успешно изменён на <b>{message.text.strip()}</b>"),
            reply_markup=templ.back_kb(calls.SettingsNavigation(to="account").pack())
        )
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

        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_account_float_text(f"✅ <b>user_agent</b> был успешно изменён на <b>{message.text.strip()}</b>"),
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