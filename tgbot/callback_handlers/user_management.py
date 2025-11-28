from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from settings import Settings as sett
from .. import templates as templ
from ..helpful import throw_float_message

router = Router()

@router.callback_query(F.data.startswith("remove_user:"))
async def callback_remove_user(callback: CallbackQuery, state: FSMContext):
    try:
        # Extract user ID from callback data
        user_id_to_remove = int(callback.data.split(":")[1])
        config = sett.get("config")
        
        # Check if user exists in the list
        if user_id_to_remove not in config["telegram"]["bot"].get("signed_users", []):
            raise ValueError("Пользователь не найден")
            
        # Don't allow removing yourself
        if user_id_to_remove == callback.from_user.id:
            raise ValueError("Нельзя удалить самого себя")
            
        # Remove the user
        config["telegram"]["bot"]["signed_users"].remove(user_id_to_remove)
        sett.set("config", config)
        
        # Show success message and refresh the users list
        await throw_float_message(
            state=state,
            message=callback.message,
            text=f"✅ Пользователь {user_id_to_remove} успешно удалён",
            reply_markup=templ.settings_users_kb(),
            callback=callback
        )
        
    except Exception as e:
        error_msg = str(e) or "Произошла ошибка при удалении пользователя"
        await throw_float_message(
            state=state,
            message=callback.message,
            text=f"❌ {error_msg}",
            reply_markup=templ.settings_users_kb(),
            callback=callback
        )

@router.callback_query(F.data == "switch_password_auth_enabled")
async def callback_switch_password_auth(callback: CallbackQuery, state: FSMContext):
    try:
        config = sett.get("config")
        # Toggle the setting
        current = config["telegram"]["bot"].get("password_auth_enabled", True)
        config["telegram"]["bot"]["password_auth_enabled"] = not current
        sett.set("config", config)
        
        # Refresh the users list
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.settings_users_text(),
            reply_markup=templ.settings_users_kb(),
            callback=callback
        )
        
    except Exception as e:
        error_msg = str(e) or "Произошла ошибка при изменении настроек"
        await throw_float_message(
            state=state,
            message=callback.message,
            text=f"❌ {error_msg}",
            reply_markup=templ.settings_users_kb(),
            callback=callback
        )
