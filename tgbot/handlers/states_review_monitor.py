"""Обработчики состояний для настройки мониторинга отзывов"""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from settings import Settings as sett
from ..states.all import ReviewMonitorStates
from .. import templates as templ

router = Router()


@router.message(ReviewMonitorStates.waiting_for_days, F.text)
async def process_review_monitor_days(message: Message, state: FSMContext):
    """Обработка ввода количества дней ожидания отзыва"""
    try:
        # шалтайболтай
        if message.text.startswith('/'):
            await state.clear()
            return

        # Проверяем, что введено число
        days = int(message.text.strip())
        
        if days < 1:
            await message.answer(
                "❌ Количество дней должно быть больше 0.\n\n"
                "Попробуйте ещё раз:",
                parse_mode="HTML"
            )
            return
        
        if days > 365:
            await message.answer(
                "❌ Количество дней не может быть больше 365.\n\n"
                "Попробуйте ещё раз:",
                parse_mode="HTML"
            )
            return
        
        # Сохраняем настройки
        config = sett.get("config")
        review_config = config.get("playerok", {}).get("review_monitoring", {})
        review_config["wait_days"] = days
        
        config["playerok"]["review_monitoring"] = review_config
        sett.set("config", config)
        
        await message.answer(
            f"✅ Время ожидания отзыва установлено: <b>{days} дн.</b>\n\n"
            "Теперь бот будет ожидать отзыв в течение указанного времени после подтверждения сделки.",
            parse_mode="HTML",
            reply_markup=templ.review_monitor_kb()
        )
        
        # Сбрасываем состояние
        await state.clear()
        
    except ValueError:
        await message.answer(
            "❌ Пожалуйста, введите корректное число.\n\n"
            "Попробуйте ещё раз",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(
            f"❌ Произошла ошибка: {e}\n\n",
            parse_mode="HTML"
        )
        await state.clear()
