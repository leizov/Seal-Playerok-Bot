import textwrap

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from core import raise_packs
from settings import Settings as sett

from .. import callback_datas as calls


RAISE_PACKS_PER_PAGE = 6


def _normalize_raise_mode(raw_mode: str | None) -> str:
    mode = str(raw_mode or "interval").strip().lower()
    if mode not in {"interval", "timing"}:
        return "interval"
    return mode


def _format_timings(timings: list[str], max_items: int = 6) -> str:
    normalized = [str(value).strip() for value in timings if str(value).strip()]
    if not normalized:
        return "не задано"
    if len(normalized) <= max_items:
        return ", ".join(normalized)
    return ", ".join(normalized[:max_items]) + f" (+{len(normalized) - max_items})"


def _raise_source_block(source: str) -> str:
    """Какие типы настройки есть, что каждый делает и какой сейчас активен."""
    lots_mark = "✅" if source == raise_packs.SOURCE_LOTS else "▫️"
    packs_mark = "✅" if source == raise_packs.SOURCE_PACKS else "▫️"
    active_name = "📦 Все лоты" if source == raise_packs.SOURCE_LOTS else "🗂 Паки"
    return (
        f"🔀 <b>Тип настройки:</b> {active_name}\n\n"
        f"{lots_mark} <b>📦 Все лоты</b> — одно общее расписание для всех лотов "
        f"(или только для указанных во «Включенных»)\n"
        f"{packs_mark} <b>🗂 Паки</b> — группы лотов по ключевым фразам, "
        f"у каждой группы своё расписание: интервал или тайминг\n"
        f"<i>Переключить — кнопка «🔀 Тип настройки». Настройки другого типа сохраняются.</i>"
    )


def _raise_disabled_line(auto_raise_config: dict) -> str:
    if auto_raise_config.get("enabled"):
        return ""
    return "\n⚠️ <b>Автоподнятие сейчас выключено</b> — включите его в «🎛 Глобальные Переключатели»\n"


def _pack_icon(pack: dict) -> str:
    if not pack["enabled"]:
        return "💔"
    if not pack["keyphrases"]:
        return "⚠️"
    return "💚"


def _settings_raise_packs_text(auto_raise_config: dict) -> str:
    packs = raise_packs.load_packs()
    working = sum(1 for pack in packs if raise_packs.is_working(pack))
    excluded = len((sett.get("auto_raise_items") or {}).get("excluded", []))
    txt = (
        "⚙️ <b>Настройки → 📈 Автоподнятие</b>\n"
        f"{_raise_disabled_line(auto_raise_config)}\n"
        f"{_raise_source_block(raise_packs.SOURCE_PACKS)}\n\n"
        f"🗂 <b>Паков:</b> {len(packs)} (работают: {working})\n"
        f"➖ <b>Исключенные:</b> {excluded} — не поднимаются ни одним паком\n\n"
        "<b>Как работают паки?</b>\n"
        "• Лот попадает в пак, если в его названии есть хотя бы одна ключевая фраза пака\n"
        "• Если лот подходит под несколько паков — его поднимает первый включённый пак по списку\n"
        "• Поднимаются только активные лоты с премиум-статусом\n"
        "• Интервал — лот поднимается, когда с его последнего поднятия прошло заданное число часов\n"
        "• Тайминг — лоты пака поднимаются в заданное время по МСК (±5 минут), каждый тайминг раз в день\n\n"
        "💚 пак работает · 💔 выключен · ⚠️ нет ключевых фраз\n\n"
        "Выберите пак или создайте новый ↓"
    )
    return txt


def settings_raise_text():
    config = sett.get("config")
    auto_raise_config = config["playerok"]["auto_raise_items"]
    if raise_packs.normalize_source(auto_raise_config.get("source")) == raise_packs.SOURCE_PACKS:
        return _settings_raise_packs_text(auto_raise_config)

    mode = _normalize_raise_mode(auto_raise_config.get("mode"))

    is_all_mode = bool(auto_raise_config["all"])
    auto_raise_items_all = "Все товары" if is_all_mode else "Указанные товары"
    auto_raise_items = sett.get("auto_raise_items")
    auto_raise_items_included = len(auto_raise_items["included"])
    auto_raise_items_excluded = len(auto_raise_items["excluded"])
    interval_hours = auto_raise_config.get("interval_hours", 24)
    timings_raw = auto_raise_config.get("timings", [])
    timings = timings_raw if isinstance(timings_raw, list) else []

    mode_name = "Интервальный" if mode == "interval" else "По таймингу"
    schedule_line = (
        f"⏱ <b>Интервал:</b> {interval_hours} ч"
        if mode == "interval"
        else f"🕒 <b>Тайминг:</b> {_format_timings(timings)}"
    )
    items_line = (
        f"➖ <b>Исключенные:</b> {auto_raise_items_excluded}"
        if is_all_mode
        else f"➕ <b>Включенные:</b> {auto_raise_items_included}"
    )

    if mode == "interval":
        mode_instruction = textwrap.dedent(
"""
<b>Как работает интервальный режим?</b>
• Бот проверяет товары каждую минуту
• Поднимает только активные товары с премиум-статусом
• Для каждого товара запоминает время последнего поднятия
• Поднимает товар только если прошёл заданный интервал
"""
        ).strip()
    else:
        mode_instruction = textwrap.dedent(
"""
<b>Как работает режим по таймингу?</b>
• Бот проверяет товары каждую минуту
• Время сравнивается по МСК
• Поднятие запускается, если до ближайшего тайминга не больше 5 минут
• Каждый тайминг выполняется не более одного раза в день
"""
        ).strip()

    txt = (
        "⚙️ <b>Настройки → 📈 Автоподнятие</b>\n"
        f"{_raise_disabled_line(auto_raise_config)}\n"
        f"{_raise_source_block(raise_packs.SOURCE_LOTS)}\n\n"
        f"📦 <b>Поднимать:</b> {auto_raise_items_all}\n"
        f"🧭 <b>Режим:</b> {mode_name}\n"
        f"{schedule_line}\n\n"
        f"{items_line}\n\n"
        "<b>Что такое автоматическое поднятие товаров?</b>\n"
        "Бот автоматически поднимает ваши товары с премиум-статусом, чтобы они оставались в топе.\n\n"
        f"{mode_instruction}\n\n"
        "Выберите действие ↓"
    )
    return txt


def _source_button(source: str) -> list[InlineKeyboardButton]:
    label = "📦 Все лоты" if source == raise_packs.SOURCE_LOTS else "🗂 Паки"
    return [InlineKeyboardButton(text=f"🔀 Тип настройки: {label}", callback_data="switch_auto_raise_source")]


def _settings_raise_packs_kb(page: int) -> InlineKeyboardMarkup:
    packs = raise_packs.load_packs()
    auto_raise_items = sett.get("auto_raise_items") or {}
    total_pages = max(1, (len(packs) + RAISE_PACKS_PER_PAGE - 1) // RAISE_PACKS_PER_PAGE)
    page = min(max(0, page), total_pages - 1)
    start = page * RAISE_PACKS_PER_PAGE

    rows = [_source_button(raise_packs.SOURCE_PACKS)]
    for number, pack in enumerate(packs[start:start + RAISE_PACKS_PER_PAGE], start=start + 1):
        rows.append([InlineKeyboardButton(
            text=f"{_pack_icon(pack)} {number}. {pack['name']} · {raise_packs.schedule_label(pack, max_timings=2)}",
            callback_data=calls.RaisePackAction(pid=pack["id"], action="open").pack(),
        )])

    if total_pages > 1:
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=calls.RaisePacksPagination(page=page - 1).pack()))
        nav_row.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="page_info"))
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton(text="➡️", callback_data=calls.RaisePacksPagination(page=page + 1).pack()))
        rows.append(nav_row)

    rows.append([InlineKeyboardButton(text="➕ Создать пак", callback_data="raise_pack_create")])
    rows.append([InlineKeyboardButton(
        text=f"➖ Исключенные: {len(auto_raise_items.get('excluded', []))}",
        callback_data=calls.ExcludedRaiseItemsPagination(page=0).pack(),
    )])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.MenuPagination(page=0).pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_raise_kb(page: int = 0):
    config = sett.get("config")
    auto_raise_config = config["playerok"]["auto_raise_items"]
    if raise_packs.normalize_source(auto_raise_config.get("source")) == raise_packs.SOURCE_PACKS:
        return _settings_raise_packs_kb(page)

    mode = _normalize_raise_mode(auto_raise_config.get("mode"))

    is_all_mode = bool(auto_raise_config["all"])
    auto_raise_items_all = "Все товары" if is_all_mode else "Указанные товары"
    auto_raise_items = sett.get("auto_raise_items")
    auto_raise_items_included = len(auto_raise_items["included"])
    auto_raise_items_excluded = len(auto_raise_items["excluded"])
    interval_hours = auto_raise_config.get("interval_hours", 24)
    timings_raw = auto_raise_config.get("timings", [])
    timings = timings_raw if isinstance(timings_raw, list) else []

    mode_label = "Интервальный" if mode == "interval" else "По таймингу"
    mode_details = (
        f"⏱ Интервал: {interval_hours} ч"
        if mode == "interval"
        else f"🕒 Тайминг: {_format_timings(timings, max_items=3)}"
    )
    mode_details_callback = "set_auto_raise_items_interval" if mode == "interval" else "set_auto_raise_items_timing"

    rows = [
        _source_button(raise_packs.SOURCE_LOTS),
        [InlineKeyboardButton(text=f"📦 Поднимать: {auto_raise_items_all}", callback_data="switch_auto_raise_items_all")],
    ]

    if is_all_mode:
        rows.append([
            InlineKeyboardButton(
                text=f"➖ Исключенные: {auto_raise_items_excluded}",
                callback_data=calls.ExcludedRaiseItemsPagination(page=0).pack(),
            )
        ])
    else:
        rows.append([
            InlineKeyboardButton(
                text=f"➕ Включенные: {auto_raise_items_included}",
                callback_data=calls.IncludedRaiseItemsPagination(page=0).pack(),
            )
        ])

    rows.extend([
        [InlineKeyboardButton(text=f"🧭 Режим: {mode_label}", callback_data="switch_auto_raise_items_mode")],
        [InlineKeyboardButton(text=mode_details, callback_data=mode_details_callback)],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.MenuPagination(page=0).pack())],
    ])

    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def settings_raise_float_text(placeholder: str):
    txt = textwrap.dedent(
        f"""
        ⚙️ <b>Настройки → 📈 Автоподнятие</b>
        \n{placeholder}
    """
    )
    return txt
