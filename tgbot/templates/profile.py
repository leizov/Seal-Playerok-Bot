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
        👤 <b>Мой профиль</b>

        <b>🆔 ID:</b> <code>{profile.id}</code>
        <b>👤 Никнейм:</b> {profile.username}
        <b>📪 Email:</b> {profile.email}
        <b>💬 Отзывы:</b> {profile.reviews_count} (<b>Рейтинг:</b> {profile.rating} ⭐)
        
        <b>💰 Баланс:</b> {profile.balance.value}₽
          ┣ <b>👜 Доступно:</b> {profile.balance.available}₽
          ┣ <b>⌛ В процессе:</b> {profile.balance.pending_income}₽
          ┗ <b>❄️ Заморожено:</b> {profile.balance.frozen}₽
        
        <b>📦 Товары:</b>
          ┣ <b>➖ Истёкших:</b> {profile.stats.items.finished}
          ┗ <b>♾️ Всего:</b> {profile.stats.items.total}
        
        <b>🛍️ Покупки:</b>
          ┣ <b>➕ Активные:</b> {profile.stats.deals.incoming.total - profile.stats.deals.incoming.finished}
          ┣ <b>➖ Завершённые:</b> {profile.stats.deals.incoming.finished}
          ┗ <b>♾️ Всего:</b> {profile.stats.deals.incoming.total}

        <b>🛒 Продажи:</b>
          ┣ <b>➕ Активные:</b> {profile.stats.deals.outgoing.total - profile.stats.deals.outgoing.finished}
          ┣ <b>➖ Завершено:</b> {profile.stats.deals.outgoing.finished}
          ┗ <b>♾️ Всего:</b> {profile.stats.deals.outgoing.total}
        
        <b>📅 Дата регистрации:</b> {datetime.fromisoformat(profile.created_at.replace('Z', '+00:00')).strftime('%d.%m.%Y %H:%M:%S')}

        Выберите действие ↓
    """)
    return txt


def profile_kb():
    rows = []
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb
