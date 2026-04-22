import html

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .. import callback_datas as calls


def _safe(value) -> str:
    return html.escape(str(value))


def _short(value: str, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def _chat_button_text(chat: dict) -> str:
    special_emoji = str(chat.get("special_emoji") or "").strip()
    status_emoji = str(chat.get("status_emoji") or "").strip()
    display_name = _short(chat.get("display_name") or "Без имени", 22)
    unread_emoji = " 🔷" if int(chat.get("unread_messages_counter") or 0) > 0 else ""

    parts = []
    if special_emoji:
        parts.append(special_emoji)
    if status_emoji:
        parts.append(status_emoji)
    parts.append(display_name)
    return " ".join(parts) + unread_emoji


def chats_menu_text(page: int, total_pages: int, total_loaded: int, total_found: int) -> str:
    lines = [
        "<b>💬 Чаты аккаунта</b>",
        "",
        "ℹ️ <i>Отображаются только последние 70 чатов.</i>",
        "",
        f"📊 Найдено: <b>{total_found}</b> из <b>{total_loaded}</b> загруженных",
        f"📄 Страница: <b>{page + 1}/{max(total_pages, 1)}</b>",
        "",
        "<b>🏷 Легенда статусов</b>",
        "⚪ Оффлайн · 🟢 Онлайн · ⛔ Забанен · 🔷 Непрочитанные",
    ]

    if total_found == 0:
        lines.extend(["", "❌ Чаты не найдены."])
    else:
        lines.extend(["", "👇 Выберите чат кнопкой ниже."])

    return "\n".join(lines)


def chats_menu_kb(page_chats: list[dict], page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    for idx in range(0, len(page_chats), 2):
        row: list[InlineKeyboardButton] = []
        for chat in page_chats[idx: idx + 2]:
            row.append(
                InlineKeyboardButton(
                    text=_chat_button_text(chat),
                    callback_data=calls.ChatHistory(chat_id=str(chat.get("id"))).pack(),
                )
            )
        rows.append(row)

    if total_pages > 1:
        rows.append(
            [
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=calls.ChatsAction(action="page", value=str(max(0, page - 1))).pack(),
                ),
                InlineKeyboardButton(
                    text=f"📄 {page + 1}/{total_pages}",
                    callback_data=calls.ChatsAction(action="noop").pack(),
                ),
                InlineKeyboardButton(
                    text="➡️",
                    callback_data=calls.ChatsAction(
                        action="page",
                        value=str(min(total_pages - 1, page + 1)),
                    ).pack(),
                ),
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="🔄 Обновить",
                callback_data=calls.ChatsAction(action="refresh").pack(),
            ),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
