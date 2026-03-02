import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

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
        [InlineKeyboardButton(text="⭐ Сообщение при отзыве", callback_data=calls.MessagesNavigation(to="review").pack())],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.MenuPagination(page=0).pack())]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def messages_greeting_text():
    """Текст страницы настройки приветственного сообщения"""
    messages = sett.get("messages")
    msg_data = messages.get("first_message", {})
    
    enabled = msg_data.get("enabled", False)
    status = "🟢 Включено" if enabled else "🔴 Выключено"
    cooldown_days = msg_data.get("cooldown_days", 7)
    text_lines = msg_data.get("text", [])
    current_text = "\n".join(text_lines) if text_lines else "<i>Текст не задан</i>"
    
    txt = textwrap.dedent(f"""
        👋 <b>Приветственное сообщение</b>
        
        Отправляется при первом новой сделке
        <b>Статус:</b> {status}
        
        <b>Сообщение:</b>
        <code>{current_text}</code>
    """)
    return txt


def messages_greeting_kb():
    """Клавиатура страницы настройки приветственного сообщения"""
    messages = sett.get("messages")
    msg_data = messages.get("first_message", {})
    enabled = msg_data.get("enabled", False)
    
    toggle_text = "🔴 Выключить" if enabled else "🟢 Включить"
    
    rows = [
        [InlineKeyboardButton(text=toggle_text, callback_data=calls.AutoResponseToggle(message_type="greeting").pack())],
        [InlineKeyboardButton(text="✏️ Изменить текст", callback_data=calls.AutoResponseEdit(message_type="greeting").pack())],
        # [InlineKeyboardButton(text="⏱ Изменить интервал", callback_data=calls.GreetingCooldownEdit().pack())],
        [InlineKeyboardButton(text="⬅️ Назад к автоответам", callback_data=calls.MessagesNavigation(to="main").pack())]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def messages_confirmation_seller_text():
    """Текст страницы настройки сообщения при подтверждении с нашей стороны"""
    messages = sett.get("messages")
    msg_data = messages.get("deal_sent", {})
    
    enabled = msg_data.get("enabled", False)
    status = "🟢 Включено" if enabled else "🔴 Выключено"
    text_lines = msg_data.get("text", [])
    current_text = "\n".join(text_lines) if text_lines else "<i>Текст не задан</i>"
    
    txt = textwrap.dedent(f"""
        ✅ <b>Подтверждение сделки (наша сторона)</b>
        
        Это сообщение отправляется покупателю, когда вы подтверждаете отправку товара.
        
        <b>Статус:</b> {status}
        
        <b>Текущее сообщение:</b>
        <code>{current_text}</code>
        
        Используйте кнопки ниже для управления ↓
    """)
    return txt


def messages_confirmation_seller_kb():
    """Клавиатура страницы настройки сообщения при подтверждении с нашей стороны"""
    messages = sett.get("messages")
    msg_data = messages.get("deal_sent", {})
    enabled = msg_data.get("enabled", False)
    
    toggle_text = "🔴 Выключить" if enabled else "🟢 Включить"
    
    rows = [
        [InlineKeyboardButton(text=toggle_text, callback_data=calls.AutoResponseToggle(message_type="confirmation_seller").pack())],
        [InlineKeyboardButton(text="✏️ Изменить текст", callback_data=calls.AutoResponseEdit(message_type="confirmation_seller").pack())],
        [InlineKeyboardButton(text="⬅️ Назад к автоответам", callback_data=calls.MessagesNavigation(to="main").pack())]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def messages_confirmation_buyer_text():
    """Текст страницы настройки сообщения при подтверждении со стороны покупателя"""
    messages = sett.get("messages")
    msg_data = messages.get("deal_confirmed", {})
    
    enabled = msg_data.get("enabled", False)
    status = "🟢 Включено" if enabled else "🔴 Выключено"
    text_lines = msg_data.get("text", [])
    current_text = "\n".join(text_lines) if text_lines else "<i>Текст не задан</i>"
    
    txt = textwrap.dedent(f"""
        ✔️ <b>Подтверждение сделки (покупатель)</b>
        
        Это сообщение отправляется покупателю после того, как он подтвердит получение товара.
        
        <b>Статус:</b> {status}
        
        <b>Текущее сообщение:</b>
        <code>{current_text}</code>
        
        Используйте кнопки ниже для управления ↓
    """)
    return txt


def messages_confirmation_buyer_kb():
    """Клавиатура страницы настройки сообщения при подтверждении со стороны покупателя"""
    messages = sett.get("messages")
    msg_data = messages.get("deal_confirmed", {})
    enabled = msg_data.get("enabled", False)
    
    toggle_text = "🔴 Выключить" if enabled else "🟢 Включить"
    
    rows = [
        [InlineKeyboardButton(text=toggle_text, callback_data=calls.AutoResponseToggle(message_type="confirmation_buyer").pack())],
        [InlineKeyboardButton(text="✏️ Изменить текст", callback_data=calls.AutoResponseEdit(message_type="confirmation_buyer").pack())],
        [InlineKeyboardButton(text="⬅️ Назад к автоответам", callback_data=calls.MessagesNavigation(to="main").pack())]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def messages_review_text():
    """Текст страницы настройки сообщения при получении отзыва"""
    messages = sett.get("messages")
    msg_data = messages.get("new_review_response", {})
    
    enabled = msg_data.get("enabled", False)
    status = "🟢 Включено" if enabled else "🔴 Выключено"
    text_lines = msg_data.get("text", [])
    current_text = "\n".join(text_lines) if text_lines else "<i>Текст не задан</i>"
    
    txt = textwrap.dedent(f"""
        ⭐ <b>Сообщение при получении отзыва</b>
        
        Это сообщение отправляется покупателю после того, как он оставит отзыв.
        !!! СУПЕР ВАЖНО: для того чтобы эти сообщения отправлялись, должна быть включена опция Мониторинг отзывов !!!
        
        <b>Статус:</b> {status}
        
        <b>Текущее сообщение:</b>
        <code>{current_text}</code>
        
        Используйте кнопки ниже для управления ↓
    """)
    return txt


def messages_review_kb():
    """Клавиатура страницы настройки сообщения при получении отзыва"""
    messages = sett.get("messages")
    msg_data = messages.get("new_review_response", {})
    enabled = msg_data.get("enabled", False)
    
    toggle_text = "🔴 Выключить" if enabled else "🟢 Включить"
    
    rows = [
        [InlineKeyboardButton(text=toggle_text, callback_data=calls.AutoResponseToggle(message_type="review").pack())],
        [InlineKeyboardButton(text="✏️ Изменить текст", callback_data=calls.AutoResponseEdit(message_type="review").pack())],
        [InlineKeyboardButton(text="⬅️ Назад к автоответам", callback_data=calls.MessagesNavigation(to="main").pack())]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb
