import html
import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime
from urllib.parse import quote

from plbot.placeholders import PROFILE_URL

from .. import callback_datas as calls


def profile_text():
    from plbot.playerokbot import get_playerok_bot
    
    plbot = get_playerok_bot()
    
    # Проверяем, подключен ли аккаунт
    if not plbot or not plbot.is_connected or not plbot.playerok_account:
        return textwrap.dedent("""
            ❌ <b>Не удалось подключиться к аккаунту</b>
            
            Playerok аккаунт недоступен. Проверьте настройки:
            
            ⚙️ <b>Настройки</b> → <b>🔑 Аккаунт</b>
            
            Убедитесь что указаны корректные:
            • Токен
            • User Agent
            • Прокси (если используется)
            
            После изменения настроек используйте /restart
        """)
    
    acc = plbot.playerok_account.get()
    profile = getattr(acc, "profile", None)

    def _n(value) -> int | float:
        return value or 0

    def _f(obj, *path):
        """Безопасно достаёт вложенное поле: Playerok иногда отдаёт блоки профиля как null."""
        for name in path:
            obj = getattr(obj, name, None)
            if obj is None:
                return None
        return obj

    balance = _f(profile, "balance")
    if balance is None:
        # В ответе `user` баланса может не быть (например, сразу после входа) —
        # берём его отдельным лёгким запросом.
        try:
            balance = acc.get_balance()
        except Exception:
            balance = None

    def _counter(*path) -> tuple:
        """(всего, завершено) или (None, None), если Playerok не прислал этот блок.
        Отсутствие данных нельзя показывать как 0 — это выглядит как «нет продаж»."""
        block = _f(profile, "stats", *path)
        total = _f(block, "total")
        if total is None:
            return None, None
        return total, _n(_f(block, "finished"))

    def _stat_line(title: str, total, finished, finished_label: str, active: bool) -> str:
        if total is None:
            return f"{title} — <i>(Playerok не прислал статистику)</i>"
        extra = f"активных: {max(total - finished, 0)}" if active else f"{finished_label}: {finished}"
        return f"{title} {total} ({extra})"

    sales_total, sales_finished = _counter("deals", "outgoing")
    purchases_total, purchases_finished = _counter("deals", "incoming")
    items_total, items_finished = _counter("items")

    raw_username = _f(profile, "username") or getattr(acc, "username", None) or ""
    username = html.escape(str(raw_username))
    profile_url = html.escape(PROFILE_URL.format(quote(str(raw_username), safe="")), quote=True)
    user_id = html.escape(str(_f(profile, "id") or getattr(acc, "id", None) or "—"))
    email = html.escape(str(_f(profile, "email") or getattr(acc, "email", None) or "—"))
    reviews_count = _n(_f(profile, "reviews_count"))
    rating = _f(profile, "rating")
    rating = rating if rating is not None else "—"

    if balance is not None:
        pending_total = _n(_f(balance, "pending_income")) + _n(_f(balance, "frozen"))
        balance_block = (
            f"<b>💰 Баланс:</b> {_n(_f(balance, 'value'))}₽\n"
            f"  ┣ <b>👜 Доступно:</b> {_n(_f(balance, 'available'))}₽\n"
            f"  ┗ <b>⌛ Ожидает поступления:</b> {pending_total}₽"
        )
    else:
        balance_block = "<b>💰 Баланс:</b> не удалось получить"

    created_raw = _f(profile, "created_at") or getattr(acc, "created_at", None)
    try:
        created = datetime.fromisoformat(str(created_raw).replace("Z", "+00:00")).strftime("%d.%m.%Y %H:%M:%S")
    except Exception:
        created = "—"

    lines = [
        f'👤 <b>Профиль <a href="{profile_url}">{username}</a></b>',
        "",
        f"<b>🆔 ID:</b> <code>{user_id}</code>",
        f"<b>📪 Email:</b> {email}",
        f"<b>💬 Отзывы:</b> {reviews_count} (<b>Рейтинг:</b> {rating} ⭐)",
        "",
        balance_block,
        "",
        _stat_line("<b>🛒 Продажи:</b>", sales_total, sales_finished, "", active=True),
        _stat_line("<b>🛍 Покупки:</b>", purchases_total, purchases_finished, "", active=True),
        _stat_line("<b>📦 Товары:</b>", items_total, items_finished, "завершённых", active=False),
        "",
        f"<b>📅 Дата регистрации:</b> {created}",
        "",
        "Выберите действие ↓",
    ]
    return "\n" + "\n".join(lines) + "\n"


def profile_kb():
    rows = [
        [
            InlineKeyboardButton(text="👛 Кошелёк", callback_data=calls.WithdrawAction(action="open").pack()),
            InlineKeyboardButton(text="⭐ Отзывы", callback_data=calls.ReviewsAction(action="refresh").pack()),
        ],

    ]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb
