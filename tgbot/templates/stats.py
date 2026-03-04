import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from plbot.stats import get_stats

from .. import callback_datas as calls


def stats_text():
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
    
    txt = textwrap.dedent(f"""
        📊 <b>Статистика Playerok бота</b>

        📅 Дата первого запуска: <b>{launch_time}</b>

        <b>Статистика за весь период:</b>
        ┣ ✅ Выполнено: <b>{getattr(stats, 'deals_completed', 0)}</b>
        ┣ 🔄 Сумма возвратов: <b>{getattr(stats, 'refunded_money', 0):.2f}</b>₽
        ┗ 💰 Сумма подтверждённых заказов: <b>{getattr(stats, 'earned_money', 0):.2f}</b>₽
        
        ⚠️ Статистика обновляется только во время работы бота
        ❗ Статистика сохраняется между перезапусками бота.
    """)
    return txt


def stats_kb():
    rows = [
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.MenuPagination(page=1).pack())]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb