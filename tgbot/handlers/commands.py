import asyncio
import html
import logging
import os
import platform
import shutil
import socket
import sys
import threading
import time
from datetime import datetime
from aiogram import types, Router, Bot, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile

from __init__ import SKIP_UPDATES
import paths
from core.config_backup import create_backup_payload, format_backup_summary, save_backup_payload_to_file
from settings import Settings as sett
from core.utils import restart as app_restart
from updater import get_update_status, install_release_update

from .. import templates as templ
from ..helpful import throw_float_message, do_auth


router = Router()
logger = logging.getLogger("seal.telegram.commands")
_PROCESS_START_TS = time.time()

try:
    import psutil  # type: ignore
except Exception:
    psutil = None


def _split_long_text(text: str, limit: int = 3500) -> list[str]:
    """
    Делит длинный текст на части для отправки в Telegram.
    """
    text = (text or "").strip()
    if not text:
        return []

    chunks: list[str] = []
    remaining = text

    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break

        split_at = remaining.rfind("\n", 0, limit)
        if split_at < 1:
            split_at = remaining.rfind(" ", 0, limit)
        if split_at < 1:
            split_at = limit

        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()

    return chunks


def _probe_playerok_account(config: dict):
    """
    Выполняет один реальный запрос к Playerok API и возвращает аккаунт.
    Бросает исключение при ошибке подключения.
    """
    from playerokapi.account import Account

    api_cfg = (config or {}).get("playerok", {}).get("api", {})
    return Account(
        token=api_cfg.get("token", ""),
        user_agent=api_cfg.get("user_agent", ""),
        requests_timeout=api_cfg.get("requests_timeout", 10),
        proxy=api_cfg.get("proxy") or None,
    ).get()


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _health_circles(level: int) -> str:
    normalized = max(1, min(5, _safe_int(level, 5)))
    return ("\U0001F7E2" * normalized) + ("\u26AA" * (5 - normalized))


def _get_playerok_health_snapshot() -> dict:
    try:
        from core.error_stats import get_playerok_connection_health

        health = get_playerok_connection_health()
        if isinstance(health, dict):
            return health
    except Exception as e:
        logger.debug("Не удалось получить health snapshot Playerok: %s", e)

    return {
        "window_minutes": 10,
        "errors_10m": 0,
        "fatal_streak": 0,
        "incident_active": False,
        "level": 5,
        "circles": _health_circles(5),
    }


def _format_playerok_stability_block() -> str:
    health = _get_playerok_health_snapshot()
    window_minutes = max(1, _safe_int(health.get("window_minutes"), 10))
    errors_10m = max(0, _safe_int(health.get("errors_10m"), 0))
    fatal_streak = max(0, _safe_int(health.get("fatal_streak"), 0))
    level = max(1, min(5, _safe_int(health.get("level"), 5)))
    circles = str(health.get("circles") or _health_circles(level))
    incident_text = "Да" if bool(health.get("incident_active")) else "Нет"

    return (
        f"\n\n<b>Стабильность за {window_minutes} минут:</b>\n"
        f"{circles} <b>{level}/5</b>\n"
        f"• Ошибки: <b>{errors_10m}</b>\n"
        f"• Фатальный стрик: <b>{fatal_streak}</b>\n"
        f"• Инцидент: <b>{incident_text}</b>"
    )


def _format_bytes(size_bytes: int | float | None) -> str:
    if size_bytes is None:
        return "н/д"
    try:
        value = float(size_bytes)
    except Exception:
        return "н/д"

    if value < 0:
        return "н/д"

    units = ["Б", "КБ", "МБ", "ГБ", "ТБ", "ПБ"]
    unit_idx = 0
    while value >= 1024 and unit_idx < len(units) - 1:
        value /= 1024
        unit_idx += 1
    return f"{value:.2f} {units[unit_idx]}"


def _safe_percent(used: float | int, total: float | int) -> str:
    try:
        used_f = float(used)
        total_f = float(total)
        if total_f <= 0:
            return "н/д"
        return f"{(used_f / total_f) * 100:.2f}%"
    except Exception:
        return "н/д"


def _get_dir_size(path: str) -> int:
    total = 0
    stack = [path]

    while stack:
        current = stack.pop()
        with os.scandir(current) as entries:
            for entry in entries:
                try:
                    if entry.is_symlink():
                        continue
                    if entry.is_file(follow_symlinks=False):
                        total += entry.stat(follow_symlinks=False).st_size
                    elif entry.is_dir(follow_symlinks=False):
                        stack.append(entry.path)
                except OSError:
                    continue
    return total


def _try_get_system_memory_without_psutil() -> tuple[int, int, int, float] | None:
    if os.name != "nt":
        return None

    try:
        import ctypes
    except Exception:
        return None

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MEMORYSTATUSEX()
    status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ok = ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
    if not ok:
        return None

    total = int(status.ullTotalPhys)
    available = int(status.ullAvailPhys)
    used = max(0, total - available)
    percent = float(status.dwMemoryLoad)
    return total, used, available, percent


def _build_sys_report() -> str:
    warnings: list[str] = []

    now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except Exception:
        local_ip = "н/д"
        warnings.append("Не удалось определить локальный IP по hostname.")

    os_text = platform.platform(aliased=True)
    process_id = os.getpid()

    ram_used_line = "н/д"
    ram_available_line = "н/д"
    swap_line = "н/д"
    bot_rss = "н/д"
    bot_vms = "н/д"
    bot_mem_percent = "н/д"

    net_sent = "н/д"
    net_recv = "н/д"
    net_packets = "н/д"

    process_threads = "н/д"
    process_files = "н/д"
    process_start_text = datetime.fromtimestamp(_PROCESS_START_TS).strftime("%Y-%m-%d %H:%M:%S")

    if psutil is not None:
        proc = None
        try:
            proc = psutil.Process(process_id)
        except Exception as e:
            warnings.append(f"Не удалось получить объект процесса через psutil: {e}")

        if proc is not None:
            try:
                mem_info = proc.memory_info()
                bot_rss = _format_bytes(mem_info.rss)
                bot_vms = _format_bytes(mem_info.vms)
            except Exception as e:
                warnings.append(f"Не удалось получить память процесса: {e}")

            try:
                bot_mem_percent = f"{proc.memory_percent():.4f}%"
            except Exception as e:
                warnings.append(f"Не удалось получить % памяти процесса: {e}")

            try:
                process_threads = str(proc.num_threads())
            except Exception as e:
                warnings.append(f"Не удалось получить число потоков процесса: {e}")

            try:
                process_files = str(len(proc.open_files()))
            except Exception as e:
                warnings.append(f"Не удалось получить число открытых файлов процесса: {e}")

            try:
                process_start_ts = float(proc.create_time())
                process_start_text = datetime.fromtimestamp(process_start_ts).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass

        try:
            vm = psutil.virtual_memory()
            ram_used_line = f"{_format_bytes(vm.used)} / {_format_bytes(vm.total)} ({vm.percent:.2f}%)"
            ram_available_line = _format_bytes(vm.available)
        except Exception as e:
            warnings.append(f"Не удалось получить данные RAM: {e}")

        try:
            sm = psutil.swap_memory()
            swap_line = f"{_format_bytes(sm.used)} / {_format_bytes(sm.total)} ({sm.percent:.2f}%)"
        except Exception as e:
            warnings.append(f"Не удалось получить данные swap: {e}")

        try:
            net = psutil.net_io_counters()
            net_sent = _format_bytes(net.bytes_sent)
            net_recv = _format_bytes(net.bytes_recv)
            net_packets = f"{net.packets_sent} / {net.packets_recv}"
        except Exception as e:
            warnings.append(f"Не удалось получить сетевые счётчики: {e}")
    else:
        warnings.append("Модуль psutil не установлен, часть метрик недоступна.")

        fallback_mem = _try_get_system_memory_without_psutil()
        if fallback_mem is not None:
            total, used, available, percent = fallback_mem
            ram_used_line = f"{_format_bytes(used)} / {_format_bytes(total)} ({percent:.2f}%)"
            ram_available_line = _format_bytes(available)
        else:
            warnings.append("Не удалось получить RAM fallback-методом.")
    if process_threads == "н/д":
        process_threads = str(threading.active_count())

    disk_total = None
    disk_used = None
    disk_free = None
    disk_percent = "н/д"
    try:
        usage = shutil.disk_usage(paths.ROOT_DIR)
        disk_total = int(usage.total)
        disk_used = int(usage.used)
        disk_free = int(usage.free)
        disk_percent = _safe_percent(disk_used, disk_total)
    except Exception as e:
        warnings.append(f"Не удалось получить использование диска: {e}")

    bot_dirs = [
        ("bot_settings", paths.BOT_SETTINGS_DIR),
        ("bot_data", paths.BOT_DATA_DIR),
        ("logs", paths.LOGS_DIR),
        ("storage", paths.STORAGE_DIR),
    ]
    bot_dir_sizes: list[tuple[str, str]] = []
    bot_total_size = 0
    for label, path in bot_dirs:
        try:
            size = _get_dir_size(path)
            bot_total_size += size
            bot_dir_sizes.append((label, _format_bytes(size)))
        except Exception as e:
            bot_dir_sizes.append((label, "н/д"))
            warnings.append(f"Не удалось посчитать размер директории {label}: {e}")

    playerok_status = "н/д"
    try:
        from plbot.playerokbot import get_playerok_bot
        plbot = get_playerok_bot()
        if plbot is None:
            playerok_status = "⚪️ Не инициализирован"
        elif getattr(plbot, "is_connected", False):
            playerok_status = "🟢 Подключен"
        else:
            playerok_status = "🔴 Не подключен"
    except Exception as e:
        warnings.append(f"Не удалось получить статус Playerok в памяти: {e}")

    warning_block = ""
    if warnings:
        unique_warnings = []
        for item in warnings:
            text = str(item).strip()
            if not text:
                continue
            if text not in unique_warnings:
                unique_warnings.append(text)

        warning_lines = []
        for warn in unique_warnings[:8]:
            escaped = html.escape(warn)
            if len(escaped) > 120:
                escaped = escaped[:117] + "..."
            warning_lines.append(f"• {escaped}")

        warning_block = (
            "\n⚠️ <b>Ограничения диагностики</b>\n"
            + "\n".join(warning_lines)
        )
    else:
        warning_block = "\n✅ <i>Все ключевые метрики успешно собраны.</i>"

    report_lines: list[str] = [
        "🧪 <b>Подробная диагностика системы</b>",
        f"🕒 <b>Время:</b> <code>{html.escape(now_text)}</code>",
        "",
        "🖥️ <b>Общая информация</b>",
        f"• Хост: <code>{html.escape(hostname)}</code>",
        f"• Локальный IP: <code>{html.escape(local_ip)}</code>",
        f"• ОС: <code>{html.escape(os_text)}</code>",
        f"• PID процесса: <code>{process_id}</code>",
        f"• Platform: <code>{html.escape(sys.platform)}</code>",
    ]

    memory_lines: list[str] = []
    if ram_used_line != "н/д":
        memory_lines.append(f"• RAM (система): <b>{html.escape(ram_used_line)}</b>")
    if ram_available_line != "н/д":
        memory_lines.append(f"• RAM доступно: <b>{html.escape(ram_available_line)}</b>")
    if bot_mem_percent != "н/д":
        memory_lines.append(f"• Доля RAM бота: <b>{html.escape(bot_mem_percent)}</b>")

    if memory_lines:
        report_lines.extend(["", "🧠 <b>Память</b>", *memory_lines])

    report_lines.extend([
        "",
        "💾 <b>Диск и хранилище</b>",
        f"• Диск проекта: <b>{_format_bytes(disk_used)}</b> / <b>{_format_bytes(disk_total)}</b> ({disk_percent})",
        f"• Свободно на диске: <b>{_format_bytes(disk_free)}</b>",
        f"• Размер данных бота: <b>{_format_bytes(bot_total_size)}</b>",
    ])
    report_lines.extend([f"• {html.escape(name)}: <b>{html.escape(size)}</b>" for name, size in bot_dir_sizes])

    network_lines: list[str] = []
    if net_sent != "н/д":
        network_lines.append(f"• Отправлено (система): <b>{html.escape(net_sent)}</b>")
    if net_recv != "н/д":
        network_lines.append(f"• Получено (система): <b>{html.escape(net_recv)}</b>")
    if network_lines:
        report_lines.extend(["", "🌐 <b>Сеть</b>", *network_lines])

    process_lines = [
        f"• Старт процесса: <code>{html.escape(process_start_text)}</code>",
        f"• Потоки процесса: <b>{html.escape(process_threads)}</b>",
        f"• Открытые файлы: <b>{html.escape(process_files)}</b>",
        f"• Playerok (в памяти): <b>{playerok_status}</b>",
        f"• Диагностический backend: <b>{'psutil' if psutil is not None else 'fallback'}</b>",
    ]
    report_lines.extend(["", "🤖 <b>Процесс бота</b>", *process_lines, warning_block])

    report = "\n".join(report_lines)

    return report


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


@router.message(Command("deals"))
async def handler_deals(message: types.Message, state: FSMContext):
    """
    Обработчик команды /deals
    Открывает меню поиска и фильтрации сделок.
    """
    await state.set_state(None)
    config = sett.get("config")
    if message.from_user.id not in config["telegram"]["bot"]["signed_users"]:
        return await do_auth(message, state)

    from ..callback_handlers.deals import show_deals_menu

    await show_deals_menu(message, state, reset=True, force_reload=True)


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
        await message.answer(
            "🔄 <b>Перезагрузка бота...</b>",
            parse_mode="HTML"
        )
        await asyncio.sleep(0.5)
        app_restart()
        
    except Exception as e:
        await message.answer(f"❌ Произошла ошибка при перезагрузке: {str(e)}")


@router.message(Command("update"))
async def handler_update(message: types.Message, state: FSMContext):
    """
    Обработчик команды /update
    Проверяет наличие новой версии и обновляет бота вручную.
    """
    config = sett.get("config")
    if message.from_user.id not in config["telegram"]["bot"].get("signed_users", []):
        return await do_auth(message, state)

    await state.set_state(None)
    await throw_float_message(
        state=state,
        message=message,
        text=templ.do_action_text("🔎 Проверяю наличие обновлений..."),
        reply_markup=templ.destroy_kb(),
    )

    loop = asyncio.get_running_loop()
    update_status = await loop.run_in_executor(None, get_update_status)
    status = update_status.get("status")
    current_version = update_status.get("current_version") or "unknown"
    latest_version = update_status.get("latest_version") or "unknown"

    if status == "error":
        error_message = html.escape(str(update_status.get("error") or "Неизвестная ошибка"))
        await throw_float_message(
            state=state,
            message=message,
            text=templ.do_action_text(
                f"❌ Не удалось проверить обновления: <code>{error_message}</code>"
            ),
            reply_markup=templ.destroy_kb(),
        )
        return

    if status == "no_releases":
        await throw_float_message(
            state=state,
            message=message,
            text=templ.do_action_text("ℹ️ В репозитории пока нет релизов."),
            reply_markup=templ.destroy_kb(),
        )
        return

    if status == "version_not_found":
        await throw_float_message(
            state=state,
            message=message,
            text=templ.do_action_text(
                f"ℹ️ Текущая версия <code>{current_version}</code> не найдена среди релизов.\n"
                f"Последняя версия: <code>{latest_version}</code>"
            ),
            reply_markup=templ.destroy_kb(),
        )
        return

    if status == "up_to_date":
        await throw_float_message(
            state=state,
            message=message,
            text=templ.do_action_text(
                f"✅ У вас уже установлена последняя версия: <code>{current_version}</code>"
            ),
            reply_markup=templ.destroy_kb(),
        )
        return

    if status != "update_available":
        await throw_float_message(
            state=state,
            message=message,
            text=templ.do_action_text("ℹ️ Обновление не требуется."),
            reply_markup=templ.destroy_kb(),
        )
        return

    if SKIP_UPDATES:
        await throw_float_message(
            state=state,
            message=message,
            text=templ.do_action_text(
                "⏭ Установка обновления пропущена, потому что "
                "<code>SKIP_UPDATES=True</code> в <code>__init__.py</code>."
            ),
            reply_markup=templ.destroy_kb(),
        )
        return

    backup_path = None
    try:
        await throw_float_message(
            state=state,
            message=message,
            text=templ.do_action_text("📦 Формирую backup перед обновлением..."),
            reply_markup=templ.destroy_kb(),
        )

        backup_payload = await loop.run_in_executor(None, create_backup_payload)
        backup_path = await loop.run_in_executor(
            None,
            save_backup_payload_to_file,
            backup_payload,
            "seal_config_backup",
        )
        backup_summary = format_backup_summary(backup_payload)

        await message.answer(
            text=templ.config_backup_warning_block(),
            parse_mode="HTML",
        )
        await message.answer_document(
            document=FSInputFile(backup_path, filename=os.path.basename(backup_path)),
            caption=templ.config_backup_export_caption(backup_summary),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.exception("Ошибка при формировании backup перед обновлением: %s", e)
        await throw_float_message(
            state=state,
            message=message,
            text=templ.do_action_text(
                f"❌ Не удалось отправить backup перед обновлением: "
                f"<code>{html.escape(str(e))}</code>\n"
                "Обновление отменено."
            ),
            reply_markup=templ.destroy_kb(),
        )
        return
    finally:
        if backup_path and os.path.exists(backup_path):
            try:
                os.remove(backup_path)
            except OSError:
                pass

    try:
        await throw_float_message(
            state=state,
            message=message,
            text=templ.do_action_text(
                f"⬇️ Устанавливаю обновление до версии <code>{latest_version}</code>..."
            ),
            reply_markup=templ.destroy_kb(),
        )

        install_status = await loop.run_in_executor(
            None,
            install_release_update,
            update_status["latest_release"],
            False,
        )
        install_result = install_status.get("status")

        if install_result == "updated":
            await throw_float_message(
                state=state,
                message=message,
                text=templ.do_action_text(
                    f"✅ Обновление <code>{latest_version}</code> установлено. Перезапускаю бота..."
                ),
                reply_markup=templ.destroy_kb(),
            )

            release_info = update_status.get("latest_release") or {}
            release_body = str(release_info.get("body") or "").strip()
            if release_body:
                release_chunks = _split_long_text(release_body)
                total_chunks = len(release_chunks)
                for index, chunk in enumerate(release_chunks, start=1):
                    suffix = f" ({index}/{total_chunks})" if total_chunks > 1 else ""
                    await message.answer(
                        f"📝 Описание релиза {latest_version}{suffix}:\n\n{chunk}"
                    )
            else:
                await message.answer(
                    f"📝 Описание релиза {latest_version} отсутствует на GitHub."
                )

            await asyncio.sleep(0.5)
            app_restart()
            return

        if install_result == "download_failed":
            fail_text = "❌ Не удалось скачать файлы обновления."
        elif install_result == "install_failed":
            fail_text = "❌ Обновление скачано, но установить его не удалось."
        else:
            fail_text = (
                "❌ Не удалось установить обновление: "
                f"<code>{html.escape(str(install_status.get('error') or 'Неизвестная ошибка'))}</code>"
            )

        await throw_float_message(
            state=state,
            message=message,
            text=templ.do_action_text(fail_text),
            reply_markup=templ.destroy_kb(),
        )
    except Exception as e:
        logger.exception("Ошибка при ручном обновлении: %s", e)
        await throw_float_message(
            state=state,
            message=message,
            text=templ.do_action_text(
                f"❌ Ошибка при установке обновления: <code>{html.escape(str(e))}</code>"
            ),
            reply_markup=templ.destroy_kb(),
        )


@router.message(Command("config_backup"))
async def handler_config_backup(message: types.Message, state: FSMContext):
    """
    Обработчик команды /config_backup
    Показывает меню управления backup-конфигом
    """
    await state.set_state(None)
    config = sett.get("config")
    if message.from_user.id not in config["telegram"]["bot"].get("signed_users", []):
        return await do_auth(message, state)

    await throw_float_message(
        state=state,
        message=message,
        text=templ.config_backup_text(),
        reply_markup=templ.config_backup_kb()
    )


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
    Генерирует fingerprint для привязки лицензии к боту
    
    ВАЖНО: Fingerprint использует ТОЛЬКО Bot ID!
    FINGERPRINT = SHA256(BOT_ID)[:32]
    
    Это гарантирует что плагин работает только с конкретным ботом.
    """
    config = sett.get("config")
    
    # Проверяем авторизацию
    if message.from_user.id not in config["telegram"]["bot"].get("signed_users", []):
        return await do_auth(message, state)
    
    try:
        import hashlib
        
        # ═══════════════════════════════════════════════════════════════
        # 1. ПОЛУЧАЕМ BOT ID
        # ═══════════════════════════════════════════════════════════════
        bot_info = await bot.get_me()
        bot_id = bot_info.id
        
        # ═══════════════════════════════════════════════════════════════
        # 2. ГЕНЕРИРУЕМ FINGERPRINT (ТОЛЬКО Bot ID)
        # ═══════════════════════════════════════════════════════════════
        fingerprint_raw = str(bot_id)
        fingerprint_full = hashlib.sha256(fingerprint_raw.encode()).hexdigest()
        
        # Берём первые 32 символа для отображения
        fingerprint = fingerprint_full[:32].upper()
        formatted = "-".join([fingerprint[i:i+4] for i in range(0, 32, 4)])
        
        await message.answer(
            f"🦭 <b>Твой Fingerprint V3</b>\n\n"
            f"<code>{formatted}</code>\n\n"
            f"📋 <i>Скопируй и отправь при покупке плагина.</i>\n"
            f"🔒 <i>Плагин будет привязан ТОЛЬКО к этому боту!</i>\n\n",

            parse_mode="HTML"
        )
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при генерации fingerprint: {str(e)}")


@router.message(Command("sys"))
async def handler_sys(message: types.Message, state: FSMContext):
    """
    Обработчик команды /sys
    Показывает подробную диагностику системы и процесса бота.
    """
    config = sett.get("config")

    if message.from_user.id not in config["telegram"]["bot"].get("signed_users", []):
        return await do_auth(message, state)

    await state.set_state(None)
    checking_msg = await message.answer(
        "🧪 <b>Собираю подробную диагностику системы...</b>",
        parse_mode="HTML",
    )

    try:
        loop = asyncio.get_running_loop()
        report_text = await loop.run_in_executor(None, _build_sys_report)
        await checking_msg.edit_text(report_text, parse_mode="HTML")
    except Exception as e:
        logger.exception("Ошибка при выполнении команды /sys: %s", e)
        err = html.escape(str(e))
        await checking_msg.edit_text(
            "❌ <b>Не удалось собрать системную диагностику</b>\n\n"
            f"<code>{err[:250]}</code>\n\n"
            "<i>Проверьте доступность системных методов и повторите команду.</i>",
            parse_mode="HTML",
        )


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
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from .. import callback_datas as calls

        probe_account = None
        last_error = None
        loop = asyncio.get_running_loop()

        # Делаем 2 реальных запроса к Playerok.
        for attempt in range(1, 3):
            try:
                probe_account = await loop.run_in_executor(None, _probe_playerok_account, config)
                last_error = None
                break
            except Exception as e:
                last_error = e
                if attempt == 1:
                    await checking_msg.edit_text(
                        "❌ <b>Не удаётся подключиться, пробую ещё...</b>",
                        parse_mode="HTML",
                    )
                    await asyncio.sleep(0.4)

        stability_block = _format_playerok_stability_block()

        if probe_account:
            # Подключено
            try:
                username = probe_account.profile.username
                user_id = probe_account.profile.id
            except Exception:
                username = "Неизвестно"
                user_id = "Неизвестно"

            proxy_status = "🟢 Активен" if config["playerok"]["api"]["proxy"] else "⚫ Не используется"

            text = (
                f"🟢 <b>Playerok подключен</b>\n\n"
                f"<b>Аккаунт:</b> @{username}\n"
                f"<b>ID:</b> <code>{user_id}</code>\n"
                f"<b>Прокси:</b> {proxy_status}\n\n"
                f"<i>✅ Бот работает нормально</i>"
                f"{stability_block}"
            )

            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить статус", callback_data="refresh_playerok_status")]
            ])

            await checking_msg.edit_text(text, parse_mode="HTML", reply_markup=kb)
        else:
            # После второй неудачи показываем ошибку.
            error_msg = html.escape(str(last_error) if last_error else "Неизвестная ошибка")
            text = (
                f"🔴 <b>Playerok не подключен</b>\n\n"
                f"<b>Ошибка:</b>\n<code>{error_msg[:200]}</code>\n\n"
                f"<i>⚠️ Проверьте настройки токена и прокси</i>"
                f"{stability_block}"
            )

            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Переподключить", callback_data="reconnect_playerok")],
                [InlineKeyboardButton(text="⚙️ Настройки аккаунта", callback_data=calls.SettingsNavigation(to="account").pack())]
            ])

            await checking_msg.edit_text(text, parse_mode="HTML", reply_markup=kb)
            
    except Exception as e:
        error_text = html.escape(str(e))
        stability_block = _format_playerok_stability_block()
        await checking_msg.edit_text(
            f"❌ <b>Ошибка при проверке статуса</b>\n\n"
            f"<code>{error_text[:200]}</code>"
            f"{stability_block}",
            parse_mode="HTML"
        )



@router.callback_query(F.data == "refresh_playerok_status")
async def callback_refresh_playerok_status(callback: types.CallbackQuery):
    """Обновляет статус подключения к Playerok."""
    await callback.message.edit_text("🔄 <b>Проверяю подключение к Playerok...</b>", parse_mode="HTML")
    await callback.answer()

    try:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from .. import callback_datas as calls

        config = sett.get("config")

        probe_account = None
        last_error = None
        loop = asyncio.get_running_loop()

        # Делаем 2 реальных запроса к Playerok.
        for attempt in range(1, 3):
            try:
                probe_account = await loop.run_in_executor(None, _probe_playerok_account, config)
                last_error = None
                break
            except Exception as e:
                last_error = e
                if attempt == 1:
                    await callback.message.edit_text(
                        "❌ <b>Не удаётся подключиться, пробую ещё...</b>",
                        parse_mode="HTML",
                    )
                    await asyncio.sleep(0.4)

        stability_block = _format_playerok_stability_block()

        if probe_account:
            try:
                username = probe_account.profile.username
                user_id = probe_account.profile.id
            except Exception:
                username = "Неизвестно"
                user_id = "Неизвестно"

            proxy_status = "🟢 Активен" if config["playerok"]["api"]["proxy"] else "⚫ Не используется"

            text = (
                f"🟢 <b>Playerok подключен</b>\n\n"
                f"<b>Аккаунт:</b> @{username}\n"
                f"<b>ID:</b> <code>{user_id}</code>\n"
                f"<b>Прокси:</b> {proxy_status}\n\n"
                f"<i>✅ Бот работает нормально</i>"
                f"{stability_block}"
            )

            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить статус", callback_data="refresh_playerok_status")]
            ])

            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        else:
            error_msg = html.escape(str(last_error) if last_error else "Неизвестная ошибка")
            text = (
                f"🔴 <b>Playerok не подключен</b>\n\n"
                f"<b>Ошибка:</b>\n<code>{error_msg[:200]}</code>\n\n"
                f"<i>⚠️ Проверьте настройки токена и прокси</i>"
                f"{stability_block}"
            )

            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Переподключить", callback_data="reconnect_playerok")],
                [InlineKeyboardButton(text="⚙️ Настройки аккаунта", callback_data=calls.SettingsNavigation(to="account").pack())]
            ])

            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

    except Exception as e:
        error_text = html.escape(str(e))
        stability_block = _format_playerok_stability_block()
        await callback.message.edit_text(
            f"❌ <b>Ошибка при проверке</b>\n\n<code>{error_text[:200]}</code>{stability_block}",
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

