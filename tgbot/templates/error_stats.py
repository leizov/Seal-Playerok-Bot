import html
import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from core.error_stats import get_error_stats_overview, get_error_stats_by_date

from .. import callback_datas as calls


def _safe_int(value) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _fmt_period(value) -> str:
    if value is None:
        return "—"
    try:
        value_f = float(value)
    except Exception:
        return "—"
    if value_f < 60:
        return f"{value_f:.1f} сек"
    if value_f < 3600:
        return f"{value_f / 60:.1f} мин"
    return f"{value_f / 3600:.1f} ч"


def error_stats_text() -> str:
    days = get_error_stats_overview(10)
    if not days:
        return textwrap.dedent(
            """
            🚨 <b>Ошибки Playerok API (последние 10 дней)</b>

            📭 Данных пока нет.
            """
        )

    lines = [
        "🚨 <b>Ошибки Playerok API (последние 10 дней)</b>",
        "",
    ]
    for row in days:
        date = row.get("date", "—")
        total = _safe_int(row.get("total_events", 0))
        uniq = _safe_int(row.get("unique_errors", 0))
        last_time = row.get("last_error_time") or "—"
        lines.append(f"• <b>{date}</b>: {total} ошибок | уникальных: {uniq} | последняя: <code>{last_time}</code>")

    return "\n".join(lines)


def error_stats_kb() -> InlineKeyboardMarkup:
    days = get_error_stats_overview(10)
    rows = []

    for row in days:
        day = str(row.get("date", ""))
        total = _safe_int(row.get("total_events", 0))
        if not day:
            continue
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"📅 {day} ({total})",
                    callback_data=calls.ErrorStatsDay(day=day).pack(),
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.MenuPagination(page=1).pack()),
            InlineKeyboardButton(text="🔄 Обновить", callback_data=calls.ErrorStatsNavigation(to="main").pack()),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def error_stats_day_text(day: str) -> str:
    data = get_error_stats_by_date(day)
    by_kind = data.get("by_kind", {}) if isinstance(data, dict) else {}
    errors = data.get("errors", []) if isinstance(data, dict) else []
    total = _safe_int(data.get("total_events", 0))
    uniq = _safe_int(data.get("unique_errors", 0))
    date = data.get("date", day)

    lines = [
        f"🚨 <b>Ошибки Playerok API за {date}</b>",
        "",
        f"📊 Всего ошибок: <b>{total}</b>",
        f"🧩 Уникальных: <b>{uniq}</b>",
        f"• timeout: {_safe_int(by_kind.get('timeout', 0))}",
        f"• http_429: {_safe_int(by_kind.get('http_429', 0))}",
        f"• http_5xx: {_safe_int(by_kind.get('http_5xx', 0))}",
        f"• graphql_429: {_safe_int(by_kind.get('graphql_429', 0))}",
        f"• graphql_5xx: {_safe_int(by_kind.get('graphql_5xx', 0))}",
        f"• cloudflare: {_safe_int(by_kind.get('cloudflare', 0))}",
        f"• other: {_safe_int(by_kind.get('other', 0))}",
        "",
        "<b>Топ ошибок:</b>",
    ]

    if not errors:
        lines.append("• Нет записей")
    else:
        for row in errors[:10]:
            count = _safe_int(row.get("count", 0))
            kind = str(row.get("kind", "other"))
            code = str(row.get("error_code", "") or "—")
            avg_period = _fmt_period(row.get("avg_interval_sec"))
            first_seen = str(row.get("first_seen", "—"))
            last_seen = str(row.get("last_seen", "—"))
            sample = html.escape(str(row.get("text_sample", "") or ""))
            if len(sample) > 120:
                sample = f"{sample[:117]}..."

            lines.append(
                f"• <b>{kind}</b> | x{count} | code: <code>{code}</code> | период: <code>{avg_period}</code>"
            )
            lines.append(f"  first: <code>{first_seen}</code> | last: <code>{last_seen}</code>")
            if sample:
                lines.append(f"  <code>{sample}</code>")

    return "\n".join(lines)


def error_stats_day_kb(day: str) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="⬅️ К списку дней", callback_data=calls.ErrorStatsNavigation(to="main").pack()),
            InlineKeyboardButton(text="🔄 Обновить", callback_data=calls.ErrorStatsDay(day=day).pack()),
        ],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data=calls.MenuPagination(page=1).pack())],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
