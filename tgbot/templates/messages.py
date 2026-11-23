import textwrap
from html import escape

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from core.chat_images import MAX_IMAGES, normalize_refs
from settings import Settings as sett
from .. import callback_datas as calls


def messages_text():
    """Текст главной страницы автоответов"""
    txt = textwrap.dedent("""
        🤖 <b>Автоответ</b>

        В этом разделе вы можете настроить автоматические ответы бота на различные события.

        Выберите тип сообщения для настройки ↓
    """)
    return txt


def messages_kb():
    """Клавиатура главной страницы автоответов"""
    rows = [
        [InlineKeyboardButton(text="👋 Приветственное сообщение", callback_data=calls.MessagesNavigation(to="greeting").pack())],
        [InlineKeyboardButton(text="✅ Подтверждение (наша сторона)", callback_data=calls.MessagesNavigation(to="confirmation_seller").pack())],
        [InlineKeyboardButton(text="✔️ Подтверждение (покупатель)", callback_data=calls.MessagesNavigation(to="confirmation_buyer").pack())],
        [InlineKeyboardButton(text="⚠️ Проблема по сделке", callback_data=calls.MessagesNavigation(to="deal_has_problem").pack())],
        [InlineKeyboardButton(text="🥰 Проблема решена", callback_data=calls.MessagesNavigation(to="deal_problem_resolved").pack())],
        [InlineKeyboardButton(text="⭐ Сообщение при отзыве", callback_data=calls.MessagesNavigation(to="review").pack())],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.MenuPagination(page=0).pack())]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


# ── Страницы отдельных автоответов ──
# Тип автоответа (как в callback-кнопках) → ключ в messages.json, заголовок и описание
_AUTO_RESPONSE_PAGES = {
    "greeting": (
        "first_message",
        "👋 <b>Приветственное сообщение</b>",
        "Это сообщение отправляется покупателю при новой сделке.",
    ),
    "confirmation_seller": (
        "deal_sent",
        "✅ <b>Подтверждение сделки (наша сторона)</b>",
        "Это сообщение отправляется покупателю, когда вы подтверждаете отправку товара.",
    ),
    "confirmation_buyer": (
        "deal_confirmed",
        "✔️ <b>Подтверждение сделки (покупатель)</b>",
        "Это сообщение отправляется покупателю после того, как он подтвердит получение товара.",
    ),
    "deal_has_problem": (
        "deal_has_problem",
        "⚠️ <b>Сообщение при проблеме в сделке</b>",
        "Это сообщение отправляется покупателю, когда в сделке открывается проблема.",
    ),
    "deal_problem_resolved": (
        "deal_problem_resolved",
        "🥰 <b>Сообщение после решения проблемы</b>",
        "Это сообщение отправляется покупателю, когда проблема в сделке решена.",
    ),
    "review": (
        "new_review_response",
        "⭐ <b>Сообщение при получении отзыва</b>",
        "Это сообщение отправляется покупателю после того, как он оставит отзыв.",
    ),
}


def _auto_response_data(message_type: str) -> tuple[dict, str, list[str]]:
    message_key = _AUTO_RESPONSE_PAGES[message_type][0]
    msg_data = (sett.get("messages") or {}).get(message_key, {}) or {}
    text_lines = [str(line) for line in msg_data.get("text", []) or []]
    current_text = "\n".join(text_lines) if any(line.strip() for line in text_lines) else ""
    return msg_data, current_text, normalize_refs(msg_data.get("images"))


def auto_response_page_text(message_type: str) -> str:
    """Текст страницы настройки автоответа: статус, текст, картинки и пояснения к кнопкам."""
    _key, title, description = _AUTO_RESPONSE_PAGES[message_type]
    msg_data, current_text, images = _auto_response_data(message_type)
    enabled = msg_data.get("enabled", False)
    status = "🟢 Включено" if enabled else "🔴 Выключено"

    lines = [title, "", description, "", f"<b>Статус:</b> {status}", "", "<b>Текущее сообщение:</b>"]
    if current_text:
        lines.append(f"<code>{escape(current_text)}</code>")
    elif images:
        lines.append("<i>Без текста — уйдут только картинки</i>")
    else:
        lines.append("<i>Текст не задан</i>")
    lines.append(f"🖼 <b>Картинки:</b> {len(images)} из {MAX_IMAGES}")
    if enabled and not current_text and not images:
        lines += ["", "⚠️ Нет ни текста, ни картинок — сообщение не отправится"]

    lines += ["", "✏️ <b>Изменить текст</b> — задать текст сообщения"]
    if current_text:
        lines.append("🧹 <b>Удалить текст</b> — оставить сообщение без текста (только картинки)")
    lines.append(f"🖼 <b>Картинки</b> — прикрепить до {MAX_IMAGES} картинок, они уйдут одним сообщением с текстом")
    lines += ["", "Используйте кнопки ниже для управления ↓"]
    return "\n".join(lines)


def auto_response_page_kb(message_type: str) -> InlineKeyboardMarkup:
    """Клавиатура страницы настройки автоответа."""
    msg_data, current_text, images = _auto_response_data(message_type)
    toggle_text = "🟢 Включено" if msg_data.get("enabled", False) else "🔴 Выключено"

    rows = [
        [InlineKeyboardButton(text=toggle_text, callback_data=calls.AutoResponseToggle(message_type=message_type).pack())],
        [InlineKeyboardButton(text="✏️ Изменить текст", callback_data=calls.AutoResponseEdit(message_type=message_type).pack())],
    ]
    if current_text:
        rows.append([InlineKeyboardButton(text="🧹 Удалить текст", callback_data=calls.AutoResponseClearText(message_type=message_type).pack())])
    rows.append([InlineKeyboardButton(
        text=f"🖼 Картинки ({len(images)}/{MAX_IMAGES})",
        callback_data=calls.ChatImagesAction(owner="ar", key=message_type, action="open").pack(),
    )])
    rows.append([InlineKeyboardButton(text="⬅️ Назад к автоответам", callback_data=calls.MessagesNavigation(to="main").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def auto_response_clear_text_text(message_type: str) -> str:
    _key, title, _description = _AUTO_RESPONSE_PAGES[message_type]
    _msg_data, current_text, images = _auto_response_data(message_type)
    lines = [
        title,
        "",
        "🧹 Удалить текст этого сообщения?",
        f"<code>{escape(current_text)}</code>" if current_text else "<i>Текст не задан</i>",
        "",
    ]
    if images:
        lines.append(f"Покупатель будет получать только картинки ({len(images)} шт.).")
    else:
        lines.append("⚠️ Картинок нет — пока вы не добавите текст или картинки, сообщение не будет отправляться.")
    lines += [
        "",
        "✅ <b>Да, удалить текст</b> — сообщение останется без текста",
        "❌ <b>Отмена</b> — вернуться к настройке сообщения",
    ]
    return "\n".join(lines)


def auto_response_clear_text_kb(message_type: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да, удалить текст", callback_data=calls.AutoResponseClearText(message_type=message_type, confirm=1).pack()),
        InlineKeyboardButton(text="❌ Отмена", callback_data=calls.MessagesNavigation(to=message_type).pack()),
    ]])


def messages_greeting_text():
    """Текст страницы настройки приветственного сообщения"""
    return auto_response_page_text("greeting")


def messages_greeting_kb():
    """Клавиатура страницы настройки приветственного сообщения"""
    return auto_response_page_kb("greeting")


def messages_confirmation_seller_text():
    """Текст страницы настройки сообщения при подтверждении с нашей стороны"""
    return auto_response_page_text("confirmation_seller")


def messages_confirmation_seller_kb():
    """Клавиатура страницы настройки сообщения при подтверждении с нашей стороны"""
    return auto_response_page_kb("confirmation_seller")


def messages_confirmation_buyer_text():
    """Текст страницы настройки сообщения при подтверждении со стороны покупателя"""
    return auto_response_page_text("confirmation_buyer")


def messages_confirmation_buyer_kb():
    """Клавиатура страницы настройки сообщения при подтверждении со стороны покупателя"""
    return auto_response_page_kb("confirmation_buyer")


def messages_deal_has_problem_text():
    """Текст страницы настройки сообщения при проблеме в сделке"""
    return auto_response_page_text("deal_has_problem")


def messages_deal_has_problem_kb():
    """Клавиатура страницы настройки сообщения при проблеме в сделке"""
    return auto_response_page_kb("deal_has_problem")


def messages_deal_problem_resolved_text():
    """Текст страницы настройки сообщения после решения проблемы в сделке"""
    return auto_response_page_text("deal_problem_resolved")


def messages_deal_problem_resolved_kb():
    """Клавиатура страницы настройки сообщения после решения проблемы в сделке"""
    return auto_response_page_kb("deal_problem_resolved")


def messages_review_text():
    """Текст страницы настройки сообщения при получении отзыва"""
    return auto_response_page_text("review")


def messages_review_kb():
    """Клавиатура страницы настройки сообщения при получении отзыва"""
    return auto_response_page_kb("review")
