"""
Чьи картинки редактируются в меню «🖼 Картинки»: автоответа или авто-выдачи.
Загрузка и сохранение ссылок на картинки, текст для предпросмотра, куда возвращаться.
"""
from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field

from core.auto_deliveries import (
    AUTO_DELIVERY_KIND_MULTI,
    normalize_auto_deliveries,
    render_multi_delivery,
    render_static_delivery,
)
from core.auto_delivery_transfer import delivery_signature, find_delivery_index
from core.chat_images import normalize_refs
from settings import Settings as sett

from .. import callback_datas as calls


logger = logging.getLogger("seal.telegram.chat_images")

OWNER_AUTO_RESPONSE = "ar"
OWNER_AUTO_DELIVERY = "ad"

# Тип автоответа (как в callback-кнопках) → ключ в messages.json и название
AUTO_RESPONSE_PAGES: dict[str, dict[str, str]] = {
    "greeting": {"key": "first_message", "icon": "👋", "title": "Приветственное сообщение"},
    "confirmation_seller": {"key": "deal_sent", "icon": "✅", "title": "Подтверждение (наша сторона)"},
    "confirmation_buyer": {"key": "deal_confirmed", "icon": "✔️", "title": "Подтверждение (покупатель)"},
    "deal_has_problem": {"key": "deal_has_problem", "icon": "⚠️", "title": "Проблема по сделке"},
    "deal_problem_resolved": {"key": "deal_problem_resolved", "icon": "🥰", "title": "Проблема решена"},
    "review": {"key": "new_review_response", "icon": "⭐", "title": "Сообщение при отзыве"},
}

# Значения подстановок для предпросмотра (как в карточке авто-выдачи)
PREVIEW_VALUES = dict(
    username="Покупатель",
    chat_id="00000000-0000-0000-0000-000000000000",
    deal_id="00000000-0000-0000-0000-000000000000",
    deal_item_name="Название товара",
    deal_item_price=100,
)
PREVIEW_SAMPLE_GOOD = "ПРИМЕР-КЛЮЧА-123"


class ImageOwnerError(Exception):
    """Автоответ или авто-выдача не найдены."""


@dataclass
class ImageOwner:
    owner: str                 # OWNER_AUTO_RESPONSE | OWNER_AUTO_DELIVERY
    key: str                   # тип автоответа или индекс авто-выдачи (строкой)
    header: str                # HTML: «где мы» для заголовка экрана
    name: str                  # HTML: «автоответ «…»» / «авто-выдача …» (именительный падеж)
    name_gen: str              # родительный: «из автоответа «…»»
    name_acc: str              # винительный: «увидит автоответ «…»»
    back_cb: str               # куда ведёт «⬅️ Назад» из меню картинок
    back_hint: str             # «вернуться к …»
    when_sent: str             # когда картинки уходят покупателю
    refs: list[str] = field(default_factory=list)
    preview_text: str = ""     # текст сообщения с примерами подстановок
    index: int | None = None   # индекс авто-выдачи


def auto_response_message_key(message_type: str) -> str | None:
    page = AUTO_RESPONSE_PAGES.get(message_type)
    return page["key"] if page else None


def _watermarked(text: str) -> str:
    config = sett.get("config") or {}
    watermark = config.get("playerok", {}).get("watermark", {})
    if text and watermark.get("enabled") and watermark.get("value"):
        return f"{watermark['value']}\n\n{text}"
    return text


def _auto_response_owner(message_type: str) -> ImageOwner:
    from plbot.placeholders import format_template

    page = AUTO_RESPONSE_PAGES.get(message_type)
    if page is None:
        raise ImageOwnerError("❌ Неизвестный тип автоответа")
    messages = sett.get("messages") or {}
    entry = messages.get(page["key"]) or {}
    lines = [str(line) for line in entry.get("text", []) or []]
    text = "\n".join(lines) if any(line.strip() for line in lines) else ""
    preview = _watermarked(format_template(text, **PREVIEW_VALUES)) if text else ""
    return ImageOwner(
        owner=OWNER_AUTO_RESPONSE,
        key=message_type,
        header=f"🤖 <b>Автоответ</b> → {page['icon']} <b>{page['title']}</b>",
        name=f"автоответ «<b>{page['title']}</b>»",
        name_gen=f"автоответа «<b>{page['title']}</b>»",
        name_acc=f"автоответ «<b>{page['title']}</b>»",
        back_cb=calls.MessagesNavigation(to=message_type).pack(),
        back_hint="вернуться к настройке сообщения",
        when_sent="Картинки уходят покупателю вместе с текстом автоответа — одним сообщением.",
        refs=normalize_refs(entry.get("images")),
        preview_text=preview,
    )


def _resolve_delivery_index(deliveries: list[dict], key: str, signature: list[str] | None) -> int:
    try:
        hint = int(key)
    except (TypeError, ValueError):
        hint = None
    if signature:
        idx = find_delivery_index(deliveries, signature, hint)
    else:
        idx = hint if hint is not None and 0 <= hint < len(deliveries) else None
    if idx is None:
        raise ImageOwnerError("❌ Авто-выдача не найдена — возможно, её удалили или изменили ключевые фразы")
    return idx


def _auto_delivery_owner(key: str, signature: list[str] | None) -> ImageOwner:
    deliveries = normalize_auto_deliveries(sett.get("auto_deliveries") or [])
    idx = _resolve_delivery_index(deliveries, key, signature)
    delivery = deliveries[idx]
    phrases = ", ".join(delivery.get("keyphrases", [])) or "без ключевых фраз"
    if len(phrases) > 40:
        phrases = phrases[:37] + "..."
    from html import escape

    if delivery.get("kind") == AUTO_DELIVERY_KIND_MULTI:
        items = delivery.get("items", [])
        preview = render_multi_delivery(
            delivery.get("format", ""), items[0] if items else PREVIEW_SAMPLE_GOOD, **PREVIEW_VALUES
        )
        kind_name = "📦 МУЛЬТИ"
        when_sent = "Картинки уходят вместе с каждым выданным товаром — одним сообщением с ним."
    else:
        preview = render_static_delivery(delivery.get("message", []), **PREVIEW_VALUES)
        kind_name = "🧾 ОБЫЧНАЯ"
        when_sent = "Картинки уходят покупателю вместе с сообщением авто-выдачи — одним сообщением."
    return ImageOwner(
        owner=OWNER_AUTO_DELIVERY,
        key=str(idx),
        header=f"🚀 <b>Авто-выдача</b> → {kind_name} <code>{escape(phrases)}</code>",
        name=f"авто-выдача <code>{escape(phrases)}</code>",
        name_gen=f"авто-выдачи <code>{escape(phrases)}</code>",
        name_acc=f"авто-выдачу <code>{escape(phrases)}</code>",
        back_cb=calls.AutoDeliveryPage(index=idx).pack(),
        back_hint="вернуться в карточку авто-выдачи",
        when_sent=when_sent,
        refs=normalize_refs(delivery.get("images")),
        preview_text=_watermarked(preview),
        index=idx,
    )


def resolve_owner(owner: str, key: str, state_data: dict | None = None, fresh: bool = False) -> ImageOwner:
    """
    Находит автоответ или авто-выдачу.
    Для авто-выдачи по отпечатку из state (тип + ключевые фразы), чтобы индекс не «уехал»
    при изменении списка. fresh=True — открыть по индексу из кнопки карточки (отпечаток сохраняется заново).
    """
    if owner == OWNER_AUTO_RESPONSE:
        return _auto_response_owner(key)
    if owner == OWNER_AUTO_DELIVERY:
        signature = None if fresh else (state_data or {}).get("cimg_ad_sig")
        return _auto_delivery_owner(key, signature)
    raise ImageOwnerError("❌ Неизвестный раздел")


def owner_signature(owner: ImageOwner) -> list[str] | None:
    if owner.owner != OWNER_AUTO_DELIVERY or owner.index is None:
        return None
    deliveries = normalize_auto_deliveries(sett.get("auto_deliveries") or [])
    if 0 <= owner.index < len(deliveries):
        return delivery_signature(deliveries[owner.index])
    return None


def save_owner_refs(owner: ImageOwner, refs: list[str]) -> list[str]:
    """Сохраняет список картинок и обновляет память Playerok-бота. Возвращает сохранённый список."""
    refs = normalize_refs(refs)
    if owner.owner == OWNER_AUTO_RESPONSE:
        message_key = auto_response_message_key(owner.key)
        if message_key is None:
            raise ImageOwnerError("❌ Неизвестный тип автоответа")
        messages = sett.get("messages") or {}
        entry = messages.setdefault(message_key, {"enabled": False, "text": []})
        if refs:
            entry["images"] = refs
        else:
            entry.pop("images", None)
        sett.set("messages", messages)
        saved = normalize_refs((sett.get("messages") or {}).get(message_key, {}).get("images"))
        if saved != refs:
            raise RuntimeError("Не удалось сохранить картинки на диск (подробности в логе)")
        try:
            from plbot.playerokbot import get_playerok_bot

            playerok_bot = get_playerok_bot()
            if playerok_bot is not None:
                playerok_bot.messages = copy.deepcopy(sett.get("messages"))
        except Exception as e:
            logger.warning("Не удалось обновить автоответы в памяти Playerok-бота: %s", e)
        owner.refs = refs
        return refs

    if owner.owner == OWNER_AUTO_DELIVERY:
        from ..callback_handlers.auto_delivery_transfer import save_deliveries

        deliveries = normalize_auto_deliveries(sett.get("auto_deliveries") or [])
        signature = owner_signature(owner)
        idx = owner.index
        if signature is None or idx is None or not (0 <= idx < len(deliveries)):
            raise ImageOwnerError("❌ Авто-выдача не найдена — возможно, её удалили")
        if refs:
            deliveries[idx]["images"] = refs
        else:
            deliveries[idx].pop("images", None)
        save_deliveries(deliveries)
        owner.refs = refs
        return refs

    raise ImageOwnerError("❌ Неизвестный раздел")
