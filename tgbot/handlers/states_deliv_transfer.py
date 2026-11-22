"""🔄 Выгрузка / загрузка авто-выдач: приём файла загрузки."""

from html import escape

from aiogram import Router, types
from aiogram.fsm.context import FSMContext

from core.auto_delivery_transfer import AutoDeliveryImportError, find_conflicts, parse_import_file

from .. import states
from .. import templates as templ
from ..callback_handlers.auto_delivery_transfer import load_deliveries, show_import_step
from ..helpful import throw_float_message


router = Router()

MAX_IMPORT_FILE_SIZE = 20 * 1024 * 1024  # лимит скачивания файлов у Telegram Bot API


async def _import_error(message: types.Message, state: FSMContext, text: str):
    # Остаёмся в ожидании файла, чтобы можно было сразу прислать исправленный.
    await throw_float_message(
        state=state,
        message=message,
        text=templ.adt_import_float_text(f"{text}\n\n📎 Отправьте исправленный файл <b>.txt</b> или <b>.json</b> ↓"),
        reply_markup=templ.back_kb(templ.ADT_MENU_CB),
    )


@router.message(states.AutoDeliveriesStates.waiting_for_transfer_import_file)
async def handler_waiting_for_transfer_import_file(message: types.Message, state: FSMContext):
    document = message.document
    if document is None:
        await _import_error(message, state, "❌ Пришлите файл выгрузки <b>документом</b> (.txt или .json), а не текстом")
        return

    file_name = document.file_name or ""
    if not file_name.lower().endswith((".txt", ".json")):
        await _import_error(message, state, "❌ Поддерживаются только файлы <b>.txt</b> и <b>.json</b>")
        return
    if document.file_size and document.file_size > MAX_IMPORT_FILE_SIZE:
        await _import_error(message, state, "❌ Файл больше 20 МБ — Telegram не даёт боту скачать такой файл")
        return

    try:
        file_info = await message.bot.get_file(document.file_id)
        downloaded = await message.bot.download_file(file_info.file_path)
        content = downloaded if isinstance(downloaded, bytes) else downloaded.read()
        imported = parse_import_file(file_name, content)
    except AutoDeliveryImportError as e:
        await _import_error(message, state, str(e))
        return
    except Exception as e:
        await _import_error(message, state, f"❌ Не удалось прочитать файл: <code>{escape(str(e))}</code>")
        return

    await state.set_state(None)
    await state.update_data(adt_import={
        "file_name": file_name,
        "entries": imported,
        "conflicts": find_conflicts(load_deliveries(), imported),
        "decisions": {},
        "pos": 0,
    })
    await show_import_step(state, message)
