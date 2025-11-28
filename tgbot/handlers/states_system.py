from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext
from datetime import datetime
import logging

from settings import Settings as sett
from core.security import hash_password, verify_password, is_password_hashed

from .. import templates as templ
from .. import states
from ..helpful import throw_float_message


router = Router()
logger = logging.getLogger("seal.auth")


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
    
    # Формируем информацию о пользователе
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
        
        # Отправляем уведомление всем пользователям (кроме того, кто авторизовался)
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
        
        # Информация для логов
        user_info = f"@{user.username}" if user.username else f"ID: {user.id}"
        
        # Проверяем пароль
        password_valid = False
        need_hash_migration = False
        
        if is_password_hashed(stored_password):
            # Пароль уже захэширован — сравниваем хэши
            password_valid = verify_password(entered_password, stored_password)
        else:
            # Пароль в открытом виде — сравниваем напрямую
            password_valid = (entered_password == stored_password)
            need_hash_migration = password_valid
        
        if not password_valid:
            # Логируем неудачную попытку
            logger.warning(f"⚠️ Неудачная попытка входа: {user.full_name} ({user_info}) - ID: {user.id}")
            raise Exception("❌ Неверный ключ-пароль.")
        
        # Определяем тип события (регистрация или повторный вход)
        is_new_user = user.id not in config["telegram"]["bot"]["signed_users"]
        
        # Добавляем пользователя в список авторизованных
        if is_new_user:
            config["telegram"]["bot"]["signed_users"].append(user.id)
            logger.info(f"✅ Новый пользователь зарегистрирован: {user.full_name} ({user_info}) - ID: {user.id}")
        else:
            logger.info(f"✅ Пользователь авторизован: {user.full_name} ({user_info}) - ID: {user.id}")
        
        # Хэшируем пароль если нужна миграция
        if need_hash_migration:
            config["telegram"]["bot"]["password"] = hash_password(stored_password)
        
        sett.set("config", config)
        
        # Отправляем уведомление другим пользователям
        await notify_auth_event(user, "register" if is_new_user else "login", success=True)

        await throw_float_message(
            state=state,
            message=message,
            text=templ.menu_text(),
            reply_markup=templ.menu_kb(page=0)
        )
    except Exception as e:
        await throw_float_message(
            state=state,
            message=message,
            text=templ.sign_text(e), 
            reply_markup=templ.destroy_kb()
        )