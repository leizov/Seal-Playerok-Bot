import math
import textwrap

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from core.auto_deliveries import AUTO_DELIVERY_KIND_MULTI, normalize_auto_deliveries
from settings import Settings as sett

from .. import callback_datas as calls


def _cut(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _kind_tag(kind: str) -> str:
    return "📦 [МУЛЬТИ]" if kind == AUTO_DELIVERY_KIND_MULTI else "🧾 [ОБЫЧНАЯ]"


def _delivery_preview(delivery: dict) -> str:
    if delivery.get("kind") == AUTO_DELIVERY_KIND_MULTI:
        items = delivery.get("items", [])
        issued_total = delivery.get("issued_total", 0)
        return f"Остаток: {len(items)} | Выдано: {issued_total}"

    message_lines = delivery.get("message", [])
    if not message_lines:
        return "Сообщение не задано"
    return message_lines[0]


def settings_delivs_text():
    auto_deliveries = normalize_auto_deliveries(sett.get("auto_deliveries") or [])
    static_count = sum(1 for delivery in auto_deliveries if delivery.get("kind") != AUTO_DELIVERY_KIND_MULTI)
    multi_count = len(auto_deliveries) - static_count

    txt = textwrap.dedent(
        f"""
        ⚙️ <b>Настройки</b> → 🚀 <b>Авто-выдача</b>
        Всего <b>{len(auto_deliveries)}</b> правил авто-выдачи

        <b>Типы:</b>
        ┣ 🧾 [ОБЫЧНАЯ] {static_count}
        ┗ 📦 [МУЛЬТИ] {multi_count}

        Нажмите на правило ниже, чтобы открыть его карточку.
        """
    )
    return txt


def settings_delivs_kb(page: int = 0):
    auto_deliveries = normalize_auto_deliveries(sett.get("auto_deliveries") or [])
    rows = []
    items_per_page = 7
    total_pages = math.ceil(len(auto_deliveries) / items_per_page)
    total_pages = total_pages if total_pages > 0 else 1

    if page < 0:
        page = 0
    elif page >= total_pages:
        page = total_pages - 1

    start_offset = page * items_per_page
    end_offset = min(start_offset + items_per_page, len(auto_deliveries))

    for idx in range(start_offset, end_offset):
        delivery = auto_deliveries[idx]
        status_icon = "🟢" if delivery.get("enabled", True) else "🔴"
        kind = _kind_tag(delivery.get("kind"))
        keyphrases = ", ".join(delivery.get("keyphrases", [])) or "Без ключевых фраз"
        preview = _delivery_preview(delivery)
        button_text = f"{status_icon} {kind} {_cut(keyphrases, 26)} → {_cut(preview, 22)}"
        rows.append(
            [
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=calls.AutoDeliveryPage(index=idx).pack(),
                )
            ]
        )

    if total_pages > 1:
        buttons_row = []
        btn_back = (
            InlineKeyboardButton(
                text="←",
                callback_data=calls.AutoDeliveriesPagination(page=page - 1).pack(),
            )
            if page > 0
            else InlineKeyboardButton(text="🛑", callback_data="123")
        )
        buttons_row.append(btn_back)

        btn_pages = InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="enter_auto_deliveries_page")
        buttons_row.append(btn_pages)

        btn_next = (
            InlineKeyboardButton(
                text="→",
                callback_data=calls.AutoDeliveriesPagination(page=page + 1).pack(),
            )
            if page < total_pages - 1
            else InlineKeyboardButton(text="🛑", callback_data="123")
        )
        buttons_row.append(btn_next)
        rows.append(buttons_row)

    rows.append([InlineKeyboardButton(text="➕ Добавить автовыдачу", callback_data="enter_new_auto_delivery")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.MenuPagination(page=0).pack())])

    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def settings_deliv_float_text(placeholder: str):
    txt = textwrap.dedent(
        f"""
        ⚙️ <b>Настройки</b> → ⌨️ <b>Авто-выдача</b>
        \n{placeholder}
    """
    )
    return txt


def settings_new_deliv_float_text(placeholder: str):
    txt = textwrap.dedent(
        f"""
        🚀 <b>Добавление пользовательской авто-выдачи</b>
        \n{placeholder}
    """
    )
    return txt


def settings_new_deliv_type_float_text(placeholder: str):
    txt = textwrap.dedent(
        f"""
        🚀 <b>Новая авто-выдача</b>
        \n{placeholder}
    """
    )
    return txt


def settings_new_deliv_type_kb(page: int = 0):
    rows = [
        [InlineKeyboardButton(text="🧾 Обычная авто-выдача", callback_data="select_new_auto_delivery_kind_static")],
        [InlineKeyboardButton(text="📦 Мультивыдача (уникальные строки)", callback_data="select_new_auto_delivery_kind_multi")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.AutoDeliveriesPagination(page=page).pack())],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
