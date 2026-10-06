import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime

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
    txt = textwrap.dedent(f"""
        👤 <b>Профиль <a href="https://playerok.ru/{profile.username}">{profile.username}</a></b>

        <b>🆔 ID:</b> <code>{profile.id}</code>
        <b>📪 Email:</b> {profile.email}
        <b>💬 Отзывы:</b> {profile.reviews_count} (<b>Рейтинг:</b> {profile.rating} ⭐)
        
        <b>💰 Баланс:</b> {profile.balance.value}₽
          ┣ <b>👜 Доступно:</b> {profile.balance.available}₽
          ┗ <b>⌛ Ожидает поступления:</b> {profile.balance.pending_income + profile.balance.frozen}₽
        
        <b>🛒 Продажи:</b> {profile.stats.items.total} (активных: {profile.stats.items.active})
        <b>🛍 Покупки:</b> {profile.stats.items.total} (активных: {profile.stats.items.active})
        <b>📦 Товары:</b> {profile.stats.items.total} (истёкших: {profile.stats.items.finished})
        
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
