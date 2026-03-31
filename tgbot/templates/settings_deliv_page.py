import textwrap
from html import escape

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from core.auto_deliveries import AUTO_DELIVERY_KIND_MULTI, normalize_auto_deliveries
from settings import Settings as sett

from .. import callback_datas as calls


def _format_keyphrases(keyphrases: list[str]) -> str:
    if not keyphrases:
        return "❌ Не задано"
    return "</code>, <code>".join(escape(phrase) for phrase in keyphrases)


def settings_deliv_page_text(index: int):
    auto_deliveries = normalize_auto_deliveries(sett.get("auto_deliveries") or [])
    if index < 0 or index >= len(auto_deliveries):
        return "❌ Авто-выдача не найдена"

    delivery = auto_deliveries[index]
    keyphrases = _format_keyphrases(delivery.get("keyphrases", []))
    enabled = "🟢 Включено" if delivery.get("enabled", True) else "🔴 Выключено"

    if delivery.get("kind") == AUTO_DELIVERY_KIND_MULTI:
        items = delivery.get("items", [])
        issued_total = delivery.get("issued_total", 0)
        issued_current_batch = delivery.get("issued_current_batch", 0)
        next_item = escape(items[0]) if items else "❌ Список пуст"

        txt = textwrap.dedent(
            f"""
            ✏️ <b>Редактирование авто-выдачи</b>

            <b>Тип:</b> 📦 <code>МУЛЬТИ</code>
            <b>Статус:</b> {enabled}
            🔑 <b>Ключевые фразы:</b> <code>{keyphrases}</code>

            📦 <b>Осталось товаров:</b> <code>{len(items)}</code>
            📤 <b>Выдано всего:</b> <code>{issued_total}</code>
            📊 <b>Выдано в текущей партии:</b> <code>{issued_current_batch}</code>
            🔜 <b>Следующий товар:</b> <blockquote>{next_item}</blockquote>

            Выберите параметр для изменения ↓
        """
        )
        return txt

    message_lines = delivery.get("message", [])
    message = "<br>".join(escape(line) for line in message_lines) or "❌ Не задано"
    txt = textwrap.dedent(
        f"""
        ✏️ <b>Редактирование авто-выдачи</b>

        <b>Тип:</b> 🧾 <code>ОБЫЧНАЯ</code>
        <b>Статус:</b> {enabled}
        🔑 <b>Ключевые фразы:</b> <code>{keyphrases}</code>
        💬 <b>Сообщение:</b> <blockquote>{message}</blockquote>

        Выберите параметр для изменения ↓
    """
    )
    return txt


def settings_deliv_page_kb(index: int, page: int = 0):
    auto_deliveries = normalize_auto_deliveries(sett.get("auto_deliveries") or [])
    if index < 0 or index >= len(auto_deliveries):
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.AutoDeliveriesPagination(page=page).pack())]
            ]
        )

    delivery = auto_deliveries[index]
    keyphrases = ", ".join(delivery.get("keyphrases", [])) or "❌ Не задано"
    enabled = delivery.get("enabled", True)
    toggle_text = "🟢 Включено" if enabled else "🔴 Выключено"

    rows = [
        [InlineKeyboardButton(text=toggle_text, callback_data="switch_auto_delivery_enabled")],
        [InlineKeyboardButton(text=f"🔑 Ключевые фразы: {keyphrases}", callback_data="enter_auto_delivery_keyphrases")],
    ]

    if delivery.get("kind") == AUTO_DELIVERY_KIND_MULTI:
        rows.append([InlineKeyboardButton(text="➕ Добавить товары", callback_data="enter_auto_delivery_add_items")])
        rows.append([InlineKeyboardButton(text="♻️ Обновить товары", callback_data="enter_auto_delivery_replace_items")])
    else:
        message = "\n".join(delivery.get("message", [])) or "❌ Не задано"
        rows.append([InlineKeyboardButton(text=f"💬 Сообщение: {message}", callback_data="enter_auto_delivery_message")])

    rows.append([InlineKeyboardButton(text="🗑️ Удалить авто-выдачу", callback_data="confirm_deleting_auto_delivery")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.AutoDeliveriesPagination(page=page).pack())])

    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def settings_deliv_page_float_text(placeholder: str):
    txt = textwrap.dedent(
        f"""
        ✏️ <b>Редактирование авто-выдачи</b>
        \n{placeholder}
    """
    )
    return txt
