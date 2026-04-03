import html

from aiogram import F, Router
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from core.plugins import get_plugin_by_uuid, activate_plugin, deactivate_plugin
from plbot.auto_reminder import DEFAULT_MESSAGE_TEXT, LEGACY_DEFAULT_MESSAGE_TEXT
from settings import Settings as sett

from .. import templates as templ
from .. import callback_datas as calls
from .. import states as states
from ..helpful import throw_float_message
from .navigation import *
from ..callback_handlers.page import callback_plugin_page


router = Router()


def _ensure_auto_reminder_config(config: dict) -> dict:
    playerok = config.setdefault("playerok", {})
    auto_reminder = playerok.setdefault("auto_reminder", {})

    auto_reminder.setdefault("enabled", False)
    auto_reminder.setdefault("interval_hours", 24.0)
    auto_reminder.setdefault("max_reminders", 3)
    current_message = str(auto_reminder.get("message_text") or "").strip()
    if not current_message or current_message == LEGACY_DEFAULT_MESSAGE_TEXT:
        auto_reminder["message_text"] = DEFAULT_MESSAGE_TEXT

    return auto_reminder


@router.callback_query(F.data == "switch_auto_response_enabled")
async def callback_switch_auto_response_enabled(callback: CallbackQuery, state: FSMContext):
    config = sett.get("config")
    # Создаем поле если его нет
    if "auto_response_enabled" not in config["playerok"]:
        config["playerok"]["auto_response_enabled"] = True
    config["playerok"]["auto_response_enabled"] = not config["playerok"]["auto_response_enabled"]
    sett.set("config", config)
    return await callback_settings_navigation(callback, calls.SettingsNavigation(to="global_switches"), state)


@router.callback_query(F.data == "switch_auto_restore_items_enabled")
async def callback_switch_auto_restore_items_enabled(callback: CallbackQuery, state: FSMContext):
    config = sett.get("config")
    config["playerok"]["auto_restore_items"]["enabled"] = not config["playerok"]["auto_restore_items"]["enabled"]
    sett.set("config", config)
    # Проверяем откуда был вызван переключатель
    data = await state.get_data()
    from_menu = data.get("from_menu", "restore")
    return await callback_settings_navigation(callback, calls.SettingsNavigation(to=from_menu), state)

@router.callback_query(F.data == "switch_auto_restore_items_all")
async def callback_switch_auto_restore_items_all(callback: CallbackQuery, state: FSMContext):
    config = sett.get("config")
    config["playerok"]["auto_restore_items"]["all"] = not config["playerok"]["auto_restore_items"]["all"]
    sett.set("config", config)
    return await callback_settings_navigation(callback, calls.SettingsNavigation(to="restore"), state)


@router.callback_query(F.data == "switch_auto_raise_items_enabled")
async def callback_switch_auto_raise_items_enabled(callback: CallbackQuery, state: FSMContext):
    config = sett.get("config")
    config["playerok"]["auto_raise_items"]["enabled"] = not config["playerok"]["auto_raise_items"]["enabled"]
    sett.set("config", config)
    # Проверяем откуда был вызван переключатель
    data = await state.get_data()
    from_menu = data.get("from_menu", "raise")
    return await callback_settings_navigation(callback, calls.SettingsNavigation(to=from_menu), state)


@router.callback_query(F.data == "switch_auto_raise_items_all")
async def callback_switch_auto_raise_items_all(callback: CallbackQuery, state: FSMContext):
    config = sett.get("config")
    config["playerok"]["auto_raise_items"]["all"] = not config["playerok"]["auto_raise_items"]["all"]
    sett.set("config", config)
    return await callback_settings_navigation(callback, calls.SettingsNavigation(to="raise"), state)


@router.callback_query(F.data == "set_auto_raise_items_interval")
async def callback_set_auto_raise_items_interval(callback: CallbackQuery, state: FSMContext):
    config = sett.get("config")
    current_interval = config["playerok"]["auto_raise_items"]["interval_hours"]
    
    await state.set_state(states.RaiseItemsStates.waiting_for_raise_interval)
    
    await throw_float_message(
        state=state,
        message=callback.message,
        text=f"⏱ <b>Изменение интервала автоподнятия</b>\n\n"
             f"Текущий интервал: <b>{current_interval}</b> ч.\n\n"
             f"Введите новый интервал (в часах) ↓\n\n"
             f"💡 <i>Товары будут подниматься автоматически\n"
             f"через указанное количество часов после последнего поднятия.</i>",
        reply_markup=templ.back_kb(calls.SettingsNavigation(to="raise").pack())
    )


@router.callback_query(F.data == "switch_auto_reminder_enabled")
async def callback_switch_auto_reminder_enabled(callback: CallbackQuery, state: FSMContext):
    config = sett.get("config")
    auto_reminder = _ensure_auto_reminder_config(config)
    auto_reminder["enabled"] = not bool(auto_reminder.get("enabled", False))
    sett.set("config", config)
    return await callback_settings_navigation(callback, calls.SettingsNavigation(to="auto_reminder"), state)


@router.callback_query(F.data == "set_auto_reminder_interval")
async def callback_set_auto_reminder_interval(callback: CallbackQuery, state: FSMContext):
    config = sett.get("config")
    auto_reminder = _ensure_auto_reminder_config(config)
    current_interval = auto_reminder.get("interval_hours", 24.0)

    await state.set_state(states.AutoReminderStates.waiting_for_interval_hours)

    await throw_float_message(
        state=state,
        message=callback.message,
        text=(
            "⏱ <b>Изменение интервала авто-напоминаний</b>\n\n"
            f"Текущий интервал: <b>{float(current_interval):g}</b> ч.\n\n"
            "Введите новый интервал в часах ↓\n\n"
            "<i>Напоминание будет отправляться не чаще указанного интервала.</i>"
        ),
        reply_markup=templ.back_kb(calls.SettingsNavigation(to="auto_reminder").pack()),
    )


@router.callback_query(F.data == "set_auto_reminder_max_reminders")
async def callback_set_auto_reminder_max_reminders(callback: CallbackQuery, state: FSMContext):
    config = sett.get("config")
    auto_reminder = _ensure_auto_reminder_config(config)
    current_max = int(auto_reminder.get("max_reminders", 3))
    current_text = "♾ Без лимита" if current_max == 0 else str(current_max)

    await state.set_state(states.AutoReminderStates.waiting_for_max_reminders)

    await throw_float_message(
        state=state,
        message=callback.message,
        text=(
            "🔢 <b>Изменение лимита напоминаний</b>\n\n"
            f"Текущий лимит: <b>{current_text}</b>\n\n"
            "Введите новое значение:\n"
            "• <code>0</code> — без лимита\n"
            "• <code>1, 2, 3...</code> — ограничение по количеству напоминаний"
        ),
        reply_markup=templ.back_kb(calls.SettingsNavigation(to="auto_reminder").pack()),
    )


@router.callback_query(F.data == "set_auto_reminder_message_text")
async def callback_set_auto_reminder_message_text(callback: CallbackQuery, state: FSMContext):
    config = sett.get("config")
    auto_reminder = _ensure_auto_reminder_config(config)
    current_text = html.escape(str(auto_reminder.get("message_text") or ""))

    await state.set_state(states.AutoReminderStates.waiting_for_message_text)

    await throw_float_message(
        state=state,
        message=callback.message,
        text=(
            "✏️ <b>Изменение текста напоминания</b>\n\n"
            f"<b>Текущий текст:</b>\n<blockquote>{current_text or 'Не задан'}</blockquote>\n\n"
            "Доступные теги:\n"
            "• <code>{deal_link}</code>\n"
            "• <code>{buyer_name}</code>\n"
            "Введите новый текст напоминания ↓"
        ),
        reply_markup=templ.back_kb(calls.SettingsNavigation(to="auto_reminder").pack()),
    )


@router.callback_query(F.data == "switch_read_chat_enabled")
async def callback_switch_read_chat_enabled(callback: CallbackQuery, state: FSMContext):
    config = sett.get("config")
    config["playerok"]["read_chat"]["enabled"] = not config["playerok"]["read_chat"]["enabled"]
    sett.set("config", config)
    # Проверяем откуда был вызван переключатель
    data = await state.get_data()
    from_menu = data.get("from_menu", "other")
    return await callback_settings_navigation(callback, calls.SettingsNavigation(to=from_menu), state)


@router.callback_query(F.data == "switch_auto_complete_deals_enabled")
async def callback_switch_auto_complete_deals_enabled(callback: CallbackQuery, state: FSMContext):
    config = sett.get("config")
    config["playerok"]["auto_complete_deals"]["enabled"] = not config["playerok"]["auto_complete_deals"]["enabled"]
    sett.set("config", config)
    # Проверяем откуда был вызван переключатель
    data = await state.get_data()
    from_menu = data.get("from_menu", "other")
    return await callback_settings_navigation(callback, calls.SettingsNavigation(to=from_menu), state)


@router.callback_query(F.data == "switch_custom_commands_enabled")
async def callback_switch_custom_commands_enabled(callback: CallbackQuery, state: FSMContext):
    config = sett.get("config")
    config["playerok"]["custom_commands"]["enabled"] = not config["playerok"]["custom_commands"]["enabled"]
    sett.set("config", config)
    return await callback_settings_navigation(callback, calls.SettingsNavigation(to="global_switches"), state)


@router.callback_query(F.data == "switch_auto_deliveries_enabled")
async def callback_switch_auto_deliveries_enabled(callback: CallbackQuery, state: FSMContext):
    config = sett.get("config")
    config["playerok"]["auto_deliveries"]["enabled"] = not config["playerok"]["auto_deliveries"]["enabled"]
    sett.set("config", config)
    # Проверяем откуда был вызван переключатель
    data = await state.get_data()
    from_menu = data.get("from_menu", "other")
    return await callback_settings_navigation(callback, calls.SettingsNavigation(to=from_menu), state)


@router.callback_query(F.data == "switch_watermark_enabled")
async def callback_switch_watermark_enabled(callback: CallbackQuery, state: FSMContext):
    config = sett.get("config")
    config["playerok"]["watermark"]["enabled"] = not config["playerok"]["watermark"]["enabled"]
    sett.set("config", config)
    return await callback_settings_navigation(callback, calls.SettingsNavigation(to="watermark"), state)


@router.callback_query(F.data == "watermark_presets")
async def callback_watermark_presets(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        text=templ.watermark_presets_text(),
        reply_markup=templ.watermark_presets_kb(),
        parse_mode="HTML"
    )


@router.callback_query(calls.SetWatermark.filter())
async def callback_set_watermark(callback: CallbackQuery, callback_data: calls.SetWatermark, state: FSMContext):
    config = sett.get("config")
    config["playerok"]["watermark"]["value"] = callback_data.value
    sett.set("config", config)
    await callback.answer(f"✅ Водяной знак установлен: {callback_data.value}", show_alert=True)
    return await callback_settings_navigation(callback, calls.SettingsNavigation(to="watermark"), state)


@router.callback_query(F.data == "switch_password_auth_enabled")
async def callback_switch_password_auth_enabled(callback: CallbackQuery, state: FSMContext):
    config = sett.get("config")
    # Инициализируем настройку, если её нет
    if "password_auth_enabled" not in config["telegram"]["bot"]:
        config["telegram"]["bot"]["password_auth_enabled"] = True
    config["telegram"]["bot"]["password_auth_enabled"] = not config["telegram"]["bot"]["password_auth_enabled"]
    sett.set("config", config)
    return await callback_settings_navigation(callback, calls.SettingsNavigation(to="users"), state)


@router.callback_query(F.data == "switch_tg_logging_enabled")
async def callback_switch_tg_logging_enabled(callback: CallbackQuery, state: FSMContext):
    config = sett.get("config")
    config["playerok"]["tg_logging"]["enabled"] = not config["playerok"]["tg_logging"]["enabled"]
    sett.set("config", config)
    # Проверяем откуда был вызван переключатель
    data = await state.get_data()
    from_menu = data.get("from_menu", "notifications")
    return await callback_settings_navigation(callback, calls.SettingsNavigation(to=from_menu), state)


@router.callback_query(F.data == "switch_tg_logging_event_new_user_message")
async def callback_switch_tg_logging_event_new_user_message(callback: CallbackQuery, state: FSMContext):
    config = sett.get("config")
    config["playerok"]["tg_logging"]["events"]["new_user_message"] = not config["playerok"]["tg_logging"]["events"]["new_user_message"]
    sett.set("config", config)
    return await callback_settings_navigation(callback, calls.SettingsNavigation(to="notifications"), state)


@router.callback_query(F.data == "switch_tg_logging_event_new_system_message")
async def callback_switch_tg_logging_event_new_system_message(callback: CallbackQuery, state: FSMContext):
    config = sett.get("config")
    config["playerok"]["tg_logging"]["events"]["new_system_message"] = not config["playerok"]["tg_logging"]["events"]["new_system_message"]
    sett.set("config", config)
    return await callback_settings_navigation(callback, calls.SettingsNavigation(to="notifications"), state)


@router.callback_query(F.data == "switch_tg_logging_event_new_deal")
async def callback_switch_tg_logging_event_new_deal(callback: CallbackQuery, state: FSMContext):
    config = sett.get("config")
    config["playerok"]["tg_logging"]["events"]["new_deal"] = not config["playerok"]["tg_logging"]["events"]["new_deal"]
    sett.set("config", config)
    return await callback_settings_navigation(callback, calls.SettingsNavigation(to="notifications"), state)


@router.callback_query(F.data == "switch_tg_logging_event_new_review")
async def callback_switch_tg_logging_event_new_review(callback: CallbackQuery, state: FSMContext):
    config = sett.get("config")
    config["playerok"]["tg_logging"]["events"]["new_review"] = not config["playerok"]["tg_logging"]["events"]["new_review"]
    sett.set("config", config)
    return await callback_settings_navigation(callback, calls.SettingsNavigation(to="notifications"), state)


@router.callback_query(F.data == "switch_tg_logging_event_new_problem")
async def callback_switch_tg_logging_event_new_problem(callback: CallbackQuery, state: FSMContext):
    config = sett.get("config")
    config["playerok"]["tg_logging"]["events"]["new_problem"] = not config["playerok"]["tg_logging"]["events"]["new_problem"]
    sett.set("config", config)
    return await callback_settings_navigation(callback, calls.SettingsNavigation(to="notifications"), state)


@router.callback_query(F.data == "switch_tg_logging_event_deal_status_changed")
async def callback_switch_tg_logging_event_deal_status_changed(callback: CallbackQuery, state: FSMContext):
    config = sett.get("config")
    config["playerok"]["tg_logging"]["events"]["deal_status_changed"] = not config["playerok"]["tg_logging"]["events"]["deal_status_changed"]
    sett.set("config", config)
    return await callback_settings_navigation(callback, calls.SettingsNavigation(to="notifications"), state)


@router.callback_query(F.data == "switch_tg_logging_event_command_received")
async def callback_switch_tg_logging_event_command_received(callback: CallbackQuery, state: FSMContext):
    config = sett.get("config")
    if "command_received" not in config["playerok"]["tg_logging"]["events"]:
        config["playerok"]["tg_logging"]["events"]["command_received"] = True
    config["playerok"]["tg_logging"]["events"]["command_received"] = not config["playerok"]["tg_logging"]["events"]["command_received"]
    sett.set("config", config)
    return await callback_settings_navigation(callback, calls.SettingsNavigation(to="notifications"), state)


@router.callback_query(F.data == "switch_tg_logging_event_auto_delivery")
async def callback_switch_tg_logging_event_auto_delivery(callback: CallbackQuery, state: FSMContext):
    config = sett.get("config")
    if "auto_delivery" not in config["playerok"]["tg_logging"]["events"]:
        config["playerok"]["tg_logging"]["events"]["auto_delivery"] = True
    config["playerok"]["tg_logging"]["events"]["auto_delivery"] = not config["playerok"]["tg_logging"]["events"]["auto_delivery"]
    sett.set("config", config)
    return await callback_settings_navigation(callback, calls.SettingsNavigation(to="notifications"), state)


@router.callback_query(F.data == "switch_tg_logging_event_item_raised")
async def callback_switch_tg_logging_event_item_raised(callback: CallbackQuery, state: FSMContext):
    config = sett.get("config")
    if "item_raised" not in config["playerok"]["tg_logging"]["events"]:
        config["playerok"]["tg_logging"]["events"]["item_raised"] = False
    config["playerok"]["tg_logging"]["events"]["item_raised"] = not config["playerok"]["tg_logging"]["events"]["item_raised"]
    sett.set("config", config)
    return await callback_settings_navigation(callback, calls.SettingsNavigation(to="notifications"), state)


@router.callback_query(F.data == "switch_plugin_enabled")
async def callback_switch_plugin_enabled(callback: CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        plugin_uuid = data.get("plugin_uuid")
        if not plugin_uuid:
            raise Exception("❌ UUID плагина не был найден, повторите процесс с самого начала")
        plugin = get_plugin_by_uuid(plugin_uuid)
        if not plugin:
            raise Exception("❌ Плагин с этим UUID не был найден, повторите процесс с самого начала")

        await deactivate_plugin(plugin_uuid) if plugin.enabled else await activate_plugin(plugin_uuid)
        return await callback_plugin_page(callback, calls.PluginPage(uuid=plugin_uuid), state)
    except Exception as e:
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.plugin_page_float_text(e), 
            reply_markup=templ.back_kb(calls.PluginsPagination(page=last_page).pack())
        )


# Маппинг типов автоответов на ключи в messages.json
MESSAGE_TYPE_MAPPING = {
    "greeting": "first_message",
    "confirmation_seller": "deal_sent",
    "confirmation_buyer": "deal_confirmed",
    "deal_has_problem": "deal_has_problem",
    "deal_problem_resolved": "deal_problem_resolved",
    "review": "new_review_response"
}

# Маппинг типов автоответов на навигацию
MESSAGE_TYPE_NAVIGATION = {
    "greeting": "greeting",
    "confirmation_seller": "confirmation_seller",
    "confirmation_buyer": "confirmation_buyer",
    "deal_has_problem": "deal_has_problem",
    "deal_problem_resolved": "deal_problem_resolved",
    "review": "review"
}


@router.callback_query(calls.AutoResponseToggle.filter())
async def callback_auto_response_toggle(callback: CallbackQuery, callback_data: calls.AutoResponseToggle, state: FSMContext):
    """Переключение вкл/выкл автоответа"""
    try:
        message_type = callback_data.message_type
        message_key = MESSAGE_TYPE_MAPPING.get(message_type)
        
        if not message_key:
            await callback.answer("❌ Неизвестный тип сообщения", show_alert=True)
            return
        
        messages = sett.get("messages")
        if message_key not in messages:
            messages[message_key] = {"enabled": False, "text": []}
        
        messages[message_key]["enabled"] = not messages[message_key]["enabled"]
        sett.set("messages", messages)
        
        nav_to = MESSAGE_TYPE_NAVIGATION[message_type]
        return await callback_messages_navigation(callback, calls.MessagesNavigation(to=nav_to), state)
        
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


@router.callback_query(calls.AutoResponseEdit.filter())
async def callback_auto_response_edit(callback: CallbackQuery, callback_data: calls.AutoResponseEdit, state: FSMContext):
    """Вход в режим редактирования текста автоответа"""
    try:
        message_type = callback_data.message_type
        message_key = MESSAGE_TYPE_MAPPING.get(message_type)
        
        if not message_key:
            await callback.answer("❌ Неизвестный тип сообщения", show_alert=True)
            return
        
        messages = sett.get("messages")
        current_text = "\n".join(messages.get(message_key, {}).get("text", []))
        
        # Устанавливаем соответствующее состояние
        state_mapping = {
            "greeting": states.AutoResponseStates.waiting_for_greeting_text,
            "confirmation_seller": states.AutoResponseStates.waiting_for_confirmation_seller_text,
            "confirmation_buyer": states.AutoResponseStates.waiting_for_confirmation_buyer_text,
            "deal_has_problem": states.AutoResponseStates.waiting_for_deal_has_problem_text,
            "deal_problem_resolved": states.AutoResponseStates.waiting_for_deal_problem_resolved_text,
            "review": states.AutoResponseStates.waiting_for_review_text
        }
        
        await state.set_state(state_mapping[message_type])
        
        # Названия для разных типов
        type_names = {
            "greeting": "приветственного сообщения",
            "confirmation_seller": "сообщения при подтверждении с нашей стороны",
            "confirmation_buyer": "сообщения при подтверждении покупателем",
            "deal_has_problem": "сообщения при проблеме в сделке",
            "deal_problem_resolved": "сообщения после решения проблемы",
            "review": "сообщения при получении отзыва"
        }
        
        nav_to = MESSAGE_TYPE_NAVIGATION[message_type]
        
        await throw_float_message(
            state=state,
            message=callback.message,
            text=f"✏️ Введите новый текст {type_names[message_type]} ↓\n\n<b>Текущий текст:</b>\n<code>{current_text or 'Не задан'}</code>\n\n💡 <i>Можно использовать несколько строк</i>",
            reply_markup=templ.back_kb(calls.MessagesNavigation(to=nav_to).pack())
        )
        
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


@router.callback_query(calls.GreetingCooldownEdit.filter())
async def callback_greeting_cooldown_edit(callback: CallbackQuery, state: FSMContext):
    """Вход в режим редактирования интервала приветствий"""
    try:
        messages = sett.get("messages")
        current_cooldown = messages.get("first_message", {}).get("cooldown_days", 7)
        
        await state.set_state(states.AutoResponseStates.waiting_for_greeting_cooldown)
        
        await throw_float_message(
            state=state,
            message=callback.message,
            text=f"⏱ <b>Изменение интервала приветствий</b>\n\n"
                 f"Текущий интервал: <b>{current_cooldown}</b> дн.\n\n"
                 f"Введите новый интервал (в днях) ↓\n\n"
                 f"💡 <i>Приветствие будет отправляться повторно,\n"
                 f"если пользователь не писал более указанного количества дней.</i>",
            reply_markup=templ.back_kb(calls.MessagesNavigation(to="greeting").pack())
        )
        
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)
