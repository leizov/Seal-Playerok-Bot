"""
Utilities for rendering deal card text for Telegram.
"""

from __future__ import annotations

from datetime import datetime
import html
import json
from typing import Any


STATUS_LABELS = {
    "PAID": "Оплачена",
    "PENDING": "Ожидает отправки",
    "SENT": "Товар отправлен",
    "CONFIRMED": "Подтверждена покупателем",
    "ROLLED_BACK": "Возврат",
}


def _enum_name(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "name"):
        return str(getattr(value, "name"))
    return str(value)


def _safe(value: Any) -> str:
    return html.escape(str(value))


def _fmt_date(value: str | None) -> str:
    if not value:
        return "—"
    try:
        iso = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%d.%m.%Y %H:%M:%S")
    except Exception:
        return _safe(value)


def _fmt_money(value: Any) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.2f}"
    except Exception:
        return _safe(value)


def _fmt_value(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, (dict, list)):
        return _safe(json.dumps(value, ensure_ascii=False))
    text = str(value).strip()
    if not text:
        return "—"
    return _safe(text)


def _fields_as_code(fields: Any) -> str:
    if not fields:
        return "🔹 <code>—</code>"

    rows: list[str] = []
    for field in fields:
        label = _fmt_value(getattr(field, "label", None) or getattr(field, "id", None) or "Поле")
        value = _fmt_value(getattr(field, "value", None))
        rows.append(f"🔹 <code>{label}: {value}</code>")
    return "\n".join(rows)


def _short_deal_id(deal_id: Any) -> str:
    deal_id_str = str(deal_id or "").strip()
    if not deal_id_str:
        return "—"
    return deal_id_str[:8]


def format_deal_card_text(deal) -> str:
    user = getattr(deal, "user", None)
    item = getattr(deal, "item", None)
    tx = getattr(deal, "transaction", None)
    review = getattr(deal, "review", None)

    deal_id_raw = getattr(deal, "id", None)
    deal_id = _fmt_value(deal_id_raw)
    deal_id_short = _fmt_value(_short_deal_id(deal_id_raw))

    status_name = _enum_name(getattr(deal, "status", None))
    status_text = STATUS_LABELS.get(status_name or "", status_name or "—")

    item_category = getattr(getattr(item, "category", None), "name", None)
    item_game = getattr(getattr(item, "game", None), "name", None)

    buyer_price = getattr(deal, "price", None)
    if buyer_price is None:
        buyer_price = getattr(item, "price", None)
    revenue = getattr(tx, "value", None)

    review_rating = int(getattr(review, "rating", 0) or 0) if review else 0
    review_rating = max(0, min(5, review_rating))
    review_stars = ("⭐" * review_rating) if review_rating else "—"

    base_section = (
        f"🟢 <b>Статус:</b> {status_text}\n"
        f"📅 <b>Дата создания:</b> {_fmt_date(getattr(deal, 'created_at', None))}\n"
        f"👤 <b>Покупатель:</b> {_fmt_value(getattr(user, 'username', None))}"
    )
    item_section = (
        f"📝 <b>Название:</b> {_fmt_value(getattr(item, 'name', None))}\n"
        f"💳 <b>Цена для покупателя:</b> {_fmt_money(buyer_price)} ₽\n"
        f"💰 <b>Наша выручка:</b> {_fmt_money(revenue)} ₽\n"
        f"🎮 <b>Игра:</b> {_fmt_value(item_game)}\n"
        f"🗂 <b>Категория:</b> {_fmt_value(item_category)}"
    )
    review_section = (
        f"🌟 <b>Оценка:</b> {review_stars}\n"
        f"💬 <b>Текст:</b> {_fmt_value(getattr(review, 'text', None) if review else None)}"
    )

    lines = [
        f"🧾 <b>Сделка <a href=\"https://playerok.com/deal/{deal_id}\">#{deal_id_short}</a></b>",
        "",
        "<b>📌 Основное</b>",
        f"<blockquote>{base_section}</blockquote>",
        "",
        "<b>📦 Товар</b>",
        f"<blockquote>{item_section}</blockquote>",
        "",
        "<b>⭐ Отзыв</b>",
        f"<blockquote>{review_section}</blockquote>",
        "",
        "<b>🧩 Поля сделки</b>",
        _fields_as_code(getattr(deal, "obtaining_fields", None)),
        "",
        "<b>🗂 Поля товара</b>",
        _fields_as_code(getattr(item, "data_fields", None)),
    ]

    return "\n".join(lines)
