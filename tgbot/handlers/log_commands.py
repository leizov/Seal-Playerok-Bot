import asyncio
import os
import logging
from pathlib import Path
from typing import List, Optional

from aiogram import types, Router, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

# Импорт путей из центрального модуля
import paths

from settings import Settings as sett
from .. import templates as templ
from .. import callback_datas as calls
from ..helpful import throw_float_message

router = Router()
logger = logging.getLogger("seal.telegram.logs")

def get_latest_logs(lines: int = 50) -> Optional[str]:
    """
    Получает последние N строк из лог-файла.
    
    :param lines: Количество строк для отображения
    :return: Текст лога или сообщение об ошибке
    """
    try:
        log_dir = Path(paths.LOGS_DIR)
        if not log_dir.exists():
            return "❌ Директория с логами не найдена."
            
        # Получаем список лог-файлов и сортируем по дате изменения
        log_files = sorted(
            log_dir.glob("*.log"),
            key=os.path.getmtime,
            reverse=True
        )
        
        if not log_files:
            return "❌ Лог-файлы не найдены."
            
        # Берем последний лог-файл
        latest_log = log_files[0]
        
        # Читаем последние N строк из файла
        with open(latest_log, 'r', encoding='utf-8') as f:
            log_lines = f.readlines()[-lines:]
            
        # Объединяем строки и обрезаем до 4000 символов (ограничение Telegram)
        log_text = ''.join(log_lines)
        if len(log_text) > 4000:
            log_text = "..." + log_text[-3997:]
            
        return f"📜 <b>Последние {len(log_lines)} строк лога:</b>\n\n<code>{log_text}</code>"
        
    except Exception as e:
        logger.error(f"Ошибка при чтении логов: {e}")
        return f"❌ Ошибка при чтении логов: {e}"

@router.message(Command("logs"))
async def handle_logs_command(message: types.Message, state: FSMContext):
    """
    Обработчик команды /logs
    Показывает последние 50 строк лога
    """
    config = sett.get("config")
    
    # Проверка прав администратора
    if message.from_user.id not in config["telegram"]["bot"].get("signed_users", []):
        return await message.answer("❌ У вас нет прав для выполнения этой команды.")
    
    # Показываем сообщение о загрузке
    msg = await message.answer("⏳ Загружаю логи...")
    
    # Получаем логи (асинхронно, чтобы не блокировать бота)
    log_text = await asyncio.get_event_loop().run_in_executor(None, get_latest_logs)
    
    # Создаем клавиатуру с кнопками
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=calls.LogsAction(action="refresh").pack())],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data=calls.LogsAction(action="close").pack())]
    ])
    
    # Обновляем сообщение с логами
    await msg.edit_text(log_text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(calls.LogsAction.filter(F.action == "refresh"))
async def refresh_logs(callback: types.CallbackQuery, callback_data: calls.LogsAction, state: FSMContext):
    """Обновление логов по нажатию кнопки"""
    log_text = await asyncio.get_event_loop().run_in_executor(None, get_latest_logs)
    
    # Проверяем, изменился ли текст логов
    if callback.message.text == log_text:
        await callback.answer("✅ Логи актуальны, обновление не требуется", show_alert=False)
        return
    
    await callback.answer("🔄 Обновляю логи...")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=calls.LogsAction(action="refresh").pack())],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data=calls.LogsAction(action="close").pack())]
    ])
    
    await callback.message.edit_text(log_text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(calls.LogsAction.filter(F.action == "close"))
async def close_logs(callback: types.CallbackQuery, callback_data: calls.LogsAction, state: FSMContext):
    """Закрытие логов"""
    await callback.message.delete()
    await callback.answer("❌ Логи закрыты")


def find_latest_error(log_text: str) -> str:
    """Находит последнюю ошибку и её traceback в логах"""
    import re
    
    # Ищем все ошибки с трейсбэками
    error_blocks = re.split(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} - .*? - (?:ERROR|CRITICAL) - .*?(?=\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} -|\Z))', 
                           log_text, 
                           flags=re.DOTALL)
    
    if len(error_blocks) < 2:
        return "❌ В логах не найдено ошибок."
    
    # Берем последнюю ошибку (нечетные элементы содержат совпадения)
    last_error = ""
    for i in range(len(error_blocks)-1, -1, -1):
        if i % 2 == 1:  # Нечетные индексы содержат совпадения
            last_error = error_blocks[i].strip()
            if last_error:  # Пропускаем пустые совпадения
                break
    
    if not last_error:
        return "❌ В логах не найдено ошибок."
    
    # Обрезаем до 4000 символов (ограничение Telegram)
    if len(last_error) > 4000:
        last_error = "..." + last_error[-3997:]
    
    return f"🛑 <b>Последняя ошибка в логах:</b>\n\n<code>{last_error}</code>"


@router.message(Command("error"))
async def handle_error_command(message: types.Message, state: FSMContext):
    """
    Обработчик команды /error
    Показывает последнюю ошибку и её traceback из логов
    """
    config = sett.get("config")
    
    # Проверка прав администратора
    if message.from_user.id not in config["telegram"]["bot"].get("signed_users", []):
        return await message.answer("❌ У вас нет прав для выполнения этой команды.")
    
    # Показываем сообщение о загрузке
    msg = await message.answer("🔍 Ищу последнюю ошибку в логах...")
    
    # Получаем логи (асинхронно, чтобы не блокировать бота)
    full_logs = await asyncio.get_event_loop().run_in_executor(None, get_latest_logs, 1000)  # Берем больше логов для поиска ошибок
    
    # Ищем последнюю ошибку
    error_text = find_latest_error(full_logs)
    
    # Создаем клавиатуру с кнопками
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Показать полные логи", callback_data=calls.LogsAction(action="show_full").pack())],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=calls.LogsAction(action="refresh_error").pack()),
         InlineKeyboardButton(text="❌ Закрыть", callback_data=calls.LogsAction(action="close").pack())]
    ])
    
    # Отправляем сообщение с ошибкой
    await msg.edit_text(error_text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(calls.LogsAction.filter(F.action == "show_full"))
async def show_full_logs(callback: types.CallbackQuery, callback_data: calls.LogsAction, state: FSMContext):
    """Показ полных логов по нажатию кнопки"""
    await callback.answer("📜 Загружаю полные логи...")
    log_text = await asyncio.get_event_loop().run_in_executor(None, get_latest_logs)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=calls.LogsAction(action="refresh").pack())],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data=calls.LogsAction(action="close").pack())]
    ])
    
    await callback.message.edit_text(log_text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(calls.LogsAction.filter(F.action == "refresh_error"))
async def refresh_error(callback: types.CallbackQuery, callback_data: calls.LogsAction, state: FSMContext):
    """Обновление ошибки по нажатию кнопки"""
    full_logs = await asyncio.get_event_loop().run_in_executor(None, get_latest_logs, 1000)
    error_text = find_latest_error(full_logs)
    
    # Проверяем, изменился ли текст ошибки
    if callback.message.text == error_text:
        await callback.answer("✅ Ошибка актуальна, обновление не требуется", show_alert=False)
        return
    
    await callback.answer("🔍 Ищу последнюю ошибку...")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Показать полные логи", callback_data=calls.LogsAction(action="show_full").pack())],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=calls.LogsAction(action="refresh_error").pack()),
         InlineKeyboardButton(text="❌ Закрыть", callback_data=calls.LogsAction(action="close").pack())]
    ])
    
    await callback.message.edit_text(error_text, reply_markup=kb, parse_mode="HTML")
