"""🖼 Картинки в сообщениях: приём картинок (фото, файл, альбом)."""
import logging
from html import escape

from aiogram import Router, types
from aiogram.fsm.context import FSMContext

from core.chat_images import (
    ALLOWED_FORMATS_TEXT,
    MAX_IMAGE_BYTES,
    MAX_IMAGES,
    ChatImageError,
    delete_images,
    format_size,
    save_image,
)

from .. import states
from .. import templates as templ
from ..helpful import throw_float_message
from ..utils.chat_image_lock import images_edit_lock
from ..utils.chat_image_owners import ImageOwnerError, resolve_owner, save_owner_refs


router = Router()
logger = logging.getLogger("seal.telegram.chat_images")

_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")


def _incoming_file(message: types.Message) -> tuple[str | None, int | None, str | None]:
    """file_id, размер и текст ошибки, если прислали не картинку."""
    if message.photo:
        photo = message.photo[-1]
        return photo.file_id, photo.file_size, None
    document = message.document
    if document is not None:
        name = (document.file_name or "").lower()
        mime = (document.mime_type or "").lower()
        if not (mime.startswith("image/") or name.endswith(_IMAGE_EXTENSIONS)):
            return None, None, f"❌ Файл <code>{escape(document.file_name or 'без имени')}</code> — не картинка. Подойдут: {ALLOWED_FORMATS_TEXT}"
        return document.file_id, document.file_size, None
    if message.animation or message.sticker or message.video:
        return None, None, f"❌ GIF, стикеры и видео не поддерживаются. Подойдут: {ALLOWED_FORMATS_TEXT}"
    return None, None, "❌ Пришлите картинку — фото или файлом"


@router.message(states.ChatImagesStates.waiting_for_image)
async def handler_waiting_for_image(message: types.Message, state: FSMContext):
    data = await state.get_data()
    owner_kind, owner_key = data.get("cimg_owner"), data.get("cimg_key")
    try:
        owner = resolve_owner(owner_kind, owner_key, data)
    except ImageOwnerError as e:
        await state.set_state(None)
        await throw_float_message(state=state, message=message, text=str(e), reply_markup=templ.destroy_kb())
        return

    file_id, file_size, error = _incoming_file(message)
    if error is None and file_size and file_size > MAX_IMAGE_BYTES:
        error = f"❌ Картинка слишком большая: {format_size(file_size)}. Максимум — {format_size(MAX_IMAGE_BYTES)}"

    image_bytes = None
    if error is None:
        try:
            downloaded = await message.bot.download(file_id)
            image_bytes = downloaded.read() if downloaded is not None else None
            if not image_bytes:
                error = "❌ Не удалось скачать картинку из Telegram, попробуйте ещё раз"
        except Exception as e:
            logger.warning("Не удалось скачать картинку из Telegram: %s", e)
            error = "❌ Не удалось скачать картинку из Telegram, попробуйте ещё раз"

    # Фото из альбома приходят параллельно — список картинок меняем по очереди
    async with images_edit_lock:
        data = await state.get_data()
        if await state.get_state() != states.ChatImagesStates.waiting_for_image.state:
            # Пока это фото из альбома ждало очереди, добавление уже завершилось (набрался лимит)
            try:
                owner = resolve_owner(owner_kind, owner_key, data)
            except ImageOwnerError:
                return
            await throw_float_message(
                state=state,
                message=message,
                text=templ.chat_images_text(owner, notice=f"❌ Уже {MAX_IMAGES} картинок — лишние не добавлены"),
                reply_markup=templ.chat_images_kb(owner),
            )
            return
        try:
            owner = resolve_owner(owner_kind, owner_key, data)
        except ImageOwnerError as e:
            await state.set_state(None)
            await throw_float_message(state=state, message=message, text=str(e), reply_markup=templ.destroy_kb())
            return
        added = int(data.get("cimg_added") or 0)

        if error is None and len(owner.refs) >= MAX_IMAGES:
            error = f"❌ Уже {MAX_IMAGES} картинок — лишние не добавлены"

        if error is None:
            ref = None
            try:
                ref = save_image(image_bytes)
                save_owner_refs(owner, owner.refs + [ref])
                added += 1
                await state.update_data(cimg_added=added)
            except ChatImageError as e:
                error = str(e)
            except Exception as e:
                logger.exception("Не удалось сохранить картинку")
                error = f"❌ Не удалось сохранить картинку: {escape(str(e))}"
                if ref is not None:
                    delete_images([ref])

        if len(owner.refs) >= MAX_IMAGES:
            await state.set_state(None)
            notice = f"✅ Добавлено картинок: {added}. Достигнут лимит — {MAX_IMAGES} шт."
            if error:
                notice = f"{error}\n{notice}"
            await throw_float_message(
                state=state,
                message=message,
                text=templ.chat_images_text(owner, notice=notice),
                reply_markup=templ.chat_images_kb(owner),
            )
            return

        await throw_float_message(
            state=state,
            message=message,
            text=templ.chat_images_add_text(owner, added=added, notice=error or ""),
            reply_markup=templ.chat_images_add_kb(owner),
        )
