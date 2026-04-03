from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext

from plbot.auto_reminder import DEFAULT_MESSAGE_TEXT, LEGACY_DEFAULT_MESSAGE_TEXT
from settings import Settings as sett

from .. import templates as templ
from .. import callback_datas as calls
from .. import states
from ..helpful import throw_float_message


router = Router()


def _ensure_auto_reminder_config(config: dict) -> dict:
    playerok = config.setdefault("playerok", {})
    auto_reminder = playerok.setdefault("auto_reminder", {})
    auto_reminder.setdefault("enabled", False)
    auto_reminder.setdefault("interval_hours", 24.0)
    auto_reminder.setdefault("max_reminders", 3)
    current_message = str(auto_reminder.get("message_text") or "").strip()
    if not current_message or current_message == LEGACY_DEFAULT_MESSAGE_TEXT:
        auto_reminder["message_text"] = DEFAULT_MESSAGE_TEXT
    return auto_reminder


@router.message(states.AutoReminderStates.waiting_for_interval_hours, F.text)
async def handler_waiting_for_auto_reminder_interval(message: types.Message, state: FSMContext):
    try:
        await state.set_state(None)
        text = message.text.strip().replace(",", ".")
        interval_hours = float(text)

        if interval_hours <= 0:
            raise Exception("❌ Интервал должен быть больше 0.")
        if interval_hours > 8760:
            raise Exception("❌ Интервал не может быть больше 8760 часов (365 дней).")

        config = sett.get("config")
        auto_reminder = _ensure_auto_reminder_config(config)
        auto_reminder["interval_hours"] = interval_hours
        sett.set("config", config)

        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_auto_reminder_float_text(
                f"✅ Интервал авто-напоминаний установлен: <b>{interval_hours:g}</b> ч."
            ),
            reply_markup=templ.back_kb(calls.SettingsNavigation(to="auto_reminder").pack()),
        )
    except ValueError:
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_auto_reminder_float_text("❌ Введите корректное число (например: <code>24</code> или <code>12.5</code>)."),
            reply_markup=templ.back_kb(calls.SettingsNavigation(to="auto_reminder").pack()),
        )
    except Exception as e:
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_auto_reminder_float_text(str(e)),
            reply_markup=templ.back_kb(calls.SettingsNavigation(to="auto_reminder").pack()),
        )


@router.message(states.AutoReminderStates.waiting_for_max_reminders, F.text)
async def handler_waiting_for_auto_reminder_max_reminders(message: types.Message, state: FSMContext):
    try:
        await state.set_state(None)
        max_reminders = int(message.text.strip())

        if max_reminders < 0:
            raise Exception("❌ Лимит не может быть меньше 0.")
        if max_reminders > 1000:
            raise Exception("❌ Лимит не может быть больше 1000.")

        config = sett.get("config")
        auto_reminder = _ensure_auto_reminder_config(config)
        auto_reminder["max_reminders"] = max_reminders
        sett.set("config", config)

        limit_text = "♾ Без лимита" if max_reminders == 0 else str(max_reminders)
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_auto_reminder_float_text(
                f"✅ Лимит авто-напоминаний установлен: <b>{limit_text}</b>"
            ),
            reply_markup=templ.back_kb(calls.SettingsNavigation(to="auto_reminder").pack()),
        )
    except ValueError:
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_auto_reminder_float_text("❌ Введите целое число (например: <code>3</code> или <code>0</code> для безлимита)."),
            reply_markup=templ.back_kb(calls.SettingsNavigation(to="auto_reminder").pack()),
        )
    except Exception as e:
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_auto_reminder_float_text(str(e)),
            reply_markup=templ.back_kb(calls.SettingsNavigation(to="auto_reminder").pack()),
        )


@router.message(states.AutoReminderStates.waiting_for_message_text, F.text)
async def handler_waiting_for_auto_reminder_message_text(message: types.Message, state: FSMContext):
    try:
        await state.set_state(None)
        message_text = message.text.strip()

        if len(message_text) < 1:
            raise Exception("❌ Текст напоминания не может быть пустым.")
        if len(message_text) > 2000:
            raise Exception("❌ Текст напоминания слишком длинный (максимум 2000 символов).")

        config = sett.get("config")
        auto_reminder = _ensure_auto_reminder_config(config)
        auto_reminder["message_text"] = message_text
        sett.set("config", config)

        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_auto_reminder_float_text(
                "✅ Текст авто-напоминания успешно обновлён.\n\n"
                "Доступные теги:\n"
                "• <code>{deal_link}</code>\n"
                "• <code>{buyer_name}</code>"
            ),
            reply_markup=templ.back_kb(calls.SettingsNavigation(to="auto_reminder").pack()),
        )
    except Exception as e:
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_auto_reminder_float_text(str(e)),
            reply_markup=templ.back_kb(calls.SettingsNavigation(to="auto_reminder").pack()),
        )
