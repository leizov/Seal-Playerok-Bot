"""Тексты и клавиатуры раздела «🔄 Выгрузка / загрузка» авто-выдач."""

import math
from html import escape

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from core.auto_deliveries import AUTO_DELIVERY_KIND_MULTI
from core.auto_delivery_transfer import (
    DECISION_REPLACE,
    DECISION_SKIP,
    TXT_MULTI_MARKER,
    TXT_STATIC_MARKER,
    summarize,
)

from .. import callback_datas as calls
from .settings_delivs import _cut, _delivery_preview, _kind_tag


ADT_MENU_CB = "adt_menu"
ADT_EXPORT_CB = "adt_export"
ADT_EXPORT_ALL_CB = "adt_export_all"
ADT_EXPORT_SOME_CB = "adt_export_some"
ADT_CLEAR_CB = "adt_clear"
ADT_SOME_NEXT_CB = "adt_some_next"
ADT_FORMAT_MAIN_CB = "adt_format_main"
ADT_TOGGLE_MULTI_CB = "adt_toggle_multi"
ADT_TOGGLE_DELETE_CB = "adt_toggle_delete"
ADT_ONE_CB = "adt_one"
ADT_ONE_BACK_CB = "adt_one_back"
ADT_ONE_TOGGLE_DELETE_CB = "adt_one_toggle_delete"
ADT_CONFIRM_EXPORT_CB = "adt_confirm_export"
ADT_IMPORT_CB = "adt_import"
ADT_IMPORT_REVIEW_CB = "adt_import_review"
ADT_IMPORT_APPLY_CB = "adt_import_apply"
ADT_IMPORT_CANCEL_CB = "adt_import_cancel"
ADT_NOOP_CB = "adt_noop"

ADT_SCOPE_MAIN = "main"
ADT_SCOPE_ONE = "one"
ADT_FMT_TXT = "txt"
ADT_FMT_JSON = "json"
ADT_FMT_TEXT = "text"

ADT_PAGE_SIZE = 7
_LIST_LIMIT = 25  # сколько строк перечислять в тексте, дальше — «… и ещё N»

ADT_FORMAT_NAMES = {
    ADT_FMT_TXT: "📄 .txt",
    ADT_FMT_JSON: "🧾 .json",
    ADT_FMT_TEXT: "📝 Текстом",
}

_HEAD = "🚀 <b>Авто-выдача</b>"
_HEAD_EXPORT = f"{_HEAD} → 📤 <b>Выгрузка</b>"
_HEAD_IMPORT = f"{_HEAD} → 📥 <b>Загрузка</b>"
_HEAD_ONE = "✏️ <b>Авто-выдача</b> → 📤 <b>Выгрузка</b>"


# ───────────────────────── общие помощники ─────────────────────────

def _phrases(delivery: dict) -> str:
    phrases = delivery.get("keyphrases", [])
    return "</code>, <code>".join(escape(p) for p in phrases) if phrases else "❌ Не задано"


def _status(delivery: dict) -> str:
    return "🟢 включена" if delivery.get("enabled", True) else "🔴 выключена"


def _kind_name(delivery: dict) -> str:
    return "📦 <code>МУЛЬТИ</code>" if delivery.get("kind") == AUTO_DELIVERY_KIND_MULTI else "🧾 <code>ОБЫЧНАЯ</code>"


def _stats_block(deliveries: list[dict]) -> list[str]:
    s = summarize(deliveries)
    return [
        f"┣ 🧾 Обычных: <b>{s['static']}</b>",
        f"┗ 📦 Мультивыдач: <b>{s['multi']}</b> (товаров: <b>{s['items']}</b>)",
    ]


def _short_line(delivery: dict) -> str:
    """Одна строка для списков: тип, фразы, остаток."""
    phrases = _cut(", ".join(delivery.get("keyphrases", [])) or "Без ключевых фраз", 60)
    if delivery.get("kind") == AUTO_DELIVERY_KIND_MULTI:
        return f"📦 <code>{escape(phrases)}</code> — <b>{len(delivery.get('items', []))}</b> шт."
    return f"🧾 <code>{escape(phrases)}</code>"


def _tree(lines: list[str], limit: int = _LIST_LIMIT) -> list[str]:
    """Оформляет строки ┣/┗ и обрезает длинный список."""
    shown = lines[:limit]
    if len(lines) > limit:
        shown.append(f"… и ещё <b>{len(lines) - limit}</b>")
    return [("┗ " if i == len(shown) - 1 else "┣ ") + line for i, line in enumerate(shown)]


def _delivery_button_text(delivery: dict, prefix: str) -> str:
    status_icon = "🟢" if delivery.get("enabled", True) else "🔴"
    keyphrases = ", ".join(delivery.get("keyphrases", [])) or "Без ключевых фраз"
    return f"{prefix} {_kind_tag(delivery.get('kind'))} {_cut(keyphrases, 24)} → {_cut(_delivery_preview(delivery), 18)}"


def _pagination_row(view: str, page: int, total_pages: int) -> list[InlineKeyboardButton]:
    noop = InlineKeyboardButton(text="🛑", callback_data=ADT_NOOP_CB)
    prev_btn = (
        InlineKeyboardButton(text="←", callback_data=calls.AutoDeliveryTransferNav(view=view, page=page - 1).pack())
        if page > 0 else noop
    )
    next_btn = (
        InlineKeyboardButton(text="→", callback_data=calls.AutoDeliveryTransferNav(view=view, page=page + 1).pack())
        if page < total_pages - 1 else noop
    )
    return [prev_btn, InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data=ADT_NOOP_CB), next_btn]


def adt_clamp_page(page: int, total: int) -> tuple[int, int]:
    total_pages = max(1, math.ceil(total / ADT_PAGE_SIZE))
    return max(0, min(page, total_pages - 1)), total_pages


def adt_float_text(placeholder: str, head: str = _HEAD) -> str:
    return f"{head}\n\n{placeholder}"


def adt_export_float_text(placeholder: str) -> str:
    return adt_float_text(placeholder, _HEAD_EXPORT)


def adt_import_float_text(placeholder: str) -> str:
    return adt_float_text(placeholder, _HEAD_IMPORT)


def adt_one_float_text(placeholder: str) -> str:
    return adt_float_text(placeholder, _HEAD_ONE)


# ───────────────────────── меню «Выгрузка / загрузка» ─────────────────────────

def adt_menu_text(deliveries: list[dict]) -> str:
    lines = [
        _HEAD,
        "",
        f"Правил авто-выдачи в боте: <b>{len(deliveries)}</b>",
        *_stats_block(deliveries),
        "",
        "📤 <b>Выгрузка</b> — сохранить авто-выдачи в файл <b>.txt</b> или <b>.json</b>: "
        "ключевые фразы, товары мультивыдачи и тексты обычных авто-выдач. "
        "Подходит для резервной копии и переноса в другой бот",
        "📥 <b>Загрузка</b> — добавить авто-выдачи из такого файла. "
        "Если ключевые фразы совпадут с уже существующими, бот спросит, что делать с каждой",
    ]
    return "\n".join(lines)


def adt_menu_kb(last_page: int = 0) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Выгрузка", callback_data=ADT_EXPORT_CB)],
        [InlineKeyboardButton(text="📥 Загрузка", callback_data=ADT_IMPORT_CB)],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.AutoDeliveriesPagination(page=last_page).pack())],
    ])


# ───────────────────────── выгрузка: что выгружать ─────────────────────────

def adt_export_text(deliveries: list[dict]) -> str:
    lines = [
        _HEAD_EXPORT,
        "",
        f"Всего авто-выдач: <b>{len(deliveries)}</b>",
        *_stats_block(deliveries),
        "",
        "Что выгрузить?",
        "",
        "📦 <b>Все авто-выдачи</b> — выгрузить всё сразу",
        "☑️ <b>Выбрать некоторые</b> — собрать свой список из существующих авто-выдач",
    ]
    return "\n".join(lines)


def adt_export_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Все авто-выдачи", callback_data=ADT_EXPORT_ALL_CB)],
        [InlineKeyboardButton(text="☑️ Выбрать некоторые", callback_data=ADT_EXPORT_SOME_CB)],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=ADT_MENU_CB)],
    ])


# ───────────────────────── выгрузка: выбор некоторых ─────────────────────────

def adt_select_text(deliveries: list[dict], selected: list[int]) -> str:
    chosen = [deliveries[i] for i in selected]
    lines = [
        f"{_HEAD_EXPORT} → ☑️ <b>Выбор</b>",
        "",
        f"Выбрано авто-выдач: <b>{len(chosen)}</b> из <b>{len(deliveries)}</b>",
        *_stats_block(chosen),
        "",
    ]
    if not chosen:
        lines += [
            "Пока ничего не выбрано — нажмите «➕ Добавить авто-выдачи».",
            "",
            "➕ <b>Добавить авто-выдачи</b> — выбрать из существующих",
            "⬅️ <b>Назад</b> — вернуться к выбору «все / некоторые»",
        ]
        return "\n".join(lines)
    lines += [
        "┣ ❌ <b>Авто-выдача</b> — убрать её из выбора",
    ]
    if len(chosen) > ADT_PAGE_SIZE:
        lines.append("┣ ← / → — листать список выбранных")
    lines += [
        "┣ ➕ <b>Добавить авто-выдачи</b> — выбрать из существующих",
        "┣ 🧹 <b>Очистить выбор</b> — убрать всё",
        "┣ ➡️ <b>Далее</b> — перейти к выбору формата файла",
        "┗ ⬅️ <b>Назад</b> — вернуться к выбору «все / некоторые»",
    ]
    return "\n".join(lines)


def adt_select_kb(deliveries: list[dict], selected: list[int], page: int = 0) -> InlineKeyboardMarkup:
    page, total_pages = adt_clamp_page(page, len(selected))
    rows = []
    for idx in selected[page * ADT_PAGE_SIZE:(page + 1) * ADT_PAGE_SIZE]:
        rows.append([InlineKeyboardButton(
            text=_delivery_button_text(deliveries[idx], "❌"),
            callback_data=calls.AutoDeliveryTransferPick(index=idx, view="sel", page=page).pack(),
        )])
    if total_pages > 1:
        rows.append(_pagination_row("sel", page, total_pages))
    rows.append([InlineKeyboardButton(text="➕ Добавить авто-выдачи", callback_data=calls.AutoDeliveryTransferNav(view="pick", page=0).pack())])
    if selected:
        rows.append([InlineKeyboardButton(text="🧹 Очистить выбор", callback_data=ADT_CLEAR_CB)])
        rows.append([InlineKeyboardButton(text=f"➡️ Далее ({len(selected)})", callback_data=ADT_SOME_NEXT_CB)])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=ADT_EXPORT_CB)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def adt_pick_text(deliveries: list[dict], selected: list[int]) -> str:
    lines = [
        f"{_HEAD_EXPORT} → ☑️ <b>Выбор</b> → ➕ <b>Добавление</b>",
        "",
        f"Выбрано авто-выдач: <b>{len(selected)}</b> из <b>{len(deliveries)}</b>",
        "",
        "Нажмите на авто-выдачу, чтобы добавить её в выгрузку. "
        "Уже выбранные отмечены ✅ — повторное нажатие уберёт её из выбора.",
        "",
        "⬜ / ✅ <b>Авто-выдача</b> — добавить / убрать",
    ]
    if len(deliveries) > ADT_PAGE_SIZE:
        lines.append("← / → — листать страницы")
    lines += [
        "✅ <b>Готово</b> — вернуться к списку выбранных",
    ]
    return "\n".join(lines)


def adt_pick_kb(deliveries: list[dict], selected: list[int], page: int = 0) -> InlineKeyboardMarkup:
    page, total_pages = adt_clamp_page(page, len(deliveries))
    chosen = set(selected)
    rows = []
    for idx in range(page * ADT_PAGE_SIZE, min((page + 1) * ADT_PAGE_SIZE, len(deliveries))):
        rows.append([InlineKeyboardButton(
            text=_delivery_button_text(deliveries[idx], "✅" if idx in chosen else "⬜"),
            callback_data=calls.AutoDeliveryTransferPick(index=idx, view="pick", page=page).pack(),
        )])
    if total_pages > 1:
        rows.append(_pagination_row("pick", page, total_pages))
    rows.append([InlineKeyboardButton(text=f"✅ Готово ({len(selected)})", callback_data=calls.AutoDeliveryTransferNav(view="sel", page=0).pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ───────────────────────── выгрузка: формат (главное меню) ─────────────────────────

def adt_format_text(chosen: list[dict], mode_all: bool, include_multi: bool, delete_multi: bool) -> str:
    multi = [d for d in chosen if d.get("kind") == AUTO_DELIVERY_KIND_MULTI]
    static = [d for d in chosen if d.get("kind") != AUTO_DELIVERY_KIND_MULTI]
    exported = chosen if include_multi else static
    multi_items = sum(len(d.get("items", [])) for d in multi)

    lines = [
        f"{_HEAD_EXPORT} → 📄 <b>Формат</b>",
        "",
        f"<b>Что выгружаем:</b> {'📦 все авто-выдачи' if mode_all else '☑️ выбранные авто-выдачи'}",
        f"Авто-выдач в файле: <b>{len(exported)}</b>",
        *_stats_block(exported),
        "",
    ]

    if multi:
        if include_multi:
            lines.append(
                f"⚠️ Среди выбранных есть мультивыдачи: <b>{len(multi)}</b> шт. (товаров: <b>{multi_items}</b>) — "
                "они будут выгружены <b>вместе с товарами</b>."
            )
            if delete_multi:
                lines.append(
                    "🗑 После выгрузки эти товары будут <b>удалены из бота</b>, чтобы их не продали дважды. "
                    "Сами мультивыдачи и их настройки останутся. Перед удалением бот попросит подтверждение."
                )
        else:
            lines.append(
                f"⚠️ Среди выбранных есть мультивыдачи: <b>{len(multi)}</b> шт. (товаров: <b>{multi_items}</b>) — "
                "они <b>не попадут</b> в файл, потому что включён режим «🚫 без мультивыдачи»."
            )
        lines.append("")
    else:
        lines += ["ℹ️ Мультивыдач среди выбранных нет.", ""]

    if not exported:
        lines += ["❗ <b>Нечего выгружать</b> — все выбранные авто-выдачи являются мультивыдачами. "
                  "Включите «📦 Мультивыдача: выгружать» или выберите другие.", ""]

    lines += [
        "┣ 📄 <b>.txt</b> — читаемый файл: можно открыть в блокноте, поправить и загрузить обратно",
        "┣ 🧾 <b>.json</b> — файл для переноса в другой бот «как есть»",
    ]
    if multi:
        lines.append("┣ 📦 <b>Мультивыдача</b> — выгружать мультивыдачи вместе с товарами или пропустить их")
        if include_multi:
            lines.append("┣ 🗑 <b>Удалить выгруженные товары</b> — после отправки файла убрать выгруженные товары из мультивыдач")
    lines.append("┗ ⬅️ <b>Назад</b> — вернуться к выбору авто-выдач")
    lines += ["", "Файл в любом случае содержит ключевые фразы, формат и товары мультивыдачи и тексты обычных авто-выдач."]
    return "\n".join(lines)


def adt_format_kb(has_multi: bool, include_multi: bool, delete_multi: bool, back_cb: str) -> InlineKeyboardMarkup:
    rows = [[
        InlineKeyboardButton(text="📄 Скачать .txt", callback_data=calls.AutoDeliveryTransferFormat(scope=ADT_SCOPE_MAIN, fmt=ADT_FMT_TXT).pack()),
        InlineKeyboardButton(text="🧾 Скачать .json", callback_data=calls.AutoDeliveryTransferFormat(scope=ADT_SCOPE_MAIN, fmt=ADT_FMT_JSON).pack()),
    ]]
    if has_multi:
        rows.append([InlineKeyboardButton(
            text="📦 Мультивыдача: ✅ выгружать" if include_multi else "📦 Мультивыдача: 🚫 не выгружать",
            callback_data=ADT_TOGGLE_MULTI_CB,
        )])
        if include_multi:
            rows.append([InlineKeyboardButton(
                text="🗑 Удалить выгруженные товары: ✅ да" if delete_multi else "🗑 Удалить выгруженные товары: ❌ нет",
                callback_data=ADT_TOGGLE_DELETE_CB,
            )])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ───────────────────────── выгрузка из карточки авто-выдачи ─────────────────────────

def adt_one_text(delivery: dict, delete_items: bool) -> str:
    is_multi = delivery.get("kind") == AUTO_DELIVERY_KIND_MULTI
    lines = [
        _HEAD_ONE,
        "",
        f"<b>Тип:</b> {_kind_name(delivery)}",
        f"<b>Статус:</b> {_status(delivery)}",
        f"🔑 <b>Ключевые фразы:</b> <code>{_phrases(delivery)}</code>",
    ]
    if is_multi:
        items = delivery.get("items", [])
        lines.append(f"📦 <b>Товаров:</b> <code>{len(items)}</code>")
        if delete_items and items:
            lines += ["", f"🗑 После выгрузки все товары (<b>{len(items)}</b> шт.) будут <b>удалены</b> из этой мультивыдачи. "
                          "Перед удалением бот попросит подтверждение."]
    lines += [
        "",
        "📄 <b>.txt</b> — читаемый файл с ключевыми фразами"
        + (", форматом выдачи и товарами" if is_multi else " и текстом сообщения")
        + "; его можно загрузить обратно через «🔄 Выгрузка / загрузка»",
        "🧾 <b>.json</b> — то же самое в формате для переноса в другой бот",
        "",
    ]
    if is_multi:
        lines.append("┣ 📝 <b>Текстом</b> — только товары, по одному в строке, сообщением в чат (без ключевых фраз). "
                     "Их можно сразу вставить в «➕ Добавить товары»")
        lines.append("┣ 🗑 <b>Удалить выгруженные товары</b> — после выгрузки убрать их из мультивыдачи (сама она останется)")
    else:
        lines.append("┣ 📝 <b>Текстом</b> — только текст сообщения, сообщением в чат (без ключевых фраз)")
    lines.append("┗ ⬅️ <b>Назад</b> — вернуться в карточку авто-выдачи")
    return "\n".join(lines)


def adt_one_kb(index: int, delivery: dict, delete_items: bool) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="📄 .txt", callback_data=calls.AutoDeliveryTransferFormat(scope=ADT_SCOPE_ONE, fmt=ADT_FMT_TXT).pack()),
            InlineKeyboardButton(text="🧾 .json", callback_data=calls.AutoDeliveryTransferFormat(scope=ADT_SCOPE_ONE, fmt=ADT_FMT_JSON).pack()),
            InlineKeyboardButton(text="📝 Текстом", callback_data=calls.AutoDeliveryTransferFormat(scope=ADT_SCOPE_ONE, fmt=ADT_FMT_TEXT).pack()),
        ]
    ]
    if delivery.get("kind") == AUTO_DELIVERY_KIND_MULTI:
        rows.append([InlineKeyboardButton(
            text="🗑 Удалить выгруженные товары: ✅ да" if delete_items else "🗑 Удалить выгруженные товары: ❌ нет",
            callback_data=ADT_ONE_TOGGLE_DELETE_CB,
        )])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.AutoDeliveryPage(index=index).pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ───────────────────────── подтверждение выгрузки с удалением ─────────────────────────

def adt_confirm_delete_text(scope: str, fmt: str, multis: list[dict], exported_total: int) -> str:
    items_total = sum(len(d.get("items", [])) for d in multis)
    head = _HEAD_ONE if scope == ADT_SCOPE_ONE else _HEAD_EXPORT
    lines = [
        head,
        "",
        "🗑 <b>Подтвердите выгрузку с удалением</b>",
        "",
        f"<b>Формат:</b> {ADT_FORMAT_NAMES.get(fmt, fmt)}",
        f"<b>Авто-выдач в выгрузке:</b> {exported_total}",
        "",
        f"Будет выгружено и <b>удалено из бота</b> мультивыдач: <b>{len(multis)}</b>, "
        f"товаров всего: <b>{items_total}</b>",
        *_tree([_short_line(d) for d in multis]),
        "",
        "Сначала бот отправит вам "
        + ("сообщения с товарами" if fmt == ADT_FMT_TEXT else "файл")
        + ". Если отправить не получится — удалённые товары вернутся обратно.",
        "Сами мультивыдачи, их ключевые фразы и формат останутся — уменьшится только остаток.",
        "",
        "✅ <b>Выгрузить и удалить</b> — выполнить",
        "❌ <b>Отменить</b> — вернуться назад, ничего не меняя",
    ]
    return "\n".join(lines)


def adt_confirm_delete_kb(cancel_cb: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Выгрузить и удалить", callback_data=ADT_CONFIRM_EXPORT_CB),
        InlineKeyboardButton(text="❌ Отменить", callback_data=cancel_cb),
    ]])


# ───────────────────────── результат выгрузки ─────────────────────────

def adt_export_caption(file_name: str, exported: list[dict]) -> str:
    s = summarize(exported)
    return (
        f"📤 <b>Выгрузка авто-выдач</b>\n"
        f"📄 <code>{escape(file_name)}</code>\n"
        f"Авто-выдач: <b>{s['total']}</b> (🧾 {s['static']} / 📦 {s['multi']}), товаров: <b>{s['items']}</b>\n\n"
        f"⚠️ В файле товары — не пересылайте его посторонним."
    )


def adt_export_done_text(scope: str, fmt: str, exported: list[dict], report: list[dict] | None, note: str = "") -> str:
    s = summarize(exported)
    head = _HEAD_ONE if scope == ADT_SCOPE_ONE else _HEAD_EXPORT
    where = "сообщениями выше ↑" if fmt == ADT_FMT_TEXT and not note else "файл выше ↑"
    lines = [
        head,
        "",
        f"✅ <b>Выгрузка готова</b> — {where}",
        f"<b>Формат:</b> {ADT_FORMAT_NAMES.get(fmt, fmt)}",
    ]
    if fmt != ADT_FMT_TEXT:
        lines += [f"<b>Авто-выдач:</b> {s['total']}", *_stats_block(exported)]
    if note:
        lines += ["", note]
    if report is not None:
        removed_total = sum(len(r.get("removed", [])) for r in report)
        lines += ["", f"🗑 Удалено из бота товаров: <b>{removed_total}</b>"]
        rows = []
        for r in report:
            phrases = escape(_cut(", ".join(r.get("keyphrases", [])) or "—", 60))
            if r.get("missing"):
                rows.append(f"📦 <code>{phrases}</code> — ⚠️ не найдена (успели изменить или удалить)")
            else:
                rows.append(f"📦 <code>{phrases}</code> — удалено <b>{len(r['removed'])}</b>, осталось <b>{r['remaining']}</b>")
        lines += _tree(rows)
    return "\n".join(lines)


def adt_export_done_kb(scope: str, index: int | None = None) -> InlineKeyboardMarkup:
    if scope == ADT_SCOPE_ONE and index is not None:
        rows = [
            [InlineKeyboardButton(text="📤 Выгрузить ещё раз", callback_data=ADT_ONE_BACK_CB)],
            [InlineKeyboardButton(text="⬅️ К авто-выдаче", callback_data=calls.AutoDeliveryPage(index=index).pack())],
        ]
    else:
        rows = [
            [InlineKeyboardButton(text="📤 Выгрузить ещё раз", callback_data=ADT_EXPORT_CB)],
            [InlineKeyboardButton(text="⬅️ К выгрузке / загрузке", callback_data=ADT_MENU_CB)],
        ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ───────────────────────── загрузка ─────────────────────────

def adt_import_prompt_text() -> str:
    lines = [
        _HEAD_IMPORT,
        "",
        "📎 Отправьте файл выгрузки <b>.txt</b> или <b>.json</b> ↓",
        "",
        "Подходят:",
        "┣ 📄 <b>.txt</b> и 🧾 <b>.json</b>, выгруженные кнопкой «📤 Выгрузка»;",
        "┗ 🧾 файл <code>bot_settings/auto_deliveries.json</code> из папки бота.",
        "",
        f"В .txt каждая авто-выдача начинается со строки <code>{TXT_MULTI_MARKER}</code> или <code>{TXT_STATIC_MARKER}</code> — "
        "так файл можно поправить вручную перед загрузкой.",
        "",
        "Ничего не изменится, пока вы не подтвердите загрузку на последнем шаге. "
        "Если ключевые фразы совпадут с уже существующими авто-выдачами, бот покажет каждое совпадение "
        "и предложит <b>заменить</b> или <b>пропустить</b>.",
        "",
        "⬅️ <b>Назад</b> — вернуться без загрузки",
    ]
    return "\n".join(lines)


def _delivery_card(delivery: dict, title: str) -> list[str]:
    lines = [
        title,
        f"┣ <b>Тип:</b> {_kind_name(delivery)} · {_status(delivery)}",
        f"┣ 🔑 <code>{_phrases(delivery)}</code>",
    ]
    if delivery.get("kind") == AUTO_DELIVERY_KIND_MULTI:
        lines.append(f"┗ 📦 Товаров: <b>{len(delivery.get('items', []))}</b>")
    else:
        message = " ".join(delivery.get("message", [])) or "—"
        lines.append(f"┗ 💬 <i>{escape(_cut(message, 120))}</i>")
    return lines


def adt_conflict_text(position: int, total: int, conflict: dict, imported: dict, existing: list[dict]) -> str:
    common = "</code>, <code>".join(escape(p) for p in conflict.get("common", []))
    lines = [
        _HEAD_IMPORT,
        "",
        f"⚠️ <b>Пересечение {position}/{total}</b>",
        f"Общие ключевые фразы: <code>{common}</code>",
        "",
        *_delivery_card(imported, f"📥 <b>Из файла (№{conflict['import_index'] + 1}):</b>"),
        "",
    ]
    shown = existing[:5]
    for i, delivery in enumerate(shown, start=1):
        title = "📌 <b>Уже в боте:</b>" if len(existing) == 1 else f"📌 <b>Уже в боте ({i}/{len(existing)}):</b>"
        lines += _delivery_card(delivery, title) + [""]
    if len(existing) > len(shown):
        lines += [f"… и ещё пересекающихся авто-выдач: <b>{len(existing) - len(shown)}</b>", ""]

    replace_hint = (
        "авто-выдача из файла встанет на место существующей, а существующая"
        + (" (вместе с её товарами)" if any(d.get("kind") == AUTO_DELIVERY_KIND_MULTI for d in existing) else "")
        + " будет удалена"
        if len(existing) == 1 else
        f"авто-выдача из файла встанет на место первой из них, а все пересекающиеся (<b>{len(existing)}</b> шт.) будут удалены"
    )
    lines += [
        f"┣ ♻️ <b>Заменить</b> — {replace_hint}",
        "┣ ⏭ <b>Пропустить</b> — оставить как есть, эту авто-выдачу из файла не загружать",
        "┣ ♻️ <b>Заменить все</b> / ⏭ <b>Пропустить все</b> — то же самое для этого и всех следующих пересечений",
        "┗ ❌ <b>Отмена</b> — ничего не загружать",
        "",
        "Изменения применятся только после подтверждения на последнем шаге.",
    ]
    return "\n".join(lines)


def adt_conflict_kb(remaining: int) -> InlineKeyboardMarkup:
    rows = [[
        InlineKeyboardButton(text="♻️ Заменить", callback_data=calls.AutoDeliveryTransferConflict(action=DECISION_REPLACE).pack()),
        InlineKeyboardButton(text="⏭ Пропустить", callback_data=calls.AutoDeliveryTransferConflict(action=DECISION_SKIP).pack()),
    ]]
    if remaining > 1:
        rows.append([
            InlineKeyboardButton(text=f"♻️ Заменить все ({remaining})", callback_data=calls.AutoDeliveryTransferConflict(action="replace_all").pack()),
            InlineKeyboardButton(text=f"⏭ Пропустить все ({remaining})", callback_data=calls.AutoDeliveryTransferConflict(action="skip_all").pack()),
        ])
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data=ADT_IMPORT_CANCEL_CB)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def adt_import_summary_text(file_name: str, imported: list[dict], stats: dict, duplicates: list[tuple[int, int]]) -> str:
    s = summarize(imported)
    lines = [
        _HEAD_IMPORT,
        "",
        "📋 <b>Проверьте загрузку</b>",
        f"📄 Файл: <code>{escape(file_name or '—')}</code>",
        f"Авто-выдач в файле: <b>{s['total']}</b> (🧾 {s['static']} / 📦 {s['multi']}, товаров: <b>{s['items']}</b>)",
        "",
        "<b>Что произойдёт:</b>",
        f"┣ ➕ Будет добавлено: <b>{stats['added']}</b>",
        f"┣ ♻️ Будет заменено: <b>{stats['replaced']}</b>"
        + (f" (удалится существующих: <b>{stats['removed_existing']}</b>)" if stats["removed_existing"] else ""),
        f"┗ ⏭ Будет пропущено: <b>{stats['skipped']}</b>",
    ]
    if duplicates:
        pairs = ", ".join(f"№{i + 1} и №{j + 1}" for i, j in duplicates[:10])
        more = f" и ещё {len(duplicates) - 10}" if len(duplicates) > 10 else ""
        lines += [
            "",
            f"⚠️ Внутри файла есть авто-выдачи с одинаковыми ключевыми фразами: {pairs}{more}. "
            "Загрузятся обе, но на товар будет срабатывать только та, что выше в списке.",
        ]
    if stats["added"] + stats["replaced"] == 0:
        lines += ["", "❗ Загружать нечего — все авто-выдачи из файла пропущены."]
    lines += [
        "",
        "Счётчики «выдано» у загруженных мультивыдач начнутся с нуля.",
        "",
        "┣ ✅ <b>Загрузить</b> — применить изменения",
    ]
    if stats["replaced"] + stats["skipped"]:
        lines.append("┣ 🔁 <b>Пересмотреть пересечения</b> — заново решить «заменить / пропустить» по каждому")
    lines.append("┗ ❌ <b>Отменить</b> — ничего не загружать")
    return "\n".join(lines)


def adt_import_summary_kb(has_conflicts: bool, can_apply: bool) -> InlineKeyboardMarkup:
    rows = []
    if can_apply:
        rows.append([InlineKeyboardButton(text="✅ Загрузить", callback_data=ADT_IMPORT_APPLY_CB)])
    if has_conflicts:
        rows.append([InlineKeyboardButton(text="🔁 Пересмотреть пересечения", callback_data=ADT_IMPORT_REVIEW_CB)])
    rows.append([InlineKeyboardButton(text="❌ Отменить", callback_data=ADT_IMPORT_CANCEL_CB)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def adt_import_done_text(stats: dict, total_now: int) -> str:
    lines = [
        _HEAD_IMPORT,
        "",
        "✅ <b>Загрузка завершена</b>",
        f"┣ ➕ Добавлено: <b>{stats['added']}</b>",
        f"┣ ♻️ Заменено: <b>{stats['replaced']}</b>"
        + (f" (удалено существующих: <b>{stats['removed_existing']}</b>)" if stats["removed_existing"] else ""),
        f"┗ ⏭ Пропущено: <b>{stats['skipped']}</b>",
        "",
        f"Правил авто-выдачи в боте теперь: <b>{total_now}</b>",
    ]
    return "\n".join(lines)


def adt_import_done_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 К списку авто-выдач", callback_data=calls.AutoDeliveriesPagination(page=0).pack())],
        [InlineKeyboardButton(text="⬅️ К выгрузке / загрузке", callback_data=ADT_MENU_CB)],
    ])


def adt_text_chunk_header(delivery: dict, part: int, parts: int, count: int) -> str:
    what = "Товары" if delivery.get("kind") == AUTO_DELIVERY_KIND_MULTI else "Текст сообщения"
    phrases = escape(_cut(", ".join(delivery.get("keyphrases", [])) or "—", 80))
    suffix = f" · часть {part}/{parts}" if parts > 1 else ""
    amount = f" ({count} шт.)" if delivery.get("kind") == AUTO_DELIVERY_KIND_MULTI else ""
    return f"📝 <b>{what}</b> <code>{phrases}</code>{amount}{suffix}"
