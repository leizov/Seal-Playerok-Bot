import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from __init__ import VERSION, DEVELOPER, REPOSITORY
from settings import Settings as sett

from .. import callback_datas as calls


def menu_text():
    config = sett.get("config")
    
    # Статусы
    account_active = "🟢" if config["playerok"]["api"]["token"] else "🔴"
    proxy_active = "🟢" if config["playerok"]["api"].get("proxy") else "⚫"
    
    txt = textwrap.dedent(f"""
        🏠 <b>Главное меню</b>

        🦭 <b>Seal Playerok Bot</b> v{VERSION}
        <b>Милый бот-помощник для Playerok</b>

        <b>Статус:</b>
        ┣ {account_active} Аккаунт
        ┗ {proxy_active} Прокси
        
        <b>Ссылки:</b>
        ┣ <b>{DEVELOPER}</b> — разработчик
        ┗ <a href="{REPOSITORY}">GitHub</a> — репозиторий

        Выберите раздел ниже ↓
    """)
    return txt


def menu_kb(page: int = 0):
    """
    Главное меню с пагинацией
    Страница 0: Основные разделы
    Страница 1: Дополнительные разделы
    """
    if page == 0:
        # Страница 1: Основные разделы
        rows = [
            [InlineKeyboardButton(text="👤 Аккаунт", callback_data=calls.SettingsNavigation(to="account").pack())],
            [InlineKeyboardButton(text="🎛 Глобальные Переключатели", callback_data=calls.SettingsNavigation(to="global_switches").pack())],
            [InlineKeyboardButton(text="♻️ Восстановление", callback_data=calls.SettingsNavigation(to="restore").pack())],
            [InlineKeyboardButton(text="🔔 Настройки Уведомлений", callback_data=calls.SettingsNavigation(to="notifications").pack())],
            [InlineKeyboardButton(text="📋 Заготовки ответов", callback_data=calls.SettingsNavigation(to="quick_replies").pack())],
            [InlineKeyboardButton(text="🔌 Плагины", callback_data=calls.PluginsPagination(page=0).pack())],
            [InlineKeyboardButton(text="🚀 Авто-выдача", callback_data=calls.AutoDeliveriesPagination(page=0).pack())],
            [InlineKeyboardButton(text="🤖 Автоответ", callback_data=calls.MessagesNavigation(to="main").pack())],
            [InlineKeyboardButton(text="⭐ Мониторинг отзывов", callback_data=calls.ReviewMonitorNavigation(to="main").pack())],
        ]
    else:
        # Страница 2: Дополнительные разделы
        rows = [
            [InlineKeyboardButton(text="📊 Статистика", callback_data=calls.StatsNavigation(to="main").pack())],
            [InlineKeyboardButton(text="⌨️ Команды", callback_data=calls.CustomCommandsPagination(page=0).pack())],
            [InlineKeyboardButton(text="👥 Пользователи", callback_data=calls.SettingsNavigation(to="users").pack())],
            [InlineKeyboardButton(text="📋 Логи", callback_data=calls.LogsNavigation(to="main").pack())],
            [InlineKeyboardButton(text="👨‍💻 Настройки разработчика", callback_data=calls.SettingsNavigation(to="developer").pack())],
        ]
    
    # Навигация между страницами
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.MenuPagination(page=page-1).pack()))
    
    nav_row.append(InlineKeyboardButton(text=f"📑 {page + 1}/2", callback_data="page_info"))
    
    if page < 1:
        nav_row.append(InlineKeyboardButton(text="➡️ Далее", callback_data=calls.MenuPagination(page=page+1).pack()))
    
    rows.append(nav_row)
    
    # Ссылки
    rows.append([
        InlineKeyboardButton(text="👨‍💻 Разработчик", url="https://t.me/leizov"),
        InlineKeyboardButton(text="📦 GitHub", url=REPOSITORY)
    ])
    
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb