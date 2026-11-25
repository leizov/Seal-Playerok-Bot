"""
Автоподнятие: тип настройки «Все лоты / Паки» и управление паками.
"""
import asyncio
import html
from logging import getLogger

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from core import raise_packs
from playerokapi.enums import ItemStatuses
from settings import Settings as sett

from .. import callback_datas as calls
from .. import states
from .. import templates as templ
from ..helpful import get_playerok_bot, throw_float_message


router = Router()
logger = getLogger("seal.telegram.raise_packs")

# Паки, у которых сейчас идёт «Поднять сейчас» — чтобы не запустить дважды
_raising_now: set[str] = set()
_background_tasks: set[asyncio.Task] = set()


async def show_raise_menu(callback: CallbackQuery, state: FSMContext, page: int = 0, alert: str | None = None):
    if alert:
        await callback.answer(alert, show_alert=True)
    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.settings_raise_text(),
        reply_markup=templ.settings_raise_kb(page=page),
        callback=None if alert else callback,
    )


async def show_pack(callback, state: FSMContext, pack: dict, packs: list[dict], notice: str | None = None,
                    answered: bool = False, message=None):
    await throw_float_message(
        state=state,
        message=message if message is not None else callback.message,
        text=templ.raise_pack_text(pack, packs, notice=notice),
        reply_markup=templ.raise_pack_kb(pack, packs),
        callback=None if answered or callback is None else callback,
    )


async def show_phrases(callback, state: FSMContext, pack: dict, page: int = 0, notice: str | None = None,
                       message=None):
    await throw_float_message(
        state=state,
        message=message if message is not None else callback.message,
        text=templ.raise_pack_phrases_text(pack, notice=notice),
        reply_markup=templ.raise_pack_phrases_kb(pack, page),
        callback=callback,
    )


async def _load_lots(pack_id: str) -> dict:
    """Активные лоты аккаунта, разобранные относительно пака. Без подключения — исключение."""
    plbot = get_playerok_bot()
    if plbot is None or not getattr(plbot, "is_connected", False) or getattr(plbot, "account", None) is None:
        raise RuntimeError("Нет подключения к Playerok")
    items = await asyncio.to_thread(plbot.get_my_items, [ItemStatuses.APPROVED])
    excluded = (sett.get("auto_raise_items") or {}).get("excluded", [])
    return raise_packs.pack_lots(items, raise_packs.load_packs(), pack_id, excluded)


@router.callback_query(F.data == "switch_auto_raise_source")
async def callback_switch_auto_raise_source(callback: CallbackQuery, state: FSMContext):
    await state.set_state(None)
    config = sett.get("config")
    auto_raise_config = config["playerok"]["auto_raise_items"]
    current = raise_packs.normalize_source(auto_raise_config.get("source"))
    auto_raise_config["source"] = (
        raise_packs.SOURCE_LOTS if current == raise_packs.SOURCE_PACKS else raise_packs.SOURCE_PACKS
    )
    sett.set("config", config)
    await show_raise_menu(callback, state)


@router.callback_query(calls.RaisePacksPagination.filter())
async def callback_raise_packs_pagination(callback: CallbackQuery, callback_data: calls.RaisePacksPagination,
                                          state: FSMContext):
    await state.set_state(None)
    await show_raise_menu(callback, state, page=callback_data.page)


@router.callback_query(F.data == "raise_pack_create")
async def callback_raise_pack_create(callback: CallbackQuery, state: FSMContext):
    await state.set_state(states.RaisePacksStates.waiting_for_new_pack_name)
    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.raise_packs_float_text(
            "➕ <b>Новый пак</b>\n\n"
            f"Введите название пака (до {raise_packs.MAX_NAME_LENGTH} символов) ↓\n\n"
            "<i>Пак создастся включённым, с интервалом 24 ч. Потом добавьте в него ключевые фразы.</i>"
        ),
        reply_markup=templ.back_kb(calls.RaisePacksPagination(page=0).pack()),
        callback=callback,
    )


@router.callback_query(calls.RaisePackAction.filter())
async def callback_raise_pack_action(callback: CallbackQuery, callback_data: calls.RaisePackAction,
                                     state: FSMContext):
    await state.set_state(None)
    packs = raise_packs.load_packs()
    position, pack = raise_packs.find_pack(packs, callback_data.pid)
    if pack is None:
        return await show_raise_menu(callback, state, alert="Пак не найден — возможно, он уже удалён")

    action = callback_data.action

    if action == "open":
        return await show_pack(callback, state, pack, packs)

    if action == "toggle":
        pack["enabled"] = not pack["enabled"]
        raise_packs.save_packs(packs)
        return await show_pack(callback, state, pack, packs)

    if action == "mode":
        pack["mode"] = (
            raise_packs.MODE_INTERVAL if pack["mode"] == raise_packs.MODE_TIMING else raise_packs.MODE_TIMING
        )
        raise_packs.save_packs(packs)
        return await show_pack(callback, state, pack, packs)

    if action in ("up", "down"):
        target = position - 1 if action == "up" else position + 1
        if 0 <= target < len(packs):
            packs[position], packs[target] = packs[target], packs[position]
            raise_packs.save_packs(packs)
        return await show_pack(callback, state, pack, packs)

    if action == "interval":
        await state.set_state(states.RaisePacksStates.waiting_for_pack_interval)
        await state.update_data(raise_pack_id=pack["id"])
        return await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.raise_pack_float_text(
                pack,
                f"Текущий интервал: <b>{raise_packs.format_hours(pack['interval_hours'])}</b> ч\n\n"
                "Введите новый интервал в часах, например <code>6</code> или <code>1.5</code> ↓\n\n"
                "<i>Лот пака поднимается, когда с его последнего поднятия прошло столько часов.</i>",
                tail="⏱ Интервал",
            ),
            reply_markup=templ.raise_pack_back_kb(pack),
            callback=callback,
        )

    if action == "timings":
        await state.set_state(states.RaisePacksStates.waiting_for_pack_timings)
        await state.update_data(raise_pack_id=pack["id"])
        current = " ".join(pack["timings"]) or "не задано"
        return await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.raise_pack_float_text(
                pack,
                f"Текущие тайминги: <b>{current}</b>\n\n"
                "Введите тайминги через пробел в формате <code>16</code> или <code>16:00</code> ↓\n\n"
                "<i>Время по МСК. Лоты пака поднимаются в каждый тайминг (±5 минут) один раз в день.</i>",
                tail="🕒 Тайминг",
            ),
            reply_markup=templ.raise_pack_back_kb(pack),
            callback=callback,
        )

    if action == "rename":
        await state.set_state(states.RaisePacksStates.waiting_for_pack_name)
        await state.update_data(raise_pack_id=pack["id"])
        return await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.raise_pack_float_text(
                pack,
                f"Введите новое название пака (до {raise_packs.MAX_NAME_LENGTH} символов) ↓",
                tail="✏️ Название",
            ),
            reply_markup=templ.raise_pack_back_kb(pack),
            callback=callback,
        )

    if action == "delete":
        return await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.raise_pack_delete_text(pack),
            reply_markup=templ.raise_pack_delete_kb(pack),
            callback=callback,
        )

    if action == "delete_yes":
        page = templ.raise_packs_list_page(packs, pack["id"])
        packs.pop(position)
        raise_packs.save_packs(packs)
        await callback.answer(f"🗑 Пак «{pack['name']}» удалён")
        return await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.settings_raise_text(),
            reply_markup=templ.settings_raise_kb(page=page),
        )

    if action == "phrases":
        return await show_phrases(callback, state, pack, page=callback_data.index)

    if action == "phrase_del":
        index = callback_data.index
        if 0 <= index < len(pack["keyphrases"]):
            removed = pack["keyphrases"].pop(index)
            raise_packs.save_packs(packs)
            notice = f"🗑 Фраза <code>{html.escape(removed, quote=False)}</code> удалена"
        else:
            notice = None
        page = templ.raise_pack_phrases_page(pack, index // templ.RAISE_PACK_PHRASES_PER_PAGE)
        return await show_phrases(callback, state, pack, page=page, notice=notice)

    if action in ("phrase_add", "phrase_file"):
        is_file = action == "phrase_file"
        await state.set_state(
            states.RaisePacksStates.waiting_for_pack_phrases_file if is_file
            else states.RaisePacksStates.waiting_for_pack_phrases
        )
        await state.update_data(raise_pack_id=pack["id"], raise_pack_phrases_page=callback_data.index)
        prompt = (
            "📄 Отправьте <b>.txt</b> файл с ключевыми фразами — по одной в строке "
            "(в строке можно указать несколько через запятую) ↓"
            if is_file else
            "Введите ключевые фразы через запятую или каждую с новой строки ↓\n\n"
            "Например: <code>duolingo, дуолинго, super</code>"
        )
        return await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.raise_pack_float_text(pack, prompt, tail="🔑 Ключевые фразы"),
            reply_markup=templ.raise_pack_back_kb(pack, "phrases", callback_data.index),
            callback=callback,
        )

    if action == "lots":
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.raise_pack_float_text(pack, "⏳ Загружаю лоты аккаунта…", tail="🔍 Подходящие лоты"),
            reply_markup=templ.raise_pack_back_kb(pack),
            callback=callback,
        )
        try:
            lots = await _load_lots(pack["id"])
        except Exception as e:
            return await throw_float_message(
                state=state,
                message=callback.message,
                text=templ.raise_pack_float_text(
                    pack, f"❌ Не удалось загрузить лоты: {html.escape(str(e), quote=False)}",
                    tail="🔍 Подходящие лоты",
                ),
                reply_markup=templ.raise_pack_lots_kb(pack),
            )
        return await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.raise_pack_lots_text(pack, lots),
            reply_markup=templ.raise_pack_lots_kb(pack),
        )

    if action == "raise":
        if pack["id"] in _raising_now:
            return await callback.answer("⏳ Этот пак уже поднимается, дождитесь итога", show_alert=True)
        if not pack["keyphrases"]:
            return await callback.answer("В паке нет ключевых фраз — поднимать нечего", show_alert=True)
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.raise_pack_float_text(pack, "⏳ Считаю лоты для поднятия…", tail="🚀 Поднять сейчас"),
            reply_markup=templ.raise_pack_back_kb(pack),
            callback=callback,
        )
        try:
            lots = await _load_lots(pack["id"])
        except Exception as e:
            return await throw_float_message(
                state=state,
                message=callback.message,
                text=templ.raise_pack_float_text(
                    pack, f"❌ Не удалось загрузить лоты: {html.escape(str(e), quote=False)}",
                    tail="🚀 Поднять сейчас",
                ),
                reply_markup=templ.raise_pack_back_kb(pack),
            )
        items = lots["raise"]
        if not items:
            return await throw_float_message(
                state=state,
                message=callback.message,
                text=templ.raise_pack_float_text(
                    pack,
                    "Сейчас нет лотов, которые поднимает этот пак.\n"
                    "Проверьте «🔍 Какие лоты подходят»: поднимаются только активные лоты с премиум-статусом.",
                    tail="🚀 Поднять сейчас",
                ),
                reply_markup=templ.raise_pack_back_kb(pack),
            )
        await state.update_data(raise_pack_now={"pack": pack["id"], "ids": [item.id for item in items]})
        return await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.raise_pack_raise_confirm_text(pack, items),
            reply_markup=templ.raise_pack_raise_confirm_kb(pack, len(items)),
        )

    if action == "raise_yes":
        data = await state.get_data()
        planned = data.get("raise_pack_now") or {}
        if planned.get("pack") != pack["id"] or not planned.get("ids"):
            await callback.answer("Подтверждение устарело — нажмите «🚀 Поднять сейчас» ещё раз", show_alert=True)
            return await show_pack(callback, state, pack, packs, answered=True)
        if pack["id"] in _raising_now:
            await callback.answer("⏳ Этот пак уже поднимается, дождитесь итога", show_alert=True)
            return await show_pack(callback, state, pack, packs, answered=True)
        await state.update_data(raise_pack_now=None)
        ids = list(planned["ids"])
        _raising_now.add(pack["id"])
        task = asyncio.create_task(_raise_now(callback, pack, ids))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
        return await show_pack(
            callback, state, pack, packs,
            notice=f"⏳ Поднимаю лоты пака: {len(ids)}. Когда закончу — пришлю итог отдельным сообщением.",
        )

    await callback.answer()


async def _raise_now(callback: CallbackQuery, pack: dict, item_ids: list[str]):
    """Разовое поднятие лотов пака (кнопка «Поднять сейчас»), итог — отдельным сообщением."""
    raised: list[str] = []
    failed: list[str] = []
    missing = 0
    try:
        plbot = get_playerok_bot()
        if plbot is None or not getattr(plbot, "is_connected", False):
            raise RuntimeError("Нет подключения к Playerok")
        items = await asyncio.to_thread(plbot.get_my_items, [ItemStatuses.APPROVED])
        by_id = {item.id: item for item in items}
        targets = [by_id[item_id] for item_id in item_ids if item_id in by_id]
        missing = len(item_ids) - len(targets)
        for number, item in enumerate(targets):
            if number:
                await asyncio.sleep(2)
            logger.info(f"🚀 Поднимаю товар «{item.name}» (пак «{pack['name']}», вручную)")
            try:
                ok = await asyncio.to_thread(plbot.raise_item, item)
            except Exception as e:
                logger.error(f"Не удалось поднять товар «{item.name}»: {e}")
                ok = False
            (raised if ok else failed).append(item.name)

        lines = [f"🚀 <b>Пак «{html.escape(pack['name'], quote=False)}»: поднято {len(raised)} из {len(item_ids)}</b>"]
        if failed:
            lines += ["", f"❌ Не удалось поднять ({len(failed)}):"]
            lines += [f"• {html.escape(name, quote=False)}" for name in failed[:15]]
            if len(failed) > 15:
                lines.append(f"…и ещё {len(failed) - 15}")
            lines.append("<i>Подробности — в логе бота.</i>")
        if missing:
            lines += ["", f"⚪ Пропущено {missing}: лоты больше не активны."]
        text = "\n".join(lines)
    except Exception as e:
        logger.error(f"Ошибка ручного поднятия пака «{pack['name']}»: {e}", exc_info=True)
        text = (
            f"❌ <b>Пак «{html.escape(pack['name'], quote=False)}»:</b> поднятие прервано — "
            f"{html.escape(str(e), quote=False)}\nУспели поднять: {len(raised)}"
        )
    finally:
        _raising_now.discard(pack["id"])
    try:
        if callback.message is not None:
            await callback.message.answer(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Не удалось отправить итог поднятия пака: {e}")
