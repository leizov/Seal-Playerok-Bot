"""
Message handlers для states заготовок ответов.
"""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from settings import Settings as sett
from .. import callback_datas as calls
from ..templates.main import do_action_text, back_kb
from ..states.quick_replies import QuickReplyStates


router = Router()


@router.message(QuickReplyStates.waiting_for_name)
async def process_quick_reply_name(message: Message, state: FSMContext):
    """Обработка ввода названия новой заготовки"""
    await state.update_data(reply_name=message.text)
    await state.set_state(QuickReplyStates.waiting_for_text)
    await message.answer(
        do_action_text(f"📝 <b>Введите текст для заготовки '{message.text}':</b>\n\n<i>Это сообщение будет отправлено пользователю</i>"),
        reply_markup=back_kb(calls.SettingsNavigation(to="quick_replies").pack()),
        parse_mode="HTML"
    )


@router.message(QuickReplyStates.waiting_for_text)
async def process_quick_reply_text(message: Message, state: FSMContext):
    """Обработка ввода текста новой заготовки"""
    data = await state.get_data()
    reply_name = data.get("reply_name")
    
    quick_replies = sett.get("quick_replies")
    if not quick_replies:
        quick_replies = {}
    
    quick_replies[reply_name] = message.text
    sett.set("quick_replies", quick_replies)
    
    await state.clear()
    await message.answer(
        f"✅ Заготовка '<b>{reply_name}</b>' успешно добавлена!",
        reply_markup=back_kb(calls.SettingsNavigation(to="quick_replies").pack()),
        parse_mode="HTML"
    )


@router.message(QuickReplyStates.editing_text)
async def process_edit_quick_reply_text(message: Message, state: FSMContext):
    """Обработка редактирования текста заготовки"""
    data = await state.get_data()
    reply_name = data.get("reply_name")
    
    quick_replies = sett.get("quick_replies")
    quick_replies[reply_name] = message.text
    sett.set("quick_replies", quick_replies)
    
    await state.clear()
    await message.answer(
        f"✅ Заготовка '<b>{reply_name}</b>' успешно обновлена!",
        reply_markup=back_kb(calls.SettingsNavigation(to="quick_replies").pack()),
        parse_mode="HTML"
    )
