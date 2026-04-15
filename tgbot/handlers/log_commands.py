import asyncio
import os
import logging
from pathlib import Path
from typing import List, Optional

from aiogram import types, Router, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext

# Импорт путей из центрального модуля
import paths

from settings import Settings as sett
from .. import templates as templ
from .. import callback_datas as calls
from ..helpful import throw_float_message

router = Router()
logger = logging.getLogger("seal.telegram.logs")


async def _safe_edit_text(message: types.Message, text: str, reply_markup=None) -> bool:
    """Returns False when Telegram says the message is not modified."""
    try:
        await message.edit_text(text, reply_markup=reply_markup)
        return True
    except TelegramAPIError as e:
        if "message is not modified" in str(e).lower():
            return False
        raise

def get_latest_log_file() -> Optional[Path]:
    """
    Возвращает путь к последнему лог-файлу.

    :return: Path к файлу лога или None
    """
    try:
        log_dir = Path(paths.LOGS_DIR)
        if not log_dir.exists():
            return None

        log_files = sorted(
            log_dir.glob("*.log"),
            key=os.path.getmtime,
            reverse=True
        )
        return log_files[0] if log_files else None
    except Exception as e:
        logger.error(f"Ошибка при получении последнего лог-файла: {e}")
        return None

def get_latest_logs(lines: int = 100) -> Optional[str]:
    """
    Получает последние N строк из лог-файла.
    
    :param lines: Количество строк для отображения
    :return: Текст лога или сообщение об ошибке
    """
    try:
        log_dir = Path(paths.LOGS_DIR)
        if not log_dir.exists():
            return "❌ Директория с логами не найдена."

        latest_log = get_latest_log_file()
        if latest_log is None:
            return "❌ Лог-файлы не найдены."

        # Читаем последние N строк из файла
        with open(latest_log, 'r', encoding='utf-8') as f:
            log_lines = f.readlines()[-lines:]
            
        # Объединяем строки и обрезаем до 4000 символов (ограничение Telegram)
        log_text = ''.join(log_lines)
        if len(log_text) > 4000:
            log_text = "..." + log_text[-3997:]
            
        return f"📜 Последние {len(log_lines)} строк лога:\n\n{log_text}"
        
    except Exception as e:
        logger.error(f"Ошибка при чтении логов: {e}")
        return f"❌ Ошибка при чтении логов: {e}"

@router.message(Command("logs"))
async def handle_logs_command(message: types.Message, state: FSMContext):
    """
    Обработчик команды /logs
    Показывает последние 100 строк лога
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
    await _safe_edit_text(msg, log_text, reply_markup=kb)

    # Дополнительно отправляем сам лог-файл
    latest_log = get_latest_log_file()
    if latest_log is not None and latest_log.exists():
        try:
            await message.answer_document(
                types.FSInputFile(str(latest_log)),
                caption=f"📎 Файл лога: {latest_log.name}"
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке файла лога: {e}")

@router.callback_query(calls.LogsAction.filter(F.action == "refresh"))
async def refresh_logs(callback: types.CallbackQuery, callback_data: calls.LogsAction, state: FSMContext):
    """Обновление логов по нажатию кнопки"""
    log_text = await asyncio.get_event_loop().run_in_executor(None, get_latest_logs)
    
    # Проверяем, изменился ли текст логов
    if callback.message.text == log_text:
        await callback.answer("✅ Логи актуальны, обновление не требуется", show_alert=False)
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=calls.LogsAction(action="refresh").pack())],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data=calls.LogsAction(action="close").pack())]
    ])

    changed = await _safe_edit_text(callback.message, log_text, reply_markup=kb)
    if not changed:
        await callback.answer("✅ Логи уже актуальны", show_alert=False)
        return

    await callback.answer("🔄 Обновляю логи...")

@router.callback_query(calls.LogsAction.filter(F.action == "close"))
async def close_logs(callback: types.CallbackQuery, callback_data: calls.LogsAction, state: FSMContext):
    """Закрытие логов"""
    await callback.message.delete()
    await callback.answer("❌ Логи закрыты")


def find_latest_error(log_text: str) -> str:
    """Находит последнюю ошибку и её traceback в логах"""
    
    # Ищем строки с маркерами ERROR (• E) или CRITICAL (• C)
    error_lines = []
    
    for line in log_text.split('\n'):
        # Проверяем наличие маркеров ERROR или CRITICAL
        if '• E' in line or '• C' in line:
            error_lines.append(line)
    
    if not error_lines:
        return "❌ В логах не найдено ошибок."
    
    # Берем последнюю ошибку
    last_error = error_lines[-1].strip()
    
    if not last_error:
        return "❌ В логах не найдено ошибок."
    
    # Обрезаем до 4000 символов (ограничение Telegram)
    if len(last_error) > 4000:
        last_error = "..." + last_error[-3997:]
    
    return f"🛑 Последняя ошибка в логах:\n\n{last_error}"


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
    await _safe_edit_text(msg, error_text, reply_markup=kb)


@router.message(Command("api_errors", "apierrors"))
async def handle_api_errors_command(message: types.Message, state: FSMContext):
    """
    Обработчик команды /api_errors
    Показывает статистику ошибок Playerok API
    """
    config = sett.get("config")

    if message.from_user.id not in config["telegram"]["bot"].get("signed_users", []):
        return await message.answer("❌ У вас нет прав для выполнения этой команды.")

    await throw_float_message(
        state=state,
        message=message,
        text=templ.error_stats_text(),
        reply_markup=templ.error_stats_kb(),
        send=True,
    )


@router.callback_query(calls.LogsAction.filter(F.action == "show_full"))
async def show_full_logs(callback: types.CallbackQuery, callback_data: calls.LogsAction, state: FSMContext):
    """Показ полных логов по нажатию кнопки"""
    log_text = await asyncio.get_event_loop().run_in_executor(None, get_latest_logs)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=calls.LogsAction(action="refresh").pack())],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data=calls.LogsAction(action="close").pack())]
    ])

    changed = await _safe_edit_text(callback.message, log_text, reply_markup=kb)
    if not changed:
        await callback.answer("✅ Логи уже актуальны", show_alert=False)
        return

    await callback.answer("📜 Загружаю полные логи...")


@router.callback_query(calls.LogsAction.filter(F.action == "refresh_error"))
async def refresh_error(callback: types.CallbackQuery, callback_data: calls.LogsAction, state: FSMContext):
    """Обновление ошибки по нажатию кнопки"""
    full_logs = await asyncio.get_event_loop().run_in_executor(None, get_latest_logs, 1000)
    error_text = find_latest_error(full_logs)
    
    # Проверяем, изменился ли текст ошибки
    if callback.message.text == error_text:
        await callback.answer("✅ Ошибка актуальна, обновление не требуется", show_alert=False)
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Показать полные логи", callback_data=calls.LogsAction(action="show_full").pack())],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=calls.LogsAction(action="refresh_error").pack()),
         InlineKeyboardButton(text="❌ Закрыть", callback_data=calls.LogsAction(action="close").pack())]
    ])

    changed = await _safe_edit_text(callback.message, error_text, reply_markup=kb)
    if not changed:
        await callback.answer("✅ Ошибка уже актуальна", show_alert=False)
        return

    await callback.answer("🔍 Ищу последнюю ошибку...")
