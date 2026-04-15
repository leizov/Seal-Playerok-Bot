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
    "APPROVED": "\u041e\u0434\u043e\u0431\u0440\u0435\u043d",
    "PENDING_APPROVAL": "\u041d\u0430 \u043c\u043e\u0434\u0435\u0440\u0430\u0446\u0438\u0438",
    "PENDING_MODERATION": "\u041d\u0430 \u043c\u043e\u0434\u0435\u0440\u0430\u0446\u0438\u0438",
    "SOLD": "\u041f\u0440\u043e\u0434\u0430\u043d",
    "BLOCKED": "\u0417\u0430\u0431\u043b\u043e\u043a\u0438\u0440\u043e\u0432\u0430\u043d",
    "DECLINED": "\u041e\u0442\u043a\u043b\u043e\u043d\u0451\u043d",
    "EXPIRED": "\u0418\u0441\u0442\u0451\u043a",
    "DRAFT": "\u0427\u0435\u0440\u043d\u043e\u0432\u0438\u043a",
}

STATUS_EMOJIS = {
    "APPROVED": "\u2705",
    "PENDING_APPROVAL": "\U0001F50E",
    "PENDING_MODERATION": "\U0001F50E",
    "SOLD": "\U0001F4B0",
    "BLOCKED": "\u26D4",
    "DECLINED": "\u26D4",
    "EXPIRED": "\u231B",
    "DRAFT": "\U0001F4DD",
}

PRIORITY_LABELS = {
    "PREMIUM": "\u041f\u0440\u0435\u043c\u0438\u0443\u043c",
    "DEFAULT": "\u0421\u0442\u0430\u043d\u0434\u0430\u0440\u0442",
}

DASH = "\u2014"


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
        return f"{float(value):.2f} \u20BD"
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
    label = STATUS_LABELS.get(status_name or "", status_name or "\u041d\u0435\u0438\u0437\u0432\u0435\u0441\u0442\u043d\u043e")
    emoji = STATUS_EMOJIS.get(status_name or "", "\u2754")
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
            f"\u26D4 <b>\u041f\u0440\u0438\u0447\u0438\u043d\u0430 "
            f"\u0431\u043b\u043e\u043a\u0438\u0440\u043e\u0432\u043a\u0438:</b> {value}\n"
        )
    return (
        f"\U0001F4AC <b>\u041e\u043f\u0438\u0441\u0430\u043d\u0438\u0435 "
        f"\u0441\u0442\u0430\u0442\u0443\u0441\u0430:</b> {value}\n"
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
        return "\U0001F539 <code>\u2014</code>"

    rows: list[str] = []
    for field in fields:
        label = _fmt_value(getattr(field, "label", None) or getattr(field, "id", None) or "\u041f\u043e\u043b\u0435")
        value = _fmt_value(getattr(field, "value", None))
        if value == DASH:
            continue
        rows.append(f"\U0001F539 <code>{label}: {value}</code>")

    return "\n".join(rows) if rows else "\U0001F539 <code>\u2014</code>"


def _user_block(item, is_owner: bool) -> str:
    user = getattr(item, "user", None)
    if user is None:
        return "<blockquote>\u2014</blockquote>"

    username = _fmt_value(getattr(user, "username", None))
    rating = _fmt_value(getattr(user, "rating", None))
    reviews = _fmt_value(getattr(user, "reviews_count", None))
    is_online = bool(getattr(user, "is_online", False))
    online_icon = "\U0001F7E2" if is_online else "\U0001F534"
    online_text = "\u0432 \u0441\u0435\u0442\u0438" if is_online else "\u043d\u0435 \u0432 \u0441\u0435\u0442\u0438"
    owner_suffix = " (\u0432\u0430\u0448 \u0430\u043a\u043a\u0430\u0443\u043d\u0442)" if is_owner else ""

    return (
        "<blockquote>"
        f"\U0001F464 <b>\u041f\u043e\u043b\u044C\u0437\u043E\u0432\u0430\u0442\u0435\u043B\u044C:</b> {username}{_safe(owner_suffix)}\n"
        f"\U0001F310 <b>\u0421\u0442\u0430\u0442\u0443\u0441 \u0432 \u0441\u0435\u0442\u0438:</b> {online_icon} {_safe(online_text)}\n"
        f"\u2B50 <b>\u0420\u0435\u0439\u0442\u0438\u043D\u0433:</b> {rating}\n"
        f"\U0001F9FE <b>\u041E\u0442\u0437\u044B\u0432\u044B:</b> {reviews}"
        "</blockquote>"
    )


def _common_item_block(item) -> str:
    game_name = _fmt_value(getattr(getattr(item, "game", None), "name", None))
    category_name = _fmt_value(getattr(getattr(item, "category", None), "name", None))
    return (
        "<blockquote>"
        f"\U0001F4DD <b>\u041D\u0430\u0437\u0432\u0430\u043D\u0438\u0435:</b> {_fmt_value(getattr(item, 'name', None))}\n"
        f"\U0001F4B3 <b>\u0426\u0435\u043D\u0430:</b> {_fmt_price(getattr(item, 'price', None))}\n"
        f"\U0001F3F7 <b>\u0421\u0442\u0430\u0442\u0443\u0441:</b> {_status_text(item)}\n"
        f"{_status_description_line(item)}"
        f"\U0001F3AE <b>\u0418\u0433\u0440\u0430:</b> {game_name}\n"
        f"\U0001F5C2 <b>\u041A\u0430\u0442\u0435\u0433\u043E\u0440\u0438\u044F:</b> {category_name}\n"
        f"\U0001F4C4 <b>\u041E\u043F\u0438\u0441\u0430\u043D\u0438\u0435:</b> {_fmt_value(getattr(item, 'description', None))}"
        "</blockquote>"
    )


def _my_item_extra_block(item) -> str:
    priority_name = _enum_name(getattr(item, "priority", None))
    priority_text = PRIORITY_LABELS.get(priority_name or "", priority_name or DASH)
    return (
        "<blockquote>"
        f"\U0001F680 <b>\u041F\u0440\u0438\u043E\u0440\u0438\u0442\u0435\u0442:</b> {_safe(priority_text)}\n"
        f"\U0001F441 <b>\u041F\u0440\u043E\u0441\u043C\u043E\u0442\u0440\u044B:</b> {_fmt_value(getattr(item, 'views_counter', None))}\n"
        f"\u2705 <b>\u041E\u0434\u043E\u0431\u0440\u0435\u043D:</b> {_fmt_date(getattr(item, 'approval_date', None))}\n"
        f"\u23F3 <b>\u0418\u0441\u0442\u0435\u0447\u0435\u043D\u0438\u0435 \u0441\u0442\u0430\u0442\u0443\u0441\u0430:</b> {_fmt_date(getattr(item, 'status_expiration_date', None))}\n"
        f"\U0001F4C6 <b>\u0421\u043E\u0437\u0434\u0430\u043D:</b> {_fmt_date(getattr(item, 'created_at', None))}\n"
        f"\U0001F6E0 <b>\u041E\u0431\u043D\u043E\u0432\u043B\u0451\u043D:</b> {_fmt_date(getattr(item, 'updated_at', None))}"
        "</blockquote>"
    )


def _item_extra_block(item) -> str:
    return (
        "<blockquote>"
        f"\U0001F4CD <b>\u041F\u043E\u0437\u0438\u0446\u0438\u044F:</b> {_fmt_value(getattr(item, 'priority_position', None))}\n"
        f"\u2705 <b>\u041E\u0434\u043E\u0431\u0440\u0435\u043D:</b> {_fmt_date(getattr(item, 'approval_date', None))}\n"
        f"\U0001F4C6 <b>\u0421\u043E\u0437\u0434\u0430\u043D:</b> {_fmt_date(getattr(item, 'created_at', None))}\n"
        f"\U0001F4B8 <b>\u041C\u043D\u043E\u0436\u0438\u0442\u0435\u043B\u044C \u043A\u043E\u043C\u0438\u0441\u0441\u0438\u0438:</b> {_fmt_value(getattr(item, 'fee_multiplier', None))}"
        "</blockquote>"
    )


def _item_profile_extra_block(item) -> str:
    priority_name = _enum_name(getattr(item, "priority", None))
    priority_text = PRIORITY_LABELS.get(priority_name or "", priority_name or DASH)
    return (
        "<blockquote>"
        f"\U0001F680 <b>\u041F\u0440\u0438\u043E\u0440\u0438\u0442\u0435\u0442:</b> {_safe(priority_text)}\n"
        f"\U0001F4CD <b>\u041F\u043E\u0437\u0438\u0446\u0438\u044F:</b> {_fmt_value(getattr(item, 'priority_position', None))}\n"
        f"\U0001F441 <b>\u041F\u0440\u043E\u0441\u043C\u043E\u0442\u0440\u044B:</b> {_fmt_value(getattr(item, 'views_counter', None))}\n"
        f"\u2705 <b>\u041E\u0434\u043E\u0431\u0440\u0435\u043D:</b> {_fmt_date(getattr(item, 'approval_date', None))}\n"
        f"\U0001F4C6 <b>\u0421\u043E\u0437\u0434\u0430\u043D:</b> {_fmt_date(getattr(item, 'created_at', None))}\n"
        f"\U0001F4B8 <b>\u041C\u043D\u043E\u0436\u0438\u0442\u0435\u043B\u044C \u043A\u043E\u043C\u0438\u0441\u0441\u0438\u0438:</b> {_fmt_value(getattr(item, 'fee_multiplier', None))}"
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
        f"\U0001F4E6 <b>\u0422\u043E\u0432\u0430\u0440 <a href=\"{safe_url}\">#{_safe(short_id)}</a></b>",
        "",
        "<b>\U0001F464 \u041F\u0440\u043E\u0434\u0430\u0432\u0435\u0446</b>",
        _user_block(item, is_owner=is_owner),
        "",
        "<b>\U0001F4E6 \u0422\u043E\u0432\u0430\u0440</b>",
        _common_item_block(item),
    ]

    details_block = _item_extra_block(item)
    if type_name == "MyItem":
        details_block = _my_item_extra_block(item)
    elif type_name in {"Item", "ForeignItem"}:
        details_block = _item_extra_block(item)
    elif type_name == "ItemProfile":
        details_block = _item_profile_extra_block(item)

    lines.extend(["", "<b>\u2699\uFE0F \u0414\u0435\u0442\u0430\u043B\u0438 \u0442\u043E\u0432\u0430\u0440\u0430</b>", details_block])

    lines.extend(
        [
            "",
            "<b>\U0001F5C2 \u041F\u043E\u043B\u044F \u0442\u043E\u0432\u0430\u0440\u0430</b>",
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
    }


def format_item_card_text(item) -> str:
    return format_item_card_payload(item=item).get("text", "")
