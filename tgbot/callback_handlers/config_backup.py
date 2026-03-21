import asyncio
import html
import logging
import os

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile

from core.config_backup import (
    apply_backup_payload,
    create_backup_payload,
    format_backup_summary,
    load_backup_payload,
    save_backup_payload_to_file,
    validate_backup_payload,
)
from settings import Settings as sett

from .. import states
from .. import templates as templ
from ..helpful import throw_float_message


router = Router()
logger = logging.getLogger("seal.telegram.config_backup")


async def _remove_pending_backup_from_state(state: FSMContext) -> None:
    data = await state.get_data()
    pending_path = data.get("config_backup_pending_path")
    if pending_path and os.path.exists(pending_path):
        try:
            os.remove(pending_path)
        except OSError:
            pass
    await state.update_data(
        config_backup_pending_path=None,
        config_backup_pending_summary=None,
    )


@router.callback_query(F.data == templ.CONFIG_BACKUP_MENU_CB)
async def callback_config_backup_menu(callback: CallbackQuery, state: FSMContext):
    await _remove_pending_backup_from_state(state)
    await state.set_state(None)
    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.config_backup_text(),
        reply_markup=templ.config_backup_kb(),
        callback=callback,
    )


@router.callback_query(F.data == templ.CONFIG_BACKUP_EXPORT_CB)
async def callback_config_backup_export(callback: CallbackQuery, state: FSMContext):
    config = sett.get("config")
    if callback.from_user.id not in config["telegram"]["bot"].get("signed_users", []):
        await callback.answer("❌ Нет доступа к backup", show_alert=True)
        return

    await state.set_state(None)
    backup_path = None
    try:
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.do_action_text("📤 Формирую backup-файл..."),
            reply_markup=templ.destroy_kb(),
            callback=callback,
        )

        loop = asyncio.get_running_loop()
        payload = await loop.run_in_executor(None, create_backup_payload)
        backup_path = await loop.run_in_executor(None, save_backup_payload_to_file, payload, "seal_config_backup")
        summary = format_backup_summary(payload)

        await callback.message.answer(
            text=templ.config_backup_warning_block(),
            parse_mode="HTML",
        )
        await callback.message.answer_document(
            document=FSInputFile(backup_path, filename=os.path.basename(backup_path)),
            caption=templ.config_backup_export_caption(summary),
            parse_mode="HTML",
        )

        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.config_backup_text(),
            reply_markup=templ.config_backup_kb(),
        )
    except Exception as e:
        logger.exception("Ошибка при выгрузке backup: %s", e)
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.error_text(html.escape(str(e))),
            reply_markup=templ.back_kb(templ.CONFIG_BACKUP_MENU_CB),
        )
    finally:
        if backup_path and os.path.exists(backup_path):
            try:
                os.remove(backup_path)
            except OSError:
                pass


@router.callback_query(F.data == templ.CONFIG_BACKUP_IMPORT_CB)
async def callback_config_backup_import_start(callback: CallbackQuery, state: FSMContext):
    config = sett.get("config")
    if callback.from_user.id not in config["telegram"]["bot"].get("signed_users", []):
        await callback.answer("❌ Нет доступа к backup", show_alert=True)
        return

    await _remove_pending_backup_from_state(state)
    await state.set_state(states.ConfigBackupStates.waiting_for_backup_file)
    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.config_backup_wait_file_text(),
        reply_markup=templ.back_kb(templ.CONFIG_BACKUP_MENU_CB),
        callback=callback,
    )


@router.callback_query(F.data == templ.CONFIG_BACKUP_CANCEL_CB)
async def callback_config_backup_import_cancel(callback: CallbackQuery, state: FSMContext):
    await _remove_pending_backup_from_state(state)
    await state.set_state(None)
    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.do_action_text("❌ Восстановление backup отменено."),
        reply_markup=templ.config_backup_kb(),
        callback=callback,
    )


@router.callback_query(F.data == templ.CONFIG_BACKUP_CONFIRM_CB)
async def callback_config_backup_import_confirm(callback: CallbackQuery, state: FSMContext):
    config = sett.get("config")
    if callback.from_user.id not in config["telegram"]["bot"].get("signed_users", []):
        await callback.answer("❌ Нет доступа к backup", show_alert=True)
        return

    data = await state.get_data()
    pending_path = data.get("config_backup_pending_path")

    if not pending_path or not os.path.exists(pending_path):
        await state.set_state(None)
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.do_action_text(
                "❌ Файл backup для восстановления не найден. Загрузите backup снова."
            ),
            reply_markup=templ.config_backup_kb(),
            callback=callback,
        )
        return

    current_backup_path = None
    try:
        with open(pending_path, "rb") as f:
            payload = load_backup_payload(f.read())
        is_valid, validation_error = validate_backup_payload(payload)
        if not is_valid:
            raise ValueError(validation_error)

        loop = asyncio.get_running_loop()
        current_payload = await loop.run_in_executor(None, create_backup_payload)
        current_backup_path = await loop.run_in_executor(
            None,
            save_backup_payload_to_file,
            current_payload,
            "pre_restore_backup",
        )
        current_summary = format_backup_summary(current_payload)

        await callback.message.answer(
            text=templ.config_backup_before_restore_text(),
            parse_mode="HTML",
        )

        try:
            await callback.message.answer_document(
                document=FSInputFile(current_backup_path, filename=os.path.basename(current_backup_path)),
                caption=templ.config_backup_before_restore_caption(current_summary),
                parse_mode="HTML",
            )
        except Exception as send_error:
            raise RuntimeError(
                f"Не удалось отправить текущий backup. Замена отменена: {send_error}"
            ) from send_error

        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.config_backup_in_progress_text(),
            reply_markup=templ.destroy_kb(),
            callback=callback,
        )

        await loop.run_in_executor(None, apply_backup_payload, payload)
        await _remove_pending_backup_from_state(state)
        await state.set_state(None)
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.config_backup_success_text(),
            reply_markup=templ.config_backup_kb(),
        )
    except Exception as e:
        logger.exception("Ошибка при применении backup: %s", e)
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.do_action_text(
                f"❌ Не удалось применить backup: <code>{html.escape(str(e))}</code>"
            ),
            reply_markup=templ.confirm_kb(
                confirm_cb=templ.CONFIG_BACKUP_CONFIRM_CB,
                cancel_cb=templ.CONFIG_BACKUP_CANCEL_CB,
            ),
        )
    finally:
        if current_backup_path and os.path.exists(current_backup_path):
            try:
                os.remove(current_backup_path)
            except OSError:
                pass
