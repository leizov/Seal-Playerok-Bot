from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext

from settings import Settings as sett

from .. import templates as templ
from .. import callback_datas as calls
from .. import states
from ..helpful import throw_float_message


router = Router()


def _parse_single_timing(raw_value: str) -> str:
    value = str(raw_value or "").strip()
    if not value:
        raise ValueError("пустое значение")

    if ":" in value:
        parts = value.split(":")
        if len(parts) != 2:
            raise ValueError("ожидается формат HH:MM")
        hour_str, minute_str = parts[0].strip(), parts[1].strip()
        if not hour_str.isdigit() or not minute_str.isdigit():
            raise ValueError("часы и минуты должны быть числами")
        hour = int(hour_str)
        minute = int(minute_str)
    else:
        if not value.isdigit():
            raise ValueError("часы должны быть числом")
        hour = int(value)
        minute = 0

    if hour < 0 or hour > 23:
        raise ValueError("часы должны быть в диапазоне 0-23")
    if minute < 0 or minute > 59:
        raise ValueError("минуты должны быть в диапазоне 0-59")

    return f"{hour:02d}:{minute:02d}"


def _parse_timings_text(raw_text: str) -> list[str]:
    tokens = [token.strip() for token in str(raw_text or "").split() if token.strip()]
    if not tokens:
        raise Exception("❌ Введите хотя бы один тайминг, например: <code>16</code> или <code>16:00</code>")

    parsed = []
    for token in tokens:
        try:
            parsed.append(_parse_single_timing(token))
        except ValueError:
            raise Exception(
                f"❌ Некорректный тайминг: <code>{token}</code>\n"
                "Используйте формат <code>16</code> или <code>16:00</code>"
            )

    unique_sorted = sorted(set(parsed), key=lambda item: (int(item[:2]), int(item[3:])))
    return unique_sorted


@router.message(states.RaiseItemsStates.waiting_for_new_included_raise_item_keyphrases, F.text)
async def handler_waiting_for_new_included_raise_item_keyphrases(message: types.Message, state: FSMContext):
    try: 
        await state.set_state(None)
        if len(message.text.strip()) <= 0:
            raise Exception("❌ Слишком короткое значение")
        
        keyphrases = [phrase.strip() for phrase in message.text.strip().split(",") if len(phrase.strip()) > 0]
        auto_raise_items = sett.get("auto_raise_items")
        auto_raise_items["included"].append(keyphrases)
        sett.set("auto_raise_items", auto_raise_items)

        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_new_raise_included_float_text(f"✅ Товар с ключевыми фразами <code>{'</code>, <code>'.join(keyphrases)}</code> успешно включён в автоподнятие"),
            reply_markup=templ.back_kb(calls.IncludedRaiseItemsPagination(page=last_page).pack())
        )
    except Exception as e:
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_new_raise_included_float_text(e), 
            reply_markup=templ.back_kb(calls.IncludedRaiseItemsPagination(page=last_page).pack())
        )


@router.message(
    states.RaiseItemsStates.waiting_for_new_included_raise_items_keyphrases_file, 
    F.document.file_name.lower().endswith('.txt')
)
async def handler_waiting_for_new_included_raise_items_keyphrases_file(message: types.Message, state: FSMContext):
    try:
        await state.set_state(None)
        file = await message.bot.get_file(message.document.file_id)
        downloaded_file = await message.bot.download_file(file.file_path)
        file_content = downloaded_file.read().decode('utf-8')

        keyphrases_list = []
        for line in file_content.splitlines():
            line = line.strip()
            if len(line) > 0:
                keyphrases = [phrase.strip() for phrase in line.split(",") if len(phrase.strip()) > 0]
                if len(keyphrases) > 0:
                    keyphrases_list.append(keyphrases)

        if len(keyphrases_list) <= 0:
            raise Exception("❌ Файл не содержит валидных ключевых фраз")

        auto_raise_items = sett.get("auto_raise_items")
        auto_raise_items["included"].extend(keyphrases_list)
        sett.set("auto_raise_items", auto_raise_items)

        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_new_raise_included_float_text(f"✅ Успешно включено <b>{len(keyphrases_list)}</b> товаров из файла в автоподнятие"),
            reply_markup=templ.back_kb(calls.IncludedRaiseItemsPagination(page=last_page).pack())
        )
    except Exception as e:
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_new_raise_included_float_text(e), 
            reply_markup=templ.back_kb(calls.IncludedRaiseItemsPagination(page=last_page).pack())
        )


@router.message(states.RaiseItemsStates.waiting_for_new_excluded_raise_item_keyphrases, F.text)
async def handler_waiting_for_new_excluded_raise_item_keyphrases(message: types.Message, state: FSMContext):
    try: 
        await state.set_state(None)
        if len(message.text.strip()) <= 0:
            raise Exception("❌ Слишком короткое значение")
        
        keyphrases = [phrase.strip() for phrase in message.text.strip().split(",") if len(phrase.strip()) > 0]
        auto_raise_items = sett.get("auto_raise_items")
        auto_raise_items["excluded"].append(keyphrases)
        sett.set("auto_raise_items", auto_raise_items)
    
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_new_raise_excluded_float_text(f"✅ Товар с ключевыми фразами <code>{'</code>, <code>'.join(keyphrases)}</code> успешно добавлен в исключения для автоподнятия"),
            reply_markup=templ.back_kb(calls.ExcludedRaiseItemsPagination(page=last_page).pack())
        )
    except Exception as e:
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_new_raise_excluded_float_text(e), 
            reply_markup=templ.back_kb(calls.ExcludedRaiseItemsPagination(page=last_page).pack())
        )


@router.message(
    states.RaiseItemsStates.waiting_for_new_excluded_raise_items_keyphrases_file, 
    F.document.file_name.lower().endswith('.txt')
)
async def handler_waiting_for_new_excluded_raise_items_keyphrases_file(message: types.Message, state: FSMContext):
    try:
        await state.set_state(None)
        file = await message.bot.get_file(message.document.file_id)
        downloaded_file = await message.bot.download_file(file.file_path)
        file_content = downloaded_file.read().decode('utf-8')

        keyphrases_list = []
        for line in file_content.splitlines():
            line = line.strip()
            if len(line) > 0:
                keyphrases = [phrase.strip() for phrase in line.split(",") if len(phrase.strip()) > 0]
                if len(keyphrases) > 0:
                    keyphrases_list.append(keyphrases)

        if len(keyphrases_list) <= 0:
            raise Exception("❌ Файл не содержит валидных ключевых фраз")

        auto_raise_items = sett.get("auto_raise_items")
        auto_raise_items["excluded"].extend(keyphrases_list)
        sett.set("auto_raise_items", auto_raise_items)

        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_new_raise_excluded_float_text(f"✅ Успешно добавлено <b>{len(keyphrases_list)}</b> товаров из файла в исключения для автоподнятия"),
            reply_markup=templ.back_kb(calls.ExcludedRaiseItemsPagination(page=last_page).pack())
        )
    except Exception as e:
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_new_raise_excluded_float_text(e), 
            reply_markup=templ.back_kb(calls.ExcludedRaiseItemsPagination(page=last_page).pack())
        )


@router.message(states.RaiseItemsStates.waiting_for_raise_interval, F.text)
async def handler_waiting_for_raise_interval(message: types.Message, state: FSMContext):
    try:
        await state.set_state(None)
        msg_text = message.text.strip()

        if ',' in msg_text:
            msg_text = msg_text.replace(',', '.')
        interval_hours = float(msg_text)
        
        if interval_hours <= 0:
            raise Exception("❌ Интервал должен быть положительным числом")
        
        if interval_hours > 8760:  # 365 дней
            raise Exception("❌ Интервал не может быть больше 8760 часов (365 дней)")
        
        config = sett.get("config")
        config["playerok"]["auto_raise_items"]["interval_hours"] = interval_hours
        sett.set("config", config)
        
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_raise_float_text(f"✅ Интервал автоподнятия установлен: <b>{interval_hours}</b> ч."),
            reply_markup=templ.back_kb(calls.SettingsNavigation(to="raise").pack())
        )
    except ValueError:
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_raise_float_text("❌ Введите корректное число"),
            reply_markup=templ.back_kb(calls.SettingsNavigation(to="raise").pack())
        )
    except Exception as e:
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_raise_float_text(e),
            reply_markup=templ.back_kb(calls.SettingsNavigation(to="raise").pack())
        )


@router.message(states.RaiseItemsStates.waiting_for_raise_timings, F.text)
async def handler_waiting_for_raise_timings(message: types.Message, state: FSMContext):
    try:
        await state.set_state(None)
        timings = _parse_timings_text(message.text.strip())

        config = sett.get("config")
        config["playerok"]["auto_raise_items"]["timings"] = timings
        sett.set("config", config)

        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_raise_float_text(
                f"✅ Тайминги автоподнятия сохранены: <code>{'</code> <code>'.join(timings)}</code>"
            ),
            reply_markup=templ.back_kb(calls.SettingsNavigation(to="raise").pack()),
        )
    except Exception as e:
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_raise_float_text(e),
            reply_markup=templ.back_kb(calls.SettingsNavigation(to="raise").pack()),
        )
