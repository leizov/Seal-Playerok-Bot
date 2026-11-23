"""🖼 Картинки в сообщениях (автоответы, авто-выдача): кнопки меню."""
import copy
import logging

from aiogram import Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, InputMediaPhoto, Message

from core.chat_images import (
    MAX_IMAGES,
    cleanup_unused_images,
    delete_images,
    existing_image_paths,
    resolve_image,
)
from settings import Settings as sett

from .. import callback_datas as calls
from .. import states
from .. import templates as templ
from ..helpful import throw_float_message
from ..utils.chat_image_owners import (
    OWNER_AUTO_DELIVERY,
    ImageOwnerError,
    auto_response_message_key,
    owner_signature,
    resolve_owner,
    save_owner_refs,
)
from ..utils.chat_image_lock import images_edit_lock


router = Router()
logger = logging.getLogger("seal.telegram.chat_images")

CAPTION_LIMIT = 1024
PREVIEW_TEXT_LIMIT = 3800


async def remember_owner(state: FSMContext, owner) -> None:
    """Запоминает, какая авто-выдача открыта (по отпечатку — индекс может измениться)."""
    if owner.owner == OWNER_AUTO_DELIVERY:
        await state.update_data(cimg_ad_sig=owner_signature(owner), auto_delivery_index=owner.index)


async def show_images_menu(state: FSMContext, message: Message, owner, callback: CallbackQuery | None = None,
                           notice: str = "", send: bool = False) -> Message | None:
    return await throw_float_message(
        state=state,
        message=message,
        text=templ.chat_images_text(owner, notice),
        reply_markup=templ.chat_images_kb(owner),
        callback=callback,
        send=send,
    )


async def _menu_below(callback: CallbackQuery, state: FSMContext, owner) -> None:
    """Меню картинок новым сообщением под присланными фото, старое меню удаляется."""
    await show_images_menu(state, callback.message, owner, send=True)
    try:
        await callback.message.delete()
    except TelegramAPIError:
        pass


async def _send_single_image(callback: CallbackQuery, path: str, caption: str) -> None:
    try:
        await callback.bot.send_photo(
            chat_id=callback.message.chat.id,
            photo=FSInputFile(path),
            caption=caption,
            parse_mode="HTML",
            reply_markup=templ.destroy_kb(),
        )
    except TelegramAPIError:
        # Например, у картинки слишком вытянутые пропорции для фото — пришлём файлом
        await callback.bot.send_document(
            chat_id=callback.message.chat.id,
            document=FSInputFile(path),
            caption=caption,
            parse_mode="HTML",
            reply_markup=templ.destroy_kb(),
        )


async def _send_preview(callback: CallbackQuery, owner) -> None:
    chat_id = callback.message.chat.id
    paths = existing_image_paths(owner.refs)
    text = owner.preview_text or ""
    if len(text) > PREVIEW_TEXT_LIMIT:
        text = text[:PREVIEW_TEXT_LIMIT].rstrip() + "…"

    if not paths:
        await callback.bot.send_message(
            chat_id=chat_id, text=templ.chat_images_preview_text(owner, text),
            parse_mode="HTML", reply_markup=templ.destroy_kb(),
        )
        return

    caption = templ.chat_images_preview_caption(owner, text, CAPTION_LIMIT)
    text_separately = caption is None
    if text_separately:
        caption = templ.chat_images_preview_caption(owner, "", CAPTION_LIMIT)
    if len(paths) == 1:
        await _send_single_image(callback, paths[0], caption)
    else:
        media = [InputMediaPhoto(media=FSInputFile(path)) for path in paths]
        media[0].caption = caption
        media[0].parse_mode = "HTML"
        await callback.bot.send_media_group(chat_id=chat_id, media=media)
    if text_separately:
        await callback.bot.send_message(
            chat_id=chat_id, text=templ.chat_images_preview_text(owner, text),
            parse_mode="HTML", reply_markup=templ.destroy_kb(),
        )


@router.callback_query(calls.ChatImagesAction.filter())
async def callback_chat_images(callback: CallbackQuery, callback_data: calls.ChatImagesAction, state: FSMContext):
    action = callback_data.action
    data = await state.get_data()
    try:
        owner = resolve_owner(callback_data.owner, callback_data.key, data, fresh=(action == "open"))
    except ImageOwnerError as e:
        await state.set_state(None)
        await callback.answer(str(e), show_alert=True)
        return
    await remember_owner(state, owner)

    try:
        if action in ("open", "menu"):
            await state.set_state(None)
            if action == "open":
                try:
                    cleanup_unused_images()
                except Exception as e:
                    logger.warning("Не удалось почистить неиспользуемые картинки: %s", e)
            await show_images_menu(state, callback.message, owner, callback)

        elif action == "add":
            if len(owner.refs) >= MAX_IMAGES:
                await callback.answer(f"❌ Уже {MAX_IMAGES} картинок — сначала удалите лишние", show_alert=True)
                return
            await state.set_state(states.ChatImagesStates.waiting_for_image)
            await state.update_data(cimg_owner=owner.owner, cimg_key=owner.key, cimg_added=0)
            await throw_float_message(
                state=state,
                message=callback.message,
                text=templ.chat_images_add_text(owner),
                reply_markup=templ.chat_images_add_kb(owner),
                callback=callback,
            )

        elif action == "show":
            number = callback_data.index + 1
            if not (1 <= number <= len(owner.refs)):
                await callback.answer("❌ Картинка не найдена — список изменился", show_alert=True)
                await show_images_menu(state, callback.message, owner)
                return
            path = resolve_image(owner.refs[number - 1])
            if path is None:
                await callback.answer("❌ Файл картинки не найден на диске — удалите её и загрузите заново", show_alert=True)
                return
            await callback.answer()
            await _send_single_image(callback, path, templ.chat_images_photo_caption(owner, number))
            await _menu_below(callback, state, owner)

        elif action == "del":
            async with images_edit_lock:
                owner = resolve_owner(callback_data.owner, owner.key, await state.get_data())
                number = callback_data.index + 1
                if not (1 <= number <= len(owner.refs)):
                    await callback.answer("❌ Картинка не найдена — список изменился", show_alert=True)
                    await show_images_menu(state, callback.message, owner)
                    return
                removed = owner.refs[number - 1]
                save_owner_refs(owner, [ref for ref in owner.refs if ref != removed])
                delete_images([removed])
            await show_images_menu(state, callback.message, owner, callback, notice=f"🗑 Картинка {number} удалена")

        elif action == "preview":
            if not owner.refs and not owner.preview_text:
                await callback.answer("Нечего показывать: нет ни текста, ни картинок", show_alert=True)
                return
            await callback.answer()
            await _send_preview(callback, owner)
            await _menu_below(callback, state, owner)

        elif action == "clear":
            if not owner.refs:
                await show_images_menu(state, callback.message, owner, callback)
                return
            await throw_float_message(
                state=state,
                message=callback.message,
                text=templ.chat_images_clear_text(owner),
                reply_markup=templ.chat_images_clear_kb(owner),
                callback=callback,
            )

        elif action == "clear_yes":
            async with images_edit_lock:
                owner = resolve_owner(callback_data.owner, owner.key, await state.get_data())
                removed = list(owner.refs)
                save_owner_refs(owner, [])
                delete_images(removed)
            await show_images_menu(
                state, callback.message, owner, callback,
                notice=f"🧹 Удалено картинок: {len(removed)}" if removed else "",
            )

        else:
            await callback.answer("❌ Неизвестное действие", show_alert=True)

    except ImageOwnerError as e:
        await state.set_state(None)
        await callback.answer(str(e), show_alert=True)
    except Exception as e:
        logger.exception("Ошибка в меню картинок")
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.chat_images_text(owner, notice=f"❌ {e}"),
            reply_markup=templ.chat_images_kb(owner),
        )


@router.callback_query(calls.AutoResponseClearText.filter())
async def callback_auto_response_clear_text(callback: CallbackQuery, callback_data: calls.AutoResponseClearText,
                                            state: FSMContext):
    """🧹 Удалить текст автоответа (сообщение может состоять только из картинок)."""
    from .navigation import callback_messages_navigation

    message_type = callback_data.message_type
    message_key = auto_response_message_key(message_type)
    if message_key is None:
        await callback.answer("❌ Неизвестный тип сообщения", show_alert=True)
        return
    await state.set_state(None)

    if not callback_data.confirm:
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.auto_response_clear_text_text(message_type),
            reply_markup=templ.auto_response_clear_text_kb(message_type),
            callback=callback,
        )
        return

    messages = sett.get("messages") or {}
    entry = messages.setdefault(message_key, {"enabled": False, "text": []})
    entry["text"] = []
    sett.set("messages", messages)
    try:
        from plbot.playerokbot import get_playerok_bot

        playerok_bot = get_playerok_bot()
        if playerok_bot is not None:
            playerok_bot.messages = copy.deepcopy(sett.get("messages"))
    except Exception as e:
        logger.warning("Не удалось обновить автоответы в памяти Playerok-бота: %s", e)
    return await callback_messages_navigation(callback, calls.MessagesNavigation(to=message_type), state)
