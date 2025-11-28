"""
Callback handlers для управления прокси.
"""

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from logging import getLogger

from settings import Settings as sett
from core.proxy_utils import validate_proxy, normalize_proxy, check_proxy, format_proxy_display
from playerokapi.account import get_account

from .. import templates as templ
from .. import callback_datas as calls
from .. import states
from ..helpful import throw_float_message


logger = getLogger("tgbot.proxy")
router = Router()


@router.callback_query(calls.ProxyListPagination.filter())
async def callback_proxy_list(callback: CallbackQuery, callback_data: calls.ProxyListPagination):
    """Отображение списка прокси с пагинацией."""
    page = callback_data.page
    text = templ.settings_proxy_list_text(page=page)
    kb = templ.settings_proxy_list_kb(page=page)
    
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(calls.ProxyPage.filter())
async def callback_proxy_page(callback: CallbackQuery, callback_data: calls.ProxyPage):
    """Отображение страницы конкретного прокси."""
    proxy_id = callback_data.proxy_id
    text = templ.settings_proxy_page_text(proxy_id=proxy_id)
    kb = templ.settings_proxy_page_kb(proxy_id=proxy_id)
    
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "enter_new_proxy")
async def callback_enter_new_proxy(callback: CallbackQuery, state: FSMContext):
    """Активирует режим ввода нового прокси."""
    await state.set_state(states.SettingsStates.waiting_for_new_proxy)
    
    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.settings_proxy_float_text(
            "🌐 Введите новый прокси в одном из форматов:\n\n"
            "<b>HTTP/HTTPS:</b>\n"
            "· <code>ip:port:user:password</code>\n"
            "· <code>user:password@ip:port</code>\n"
            "· <code>ip:port</code> (без авторизации)\n\n"
            "<b>SOCKS5:</b>\n"
            "· <code>socks5://user:password@ip:port</code>\n"
            "· <code>socks5://ip:port</code> (без авторизации)\n\n"
            "<b>Примеры:</b>\n"
            "HTTP: <code>91.221.39.249:63880:user:pass</code>\n"
            "SOCKS5: <code>socks5://user:pass@91.221.39.249:63880</code>"
        ),
        reply_markup=templ.back_kb(calls.ProxyListPagination(page=0).pack())
    )
    await callback.answer()


@router.message(states.SettingsStates.waiting_for_new_proxy, F.text)
async def handler_add_new_proxy(message: Message, state: FSMContext):
    """Обработчик добавления нового прокси с проверкой."""
    await state.set_state(None)
    proxy_input = message.text.strip()
    
    try:
        # Валидация формата
        validate_proxy(proxy_input)
        
        # Нормализация
        normalized_proxy = normalize_proxy(proxy_input)
        
        # Проверка на дубликат
        proxy_list = sett.get("proxy_list") or {}
        if normalized_proxy in proxy_list.values():
            raise ValueError("❌ Такой прокси уже добавлен в список")
        
        # Отправляем сообщение о проверке
        checking_msg = await message.answer("🔄 Проверяю прокси, подождите...")
        
        # Проверка работоспособности
        is_working = check_proxy(normalized_proxy, timeout=10)
        
        await checking_msg.delete()
        
        # Добавляем прокси в список
        max_id = max([int(k) for k in proxy_list.keys()], default=0)
        new_id = max_id + 1
        proxy_list[str(new_id)] = normalized_proxy
        sett.set("proxy_list", proxy_list)
        
        # Формируем сообщение
        status_emoji = "✅" if is_working else "⚠️"
        status_text = "работает и добавлен" if is_working else "добавлен, но не прошёл проверку"
        is_socks = normalized_proxy.startswith(('socks5://', 'socks4://'))
        
        display = format_proxy_display(normalized_proxy)
        
        result_text = (
            f"{status_emoji} <b>Прокси {status_text}</b>\n\n"
            f"<b>Адрес:</b> <code>{display}</code>\n"
            f"<b>ID:</b> {new_id}\n"
            f"<b>Тип:</b> {'SOCKS5' if is_socks else 'HTTP/HTTPS'}\n\n"
        )
        
        if is_socks:
            result_text += "<i>⚠️ SOCKS прокси могут работать менее стабильно с Playerok. Рекомендуется HTTP/HTTPS.</i>\n\n"
        
        if not is_working:
            result_text += "<i>Прокси может работать медленно или иметь проблемы.\nБот попытается использовать его при активации.</i>"
        else:
            result_text += "<i>Нажмите на прокси в списке, чтобы активировать его.</i>"
        
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_proxy_float_text(result_text),
            reply_markup=templ.back_kb(calls.ProxyListPagination(page=0).pack())
        )
        
        logger.info(f"Добавлен новый прокси ID:{new_id}, работает: {is_working}")
        
    except ValueError as e:
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_proxy_float_text(str(e)),
            reply_markup=templ.back_kb(calls.ProxyListPagination(page=0).pack())
        )
    except Exception as e:
        logger.error(f"Ошибка при добавлении прокси: {e}", exc_info=True)
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_proxy_float_text(f"❌ Произошла ошибка: {str(e)}"),
            reply_markup=templ.back_kb(calls.ProxyListPagination(page=0).pack())
        )


@router.callback_query(F.data.startswith("activate_proxy:"))
async def callback_activate_proxy(callback: CallbackQuery):
    """Активирует выбранный прокси с проверкой."""
    proxy_id = int(callback.data.split(":")[1])
    
    proxy_list = sett.get("proxy_list") or {}
    proxy_str = proxy_list.get(str(proxy_id))
    
    if not proxy_str:
        await callback.answer("❌ Прокси не найден", show_alert=True)
        return
    
    # Отправляем сообщение о проверке
    checking_msg = await callback.message.answer("🔄 Проверяю прокси перед активацией...")
    
    # Проверка работоспособности
    is_working = check_proxy(proxy_str, timeout=10)
    
    await checking_msg.delete()
    
    if is_working:
        # Активируем прокси в конфиге
        config = sett.get("config")
        config["playerok"]["api"]["proxy"] = proxy_str
        sett.set("config", config)
        
        # Hot-reload: обновляем прокси в работающем Account
        account = get_account()
        if account:
            account.update_proxy(proxy_str)
        
        display = format_proxy_display(proxy_str)
        await callback.answer(f"✅ Прокси активирован: {display}", show_alert=True)
        
        logger.info(f"Активирован прокси ID:{proxy_id} (hot-reload)")
    else:
        await callback.answer(
            "⚠️ Прокси не прошёл проверку!\n\nВы можете попробовать активировать его позже или использовать другой прокси.",
            show_alert=True
        )
    
    # Обновляем страницу прокси
    text = templ.settings_proxy_page_text(proxy_id=proxy_id)
    kb = templ.settings_proxy_page_kb(proxy_id=proxy_id)
    await callback.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data == "deactivate_proxy")
async def callback_deactivate_proxy(callback: CallbackQuery):
    """Деактивирует текущий прокси."""
    config = sett.get("config")
    config["playerok"]["api"]["proxy"] = ""
    sett.set("config", config)
    
    # Hot-reload: отключаем прокси в работающем Account
    account = get_account()
    if account:
        account.update_proxy(None)
    
    await callback.answer("✅ Прокси деактивирован", show_alert=True)
    logger.info("Прокси деактивирован (hot-reload)")
    
    # Возвращаемся к списку
    text = templ.settings_proxy_list_text(page=0)
    kb = templ.settings_proxy_list_kb(page=0)
    await callback.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data.startswith("check_proxy:"))
async def callback_check_proxy(callback: CallbackQuery):
    """Проверяет работоспособность прокси."""
    proxy_id = int(callback.data.split(":")[1])
    
    proxy_list = sett.get("proxy_list") or {}
    proxy_str = proxy_list.get(str(proxy_id))
    
    if not proxy_str:
        await callback.answer("❌ Прокси не найден", show_alert=True)
        return
    
    # Отправляем сообщение о проверке
    checking_msg = await callback.message.answer("🔄 Проверяю прокси...")
    
    # Проверка работоспособности
    is_working = check_proxy(proxy_str, timeout=10)
    
    await checking_msg.delete()
    
    if is_working:
        await callback.answer("✅ Прокси работает!", show_alert=True)
    else:
        await callback.answer("❌ Прокси не работает или не отвечает", show_alert=True)


@router.callback_query(F.data.startswith("delete_proxy:"))
async def callback_delete_proxy(callback: CallbackQuery):
    """Удаляет прокси из списка."""
    proxy_id = int(callback.data.split(":")[1])
    
    config = sett.get("config")
    proxy_list = sett.get("proxy_list") or {}
    current_proxy = config["playerok"]["api"]["proxy"]
    
    proxy_str = proxy_list.get(str(proxy_id))
    
    if not proxy_str:
        await callback.answer("❌ Прокси не найден", show_alert=True)
        return
    
    # Проверяем, не является ли прокси активным
    if proxy_str == current_proxy:
        await callback.answer("❌ Нельзя удалить активный прокси! Сначала деактивируйте его.", show_alert=True)
        return
    
    # Удаляем прокси
    del proxy_list[str(proxy_id)]
    sett.set("proxy_list", proxy_list)
    
    display = format_proxy_display(proxy_str)
    await callback.answer(f"✅ Прокси удалён: {display}", show_alert=True)
    
    logger.info(f"Удалён прокси ID:{proxy_id}")
    
    # Возвращаемся к списку
    text = templ.settings_proxy_list_text(page=0)
    kb = templ.settings_proxy_list_kb(page=0)
    await callback.message.edit_text(text, reply_markup=kb)
