"""
Utilities for rendering item cards for Telegram.
"""

from __future__ import annotations

from datetime import datetime
import html
import json
from typing import Any
from urllib.parse import quote


STATUS_LABELS = {
    "APPROVED": "Одобрен",
    "PENDING_APPROVAL": "На модерации",
    "PENDING_MODERATION": "На модерации",
    "SOLD": "Продан",
    "BLOCKED": "Заблокирован",
    "DECLINED": "Отклонён",
    "EXPIRED": "Истёк",
    "DRAFT": "Черновик",
}

STATUS_EMOJIS = {
    "APPROVED": "✅",
    "PENDING_APPROVAL": "🔎",
    "PENDING_MODERATION": "🔎",
    "SOLD": "💰",
    "BLOCKED": "⛔",
    "DECLINED": "⛔",
    "EXPIRED": "⌛",
    "DRAFT": "📝",
}

PRIORITY_LABELS = {
    "PREMIUM": "Премиум",
    "DEFAULT": "Стандарт",
}

DASH = "—"


def _enum_name(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "name"):
        return str(getattr(value, "name"))
    return str(value)


def _safe(value: Any) -> str:
    return html.escape(str(value))


def _fmt_value(value: Any) -> str:
    if value is None:
        return DASH
    if isinstance(value, (dict, list)):
        return _safe(json.dumps(value, ensure_ascii=False))
    text = str(value).strip()
    if not text:
        return DASH
    return _safe(text)


def _fmt_price(value: Any) -> str:
    if value is None:
        return DASH
    try:
        return f"{float(value):.2f} ₽"
    except Exception:
        return _safe(value)


def _fmt_date(value: str | None) -> str:
    if not value:
        return DASH
    try:
        iso = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%d.%m.%Y %H:%M:%S")
    except Exception:
        return _safe(value)


def _short_id(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return DASH
    return text[:8]


def _status_text(item) -> str:
    status_name = _enum_name(getattr(item, "status", None))
    label = STATUS_LABELS.get(status_name or "", status_name or "Неизвестно")
    emoji = STATUS_EMOJIS.get(status_name or "", "❔")
    return f"{emoji} {label}"


def _status_description_value(item) -> str | None:
    raw = getattr(item, "status_description", None)
    if raw is None:
        return None

    if isinstance(raw, (int, float)):
        if float(raw) == 0:
            return None
        return _fmt_value(raw)

    text = str(raw).strip()
    if not text:
        return None

    normalized = text.replace(",", ".")
    try:
        if float(normalized) == 0:
            return None
    except Exception:
        pass

    if text.lower() in {"none", "null"}:
        return None

    return _safe(text)


def _status_description_line(item) -> str:
    value = _status_description_value(item)
    if value is None:
        return ""

    status_name = _enum_name(getattr(item, "status", None))
    if status_name == "BLOCKED":
        return (
            f"⛔ <b>Причина "
            f"блокировки:</b> {value}\n"
        )
    return (
        f"💬 <b>Описание "
        f"статуса:</b> {value}\n"
    )


def _item_type(item) -> str:
    return str(type(item).__name__)


def build_item_url(item_slug: Any, item_id: Any) -> str:
    slug_or_id = str(item_slug or item_id or "").strip()
    if not slug_or_id:
        return "https://playerok.com/products/"
    return f"https://playerok.com/products/{quote(slug_or_id)}"


def _is_owner(item, account) -> bool:
    if item is None or account is None:
        return False

    item_user = getattr(item, "user", None)
    item_username = str(getattr(item_user, "username", "") or "").strip().lower()
    item_user_id = str(getattr(item_user, "id", "") or "").strip()
    account_username = str(getattr(account, "username", "") or "").strip().lower()
    account_id = str(getattr(account, "id", "") or "").strip()

    if item_username and account_username and item_username == account_username:
        return True
    if item_user_id and account_id and item_user_id == account_id:
        return True
    return False


def _field_rows(fields: Any) -> str:
    if not fields:
        return "🔹 <code>—</code>"

    rows: list[str] = []
    for field in fields:
        label = _fmt_value(getattr(field, "label", None) or getattr(field, "id", None) or "Поле")
        value = _fmt_value(getattr(field, "value", None))
        if value == DASH:
            continue
        rows.append(f"🔹 <code>{label}: {value}</code>")

    return "\n".join(rows) if rows else "🔹 <code>—</code>"


def _user_block(item, is_owner: bool) -> str:
    user = getattr(item, "user", None)
    if user is None:
        return "<blockquote>—</blockquote>"

    username = _fmt_value(getattr(user, "username", None))
    rating = _fmt_value(getattr(user, "rating", None))
    reviews = _fmt_value(getattr(user, "reviews_count", None))
    is_online = bool(getattr(user, "is_online", False))
    online_icon = "🟢" if is_online else "🔴"
    online_text = "в сети" if is_online else "не в сети"
    owner_suffix = " (ваш аккаунт)" if is_owner else ""

    return (
        "<blockquote>"
        f"👤 <b>Пользователь:</b> {username}{_safe(owner_suffix)}\n"
        f"🌐 <b>Статус в сети:</b> {online_icon} {_safe(online_text)}\n"
        f"⭐ <b>Рейтинг:</b> {rating}\n"
        f"🧾 <b>Отзывы:</b> {reviews}"
        "</blockquote>"
    )


def _common_item_block(item) -> str:
    game_name = _fmt_value(getattr(getattr(item, "game", None), "name", None))
    category_name = _fmt_value(getattr(getattr(item, "category", None), "name", None))
    return (
        "<blockquote>"
        f"📝 <b>Название:</b> {_fmt_value(getattr(item, 'name', None))}\n"
        f"💳 <b>Цена:</b> {_fmt_price(getattr(item, 'price', None))}\n"
        f"🏷 <b>Статус:</b> {_status_text(item)}\n"
        f"{_status_description_line(item)}"
        f"🎮 <b>Игра:</b> {game_name}\n"
        f"🗂 <b>Категория:</b> {category_name}\n"
        f"📄 <b>Описание:</b> {_fmt_value(getattr(item, 'description', None))}"
        "</blockquote>"
    )


def _keep_in_sale_text(item) -> str:
    if not getattr(item, "keep_in_sale_available", None):
        return "недоступно"
    return "✅ включено" if getattr(item, "keep_in_sale", None) else "❌ выключено"


def _my_item_flags_lines(item) -> str:
    lines = [f"♾ <b>Оставлять в продаже:</b> {_keep_in_sale_text(item)}\n"]
    deals_counter = getattr(item, "deals_counter", None)
    lines.append(f"🛒 <b>Продаж:</b> {_fmt_value(deals_counter if deals_counter is not None else 0)}\n")
    if getattr(item, "may_be_published", None) is False:
        lines.append("⛔ <b>Повторная публикация:</b> запрещена Playerok\n")
    if getattr(item, "is_attachments_forbidden", None):
        lines.append("🖼 <b>Картинки:</b> скрыты модерацией\n")
    return "".join(lines)


def _my_item_extra_block(item) -> str:
    priority_name = _enum_name(getattr(item, "priority", None))
    priority_text = PRIORITY_LABELS.get(priority_name or "", priority_name or DASH)
    return (
        "<blockquote>"
        f"{_my_item_flags_lines(item)}"
        f"🚀 <b>Приоритет:</b> {_safe(priority_text)}\n"
        f"👁 <b>Просмотры:</b> {_fmt_value(getattr(item, 'views_counter', None))}\n"
        f"✅ <b>Одобрен:</b> {_fmt_date(getattr(item, 'approval_date', None))}\n"
        f"⏳ <b>Истечение статуса:</b> {_fmt_date(getattr(item, 'status_expiration_date', None))}\n"
        f"📆 <b>Создан:</b> {_fmt_date(getattr(item, 'created_at', None))}\n"
        f"🛠 <b>Обновлён:</b> {_fmt_date(getattr(item, 'updated_at', None))}"
        "</blockquote>"
    )


def _item_extra_block(item) -> str:
    return (
        "<blockquote>"
        f"📍 <b>Позиция:</b> {_fmt_value(getattr(item, 'priority_position', None))}\n"
        f"✅ <b>Одобрен:</b> {_fmt_date(getattr(item, 'approval_date', None))}\n"
        f"📆 <b>Создан:</b> {_fmt_date(getattr(item, 'created_at', None))}\n"
        f"💸 <b>Множитель комиссии:</b> {_fmt_value(getattr(item, 'fee_multiplier', None))}"
        "</blockquote>"
    )


def _item_profile_extra_block(item) -> str:
    priority_name = _enum_name(getattr(item, "priority", None))
    priority_text = PRIORITY_LABELS.get(priority_name or "", priority_name or DASH)
    return (
        "<blockquote>"
        f"🚀 <b>Приоритет:</b> {_safe(priority_text)}\n"
        f"📍 <b>Позиция:</b> {_fmt_value(getattr(item, 'priority_position', None))}\n"
        f"👁 <b>Просмотры:</b> {_fmt_value(getattr(item, 'views_counter', None))}\n"
        f"✅ <b>Одобрен:</b> {_fmt_date(getattr(item, 'approval_date', None))}\n"
        f"📆 <b>Создан:</b> {_fmt_date(getattr(item, 'created_at', None))}\n"
        f"💸 <b>Множитель комиссии:</b> {_fmt_value(getattr(item, 'fee_multiplier', None))}"
        "</blockquote>"
    )


def format_item_card_payload(item, account=None, item_url: str | None = None) -> dict:
    item_id = str(getattr(item, "id", "") or "").strip()
    item_slug = str(getattr(item, "slug", "") or "").strip()
    short_id = _short_id(item_id or item_slug)
    resolved_url = item_url or build_item_url(item_slug, item_id)
    safe_url = html.escape(resolved_url, quote=True)
    type_name = _item_type(item)
    status_name = _enum_name(getattr(item, "status", None))
    is_owner = _is_owner(item, account)

    lines = [
        f"📦 <b>Товар <a href=\"{safe_url}\">#{_safe(short_id)}</a></b>",
        "",
        "<b>👤 Продавец</b>",
        _user_block(item, is_owner=is_owner),
        "",
        "<b>📦 Товар</b>",
        _common_item_block(item),
    ]

    details_block = _item_extra_block(item)
    if type_name == "MyItem":
        details_block = _my_item_extra_block(item)
    elif type_name in {"Item", "ForeignItem"}:
        details_block = _item_extra_block(item)
    elif type_name == "ItemProfile":
        details_block = _item_profile_extra_block(item)

    lines.extend(["", "<b>⚙️ Детали товара</b>", details_block])

    lines.extend(
        [
            "",
            "<b>🗂 Поля товара</b>",
            _field_rows(getattr(item, "data_fields", None)),
        ]
    )

    return {
        "text": "\n".join(lines),
        "item_id": item_id,
        "item_slug": item_slug,
        "short_id": short_id,
        "item_url": resolved_url,
        "is_owner": is_owner,
        "item_status": status_name,
        "type_name": type_name,
        "keep_in_sale": bool(getattr(item, "keep_in_sale", False)),
        "keep_in_sale_available": bool(getattr(item, "keep_in_sale_available", False)),
    }


def format_item_card_text(item) -> str:
    return format_item_card_payload(item=item).get("text", "")
