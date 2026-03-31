from aiogram import F, Router
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from core.auto_deliveries import AUTO_DELIVERY_KIND_MULTI, AUTO_DELIVERY_KIND_STATIC, normalize_auto_deliveries
from settings import Settings as sett

from .. import templates as templ
from .. import callback_datas as calls
from .. import states as states
from ..helpful import throw_float_message
from .navigation import *


router = Router()


@router.callback_query(F.data == "enter_token")
async def callback_enter_token(callback: CallbackQuery, state: FSMContext):
    await state.set_state(states.SettingsStates.waiting_for_token)
    await throw_float_message(
        state=state, 
        message=callback.message, 
        text=templ.settings_account_float_text(f"🔐 Введите новый <b>токен</b> вашего аккаунта ↓"), 
        reply_markup=templ.back_kb(calls.SettingsNavigation(to="account").pack())
    )


@router.callback_query(F.data == "enter_user_agent")
async def callback_enter_user_agent(callback: CallbackQuery, state: FSMContext):
    await state.set_state(states.SettingsStates.waiting_for_user_agent)
    config = sett.get("config")
    user_agent = config["playerok"]["api"]["user_agent"] or "❌ Не задано"
    await throw_float_message(
        state=state, 
        message=callback.message, 
        text=templ.settings_account_float_text(f"🎩 Введите новый <b>user_agent</b> вашего браузера ↓\n┗ Текущее: <code>{user_agent}</code>"), 
        reply_markup=templ.back_kb(calls.SettingsNavigation(to="account").pack())
    )


# Старый обработчик прокси - теперь используется новая система управления прокси
# См. tgbot/callback_handlers/proxy_management.py
# @router.callback_query(F.data == "enter_proxy")
# async def callback_enter_proxy(callback: CallbackQuery, state: FSMContext):
#     await state.set_state(states.SettingsStates.waiting_for_proxy)
#     config = sett.get("config")
#     proxy = config["playerok"]["api"]["proxy"] or "❌ Не задано"
#     await throw_float_message(
#         state=state, 
#         message=callback.message, 
#         text=templ.settings_account_float_text(
#             f"🌐 Введите новый <b>прокси-сервер</b> ↓\n\n"
#             f"<b>Форматы HTTP/HTTPS:</b>\n"
#             f"· <code>ip:port:user:password</code>\n"
#             f"· <code>user:password@ip:port</code>\n"
#             f"· <code>ip:port</code> (без авторизации)\n\n"
#             f"<b>Форматы SOCKS5:</b>\n"
#             f"· <code>socks5://user:password@ip:port</code>\n"
#             f"· <code>socks5://ip:port</code> (без авторизации)\n\n"
#             f"<b>Примеры:</b>\n"
#             f"HTTP: <code>91.221.39.249:63880:user:pass</code>\n"
#             f"SOCKS5: <code>socks5://user:pass@91.221.39.249:63880</code>\n\n"
#             f"┗ Текущее: <code>{proxy}</code>"
#         ), 
#         reply_markup=templ.back_kb(calls.SettingsNavigation(to="account").pack())
#     )


@router.callback_query(F.data == "enter_requests_timeout")
async def callback_enter_requests_timeout(callback: CallbackQuery, state: FSMContext):
    await state.set_state(states.SettingsStates.waiting_for_requests_timeout)
    config = sett.get("config")
    requests_timeout = config["playerok"]["api"]["requests_timeout"] or "❌ Не задано"
    await throw_float_message(
        state=state, 
        message=callback.message, 
        text=templ.settings_developer_float_text(f"🛜 Введите новый <b>таймаут подключения</b> (в секундах) ↓\n┗ Текущее: <code>{requests_timeout}</code>"), 
        reply_markup=templ.back_kb(calls.SettingsNavigation(to="developer").pack())
    )


@router.callback_query(F.data == "enter_listener_requests_delay")
async def callback_enter_listener_requests_delay(callback: CallbackQuery, state: FSMContext):
    await state.set_state(states.SettingsStates.waiting_for_listener_requests_delay)
    config = sett.get("config")
    requests_timeout = config["playerok"]["api"]["listener_requests_delay"] or "❌ Не задано"
    await throw_float_message(
        state=state, 
        message=callback.message, 
        text=templ.settings_developer_float_text(f"⏱️ Введите новую <b>периодичность запросов</b> (в секундах) ↓\n┗ Текущее: <code>{requests_timeout}</code>"), 
        reply_markup=templ.back_kb(calls.SettingsNavigation(to="developer").pack())
    )


@router.callback_query(F.data == "enter_watermark_value")
async def callback_enter_watermark_value(callback: CallbackQuery, state: FSMContext):
    await state.set_state(states.SettingsStates.waiting_for_watermark_value)
    config = sett.get("config")
    watermark_value = config["playerok"]["watermark"]["value"] or "❌ Не задано"
    await throw_float_message(
        state=state, 
        message=callback.message, 
        text=templ.settings_watermark_float_text(f"✍️©️ Введите новый <b>водяной знак</b> под сообщениями ↓\n┗ Текущее: <code>{watermark_value}</code>"), 
        reply_markup=templ.back_kb(calls.SettingsNavigation(to="watermark").pack())
    )


@router.callback_query(F.data == "enter_new_included_restore_item_keyphrases")
async def callback_enter_new_included_restore_item_keyphrases(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    last_page = data.get("last_page", 0)
    await state.set_state(states.RestoreItemsStates.waiting_for_new_included_restore_item_keyphrases)
    await throw_float_message(
        state=state, 
        message=callback.message, 
        text=templ.settings_new_restore_included_float_text(f"🔑 Введите <b>ключевые фразы</b> названия товара, который нужно включить в авто-восстановление (указываются через запятую, например, \"samp аккаунт, со всеми данными\") ↓"), 
        reply_markup=templ.back_kb(calls.IncludedRestoreItemsPagination(page=last_page).pack())
    )


@router.callback_query(F.data == "enter_new_excluded_restore_item_keyphrases")
async def callback_enter_new_excluded_restore_item_keyphrases(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    last_page = data.get("last_page", 0)
    await state.set_state(states.RestoreItemsStates.waiting_for_new_excluded_restore_item_keyphrases)
    await throw_float_message(
        state=state, 
        message=callback.message, 
        text=templ.settings_new_restore_excluded_float_text(f"🔑 Введите <b>ключевые фразы</b> названия товара, который нужно исключить из авто-восстановления (указываются через запятую, например, \"samp аккаунт, со всеми данными\") ↓"), 
        reply_markup=templ.back_kb(calls.ExcludedRestoreItemsPagination(page=last_page).pack())
    )
        

@router.callback_query(F.data == "enter_custom_commands_page")
async def callback_enter_custom_commands_page(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    last_page = data.get("last_page", 0)
    await state.set_state(states.CustomCommandsStates.waiting_for_page)
    await throw_float_message(
        state=state, 
        message=callback.message, 
        text=templ.settings_comms_float_text(f"📃 Введите номер страницы для перехода ↓"), 
        reply_markup=templ.back_kb(calls.CustomCommandsPagination(page=last_page).pack())
    )


@router.callback_query(F.data == "enter_new_custom_command")
async def callback_enter_new_custom_command(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    last_page = data.get("last_page", 0)
    await state.set_state(states.CustomCommandsStates.waiting_for_new_custom_command)
    await throw_float_message(
        state=state, 
        message=callback.message, 
        text=templ.settings_new_comm_float_text(f"⌨️ Введите <b>новую команду</b> (например, <code>!тест</code>) ↓"), 
        reply_markup=templ.back_kb(calls.CustomCommandsPagination(page=last_page).pack())
    )


@router.callback_query(F.data == "enter_custom_command_answer")
async def callback_enter_custom_command_answer(callback: CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        custom_commands = sett.get("custom_commands")
        custom_command = data.get("custom_command")
        if not custom_command:
            raise Exception("❌ Пользовательская команда не была найдена, повторите процесс с самого начала")
        
        await state.set_state(states.CustomCommandsStates.waiting_for_custom_command_answer)
        custom_command_answer = "\n".join(custom_commands[custom_command]) or "❌ Не задано"
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.settings_comm_page_float_text(f"💬 Введите новый <b>текст ответа</b> команды <code>{custom_command}</code> ↓\n┗ Текущее: <blockquote>{custom_command_answer}</blockquote>"), 
            reply_markup=templ.back_kb(calls.CustomCommandPage(command=custom_command).pack())
        )
    except Exception as e:
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.settings_comm_page_float_text(e), 
            reply_markup=templ.back_kb(calls.CustomCommandsPagination(page=last_page).pack())
        )


@router.callback_query(F.data == "enter_auto_deliveries_page")
async def callback_enter_auto_deliveries_page(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    last_page = data.get("last_page", 0)
    await state.set_state(states.AutoDeliveriesStates.waiting_for_page)
    await throw_float_message(
        state=state, 
        message=callback.message, 
        text=templ.settings_delivs_float_text(f"📃 Введите номер страницы для перехода ↓"), 
        reply_markup=templ.back_kb(calls.AutoDeliveriesPagination(page=last_page).pack())
    )


@router.callback_query(F.data == "enter_new_auto_delivery")
async def callback_enter_new_auto_delivery(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    last_page = data.get("last_page", 0)
    await state.set_state(None)
    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.settings_new_deliv_type_float_text(
            "Выберите тип новой авто-выдачи:\n\n"
            "🧾 <b>Обычная</b> - один и тот же текст на каждую покупку.\n"
            "📦 <b>Мультивыдача</b> - каждая покупка получает следующую уникальную строку."
        ),
        reply_markup=templ.settings_new_deliv_type_kb(last_page),
    )


@router.callback_query(F.data == "enter_new_auto_delivery_keyphrases")
async def callback_enter_new_auto_delivery_keyphrases(callback: CallbackQuery, state: FSMContext):
    # Совместимость со старыми кнопками: считаем это выбором static.
    await callback_select_new_auto_delivery_kind_static(callback, state)


@router.callback_query(F.data == "select_new_auto_delivery_kind_static")
async def callback_select_new_auto_delivery_kind_static(callback: CallbackQuery, state: FSMContext):
    await state.set_state(states.AutoDeliveriesStates.waiting_for_new_auto_delivery_keyphrases)
    await state.update_data(
        new_auto_delivery_kind=AUTO_DELIVERY_KIND_STATIC,
        new_auto_delivery_message=None,
        new_auto_delivery_items=None,
    )
    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.settings_new_deliv_float_text(
            "🔑 Введите <b>ключевые фразы</b> товара через запятую "
            "(например: <code>telegram, подписчики</code>) ↓"
        ),
        reply_markup=templ.back_kb("enter_new_auto_delivery"),
    )


@router.callback_query(F.data == "select_new_auto_delivery_kind_multi")
async def callback_select_new_auto_delivery_kind_multi(callback: CallbackQuery, state: FSMContext):
    await state.set_state(states.AutoDeliveriesStates.waiting_for_new_auto_delivery_keyphrases)
    await state.update_data(
        new_auto_delivery_kind=AUTO_DELIVERY_KIND_MULTI,
        new_auto_delivery_message=None,
        new_auto_delivery_items=None,
    )
    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.settings_new_deliv_float_text(
            "🔑 Введите <b>ключевые фразы</b> товара через запятую "
            "(например: <code>steam, key</code>) ↓"
        ),
        reply_markup=templ.back_kb("enter_new_auto_delivery"),
    )


@router.callback_query(F.data == "enter_auto_delivery_keyphrases")
async def callback_enter_auto_delivery_keyphrases(callback: CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        auto_delivery_index = data.get("auto_delivery_index")
        if auto_delivery_index is None:
            raise Exception("❌ Авто-выдача не была найдена, повторите процесс с самого начала")
        
        await state.set_state(states.AutoDeliveriesStates.waiting_for_auto_delivery_keyphrases)
        auto_deliveries = normalize_auto_deliveries(sett.get("auto_deliveries") or [])
        if auto_delivery_index < 0 or auto_delivery_index >= len(auto_deliveries):
            raise Exception("❌ Авто-выдача не была найдена")
        auto_delivery_message = "</code>, <code>".join(auto_deliveries[auto_delivery_index]["keyphrases"]) or "❌ Не задано"
        
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.settings_deliv_page_float_text(f"🔑 Введите новые <b>ключевые фразы</b> названия товара, на который авто-выдачи (указываются через запятую)\n┗ Текущее: <code>{auto_delivery_message}</code>"), 
            reply_markup=templ.back_kb(calls.AutoDeliveryPage(index=auto_delivery_index).pack())
        )
    except Exception as e:
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.settings_deliv_page_float_text(e), 
            reply_markup=templ.back_kb(calls.AutoDeliveriesPagination(page=last_page).pack())
        )


@router.callback_query(F.data == "enter_auto_delivery_message")
async def callback_enter_auto_delivery_message(callback: CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        auto_delivery_index = data.get("auto_delivery_index")
        if auto_delivery_index is None:
            raise Exception("❌ Авто-выдача не была найдена, повторите процесс с самого начала")
        
        auto_deliveries = normalize_auto_deliveries(sett.get("auto_deliveries") or [])
        if auto_delivery_index < 0 or auto_delivery_index >= len(auto_deliveries):
            raise Exception("❌ Авто-выдача не была найдена")
        auto_delivery = auto_deliveries[auto_delivery_index]
        if auto_delivery.get("kind") == AUTO_DELIVERY_KIND_MULTI:
            raise Exception("❌ Это мультивыдача. Используйте кнопки добавления или обновления товаров.")

        await state.set_state(states.AutoDeliveriesStates.waiting_for_auto_delivery_message)
        auto_delivery_message = "\n".join(auto_delivery.get("message", [])) or "❌ Не задано"
        
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.settings_deliv_page_float_text(f"💬 Введите новое <b>сообщение</b> после покупки\n┗ Текущее: <blockquote>{auto_delivery_message}</blockquote>"), 
            reply_markup=templ.back_kb(calls.AutoDeliveryPage(index=auto_delivery_index).pack())
        )
    except Exception as e:
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.settings_deliv_page_float_text(e), 
            reply_markup=templ.back_kb(calls.AutoDeliveriesPagination(page=last_page).pack())
        )


@router.callback_query(F.data == "enter_auto_delivery_add_items")
async def callback_enter_auto_delivery_add_items(callback: CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        auto_delivery_index = data.get("auto_delivery_index")
        if auto_delivery_index is None:
            raise Exception("❌ Авто-выдача не была найдена")

        auto_deliveries = normalize_auto_deliveries(sett.get("auto_deliveries") or [])
        if auto_delivery_index < 0 or auto_delivery_index >= len(auto_deliveries):
            raise Exception("❌ Авто-выдача не была найдена")
        if auto_deliveries[auto_delivery_index].get("kind") != AUTO_DELIVERY_KIND_MULTI:
            raise Exception("❌ Добавление товаров доступно только для мультивыдачи.")

        await state.set_state(states.AutoDeliveriesStates.waiting_for_auto_delivery_add_items)
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.settings_deliv_page_float_text(
                "➕ Отправьте новые товары для добавления в конец списка:\n\n"
                "• текстом (каждая непустая строка = один товар)\n"
                "или\n"
                "• <b>.txt</b> файлом (каждая непустая строка = один товар)."
            ),
            reply_markup=templ.back_kb(calls.AutoDeliveryPage(index=auto_delivery_index).pack())
        )
    except Exception as e:
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.settings_deliv_page_float_text(e),
            reply_markup=templ.back_kb(calls.AutoDeliveriesPagination(page=last_page).pack())
        )


@router.callback_query(F.data == "enter_auto_delivery_replace_items")
async def callback_enter_auto_delivery_replace_items(callback: CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        auto_delivery_index = data.get("auto_delivery_index")
        if auto_delivery_index is None:
            raise Exception("❌ Авто-выдача не была найдена")

        auto_deliveries = normalize_auto_deliveries(sett.get("auto_deliveries") or [])
        if auto_delivery_index < 0 or auto_delivery_index >= len(auto_deliveries):
            raise Exception("❌ Авто-выдача не была найдена")
        if auto_deliveries[auto_delivery_index].get("kind") != AUTO_DELIVERY_KIND_MULTI:
            raise Exception("❌ Обновление товаров доступно только для мультивыдачи.")

        await state.set_state(states.AutoDeliveriesStates.waiting_for_auto_delivery_replace_items)
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.settings_deliv_page_float_text(
                "♻️ Отправьте новую партию товаров для полной замены текущего списка:\n\n"
                "• текстом (каждая непустая строка = один товар)\n"
                "или\n"
                "• <b>.txt</b> файлом (каждая непустая строка = один товар).\n\n"
                "ℹ️ Счетчик «Выдано в текущей партии» будет сброшен в 0."
            ),
            reply_markup=templ.back_kb(calls.AutoDeliveryPage(index=auto_delivery_index).pack())
        )
    except Exception as e:
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.settings_deliv_page_float_text(e),
            reply_markup=templ.back_kb(calls.AutoDeliveriesPagination(page=last_page).pack())
        )


@router.callback_query(F.data == "enter_tg_logging_chat_id")
async def callback_enter_tg_logging_chat_id(callback: CallbackQuery, state: FSMContext):
    await state.set_state(states.SettingsStates.waiting_for_tg_logging_chat_id)
    config = sett.get("config")
    tg_logging_chat_id = config["playerok"]["tg_logging"]["chat_id"] or "✔️ Ваш чат с ботом"
    await throw_float_message(
        state=state, 
        message=callback.message, 
        text=templ.settings_notifications_float_text(f"💬 Введите новый <b>ID чата для уведомлений</b> (вы можете указать как цифровой ID, так и юзернейм чата) ↓\n┗ Текущее: <code>{tg_logging_chat_id}</code>"), 
        reply_markup=templ.back_kb(calls.SettingsNavigation(to="notifications").pack())
    )
