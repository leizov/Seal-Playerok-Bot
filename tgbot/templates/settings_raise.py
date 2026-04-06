import textwrap

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from settings import Settings as sett

from .. import callback_datas as calls


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


def settings_raise_text():
    config = sett.get("config")
    auto_raise_config = config["playerok"]["auto_raise_items"]
    mode = _normalize_raise_mode(auto_raise_config.get("mode"))

    is_all_mode = bool(auto_raise_config["all"])
    auto_raise_items_all = "Все предметы" if is_all_mode else "Указанные предметы"
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

    txt = textwrap.dedent(
f"""
⚙️ <b>Настройки → 📈 Автоподнятие</b>

📦 <b>Поднимать:</b> {auto_raise_items_all}
🧭 <b>Режим:</b> {mode_name}
{schedule_line}

{items_line}

<b>Что такое автоматическое поднятие товаров?</b>
Бот автоматически поднимает ваши товары с премиум-статусом, чтобы они оставались в топе.

{mode_instruction}

Выберите действие ↓
"""
    )
    return txt


def settings_raise_kb():
    config = sett.get("config")
    auto_raise_config = config["playerok"]["auto_raise_items"]
    mode = _normalize_raise_mode(auto_raise_config.get("mode"))

    is_all_mode = bool(auto_raise_config["all"])
    auto_raise_items_all = "Все предметы" if is_all_mode else "Указанные предметы"
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

    rows = [[InlineKeyboardButton(text=f"📦 Поднимать: {auto_raise_items_all}", callback_data="switch_auto_raise_items_all")]]

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
