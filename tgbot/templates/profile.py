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

    sales_total = _n(_f(profile, "stats", "deals", "outgoing", "total"))
    sales_active = sales_total - _n(_f(profile, "stats", "deals", "outgoing", "finished"))
    purchases_total = _n(_f(profile, "stats", "deals", "incoming", "total"))
    purchases_active = purchases_total - _n(_f(profile, "stats", "deals", "incoming", "finished"))
    items_total = _n(_f(profile, "stats", "items", "total"))
    items_finished = _n(_f(profile, "stats", "items", "finished"))

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
        f"<b>🛒 Продажи:</b> {sales_total} (активных: {sales_active})",
        f"<b>🛍 Покупки:</b> {purchases_total} (активных: {purchases_active})",
        f"<b>📦 Товары:</b> {items_total} (истёкших: {items_finished})",
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
