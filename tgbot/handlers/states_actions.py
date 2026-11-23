import asyncio
import html
import os
import uuid

from aiogram import types, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, InputMediaPhoto

from core.chat_images import MAX_IMAGE_BYTES, MAX_IMAGES, detect_image_type, format_size
from paths import CACHE_DIR
from .. import templates as templ
from .. import states
from ..helpful import throw_float_message

router = Router()
MAX_PHOTO_WIGHT = MAX_IMAGE_BYTES  # максимальный размер картинки в байтах
ALBUM_WAIT_SECONDS = 1.5           # сколько ждём остальные фото альбома
CAPTION_TEXT_LIMIT = 800           # подпись к фото в Telegram — до 1024 символов

# media_group_id → сообщения альбома, пока он собирается
_albums: dict[str, list[types.Message]] = {}


def _image_of(message: types.Message):
    """Картинка из сообщения: (объект файла Telegram, название типа) или (None, None)."""
    if message.photo:
        return message.photo[-1], "Фото"
    if message.animation:
        # Playerok не принимает GIF — отправляем первый кадр (превью)
        thumbnail = message.animation.thumbnail
        if not thumbnail:
            raise TypeError("❌ Неподдерживаемый формат для сообщения")
        return thumbnail, "GIF"
    document = message.document
    if document is not None and (document.mime_type or "").lower().startswith("image/"):
        return document, "Картинка"
    return None, None


def _files_label(files: list[tuple]) -> str:
    kinds: dict[str, int] = {}
    for _file, kind in files:
        kinds[kind] = kinds.get(kind, 0) + 1
    return ", ".join(kind if count == 1 else f"{kind} ×{count}" for kind, count in kinds.items())


@router.message(states.ActionsStates.waiting_for_message_text)
async def handler_waiting_for_password(message: types.Message, state: FSMContext):
    group_id = message.media_group_id
    if group_id:
        # Фото альбома приходят отдельными сообщениями — собираем их и отправляем одним сообщением
        album = _albums.setdefault(group_id, [])
        album.append(message)
        if len(album) > 1:
            return
        await asyncio.sleep(ALBUM_WAIT_SECONDS)
        messages = sorted(_albums.pop(group_id, [message]), key=lambda m: m.message_id)
    else:
        messages = [message]
    await _send_to_playerok_chat(messages, state)


async def _send_to_playerok_chat(messages: list[types.Message], state: FSMContext):
    actual_msg = messages[0]
    temp_paths: list[str] = []
    try:
        await state.set_state(None)
        from plbot.playerokbot import get_playerok_bot

        data = await state.get_data()
        plbot = get_playerok_bot()
        username = data.get("username")
        chat = plbot.get_chat_by_username(username)

        text = next((m.text or m.caption for m in messages if (m.text or m.caption)), None) or ''
        files = []
        for msg in messages:
            file_info, file_type = _image_of(msg)
            if file_info:
                files.append((file_info, file_type))

        if not files and not text:
            raise TypeError("❌ Неподдерживаемый формат для сообщения")
        if len(files) > MAX_IMAGES:
            raise ValueError(f"❌ В одном сообщении можно отправить не больше {MAX_IMAGES} картинок, а в альбоме их {len(files)}")
        for file_info, _file_type in files:
            if file_info.file_size and file_info.file_size > MAX_PHOTO_WIGHT:
                raise ValueError(f"❌ Файл слишком большой, максимальный размер: {format_size(MAX_PHOTO_WIGHT)}")

        sent = None
        if files:
            label = _files_label(files)
            actual_msg = await throw_float_message(
                state=state,
                message=actual_msg,
                text=templ.do_action_text(f"📲 Начинаю отправку: {label}{' + текст' if text else ''}"),
                delete_user_message=False
            ) or actual_msg

            tg_bot = messages[0].bot
            photo_cache_dir = os.path.join(CACHE_DIR, 'photo_cache')
            os.makedirs(photo_cache_dir, exist_ok=True)
            for file_info, _file_type in files:
                downloaded = await tg_bot.download(file_info.file_id)
                file_bytes = downloaded.read()
                ext = detect_image_type(file_bytes) or "jpg"
                temp_photo_path = os.path.join(photo_cache_dir, f"{uuid.uuid4()}.{ext}")
                with open(temp_photo_path, 'wb') as f:
                    f.write(file_bytes)
                temp_paths.append(temp_photo_path)

            # Текст и картинки уходят одним сообщением (сетевые запросы — вне цикла событий Telegram)
            sent = await asyncio.to_thread(plbot.send_message, chat.id, text or None, images=temp_paths)
            if sent:
                quote = text if len(text) <= CAPTION_TEXT_LIMIT else text[:CAPTION_TEXT_LIMIT].rstrip() + "…"
                caption = f"✅ Пользователю <b>{html.escape(str(username))}</b> было отправлено: {label}"
                if text:
                    caption += f"\n<blockquote>{html.escape(quote)}</blockquote>"
                try:
                    await actual_msg.edit_media(
                        media=InputMediaPhoto(
                            media=FSInputFile(temp_paths[0]),
                            caption=templ.do_action_text(caption),
                            parse_mode='HTML'
                        ),
                        reply_markup=templ.destroy_kb(),
                    )
                except Exception:
                    await throw_float_message(
                        state=state,
                        message=actual_msg,
                        text=templ.do_action_text(caption),
                        reply_markup=templ.destroy_kb(),
                        delete_user_message=False
                    )

        elif text:
            sent = await asyncio.to_thread(plbot.send_message, chat.id, text)
            if sent:
                await throw_float_message(
                    state=state,
                    message=actual_msg,
                    text=templ.do_action_text(
                        f"✅ Пользователю <b>{html.escape(str(username))}</b> было отправлено сообщение: <blockquote>{html.escape(text)}</blockquote>"),
                    reply_markup=templ.destroy_kb(),
                    delete_user_message=False
                )

        if not sent:
            raise TypeError(f"❌ Не удалось отправить сообщение, смотри логи")

    except Exception as e:
        error_text = html.escape(str(e))
        await throw_float_message(
            state=state,
            message=actual_msg,
            text=templ.do_action_text(error_text),
            reply_markup=templ.destroy_kb(),
            delete_user_message=False
        )
    finally:
        for path in temp_paths:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass
