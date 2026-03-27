import html

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .. import callback_datas as calls


STATUS_LABELS = {
    "ALL": "Все",
    "PAID": "Оплачена",
    "SENT": "Отправлена",
    "CONFIRMED": "Подтверждена",
    "ROLLED_BACK": "Возврат",
}

SORT_FIELD_LABELS = {
    "TIME": "Время",
    "PRICE": "Цена",
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


def _mark(active: bool, text: str) -> str:
    return f"✅ {text}" if active else text


def _deal_link(deal_id: str | None) -> str:
    if not deal_id:
        return "—"
    safe_id = html.escape(str(deal_id), quote=True)
    return f"<a href=\"https://playerok.com/deal/{safe_id}\">перейти</a>"


def _sort_order_caption(sort_by: str, sort_order: str) -> str:
    if sort_by == "PRICE":
        return "от дорогих к дешёвым" if sort_order == "DESC" else "от дешёвых к дорогим"
    return "от новых к старым" if sort_order == "DESC" else "от старых к новым"


def _sort_toggle_button_text(sort_by: str, sort_order: str) -> str:
    if sort_by == "PRICE":
        return "💳 От дорогих к дешёвым" if sort_order == "DESC" else "💳 От дешёвых к дорогим"
    return "🕒 От новых к старым" if sort_order == "DESC" else "🕒 От старых к новым"


def deals_search_text(
    filters: dict,
    page_deals: list[dict],
    page: int,
    total_pages: int,
    total_found: int,
    total_loaded: int,
) -> str:
    status_text = STATUS_LABELS.get(filters.get("status", "ALL"), filters.get("status", "ALL"))
    problem_text = "Только с проблемой" if filters.get("only_problem") else "Все сделки"
    sort_by = filters.get("sort_by", "TIME")
    sort_order = filters.get("sort_order", "DESC")
    sort_field = SORT_FIELD_LABELS.get(sort_by, sort_by)
    sort_order_text = _sort_order_caption(sort_by, sort_order)

    lines = [
        "<b>🧾 Поиск сделок</b>",
        "",
        "ℹ️ <i>Отображаются только последние 70 сделок.</i>",
        "",
        f"📊 Найдено: <b>{total_found}</b> из <b>{total_loaded}</b> загруженных",
        f"📄 Страница: <b>{page + 1}/{max(total_pages, 1)}</b>",
        "",
        "<b>🎛 Текущие фильтры</b>",
        f"📌 Статус: <code>{_safe(status_text)}</code>",
        f"⚠️ Проблема: <code>{_safe(problem_text)}</code>",
        f"🔀 Сортировка: <code>{_safe(sort_field)}, {_safe(sort_order_text)}</code>",
        "",
        "<b>📋 Сделки на странице</b>",
    ]

    if not page_deals:
        lines.append("❌ По выбранным фильтрам сделки не найдены.")
    else:
        start_index = page * 10
        for index, deal in enumerate(page_deals, start=1):
            buyer = _safe(_short(deal.get("buyer") or "Покупатель", 24))
            item_name = _safe(_short(deal.get("item_name") or "Без названия", 34))
            price = _fmt_price(deal.get("price"))
            deal_link = _deal_link(deal.get("id"))
            has_problem = " ⚠️" if deal.get("has_problem") else ""
            lines.append(
                f"{start_index + index}. 👤 <b>{buyer}</b>{has_problem} | "
                f"💳 {price} | 📦 {item_name} | 🔗 {deal_link}"
            )

    return "\n".join(lines)


def deals_search_kb(filters: dict, page_deals: list[dict], page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    for deal in page_deals:
        buyer = (deal.get("buyer") or "Покупатель").strip() or "Покупатель"
        buyer = _short(buyer, 32)
        rows.append(
            [
                InlineKeyboardButton(
                    text=buyer,
                    callback_data=calls.DealView(de_id=str(deal.get("id"))).pack(),
                )
            ]
        )

    if total_pages > 1:
        rows.append(
            [
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=calls.DealsAction(action="page", value=str(max(0, page - 1))).pack(),
                ),
                InlineKeyboardButton(
                    text=f"📄 {page + 1}/{total_pages}",
                    callback_data=calls.DealsAction(action="noop").pack(),
                ),
                InlineKeyboardButton(
                    text="➡️",
                    callback_data=calls.DealsAction(
                        action="page",
                        value=str(min(total_pages - 1, page + 1)),
                    ).pack(),
                ),
            ]
        )

    status = filters.get("status", "ALL")
    rows.append(
        [
            InlineKeyboardButton(
                text=_mark(status == "ALL", "Все"),
                callback_data=calls.DealsAction(action="status", value="ALL").pack(),
            ),
            InlineKeyboardButton(
                text=_mark(status == "PAID", "Оплачена"),
                callback_data=calls.DealsAction(action="status", value="PAID").pack(),
            ),
            InlineKeyboardButton(
                text=_mark(status == "SENT", "Отправлена"),
                callback_data=calls.DealsAction(action="status", value="SENT").pack(),
            ),
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text=_mark(status == "CONFIRMED", "Подтверждена"),
                callback_data=calls.DealsAction(action="status", value="CONFIRMED").pack(),
            ),
            InlineKeyboardButton(
                text=_mark(status == "ROLLED_BACK", "Возврат"),
                callback_data=calls.DealsAction(action="status", value="ROLLED_BACK").pack(),
            ),
        ]
    )

    rows.append(
        [
            InlineKeyboardButton(
                text=_mark(bool(filters.get("only_problem")), "⚠️ Только с проблемой"),
                callback_data=calls.DealsAction(action="problem").pack(),
            )
        ]
    )

    sort_by = filters.get("sort_by", "TIME")
    sort_order = filters.get("sort_order", "DESC")
    rows.append(
        [
            InlineKeyboardButton(
                text=_mark(sort_by == "TIME", "🕒 Время"),
                callback_data=calls.DealsAction(action="sort_by", value="TIME").pack(),
            ),
            InlineKeyboardButton(
                text=_mark(sort_by == "PRICE", "💳 Цена"),
                callback_data=calls.DealsAction(action="sort_by", value="PRICE").pack(),
            ),
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text=_sort_toggle_button_text(sort_by, sort_order),
                callback_data=calls.DealsAction(action="sort_toggle").pack(),
            ),
        ]
    )

    rows.append(
        [
            InlineKeyboardButton(
                text="♻️ Сброс",
                callback_data=calls.DealsAction(action="reset").pack(),
            ),
            InlineKeyboardButton(
                text="🔄 Обновить",
                callback_data=calls.DealsAction(action="refresh").pack(),
            ),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)
