from __future__ import annotations

from typing import Any


AUTO_DELIVERY_KIND_STATIC = "static"
AUTO_DELIVERY_KIND_MULTI = "multi"

# Формат сообщения мультивыдачи: {good} — выдаваемая строка товара.
GOOD_PLACEHOLDER = "{good}"
DEFAULT_MULTI_FORMAT = "Ваш товар: {good}"
# Для старых мультивыдач без поля format: отправляем строку как раньше, без префикса.
LEGACY_MULTI_FORMAT = GOOD_PLACEHOLDER
LINE_BREAK_TOKEN = "\\n"  # два символа: обратный слеш + n


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        result = []
        for item in value:
            text = str(item).strip()
            if text:
                result.append(text)
        return result
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    return []


def parse_delivery_items_text(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def normalize_auto_delivery(entry: Any) -> dict[str, Any]:
    raw = entry if isinstance(entry, dict) else {}

    kind = str(raw.get("kind", AUTO_DELIVERY_KIND_STATIC)).strip().lower()
    if kind not in (AUTO_DELIVERY_KIND_STATIC, AUTO_DELIVERY_KIND_MULTI):
        kind = AUTO_DELIVERY_KIND_STATIC

    keyphrases = _normalize_str_list(raw.get("keyphrases"))
    enabled = bool(raw.get("enabled", True))

    normalized: dict[str, Any] = {
        "kind": kind,
        "enabled": enabled,
        "keyphrases": keyphrases,
    }

    if kind == AUTO_DELIVERY_KIND_MULTI:
        normalized["items"] = _normalize_str_list(raw.get("items"))
        normalized["issued_total"] = max(0, _to_int(raw.get("issued_total"), 0))
        normalized["issued_current_batch"] = max(0, _to_int(raw.get("issued_current_batch"), 0))
        fmt = raw.get("format")
        normalized["format"] = fmt.strip() if isinstance(fmt, str) and fmt.strip() else LEGACY_MULTI_FORMAT
    else:
        normalized["message"] = _normalize_str_list(raw.get("message"))

    return normalized


def normalize_auto_deliveries(auto_deliveries: Any) -> list[dict[str, Any]]:
    if not isinstance(auto_deliveries, list):
        return []
    return [normalize_auto_delivery(entry) for entry in auto_deliveries]


def expand_line_breaks(text: str) -> str:
    """Заменяет символы \\n внутри строки на настоящий перенос строки."""
    return (text or "").replace(LINE_BREAK_TOKEN, "\n")


def validate_multi_format(fmt: str) -> str:
    """Проверяет формат мультивыдачи и возвращает его без лишних пробелов по краям."""
    fmt = (fmt or "").strip()
    if not fmt:
        raise ValueError("❌ Формат не может быть пустым")
    if GOOD_PLACEHOLDER not in fmt:
        raise ValueError(f"❌ В формате обязательно должна быть подстановка <code>{GOOD_PLACEHOLDER}</code> — иначе покупатель не получит товар")
    return fmt


def render_multi_delivery(fmt: str, good: str, **values) -> str:
    """
    Собирает сообщение мультивыдачи: подставляет {good} и общие подстановки,
    затем превращает \\n в переносы строк (и в формате, и в строке товара).
    Если {good} в формате нет (испорченный файл), товар всё равно дописывается в конец.
    """
    from plbot.placeholders import format_template

    fmt = fmt or LEGACY_MULTI_FORMAT
    if GOOD_PLACEHOLDER not in fmt:
        fmt = f"{fmt}\n{GOOD_PLACEHOLDER}"
    # Переносы в формате раскрываем до подстановки, а в товаре — отдельно:
    # значение подстановки повторно не разбирается, поэтому {...} внутри товара не тронется.
    return format_template(expand_line_breaks(fmt), good=expand_line_breaks(good), **values)


def render_static_delivery(message_lines: list[str], **values) -> str:
    from plbot.placeholders import format_template

    text = "\n".join(message_lines or [])
    return format_template(expand_line_breaks(text), **values) if text else ""


def match_auto_delivery_keyphrase(item_name: str, keyphrases: list[str]) -> str | None:
    item_name_lower = (item_name or "").lower()
    for phrase in keyphrases:
        phrase_lower = phrase.lower()
        if phrase_lower and (phrase_lower in item_name_lower or item_name_lower == phrase_lower):
            return phrase
    return None
