import json
import os
from datetime import datetime
from dataclasses import dataclass, asdict


STATS_FILE = "bot_data/stats.json"


@dataclass
class Stats:
    bot_launch_time: datetime
    deals_completed: int
    refunded_money: float
    earned_money: float

        
_stats = Stats(
    bot_launch_time=None,
    deals_completed=0,
    refunded_money=0.0,
    earned_money=0.0
)


def get_stats() -> Stats:
    return _stats


def set_stats(new):
    global _stats
    _stats = new
    save_stats()


def save_stats():
    """Сохраняет статистику в файл"""
    try:
        os.makedirs(os.path.dirname(STATS_FILE), exist_ok=True)
        data = asdict(_stats)
        # Конвертируем datetime в строку
        if data['bot_launch_time']:
            data['bot_launch_time'] = data['bot_launch_time'].isoformat()
        
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Ошибка при сохранении статистики: {e}")


def load_stats():
    """Загружает статистику из файла"""
    global _stats
    try:
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Конвертируем строку обратно в datetime
            if data.get('bot_launch_time'):
                data['bot_launch_time'] = datetime.fromisoformat(data['bot_launch_time'])
            else:
                data['bot_launch_time'] = None
            
            _stats = Stats(**data)
            print(f"Статистика успешно загружена из файла")
        else:
            print(f"Файл статистики не найден, используются значения по умолчанию")
    except Exception as e:
        print(f"Ошибка при загрузке статистики: {e}")
        print(f"Используются значения по умолчанию")