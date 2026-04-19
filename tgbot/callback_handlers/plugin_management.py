import html
import os
import shutil
import tempfile
from pathlib import Path

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile

import paths

from core.plugins import deactivate_plugin, get_plugin_by_uuid, resolve_plugin_source_path

from .. import callback_datas as calls
from .. import states
from .. import templates as templ
from ..helpful import throw_float_message


router = Router()


def _prepare_plugin_artifact(plugin_path: Path) -> tuple[Path, str, Path | None]:
    """
    Подготавливает файл для отправки в Telegram.
    Если плагин — папка, создаёт временный zip.
    """
    if plugin_path.is_dir():
        temp_dir = Path(tempfile.mkdtemp(prefix="seal_plugin_export_"))
        archive_base = temp_dir / plugin_path.name
        archive_path = shutil.make_archive(
            str(archive_base),
            "zip",
            root_dir=str(plugin_path.parent),
            base_dir=plugin_path.name,
        )
        archive_file = Path(archive_path)
        return archive_file, archive_file.name, temp_dir

    return plugin_path, plugin_path.name, None


def _cleanup_temp_dir(temp_dir: Path | None) -> None:
    if not temp_dir:
        return
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
    except OSError:
        pass


def _delete_plugin_source(plugin_path: Path) -> None:
    plugins_root = Path(paths.PLUGINS_DIR).resolve()
    target_path = plugin_path.resolve()
    if plugins_root != target_path and plugins_root not in target_path.parents:
        raise ValueError("Некорректный путь удаления плагина")

    if plugin_path.is_dir():
        shutil.rmtree(plugin_path)
    else:
        os.remove(plugin_path)


async def _get_selected_plugin(state: FSMContext):
    data = await state.get_data()
    plugin_uuid = data.get("plugin_uuid")
    if not plugin_uuid:
        raise Exception("❌ UUID плагина не был найден, повторите процесс с самого начала")

    plugin = get_plugin_by_uuid(plugin_uuid)
    if not plugin:
        raise Exception("❌ Плагин с этим UUID не был найден, повторите процесс с самого начала")

    last_page = data.get("last_page", 0)
    return plugin_uuid, plugin, last_page


@router.callback_query(F.data == "plugin_add_warning")
async def callback_plugin_add_warning(callback: CallbackQuery, state: FSMContext):
    await state.set_state(None)
    data = await state.get_data()
    last_page = data.get("last_page", 0)

    text = templ.do_action_text(
        "⚠️ <b>Внимание перед загрузкой плагина</b>\n\n"
        "Загрузка неофициальных плагинов может быть <b>опасной</b>:\n"
        "плагин получает доступ к данным и функционалу бота.\n\n"
        "Загружайте только плагины из доверенных источников.\n"
        "Купить официальные плагины: <b>@leizov</b>\n\n"
        "Подтвердить переход к загрузке плагина?"
    )
    await throw_float_message(
        state=state,
        message=callback.message,
        text=text,
        reply_markup=templ.confirm_kb(
            confirm_cb="plugin_add_start",
            cancel_cb=calls.PluginsPagination(page=last_page).pack(),
        ),
        callback=callback,
    )


@router.callback_query(F.data == "plugin_add_start")
async def callback_plugin_add_start(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    last_page = data.get("last_page", 0)
    await state.set_state(states.PluginStates.waiting_for_plugin_file)
    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.do_action_text(
            "📥 Отправьте файл плагина в чат.\n\n"
            "Поддерживаются любые файлы плагинов, включая <code>.py</code>, <code>.pyd</code>, <code>.so</code> и другие.\n"
            "Для отмены нажмите <b>Назад</b>."
        ),
        reply_markup=templ.back_kb(calls.PluginsPagination(page=last_page).pack()),
        callback=callback,
    )


@router.callback_query(F.data == "plugin_delete_ask")
async def callback_plugin_delete_ask(callback: CallbackQuery, state: FSMContext):
    try:
        await state.set_state(None)
        plugin_uuid, plugin, _ = await _get_selected_plugin(state)
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.do_action_text(
                f"🗑 Подтвердите удаление плагина <b>{html.escape(plugin.meta.name)}</b>.\n\n"
                "Перед удалением я отправлю файл плагина в чат."
            ),
            reply_markup=templ.confirm_kb(
                confirm_cb="plugin_delete_confirm",
                cancel_cb=calls.PluginPage(uuid=plugin_uuid).pack(),
            ),
            callback=callback,
        )
    except Exception as e:
        try:
            await callback.answer()
        except Exception:
            pass
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.plugin_page_float_text(e),
            reply_markup=templ.back_kb(calls.PluginsPagination(page=last_page).pack()),
            callback=callback,
        )


@router.callback_query(F.data == "plugin_export")
async def callback_plugin_export(callback: CallbackQuery, state: FSMContext):
    temp_dir: Path | None = None
    try:
        await state.set_state(None)
        plugin_uuid, plugin, last_page = await _get_selected_plugin(state)
        plugin_path = resolve_plugin_source_path(plugin)
        if plugin_path is None or not plugin_path.exists():
            raise Exception("❌ Файл/папка плагина не найдены в директории plugins/")

        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.do_action_text("📤 Выгружаю плагин, подождите..."),
            reply_markup=templ.destroy_kb(),
            callback=callback,
        )

        artifact_path, artifact_name, temp_dir = _prepare_plugin_artifact(plugin_path)
        await callback.message.answer_document(
            document=FSInputFile(str(artifact_path), filename=artifact_name),
            caption=(
                "📦 <b>Плагин выгружен</b>\n"
                f"Имя: <code>{html.escape(artifact_name)}</code>"
            ),
            parse_mode="HTML",
        )

        await state.update_data(plugin_uuid=plugin_uuid)
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.plugin_page_text(plugin_uuid),
            reply_markup=templ.plugin_page_kb(plugin_uuid, last_page),
        )
    except Exception as e:
        try:
            await callback.answer()
        except Exception:
            pass
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.plugin_page_float_text(e),
            reply_markup=templ.back_kb(calls.PluginsPagination(page=last_page).pack()),
        )
    finally:
        _cleanup_temp_dir(temp_dir)


@router.callback_query(F.data == "plugin_delete_confirm")
async def callback_plugin_delete_confirm(callback: CallbackQuery, state: FSMContext):
    temp_dir: Path | None = None
    try:
        await state.set_state(None)
        _, plugin, last_page = await _get_selected_plugin(state)
        plugin_path = resolve_plugin_source_path(plugin)
        if plugin_path is None or not plugin_path.exists():
            raise Exception("❌ Файл/папка плагина не найдены в директории plugins/")

        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.do_action_text("🗑 Удаляю плагин, подождите..."),
            reply_markup=templ.destroy_kb(),
            callback=callback,
        )

        artifact_path, artifact_name, temp_dir = _prepare_plugin_artifact(plugin_path)
        await callback.message.answer_document(
            document=FSInputFile(str(artifact_path), filename=artifact_name),
            caption=(
                "📦 <b>Копия плагина перед удалением</b>\n"
                f"Имя: <code>{html.escape(artifact_name)}</code>"
            ),
            parse_mode="HTML",
        )

        deactivated = await deactivate_plugin(plugin.uuid)
        if plugin.enabled and not deactivated:
            raise Exception("❌ Не удалось деактивировать плагин перед удалением")
        _delete_plugin_source(plugin_path)

        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.plugins_text(),
            reply_markup=templ.plugins_kb(last_page),
        )
    except Exception as e:
        try:
            await callback.answer()
        except Exception:
            pass
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.plugin_page_float_text(e),
            reply_markup=templ.back_kb(calls.PluginsPagination(page=last_page).pack()),
        )
    finally:
        _cleanup_temp_dir(temp_dir)
