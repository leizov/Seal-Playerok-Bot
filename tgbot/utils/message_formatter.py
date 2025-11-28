"""
Утилиты для форматирования сообщений
"""


from playerokapi.types import ItemDeal


def format_system_message(msg_text: str, deal: ItemDeal=None) -> tuple[str, str] | tuple[None, None]:
    """
    Форматирует системное сообщение в читаемый вид.
    
    :param msg_text: Текст сообщения
    :param deal: Объект сделки (опционально)
    :param item: Объект предмета (опционально)
    :return: Кортеж (emoji, formatted_text) или (None, None) если сообщение не системное
    """
    system_messages = {
        "{{ITEM_PAID}}": (
            "💰",
            "<b>🔔 Товар оплачен!</b>"
        ),
        "{{ITEM_SENT}}": (
            "📦",
            "<b>📤 Товар отправлен</b>"
        ),
        "{{DEAL_CONFIRMED}}": (
            "✅",
            "<b>🎉 Сделка подтверждена!</b>"
        ),
        "{{DEAL_ROLLED_BACK}}": (
            "↩️",
            "<b>⚠️ Сделка отменена</b>"
        ),
        "{{DEAL_HAS_PROBLEM}}": (
            "⚠️",
            "<b>⚠️ Проблема со сделкой!</b>"
        ),
        "{{DEAL_PROBLEM_RESOLVED}}": (
            "✅",
            "<b>✅ Проблема решена</b>"
        ),
    }
    
    if msg_text in system_messages:
        emoji, text = system_messages[msg_text]
        
        # Добавляем информацию о товаре из deal.item
        actual_item = deal.item if deal else None
            
        if actual_item:
            item_name = getattr(actual_item, 'name', None)
            item_price = getattr(actual_item, 'price', None)
            
            if item_name:
                text += f"\n📦 <b>Товар:</b> {item_name}"
            if item_price:
                text += f"\n💵 <b>Цена:</b> {item_price}₽"
        
        return emoji, text
    
    return None, None


def get_system_message_description(msg_text: str) -> str | None:
    """
    Возвращает краткое описание системного сообщения без HTML разметки.
    
    :param msg_text: Текст сообщения
    :return: Краткое описание или None если сообщение не системное
    """
    descriptions = {
        "{{ITEM_PAID}}": "Товар оплачен",
        "{{ITEM_SENT}}": "Товар отправлен",
        "{{DEAL_CONFIRMED}}": "Сделка подтверждена",
        "{{DEAL_ROLLED_BACK}}": "Сделка отменена",
        "{{DEAL_HAS_PROBLEM}}": "Проблема со сделкой",
        "{{DEAL_PROBLEM_RESOLVED}}": "Проблема решена",
    }
    
    return descriptions.get(msg_text)
