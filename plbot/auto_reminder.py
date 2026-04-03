from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from logging import getLogger
from typing import TYPE_CHECKING, Callable

from playerokapi.enums import ItemDealStatuses

import paths

if TYPE_CHECKING:
    from playerokapi.account import Account
    from playerokapi.types import ItemDeal


logger = getLogger("seal.auto_reminder")

DEALS_FILE = paths.AUTO_REMINDER_DEALS_FILE
CHECK_INTERVAL_SECONDS = 300

DEFAULT_MESSAGE_TEXT = "⏰ Пожалуйста, подтвердите сделку, вы уже получили свой товар!\n🔗 {deal_link}"
LEGACY_DEFAULT_MESSAGE_TEXT = (
    "⏰ Напоминание: пожалуйста, подтвердите сделку, если товар уже получен.\n"
    "🔗 {deal_link}"
)


class _SafeFormat(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def _to_int(value, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _to_float(value, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _parse_datetime(value) -> datetime | None:
    if value is None:
        return None
    try:
        dt = datetime.fromisoformat(str(value))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _normalize_message_text(value) -> str:
    text = str(value or "").strip()
    if not text or text == LEGACY_DEFAULT_MESSAGE_TEXT:
        return DEFAULT_MESSAGE_TEXT
    return text


def _extract_buyer_name(deal, fallback: str = "") -> str:
    users = (
        getattr(getattr(deal, "user", None), "username", None),
        getattr(getattr(deal, "buyer", None), "username", None),
        getattr(getattr(deal, "customer", None), "username", None),
        getattr(getattr(deal, "partner", None), "username", None),
    )
    for username in users:
        if username:
            return str(username)
    return str(fallback or "")


def get_auto_reminder_config(config: dict | None) -> dict:
    playerok = (config or {}).get("playerok", {})
    auto_reminder = playerok.get("auto_reminder", {}) if isinstance(playerok, dict) else {}

    enabled = bool(auto_reminder.get("enabled", False))
    interval_hours = _to_float(auto_reminder.get("interval_hours", 24.0), 24.0)
    if interval_hours <= 0:
        interval_hours = 24.0

    max_reminders = _to_int(auto_reminder.get("max_reminders", 3), 3)
    if max_reminders < 0:
        max_reminders = 0

    message_text = _normalize_message_text(auto_reminder.get("message_text"))

    return {
        "enabled": enabled,
        "interval_hours": interval_hours,
        "max_reminders": max_reminders,
        "message_text": message_text,
    }


def load_deals() -> dict[str, dict]:
    if not os.path.exists(DEALS_FILE):
        return {}

    try:
        with open(DEALS_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            return loaded
    except Exception as e:
        logger.error(f"Ошибка чтения файла авто-напоминаний: {e}")

    return {}


def save_deals(deals: dict[str, dict]) -> None:
    os.makedirs(os.path.dirname(DEALS_FILE), exist_ok=True)
    try:
        with open(DEALS_FILE, "w", encoding="utf-8") as f:
            json.dump(deals, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения файла авто-напоминаний: {e}")


def add_deal_to_monitor(deal: ItemDeal, chat_id: str) -> None:
    deal_id = str(getattr(deal, "id", "") or "").strip()
    if not deal_id:
        return

    now = datetime.now(timezone.utc).isoformat()
    deals = load_deals()
    deals[deal_id] = {
        "deal_id": deal_id,
        "chat_id": str(chat_id),
        "created_at": now,
        "last_reminder_at": now,
        "reminders_sent": 0,
        "item_name": str(getattr(getattr(deal, "item", None), "name", "") or ""),
        "user_username": _extract_buyer_name(deal),
    }
    save_deals(deals)
    logger.info(f"Сделка {deal_id} добавлена в авто-напоминания")


def remove_deal_from_monitor(deal_id: str) -> None:
    did = str(deal_id)
    deals = load_deals()
    if did in deals:
        del deals[did]
        save_deals(deals)
        logger.info(f"Сделка {did} удалена из авто-напоминаний")


def get_monitoring_stats() -> dict:
    deals = load_deals()
    current_time = datetime.now(timezone.utc)

    items = []
    for deal_id, data in deals.items():
        last_reminder_at = _parse_datetime(data.get("last_reminder_at"))
        if last_reminder_at:
            since_last = current_time - last_reminder_at
            since_last_minutes = int(max(0, since_last.total_seconds()) // 60)
        else:
            since_last_minutes = None

        items.append(
            {
                "deal_id": deal_id,
                "chat_id": str(data.get("chat_id", "")),
                "reminders_sent": _to_int(data.get("reminders_sent", 0), 0),
                "last_reminder_minutes_ago": since_last_minutes,
            }
        )

    return {
        "total": len(deals),
        "deals": items,
    }


def _format_reminder_text(message_template: str, deal_id: str, deal_data: dict) -> str:
    deal_link = f"https://playerok.com/deal/{deal_id}"
    prepared_template = _normalize_message_text(message_template).replace("{deal_link}", deal_link)
    buyer_name = str(deal_data.get("user_username") or "покупатель")

    values = _SafeFormat(
        deal_id=deal_id,
        deal_link=deal_link,
        item_name=str(deal_data.get("item_name") or ""),
        buyer_name=buyer_name,
        buyer_username=buyer_name,
        username=buyer_name,
    )

    try:
        text = prepared_template.format_map(values).strip()
    except Exception:
        text = prepared_template.strip()

    if not text:
        text = DEFAULT_MESSAGE_TEXT.replace("{deal_link}", deal_link)
    return text


async def check_auto_reminders_task(
    account: Account,
    send_message_callback,
    get_config_callback: Callable[[], dict] | None = None,
) -> None:
    while True:
        try:
            config = {}
            if callable(get_config_callback):
                try:
                    config = get_config_callback() or {}
                except Exception:
                    config = {}

            auto_reminder_config = get_auto_reminder_config(config)

            if not auto_reminder_config["enabled"]:
                await asyncio.sleep(60)
                continue

            deals = load_deals()
            if not deals:
                await asyncio.sleep(CHECK_INTERVAL_SECONDS)
                continue

            now = datetime.now(timezone.utc)
            changed = False

            for deal_id, deal_data in list(deals.items()):
                try:
                    chat_id = str(deal_data.get("chat_id") or "")
                    if not chat_id:
                        del deals[deal_id]
                        changed = True
                        continue

                    deal = account.get_deal(deal_id)
                    deal_status = getattr(deal, "status", None)

                    if deal_status != ItemDealStatuses.SENT:
                        del deals[deal_id]
                        changed = True
                        logger.info(
                            f"Сделка {deal_id} удалена из авто-напоминаний (статус: {getattr(deal_status, 'name', deal_status)})"
                        )
                        continue

                    actual_buyer_name = _extract_buyer_name(deal, fallback=deal_data.get("user_username", ""))
                    if deal_data.get("user_username") != actual_buyer_name:
                        deal_data["user_username"] = actual_buyer_name
                        changed = True

                    reminders_sent = _to_int(deal_data.get("reminders_sent", 0), 0)
                    max_reminders = auto_reminder_config["max_reminders"]

                    if max_reminders > 0 and reminders_sent >= max_reminders:
                        del deals[deal_id]
                        changed = True
                        logger.info(f"Сделка {deal_id} удалена из авто-напоминаний (достигнут лимит)")
                        continue

                    last_reminder_at = (
                        _parse_datetime(deal_data.get("last_reminder_at"))
                        or _parse_datetime(deal_data.get("created_at"))
                        or now
                    )

                    if now - last_reminder_at < timedelta(hours=auto_reminder_config["interval_hours"]):
                        continue

                    reminder_text = _format_reminder_text(
                        auto_reminder_config["message_text"],
                        deal_id=deal_id,
                        deal_data=deal_data,
                    )

                    sent_message = send_message_callback(chat_id, reminder_text)
                    if sent_message is None:
                        logger.warning(f"Не удалось отправить авто-напоминание по сделке {deal_id}, повторим позже")
                        continue
                    reminders_sent += 1
                    changed = True

                    if max_reminders > 0 and reminders_sent >= max_reminders:
                        del deals[deal_id]
                        logger.info(
                            f"Отправлено последнее авто-напоминание по сделке {deal_id}, запись удалена (лимит: {max_reminders})"
                        )
                    else:
                        deal_data["last_reminder_at"] = now.isoformat()
                        deal_data["reminders_sent"] = reminders_sent
                        deals[deal_id] = deal_data
                        logger.info(
                            f"Отправлено авто-напоминание по сделке {deal_id} (#{reminders_sent})"
                        )

                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"Ошибка проверки сделки {deal_id} в авто-напоминаниях: {e}")
                    continue

            if changed:
                save_deals(deals)

            await asyncio.sleep(CHECK_INTERVAL_SECONDS)
        except Exception as e:
            logger.error(f"Критическая ошибка цикла авто-напоминаний: {e}", exc_info=True)
            await asyncio.sleep(60)
