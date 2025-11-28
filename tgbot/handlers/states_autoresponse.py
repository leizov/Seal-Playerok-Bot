from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext

from settings import Settings as sett

from .. import templates as templ
from .. import states
from .. import callback_datas as calls
from ..helpful import throw_float_message


router = Router()


# Маппинг типов автоответов на ключи в messages.json
MESSAGE_TYPE_MAPPING = {
    "greeting": "first_message",
    "confirmation_seller": "deal_sent",
    "confirmation_buyer": "deal_confirmed",
    "review": "new_review_response"
}


def save_auto_response_text(message_key: str, text: str):
    """Сохраняет текст автоответа в настройки"""
    messages = sett.get("messages")
    
    # Разбиваем текст на строки
    text_lines = text.split('\n')
    
    if message_key not in messages:
        messages[message_key] = {"enabled": False, "text": []}
    
    messages[message_key]["text"] = text_lines
    sett.set("messages", messages)


@router.message(states.AutoResponseStates.waiting_for_greeting_text, F.text)
async def handler_waiting_for_greeting_text(message: types.Message, state: FSMContext):
    try:
        await state.set_state(None)
        
        if len(message.text.strip()) < 1:
            raise Exception("❌ Текст не может быть пустым")
        
        if len(message.text) > 2000:
            raise Exception("❌ Текст слишком длинный (максимум 2000 символов)")
        
        save_auto_response_text("first_message", message.text)
        
        await throw_float_message(
            state=state,
            message=message,
            text="✅ <b>Приветственное сообщение</b> успешно обновлено!",
            reply_markup=templ.back_kb(calls.MessagesNavigation(to="greeting").pack())
        )
    except Exception as e:
        await throw_float_message(
            state=state,
            message=message,
            text=str(e),
            reply_markup=templ.back_kb(calls.MessagesNavigation(to="greeting").pack())
        )


@router.message(states.AutoResponseStates.waiting_for_confirmation_seller_text, F.text)
async def handler_waiting_for_confirmation_seller_text(message: types.Message, state: FSMContext):
    try:
        await state.set_state(None)
        
        if len(message.text.strip()) < 1:
            raise Exception("❌ Текст не может быть пустым")
        
        if len(message.text) > 2000:
            raise Exception("❌ Текст слишком длинный (максимум 2000 символов)")
        
        save_auto_response_text("deal_sent", message.text)
        
        await throw_float_message(
            state=state,
            message=message,
            text="✅ <b>Сообщение при подтверждении (наша сторона)</b> успешно обновлено!",
            reply_markup=templ.back_kb(calls.MessagesNavigation(to="confirmation_seller").pack())
        )
    except Exception as e:
        await throw_float_message(
            state=state,
            message=message,
            text=str(e),
            reply_markup=templ.back_kb(calls.MessagesNavigation(to="confirmation_seller").pack())
        )


@router.message(states.AutoResponseStates.waiting_for_confirmation_buyer_text, F.text)
async def handler_waiting_for_confirmation_buyer_text(message: types.Message, state: FSMContext):
    try:
        await state.set_state(None)
        
        if len(message.text.strip()) < 1:
            raise Exception("❌ Текст не может быть пустым")
        
        if len(message.text) > 2000:
            raise Exception("❌ Текст слишком длинный (максимум 2000 символов)")
        
        save_auto_response_text("deal_confirmed", message.text)
        
        await throw_float_message(
            state=state,
            message=message,
            text="✅ <b>Сообщение при подтверждении покупателем</b> успешно обновлено!",
            reply_markup=templ.back_kb(calls.MessagesNavigation(to="confirmation_buyer").pack())
        )
    except Exception as e:
        await throw_float_message(
            state=state,
            message=message,
            text=str(e),
            reply_markup=templ.back_kb(calls.MessagesNavigation(to="confirmation_buyer").pack())
        )


@router.message(states.AutoResponseStates.waiting_for_review_text, F.text)
async def handler_waiting_for_review_text(message: types.Message, state: FSMContext):
    try:
        await state.set_state(None)
        
        if len(message.text.strip()) < 1:
            raise Exception("❌ Текст не может быть пустым")
        
        if len(message.text) > 2000:
            raise Exception("❌ Текст слишком длинный (максимум 2000 символов)")
        
        save_auto_response_text("new_review_response", message.text)
        
        await throw_float_message(
            state=state,
            message=message,
            text="✅ <b>Сообщение при получении отзыва</b> успешно обновлено!",
            reply_markup=templ.back_kb(calls.MessagesNavigation(to="review").pack())
        )
    except Exception as e:
        await throw_float_message(
            state=state,
            message=message,
            text=str(e),
            reply_markup=templ.back_kb(calls.MessagesNavigation(to="review").pack())
        )


@router.message(states.AutoResponseStates.waiting_for_greeting_cooldown, F.text)
async def handler_waiting_for_greeting_cooldown(message: types.Message, state: FSMContext):
    """Обработка ввода нового интервала приветствий"""
    try:
        await state.set_state(None)
        
        # Проверяем, что введено число
        try:
            days = int(message.text.strip())
        except ValueError:
            raise Exception("❌ Введите целое число дней")
        
        if days < 1:
            raise Exception("❌ Интервал должен быть минимум 1 день")
        
        if days > 365:
            raise Exception("❌ Интервал не может быть больше 365 дней")
        
        # Сохраняем новое значение
        messages = sett.get("messages")
        if "first_message" not in messages:
            messages["first_message"] = {"enabled": True, "text": [], "cooldown_days": days}
        else:
            messages["first_message"]["cooldown_days"] = days
        sett.set("messages", messages)
        
        await throw_float_message(
            state=state,
            message=message,
            text=f"✅ Интервал приветствий изменён на <b>{days}</b> дн.",
            reply_markup=templ.back_kb(calls.MessagesNavigation(to="greeting").pack())
        )
    except Exception as e:
        await throw_float_message(
            state=state,
            message=message,
            text=str(e),
            reply_markup=templ.back_kb(calls.MessagesNavigation(to="greeting").pack())
        )
