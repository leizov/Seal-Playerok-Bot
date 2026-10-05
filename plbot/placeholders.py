"""
Единые подстановки для пользовательских текстов (автоответы, команды, заготовки).

Подстановка выполняется регулярным выражением, а не str.format, поэтому:
- неизвестные/недоступные переменные остаются в тексте как есть ({foo});
- одиночные фигурные скобки в тексте не ломают сообщение;
- обращения к атрибутам ({x.__class__}) и индексы не выполняются;
- {{ и }} превращаются в { и } (как в str.format).
"""
import re
from datetime import datetime
from html import escape
from typing import Any
from urllib.parse import quote

DEAL_URL = "https://playerok.com/deal/{}"
CHAT_URL = "https://playerok.com/chats/{}"
PROFILE_URL = "https://playerok.com/profile/{}"

# key -> (описание, где доступно)
PLACEHOLDERS: dict[str, tuple[str, str]] = {
    "username": ("никнейм покупателя", "all"),
    "buyer_username": ("никнейм покупателя (синоним {username})", "all"),
    "date": ("текущая дата, ДД.ММ.ГГГГ", "all"),
    "time": ("текущее время, ЧЧ:ММ", "all"),
    "chat_link": ("ссылка на чат с покупателем", "all"),
    "buyer_link": ("ссылка на профиль покупателя", "all"),
    "deal_id": ("ID сделки", "deal"),
    "deal_link": ("ссылка на сделку", "deal"),
    "deal_item_name": ("название купленного товара", "deal"),
    "item_name": ("название товара (синоним {deal_item_name})", "deal"),
    "deal_item_price": ("цена товара, ₽", "deal"),
}

_PATTERN = re.compile(r"\{\{|\}\}|\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text != "" else None


def build_values(**kwargs) -> dict[str, str]:
    """Собирает значения подстановок; синонимы и ссылки вычисляются автоматически."""
    now = datetime.now()
    values: dict[str, str] = {
        "date": now.strftime("%d.%m.%Y"),
        "time": now.strftime("%H:%M"),
    }
    for key, value in kwargs.items():
        cleaned = _clean(value)
        if cleaned is not None:
            values[key] = cleaned

    username = values.get("username") or values.get("buyer_username")
    if username:
        values.setdefault("username", username)
        values.setdefault("buyer_username", username)
        values.setdefault("buyer_link", PROFILE_URL.format(quote(username, safe="")))

    item_name = values.get("deal_item_name") or values.get("item_name")
    if item_name:
        values.setdefault("deal_item_name", item_name)
        values.setdefault("item_name", item_name)

    if values.get("deal_id"):
        values.setdefault("deal_link", DEAL_URL.format(values["deal_id"]))
    if values.get("chat_id"):
        values.setdefault("chat_link", CHAT_URL.format(values["chat_id"]))
    return values


def format_template(text: str, **kwargs) -> str:
    """Безопасно подставляет значения в текст. Неизвестные переменные не трогает."""
    if not text:
        return text or ""
    values = build_values(**kwargs)

    def _sub(match: re.Match) -> str:
        token = match.group(0)
        if token == "{{":
            return "{"
        if token == "}}":
            return "}"
        return values.get(match.group(1), token)

    return _PATTERN.sub(_sub, str(text))


def placeholders_help(scope: str = "deal") -> str:
    """
    HTML-справка по подстановкам для экранов редактирования.

    :param scope: "deal" — доступны и переменные сделки; "chat" — только общие.
    """
    lines = ["🧩 <b>Подстановки</b> (вставьте в текст как есть):"]
    for key, (desc, where) in PLACEHOLDERS.items():
        if where == "deal" and scope != "deal":
            continue
        lines.append(f"・ <code>{{{key}}}</code> — {escape(desc)}")
    if scope != "deal":
        lines.append("<i>Переменные сделки здесь недоступны и останутся как есть.</i>")
    else:
        lines.append("<i>Если значение недоступно для события, переменная останется как есть.</i>")
    return "\n".join(lines)
