import asyncio
import os
import sys
from aiogram import types, Router, Bot, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from settings import Settings as sett

from .. import templates as templ
from ..helpful import throw_float_message, do_auth


router = Router()


@router.message(Command("start"))
async def handler_start(message: types.Message, state: FSMContext):
    await state.set_state(None)
    config = sett.get("config")
    if message.from_user.id not in config["telegram"]["bot"]["signed_users"]:
        return await do_auth(message, state)
    await throw_float_message(
        state=state,
        message=message,
        text=templ.menu_text(),
        reply_markup=templ.menu_kb(page=0)
    )


@router.message(Command("developer"))
async def handler_developer(message: types.Message, state: FSMContext):
    """
    Обработчик команды /developer
    Открывает настройки разработчика
    """
    await state.set_state(None)
    config = sett.get("config")
    if message.from_user.id not in config["telegram"]["bot"]["signed_users"]:
        return await do_auth(message, state)
    await throw_float_message(
        state=state,
        message=message,
        text=templ.settings_developer_text(),
        reply_markup=templ.settings_developer_kb()
    )


@router.message(Command("watermark"))
async def handler_watermark(message: types.Message, state: FSMContext):
    """
    Обработчик команды /watermark
    Открывает настройки водяного знака
    """
    await state.set_state(None)
    config = sett.get("config")
    if message.from_user.id not in config["telegram"]["bot"]["signed_users"]:
        return await do_auth(message, state)
    await throw_float_message(
        state=state,
        message=message,
        text=templ.settings_watermark_text(),
        reply_markup=templ.settings_watermark_kb()
    )


@router.message(Command("profile"))
async def handler_profile(message: types.Message, state: FSMContext):
    """
    Обработчик команды /profile
    Открывает профиль пользователя Playerok
    """
    await state.set_state(None)
    config = sett.get("config")
    if message.from_user.id not in config["telegram"]["bot"]["signed_users"]:
        return await do_auth(message, state)
    await throw_float_message(
        state=state,
        message=message,
        text=templ.profile_text(),
        reply_markup=templ.profile_kb()
    )


@router.message(Command("restart"))
async def handler_restart(message: types.Message, state: FSMContext):
    """
    Обработчик команды /restart
    Перезагружает бота (доступно только администраторам)
    """
    config = sett.get("config")
    
    # Проверяем, является ли пользователь администратором
    if message.from_user.id not in config["telegram"]["bot"].get("signed_users", []):
        return await message.answer("❌ У вас нет прав для выполнения этой команды.")
    
    try:
        # Отправляем сообщение о начале перезагрузки
        restart_msg = await message.answer(
            "🔄 <b>Перезагрузка бота...</b>",
            parse_mode="HTML"
        )
        
        # Даем время на отправку сообщения
        await asyncio.sleep(1)
        
        # Завершаем текущий процесс и перезапускаем
        # os.execl заменяет текущий процесс новым, все ресурсы автоматически освобождаются
        python = sys.executable
        os.execl(python, python, *sys.argv)
        
    except Exception as e:
        await message.answer(f"❌ Произошла ошибка при перезагрузке: {str(e)}")


@router.message(Command("power_off", "poweroff"))
async def handler_power_off(message: types.Message, state: FSMContext):
    """
    Обработчик команды /power_off
    Полностью выключает бота (доступно только администраторам)
    """
    config = sett.get("config")
    
    # Проверяем, является ли пользователь администратором
    if message.from_user.id not in config["telegram"]["bot"].get("signed_users", []):
        return await message.answer("❌ У вас нет прав для выполнения этой команды.")
    
    try:
        # Отправляем сообщение о выключении
        await message.answer("⚡️ Выключаю бота... До свидания!")
        
        # Даем время на отправку сообщения
        await asyncio.sleep(0.5)
        
        # Завершаем процесс
        os._exit(0)
        
    except Exception as e:
        await message.answer(f"❌ Произошла ошибка при выключении: {str(e)}")


@router.message(Command("fingerprint"))
async def handler_fingerprint(message: types.Message, state: FSMContext, bot: Bot):
    """
    Обработчик команды /fingerprint
    Генерирует HWID для привязки лицензии к железу И боту
    
    ВАЖНО: Fingerprint V2 включает Bot ID!
    FINGERPRINT = SHA256(HWID + BOT_ID)[:32]
    
    Это гарантирует что плагин работает только на конкретной машине
    с конкретным ботом. Нельзя перенести на другого бота.
    """
    config = sett.get("config")
    
    # Проверяем авторизацию
    if message.from_user.id not in config["telegram"]["bot"].get("signed_users", []):
        return await do_auth(message, state)
    
    try:
        import hashlib
        import subprocess
        import uuid
        import sys
        
        # ═══════════════════════════════════════════════════════════════
        # 1. СОБИРАЕМ HWID (аппаратные компоненты)
        # ═══════════════════════════════════════════════════════════════
        components = []
        
        # MAC address
        components.append(hex(uuid.getnode()))
        
        # CPU ID (Windows only)
        try:
            if sys.platform == "win32":
                result = subprocess.check_output('wmic cpu get processorid', 
                                                shell=True, stderr=subprocess.DEVNULL)
                cpu_id = result.decode().split("\n")[1].strip()
                if cpu_id:
                    components.append(cpu_id)
        except Exception:
            pass
        
        # Motherboard serial (Windows only)
        try:
            if sys.platform == "win32":
                result = subprocess.check_output('wmic baseboard get serialnumber',
                                                shell=True, stderr=subprocess.DEVNULL)
                mb_serial = result.decode().split("\n")[1].strip()
                if mb_serial:
                    components.append(mb_serial)
        except Exception:
            pass
        
        # Disk serial (Windows only)
        try:
            if sys.platform == "win32":
                result = subprocess.check_output('wmic diskdrive get serialnumber',
                                                shell=True, stderr=subprocess.DEVNULL)
                disk_serial = result.decode().split("\n")[1].strip()
                if disk_serial:
                    components.append(disk_serial)
        except Exception:
            pass
        
        # Linux machine-id
        if sys.platform.startswith("linux"):
            try:
                with open("/etc/machine-id", "r") as f:
                    components.append(f"MACHINE:{f.read().strip()}")
            except Exception:
                pass
        
        # ═══════════════════════════════════════════════════════════════
        # 2. ПОЛУЧАЕМ BOT ID
        # ═══════════════════════════════════════════════════════════════
        bot_info = await bot.get_me()
        bot_id = bot_info.id
        
        # ═══════════════════════════════════════════════════════════════
        # 3. ГЕНЕРИРУЕМ FINGERPRINT V2 (HWID + Bot ID)
        # ═══════════════════════════════════════════════════════════════
        # Сначала хешируем HWID
        hwid_raw = '|'.join(components)
        hwid_hash = hashlib.sha256(hwid_raw.encode()).hexdigest()
        
        # Затем комбинируем с Bot ID и хешируем снова
        # Это гарантирует что один и тот же HWID с разными ботами
        # даст разные fingerprint
        combined = f"{hwid_hash}:{bot_id}"
        fingerprint_full = hashlib.sha256(combined.encode()).hexdigest()
        
        # Берём первые 32 символа для отображения
        fingerprint = fingerprint_full[:32].upper()
        formatted = "-".join([fingerprint[i:i+4] for i in range(0, 32, 4)])
        
        await message.answer(
            f"🦭 <b>Твой Fingerprint V2</b>\n\n"
            f"<code>{formatted}</code>\n\n"
            f"📋 <i>Скопируй и отправь при покупке плагина.</i>\n"
            f"🔒 <i>Плагин будет привязан к этому железу И этому боту!</i>\n\n"
            f"<b>Компоненты:</b>\n"
            f"• HWID: <code>{hwid_hash[:12]}...</code>\n"
            f"• Bot ID: <code>{bot_id}</code>\n"
            f"• Версия: <code>V2 (с Bot ID)</code>",
            parse_mode="HTML"
        )
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при генерации fingerprint: {str(e)}")


@router.message(Command("playerok_status"))
async def handler_playerok_status(message: types.Message, state: FSMContext):
    """
    Обработчик команды /playerok_status
    Показывает статус подключения к Playerok
    """
    config = sett.get("config")
    
    # Проверяем авторизацию
    if message.from_user.id not in config["telegram"]["bot"].get("signed_users", []):
        return await do_auth(message, state)
    
    # Отправляем промежуточное сообщение
    checking_msg = await message.answer("🔄 <b>Проверяю подключение к Playerok...</b>", parse_mode="HTML")
    
    try:
        from plbot.playerokbot import PlayerokBot
        playerok_bot = PlayerokBot()
        
        if playerok_bot.is_connected and playerok_bot.playerok_account:
            # Подключено
            try:
                username = playerok_bot.playerok_account.profile.username
                user_id = playerok_bot.playerok_account.profile.id
            except:
                username = "Неизвестно"
                user_id = "Неизвестно"
            
            proxy_status = "🟢 Активен" if config["playerok"]["api"]["proxy"] else "⚫ Не используется"
            
            text = (
                f"🟢 <b>Playerok подключен</b>\n\n"
                f"<b>Аккаунт:</b> @{username}\n"
                f"<b>ID:</b> <code>{user_id}</code>\n"
                f"<b>Прокси:</b> {proxy_status}\n\n"
                f"<i>✅ Бот работает нормально</i>"
            )
            
            # Кнопка обновления
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить статус", callback_data="refresh_playerok_status")]
            ])
            
            await checking_msg.edit_text(text, parse_mode="HTML", reply_markup=kb)
        else:
            # Не подключено
            error_msg = str(playerok_bot.connection_error) if playerok_bot.connection_error else "Неизвестная ошибка"
            # Экранируем HTML теги в ошибке
            error_msg = error_msg.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
            
            text = (
                f"🔴 <b>Playerok не подключен</b>\n\n"
                f"<b>Ошибка:</b>\n<code>{error_msg[:200]}</code>\n\n"
                f"<i>⚠️ Проверьте настройки токена и прокси</i>"
            )
            
            # Кнопки переподключения и настроек
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            from .. import callback_datas as calls
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Переподключить", callback_data="reconnect_playerok")],
                [InlineKeyboardButton(text="⚙️ Настройки аккаунта", callback_data=calls.SettingsNavigation(to="account").pack())]
            ])
            
            await checking_msg.edit_text(text, parse_mode="HTML", reply_markup=kb)
            
    except Exception as e:
        error_text = str(e).replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
        await checking_msg.edit_text(
            f"❌ <b>Ошибка при проверке статуса</b>\n\n"
            f"<code>{error_text[:200]}</code>",
            parse_mode="HTML"
        )



@router.callback_query(F.data == "refresh_playerok_status")
async def callback_refresh_playerok_status(callback: types.CallbackQuery):
    """Обновляет статус подключения к Playerok."""
    # Показываем промежуточное сообщение
    await callback.message.edit_text("🔄 <b>Проверяю подключение...</b>", parse_mode="HTML")
    await callback.answer()
    
    try:
        from plbot.playerokbot import PlayerokBot
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from .. import callback_datas as calls
        
        config = sett.get("config")
        playerok_bot = PlayerokBot()
        
        if playerok_bot.is_connected and playerok_bot.playerok_account:
            # Подключено
            try:
                username = playerok_bot.playerok_account.profile.username
                user_id = playerok_bot.playerok_account.profile.id
            except:
                username = "Неизвестно"
                user_id = "Неизвестно"
            
            proxy_status = "🟢 Активен" if config["playerok"]["api"]["proxy"] else "⚫ Не используется"
            
            text = (
                f"🟢 <b>Playerok подключен</b>\n\n"
                f"<b>Аккаунт:</b> @{username}\n"
                f"<b>ID:</b> <code>{user_id}</code>\n"
                f"<b>Прокси:</b> {proxy_status}\n\n"
                f"<i>✅ Бот работает нормально</i>"
            )
            
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить статус", callback_data="refresh_playerok_status")]
            ])
            
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        else:
            # Не подключено
            error_msg = str(playerok_bot.connection_error) if playerok_bot.connection_error else "Неизвестная ошибка"
            error_msg = error_msg.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
            
            text = (
                f"🔴 <b>Playerok не подключен</b>\n\n"
                f"<b>Ошибка:</b>\n<code>{error_msg[:200]}</code>\n\n"
                f"<i>⚠️ Проверьте настройки токена и прокси</i>"
            )
            
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Переподключить", callback_data="reconnect_playerok")],
                [InlineKeyboardButton(text="⚙️ Настройки аккаунта", callback_data=calls.SettingsNavigation(to="account").pack())]
            ])
            
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
            
    except Exception as e:
        error_text = str(e).replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
        await callback.message.edit_text(
            f"❌ <b>Ошибка при проверке</b>\n\n<code>{error_text[:200]}</code>",
            parse_mode="HTML"
        )


@router.callback_query(F.data == "reconnect_playerok")
async def callback_reconnect_playerok(callback: types.CallbackQuery):
    """Переподключает к Playerok."""
    # Показываем промежуточное сообщение
    await callback.message.edit_text("🔄 <b>Переподключаюсь к Playerok...</b>", parse_mode="HTML")
    await callback.answer()
    
    try:
        from plbot.playerokbot import PlayerokBot
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from .. import callback_datas as calls
        
        playerok_bot = PlayerokBot()
        success = await playerok_bot.reconnect()
        
        config = sett.get("config")
        
        if success and playerok_bot.is_connected:
            # Успешно переподключено
            try:
                username = playerok_bot.playerok_account.profile.username
                user_id = playerok_bot.playerok_account.profile.id
            except:
                username = "Неизвестно"
                user_id = "Неизвестно"
            
            proxy_status = "🟢 Активен" if config["playerok"]["api"]["proxy"] else "⚫ Не используется"
            
            text = (
                f"🟢 <b>Playerok подключен</b>\n\n"
                f"<b>Аккаунт:</b> @{username}\n"
                f"<b>ID:</b> <code>{user_id}</code>\n"
                f"<b>Прокси:</b> {proxy_status}\n\n"
                f"<i>✅ Переподключение успешно!</i>"
            )
            
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить статус", callback_data="refresh_playerok_status")]
            ])
            
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        else:
            # Не удалось переподключиться
            error_msg = str(playerok_bot.connection_error) if playerok_bot.connection_error else "Неизвестная ошибка"
            error_msg = error_msg.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
            
            text = (
                f"🔴 <b>Не удалось переподключиться</b>\n\n"
                f"<b>Ошибка:</b>\n<code>{error_msg[:200]}</code>\n\n"
                f"<i>⚠️ Проверьте настройки токена и прокси</i>"
            )
            
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="reconnect_playerok")],
                [InlineKeyboardButton(text="⚙️ Настройки аккаунта", callback_data=calls.SettingsNavigation(to="account").pack())]
            ])
            
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
            
    except Exception as e:
        error_text = str(e).replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
        await callback.message.edit_text(
            f"❌ <b>Ошибка переподключения</b>\n\n<code>{error_text[:200]}</code>",
            parse_mode="HTML"
        )
