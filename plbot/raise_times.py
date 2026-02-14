"""
Модуль для работы с временем последнего поднятия товаров.
Хранит информацию о том, когда каждый товар был поднят последний раз.
"""
import json
import os
from typing import Dict
from datetime import datetime
from logging import getLogger

import paths


logger = getLogger("seal.playerok.raise_times")


class RaiseTimes:
    """Класс для хранения времени последнего поднятия товаров."""
    
    def __init__(self):
        self.times: Dict[str, float] = {}  # {item_id: timestamp}
    
    def to_dict(self) -> dict:
        """Преобразует объект в словарь для сохранения."""
        return {
            "times": self.times
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'RaiseTimes':
        """Создаёт объект из словаря."""
        obj = cls()
        obj.times = data.get("times", {})
        return obj


# Глобальный экземпляр
_raise_times: RaiseTimes | None = None


def get_raise_times() -> RaiseTimes:
    """Получает глобальный экземпляр времени поднятия товаров."""
    global _raise_times
    if _raise_times is None:
        _raise_times = load_raise_times()
    return _raise_times


def set_raise_times(raise_times: RaiseTimes):
    """Устанавливает глобальный экземпляр времени поднятия товаров."""
    global _raise_times
    _raise_times = raise_times
    save_raise_times()


def load_raise_times() -> RaiseTimes:
    """Загружает время поднятия товаров из файла."""
    try:
        if os.path.exists(paths.AUTO_RAISE_ITEMS_TIMES_FILE):
            with open(paths.AUTO_RAISE_ITEMS_TIMES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return RaiseTimes.from_dict(data)
    except Exception as e:
        logger.error(f"Ошибка загрузки времени поднятия товаров: {e}")
    
    return RaiseTimes()


def save_raise_times():
    """Сохраняет время поднятия товаров в файл."""
    try:
        raise_times = get_raise_times()
        os.makedirs(os.path.dirname(paths.AUTO_RAISE_ITEMS_TIMES_FILE), exist_ok=True)
        with open(paths.AUTO_RAISE_ITEMS_TIMES_FILE, 'w', encoding='utf-8') as f:
            json.dump(raise_times.to_dict(), f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Ошибка сохранения времени поднятия товаров: {e}")


def get_last_raise_time(item_id: str) -> float | None:
    """
    Получает время последнего поднятия товара.
    
    :param item_id: ID товара
    :return: Timestamp последнего поднятия или None если товар ещё не поднимался
    """
    raise_times = get_raise_times()
    return raise_times.times.get(item_id)


def set_last_raise_time(item_id: str, timestamp: float | None = None):
    """
    Устанавливает время последнего поднятия товара.
    
    :param item_id: ID товара
    :param timestamp: Timestamp поднятия (если None - используется текущее время)
    """
    raise_times = get_raise_times()
    if timestamp is None:
        timestamp = datetime.now().timestamp()
    raise_times.times[item_id] = timestamp
    save_raise_times()


def should_raise_item(item_id: str, interval_hours: int) -> bool:
    """
    Проверяет, нужно ли поднимать товар (прошёл ли интервал).
    
    :param item_id: ID товара
    :param interval_hours: Интервал в часах
    :return: True если нужно поднимать, False если ещё рано
    """
    last_raise = get_last_raise_time(item_id)
    
    # Если товар ещё не поднимался - запоминаем текущее время как старт интервала
    if last_raise is None:
        set_last_raise_time(item_id)
        return False
    
    # Проверяем прошёл ли интервал
    current_time = datetime.now().timestamp()
    interval_seconds = interval_hours * 3600
    
    return (current_time - last_raise) >= interval_seconds
