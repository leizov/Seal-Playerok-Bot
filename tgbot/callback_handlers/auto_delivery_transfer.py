"""🔄 Выгрузка / загрузка авто-выдач: кнопки."""

import asyncio
import copy
import logging
from html import escape

from aiogram import F, Router
from aiogram.exceptions import TelegramRetryAfter
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from core.auto_deliveries import normalize_auto_deliveries
from core.auto_delivery_transfer import (
    AutoDeliveryImportError,
    DECISION_REPLACE,
    DECISION_SKIP,
    apply_import,
    build_export_json,
    build_export_txt,
    delivery_signature,
    export_file_name,
    find_conflicts,
    find_delivery_index,
    find_internal_duplicates,
    is_multi,
    plain_text_lines,
    remove_exported_items,
    restore_removed_items,
)
from settings import Settings as sett

from .. import callback_datas as calls
from .. import states
from .. import templates as templ
from ..helpful import throw_float_message


router = Router()
logger = logging.getLogger("seal.telegram.auto_delivery_transfer")

TEXT_CHUNK_BUDGET = 3800   # символов на одно сообщение (лимит Telegram — 4096 вместе с заголовком)
TEXT_MAX_MESSAGES = 10     # больше — отправляем тем же содержимым в .txt


# ───────────────────────── хранилище ─────────────────────────

def load_deliveries() -> list[dict]:
    return normalize_auto_deliveries(sett.get("auto_deliveries") or [])


def save_deliveries(deliveries: list[dict]) -> None:
    """Сохраняет список и сразу обновляет память Playerok-бота (иначе он может выдать
    уже выгруженный товар или записать поверх файла старый список)."""
    normalized = normalize_auto_deliveries(deliveries)
    sett.set("auto_deliveries", normalized)
    if load_deliveries() != normalized:
        raise RuntimeError("Не удалось сохранить авто-выдачи на диск (подробности в логе)")
    try:
        from plbot.playerokbot import get_playerok_bot

        playerok_bot = get_playerok_bot()
        if playerok_bot is not None:
            playerok_bot.auto_deliveries = copy.deepcopy(normalized)
    except Exception as e:
        logger.warning("Не удалось обновить авто-выдачи в памяти Playerok-бота: %s", e)


def _delete_unused_images(before: list[dict], after: list[dict]) -> None:
    """Удаляет файлы картинок авто-выдач, которые пропали из списка (например, при замене)."""
    old_refs = {ref for d in before for ref in d.get("images", [])}
    new_refs = {ref for d in after for ref in d.get("images", [])}
    if old_refs - new_refs:
        try:
            from core.chat_images import delete_images

            delete_images(old_refs - new_refs)
        except Exception as e:
            logger.warning("Не удалось удалить картинки заменённых авто-выдач: %s", e)


def _has_access(user_id: int) -> bool:
    config = sett.get("config") or {}
    return user_id in config.get("telegram", {}).get("bot", {}).get("signed_users", [])


async def _deny(callback: CallbackQuery) -> bool:
    if _has_access(callback.from_user.id):
        return False
    await callback.answer("❌ Нет доступа к выгрузке и загрузке авто-выдач", show_alert=True)
    return True


# ───────────────────────── выбор авто-выдач ─────────────────────────

def _resolve_selected(data: dict, deliveries: list[dict]) -> list[int]:
    """Выбранные авто-выдачи хранятся с отпечатком — так выбор не «съедет», если список изменится."""
    result = []
    for entry in data.get("adt_selected") or []:
        idx = find_delivery_index(deliveries, entry.get("signature") or [], entry.get("index"))
        if idx is not None and idx not in result:
            result.append(idx)
    return result


def _pack_selected(indices: list[int], deliveries: list[dict]) -> list[dict]:
    return [{"index": i, "signature": delivery_signature(deliveries[i])} for i in indices]


def _main_targets(data: dict, deliveries: list[dict]) -> tuple[list[int], bool]:
    mode_all = data.get("adt_mode") != "some"
    if mode_all:
        return list(range(len(deliveries))), True
    return _resolve_selected(data, deliveries), False


def _resolve_one(data: dict, deliveries: list[dict]) -> int | None:
    return find_delivery_index(deliveries, data.get("adt_one_signature") or [], data.get("auto_delivery_index"))


# ───────────────────────── отрисовка экранов ─────────────────────────

async def _show_menu(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await throw_float_message(
        state, callback.message,
        templ.adt_menu_text(load_deliveries()),
        templ.adt_menu_kb(data.get("last_page", 0)),
        callback,
    )


async def _show_select(callback: CallbackQuery, state: FSMContext, view: str, page: int):
    data = await state.get_data()
    deliveries = load_deliveries()
    selected = _resolve_selected(data, deliveries)
    await state.update_data(adt_selected=_pack_selected(selected, deliveries), adt_mode="some")
    if view == "pick":
        text = templ.adt_pick_text(deliveries, selected)
        kb = templ.adt_pick_kb(deliveries, selected, page)
    else:
        text = templ.adt_select_text(deliveries, selected)
        kb = templ.adt_select_kb(deliveries, selected, page)
    await throw_float_message(state, callback.message, text, kb, callback)


async def _show_format(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    deliveries = load_deliveries()
    targets, mode_all = _main_targets(data, deliveries)
    if not targets:
        if mode_all:
            await throw_float_message(
                state, callback.message,
                templ.adt_export_float_text("❌ Авто-выдач пока нет — выгружать нечего"),
                templ.back_kb(templ.ADT_MENU_CB), callback,
            )
        else:
            await _show_select(callback, state, "sel", 0)
        return

    chosen = [deliveries[i] for i in targets]
    include_multi = data.get("adt_include_multi", True)
    delete_multi = data.get("adt_delete_multi", False)
    back_cb = templ.ADT_EXPORT_CB if mode_all else calls.AutoDeliveryTransferNav(view="sel", page=0).pack()
    await throw_float_message(
        state, callback.message,
        templ.adt_format_text(chosen, mode_all, include_multi, delete_multi),
        templ.adt_format_kb(any(is_multi(d) for d in chosen), include_multi, delete_multi, back_cb),
        callback,
    )


async def _show_one(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    deliveries = load_deliveries()
    idx = _resolve_one(data, deliveries)
    if idx is None:
        await throw_float_message(
            state, callback.message,
            templ.adt_one_float_text("❌ Авто-выдача не найдена — возможно, её уже удалили"),
            templ.back_kb(calls.AutoDeliveriesPagination(page=data.get("last_page", 0)).pack()), callback,
        )
        return
    await state.update_data(auto_delivery_index=idx, adt_one_signature=delivery_signature(deliveries[idx]))
    delete_items = data.get("adt_one_delete", False)
    await throw_float_message(
        state, callback.message,
        templ.adt_one_text(deliveries[idx], delete_items),
        templ.adt_one_kb(idx, deliveries[idx], delete_items),
        callback,
    )


# ───────────────────────── меню ─────────────────────────

@router.callback_query(F.data == templ.ADT_NOOP_CB)
async def callback_adt_noop(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(F.data == templ.ADT_MENU_CB)
async def callback_adt_menu(callback: CallbackQuery, state: FSMContext):
    await state.set_state(None)
    await state.update_data(adt_import=None, adt_pending_export=None)
    await _show_menu(callback, state)


@router.callback_query(F.data == templ.ADT_EXPORT_CB)
async def callback_adt_export(callback: CallbackQuery, state: FSMContext):
    if await _deny(callback):
        return
    await state.set_state(None)
    await state.update_data(adt_pending_export=None)
    await throw_float_message(state, callback.message, templ.adt_export_text(load_deliveries()), templ.adt_export_kb(), callback)


@router.callback_query(F.data == templ.ADT_EXPORT_ALL_CB)
async def callback_adt_export_all(callback: CallbackQuery, state: FSMContext):
    if await _deny(callback):
        return
    if not load_deliveries():
        await callback.answer("Авто-выдач пока нет — выгружать нечего", show_alert=True)
        return
    await state.update_data(adt_mode="all", adt_include_multi=True, adt_delete_multi=False, adt_pending_export=None)
    await _show_format(callback, state)


@router.callback_query(F.data == templ.ADT_EXPORT_SOME_CB)
async def callback_adt_export_some(callback: CallbackQuery, state: FSMContext):
    if await _deny(callback):
        return
    await _show_select(callback, state, "sel", 0)


@router.callback_query(calls.AutoDeliveryTransferNav.filter())
async def callback_adt_nav(callback: CallbackQuery, callback_data: calls.AutoDeliveryTransferNav, state: FSMContext):
    if await _deny(callback):
        return
    await _show_select(callback, state, callback_data.view, callback_data.page)


@router.callback_query(calls.AutoDeliveryTransferPick.filter())
async def callback_adt_pick(callback: CallbackQuery, callback_data: calls.AutoDeliveryTransferPick, state: FSMContext):
    if await _deny(callback):
        return
    data = await state.get_data()
    deliveries = load_deliveries()
    selected = _resolve_selected(data, deliveries)
    idx = callback_data.index
    if 0 <= idx < len(deliveries):
        if idx in selected:
            selected.remove(idx)
        else:
            selected.append(idx)
        await state.update_data(adt_selected=_pack_selected(selected, deliveries))
    await _show_select(callback, state, callback_data.view, callback_data.page)


@router.callback_query(F.data == templ.ADT_CLEAR_CB)
async def callback_adt_clear(callback: CallbackQuery, state: FSMContext):
    await state.update_data(adt_selected=[])
    await _show_select(callback, state, "sel", 0)


@router.callback_query(F.data == templ.ADT_SOME_NEXT_CB)
async def callback_adt_some_next(callback: CallbackQuery, state: FSMContext):
    if await _deny(callback):
        return
    data = await state.get_data()
    if not _resolve_selected(data, load_deliveries()):
        await callback.answer("Сначала выберите хотя бы одну авто-выдачу", show_alert=True)
        return
    await state.update_data(adt_mode="some", adt_include_multi=True, adt_delete_multi=False, adt_pending_export=None)
    await _show_format(callback, state)


@router.callback_query(F.data == templ.ADT_FORMAT_MAIN_CB)
async def callback_adt_format_main(callback: CallbackQuery, state: FSMContext):
    await state.update_data(adt_pending_export=None)
    await _show_format(callback, state)


@router.callback_query(F.data == templ.ADT_TOGGLE_MULTI_CB)
async def callback_adt_toggle_multi(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    include_multi = not data.get("adt_include_multi", True)
    # «Удалить выгруженные» имеет смысл только когда мультивыдача выгружается — при выключении сбрасываем.
    await state.update_data(adt_include_multi=include_multi, adt_delete_multi=False if not include_multi else data.get("adt_delete_multi", False))
    await _show_format(callback, state)


@router.callback_query(F.data == templ.ADT_TOGGLE_DELETE_CB)
async def callback_adt_toggle_delete(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.update_data(adt_delete_multi=not data.get("adt_delete_multi", False))
    await _show_format(callback, state)


# ───────────────────────── выгрузка из карточки ─────────────────────────

@router.callback_query(F.data == templ.ADT_ONE_CB)
async def callback_adt_one(callback: CallbackQuery, state: FSMContext):
    if await _deny(callback):
        return
    await state.set_state(None)
    data = await state.get_data()
    deliveries = load_deliveries()
    idx = data.get("auto_delivery_index")
    signature = delivery_signature(deliveries[idx]) if isinstance(idx, int) and 0 <= idx < len(deliveries) else []
    await state.update_data(adt_one_delete=False, adt_one_signature=signature, adt_pending_export=None)
    await _show_one(callback, state)


@router.callback_query(F.data == templ.ADT_ONE_BACK_CB)
async def callback_adt_one_back(callback: CallbackQuery, state: FSMContext):
    await state.update_data(adt_pending_export=None)
    await _show_one(callback, state)


@router.callback_query(F.data == templ.ADT_ONE_TOGGLE_DELETE_CB)
async def callback_adt_one_toggle_delete(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.update_data(adt_one_delete=not data.get("adt_one_delete", False))
    await _show_one(callback, state)


# ───────────────────────── выгрузка: выполнение ─────────────────────────

def _collect_export(data: dict, scope: str, deliveries: list[dict]) -> tuple[list[int], bool]:
    """Индексы выгружаемых авто-выдач и включено ли удаление выгруженных товаров."""
    if scope == templ.ADT_SCOPE_ONE:
        idx = _resolve_one(data, deliveries)
        return ([idx] if idx is not None else []), bool(data.get("adt_one_delete", False))
    targets, _ = _main_targets(data, deliveries)
    include_multi = data.get("adt_include_multi", True)
    if not include_multi:
        targets = [i for i in targets if not is_multi(deliveries[i])]
    return targets, bool(include_multi and data.get("adt_delete_multi", False))


def _back_cb(scope: str) -> str:
    return templ.ADT_ONE_BACK_CB if scope == templ.ADT_SCOPE_ONE else templ.ADT_FORMAT_MAIN_CB


def _float(scope: str, text: str) -> str:
    return templ.adt_one_float_text(text) if scope == templ.ADT_SCOPE_ONE else templ.adt_export_float_text(text)


@router.callback_query(calls.AutoDeliveryTransferFormat.filter())
async def callback_adt_format(callback: CallbackQuery, callback_data: calls.AutoDeliveryTransferFormat, state: FSMContext):
    if await _deny(callback):
        return
    scope, fmt = callback_data.scope, callback_data.fmt
    if fmt == templ.ADT_FMT_TEXT and scope != templ.ADT_SCOPE_ONE:
        await callback.answer("❌ Текстом можно выгрузить только одну авто-выдачу из её карточки", show_alert=True)
        return

    data = await state.get_data()
    deliveries = load_deliveries()
    targets, delete = _collect_export(data, scope, deliveries)
    if not targets:
        await callback.answer("❗ Нечего выгружать", show_alert=True)
        return
    if fmt == templ.ADT_FMT_TEXT and not plain_text_lines(deliveries[targets[0]]):
        await callback.answer("❗ Нечего выгружать: " + ("в мультивыдаче нет товаров" if is_multi(deliveries[targets[0]]) else "сообщение пустое"), show_alert=True)
        return

    multis = [deliveries[i] for i in targets if is_multi(deliveries[i]) and deliveries[i].get("items")]
    if delete and multis:
        await state.update_data(adt_pending_export={"scope": scope, "fmt": fmt})
        await throw_float_message(
            state, callback.message,
            templ.adt_confirm_delete_text(scope, fmt, multis, len(targets)),
            templ.adt_confirm_delete_kb(_back_cb(scope)),
            callback,
        )
        return
    await _perform_export(callback, state, scope, fmt, delete=False)


@router.callback_query(F.data == templ.ADT_CONFIRM_EXPORT_CB)
async def callback_adt_confirm_export(callback: CallbackQuery, state: FSMContext):
    if await _deny(callback):
        return
    data = await state.get_data()
    pending = data.get("adt_pending_export")
    if not pending:
        await callback.answer("Это подтверждение уже неактуально — выберите формат ещё раз", show_alert=True)
        return
    await state.update_data(adt_pending_export=None)
    await _perform_export(callback, state, pending["scope"], pending["fmt"], delete=True)


def _chunk_lines(lines: list[str]) -> list[list[str]] | None:
    """Делит строки на сообщения по лимиту. None — если какая-то строка не помещается в сообщение целиком."""
    chunks, current, size = [], [], 0
    for line in lines:
        line_size = len(escape(line)) + 1
        if line_size > TEXT_CHUNK_BUDGET:
            return None
        if current and size + line_size > TEXT_CHUNK_BUDGET:
            chunks.append(current)
            current, size = [], 0
        current.append(line)
        size += line_size
    if current:
        chunks.append(current)
    return chunks


async def _answer_with_retry(coro_factory):
    try:
        return await coro_factory()
    except TelegramRetryAfter as e:
        await asyncio.sleep(e.retry_after + 1)
        return await coro_factory()


async def _send_text_export(message: Message, delivery: dict) -> str:
    """Отправляет товары / текст сообщениями. Возвращает пояснение, если пришлось отправить файлом."""
    lines = plain_text_lines(delivery)
    chunks = _chunk_lines(lines)
    if chunks is None or len(chunks) > TEXT_MAX_MESSAGES:
        file_name = export_file_name("txt", suffix=(delivery.get("keyphrases") or [""])[0] + "_text")
        await _answer_with_retry(lambda: message.answer_document(
            BufferedInputFile(("\n".join(lines) + "\n").encode("utf-8"), filename=file_name),
            caption=templ.adt_text_chunk_header(delivery, 1, 1, len(lines)) + "\n\n⚠️ Не пересылайте этот файл посторонним.",
            parse_mode="HTML",
        ))
        reason = "в одной строке больше символов, чем помещается в сообщение" if chunks is None else \
            f"нужно было бы сообщений: {len(chunks)}, а лимит — {TEXT_MAX_MESSAGES}"
        return (f"ℹ️ Текст слишком большой для сообщений ({reason}), поэтому он отправлен "
                f"<b>.txt</b> файлом — тоже без ключевых фраз, по одной строке.")

    for number, chunk in enumerate(chunks, start=1):
        text = f"{templ.adt_text_chunk_header(delivery, number, len(chunks), len(lines))}\n<pre>{escape(chr(10).join(chunk))}</pre>"
        await _answer_with_retry(lambda text=text: message.answer(text, parse_mode="HTML"))
        if number < len(chunks):
            await asyncio.sleep(0.4)
    return ""


async def _perform_export(callback: CallbackQuery, state: FSMContext, scope: str, fmt: str, delete: bool):
    data = await state.get_data()
    menu_message = callback.message
    try:
        deliveries = load_deliveries()
        targets, _ = _collect_export(data, scope, deliveries)
        if not targets:
            raise ValueError("❗ Нечего выгружать — список авто-выдач изменился")
        exported = [copy.deepcopy(deliveries[i]) for i in targets]

        file_name, content = None, None
        if fmt == templ.ADT_FMT_TXT:
            content = build_export_txt(exported)
        elif fmt == templ.ADT_FMT_JSON:
            content = build_export_json(exported)
        elif fmt != templ.ADT_FMT_TEXT:
            raise ValueError("❌ Неизвестный формат выгрузки")
        if content is not None:
            suffix = (exported[0].get("keyphrases") or [""])[0] if scope == templ.ADT_SCOPE_ONE else ""
            file_name = export_file_name(fmt, suffix=suffix)

        # Удаляем сразу, до отправки: так Playerok-бот не успеет продать уже выгруженную строку.
        # Если отправить не получится — вернём строки обратно.
        report = None
        if delete:
            snapshot = [
                {"index": i, "signature": delivery_signature(deliveries[i]), "items": list(deliveries[i]["items"])}
                for i in targets if is_multi(deliveries[i]) and deliveries[i].get("items")
            ]
            if snapshot:
                deliveries, report = remove_exported_items(deliveries, snapshot)
                save_deliveries(deliveries)
    except Exception as e:
        await throw_float_message(state, menu_message, _float(scope, escape(str(e))), templ.back_kb(_back_cb(scope)), callback)
        return

    await throw_float_message(
        state, menu_message,
        _float(scope, "⏳ Выгружаю…" + ("\n🗑 Выгруженные товары уже убраны из бота и вернутся, если отправка не удастся." if report else "")),
        None, callback,
    )

    note = ""
    try:
        if fmt == templ.ADT_FMT_TEXT:
            note = await _send_text_export(menu_message, exported[0])
        else:
            await _answer_with_retry(lambda: menu_message.answer_document(
                BufferedInputFile(content.encode("utf-8"), filename=file_name),
                caption=templ.adt_export_caption(file_name, exported),
                parse_mode="HTML",
            ))
    except Exception as e:
        logger.exception("Ошибка при выгрузке авто-выдач: %s", e)
        restored = ""
        if report:
            try:
                save_deliveries(restore_removed_items(load_deliveries(), report))
                restored = "\n\n↩️ Удалённые товары возвращены обратно — ничего не потеряно."
            except Exception as restore_error:
                logger.exception("Не удалось вернуть товары после ошибки выгрузки: %s", restore_error)
                lost = "\n".join(item for r in report for item in r.get("removed", []))
                restored = "\n\n❗ Не удалось вернуть товары в бот. Вот они — добавьте их вручную:\n<pre>" + escape(lost[:3000]) + "</pre>"
        await throw_float_message(
            state, menu_message,
            _float(scope, f"❌ Не удалось отправить выгрузку: <code>{escape(str(e))}</code>{restored}"),
            templ.back_kb(_back_cb(scope)),
        )
        return

    index = _resolve_one(await state.get_data(), load_deliveries()) if scope == templ.ADT_SCOPE_ONE else None
    await throw_float_message(
        state, menu_message,
        templ.adt_export_done_text(scope, fmt, exported, report, note),
        templ.adt_export_done_kb(scope, index),
        send=True,
    )
    # Меню переезжает под файл, старое сообщение с «⏳ Выгружаю…» убираем.
    try:
        await menu_message.delete()
    except Exception:
        pass


# ───────────────────────── загрузка ─────────────────────────

@router.callback_query(F.data == templ.ADT_IMPORT_CB)
async def callback_adt_import(callback: CallbackQuery, state: FSMContext):
    if await _deny(callback):
        return
    await state.update_data(adt_import=None)
    await state.set_state(states.AutoDeliveriesStates.waiting_for_transfer_import_file)
    await throw_float_message(state, callback.message, templ.adt_import_prompt_text(), templ.back_kb(templ.ADT_MENU_CB), callback)


async def show_import_step(state: FSMContext, message: Message, callback: CallbackQuery | None = None):
    """Следующее нерешённое пересечение или итог загрузки."""
    data = await state.get_data()
    imp = data.get("adt_import")
    if not imp:
        await throw_float_message(
            state, message,
            templ.adt_import_float_text("❌ Загрузка не найдена — отправьте файл ещё раз"),
            templ.back_kb(templ.ADT_MENU_CB), callback,
        )
        return

    current = load_deliveries()
    conflicts, pos = imp["conflicts"], imp["pos"]
    if pos < len(conflicts):
        conflict = conflicts[pos]
        existing = [current[j] for j in conflict["existing"] if 0 <= j < len(current)]
        await throw_float_message(
            state, message,
            templ.adt_conflict_text(pos + 1, len(conflicts), conflict, imp["entries"][conflict["import_index"]], existing),
            templ.adt_conflict_kb(len(conflicts) - pos),
            callback,
        )
        return

    decisions = {int(k): v for k, v in imp["decisions"].items()}
    try:
        _, stats = apply_import(copy.deepcopy(current), copy.deepcopy(imp["entries"]), decisions)
    except AutoDeliveryImportError as e:
        await throw_float_message(
            state, message,
            templ.adt_import_float_text(f"{e}\n\nНажмите «🔁 Пересмотреть пересечения», чтобы решить заново."),
            templ.adt_import_summary_kb(has_conflicts=True, can_apply=False),
            callback,
        )
        return
    await throw_float_message(
        state, message,
        templ.adt_import_summary_text(imp["file_name"], imp["entries"], stats, find_internal_duplicates(imp["entries"])),
        templ.adt_import_summary_kb(has_conflicts=bool(conflicts), can_apply=stats["added"] + stats["replaced"] > 0),
        callback,
    )


@router.callback_query(calls.AutoDeliveryTransferConflict.filter())
async def callback_adt_conflict(callback: CallbackQuery, callback_data: calls.AutoDeliveryTransferConflict, state: FSMContext):
    data = await state.get_data()
    imp = data.get("adt_import")
    if imp:
        conflicts, pos = imp["conflicts"], imp["pos"]
        action = callback_data.action
        base = DECISION_REPLACE if action.startswith(DECISION_REPLACE) else DECISION_SKIP
        apply_to = conflicts[pos:] if action.endswith("_all") else conflicts[pos:pos + 1]
        for conflict in apply_to:
            imp["decisions"][str(conflict["import_index"])] = base
        imp["pos"] = min(len(conflicts), pos + len(apply_to))
        await state.update_data(adt_import=imp)
    await show_import_step(state, callback.message, callback)


@router.callback_query(F.data == templ.ADT_IMPORT_REVIEW_CB)
async def callback_adt_import_review(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    imp = data.get("adt_import")
    if imp:
        # Пересечения пересчитываем по актуальному списку: он мог измениться.
        imp["conflicts"] = find_conflicts(load_deliveries(), imp["entries"])
        imp["pos"] = 0
        imp["decisions"] = {}
        await state.update_data(adt_import=imp)
    await show_import_step(state, callback.message, callback)


@router.callback_query(F.data == templ.ADT_IMPORT_APPLY_CB)
async def callback_adt_import_apply(callback: CallbackQuery, state: FSMContext):
    if await _deny(callback):
        return
    data = await state.get_data()
    imp = data.get("adt_import")
    if not imp:
        await callback.answer("Эта загрузка уже применена или отменена", show_alert=True)
        return
    try:
        decisions = {int(k): v for k, v in imp["decisions"].items()}
        current = load_deliveries()
        new_list, stats = apply_import(current, copy.deepcopy(imp["entries"]), decisions)
        save_deliveries(new_list)
        _delete_unused_images(current, new_list)
    except AutoDeliveryImportError as e:
        await throw_float_message(
            state, callback.message,
            templ.adt_import_float_text(f"{e}\n\nНажмите «🔁 Пересмотреть пересечения», чтобы решить заново."),
            templ.adt_import_summary_kb(has_conflicts=True, can_apply=False),
            callback,
        )
        return
    except Exception as e:
        logger.exception("Ошибка при загрузке авто-выдач: %s", e)
        await throw_float_message(
            state, callback.message,
            templ.adt_import_float_text(f"❌ Не удалось сохранить авто-выдачи: <code>{escape(str(e))}</code>"),
            templ.back_kb(templ.ADT_MENU_CB), callback,
        )
        return
    await state.update_data(adt_import=None)
    await throw_float_message(
        state, callback.message,
        templ.adt_import_done_text(stats, len(new_list)),
        templ.adt_import_done_kb(),
        callback,
    )


@router.callback_query(F.data == templ.ADT_IMPORT_CANCEL_CB)
async def callback_adt_import_cancel(callback: CallbackQuery, state: FSMContext):
    await state.set_state(None)
    await state.update_data(adt_import=None)
    await _show_menu(callback, state)
