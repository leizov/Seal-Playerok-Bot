import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

from __init__ import VERSION, DEVELOPER, REPOSITORY
from settings import Settings as sett

from .. import callback_datas as calls

START_SHORTCUT_MAIN_MENU = "🏠 Главное меню"
START_SHORTCUT_DEALS = "💼 Сделки"
START_SHORTCUT_ITEMS = "📦 Товары"
START_SHORTCUT_CHATS = "💬 Чаты"
START_SHORTCUT_PROFILE = "👤 Профиль"


def menu_text():
    txt = textwrap.dedent(f"""
        🏠 <b>Главное меню</b>

        🦭 <b>Seal Playerok Bot</b> v{VERSION}
        <b>Милый бот-помощник для Playerok</b>

        <b>Ссылки:</b>
        ┣ <b>{DEVELOPER}</b> — разработчик
        ┣ Канал: @SealPlayerok
        ┣ Чат: @SealPlayerokChat
        ┗ <a href="{REPOSITORY}">GitHub</a> — репозиторий

        ⭐ <b>Если бот полезен, поставьте звёздочку в репозитории GitHub.</b>

        Выберите раздел ниже ↓
    """)
    return txt


def start_banner_caption_text() -> str:
    txt = textwrap.dedent("""
        🦭 <b>Привет!</b>

        <b>Быстрее тыкай по кнопкам снизу!</b>
    """)
    return txt.strip()


def start_shortcuts_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=START_SHORTCUT_MAIN_MENU),
            ],
            [
                KeyboardButton(text=START_SHORTCUT_DEALS),
                KeyboardButton(text=START_SHORTCUT_ITEMS),
            ],
            [
                KeyboardButton(text=START_SHORTCUT_CHATS),
                KeyboardButton(text=START_SHORTCUT_PROFILE),
            ],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Выберите раздел",
    )


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
            [InlineKeyboardButton(text="📈 Авто-поднятие", callback_data=calls.SettingsNavigation(to="raise").pack())],
            [InlineKeyboardButton(text="✅ Авто-подтверждение", callback_data=calls.SettingsNavigation(to="auto_complete").pack())],
            [InlineKeyboardButton(text="🔔 Настройки Уведомлений", callback_data=calls.SettingsNavigation(to="notifications").pack())],
            [InlineKeyboardButton(text="📋 Заготовки ответов", callback_data=calls.SettingsNavigation(to="quick_replies").pack())],
            [InlineKeyboardButton(text="🔌 Плагины", callback_data=calls.PluginsPagination(page=0).pack())],
            [InlineKeyboardButton(text="🚀 Авто-выдача", callback_data=calls.AutoDeliveriesPagination(page=0).pack())],
            [InlineKeyboardButton(text="🤖 Автоответ", callback_data=calls.MessagesNavigation(to="main").pack())],
        ]
    else:
        # Страница 2: Дополнительные разделы
        rows = [
            [InlineKeyboardButton(text="📊 Статистика", callback_data=calls.StatsNavigation(to="main").pack())],
            [InlineKeyboardButton(text="⌨️ Команды", callback_data=calls.CustomCommandsPagination(page=0).pack())],
            [InlineKeyboardButton(text="⏰ Авто-Напоминание", callback_data=calls.SettingsNavigation(to="auto_reminder").pack())],
            [InlineKeyboardButton(text="👥 Пользователи", callback_data=calls.SettingsNavigation(to="users").pack())],
            [InlineKeyboardButton(text="📋 Логи", callback_data=calls.LogsNavigation(to="main").pack())],
            # [InlineKeyboardButton(text="👨‍💻 Настройки разработчика", callback_data=calls.SettingsNavigation(to="developer").pack())],
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
