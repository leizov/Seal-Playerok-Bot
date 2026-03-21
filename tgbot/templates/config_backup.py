from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .. import callback_datas as calls


CONFIG_BACKUP_MENU_CB = "config_backup_menu"
CONFIG_BACKUP_EXPORT_CB = "config_backup_export"
CONFIG_BACKUP_IMPORT_CB = "config_backup_import_start"
CONFIG_BACKUP_CONFIRM_CB = "config_backup_import_confirm"
CONFIG_BACKUP_CANCEL_CB = "config_backup_import_cancel"


def _join_lines(*lines: str) -> str:
    return "\n".join(lines).strip()


def config_backup_warning_block() -> str:
    return _join_lines(
        "🛑 <b>Не передавайте backup-файл третьим лицам.</b>",
        "Тот, кто получит этот файл, может получить доступ к боту,",
        "данным плагинов и аккаунту Playerok.",
    )


def config_backup_text() -> str:
    return _join_lines(
        "💾 <b>Управление backup-конфигом</b>",
        "",
        "📤 <b>Выгрузить backup</b> — скачать текущий файл конфигурации.",
        "📥 <b>Загрузить backup</b> — восстановить данные из своего файла.",
        "",
        config_backup_warning_block(),
        "",
        "👇 Выберите действие:",
    )


def config_backup_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="📤 Выгрузить backup", callback_data=CONFIG_BACKUP_EXPORT_CB)],
        [InlineKeyboardButton(text="📥 Загрузить backup", callback_data=CONFIG_BACKUP_IMPORT_CB)],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.MenuPagination(page=1).pack())],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def config_backup_wait_file_text() -> str:
    return _join_lines(
        "📥 <b>Загрузка backup</b>",
        "",
        "1. Отправьте сюда <b>.json</b> backup-файл.",
        "2. Я проверю формат и покажу сводку.",
        "3. После подтверждения заменю данные.",
        "",
        config_backup_warning_block(),
    )


def config_backup_wait_file_error_text(error: str) -> str:
    return _join_lines(
        "❌ <b>Файл backup не принят</b>",
        "",
        f"<blockquote>{error}</blockquote>",
        "",
        "📎 Отправьте корректный <b>.json</b> backup-файл.",
    )


def config_backup_confirm_text(summary_html: str) -> str:
    return _join_lines(
        "⚠️ <b>Подтверждение восстановления</b>",
        "",
        "Будет выполнена замена данных в:",
        "• <code>bot_settings</code>",
        "• <code>storage/plugins</code> (по папкам плагинов)",
        "",
        "📊 <b>Содержимое загруженного backup:</b>",
        summary_html,
        "",
        "🛟 Перед заменой я отправлю текущий backup как точку отката.",
        "Если отправить его не получится, замена будет отменена.",
        "",
        config_backup_warning_block(),
        "",
        "Подтвердить восстановление?",
    )


def config_backup_export_caption(summary_html: str) -> str:
    return _join_lines(
        "✅ <b>Backup успешно выгружен</b>",
        "",
        summary_html,
        "",
        config_backup_warning_block(),
    )


def config_backup_before_restore_caption(summary_html: str) -> str:
    return _join_lines(
        "🛟 <b>Текущий backup перед заменой</b>",
        "",
        summary_html,
    )


def config_backup_before_restore_text() -> str:
    return _join_lines(
        "📦 <b>Отправляю текущий backup перед восстановлением...</b>",
        "",
        config_backup_warning_block(),
    )


def config_backup_in_progress_text() -> str:
    return _join_lines(
        "⏳ <b>Применяю backup...</b>",
        "",
        "Пожалуйста, подождите. Идёт замена данных.",
    )


def config_backup_success_text() -> str:
    return _join_lines(
        "✅ <b>Backup успешно применён</b>",
        "",
        "Изменения записаны.",
        "🔄 Выполните <code>/restart</code>, чтобы применить их в работе бота.",
    )
