import html
from datetime import datetime

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .. import callback_datas as calls

REVIEWS_SHOW_COUNT = 10
REVIEW_TEXT_LIMIT = 300


def _fmt_date(value) -> str:
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime("%d.%m.%Y %H:%M")
    except Exception:
        return html.escape(str(value))


def _review_line(review) -> str:
    rating = int(getattr(review, "rating", 0) or 0)
    stars = "⭐" * max(0, min(rating, 5)) or "—"
    creator = getattr(review, "creator", None)
    username = html.escape(str(getattr(creator, "username", None) or "?"))
    deal = getattr(review, "deal", None)
    item = getattr(deal, "item", None) if deal else None
    item_name = getattr(item, "name", None)

    text = str(getattr(review, "text", None) or "").strip()
    if len(text) > REVIEW_TEXT_LIMIT:
        text = text[:REVIEW_TEXT_LIMIT].rstrip() + "…"

    lines = [f"{stars} <b>{username}</b> · {_fmt_date(getattr(review, 'created_at', None))}"]
    if item_name:
        lines.append(f"📦 {html.escape(str(item_name))}")
    lines.append(f"<i>{html.escape(text)}</i>" if text else "<i>Без текста</i>")
    return "<blockquote>" + "\n".join(lines) + "</blockquote>"


def reviews_text(reviews: list, total_count: int | None = None) -> str:
    header = "⭐ <b>Последние отзывы</b>"
    if total_count is not None:
        header += f" (всего: {total_count})"
    if not reviews:
        return header + "\n\nОтзывов пока нет."
    return header + "\n\n" + "\n".join(_review_line(review) for review in reviews)


def reviews_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Обновить",
                    callback_data=calls.ReviewsAction(action="refresh").pack(),
                )
            ]
        ]
    )
