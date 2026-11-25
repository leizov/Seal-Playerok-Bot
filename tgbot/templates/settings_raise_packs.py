import html

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from core import raise_packs

from .. import callback_datas as calls
from .settings_raise import RAISE_PACKS_PER_PAGE


RAISE_PACK_PHRASES_PER_PAGE = 8
RAISE_PACK_LOTS_SHOWN = 15


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

    if pack["mode"] == raise_packs.MODE_TIMING:
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

    lines.append(
        "<i>Лот попадает в пак, если в его названии есть хотя бы одна фраза. "
        "Если лот подходит и под пак выше по списку — его поднимает тот пак.</i>"
    )
    return "\n".join(lines)


def raise_pack_kb(pack: dict, packs: list[dict]) -> InlineKeyboardMarkup:
    position, _ = raise_packs.find_pack(packs, pack["id"])
    is_timing = pack["mode"] == raise_packs.MODE_TIMING
    rows = [
        [_btn("💚 Пак включён" if pack["enabled"] else "💔 Пак выключен", pack, "toggle")],
        [_btn(f"🔑 Ключевые фразы: {len(pack['keyphrases'])}", pack, "phrases")],
        [_btn(f"🧭 Режим: {'По таймингу' if is_timing else 'Интервальный'}", pack, "mode")],
        [_btn(
            f"🕒 Тайминг: {', '.join(pack['timings'][:3]) or 'не задано'}"
            + (f" (+{len(pack['timings']) - 3})" if len(pack["timings"]) > 3 else "")
            if is_timing else f"⏱ Интервал: {raise_packs.format_hours(pack['interval_hours'])} ч",
            pack, "timings" if is_timing else "interval",
        )],
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


def raise_pack_lots_text(pack: dict, lots: dict) -> str:
    lines = [_pack_path(pack, "🔍 Подходящие лоты"), ""]
    if not pack["keyphrases"]:
        lines.append("⚠️ В паке нет ключевых фраз — под него не подходит ни один лот.")
        return "\n".join(lines)

    to_raise = lots["raise"]
    lines.append(f"✅ <b>Будут подниматься этим паком ({len(to_raise)}):</b>")
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
