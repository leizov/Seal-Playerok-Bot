import asyncio
import html
import os

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from core.config_backup import (
    format_backup_summary,
    load_backup_payload,
    save_backup_payload_to_file,
    validate_backup_payload,
)

from .. import states
from .. import templates as templ
from ..helpful import throw_float_message


router = Router()


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


@router.message(states.ConfigBackupStates.waiting_for_backup_file, F.document)
async def handler_waiting_for_config_backup_file(message: types.Message, state: FSMContext):
    try:
        file_name = message.document.file_name or ""
        if not file_name.lower().endswith(".json"):
            raise ValueError("Файл должен быть в формате .json")

        file_info = await message.bot.get_file(message.document.file_id)
        downloaded_file = await message.bot.download_file(file_info.file_path)
        file_bytes = downloaded_file if isinstance(downloaded_file, bytes) else downloaded_file.read()

        payload = load_backup_payload(file_bytes)
        is_valid, validation_error = validate_backup_payload(payload)
        if not is_valid:
            raise ValueError(validation_error)

        loop = asyncio.get_running_loop()
        pending_path = await loop.run_in_executor(
            None,
            save_backup_payload_to_file,
            payload,
            "pending_restore_backup",
        )
        summary = format_backup_summary(payload)

        await _remove_pending_backup_from_state(state)
        await state.update_data(
            config_backup_pending_path=pending_path,
            config_backup_pending_summary=summary,
        )
        await state.set_state(states.ConfigBackupStates.waiting_for_restore_confirmation)

        await throw_float_message(
            state=state,
            message=message,
            text=templ.config_backup_confirm_text(summary),
            reply_markup=templ.confirm_kb(
                confirm_cb=templ.CONFIG_BACKUP_CONFIRM_CB,
                cancel_cb=templ.CONFIG_BACKUP_CANCEL_CB,
            ),
        )
    except Exception as e:
        await throw_float_message(
            state=state,
            message=message,
            text=templ.config_backup_wait_file_error_text(html.escape(str(e))),
            reply_markup=templ.back_kb(templ.CONFIG_BACKUP_MENU_CB),
        )


@router.message(states.ConfigBackupStates.waiting_for_backup_file)
async def handler_waiting_for_config_backup_file_invalid_input(message: types.Message, state: FSMContext):
    await throw_float_message(
        state=state,
        message=message,
        text=templ.config_backup_wait_file_text(),
        reply_markup=templ.back_kb(templ.CONFIG_BACKUP_MENU_CB),
    )


@router.message(states.ConfigBackupStates.waiting_for_restore_confirmation)
async def handler_waiting_for_config_backup_confirmation(message: types.Message, state: FSMContext):
    data = await state.get_data()
    summary = data.get("config_backup_pending_summary")
    if not summary:
        summary = "Файл уже загружен и ожидает подтверждения."

    await throw_float_message(
        state=state,
        message=message,
        text=templ.config_backup_confirm_text(summary),
        reply_markup=templ.confirm_kb(
            confirm_cb=templ.CONFIG_BACKUP_CONFIRM_CB,
            cancel_cb=templ.CONFIG_BACKUP_CANCEL_CB,
        ),
    )
