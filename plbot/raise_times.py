"""
Модуль хранения времени автоподнятия.

Содержит:
1) times: время последнего поднятия по item_id (для интервального режима)
2) completed_timings_by_date: выполненные тайминги по датам МСК (для режима по таймингу)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from logging import getLogger
from typing import Dict

import paths


logger = getLogger("seal.playerok.raise_times")
MSK_TZ = timezone(timedelta(hours=3))


def _normalize_timing(value: str) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    parts = raw.split(":")
    if len(parts) != 2:
        return None
    if not parts[0].isdigit() or not parts[1].isdigit():
        return None
    hour = int(parts[0])
    minute = int(parts[1])
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def _normalize_msk_date(value: str) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        date_obj = datetime.strptime(raw, "%Y-%m-%d")
    except Exception:
        return None
    return date_obj.strftime("%Y-%m-%d")


class RaiseTimes:
    """Хранилище данных автоподнятия."""

    def __init__(self):
        self.times: Dict[str, float] = {}  # {item_id: timestamp}
        self.completed_timings_by_date: Dict[str, list[str]] = {}  # {"YYYY-MM-DD": ["HH:MM", ...]}

    def to_dict(self) -> dict:
        return {
            "times": self.times,
            "completed_timings_by_date": self.completed_timings_by_date,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RaiseTimes":
        obj = cls()

        raw_times = data.get("times", {})
        if isinstance(raw_times, dict):
            sanitized_times = {}
            for key, value in raw_times.items():
                try:
                    sanitized_times[str(key)] = float(value)
                except Exception:
                    continue
            obj.times = sanitized_times

        raw_completed = data.get("completed_timings_by_date", {})
        if isinstance(raw_completed, dict):
            sanitized_completed: dict[str, list[str]] = {}
            for raw_date, raw_timings in raw_completed.items():
                normalized_date = _normalize_msk_date(str(raw_date))
                if not normalized_date:
                    continue

                timings_values = raw_timings if isinstance(raw_timings, list) else []
                normalized_timings: set[str] = set()
                for raw_timing in timings_values:
                    normalized_timing = _normalize_timing(str(raw_timing))
                    if normalized_timing:
                        normalized_timings.add(normalized_timing)

                if normalized_timings:
                    sanitized_completed[normalized_date] = sorted(
                        normalized_timings,
                        key=lambda item: (int(item[:2]), int(item[3:])),
                    )

            obj.completed_timings_by_date = sanitized_completed

        return obj


_raise_times: RaiseTimes | None = None


def get_raise_times() -> RaiseTimes:
    global _raise_times
    if _raise_times is None:
        _raise_times = load_raise_times()
    return _raise_times


def set_raise_times(raise_times: RaiseTimes):
    global _raise_times
    _raise_times = raise_times
    save_raise_times()


def load_raise_times() -> RaiseTimes:
    try:
        if os.path.exists(paths.AUTO_RAISE_ITEMS_TIMES_FILE):
            with open(paths.AUTO_RAISE_ITEMS_TIMES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return RaiseTimes.from_dict(data)
    except Exception as e:
        logger.error(f"Ошибка загрузки времени поднятия товаров: {e}")

    return RaiseTimes()


def save_raise_times():
    try:
        raise_times = get_raise_times()
        os.makedirs(os.path.dirname(paths.AUTO_RAISE_ITEMS_TIMES_FILE), exist_ok=True)
        with open(paths.AUTO_RAISE_ITEMS_TIMES_FILE, "w", encoding="utf-8") as f:
            json.dump(raise_times.to_dict(), f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Ошибка сохранения времени поднятия товаров: {e}")


def get_last_raise_time(item_id: str) -> float | None:
    raise_times = get_raise_times()
    return raise_times.times.get(str(item_id))


def set_last_raise_time(item_id: str, timestamp: float | None = None):
    raise_times = get_raise_times()
    if timestamp is None:
        timestamp = datetime.now().timestamp()
    raise_times.times[str(item_id)] = float(timestamp)
    save_raise_times()


def should_raise_item(item_id: str, interval_hours: int | float) -> bool:
    last_raise = get_last_raise_time(item_id)

    if last_raise is None:
        set_last_raise_time(item_id)
        return False

    current_time = datetime.now().timestamp()
    interval_seconds = float(interval_hours) * 3600
    return (current_time - last_raise) >= interval_seconds


def get_msk_now() -> datetime:
    return datetime.now(MSK_TZ)


def get_completed_timings_for_date(msk_date: str) -> list[str]:
    normalized_date = _normalize_msk_date(msk_date)
    if not normalized_date:
        return []
    raise_times = get_raise_times()
    return list(raise_times.completed_timings_by_date.get(normalized_date, []))


def is_timing_completed(msk_date: str, timing: str) -> bool:
    normalized_date = _normalize_msk_date(msk_date)
    normalized_timing = _normalize_timing(timing)
    if not normalized_date or not normalized_timing:
        return False
    raise_times = get_raise_times()
    return normalized_timing in set(raise_times.completed_timings_by_date.get(normalized_date, []))


def mark_timing_completed(msk_date: str, timing: str):
    normalized_date = _normalize_msk_date(msk_date)
    normalized_timing = _normalize_timing(timing)
    if not normalized_date or not normalized_timing:
        return

    raise_times = get_raise_times()
    current_values = set(raise_times.completed_timings_by_date.get(normalized_date, []))
    current_values.add(normalized_timing)
    raise_times.completed_timings_by_date[normalized_date] = sorted(
        current_values,
        key=lambda item: (int(item[:2]), int(item[3:])),
    )
    save_raise_times()


def cleanup_completed_timings(current_msk_date: str):
    normalized_date = _normalize_msk_date(current_msk_date)
    if not normalized_date:
        return

    raise_times = get_raise_times()
    if not raise_times.completed_timings_by_date:
        return

    if list(raise_times.completed_timings_by_date.keys()) == [normalized_date]:
        return

    raise_times.completed_timings_by_date = {
        normalized_date: list(raise_times.completed_timings_by_date.get(normalized_date, []))
    } if normalized_date in raise_times.completed_timings_by_date else {}
    save_raise_times()
