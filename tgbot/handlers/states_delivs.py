from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext

from core.auto_deliveries import (
    AUTO_DELIVERY_KIND_MULTI,
    AUTO_DELIVERY_KIND_STATIC,
    normalize_auto_deliveries,
    parse_delivery_items_text,
)
from settings import Settings as sett

from .. import templates as templ
from .. import states
from .. import callback_datas as calls
from ..helpful import throw_float_message


router = Router()


def _parse_keyphrases(text: str) -> list[str]:
    return [phrase.strip() for phrase in (text or "").split(",") if phrase.strip()]


def _decode_txt_bytes(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="ignore")


async def _extract_delivery_items(message: types.Message) -> list[str]:
    if message.text:
        items = parse_delivery_items_text(message.text)
    elif message.document:
        filename = (message.document.file_name or "").lower()
        if not filename.endswith(".txt"):
            raise Exception("❌ Поддерживаются только .txt файлы")

        file = await message.bot.get_file(message.document.file_id)
        downloaded_file = await message.bot.download_file(file.file_path)
        file_content = _decode_txt_bytes(downloaded_file.read())
        items = parse_delivery_items_text(file_content)
    else:
        raise Exception("❌ Отправьте текстом или .txt файлом")

    if not items:
        raise Exception("❌ Не найдено ни одной непустой строки с товаром")
    return items


def _resolve_delivery_index(state_data: dict, auto_deliveries: list[dict]) -> int:
    index = state_data.get("auto_delivery_index")
    if index is None:
        raise Exception("❌ Авто-выдача не была найдена")
    if index < 0 or index >= len(auto_deliveries):
        raise Exception("❌ Авто-выдача не была найдена")
    return index


def _auto_delivery_back_callback(data: dict) -> str:
    index = data.get("auto_delivery_index")
    if isinstance(index, int):
        return calls.AutoDeliveryPage(index=index).pack()
    return calls.AutoDeliveriesPagination(page=data.get("last_page", 0)).pack()


@router.message(states.AutoDeliveriesStates.waiting_for_page, F.text)
async def handler_waiting_for_auto_deliveries_page(message: types.Message, state: FSMContext):
    try:
        await state.set_state(None)
        if not message.text.strip().isdigit():
            raise Exception("❌ Вы должны ввести числовое значение")

        await state.update_data(last_page=int(message.text.strip()) - 1)
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_delivs_float_text("📃 Введите номер страницы для перехода ↓"),
            reply_markup=templ.settings_delivs_kb(int(message.text) - 1),
        )
    except Exception as e:
        data = await state.get_data()
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_delivs_float_text(e),
            reply_markup=templ.back_kb(calls.AutoDeliveriesPagination(page=data.get("last_page", 0)).pack()),
        )


@router.message(states.AutoDeliveriesStates.waiting_for_new_auto_delivery_keyphrases, F.text)
async def handler_waiting_for_new_auto_delivery_keyphrases(message: types.Message, state: FSMContext):
    try:
        keyphrases = _parse_keyphrases(message.text)
        if not keyphrases:
            raise Exception("❌ Укажите хотя бы одну ключевую фразу")

        data = await state.get_data()
        new_kind = data.get("new_auto_delivery_kind") or AUTO_DELIVERY_KIND_STATIC
        await state.update_data(new_auto_delivery_keyphrases=keyphrases)

        if new_kind == AUTO_DELIVERY_KIND_MULTI:
            await state.set_state(states.AutoDeliveriesStates.waiting_for_new_auto_delivery_multi_items)
            await throw_float_message(
                state=state,
                message=message,
                text=templ.settings_new_deliv_float_text(
                    "📦 Отправьте товары для мультивыдачи:\n\n"
                    "• текстом (каждая непустая строка = один товар)\n"
                    "или\n"
                    "• <b>.txt</b> файлом (каждая непустая строка = один товар)."
                ),
                reply_markup=templ.back_kb("enter_new_auto_delivery"),
            )
            return

        await state.set_state(states.AutoDeliveriesStates.waiting_for_new_auto_delivery_message)
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_new_deliv_float_text(
                "💬 Введите <b>сообщение авто-выдачи</b>, которое будет отправляться после покупки ↓"
            ),
            reply_markup=templ.back_kb("enter_new_auto_delivery"),
        )
    except Exception as e:
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_new_deliv_float_text(e),
            reply_markup=templ.back_kb("enter_new_auto_delivery"),
        )


@router.message(states.AutoDeliveriesStates.waiting_for_new_auto_delivery_message, F.text)
async def handler_waiting_for_new_auto_delivery_message(message: types.Message, state: FSMContext):
    try:
        new_message = message.text.strip()
        if not new_message:
            raise Exception("❌ Слишком короткое значение")

        data = await state.get_data()
        await state.update_data(new_auto_delivery_message=new_message)

        keyphrases = "</code>, <code>".join(data.get("new_auto_delivery_keyphrases", []))
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_new_deliv_float_text(
                f"➕ Подтвердите <b>добавление авто-выдачи</b> с ключевыми фразами <code>{keyphrases}</code>"
            ),
            reply_markup=templ.confirm_kb(
                confirm_cb="add_new_auto_delivery",
                cancel_cb="enter_new_auto_delivery",
            ),
        )
    except Exception as e:
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_new_deliv_float_text(e),
            reply_markup=templ.back_kb("enter_new_auto_delivery"),
        )


@router.message(states.AutoDeliveriesStates.waiting_for_new_auto_delivery_multi_items)
async def handler_waiting_for_new_auto_delivery_multi_items(message: types.Message, state: FSMContext):
    try:
        new_items = await _extract_delivery_items(message)
        data = await state.get_data()
        await state.update_data(new_auto_delivery_items=new_items)

        keyphrases = "</code>, <code>".join(data.get("new_auto_delivery_keyphrases", []))
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_new_deliv_float_text(
                f"➕ Подтвердите <b>добавление мультивыдачи</b> с ключевыми фразами <code>{keyphrases}</code>\n"
                f"📦 Загружено товаров: <b>{len(new_items)}</b>"
            ),
            reply_markup=templ.confirm_kb(
                confirm_cb="add_new_auto_delivery",
                cancel_cb="enter_new_auto_delivery",
            ),
        )
    except Exception as e:
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_new_deliv_float_text(e),
            reply_markup=templ.back_kb("enter_new_auto_delivery"),
        )


@router.message(states.AutoDeliveriesStates.waiting_for_auto_delivery_keyphrases, F.text)
async def handler_waiting_for_auto_delivery_keyphrases(message: types.Message, state: FSMContext):
    try:
        keyphrases = _parse_keyphrases(message.text)
        if not keyphrases:
            raise Exception("❌ Укажите хотя бы одну ключевую фразу")

        data = await state.get_data()
        auto_deliveries = normalize_auto_deliveries(sett.get("auto_deliveries") or [])
        auto_delivery_index = _resolve_delivery_index(data, auto_deliveries)

        auto_deliveries[auto_delivery_index]["keyphrases"] = keyphrases
        sett.set("auto_deliveries", auto_deliveries)
        await state.set_state(None)

        keyphrases_text = "</code>, <code>".join(keyphrases)
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_deliv_page_float_text(
                f"✅ <b>Ключевые фразы</b> успешно изменены на: <code>{keyphrases_text}</code>"
            ),
            reply_markup=templ.back_kb(calls.AutoDeliveryPage(index=auto_delivery_index).pack()),
        )
    except Exception as e:
        data = await state.get_data()
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_deliv_page_float_text(e),
            reply_markup=templ.back_kb(_auto_delivery_back_callback(data)),
        )


@router.message(states.AutoDeliveriesStates.waiting_for_auto_delivery_message, F.text)
async def handler_waiting_for_auto_delivery_message(message: types.Message, state: FSMContext):
    try:
        new_message = message.text.strip()
        if not new_message:
            raise Exception("❌ Слишком короткий текст")

        data = await state.get_data()
        auto_deliveries = normalize_auto_deliveries(sett.get("auto_deliveries") or [])
        auto_delivery_index = _resolve_delivery_index(data, auto_deliveries)

        if auto_deliveries[auto_delivery_index].get("kind") == AUTO_DELIVERY_KIND_MULTI:
            raise Exception("❌ Для мультивыдачи сообщение не редактируется")

        auto_deliveries[auto_delivery_index]["message"] = new_message.splitlines()
        sett.set("auto_deliveries", auto_deliveries)
        await state.set_state(None)

        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_deliv_page_float_text(
                f"✅ <b>Сообщение авто-выдачи</b> успешно изменено на: <blockquote>{new_message}</blockquote>"
            ),
            reply_markup=templ.back_kb(calls.AutoDeliveryPage(index=auto_delivery_index).pack()),
        )
    except Exception as e:
        data = await state.get_data()
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_deliv_page_float_text(e),
            reply_markup=templ.back_kb(_auto_delivery_back_callback(data)),
        )


@router.message(states.AutoDeliveriesStates.waiting_for_auto_delivery_add_items)
async def handler_waiting_for_auto_delivery_add_items(message: types.Message, state: FSMContext):
    try:
        new_items = await _extract_delivery_items(message)

        data = await state.get_data()
        auto_deliveries = normalize_auto_deliveries(sett.get("auto_deliveries") or [])
        auto_delivery_index = _resolve_delivery_index(data, auto_deliveries)

        auto_delivery = auto_deliveries[auto_delivery_index]
        if auto_delivery.get("kind") != AUTO_DELIVERY_KIND_MULTI:
            raise Exception("❌ Добавление товаров доступно только для мультивыдачи")

        auto_delivery.setdefault("items", [])
        auto_delivery["items"].extend(new_items)
        sett.set("auto_deliveries", auto_deliveries)
        await state.set_state(None)

        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_deliv_page_float_text(
                f"✅ Добавлено <b>{len(new_items)}</b> товаров.\n"
                f"📦 Осталось: <code>{len(auto_delivery.get('items', []))}</code>"
            ),
            reply_markup=templ.back_kb(calls.AutoDeliveryPage(index=auto_delivery_index).pack()),
        )
    except Exception as e:
        data = await state.get_data()
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_deliv_page_float_text(e),
            reply_markup=templ.back_kb(_auto_delivery_back_callback(data)),
        )


@router.message(states.AutoDeliveriesStates.waiting_for_auto_delivery_replace_items)
async def handler_waiting_for_auto_delivery_replace_items(message: types.Message, state: FSMContext):
    try:
        new_items = await _extract_delivery_items(message)

        data = await state.get_data()
        auto_deliveries = normalize_auto_deliveries(sett.get("auto_deliveries") or [])
        auto_delivery_index = _resolve_delivery_index(data, auto_deliveries)

        auto_delivery = auto_deliveries[auto_delivery_index]
        if auto_delivery.get("kind") != AUTO_DELIVERY_KIND_MULTI:
            raise Exception("❌ Обновление товаров доступно только для мультивыдачи")

        auto_delivery["items"] = new_items
        auto_delivery["issued_current_batch"] = 0
        sett.set("auto_deliveries", auto_deliveries)
        await state.set_state(None)

        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_deliv_page_float_text(
                f"✅ Товарная партия полностью обновлена.\n"
                f"📦 Осталось: <code>{len(new_items)}</code>\n"
                f"📊 Выдано в текущей партии: <code>0</code>"
            ),
            reply_markup=templ.back_kb(calls.AutoDeliveryPage(index=auto_delivery_index).pack()),
        )
    except Exception as e:
        data = await state.get_data()
        await throw_float_message(
            state=state,
            message=message,
            text=templ.settings_deliv_page_float_text(e),
            reply_markup=templ.back_kb(_auto_delivery_back_callback(data)),
        )
