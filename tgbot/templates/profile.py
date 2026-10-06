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
    profile = acc.profile

    def _n(value) -> int | float:
        return value or 0

    balance = profile.balance
    deals = profile.stats.deals
    items = profile.stats.items
    sales_total = _n(deals.outgoing.total)
    sales_active = sales_total - _n(deals.outgoing.finished)
    purchases_total = _n(deals.incoming.total)
    purchases_active = purchases_total - _n(deals.incoming.finished)
    pending_total = _n(balance.pending_income) + _n(balance.frozen)
    username = html.escape(str(profile.username or ""))
    profile_url = html.escape(PROFILE_URL.format(quote(str(profile.username or ""), safe="")), quote=True)

    txt = textwrap.dedent(f"""
        👤 <b>Профиль <a href="{profile_url}">{username}</a></b>

        <b>🆔 ID:</b> <code>{profile.id}</code>
        <b>📪 Email:</b> {profile.email}
        <b>💬 Отзывы:</b> {profile.reviews_count} (<b>Рейтинг:</b> {profile.rating} ⭐)
        
        <b>💰 Баланс:</b> {_n(balance.value)}₽
          ┣ <b>👜 Доступно:</b> {_n(balance.available)}₽
          ┗ <b>⌛ Ожидает поступления:</b> {pending_total}₽
        
        <b>🛒 Продажи:</b> {sales_total} (активных: {sales_active})
        <b>🛍 Покупки:</b> {purchases_total} (активных: {purchases_active})
        <b>📦 Товары:</b> {_n(items.total)} (истёкших: {_n(items.finished)})
        
        <b>📅 Дата регистрации:</b> {datetime.fromisoformat(profile.created_at.replace('Z', '+00:00')).strftime('%d.%m.%Y %H:%M:%S')}

        Выберите действие ↓
    """)
    return txt


def profile_kb():
    rows = [
        [
            InlineKeyboardButton(text="👛 Кошелёк", callback_data=calls.WithdrawAction(action="open").pack()),
            InlineKeyboardButton(text="⭐ Отзывы", callback_data=calls.ReviewsAction(action="refresh").pack()),
        ],

    ]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb
