"""
История авто-выдач: что, кому и когда было выдано.

Хранится в bot_data/auto_delivery_history.json (новые записи в начале списка).
Запись атомарная (через временный файл), доступ из разных потоков — под блокировкой.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from logging import getLogger
from typing import Any

import paths

HISTORY_FILE = paths.AUTO_DELIVERY_HISTORY_FILE
MAX_HISTORY_ENTRIES = 1000

STATUS_SENT = "sent"
STATUS_FAILED = "failed"
STATUS_OUT_OF_STOCK = "out_of_stock"

logger = getLogger("seal.delivery_history")
_lock = threading.RLock()


def _read() -> list[dict[str, Any]]:
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [entry for entry in data if isinstance(entry, dict)] if isinstance(data, list) else []
    except FileNotFoundError:
        return []
    except Exception as e:
        logger.error("Не удалось прочитать историю выдач: %s", e)
        return []


def _write(entries: list[dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    tmp_path = f"{HISTORY_FILE}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, HISTORY_FILE)


def add_record(
    *,
    status: str,
    kind: str,
    deal_id: Any = None,
    chat_id: Any = None,
    buyer: Any = None,
    item_name: Any = None,
    item_price: Any = None,
    keyphrase: Any = None,
    good: str | None = None,
    message: str | None = None,
    remaining: int | None = None,
) -> dict[str, Any] | None:
    """Добавляет запись в историю. Ошибки записи только логируются — выдача не должна падать."""
    with _lock:
        try:
            entries = _read()
            next_id = max((int(e.get("id", 0) or 0) for e in entries), default=0) + 1
            record = {
                "id": next_id,
                "time": datetime.now().isoformat(timespec="seconds"),
                "status": status,
                "kind": kind,
                "deal_id": str(deal_id) if deal_id is not None else None,
                "chat_id": str(chat_id) if chat_id is not None else None,
                "buyer": str(buyer) if buyer is not None else None,
                "item_name": str(item_name) if item_name is not None else None,
                "item_price": item_price,
                "keyphrase": str(keyphrase) if keyphrase is not None else None,
                "good": good,
                "message": message,
                "remaining": remaining,
            }
            entries.insert(0, record)
            del entries[MAX_HISTORY_ENTRIES:]
            _write(entries)
            return record
        except Exception as e:
            logger.error("Не удалось сохранить запись истории выдач: %s", e)
            return None


def get_records() -> list[dict[str, Any]]:
    """Все записи, новые первыми."""
    with _lock:
        return _read()


def get_record(record_id: int) -> dict[str, Any] | None:
    for entry in get_records():
        if int(entry.get("id", 0) or 0) == int(record_id):
            return entry
    return None


def get_records_for_deal(deal_id: Any) -> list[dict[str, Any]]:
    return [e for e in get_records() if e.get("deal_id") == str(deal_id)]
