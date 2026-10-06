from datetime import datetime
from html import escape

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from core.auto_deliveries import AUTO_DELIVERY_KIND_MULTI
from plbot.delivery_history import STATUS_FAILED, STATUS_OUT_OF_STOCK, STATUS_SENT

from .. import callback_datas as calls

DELIVERY_HISTORY_PAGE_SIZE = 10
DEAL_URL = "https://playerok.com/deal/{}"
_TEXT_LIMIT = 1500

_STATUS_ICONS = {STATUS_SENT: "✅", STATUS_FAILED: "❌", STATUS_OUT_OF_STOCK: "⚠️"}
_STATUS_NAMES = {
    STATUS_SENT: "✅ Отправлено",
    STATUS_FAILED: "❌ Не отправлено (ошибка Playerok)",
    STATUS_OUT_OF_STOCK: "⚠️ Товар закончился",
}


def _short(value, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: max(0, limit - 1)].rstrip() + "…"


def _cut(value, limit: int = _TEXT_LIMIT) -> str:
    text = str(value or "")
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def _fmt_time(value, short: bool = False) -> str:
    try:
        dt = datetime.fromisoformat(str(value))
        return dt.strftime("%d.%m %H:%M" if short else "%d.%m.%Y %H:%M:%S")
    except Exception:
        return str(value or "—")


def history_page_count(total: int) -> int:
    return max(1, (total + DELIVERY_HISTORY_PAGE_SIZE - 1) // DELIVERY_HISTORY_PAGE_SIZE)


def delivery_history_text(records: list[dict], page: int) -> str:
    lines = ["⚙️ <b>Настройки</b> → 🚀 <b>Авто-выдача</b> → 📜 <b>История выдач</b>", ""]
    if not records:
        lines.append("Выдач пока не было.")
        return "\n".join(lines)

    sent = sum(1 for r in records if r.get("status") == STATUS_SENT)
    failed = sum(1 for r in records if r.get("status") == STATUS_FAILED)
    empty = sum(1 for r in records if r.get("status") == STATUS_OUT_OF_STOCK)
    lines += [
        f"Всего записей: <b>{len(records)}</b>",
        f"┣ ✅ Отправлено: <b>{sent}</b>",
        f"┣ ❌ Ошибка отправки: <b>{failed}</b>",
        f"┗ ⚠️ Товар закончился: <b>{empty}</b>",
        "",
        f"📄 Страница: <b>{page + 1}/{history_page_count(len(records))}</b>",
        "👇 Нажмите на запись, чтобы увидеть, что именно получил покупатель.",
    ]
    if failed or empty:
        lines += ["", "<i>❌ и ⚠️ — покупатель не получил товар, проверьте эти сделки вручную.</i>"]
    return "\n".join(lines)


def delivery_history_kb(records: list[dict], page: int) -> InlineKeyboardMarkup:
    total_pages = history_page_count(len(records))
    page = max(0, min(page, total_pages - 1))
    start = page * DELIVERY_HISTORY_PAGE_SIZE
    rows: list[list[InlineKeyboardButton]] = []

    for record in records[start:start + DELIVERY_HISTORY_PAGE_SIZE]:
        icon = _STATUS_ICONS.get(record.get("status"), "•")
        text = (
            f"{icon} {_fmt_time(record.get('time'), short=True)} | "
            f"{_short(record.get('buyer') or '?', 14)} | {_short(record.get('item_name') or '—', 18)}"
        )
        rows.append([
            InlineKeyboardButton(
                text=text,
                callback_data=calls.DeliveryHistoryRecord(rec_id=int(record.get("id", 0) or 0), page=page).pack(),
            )
        ])

    if total_pages > 1:
        rows.append([
            InlineKeyboardButton(text="⬅️", callback_data=calls.DeliveryHistoryPagination(page=max(0, page - 1)).pack()),
            InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data=calls.DeliveryHistoryPagination(page=page).pack()),
            InlineKeyboardButton(text="➡️", callback_data=calls.DeliveryHistoryPagination(page=min(total_pages - 1, page + 1)).pack()),
        ])

    rows.append([InlineKeyboardButton(text="⬅️ К авто-выдачам", callback_data=calls.AutoDeliveriesPagination(page=0).pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def delivery_record_text(record: dict | None) -> str:
    if not record:
        return "📜 <b>Запись истории выдач</b>\n\n❌ Запись не найдена (возможно, история была очищена)."

    kind = "📦 Мультивыдача" if record.get("kind") == AUTO_DELIVERY_KIND_MULTI else "🧾 Обычная авто-выдача"
    lines = [
        f"📜 <b>Запись истории выдач #{record.get('id')}</b>",
        "",
        f"<b>Статус:</b> {_STATUS_NAMES.get(record.get('status'), escape(str(record.get('status'))))}",
        f"<b>Тип:</b> {kind}",
        f"<b>Время:</b> {_fmt_time(record.get('time'))}",
        f"👤 <b>Покупатель:</b> {escape(str(record.get('buyer') or '—'))}",
        f"📦 <b>Товар:</b> {escape(str(record.get('item_name') or '—'))}",
    ]
    if record.get("item_price") is not None:
        lines.append(f"💰 <b>Сумма:</b> {escape(str(record.get('item_price')))}₽")
    if record.get("keyphrase"):
        lines.append(f"🧩 <b>Ключевая фраза:</b> {escape(str(record.get('keyphrase')))}")
    if record.get("deal_id"):
        url = escape(DEAL_URL.format(record["deal_id"]))
        lines.append(f'🧾 <b>Сделка:</b> <a href="{url}">#{escape(str(record["deal_id"])[:8])}</a>')
    if record.get("remaining") is not None:
        lines.append(f"📦 <b>Осталось после выдачи:</b> {record.get('remaining')}")
    if record.get("good") is not None:
        lines += ["", "🔑 <b>Выданная строка:</b>", f"<tg-spoiler>{escape(_cut(record.get('good')))}</tg-spoiler>"]
    if record.get("message"):
        lines += ["", "💬 <b>Сообщение покупателю:</b>", f"<blockquote>{escape(_cut(record.get('message')))}</blockquote>"]
    if record.get("status") == STATUS_FAILED:
        lines += ["", "<i>Сообщение не дошло до покупателя. Строка уже списана со склада — отправьте её вручную.</i>"]
    return "\n".join(lines)


def delivery_record_kb(record: dict | None, page: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if record and record.get("buyer"):
        rows.append([
            InlineKeyboardButton(
                text="💬 Написать покупателю",
                callback_data=calls.RememberUsername(name=str(record["buyer"]), do="send_mess").pack(),
            )
        ])
    if record and record.get("deal_id"):
        rows.append([InlineKeyboardButton(text="🔗 Открыть сделку", url=DEAL_URL.format(record["deal_id"]))])
    rows.append([InlineKeyboardButton(text="⬅️ К истории", callback_data=calls.DeliveryHistoryPagination(page=page).pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)
