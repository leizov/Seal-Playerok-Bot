import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from plbot.stats import get_stats

from .. import callback_datas as calls


def stats_text(period: str = "all"):
    stats = get_stats()

    # Handle case when stats is None
    if stats is None:
        return textwrap.dedent("""
            📊 <b>Статистика Playerok бота</b>

            ❌ Нет данных о статистике

            Бот еще не собрал статистику или произошла ошибка при загрузке.
        """)

    # Format launch time safely
    launch_time = 'Не запущен'
    if stats.bot_launch_time:
        try:
            launch_time = stats.bot_launch_time.strftime("%d.%m.%Y %H:%M:%S")
        except (AttributeError, ValueError):
            launch_time = 'Ошибка формата даты'

    month_started = "—"
    try:
        if getattr(stats, "month_started_at", None):
            month_started = stats.month_started_at.strftime("%d.%m.%Y %H:%M:%S")
    except Exception:
        pass

    show_month = period == "month"
    period_title = "За месяц" if show_month else "За всё время"

    sales_count = getattr(stats, "sales_month_count", 0) if show_month else getattr(stats, "sales_total_count", 0)
    refund_count = getattr(stats, "refund_month_count", 0) if show_month else getattr(stats, "refund_total_count", 0)
    sales_sum = getattr(stats, "sales_month_sum", 0.0) if show_month else getattr(stats, "sales_total_sum", 0.0)
    refund_sum = getattr(stats, "refund_month_sum", 0.0) if show_month else getattr(stats, "refund_total_sum", 0.0)
    raises_sum = getattr(stats, "raises_month_sum", 0.0) if show_month else getattr(stats, "raises_total_sum", 0.0)

    txt = textwrap.dedent(f"""
        📊 <b>Статистика Playerok бота</b>

        📅 Дата первого запуска: <b>{launch_time}</b>
        🗓️ Начало текущего месяца: <b>{month_started}</b>

        <b>Режим:</b> {period_title}

        <b>Продажи:</b>
        ┣ 📦 Всего: <b>{sales_count}</b>
        ┗ 🔄 Возвраты: <b>{refund_count}</b>

        <b>Суммы:</b>
        ┣ 💰 Всего: <b>{sales_sum:.2f}</b>₽
        ┗ ↩️ Возвраты: <b>{refund_sum:.2f}</b>₽

        <i>(только произведённые автоматически)</i>
        <b>Поднятия и восстановления:</b>
        ┗ 📈 Сумма: <b>{raises_sum:.2f}</b>₽

        ⚠️ Статистика обновляется только во время работы бота.
        ❗ Статистика сохраняется между перезапусками бота.
    """)
    return txt


def stats_kb(period: str = "all"):
    rows = [
        [
            InlineKeyboardButton(
                text=("📌 За всё время" if period == "all" else "📍 За всё время"),
                callback_data=calls.StatsNavigation(to="all").pack()
            ),
            InlineKeyboardButton(
                text=("📌 За месяц" if period == "month" else "📍 За месяц"),
                callback_data=calls.StatsNavigation(to="month").pack()
            ),
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.MenuPagination(page=1).pack())]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb
