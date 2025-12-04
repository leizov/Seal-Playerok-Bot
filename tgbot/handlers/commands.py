import asyncio
import os
import sys
from aiogram import types, Router, Bot
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
async def handler_fingerprint(message: types.Message, state: FSMContext):
    """
    Обработчик команды /fingerprint
    Генерирует HWID для привязки лицензии к железу
    
    ВАЖНО: Алгоритм должен совпадать с protection.py!
    HWID = SHA256(MAC|CPU_ID|MB_SERIAL|DISK_SERIAL)
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
        
        # Собираем аппаратные компоненты (КАК В PROTECTION.PY!)
        components = []
        
        # 1. MAC address
        components.append(hex(uuid.getnode()))
        
        # 2. CPU ID (Windows only)
        try:
            if sys.platform == "win32":
                result = subprocess.check_output('wmic cpu get processorid', 
                                                shell=True, stderr=subprocess.DEVNULL)
                cpu_id = result.decode().split("\n")[1].strip()
                if cpu_id:
                    components.append(cpu_id)
        except Exception:
            pass
        
        # 3. Motherboard serial (Windows only)
        try:
            if sys.platform == "win32":
                result = subprocess.check_output('wmic baseboard get serialnumber',
                                                shell=True, stderr=subprocess.DEVNULL)
                mb_serial = result.decode().split("\n")[1].strip()
                if mb_serial:
                    components.append(mb_serial)
        except Exception:
            pass
        
        # 4. Disk serial (Windows only)
        try:
            if sys.platform == "win32":
                result = subprocess.check_output('wmic diskdrive get serialnumber',
                                                shell=True, stderr=subprocess.DEVNULL)
                disk_serial = result.decode().split("\n")[1].strip()
                if disk_serial:
                    components.append(disk_serial)
        except Exception:
            pass
        
        # Генерируем HWID (КАК В PROTECTION.PY!)
        # ПОЛНЫЙ SHA256 хеш, первые 32 символа для отображения
        hwid_raw = '|'.join(components)
        hwid_full = hashlib.sha256(hwid_raw.encode()).hexdigest()
        
        # Для покупки используем полный хеш (64 символа)
        # Но показываем первые 32 в формате XXXX-XXXX-...
        fingerprint = hwid_full[:32].upper()
        formatted = "-".join([fingerprint[i:i+4] for i in range(0, 32, 4)])
        
        await message.answer(
            f"🦭 <b>Твой Hardware Fingerprint</b>\n\n"
            f"<code>{formatted}</code>\n\n"
            f"📋 <i>Скопируй и отправь при покупке плагина.</i>\n"
            f"🔒 <i>Плагин будет привязан к этому железу!</i>\n\n"
            f"<b>Компоненты:</b>\n"
            f"• MAC: <code>{components[0][:16]}...</code>\n"
            f"• CPU/MB/Disk: {len(components)-1} компонент(ов)",
            parse_mode="HTML"
        )
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при генерации fingerprint: {str(e)}")
