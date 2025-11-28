import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pathlib import Path
import logging

from .. import callback_datas as calls

logger = logging.getLogger("seal.telegram.logs")


def get_latest_logs(lines: int = 30) -> str:
    """
    Получает последние N строк из лог-файла.
    
    :param lines: Количество последних строк для получения
    :return: Текст лога или сообщение об ошибке
    """
    try:
        log_dir = Path("logs")
        if not log_dir.exists():
            return "❌ Директория с логами не найдена."
            
        log_files = sorted(log_dir.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
        
        if not log_files:
            return "❌ Лог-файлы не найдены."
        
        latest_log = log_files[0]
        
        with open(latest_log, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
            
            log_content = ''.join(last_lines)
            
            if len(log_content) > 3500:
                log_content = log_content[-3500:]
                log_content = "...\n" + log_content
            
            return f"📋 <b>Логи</b> ({latest_log.name})\n\n<code>{log_content}</code>"
            
    except Exception as e:
        logger.error(f"Ошибка при чтении логов: {e}")
        return f"❌ Ошибка при чтении логов: {e}"


def logs_text():
    """Текст страницы логов"""
    return get_latest_logs(30)


def logs_kb():
    """Клавиатура страницы логов"""
    rows = [
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.MenuPagination(page=1).pack()),
            InlineKeyboardButton(text="🔄️ Обновить", callback_data=calls.LogsNavigation(to="main").pack())
        ]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb
