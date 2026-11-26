"""
Ввод данных для паков автоподнятия: название, интервал, тайминги, ключевые фразы,
место для режима «По позиции» и участки его расписания.
При ошибке ввода состояние остаётся — можно сразу отправить исправленное значение.
"""
import html

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from core import raise_packs

from .. import callback_datas as calls
from .. import states
from .. import templates as templ
from ..callback_handlers.raise_packs import (
    apply_segment_value,
    prompt_segment_step,
    segment_context,
    show_cooldown_confirm,
    show_pack,
    show_phrases,
    show_schedule,
)
from ..helpful import throw_float_message
from .states_raise import _parse_timings_text


router = Router()


def _validate_name(raw: str, packs: list[dict], except_id: str | None = None) -> str:
    name = " ".join(str(raw or "").split())
    if not name:
        raise ValueError("❌ Название не может быть пустым")
    if len(name) > raise_packs.MAX_NAME_LENGTH:
        raise ValueError(f"❌ Слишком длинное название — максимум {raise_packs.MAX_NAME_LENGTH} символов")
    if raise_packs.is_name_taken(name, packs, except_id=except_id):
        raise ValueError(f"❌ Пак «{html.escape(name, quote=False)}» уже есть — введите другое название")
    return name


async def _current_pack(message: types.Message, state: FSMContext):
    """Пак, который сейчас редактируется. Если его удалили — сообщает об этом и возвращает (packs, None)."""
    data = await state.get_data()
    packs = raise_packs.load_packs()
    _, pack = raise_packs.find_pack(packs, data.get("raise_pack_id") or "")
    if pack is None:
        await state.set_state(None)
        await throw_float_message(
            state=state,
            message=message,
            text=templ.raise_packs_float_text("❌ Пак не найден — возможно, он уже удалён"),
            reply_markup=templ.back_kb(calls.RaisePacksPagination(page=0).pack()),
        )
    return packs, pack


async def _input_error(message: types.Message, state: FSMContext, pack: dict, error, tail: str,
                       back_action: str = "open", back_index: int = 0):
    await throw_float_message(
        state=state,
        message=message,
        text=templ.raise_pack_float_text(pack, f"{error}\n\nОтправьте значение ещё раз ↓", tail=tail),
        reply_markup=templ.raise_pack_back_kb(pack, back_action, back_index),
    )


@router.message(states.RaisePacksStates.waiting_for_new_pack_name, F.text)
async def handler_new_raise_pack_name(message: types.Message, state: FSMContext):
    packs = raise_packs.load_packs()
    try:
        name = _validate_name(message.text, packs)
    except ValueError as e:
        return await throw_float_message(
            state=state,
            message=message,
            text=templ.raise_packs_float_text(f"➕ <b>Новый пак</b>\n\n{e}\n\nВведите название ещё раз ↓"),
            reply_markup=templ.back_kb(calls.RaisePacksPagination(page=0).pack()),
        )
    await state.set_state(None)
    pack = raise_packs.new_pack(name, packs)
    packs.append(pack)
    raise_packs.save_packs(packs)
    await show_pack(
        None, state, pack, packs, message=message,
        notice="✅ Пак создан. Теперь добавьте ключевые фразы — по ним бот поймёт, какие лоты в него входят.",
    )


@router.message(states.RaisePacksStates.waiting_for_pack_name, F.text)
async def handler_raise_pack_name(message: types.Message, state: FSMContext):
    packs, pack = await _current_pack(message, state)
    if pack is None:
        return
    try:
        name = _validate_name(message.text, packs, except_id=pack["id"])
    except ValueError as e:
        return await _input_error(message, state, pack, e, "✏️ Название")
    await state.set_state(None)
    pack["name"] = name
    raise_packs.save_packs(packs)
    await show_pack(None, state, pack, packs, message=message, notice="✅ Название изменено")


@router.message(states.RaisePacksStates.waiting_for_pack_interval, F.text)
async def handler_raise_pack_interval(message: types.Message, state: FSMContext):
    packs, pack = await _current_pack(message, state)
    if pack is None:
        return
    try:
        try:
            hours = float(message.text.strip().replace(",", "."))
        except ValueError:
            raise ValueError("❌ Введите число часов, например <code>6</code> или <code>1.5</code>")
        if hours <= 0:
            raise ValueError("❌ Интервал должен быть больше нуля")
        if hours > raise_packs.MAX_INTERVAL_HOURS:
            raise ValueError("❌ Интервал не может быть больше 8760 часов (365 дней)")
    except ValueError as e:
        return await _input_error(message, state, pack, e, "⏱ Интервал")
    await state.set_state(None)
    pack["interval_hours"] = hours
    raise_packs.save_packs(packs)
    await show_pack(
        None, state, pack, packs, message=message,
        notice=f"✅ Интервал пака: каждые {raise_packs.format_hours(hours)} ч",
    )


@router.message(states.RaisePacksStates.waiting_for_pack_timings, F.text)
async def handler_raise_pack_timings(message: types.Message, state: FSMContext):
    packs, pack = await _current_pack(message, state)
    if pack is None:
        return
    try:
        timings = _parse_timings_text(message.text.strip())
    except Exception as e:
        return await _input_error(message, state, pack, e, "🕒 Тайминг")
    await state.set_state(None)
    pack["timings"] = raise_packs.normalize_timings(timings)
    raise_packs.save_packs(packs)
    await show_pack(
        None, state, pack, packs, message=message,
        notice=f"✅ Тайминги пака (МСК): {', '.join(pack['timings'])}",
    )


async def _add_phrases(message: types.Message, state: FSMContext, text: str, source: str):
    packs, pack = await _current_pack(message, state)
    if pack is None:
        return
    data = await state.get_data()
    page = int(data.get("raise_pack_phrases_page") or 0)
    phrases = raise_packs.parse_keyphrases_text(text)
    if not phrases:
        return await _input_error(
            message, state, pack, f"❌ {source} не содержит ключевых фраз", "🔑 Ключевые фразы", "phrases", page,
        )
    await state.set_state(None)
    before = {p.lower() for p in pack["keyphrases"]}
    added = [p for p in phrases if p.lower() not in before]
    pack["keyphrases"] = raise_packs.normalize_keyphrases(pack["keyphrases"] + phrases)
    raise_packs.save_packs(packs)
    if added:
        shown = ", ".join(f"<code>{html.escape(p, quote=False)}</code>" for p in added[:10])
        if len(added) > 10:
            shown += f" и ещё {len(added) - 10}"
        notice = f"✅ Добавлено фраз: {len(added)} — {shown}"
    else:
        notice = "ℹ️ Все эти фразы уже есть в паке"
    skipped = len(phrases) - len(added)
    if added and skipped:
        notice += f"\nℹ️ Уже были в паке: {skipped}"
    last_page = templ.raise_pack_phrases_page(pack, 10 ** 6)
    await show_phrases(None, state, pack, page=last_page, notice=notice, message=message)


@router.message(states.RaisePacksStates.waiting_for_pack_phrases, F.text)
async def handler_raise_pack_phrases(message: types.Message, state: FSMContext):
    await _add_phrases(message, state, message.text, "Сообщение")


@router.message(states.RaisePacksStates.waiting_for_pack_phrases_file, F.document)
async def handler_raise_pack_phrases_file(message: types.Message, state: FSMContext):
    packs, pack = await _current_pack(message, state)
    if pack is None:
        return
    data = await state.get_data()
    page = int(data.get("raise_pack_phrases_page") or 0)
    file_name = (message.document.file_name or "").lower()
    if not file_name.endswith(".txt"):
        return await _input_error(
            message, state, pack, "❌ Нужен файл <b>.txt</b>", "🔑 Ключевые фразы", "phrases", page,
        )
    try:
        file = await message.bot.get_file(message.document.file_id)
        downloaded = await message.bot.download_file(file.file_path)
        text = downloaded.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        return await _input_error(
            message, state, pack, "❌ Файл должен быть в кодировке UTF-8", "🔑 Ключевые фразы", "phrases", page,
        )
    except Exception as e:
        return await _input_error(
            message, state, pack, f"❌ Не удалось прочитать файл: {html.escape(str(e), quote=False)}",
            "🔑 Ключевые фразы", "phrases", page,
        )
    await _add_phrases(message, state, text, "Файл")


@router.message(states.RaisePacksStates.waiting_for_pack_first_position, F.text)
async def handler_raise_pack_first_position(message: types.Message, state: FSMContext):
    packs, pack = await _current_pack(message, state)
    if pack is None:
        return
    try:
        position = raise_packs.parse_position(message.text)
    except ValueError as e:
        return await throw_float_message(
            state=state,
            message=message,
            text=templ.raise_pack_first_position_text(pack, error=str(e)),
            reply_markup=templ.raise_pack_back_kb(
                pack, "mode_pick", raise_packs.MODES.index(raise_packs.MODE_POSITION),
            ),
        )
    await state.set_state(None)
    pack["position_schedule"] = raise_packs.base_schedule(position)
    pack["mode"] = raise_packs.MODE_POSITION
    raise_packs.save_packs(packs)
    await show_pack(
        None, state, pack, packs, message=message,
        notice=(
            f"✅ Режим «По позиции»: весь день место ≤ {position}, кулдаун "
            f"{raise_packs.format_cooldown(raise_packs.DEFAULT_COOLDOWN_MINUTES)}.\n"
            "Участки времени со своим местом и кулдауном — в «📅 Расписание»."
        ),
    )


_SEGMENT_PARSERS = {
    "time": raise_packs.parse_time_range,
    "position": raise_packs.parse_position,
    "cooldown": raise_packs.parse_cooldown,
}


async def _segment_input(message: types.Message, state: FSMContext, field: str):
    packs, pack = await _current_pack(message, state)
    if pack is None:
        return
    ctx = segment_context(await state.get_data(), pack["id"])
    if ctx is None:
        await state.set_state(None)
        return await show_schedule(None, state, pack, message=message, notice="❌ Ввод устарел — начните заново")
    try:
        value = _SEGMENT_PARSERS[field](message.text)
    except ValueError as e:
        return await prompt_segment_step(state, pack, ctx, field, message=message, error=str(e))
    if field == "cooldown" and raise_packs.cooldown_needs_confirm(value):
        return await show_cooldown_confirm(state, pack, ctx, value, message=message)
    await apply_segment_value(state, pack, packs, ctx, field, value, message=message)


@router.message(states.RaisePacksStates.waiting_for_segment_time, F.text)
async def handler_raise_pack_segment_time(message: types.Message, state: FSMContext):
    await _segment_input(message, state, "time")


@router.message(states.RaisePacksStates.waiting_for_segment_position, F.text)
async def handler_raise_pack_segment_position(message: types.Message, state: FSMContext):
    await _segment_input(message, state, "position")


@router.message(states.RaisePacksStates.waiting_for_segment_cooldown, F.text)
async def handler_raise_pack_segment_cooldown(message: types.Message, state: FSMContext):
    await _segment_input(message, state, "cooldown")
