import json
import logging
import os
import threading
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

# Импорт путей из центрального модуля
import paths


STATS_FILE = paths.STATS_FILE
logger = logging.getLogger("seal.stats")

# Сколько дней хранить дневной журнал (чтобы файл не рос бесконечно).
DAILY_RETENTION_DAYS = 400

# Все записи статистики идут из разных потоков (daemon workers) — сериализуем.
_lock = threading.RLock()

# TODO(stats-charts): графики по дневному журналу (продажи/выручка по дням,
#  расходы на поднятия). Данные уже есть в Stats.daily — нужен только рендер
#  картинки (например, matplotlib) и кнопка «📈 График» на экране статистики.


def _empty_day() -> dict[str, Any]:
    return {
        "sales_count": 0,
        "sales_sum": 0.0,
        "refund_count": 0,
        "refund_sum": 0.0,
        "reviews_count": 0,
        "raises_sum": 0.0,
        "keep_in_sale_sum": 0.0,
        "items": {},
    }


@dataclass
class Stats:
    bot_launch_time: datetime | None
    month_started_at: datetime | None
    month_key: str
    sales_total_count: int
    reviews_total_count: int
    refund_total_count: int
    sales_total_sum: float
    refund_total_sum: float
    raises_total_sum: float
    sales_month_count: int
    reviews_month_count: int
    refund_month_count: int
    sales_month_sum: float
    refund_month_sum: float
    raises_month_sum: float
    # Оценочный расход на «Оставлять в продаже» (по текущей цене поднятия товара).
    keep_in_sale_total_sum: float = 0.0
    keep_in_sale_month_sum: float = 0.0
    # Дата начала ведения дневного журнала (до неё есть только агрегаты).
    daily_started_at: datetime | None = None
    # Дневной журнал: "YYYY-MM-DD" -> счётчики дня + items {name: {count, sum}}.
    daily: dict[str, dict[str, Any]] = field(default_factory=dict)


_stats = Stats(
    bot_launch_time=None,
    month_started_at=None,
    month_key="",
    sales_total_count=0,
    reviews_total_count=0,
    refund_total_count=0,
    sales_total_sum=0.0,
    refund_total_sum=0.0,
    raises_total_sum=0.0,
    sales_month_count=0,
    reviews_month_count=0,
    refund_month_count=0,
    sales_month_sum=0.0,
    refund_month_sum=0.0,
    raises_month_sum=0.0,
)


def get_stats() -> Stats:
    return _stats


def set_stats(new):
    global _stats
    with _lock:
        _stats = new
        ensure_month_window()
        save_stats()


def _month_key_now() -> str:
    return datetime.now().strftime("%Y-%m")


def ensure_month_window():
    """Проверяет границу месяца и сбрасывает только месячные счётчики."""
    with _lock:
        if _stats.daily_started_at is None:
            _stats.daily_started_at = datetime.now()

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
        _stats.reviews_month_count = 0
        _stats.refund_month_count = 0
        _stats.sales_month_sum = 0.0
        _stats.refund_month_sum = 0.0
        _stats.raises_month_sum = 0.0
        _stats.keep_in_sale_month_sum = 0.0


def _normalize_amount(value: Any) -> float:
    try:
        return round(float(value), 2)
    except Exception:
        return 0.0


def _today_key() -> str:
    return date.today().isoformat()


def _day(key: str | None = None) -> dict[str, Any]:
    key = key or _today_key()
    day = _stats.daily.get(key)
    if not isinstance(day, dict):
        day = _empty_day()
        _stats.daily[key] = day
    else:
        for k, v in _empty_day().items():
            day.setdefault(k, v if not isinstance(v, dict) else {})
    return day


def _prune_daily():
    cutoff = (date.today() - timedelta(days=DAILY_RETENTION_DAYS)).isoformat()
    for key in [k for k in _stats.daily if k < cutoff]:
        _stats.daily.pop(key, None)


def record_new_deal(amount: float, item_name: str | None = None):
    with _lock:
        ensure_month_window()
        val = _normalize_amount(amount)
        _stats.sales_total_count += 1
        _stats.sales_month_count += 1
        _stats.sales_total_sum = round(_stats.sales_total_sum + val, 2)
        _stats.sales_month_sum = round(_stats.sales_month_sum + val, 2)

        day = _day()
        day["sales_count"] += 1
        day["sales_sum"] = round(day["sales_sum"] + val, 2)
        name = str(item_name or "").strip()
        if name:
            item = day["items"].setdefault(name, {"count": 0, "sum": 0.0})
            item["count"] = int(item.get("count", 0)) + 1
            item["sum"] = round(float(item.get("sum", 0.0)) + val, 2)
        save_stats()


def record_review():
    with _lock:
        ensure_month_window()
        _stats.reviews_total_count += 1
        _stats.reviews_month_count += 1
        _day()["reviews_count"] += 1
        save_stats()


def record_refund(amount: float):
    with _lock:
        ensure_month_window()
        val = _normalize_amount(amount)
        _stats.refund_total_count += 1
        _stats.refund_month_count += 1
        _stats.refund_total_sum = round(_stats.refund_total_sum + val, 2)
        _stats.refund_month_sum = round(_stats.refund_month_sum + val, 2)
        day = _day()
        day["refund_count"] += 1
        day["refund_sum"] = round(day["refund_sum"] + val, 2)
        save_stats()


def record_raise(amount: float):
    with _lock:
        ensure_month_window()
        val = _normalize_amount(amount)
        _stats.raises_total_sum = round(_stats.raises_total_sum + val, 2)
        _stats.raises_month_sum = round(_stats.raises_month_sum + val, 2)
        day = _day()
        day["raises_sum"] = round(day["raises_sum"] + val, 2)
        save_stats()


def record_keep_in_sale(amount: float):
    """
    Оценочный расход «Оставлять в продаже»: после продажи такой товар остаётся
    в продаже, и мы считаем, что Playerok списал текущую цену его поднятия.
    Реальное списание может отличаться (оценка может быть завышена).
    """
    val = _normalize_amount(amount)
    if val <= 0:
        return
    with _lock:
        ensure_month_window()
        _stats.keep_in_sale_total_sum = round(_stats.keep_in_sale_total_sum + val, 2)
        _stats.keep_in_sale_month_sum = round(_stats.keep_in_sale_month_sum + val, 2)
        day = _day()
        day["keep_in_sale_sum"] = round(day["keep_in_sale_sum"] + val, 2)
        save_stats()


# ---------------------------------------------------------------------------
# Агрегаты по дневному журналу
# ---------------------------------------------------------------------------

def period_days(period: str, today: date | None = None) -> list[str]:
    """
    Ключи дней периода:
    - week  — последние 7 дней, включая сегодня;
    - month — с 1-го числа текущего календарного месяца по сегодня.
    """
    today = today or date.today()
    if period == "week":
        start = today - timedelta(days=6)
    elif period == "month":
        start = today.replace(day=1)
    else:
        raise ValueError(f"Неизвестный период: {period}")
    days = (today - start).days + 1
    return [(start + timedelta(days=i)).isoformat() for i in range(days)]


def summarize_days(keys: list[str]) -> dict[str, Any]:
    """Суммирует дневной журнал по указанным дням."""
    with _lock:
        result = _empty_day()
        items: dict[str, dict[str, Any]] = {}
        best_day: tuple[str, float] | None = None
        days_with_data = 0
        for key in keys:
            day = _stats.daily.get(key)
            if not isinstance(day, dict):
                continue
            days_with_data += 1
            for field_name in ("sales_count", "refund_count", "reviews_count"):
                result[field_name] += int(day.get(field_name, 0) or 0)
            for field_name in ("sales_sum", "refund_sum", "raises_sum", "keep_in_sale_sum"):
                result[field_name] = round(result[field_name] + _normalize_amount(day.get(field_name, 0.0)), 2)
            for name, data in (day.get("items") or {}).items():
                agg = items.setdefault(name, {"count": 0, "sum": 0.0})
                agg["count"] += int(data.get("count", 0) or 0)
                agg["sum"] = round(agg["sum"] + _normalize_amount(data.get("sum", 0.0)), 2)
            day_sum = _normalize_amount(day.get("sales_sum", 0.0))
            if day_sum > 0 and (best_day is None or day_sum > best_day[1]):
                best_day = (key, day_sum)

        top_item = None
        if items:
            # Популярный = больше всего продаж; при равенстве — больше выручка.
            name, data = max(items.items(), key=lambda kv: (kv[1]["count"], kv[1]["sum"]))
            top_item = {"name": name, "count": data["count"], "sum": data["sum"]}

        result["items"] = items
        result["best_day"] = {"date": best_day[0], "sum": best_day[1]} if best_day else None
        result["top_item"] = top_item
        result["days_with_data"] = days_with_data
        return result


def _from_legacy(data: dict[str, Any]) -> dict[str, Any]:
    """
    Миграция старого формата:
    deals_completed -> sales_total_count
    earned_money -> sales_total_sum
    refunded_money -> refund_total_sum
    Дневного журнала в старых файлах нет — он начинается с момента обновления.
    """
    daily = data.get("daily")
    migrated = {
        "bot_launch_time": data.get("bot_launch_time"),
        "month_started_at": data.get("month_started_at"),
        "month_key": data.get("month_key", ""),
        "sales_total_count": int(data.get("sales_total_count", data.get("deals_completed", 0)) or 0),
        "reviews_total_count": int(data.get("reviews_total_count", 0) or 0),
        "refund_total_count": int(data.get("refund_total_count", 0) or 0),
        "sales_total_sum": _normalize_amount(data.get("sales_total_sum", data.get("earned_money", 0.0))),
        "refund_total_sum": _normalize_amount(data.get("refund_total_sum", data.get("refunded_money", 0.0))),
        "raises_total_sum": _normalize_amount(data.get("raises_total_sum", 0.0)),
        "sales_month_count": int(data.get("sales_month_count", 0) or 0),
        "reviews_month_count": int(data.get("reviews_month_count", 0) or 0),
        "refund_month_count": int(data.get("refund_month_count", 0) or 0),
        "sales_month_sum": _normalize_amount(data.get("sales_month_sum", 0.0)),
        "refund_month_sum": _normalize_amount(data.get("refund_month_sum", 0.0)),
        "raises_month_sum": _normalize_amount(data.get("raises_month_sum", 0.0)),
        "keep_in_sale_total_sum": _normalize_amount(data.get("keep_in_sale_total_sum", 0.0)),
        "keep_in_sale_month_sum": _normalize_amount(data.get("keep_in_sale_month_sum", 0.0)),
        "daily_started_at": data.get("daily_started_at"),
        "daily": daily if isinstance(daily, dict) else {},
    }
    return migrated


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def save_stats():
    """Сохраняет статистику в файл (атомарно, через временный файл)."""
    with _lock:
        try:
            os.makedirs(os.path.dirname(STATS_FILE), exist_ok=True)
            ensure_month_window()
            _prune_daily()
            data = asdict(_stats)
            for key in ("bot_launch_time", "month_started_at", "daily_started_at"):
                if data.get(key):
                    data[key] = data[key].isoformat()

            tmp_path = f"{STATS_FILE}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            os.replace(tmp_path, STATS_FILE)
        except Exception as e:
            logger.error("Ошибка при сохранении статистики: %s", e)


def load_stats():
    """Загружает статистику из файла"""
    global _stats
    with _lock:
        try:
            if os.path.exists(STATS_FILE):
                with open(STATS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)

                data = _from_legacy(data)
                for key in ("bot_launch_time", "month_started_at", "daily_started_at"):
                    data[key] = _parse_dt(data.get(key))

                _stats = Stats(**data)
                ensure_month_window()
                logger.info("Статистика успешно загружена из файла")
            else:
                logger.warning("Файл статистики не найден, используются значения по умолчанию")
                ensure_month_window()
        except Exception as e:
            logger.error("Ошибка при загрузке статистики: %s", e)
            logger.warning("Используются значения по умолчанию")
            ensure_month_window()
