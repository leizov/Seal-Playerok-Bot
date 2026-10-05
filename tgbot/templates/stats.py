import textwrap
from datetime import datetime
from html import escape

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from plbot.stats import get_stats, period_days, summarize_days

from .. import callback_datas as calls


def _money(value) -> str:
    try:
        return f"{float(value):.2f}"
    except Exception:
        return "0.00"


def _get_balance_info() -> tuple[str, str]:
    total = "н/д"
    available = "н/д"

    try:
        from plbot.playerokbot import get_playerok_bot

        plbot = get_playerok_bot()
        if not plbot or not plbot.is_connected or not plbot.playerok_account:
            return total, available

        acc = plbot.playerok_account.get()
        profile = getattr(acc, "profile", None)
        balance = getattr(profile, "balance", None)
        if not balance:
            return total, available

        total = _money(getattr(balance, "value", 0))
        available = _money(getattr(balance, "available", 0))
    except Exception:
        pass

    return total, available


_PERIOD_TITLES = {"week": "За 7 дней", "month": "За месяц", "all": "За всё время"}


def _fmt_day(key: str) -> str:
    try:
        return datetime.strptime(key, "%Y-%m-%d").strftime("%d.%m.%Y")
    except Exception:
        return key


def _journal_lines(summary: dict, period: str, stats) -> str:
    lines = []
    best_day = summary.get("best_day")
    top_item = summary.get("top_item")
    label = "Лучший день месяца" if period == "month" else "Лучший день"
    lines.append(
        f"🏆 {label}: "
        + (f"<b>{_fmt_day(best_day['date'])}</b> — <b>{_money(best_day['sum'])}</b>₽" if best_day else "—")
    )
    if top_item:
        lines.append(
            f"🔥 Популярный товар: <b>{escape(str(top_item['name']))}</b> — "
            f"<b>{top_item['count']}</b> шт. на <b>{_money(top_item['sum'])}</b>₽"
        )
    else:
        lines.append("🔥 Популярный товар: —")

    started = getattr(stats, "daily_started_at", None)
    if started:
        try:
            lines.append(f"<i>ℹ️ Подневный учёт ведётся с {started.strftime('%d.%m.%Y')}.</i>")
        except Exception:
            pass
    return "\n".join(lines)


def stats_text(period: str = "all"):
    stats = get_stats()
    if period not in _PERIOD_TITLES:
        period = "all"

    if stats is None:
        return textwrap.dedent(
            """
            📊 <b>Статистика Playerok бота</b>

            ❌ Нет данных о статистике
            """
        )

    launch_time = "Не запущен"
    if stats.bot_launch_time:
        try:
            launch_time = stats.bot_launch_time.strftime("%d.%m.%Y %H:%M:%S")
        except (AttributeError, ValueError):
            launch_time = "Ошибка формата даты"

    month_started = "—"
    try:
        if getattr(stats, "month_started_at", None):
            month_started = stats.month_started_at.strftime("%d.%m.%Y %H:%M:%S")
    except Exception:
        pass

    if period == "week":
        summary = summarize_days(period_days("week"))
        sales_count = summary["sales_count"]
        refund_count = summary["refund_count"]
        reviews_count = summary["reviews_count"]
        sales_sum = summary["sales_sum"]
        refund_sum = summary["refund_sum"]
        raises_sum = summary["raises_sum"]
        keep_sum = summary["keep_in_sale_sum"]
    elif period == "month":
        # Счётчики месяца — из агрегатов (они велись и до дневного журнала).
        summary = summarize_days(period_days("month"))
        sales_count = getattr(stats, "sales_month_count", 0)
        refund_count = getattr(stats, "refund_month_count", 0)
        reviews_count = getattr(stats, "reviews_month_count", 0)
        sales_sum = getattr(stats, "sales_month_sum", 0.0)
        refund_sum = getattr(stats, "refund_month_sum", 0.0)
        raises_sum = getattr(stats, "raises_month_sum", 0.0)
        keep_sum = getattr(stats, "keep_in_sale_month_sum", 0.0)
    else:
        summary = summarize_days(sorted((getattr(stats, "daily", None) or {}).keys()))
        sales_count = getattr(stats, "sales_total_count", 0)
        refund_count = getattr(stats, "refund_total_count", 0)
        reviews_count = getattr(stats, "reviews_total_count", 0)
        sales_sum = getattr(stats, "sales_total_sum", 0.0)
        refund_sum = getattr(stats, "refund_total_sum", 0.0)
        raises_sum = getattr(stats, "raises_total_sum", 0.0)
        keep_sum = getattr(stats, "keep_in_sale_total_sum", 0.0)

    balance_total, balance_available = _get_balance_info()

    txt = textwrap.dedent(
        f"""
        📊 <b>Статистика Playerok бота</b>

        📅 Дата первого запуска: <b>{launch_time}</b>
        🗓️ Начало текущего месяца: <b>{month_started}</b>

        <b>Режим:</b> {_PERIOD_TITLES[period]}

        <b>Баланс:</b>
        ┣ 💰 Всего: <b>{balance_total}</b>₽
        ┗ 💸 Можно вывести: <b>{balance_available}</b>₽

        <b>Продажи:</b>
        ┣ 📦 Всего: <b>{sales_count}</b>
        ┗ 🔄 Возвраты: <b>{refund_count}</b>

        <b>Отзывы:</b>
        ┗ 💬 Получено: <b>{reviews_count}</b>

        <b>Суммы:</b>
        ┣ 💰 Продажи: <b>{_money(sales_sum)}</b>₽
        ┣ ↩️ Возвраты: <b>{_money(refund_sum)}</b>₽
        ┣ 📈 Поднятия/восстановления: <b>{_money(raises_sum)}</b>₽
        ┗ ♾ «Оставлять в продаже» (оценка): <b>{_money(keep_sum)}</b>₽
        """
    ).strip("\n")

    txt += "\n\n" + _journal_lines(summary, period, stats)
    txt += textwrap.dedent(
        """

        ⚠️ Статистика обновляется только во время работы бота.
        ❗ Статистика сохраняется между перезапусками бота.
        ℹ️ Расход «Оставлять в продаже» считается по текущей цене поднятия товара и может быть выше реального.
        """
    )
    return txt


def stats_kb(period: str = "all"):
    def _btn(key: str) -> InlineKeyboardButton:
        mark = "📌" if period == key else "📍"
        return InlineKeyboardButton(
            text=f"{mark} {_PERIOD_TITLES[key]}",
            callback_data=calls.StatsNavigation(to=key).pack(),
        )

    rows = [
        [_btn("week"), _btn("month"), _btn("all")],
        # TODO(stats-charts): кнопка «📈 График» по дневному журналу.
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.MenuPagination(page=1).pack())],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)

