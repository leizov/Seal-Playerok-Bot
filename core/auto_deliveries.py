from __future__ import annotations

from typing import Any


AUTO_DELIVERY_KIND_STATIC = "static"
AUTO_DELIVERY_KIND_MULTI = "multi"


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
    else:
        normalized["message"] = _normalize_str_list(raw.get("message"))

    return normalized


def normalize_auto_deliveries(auto_deliveries: Any) -> list[dict[str, Any]]:
    if not isinstance(auto_deliveries, list):
        return []
    return [normalize_auto_delivery(entry) for entry in auto_deliveries]


def match_auto_delivery_keyphrase(item_name: str, keyphrases: list[str]) -> str | None:
    item_name_lower = (item_name or "").lower()
    for phrase in keyphrases:
        phrase_lower = phrase.lower()
        if phrase_lower and (phrase_lower in item_name_lower or item_name_lower == phrase_lower):
            return phrase
    return None
