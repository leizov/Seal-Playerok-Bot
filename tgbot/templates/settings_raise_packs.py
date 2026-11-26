import html
import math
import time
from datetime import datetime

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from core import raise_packs

from .. import callback_datas as calls
from .settings_raise import RAISE_PACKS_PER_PAGE


RAISE_PACK_PHRASES_PER_PAGE = 8
RAISE_PACK_LOTS_SHOWN = 15
RAISE_PACK_SCHEDULE_LINES_IN_CARD = 8

MODE_NAMES = {
    raise_packs.MODE_INTERVAL: "Интервальный",
    raise_packs.MODE_TIMING: "По таймингу",
    raise_packs.MODE_POSITION: "По позиции",
}
MODE_ICONS = {
    raise_packs.MODE_INTERVAL: "⏱",
    raise_packs.MODE_TIMING: "🕒",
    raise_packs.MODE_POSITION: "📊",
}


def _esc(value) -> str:
    return html.escape(str(value or ""), quote=False)


def _pack_path(pack: dict, tail: str | None = None) -> str:
    path = f"⚙️ <b>Автоподнятие → 🗂 Паки → {_esc(pack['name'])}</b>"
    if tail:
        path += f"<b> → {tail}</b>"
    return path


def _btn(text: str, pack: dict, action: str, index: int = 0) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=text,
        callback_data=calls.RaisePackAction(pid=pack["id"], action=action, index=index).pack(),
    )


def _plural(number: int, one: str, few: str, many: str) -> str:
    number = abs(int(number))
    if number % 10 == 1 and number % 100 != 11:
        return one
    if 2 <= number % 10 <= 4 and not 12 <= number % 100 <= 14:
        return few
    return many


def _ago(timestamp: float | None) -> str:
    if not timestamp:
        return "—"
    seconds = max(0, time.time() - timestamp)
    if seconds < 60:
        return "только что"
    if seconds < 3600:
        return f"{int(seconds // 60)} мин назад"
    return f"{int(seconds // 3600)} ч назад"


def _msk_now() -> datetime:
    return datetime.now(raise_packs.MSK_TZ)


def raise_pack_pause_line(pack: dict) -> str | None:
    """«⏳ Начнёт поднимать через N мин» — пауза режима «По позиции» после изменения настроек."""
    if pack["mode"] != raise_packs.MODE_POSITION:
        return None
    left = raise_packs.pause_left_seconds(pack)
    if left <= 0:
        return None
    minutes = max(1, math.ceil(left / 60))
    return (
        f"⏳ <b>Начнёт поднимать через {minutes} мин</b> — недавно меняли настройки пака. "
        "Кулдаун лотов на это время замирает"
    )


def raise_pack_schedule_lines(pack: dict, limit: int | None = None) -> list[str]:
    """Участки расписания и пустое время по порядку суток."""
    lines = []
    for kind, value in raise_packs.schedule_entries(pack["position_schedule"]):
        if kind == "segment":
            lines.append(f"• {raise_packs.segment_range(value)} — {raise_packs.segment_summary(value)}")
        else:
            lines.append(f"• {raise_packs.format_range(*value)} — ▫️ пусто, ничего не поднимается")
    if not lines:
        lines.append("• весь день — ▫️ пусто, ничего не поднимается")
    if limit is not None and len(lines) > limit:
        hidden = len(lines) - limit
        lines = lines[:limit] + [f"<i>…и ещё {hidden} — в «📅 Расписание»</i>"]
    return lines


def raise_pack_now_line(pack: dict) -> str:
    now = _msk_now()
    segment = raise_packs.active_segment(pack["position_schedule"], raise_packs.msk_minutes(now))
    clock = now.strftime("%H:%M")
    if segment is None or segment["position"] is None:
        return f"▶️ <b>Сейчас ({clock}):</b> ничего не поднимается"
    return f"▶️ <b>Сейчас ({clock}):</b> {raise_packs.segment_summary(segment)}"


def raise_packs_list_page(packs: list[dict], pack_id: str) -> int:
    index, _ = raise_packs.find_pack(packs, pack_id)
    return max(0, index) // RAISE_PACKS_PER_PAGE


def raise_pack_back_kb(pack: dict, action: str = "open", index: int = 0) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn("⬅️ Назад", pack, action, index)]])


def raise_packs_float_text(placeholder: str) -> str:
    return f"⚙️ <b>Автоподнятие → 🗂 Паки</b>\n\n{placeholder}"


def raise_pack_float_text(pack: dict, placeholder: str, tail: str | None = None) -> str:
    return f"{_pack_path(pack, tail)}\n\n{placeholder}"


# ── Карточка пака ──

def raise_pack_text(pack: dict, packs: list[dict], notice: str | None = None) -> str:
    position, _ = raise_packs.find_pack(packs, pack["id"])
    lines = []
    if notice:
        lines += [notice, ""]
    lines.append(_pack_path(pack))
    lines.append("")

    if pack["enabled"]:
        lines.append("💚 <b>Статус:</b> включён")
    else:
        lines.append("💔 <b>Статус:</b> выключен — лоты пака не поднимаются")

    if pack["mode"] == raise_packs.MODE_POSITION:
        lines.append("🧭 <b>Режим:</b> по позиции")
        lines.append("📅 <b>Расписание (МСК):</b>")
        lines += raise_pack_schedule_lines(pack, limit=RAISE_PACK_SCHEDULE_LINES_IN_CARD)
        lines.append(raise_pack_now_line(pack))
        pause = raise_pack_pause_line(pack)
        if pause:
            lines.append(pause)
    elif pack["mode"] == raise_packs.MODE_TIMING:
        lines.append("🧭 <b>Режим:</b> по таймингу")
        timings = ", ".join(pack["timings"]) if pack["timings"] else "не задано"
        lines.append(f"🕒 <b>Тайминг (МСК):</b> {timings}")
    else:
        lines.append("🧭 <b>Режим:</b> интервальный")
        lines.append(f"⏱ <b>Интервал:</b> каждые {raise_packs.format_hours(pack['interval_hours'])} ч")

    phrases = pack["keyphrases"]
    if phrases:
        shown = ", ".join(f"<code>{_esc(p)}</code>" for p in phrases[:10])
        if len(phrases) > 10:
            shown += f" и ещё {len(phrases) - 10}"
        lines.append(f"🔑 <b>Ключевые фразы ({len(phrases)}):</b> {shown}")
    else:
        lines.append("🔑 <b>Ключевые фразы:</b> нет")

    lines.append(f"📍 <b>Место в списке:</b> {position + 1} из {len(packs)}")
    lines.append("")

    if not phrases:
        lines.append("⚠️ Добавьте ключевые фразы — без них пак ничего не поднимает.")
    if pack["mode"] == raise_packs.MODE_TIMING and not pack["timings"]:
        lines.append("⚠️ Задайте тайминги — без них пак ничего не поднимает.")
    if pack["mode"] == raise_packs.MODE_POSITION and not raise_packs.has_raising_segments(pack["position_schedule"]):
        lines.append("⚠️ В расписании нет участков с местом — пак ничего не поднимает.")

    lines.append(
        "<i>Лот попадает в пак, если в его названии есть хотя бы одна фраза. "
        "Если лот подходит и под пак выше по списку — его поднимает тот пак.</i>"
    )
    return "\n".join(lines)


def raise_pack_kb(pack: dict, packs: list[dict]) -> InlineKeyboardMarkup:
    position, _ = raise_packs.find_pack(packs, pack["id"])
    mode = pack["mode"]
    if mode == raise_packs.MODE_POSITION:
        count = len(pack["position_schedule"])
        schedule_button = _btn(
            f"📅 Расписание: {count} {_plural(count, 'участок', 'участка', 'участков')}", pack, "schedule",
        )
    elif mode == raise_packs.MODE_TIMING:
        schedule_button = _btn(
            f"🕒 Тайминг: {', '.join(pack['timings'][:3]) or 'не задано'}"
            + (f" (+{len(pack['timings']) - 3})" if len(pack["timings"]) > 3 else ""),
            pack, "timings",
        )
    else:
        schedule_button = _btn(f"⏱ Интервал: {raise_packs.format_hours(pack['interval_hours'])} ч", pack, "interval")
    rows = [
        [_btn("💚 Пак включён" if pack["enabled"] else "💔 Пак выключен", pack, "toggle")],
        [_btn(f"🔑 Ключевые фразы: {len(pack['keyphrases'])}", pack, "phrases")],
        [_btn(f"🧭 Режим: {MODE_NAMES[mode]}", pack, "mode")],
        [schedule_button],
        [_btn("🔍 Какие лоты подходят", pack, "lots")],
        [_btn("🚀 Поднять сейчас", pack, "raise")],
    ]
    order_row = []
    if position > 0:
        order_row.append(_btn("⬆️ Выше в списке", pack, "up"))
    if 0 <= position < len(packs) - 1:
        order_row.append(_btn("⬇️ Ниже в списке", pack, "down"))
    if order_row:
        rows.append(order_row)
    rows.append([_btn("✏️ Переименовать", pack, "rename"), _btn("🗑 Удалить", pack, "delete")])
    rows.append([InlineKeyboardButton(
        text="⬅️ Назад",
        callback_data=calls.RaisePacksPagination(page=raise_packs_list_page(packs, pack["id"])).pack(),
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── Ключевые фразы ──

def raise_pack_phrases_page(pack: dict, page: int) -> int:
    total_pages = max(1, (len(pack["keyphrases"]) + RAISE_PACK_PHRASES_PER_PAGE - 1) // RAISE_PACK_PHRASES_PER_PAGE)
    return min(max(0, page), total_pages - 1)


def raise_pack_phrases_text(pack: dict, notice: str | None = None) -> str:
    lines = []
    if notice:
        lines += [notice, ""]
    lines += [
        _pack_path(pack, "🔑 Ключевые фразы"),
        "",
        "Лот попадает в пак, если в его названии есть <b>хотя бы одна</b> из фраз (регистр не важен).",
        "Нажмите на фразу, чтобы удалить её.",
        "",
        f"<b>Всего фраз:</b> {len(pack['keyphrases'])}",
    ]
    return "\n".join(lines)


def raise_pack_phrases_kb(pack: dict, page: int = 0) -> InlineKeyboardMarkup:
    phrases = pack["keyphrases"]
    page = raise_pack_phrases_page(pack, page)
    start = page * RAISE_PACK_PHRASES_PER_PAGE
    rows = []
    for index, phrase in enumerate(phrases[start:start + RAISE_PACK_PHRASES_PER_PAGE], start=start):
        label = phrase if len(phrase) <= 40 else phrase[:40] + "…"
        rows.append([_btn(f"🗑 {label}", pack, "phrase_del", index)])

    total_pages = max(1, (len(phrases) + RAISE_PACK_PHRASES_PER_PAGE - 1) // RAISE_PACK_PHRASES_PER_PAGE)
    if total_pages > 1:
        nav_row = []
        if page > 0:
            nav_row.append(_btn("⬅️", pack, "phrases", page - 1))
        nav_row.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="page_info"))
        if page < total_pages - 1:
            nav_row.append(_btn("➡️", pack, "phrases", page + 1))
        rows.append(nav_row)

    rows.append([_btn("➕ Добавить", pack, "phrase_add", page), _btn("📄 Из файла", pack, "phrase_file", page)])
    rows.append([_btn("⬅️ Назад", pack, "open")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── Подходящие лоты ──

def _lot_lines(items, limit: int = RAISE_PACK_LOTS_SHOWN, suffix=None) -> list[str]:
    lines = []
    for entry in items[:limit]:
        if suffix:
            item, extra = entry
            lines.append(f"• {_esc(getattr(item, 'name', ''))} — {suffix(extra)}")
        else:
            lines.append(f"• {_esc(getattr(entry, 'name', ''))}")
    if len(items) > limit:
        lines.append(f"<i>…и ещё {len(items) - limit}</i>")
    return lines


def _position_lot_lines(items, positions: dict, limit: int = RAISE_PACK_LOTS_SHOWN) -> list[str]:
    lines = []
    for item in items[:limit]:
        entry = positions.get(getattr(item, "id", None)) or {}
        name = _esc(getattr(item, "name", ""))
        if entry.get("position") is not None:
            lines.append(f"• {name} — 📍 {entry['position']} ({_ago(entry.get('checked_at'))})")
        else:
            lines.append(f"• {name} — 📍 ещё не проверялось")
    if len(items) > limit:
        lines.append(f"<i>…и ещё {len(items) - limit}</i>")
    return lines


def raise_pack_lots_text(pack: dict, lots: dict, positions: dict | None = None) -> str:
    lines = [_pack_path(pack, "🔍 Подходящие лоты"), ""]
    if not pack["keyphrases"]:
        lines.append("⚠️ В паке нет ключевых фраз — под него не подходит ни один лот.")
        return "\n".join(lines)

    to_raise = lots["raise"]
    lines.append(f"✅ <b>Будут подниматься этим паком ({len(to_raise)}):</b>")
    if pack["mode"] == raise_packs.MODE_POSITION and positions is not None:
        lines += _position_lot_lines(to_raise, positions) or ["—"]
    else:
        lines += _lot_lines(to_raise) or ["—"]

    if lots["taken"]:
        lines += ["", f"↪️ <b>Их поднимает пак выше по списку ({len(lots['taken'])}):</b>"]
        lines += _lot_lines(lots["taken"], suffix=lambda owner: f"пак «{_esc(owner['name'])}»")
    if lots["not_premium"]:
        lines += ["", f"⚪ <b>Без премиум-статуса — бот их не поднимает ({len(lots['not_premium'])}):</b>"]
        lines += _lot_lines(lots["not_premium"])
    if lots["excluded"]:
        lines += ["", f"➖ <b>В списке «Исключенные» ({len(lots['excluded'])}):</b>"]
        lines += _lot_lines(lots["excluded"])

    if not pack["enabled"]:
        lines += ["", "💔 <i>Пак выключен — пока он выключен, эти лоты автоматически не поднимаются.</i>"]
    if pack["mode"] == raise_packs.MODE_POSITION and positions is not None:
        lines += ["", "<i>📍 — место лота в категории по последней проверке бота (проверка раз в минуту, "
                      "пока действует участок с местом).</i>"]
    lines += ["", "<i>Учитываются только активные лоты вашего аккаунта.</i>"]
    return "\n".join(lines)


def raise_pack_lots_kb(pack: dict) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("🔄 Обновить", pack, "lots")],
        [_btn("⬅️ Назад", pack, "open")],
    ])


# ── Поднять сейчас ──

def raise_pack_raise_confirm_text(pack: dict, items) -> str:
    lines = [
        _pack_path(pack, "🚀 Поднять сейчас"),
        "",
        f"Будет поднято лотов: <b>{len(items)}</b>",
    ]
    lines += _lot_lines(items, limit=10)
    lines += [
        "",
        "💰 Каждое поднятие платное: за каждый лот спишется стоимость премиум-статуса.",
        "Расписание пака не меняется — для интервала отсчёт начнётся заново с момента поднятия.",
        "",
        "Подтвердите ↓",
    ]
    return "\n".join(lines)


def raise_pack_raise_confirm_kb(pack: dict, count: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        _btn(f"✅ Поднять {count}", pack, "raise_yes"),
        _btn("❌ Отмена", pack, "open"),
    ]])


# ── Удаление ──

def raise_pack_delete_text(pack: dict) -> str:
    return (
        f"{_pack_path(pack, '🗑 Удаление')}\n\n"
        f"Удалить пак <b>«{_esc(pack['name'])}»</b>?\n"
        f"Его ключевые фразы ({len(pack['keyphrases'])}) и расписание будут удалены. "
        "Лоты пака перестанут подниматься (если не подходят под другой пак)."
    )


def raise_pack_delete_kb(pack: dict) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        _btn("✅ Да, удалить", pack, "delete_yes"),
        _btn("❌ Отмена", pack, "open"),
    ]])


# ── Режим ──
# Кнопки режимов только выбирают (выбор — в callback_data, ничего не сохраняется),
# применяет выбор кнопка «✅ Сохранить».

MODE_SELECTED_MARK = "🔵"
MODE_UNSELECTED_MARK = "⚪"

MODE_DESCRIPTIONS = {
    raise_packs.MODE_INTERVAL:
        "Лот поднимается, когда с его последнего поднятия прошло заданное число часов. "
        "У каждого лота свой отсчёт.",
    raise_packs.MODE_TIMING:
        "Лоты пака поднимаются в заданное время по МСК (±5 минут), каждый тайминг — раз в день. "
        "Место лота не учитывается.",
    raise_packs.MODE_POSITION:
        "Бот раз в минуту смотрит место каждого лота в его категории. Лот поднимается, только если "
        "он две проверки подряд ниже нужного места и прошёл кулдаун. Место и кулдаун задаются "
        "участками времени в «📅 Расписание».",
}


def _mode_settings_line(pack: dict, mode: str) -> str:
    if mode == raise_packs.MODE_INTERVAL:
        return f"интервал {raise_packs.format_hours(pack['interval_hours'])} ч"
    if mode == raise_packs.MODE_TIMING:
        if not pack["timings"]:
            return "тайминги не заданы — пока их нет, пак ничего не поднимает"
        return "тайминги " + ", ".join(pack["timings"])
    schedule = pack["position_schedule"]
    if not schedule:
        return "расписания ещё нет — после сохранения бот спросит место"
    count = len(schedule)
    return f"расписание: {count} {_plural(count, 'участок', 'участка', 'участков')}"


def raise_pack_mode_text(pack: dict, selected: str | None = None) -> str:
    current = pack["mode"]
    selected = selected if selected in raise_packs.MODES else current
    lines = [
        _pack_path(pack, "🧭 Режим"),
        "",
        f"<b>Сейчас:</b> {MODE_ICONS[current]} {MODE_NAMES[current]}",
    ]
    if selected != current:
        lines.append(f"<b>Выбран:</b> {MODE_ICONS[selected]} {MODE_NAMES[selected]} — ещё не сохранён")
    for mode in raise_packs.MODES:
        tag = " <i>(сейчас)</i>" if mode == current else ""
        title = f"{MODE_ICONS[mode]} {MODE_NAMES[mode]}"
        description = MODE_DESCRIPTIONS[mode]
        if mode == selected:
            title, description = f"<b>{title}</b>", f"<b>{description}</b>"
            mark = MODE_SELECTED_MARK
        else:
            mark = MODE_UNSELECTED_MARK
        lines += [
            "",
            f"{mark} {title}{tag}",
            description,
            f"<i>Настройка: {_mode_settings_line(pack, mode)}</i>",
        ]
    lines.append("")
    if selected == current:
        lines.append("Выберите режим кнопкой ниже, сравните описание и нажмите «✅ Сохранить».")
    else:
        lines.append(f"Нажмите «✅ Сохранить», чтобы переключить пак на «{MODE_NAMES[selected]}».")
        if selected == raise_packs.MODE_POSITION:
            lines.append(
                f"<i>После переключения пак {raise_packs.SETTINGS_PAUSE_SECONDS // 60} минуты ничего не поднимает.</i>"
            )
    lines.append("<i>Настройки каждого режима сохраняются при переключении.</i>")
    return "\n".join(lines)


def raise_pack_mode_kb(pack: dict, selected: str | None = None) -> InlineKeyboardMarkup:
    current = pack["mode"]
    selected = selected if selected in raise_packs.MODES else current
    rows = []
    for index, mode in enumerate(raise_packs.MODES):
        mark = MODE_SELECTED_MARK if mode == selected else MODE_UNSELECTED_MARK
        rows.append([_btn(f"{mark} {MODE_ICONS[mode]} {MODE_NAMES[mode]}", pack, "mode_pick", index)])
    if selected != current:
        rows.append([_btn("✅ Сохранить", pack, "mode_save", raise_packs.MODES.index(selected))])
    rows.append([_btn("⬅️ Назад", pack, "open")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def raise_pack_first_position_text(pack: dict, error: str | None = None) -> str:
    lines = [_pack_path(pack, "📊 По позиции"), ""]
    if error:
        lines += [error, ""]
    lines += [
        "Введите место в категории, ниже которого лот нужно поднимать ↓",
        "Например, <code>10</code> — держать лоты пака в топ‑10.",
        "",
        f"<i>Это место станет участком «весь день» с кулдауном {raise_packs.DEFAULT_COOLDOWN_MINUTES} мин. "
        "Потом в «📅 Расписание» можно добавить участки времени со своим местом и кулдауном.</i>",
    ]
    return "\n".join(lines)


# ── Расписание режима «По позиции» ──

def raise_pack_schedule_text(pack: dict, notice: str | None = None) -> str:
    lines = []
    if notice:
        lines += [notice, ""]
    lines += [
        _pack_path(pack, "📅 Расписание"),
        "",
        "Время по МСК. Бот раз в минуту проверяет место каждого лота пака. Лот поднимается, если он "
        "ниже места участка две проверки подряд и с его последнего поднятия прошёл кулдаун участка.",
        "",
    ]
    lines += raise_pack_schedule_lines(pack)
    lines.append("")
    lines.append(raise_pack_now_line(pack))
    pause = raise_pack_pause_line(pack)
    if pause:
        lines.append(pause)
    if pack["mode"] != raise_packs.MODE_POSITION:
        lines += ["", "ℹ️ <i>Расписание работает, только когда у пака выбран режим «По позиции».</i>"]
    lines += [
        "",
        "<i>Нажмите на участок, чтобы изменить или удалить его. Новый участок забирает время у тех, "
        "с которыми пересекается. Время без участков пустое — в него лоты не поднимаются.</i>",
    ]
    return "\n".join(lines)


def _segment_button_text(segment: dict) -> str:
    if segment["position"] is None:
        return f"{raise_packs.segment_range(segment)} · 🚫 не поднимать"
    return (
        f"{raise_packs.segment_range(segment)} · ≤{segment['position']} · "
        f"{raise_packs.format_cooldown(segment['cooldown_minutes'])}"
    )


def raise_pack_schedule_kb(pack: dict) -> InlineKeyboardMarkup:
    rows = [
        [_btn(_segment_button_text(segment), pack, "seg", segment["id"])]
        for segment in pack["position_schedule"]
    ]
    rows.append([_btn("➕ Добавить участок", pack, "seg_add")])
    rows.append([_btn("⬅️ Назад", pack, "open")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def raise_pack_segment_text(pack: dict, segment: dict, notice: str | None = None) -> str:
    lines = []
    if notice:
        lines += [notice, ""]
    lines += [
        _pack_path(pack, f"📅 Расписание → {raise_packs.segment_range(segment)}"),
        "",
        f"🕒 <b>Время (МСК):</b> {raise_packs.segment_range(segment)}",
    ]
    if segment["position"] is None:
        lines.append("📊 <b>Место:</b> 🚫 не поднимать — в это время пак ничего не поднимает")
    else:
        lines.append(f"📊 <b>Место:</b> поднимать, если лот ниже {segment['position']}-го места")
        lines.append(f"🧊 <b>Кулдаун:</b> {raise_packs.format_cooldown(segment['cooldown_minutes'])} — "
                     "не чаще одного поднятия лота за это время")
    lines += ["", "<i>Если удалить участок, его время станет пустым — в него ничего не поднимается.</i>"]
    return "\n".join(lines)


def raise_pack_segment_kb(pack: dict, segment: dict) -> InlineKeyboardMarkup:
    sid = segment["id"]
    rows = [
        [_btn("🕒 Изменить время", pack, "seg_time", sid)],
        [_btn("📊 Изменить место", pack, "seg_pos", sid)],
    ]
    if segment["position"] is not None:
        rows.append([_btn("🧊 Изменить кулдаун", pack, "seg_cd", sid)])
    rows.append([_btn("🗑 Удалить участок", pack, "seg_del", sid)])
    rows.append([_btn("⬅️ Назад", pack, "schedule")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _segment_back(pack: dict, sid: int | None) -> InlineKeyboardButton:
    if sid:
        return _btn("⬅️ Назад", pack, "seg", sid)
    return _btn("❌ Отмена", pack, "schedule")


def raise_pack_segment_back_kb(pack: dict, sid: int | None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_segment_back(pack, sid)]])


def raise_pack_segment_time_text(pack: dict, segment: dict | None = None, error: str | None = None) -> str:
    if segment is None:
        lines = [_pack_path(pack, "➕ Новый участок"), "", "<b>Шаг 1 из 3 — время</b>", ""]
    else:
        lines = [
            _pack_path(pack, f"📅 Расписание → {raise_packs.segment_range(segment)}"), "",
            f"Сейчас: <b>{raise_packs.segment_range(segment)}</b>", "",
        ]
    if error:
        lines += [error, ""]
    lines += [
        "Введите время участка по МСК ↓",
        "Например: <code>15-20</code>, <code>15:30-20:00</code>, <code>23-8</code> (через полночь), "
        "<code>весь день</code>",
        "",
        "<i>Участок заберёт это время у тех, с которыми пересекается.</i>",
    ]
    return "\n".join(lines)


def raise_pack_segment_position_text(pack: dict, time_range: str, is_new: bool, error: str | None = None) -> str:
    if is_new:
        lines = [_pack_path(pack, f"➕ Новый участок {time_range}"), "", "<b>Шаг 2 из 3 — место</b>", ""]
    else:
        lines = [_pack_path(pack, f"📅 Расписание → {time_range}"), ""]
    if error:
        lines += [error, ""]
    lines += [
        "Введите место в категории: лот поднимается, если опустился ниже него ↓",
        "Например, <code>10</code> — держать лоты в топ‑10.",
        "",
        "Или нажмите «🚫 Не поднимать» — тогда в это время пак ничего не поднимает.",
    ]
    return "\n".join(lines)


def raise_pack_segment_position_kb(pack: dict, sid: int | None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("🚫 Не поднимать", pack, "seg_skip", sid or 0)],
        [_segment_back(pack, sid)],
    ])


def raise_pack_segment_cooldown_text(pack: dict, time_range: str, is_new: bool, error: str | None = None) -> str:
    if is_new:
        lines = [_pack_path(pack, f"➕ Новый участок {time_range}"), "", "<b>Шаг 3 из 3 — кулдаун</b>", ""]
    else:
        lines = [_pack_path(pack, f"📅 Расписание → {time_range}"), ""]
    if error:
        lines += [error, ""]
    lines += [
        "Введите кулдаун в минутах — минимальное время между поднятиями одного лота ↓",
        "",
        f"<i>Не меньше {raise_packs.MIN_COOLDOWN_MINUTES} мин. Меньше "
        f"{raise_packs.CONFIRM_COOLDOWN_BELOW_MINUTES} мин — только с подтверждением: "
        "каждое поднятие платное.</i>",
    ]
    return "\n".join(lines)


def raise_pack_segment_cooldown_kb(pack: dict, sid: int | None) -> InlineKeyboardMarkup:
    default = raise_packs.DEFAULT_COOLDOWN_MINUTES
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn(f"⏭ {default} мин (по умолчанию)", pack, "seg_cd_set", default)],
        [_segment_back(pack, sid)],
    ])


def raise_pack_cooldown_confirm_text(pack: dict, time_range: str, minutes: int) -> str:
    per_hour = raise_packs.cooldown_hourly_max(minutes)
    return "\n".join([
        _pack_path(pack, f"📅 Расписание → {time_range}"),
        "",
        f"⚠️ <b>Кулдаун {raise_packs.format_cooldown(minutes)}</b>",
        "",
        f"С таким кулдауном один лот может подниматься до <b>{per_hour} раз в час</b>, "
        "и каждое поднятие платное. Если конкуренты часто поднимают свои лоты, это быстро расходует баланс.",
        "",
        f"Оставить {raise_packs.format_cooldown(minutes)}?",
    ])


def raise_pack_cooldown_confirm_kb(pack: dict, minutes: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn(f"✅ Да, {raise_packs.format_cooldown(minutes)}", pack, "seg_cd_set", minutes)],
        [_btn("✏️ Ввести другой", pack, "seg_cd_again")],
    ])
