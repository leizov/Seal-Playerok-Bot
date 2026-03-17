import time

from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, InputMediaPhoto
from .. import templates as templ
from .. import states
from ..helpful import throw_float_message
import os
import uuid
from paths import CACHE_DIR
import io

router = Router()
MAX_PHOTO_WIGHT = 1024 * 8 * 500

@router.message(states.ActionsStates.waiting_for_message_text)
async def handler_waiting_for_password(message: types.Message, state: FSMContext):
    try:
        actual_msg = message
        await state.set_state(None)
        from plbot.playerokbot import get_playerok_bot

        data = await state.get_data()
        plbot = get_playerok_bot()
        username = data.get("username")
        chat = plbot.get_chat_by_username(username)

        if message.media_group_id:
            #todo добавить возможность прикреплять много фото
            await throw_float_message(
                state=state,
                message=actual_msg,
                text=templ.do_action_text(
                    f"Отправка сообщения с множественными прикреплёнными изображениями не доступна("),
                reply_markup=templ.destroy_kb(),
                delete_user_message=False
            )
            return

        text = message.text

        file_info = None
        file_type = None
        if message.photo:
            file_info = message.photo[-1]
            file_type = 'Фото'
            text = message.caption

        elif message.animation:
            try:
                file_info = message.animation.thumbnail
                if not file_info:
                    raise TypeError("❌ Неподдерживаемый формат для сообщения")
            except:
                raise TypeError("❌ Неподдерживаемый формат для сообщения")

            file_type = 'GIF'
            text = message.caption

        text = text if text else ''

        if not file_info and not text:
            raise TypeError("❌ Неподдерживаемый формат для сообщения")

        success = False

        if file_info:
            #todo коррекция пределов веса и сниженние качества
            if file_info.file_size > MAX_PHOTO_WIGHT:
                raise ValueError(f"❌ Файл слишком большой, максимальный размер: {MAX_PHOTO_WIGHT // 8 // 1024} Кб")

            actual_msg = await throw_float_message(
                state=state,
                message=actual_msg,
                text=templ.do_action_text(
                    f"📲 Начинаю отправку: {file_type}{'+ текст' if message.text else ''}"),
                delete_user_message=False
            )

            from ..telegrambot import get_telegram_bot
            tg_bot = get_telegram_bot().bot
            file_obj = await tg_bot.get_file(file_info.file_id)


            file_path= file_obj.file_path
            downloaded_file = await tg_bot.download_file(file_path)

            if isinstance(downloaded_file, bytes):
                file_bytes = downloaded_file
            else:
                # на случай, если вернётся BytesIO
                file_bytes = downloaded_file.read()

            photo_cache_dir = os.path.join(CACHE_DIR, 'photo_cache')
            os.makedirs(photo_cache_dir, exist_ok=True)
            temp_photo_path = os.path.join(photo_cache_dir, str(uuid.uuid4()) + '.jpg')

            with open(temp_photo_path, 'wb') as f:
                f.write(file_bytes)

            # if file_type == 'GIF':
            #     try:
            #         from PIL import Image
            #     except:
            #         raise ImportError(f"❌ Не удалось отправить GIF, не установлен Pillow")
            #
            #     io_obj = io.BytesIO(file_bytes)
            #     io_obj.seek(0)
            #     gif_image = Image.open(io_obj)
            #     raise ValueError(gif_image.format)
            #
            #     # первый кадр берём
            #     gif_image.seek(0)
            #     if gif_image.mode != 'RGB':
            #         gif_image = gif_image.convert('RGB')
            #     gif_image.save(temp_photo_path, 'JPEG', quality=85)
            #
            # else:
            #     with open(temp_photo_path, 'wb') as f:
            #         f.write(file_bytes)

            if text:
                if (
                    plbot.send_message(chat_id=chat.id, photo_file_path=temp_photo_path) and
                    plbot.send_message(chat_id=chat.id, text=text)
                ):
                    success = True
                    await actual_msg.edit_media(
                        media=InputMediaPhoto(
                            media=FSInputFile(temp_photo_path),
                            caption=templ.do_action_text(
                                f"✅ Пользователю <b>{username}</b> было отправлено сообщение: <blockquote>{text}</blockquote> + {file_type}"
                            ),
                            parse_mode='HTML'
                        ),
                        reply_markup=templ.destroy_kb(),

                    )
            else:
                if plbot.send_message(chat_id=chat.id, photo_file_path=temp_photo_path):
                    success = True
                    await actual_msg.edit_media(
                        media=InputMediaPhoto(
                            media=FSInputFile(temp_photo_path),
                            caption=templ.do_action_text(
                                f"✅ Пользователю <b>{username}</b> было отправлено {file_type}"
                            ),
                            parse_mode='HTML'
                        ),
                        reply_markup=templ.destroy_kb(),

                    )

        elif text:
            if plbot.send_message(chat_id=chat.id, text=text):
                success = True
                await throw_float_message(
                    state=state,
                    message=actual_msg,
                    text=templ.do_action_text(
                        f"✅ Пользователю <b>{username}</b> было отправлено сообщение: <blockquote>{text}</blockquote>"),
                    reply_markup=templ.destroy_kb(),
                    delete_user_message=False
                )

        if not success:
            raise TypeError(f"❌ Не удалось отправить сообщение, смотри логи")

    except Exception as e:
        import html
        error_text = html.escape(str(e))
        await throw_float_message(
            state=state,
            message=actual_msg,
            text=templ.do_action_text(error_text),
            reply_markup=templ.destroy_kb(),
            delete_user_message=False
        )
    finally:
        try:
            if 'temp_photo_path' in locals():
                if os.path.exists(temp_photo_path):
                    os.remove(temp_photo_path)
        except: pass