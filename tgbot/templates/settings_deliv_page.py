import textwrap
from html import escape

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from core.auto_deliveries import (
    AUTO_DELIVERY_KIND_MULTI,
    DEFAULT_MULTI_FORMAT,
    normalize_auto_deliveries,
    render_multi_delivery,
    render_static_delivery,
)
from plbot.placeholders import placeholders_help
from settings import Settings as sett

from .. import callback_datas as calls


_PREVIEW_VALUES = dict(
    username="Покупатель",
    deal_id="00000000-0000-0000-0000-000000000000",
    deal_item_name="Название товара",
    deal_item_price=100,
)
_PREVIEW_LIMIT = 1500


def _cut_preview(text: str) -> str:
    return text if len(text) <= _PREVIEW_LIMIT else text[:_PREVIEW_LIMIT].rstrip() + "…"


def line_break_hint() -> str:
    """Подсказка, как сделать перенос строки внутри одной строки товара."""
    return (
        "↩️ <b>Перенос строки внутри товара:</b> напишите <code>\\n</code> — "
        "покупатель получит текст с новой строки.\n"
        "Пример: <code>Логин: abc\\nПароль: 123</code> → придёт двумя строками."
    )


def multi_format_hint() -> str:
    return (
        "🧩 <b>Формат выдачи</b> — текст, который получит покупатель. "
        "Вместо <code>{good}</code> подставится строка товара.\n"
        "Можно писать в несколько строк или использовать <code>\\n</code>.\n\n"
        f"{placeholders_help('multi')}"
    )


def multi_format_preview(fmt: str, sample_good: str | None) -> str:
    """HTML-превью того, что получит покупатель (на первой строке товара)."""
    good = sample_good if sample_good else "ПРИМЕР-КЛЮЧА-123"
    rendered = render_multi_delivery(fmt, good, **_PREVIEW_VALUES)
    return f"👀 <b>Так увидит покупатель:</b>\n<blockquote>{escape(_cut_preview(rendered))}</blockquote>"


def static_message_preview(message: str) -> str:
    rendered = render_static_delivery(str(message or "").splitlines(), **_PREVIEW_VALUES)
    return f"👀 <b>Так увидит покупатель:</b>\n<blockquote>{escape(_cut_preview(rendered))}</blockquote>"


def new_multi_format_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ Оставить «{DEFAULT_MULTI_FORMAT}»", callback_data="use_default_multi_format")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="enter_new_auto_delivery")],
    ])


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
        next_item = escape(_cut_preview(items[0])) if items else "❌ Список пуст"
        fmt = delivery.get("format", "")

        lines = [
            "✏️ <b>Редактирование авто-выдачи</b>",
            "",
            "<b>Тип:</b> 📦 <code>МУЛЬТИ</code>",
            f"<b>Статус:</b> {enabled}",
            f"🔑 <b>Ключевые фразы:</b> <code>{keyphrases}</code>",
            f"🧩 <b>Формат выдачи:</b> <code>{escape(_cut_preview(fmt))}</code>",
            "",
            f"📦 <b>Осталось товаров:</b> <code>{len(items)}</code>",
            f"📤 <b>Выдано всего:</b> <code>{issued_total}</code>",
            f"📊 <b>Выдано в текущей партии:</b> <code>{issued_current_batch}</code>",
            f"🔜 <b>Следующий товар:</b> <blockquote>{next_item}</blockquote>",
        ]
        if items:
            lines += ["", multi_format_preview(fmt, items[0])]
        lines += ["", "Выберите параметр для изменения ↓"]
        return "\n".join(lines)

    message_lines = delivery.get("message", [])
    message = "\n".join(escape(line) for line in message_lines) or "❌ Не задано"
    lines = [
        "✏️ <b>Редактирование авто-выдачи</b>",
        "",
        "<b>Тип:</b> 🧾 <code>ОБЫЧНАЯ</code>",
        f"<b>Статус:</b> {enabled}",
        f"🔑 <b>Ключевые фразы:</b> <code>{keyphrases}</code>",
        f"💬 <b>Шаблон сообщения:</b> <blockquote>{message}</blockquote>",
    ]
    if message_lines:
        lines += ["", static_message_preview("\n".join(message_lines))]
    lines += ["", "Выберите параметр для изменения ↓"]
    return "\n".join(lines)


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
        rows.append([InlineKeyboardButton(text="🧩 Формат выдачи", callback_data="enter_auto_delivery_format")])
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
