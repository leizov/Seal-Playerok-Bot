from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, Message, CallbackQuery
from aiogram.exceptions import TelegramAPIError

from . import templates as templ


def get_playerok_bot():
    """Получает экземпляр Playerok бота"""
    from plbot.playerokbot import get_playerok_bot as _get_playerok_bot
    return _get_playerok_bot()


async def do_auth(message: Message, state: FSMContext) -> Message | None:
    """
    Начинает процесс авторизации в боте (запрашивает пароль, указанный в конфиге).

    :param message: Исходное сообщение.
    :type message: `aiogram.types.Message`

    :param state: Исходное состояние.
    :type state: `aiogram.fsm.context.FSMContext`
    """
    from . import states
    
    await state.set_state(states.SystemStates.waiting_for_password)
    return await throw_float_message(
        state=state,
        message=message,
        text=templ.sign_text('🔑 Введите ключ-пароль, указанный вами в конфиге бота ↓'),
        reply_markup=templ.destroy_kb()
    )


async def throw_float_message(state: FSMContext, message: Message, text: str, 
                              reply_markup: InlineKeyboardMarkup = None,
                              callback: CallbackQuery = None,
                              send: bool = False,
                              delete_user_message: bool = True) -> Message | None:
    """
    Изменяет плавающее сообщение (изменяет текст акцентированного сообщения) или родительское сообщение бота, переданное в аргумент `message`.\n
    Если не удалось найти акцентированное сообщение, или это сообщение - команда, отправит новое акцентированное сообщение.

    :param state: Состояние бота.
    :type state: `aiogram.fsm.context.FSMContext`
    
    :param message: Переданный в handler объект сообщения.
    :type message: `aiogram.types.Message`

    :param text: Текст сообщения.
    :type text: `str`

    :param reply_markup: Клавиатура сообщения, _опционально_.
    :type reply_markup: `aiogram.typesInlineKeyboardMarkup.`

    :param callback: CallbackQuery хендлера, для ответа пустой AnswerCallbackQuery, _опционально_.
    :type callback: `aiogram.types.CallbackQuery` or `None`

    :param send: Отправить ли новое акцентированное сообщение, _опционально_.
    :type send: `bool`
    """
    from .telegrambot import get_telegram_bot
    bot = None
    mess = None
    accent_message_id = None
    target_chat_id = None
    try:
        tg_bot = get_telegram_bot()
        if tg_bot is None:
            return None
        bot = tg_bot.bot

        if message is None and callback is not None:
            message = callback.message
        if message is None:
            return None

        data = await state.get_data()
        message_chat = getattr(message, "chat", None)
        target_chat_id = getattr(message_chat, "id", None)
        if target_chat_id is None and callback and callback.from_user:
            target_chat_id = callback.from_user.id

        current_message_id = getattr(message, "message_id", None)
        message_from_user_id = getattr(getattr(message, "from_user", None), "id", None)

        accent_message_id = current_message_id
        if message_from_user_id is not None and message_from_user_id != bot.id:
            accent_message_id = data.get("accent_message_id")
        new_mess_cond = False

        if not send:
            message_text = getattr(message, "text", None)
            if message_text is not None:
                new_mess_cond = (
                    message_from_user_id is not None
                    and message_from_user_id != bot.id
                    and message_text.startswith('/')
                )

            if accent_message_id is not None and not new_mess_cond:
                try:
                    if (
                        message_from_user_id is not None
                        and message_from_user_id != bot.id
                        and delete_user_message
                        and target_chat_id is not None
                        and current_message_id is not None
                    ):
                        await bot.delete_message(target_chat_id, current_message_id)
                    mess = await bot.edit_message_text(
                        text=text,
                        reply_markup=reply_markup, 
                        chat_id=target_chat_id, 
                        message_id=accent_message_id, 
                        parse_mode="HTML"
                    )
                except TelegramAPIError as e:
                    if "message to edit not found" in e.message.lower():
                        accent_message_id = None
                    elif "message is not modified" in e.message.lower():
                        if callback:
                            await bot.answer_callback_query(
                                callback_query_id=callback.id,
                                show_alert=False,
                                cache_time=0
                            )
                        pass
                    elif "query is too old" in e.message.lower():
                        return
                    else:
                        raise e
        if callback:
            await bot.answer_callback_query(
                callback_query_id=callback.id, 
                show_alert=False, 
                cache_time=0
            )
        if (accent_message_id is None or new_mess_cond or send) and target_chat_id is not None:
            mess = await bot.send_message(
                chat_id=target_chat_id, 
                text=text, 
                reply_markup=reply_markup, 
                parse_mode="HTML"
            )
    except Exception as e:
        try:
            if bot is not None and accent_message_id is not None and target_chat_id is not None:
                mess = await bot.edit_message_text(
                    chat_id=target_chat_id,
                    reply_markup=templ.destroy_kb(),
                    text=templ.error_text(e),
                    message_id=accent_message_id,
                    parse_mode="HTML"
                )
            elif bot is not None and target_chat_id is not None:
                mess = await bot.send_message(
                    chat_id=target_chat_id,
                    reply_markup=templ.destroy_kb(),
                    text=templ.error_text(e),
                    parse_mode="HTML"
                )
        except Exception as e:
            if bot is not None and target_chat_id is not None:
                mess = await bot.send_message(
                    chat_id=target_chat_id,
                    reply_markup=templ.destroy_kb(),
                    text=templ.error_text(e),
                    parse_mode="HTML"
                )
    finally:
        if mess: await state.update_data(accent_message_id=mess.message_id)
    return mess
