import html

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .. import callback_datas as calls


PRESET_LABELS = {
    "PREMIUM": "🚀 Премиум",
    "APPROVED": "✅ Одобренные",
    "MODERATION": "🔎 На модерации",
    "SOLD": "💰 Проданные",
    "BLOCKED_DECLINED": "⛔ Заблок. / Отклон.",
    "DRAFT": "📄 Черновики",
}

FILTER_STATUS_LEGEND = "✅ Одобрен · 🔎 На модерации · 💰 Продан · ⛔ Заблок./Отклон. · 📄 Черновик · ⌛ Истёк"

STATUS_EMOJIS = {
    "APPROVED": "✅",
    "PENDING_APPROVAL": "🔎",
    "PENDING_MODERATION": "🔎",
    "SOLD": "💰",
    "BLOCKED": "⛔",
    "DECLINED": "⛔",
    "EXPIRED": "⌛",
    "DRAFT": "📄",
}


def _safe(value) -> str:
    return html.escape(str(value))


def _short(value: str, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def _fmt_price(value) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.2f} ₽"
    except Exception:
        return _safe(value)


def _status_emoji(status: str | None) -> str:
    status_name = str(status or "").upper()
    return STATUS_EMOJIS.get(status_name, "❔")


def _sort_caption(sort_order: str) -> str:
    return "дороже -> дешевле" if str(sort_order).upper() == "DESC" else "дешевле -> дороже"


def _item_button_text(item: dict) -> str:
    name = _short(item.get("name") or "Без названия", 22)
    price = _fmt_price(item.get("price"))
    emoji = _status_emoji(item.get("status"))
    return f"{name} | {price} | {emoji}"


def _toggle(enabled: bool) -> str:
    return "✅" if enabled else "❌"


def items_menu_text(
    filters: dict,
    page: int,
    total_pages: int,
    total_found: int,
    total_loaded: int,
) -> str:
    presets = [PRESET_LABELS.get(preset, preset) for preset in filters.get("status_presets", [])]
    status_text = ", ".join(presets) if presets else "Все статусы"
    name_query = str(filters.get("name_query") or "").strip()

    lines = [
        "<b>📦 Товары аккаунта</b>",
        "",
        "ℹ️ <i>Отображаются только последние 70 товаров.</i>",
        "",
        f"📊 Найдено: <b>{total_found}</b> из <b>{total_loaded}</b> загруженных",
        f"📄 Страница: <b>{page + 1}/{max(total_pages, 1)}</b>",
        "",
        "<b>🎛 Текущие фильтры</b>",
        f"📌 Статусы: <code>{_safe(status_text)}</code>",
        f"💳 Сортировка: <code>{_safe(_sort_caption(filters.get('sort_order', 'DESC')))}</code>",
    ]

    if name_query:
        lines.append(f"🔤 Поиск: <code>{_safe(name_query)}</code>")

    lines.extend(
        [
            "",
            "<b>🏷 Легенда статусов</b>",
            FILTER_STATUS_LEGEND,
        ]
    )

    if total_found == 0:
        lines.extend(["", "❌ По выбранным фильтрам товары не найдены."])
    else:
        lines.extend(["", "👇 Выберите товар кнопкой ниже."])

    return "\n".join(lines)


def items_menu_kb(filters: dict, page_items: list[dict], page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    for item in page_items:
        rows.append(
            [
                InlineKeyboardButton(
                    text=_item_button_text(item),
                    callback_data=calls.ItemViewFromItems(it_id=str(item.get("id"))).pack(),
                )
            ]
        )

    if total_pages > 1:
        rows.append(
            [
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=calls.ItemsAction(action="page", value=str(max(0, page - 1))).pack(),
                ),
                InlineKeyboardButton(
                    text=f"📄 {page + 1}/{total_pages}",
                    callback_data=calls.ItemsAction(action="noop").pack(),
                ),
                InlineKeyboardButton(
                    text="➡️",
                    callback_data=calls.ItemsAction(
                        action="page",
                        value=str(min(total_pages - 1, page + 1)),
                    ).pack(),
                ),
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="🔎 Фильтр",
                callback_data=calls.ItemsAction(action="open_filter").pack(),
            ),
            InlineKeyboardButton(
                text="🔄 Обновить",
                callback_data=calls.ItemsAction(action="refresh").pack(),
            ),
        ]
    )

    name_query = str(filters.get("name_query") or "").strip()
    if name_query:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🔤 Поиск по названию",
                    callback_data=calls.ItemsAction(action="search_enter").pack(),
                ),
                InlineKeyboardButton(
                    text="🧹 Сбросить поиск",
                    callback_data=calls.ItemsAction(action="search_clear").pack(),
                ),
            ]
        )
    else:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🔤 Поиск по названию",
                    callback_data=calls.ItemsAction(action="search_enter").pack(),
                ),
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def items_filter_text(filters: dict) -> str:
    selected = set(filters.get("status_presets", []))
    lines = ["🔎 <b>Фильтры товаров</b>", "", "Настройте фильтры и нажмите «К списку»."]

    for preset in ("PREMIUM", "APPROVED", "MODERATION", "SOLD", "BLOCKED_DECLINED", "DRAFT"):
        label = PRESET_LABELS.get(preset, preset)
        lines.append(f"{label}: {_toggle(preset in selected)}")

    lines.extend(
        [
            "",
            f"💳 Сортировка по цене: <b>{_safe(_sort_caption(filters.get('sort_order', 'DESC')))}</b>",
            "",
            "Нажмите «🔍 Найти», чтобы применить фильтры.",
        ]
    )
    return "\n".join(lines)


def items_filter_kb(filters: dict) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    selected = set(filters.get("status_presets", []))

    for preset in ("PREMIUM", "APPROVED", "MODERATION", "SOLD", "BLOCKED_DECLINED", "DRAFT"):
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{PRESET_LABELS.get(preset, preset)}: {_toggle(preset in selected)}",
                    callback_data=calls.ItemsAction(action="toggle_preset", value=preset).pack(),
                )
            ]
        )

    sort_order = str(filters.get("sort_order", "DESC")).upper()
    rows.append(
        [
            InlineKeyboardButton(
                text="💳 Сначала дорогие" if sort_order == "DESC" else "💳 Сначала дешёвые",
                callback_data=calls.ItemsAction(action="sort_toggle").pack(),
            )
        ]
    )

    rows.append(
        [
            InlineKeyboardButton(
                text="🔍 Найти",
                callback_data=calls.ItemsAction(action="apply").pack(),
            ),
            InlineKeyboardButton(
                text="♻️ Сброс",
                callback_data=calls.ItemsAction(action="reset").pack(),
            ),
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ К списку",
                callback_data=calls.ItemsAction(action="close_filter").pack(),
            ),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
