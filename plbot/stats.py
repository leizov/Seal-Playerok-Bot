import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

# Импорт путей из центрального модуля
import paths


STATS_FILE = paths.STATS_FILE


@dataclass
class Stats:
    bot_launch_time: datetime | None
    month_started_at: datetime | None
    month_key: str
    sales_total_count: int
    refund_total_count: int
    sales_total_sum: float
    refund_total_sum: float
    raises_total_sum: float
    sales_month_count: int
    refund_month_count: int
    sales_month_sum: float
    refund_month_sum: float
    raises_month_sum: float


_stats = Stats(
    bot_launch_time=None,
    month_started_at=None,
    month_key="",
    sales_total_count=0,
    refund_total_count=0,
    sales_total_sum=0.0,
    refund_total_sum=0.0,
    raises_total_sum=0.0,
    sales_month_count=0,
    refund_month_count=0,
    sales_month_sum=0.0,
    refund_month_sum=0.0,
    raises_month_sum=0.0,
)


def get_stats() -> Stats:
    return _stats


def set_stats(new):
    global _stats
    _stats = new
    ensure_month_window()
    save_stats()


def _month_key_now() -> str:
    return datetime.now().strftime("%Y-%m")


def ensure_month_window():
    """Проверяет границу месяца и сбрасывает только месячные счётчики."""
    if _stats.month_key == "":
        _stats.month_key = _month_key_now()
        _stats.month_started_at = datetime.now()
        return

    current_key = _month_key_now()
    if _stats.month_key == current_key:
        return

    _stats.month_key = current_key
    _stats.month_started_at = datetime.now()
    _stats.sales_month_count = 0
    _stats.refund_month_count = 0
    _stats.sales_month_sum = 0.0
    _stats.refund_month_sum = 0.0
    _stats.raises_month_sum = 0.0


def _normalize_amount(value: Any) -> float:
    try:
        return round(float(value), 2)
    except Exception:
        return 0.0


def record_new_deal(amount: float):
    ensure_month_window()
    val = _normalize_amount(amount)
    _stats.sales_total_count += 1
    _stats.sales_month_count += 1
    _stats.sales_total_sum = round(_stats.sales_total_sum + val, 2)
    _stats.sales_month_sum = round(_stats.sales_month_sum + val, 2)
    save_stats()


def record_refund(amount: float):
    ensure_month_window()
    val = _normalize_amount(amount)
    _stats.refund_total_count += 1
    _stats.refund_month_count += 1
    _stats.refund_total_sum = round(_stats.refund_total_sum + val, 2)
    _stats.refund_month_sum = round(_stats.refund_month_sum + val, 2)
    save_stats()


def record_raise(amount: float):
    ensure_month_window()
    val = _normalize_amount(amount)
    _stats.raises_total_sum = round(_stats.raises_total_sum + val, 2)
    _stats.raises_month_sum = round(_stats.raises_month_sum + val, 2)
    save_stats()


def _from_legacy(data: dict[str, Any]) -> dict[str, Any]:
    """
    Миграция старого формата:
    deals_completed -> sales_total_count
    earned_money -> sales_total_sum
    refunded_money -> refund_total_sum
    """
    migrated = {
        "bot_launch_time": data.get("bot_launch_time"),
        "month_started_at": data.get("month_started_at"),
        "month_key": data.get("month_key", ""),
        "sales_total_count": int(data.get("sales_total_count", data.get("deals_completed", 0)) or 0),
        "refund_total_count": int(data.get("refund_total_count", 0) or 0),
        "sales_total_sum": _normalize_amount(data.get("sales_total_sum", data.get("earned_money", 0.0))),
        "refund_total_sum": _normalize_amount(data.get("refund_total_sum", data.get("refunded_money", 0.0))),
        "raises_total_sum": _normalize_amount(data.get("raises_total_sum", 0.0)),
        "sales_month_count": int(data.get("sales_month_count", 0) or 0),
        "refund_month_count": int(data.get("refund_month_count", 0) or 0),
        "sales_month_sum": _normalize_amount(data.get("sales_month_sum", 0.0)),
        "refund_month_sum": _normalize_amount(data.get("refund_month_sum", 0.0)),
        "raises_month_sum": _normalize_amount(data.get("raises_month_sum", 0.0)),
    }
    return migrated


def save_stats():
    """Сохраняет статистику в файл"""
    try:
        os.makedirs(os.path.dirname(STATS_FILE), exist_ok=True)
        ensure_month_window()
        data = asdict(_stats)
        # Конвертируем datetime в строку
        if data["bot_launch_time"]:
            data["bot_launch_time"] = data["bot_launch_time"].isoformat()
        if data["month_started_at"]:
            data["month_started_at"] = data["month_started_at"].isoformat()

        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Ошибка при сохранении статистики: {e}")


def load_stats():
    """Загружает статистику из файла"""
    global _stats
    try:
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            data = _from_legacy(data)

            # Конвертируем строки в datetime
            if data.get("bot_launch_time"):
                data["bot_launch_time"] = datetime.fromisoformat(data["bot_launch_time"])
            else:
                data["bot_launch_time"] = None

            if data.get("month_started_at"):
                data["month_started_at"] = datetime.fromisoformat(data["month_started_at"])
            else:
                data["month_started_at"] = None

            _stats = Stats(**data)
            ensure_month_window()
            print(f"Статистика успешно загружена из файла")
        else:
            print(f"Файл статистики не найден, используются значения по умолчанию")
            ensure_month_window()
    except Exception as e:
        print(f"Ошибка при загрузке статистики: {e}")
        print(f"Используются значения по умолчанию")
        ensure_month_window()
