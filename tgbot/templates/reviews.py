import html
from datetime import datetime

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .. import callback_datas as calls

MAX_REVIEWS_TO_LOAD = 100
REVIEWS_PAGE_SIZE = 10
REVIEW_TEXT_LIMIT = 3000
# Оставлено для совместимости со старым кодом.
REVIEWS_SHOW_COUNT = REVIEWS_PAGE_SIZE

DEAL_URL = "https://playerok.com/deal/{}"


def _safe(value) -> str:
    return html.escape(str(value))


def _short(value, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _fmt_date(value) -> str:
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime("%d.%m.%Y %H:%M")
    except Exception:
        return _safe(value)


def _fmt_price(value) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.2f} ₽"
    except Exception:
        return _safe(value)


def review_to_dict(review) -> dict:
    """Компактное представление отзыва для кэша FSM (только JSON-совместимые значения)."""
    deal = getattr(review, "deal", None)
    item = getattr(deal, "item", None) if deal else None
    creator = getattr(review, "creator", None)
    return {
        "id": str(getattr(review, "id", "") or ""),
        "rating": getattr(review, "rating", None),
        "text": getattr(review, "text", None),
        "created_at": getattr(review, "created_at", None),
        "buyer": getattr(creator, "username", None),
        "deal_id": str(getattr(deal, "id", "") or "") or None,
        "item_name": getattr(item, "name", None),
        "item_price": getattr(item, "price", None),
    }


def _rating(review: dict) -> int:
    try:
        return max(0, min(int(review.get("rating") or 0), 5))
    except Exception:
        return 0


def review_button_text(review: dict) -> str:
    item_name = _short(review.get("item_name") or "Без товара", 20)
    buyer = _short(review.get("buyer") or "?", 14)
    return f"{item_name} | {buyer} | {_rating(review)}⭐"


def reviews_list_text(
    page_reviews: list[dict],
    page: int,
    total_pages: int,
    total_loaded: int,
    total_count: int | None = None,
) -> str:
    lines = ["<b>⭐ Отзывы</b>", ""]
    if total_count is not None and total_count > total_loaded:
        lines.extend([f"ℹ️ <i>Отображаются только последние {total_loaded} отзывов.</i>", ""])

    if total_loaded:
        lines.append(f"📊 Загружено: <b>{total_loaded}</b>" + (f" из <b>{total_count}</b>" if total_count is not None else ""))
        lines.append(f"📄 Страница: <b>{page + 1}/{max(total_pages, 1)}</b>")
        lines.extend(["", "👇 Выберите отзыв кнопкой ниже."])
    else:
        lines.append("Отзывов пока нет.")
    return "\n".join(lines)


def reviews_list_kb(page_reviews: list[dict], page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for review in page_reviews:
        rows.append(
            [
                InlineKeyboardButton(
                    text=review_button_text(review),
                    callback_data=calls.ReviewView(rv_id=str(review.get("id"))).pack(),
                )
            ]
        )

    if total_pages > 1:
        rows.append(
            [
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=calls.ReviewsPage(page=max(0, page - 1)).pack(),
                ),
                InlineKeyboardButton(
                    text=f"📄 {page + 1}/{total_pages}",
                    callback_data=calls.ReviewsAction(action="noop").pack(),
                ),
                InlineKeyboardButton(
                    text="➡️",
                    callback_data=calls.ReviewsPage(page=min(total_pages - 1, page + 1)).pack(),
                ),
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(text="🔄 Обновить", callback_data=calls.ReviewsAction(action="refresh").pack()),
            InlineKeyboardButton(text="⬅️ В профиль", callback_data=calls.ProfileNavigation(to="main").pack()),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def review_card_text(review: dict) -> str:
    rating = _rating(review)
    stars = "⭐" * rating if rating else "—"
    text = str(review.get("text") or "").strip()
    if len(text) > REVIEW_TEXT_LIMIT:
        text = text[:REVIEW_TEXT_LIMIT].rstrip() + "…"

    deal_id = review.get("deal_id")
    lines = [
        f"<b>⭐ Отзыв</b> {stars} <b>({rating}/5)</b>",
        "",
        f"👤 <b>Покупатель:</b> {_safe(review.get('buyer') or '—')}",
        f"📅 <b>Дата:</b> {_fmt_date(review.get('created_at'))}",
        "",
        f"📦 <b>Товар:</b> {_safe(review.get('item_name') or '—')}",
        f"💳 <b>Цена:</b> {_fmt_price(review.get('item_price'))}",
    ]
    if deal_id:
        url = _safe(DEAL_URL.format(deal_id))
        lines.append(f'🧾 <b>Сделка:</b> <a href="{url}">#{_safe(str(deal_id)[:8])}</a>')
    lines.extend(["", "💬 <b>Текст отзыва:</b>"])
    lines.append(f"<blockquote>{_safe(text)}</blockquote>" if text else "<i>Без текста</i>")
    return "\n".join(lines)


def review_card_kb(review: dict) -> InlineKeyboardMarkup:
    rv_id = str(review.get("id"))
    buyer = review.get("buyer")
    deal_id = review.get("deal_id")
    rows: list[list[InlineKeyboardButton]] = []

    if buyer:
        rows.append(
            [
                InlineKeyboardButton(
                    text="💬 Написать",
                    callback_data=calls.RememberUsername(name=buyer, do="send_mess").pack(),
                ),
                InlineKeyboardButton(
                    text="📋 Заготовки",
                    callback_data=calls.RememberUsername(name=buyer, do="quick_reply").pack(),
                ),
            ]
        )

    nav_row: list[InlineKeyboardButton] = []
    if deal_id:
        nav_row.append(
            InlineKeyboardButton(text="🧾 Просмотр сделки", callback_data=calls.ReviewDeal(rv_id=rv_id).pack())
        )
    if deal_id or buyer:
        nav_row.append(
            InlineKeyboardButton(text="📜 Просмотр чата", callback_data=calls.ReviewChat(rv_id=rv_id).pack())
        )
    if nav_row:
        rows.append(nav_row)

    back_row = [InlineKeyboardButton(text="⬅️ К отзывам", callback_data=calls.ReviewsAction(action="open").pack())]
    if deal_id:
        back_row.append(InlineKeyboardButton(text="🔗 Открыть сделку", url=DEAL_URL.format(deal_id)))
    rows.append(back_row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


# --- совместимость: старые имена, которые могут использовать плагины ---

def reviews_text(reviews: list, total_count: int | None = None) -> str:
    items = [review_to_dict(r) for r in reviews or []]
    return reviews_list_text(items[:REVIEWS_PAGE_SIZE], 0, 1, len(items), total_count)


def reviews_kb() -> InlineKeyboardMarkup:
    return reviews_list_kb([], 0, 1)
