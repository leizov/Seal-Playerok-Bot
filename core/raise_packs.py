"""
Паки автоподнятия.

Пак — группа лотов со своими ключевыми фразами и своим расписанием
(интервал, тайминги или позиция в категории).
Лот попадает в пак, если в его названии есть хотя бы одна фраза пака (регистр не важен).
Если лот подходит под несколько паков, работает первый включённый пак по порядку в списке.

Файл: bot_settings/auto_raise_packs.json — список паков:
    {"id": "1a2b3c4d", "name": "Duolingo", "enabled": true, "keyphrases": ["duolingo"],
     "mode": "interval", "interval_hours": 24.0, "timings": ["12:00"],
     "position_schedule": [{"id": 1, "start": "00:00", "end": "00:00", "position": 10,
                            "cooldown_minutes": 10, "base": true}],
     "changed_at": 1764000000.0, "pause_windows": [[1764000000.0, 1764000180.0]]}

Режим «По позиции»: расписание — участки времени (МСК), у каждого своё место и кулдаун
(или «не поднимать»). Участки не пересекаются: новый участок забирает своё время у остальных.
Время, которое не покрыто ни одним участком, — пустое: в него ничего не поднимается.
start == end — участок на весь день. end раньше start — участок через полночь.

После любого изменения пака режим «По позиции» 3 минуты не поднимает (pause_windows — эти паузы).
Время пауз не засчитывается в кулдаун лотов пака: кулдаун на паузе «замирает».
"""

from __future__ import annotations

import math
import re
import time
import uuid
from datetime import datetime, timedelta, timezone

from settings import Settings as sett


SETTINGS_NAME = "auto_raise_packs"

SOURCE_LOTS = "lots"
SOURCE_PACKS = "packs"

MODE_INTERVAL = "interval"
MODE_TIMING = "timing"
MODE_POSITION = "position"
MODES = (MODE_INTERVAL, MODE_TIMING, MODE_POSITION)

DEFAULT_INTERVAL_HOURS = 24.0
MAX_INTERVAL_HOURS = 8760.0
MAX_NAME_LENGTH = 40
TIMING_WINDOW_MINUTES = 5

# ── Режим «По позиции» ──
DAY_MINUTES = 24 * 60
MAX_POSITION = 1000
DEFAULT_COOLDOWN_MINUTES = 10
MIN_COOLDOWN_MINUTES = 2            # меньше поставить нельзя
CONFIRM_COOLDOWN_BELOW_MINUTES = 10  # меньше — только с подтверждением
MAX_COOLDOWN_MINUTES = 7 * 24 * 60
MAX_SEGMENTS = 24
SETTINGS_PAUSE_SECONDS = 180        # после изменения настроек пак «По позиции» 3 минуты не поднимает
MAX_PAUSE_WINDOWS = 50              # сколько последних пауз помнить (для расчёта кулдауна)
POSITION_STREAK_REQUIRED = 2        # лот ниже места столько проверок подряд → поднимаем

MSK_TZ = timezone(timedelta(hours=3))


# ── Нормализация ──

def normalize_source(raw) -> str:
    """Тип настройки автоподнятия: «Все лоты» (lots) или «Паки» (packs)."""
    value = str(raw or "").strip().lower()
    return SOURCE_PACKS if value == SOURCE_PACKS else SOURCE_LOTS


def normalize_mode(raw) -> str:
    value = str(raw or "").strip().lower()
    return value if value in MODES else MODE_INTERVAL


def normalize_timing(raw) -> str | None:
    """«16», «16:00», «9:5» → «16:00», «09:05». Некорректное значение → None."""
    value = str(raw or "").strip()
    if not value:
        return None
    parts = value.split(":") if ":" in value else [value, "0"]
    if len(parts) != 2 or not parts[0].strip().isdigit() or not parts[1].strip().isdigit():
        return None
    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return f"{hour:02d}:{minute:02d}"


def normalize_timings(raw) -> list[str]:
    if not isinstance(raw, list):
        return []
    unique = {t for t in (normalize_timing(v) for v in raw) if t}
    return sorted(unique, key=lambda t: (int(t[:2]), int(t[3:])))


def normalize_keyphrases(raw) -> list[str]:
    """Список фраз без пустых и без повторов (без учёта регистра), порядок сохраняется."""
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for value in raw:
        phrase = " ".join(str(value or "").split())
        key = phrase.lower()
        if phrase and key not in seen:
            seen.add(key)
            result.append(phrase)
    return result


def parse_keyphrases_text(text: str) -> list[str]:
    """Фразы из сообщения или .txt: через запятую и/или с новой строки."""
    chunks = []
    for line in str(text or "").splitlines():
        chunks.extend(line.split(","))
    return normalize_keyphrases(chunks)


def _normalize_interval(raw) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_INTERVAL_HOURS
    if value <= 0 or value > MAX_INTERVAL_HOURS:
        return DEFAULT_INTERVAL_HOURS
    return value


def normalize_pack(raw) -> dict | None:
    if not isinstance(raw, dict):
        return None
    pack_id = str(raw.get("id") or "").strip()
    if not pack_id:
        return None
    name = " ".join(str(raw.get("name") or "").split())[:MAX_NAME_LENGTH] or "Без названия"
    return {
        "id": pack_id,
        "name": name,
        "enabled": bool(raw.get("enabled", True)),
        "keyphrases": normalize_keyphrases(raw.get("keyphrases")),
        "mode": normalize_mode(raw.get("mode")),
        "interval_hours": _normalize_interval(raw.get("interval_hours", DEFAULT_INTERVAL_HOURS)),
        "timings": normalize_timings(raw.get("timings")),
        "position_schedule": normalize_schedule(raw.get("position_schedule")),
        "changed_at": _normalize_timestamp(raw.get("changed_at")),
        "pause_windows": _normalize_windows(raw.get("pause_windows")),
    }


def _normalize_windows(raw) -> list[list[float]]:
    if not isinstance(raw, list):
        return []
    windows = []
    for item in raw:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            continue
        start, end = _normalize_timestamp(item[0]), _normalize_timestamp(item[1])
        if start and end > start:
            windows.append([start, end])
    windows.sort()
    merged: list[list[float]] = []
    for start, end in windows:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged[-MAX_PAUSE_WINDOWS:]


def _normalize_timestamp(raw) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.0
    return value if value > 0 and math.isfinite(value) else 0.0


def normalize_packs(raw) -> list[dict]:
    if not isinstance(raw, list):
        return []
    packs: list[dict] = []
    seen_ids: set[str] = set()
    for item in raw:
        pack = normalize_pack(item)
        if pack and pack["id"] not in seen_ids:
            seen_ids.add(pack["id"])
            packs.append(pack)
    return packs


# ── Хранение ──

def load_packs() -> list[dict]:
    return normalize_packs(sett.get(SETTINGS_NAME) or [])


_SERVICE_KEYS = ("changed_at", "pause_windows")


def _settings_key(pack: dict) -> dict:
    return {key: value for key, value in pack.items() if key not in _SERVICE_KEYS}


def _add_pause(windows: list[list[float]], now: float) -> list[list[float]]:
    """Новая пауза после изменения: продлевает текущую или начинает новую. Старше 7 дней — забываются."""
    windows = [list(w) for w in windows if w[1] >= now - MAX_COOLDOWN_MINUTES * 60]
    if windows and now <= windows[-1][1]:
        windows[-1][1] = max(windows[-1][1], now + SETTINGS_PAUSE_SECONDS)
    else:
        windows.append([now, now + SETTINGS_PAUSE_SECONDS])
    return windows[-MAX_PAUSE_WINDOWS:]


def save_packs(packs: list[dict], now: float | None = None):
    """
    Сохраняет паки. Пакам, у которых что-то изменилось (включая место в списке),
    проставляется changed_at и добавляется пауза — 3 минуты режим «По позиции» не поднимает,
    и это время не засчитывается в кулдаун лотов пака.
    """
    now = time.time() if now is None else now
    previous = {pack["id"]: (index, pack) for index, pack in enumerate(load_packs())}
    result = []
    for index, pack in enumerate(normalize_packs(packs)):
        old = previous.get(pack["id"])
        if old is None or old[0] != index or _settings_key(old[1]) != _settings_key(pack):
            pack["changed_at"] = now
            pack["pause_windows"] = _add_pause(old[1]["pause_windows"] if old else [], now)
        else:
            pack["changed_at"] = old[1]["changed_at"]
            pack["pause_windows"] = old[1]["pause_windows"]
        result.append(pack)
    sett.set(SETTINGS_NAME, result)
    # Вызывающий код продолжает работать со своими объектами — обновляем в них служебные поля
    by_id = {pack["id"]: pack for pack in result}
    for pack in packs:
        if isinstance(pack, dict) and pack.get("id") in by_id:
            for key in _SERVICE_KEYS:
                pack[key] = by_id[pack["id"]][key]


def find_pack(packs: list[dict], pack_id: str) -> tuple[int, dict | None]:
    for index, pack in enumerate(packs):
        if pack["id"] == str(pack_id):
            return index, pack
    return -1, None


def get_pack(pack_id: str) -> dict | None:
    return find_pack(load_packs(), pack_id)[1]


def new_pack(name: str, existing: list[dict]) -> dict:
    taken = {p["id"] for p in existing}
    pack_id = uuid.uuid4().hex[:8]
    while pack_id in taken:
        pack_id = uuid.uuid4().hex[:8]
    return normalize_pack({
        "id": pack_id,
        "name": name,
        "enabled": True,
        "keyphrases": [],
        "mode": MODE_INTERVAL,
        "interval_hours": DEFAULT_INTERVAL_HOURS,
        "timings": [],
        "position_schedule": [],
    })


def is_name_taken(name: str, packs: list[dict], except_id: str | None = None) -> bool:
    key = " ".join(str(name or "").split()).lower()
    return any(p["name"].lower() == key and p["id"] != except_id for p in packs)


# ── Подбор лотов ──

def name_matches(item_name: str, keyphrases: list[str]) -> bool:
    name = str(item_name or "").lower()
    return any(phrase.lower() in name for phrase in keyphrases if phrase)


def is_excluded(item_name: str, excluded_entries) -> bool:
    """Общий список «Исключенные» автоподнятия: [[фраза, …], …]."""
    for entry in excluded_entries or []:
        phrases = entry if isinstance(entry, list) else [entry]
        if name_matches(item_name, [str(p) for p in phrases]):
            return True
    return False


def is_working(pack: dict) -> bool:
    """Пак участвует в подборе лотов: включён и есть хотя бы одна фраза."""
    return bool(pack.get("enabled")) and bool(pack.get("keyphrases"))


def find_pack_for_item(item_name: str, packs: list[dict], force_enabled_id: str | None = None) -> dict | None:
    """
    Первый работающий пак по порядку, под фразы которого подходит лот.
    force_enabled_id — считать этот пак включённым (для просмотра/ручного поднятия выключенного пака).
    """
    for pack in packs:
        enabled = pack.get("enabled") or pack["id"] == force_enabled_id
        if enabled and pack.get("keyphrases") and name_matches(item_name, pack["keyphrases"]):
            return pack
    return None


def is_premium(item) -> bool:
    priority = getattr(item, "priority", None)
    if priority is None:
        return False
    return str(getattr(priority, "name", priority)).upper() != "DEFAULT"


def pack_lots(items, packs: list[dict], pack_id: str, excluded_entries=None) -> dict:
    """
    Разбирает активные лоты аккаунта относительно пака.

    :return: {"raise": [...] — будут подниматься этим паком,
              "not_premium": [...] — подходят, но без премиум-статуса (бот такие не поднимает),
              "taken": [(item, pack), ...] — подходят, но их забрал пак выше по списку,
              "excluded": [...] — подходят, но в общем списке «Исключенные»}
    """
    result = {"raise": [], "not_premium": [], "taken": [], "excluded": []}
    _, target = find_pack(packs, pack_id)
    if target is None or not target.get("keyphrases"):
        return result
    for item in items or []:
        name = getattr(item, "name", "") or ""
        if not name_matches(name, target["keyphrases"]):
            continue
        if is_excluded(name, excluded_entries):
            result["excluded"].append(item)
            continue
        owner = find_pack_for_item(name, packs, force_enabled_id=pack_id)
        if owner is not None and owner["id"] != pack_id:
            result["taken"].append((item, owner))
            continue
        if not is_premium(item):
            result["not_premium"].append(item)
            continue
        result["raise"].append(item)
    return result


# ── Тайминги ──

def due_timing(timings: list[str], now_minutes: int, window: int = TIMING_WINDOW_MINUTES) -> str | None:
    """Ближайший тайминг, если до него (или после него) не больше window минут, иначе None."""
    slots = [(t, int(t[:2]) * 60 + int(t[3:])) for t in normalize_timings(timings)]
    if not slots:
        return None
    timing, minutes = min(slots, key=lambda slot: abs(now_minutes - slot[1]))
    return timing if abs(now_minutes - minutes) <= window else None


# ── Подписи ──

def schedule_label(pack: dict, max_timings: int = 3, now_minutes: int | None = None) -> str:
    if pack["mode"] == MODE_POSITION:
        if not pack["position_schedule"]:
            return "📊 нет участков"
        segment = active_segment(pack["position_schedule"], msk_minutes() if now_minutes is None else now_minutes)
        if segment is None or segment["position"] is None:
            return "📊 сейчас не поднимает"
        return f"📊 ≤{segment['position']}"
    if pack["mode"] == MODE_TIMING:
        timings = pack["timings"]
        if not timings:
            return "🕒 тайминг не задан"
        shown = ", ".join(timings[:max_timings])
        if len(timings) > max_timings:
            shown += f" (+{len(timings) - max_timings})"
        return f"🕒 {shown}"
    return f"⏱ {format_hours(pack['interval_hours'])} ч"


def format_hours(value: float) -> str:
    value = float(value)
    return str(int(value)) if value.is_integer() else f"{value:g}"



# ── Режим «По позиции»: участки расписания ──

def msk_minutes(now: datetime | None = None) -> int:
    now = now or datetime.now(MSK_TZ)
    return now.hour * 60 + now.minute


def _to_minutes(value: str) -> int:
    return int(value[:2]) * 60 + int(value[3:])


def _fmt_minutes(minutes: int) -> str:
    minutes %= DAY_MINUTES
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _normalize_segment_time(raw) -> str | None:
    value = str(raw or "").strip()
    if value in ("24", "24:00", "24:0"):
        return "00:00"
    return normalize_timing(value)


def _normalize_position(raw) -> int | None:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if 1 <= value <= MAX_POSITION else None


def _normalize_cooldown(raw) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_COOLDOWN_MINUTES
    return min(max(value, MIN_COOLDOWN_MINUTES), MAX_COOLDOWN_MINUTES)


def normalize_segment(raw) -> dict | None:
    if not isinstance(raw, dict):
        return None
    start = _normalize_segment_time(raw.get("start"))
    end = _normalize_segment_time(raw.get("end"))
    try:
        segment_id = int(raw.get("id"))
    except (TypeError, ValueError):
        return None
    if start is None or end is None or segment_id < 1:
        return None
    return {
        "id": segment_id,
        "start": start,
        "end": end,
        "position": _normalize_position(raw.get("position")),
        "cooldown_minutes": _normalize_cooldown(raw.get("cooldown_minutes", DEFAULT_COOLDOWN_MINUTES)),
        "base": bool(raw.get("base", False)),
    }


def sort_schedule(schedule: list[dict]) -> list[dict]:
    return sorted(schedule, key=lambda seg: (_to_minutes(seg["start"]), seg["id"]))


def normalize_schedule(raw) -> list[dict]:
    if not isinstance(raw, list):
        return []
    result: list[dict] = []
    seen: set[int] = set()
    for item in raw:
        segment = normalize_segment(item)
        if segment and segment["id"] not in seen:
            seen.add(segment["id"])
            result.append(segment)
    return sort_schedule(result)[:MAX_SEGMENTS * 2]


def is_full_day(segment: dict) -> bool:
    return segment["start"] == segment["end"]


def _wraps(start: int, end: int) -> bool:
    """Участок переходит через полночь (весь день не с 00:00 — тоже)."""
    return start > end or (start == end and start != 0)


def _linear(start: int, end: int) -> list[tuple[int, int]]:
    """Участок как отрезки внутри суток [a, b)."""
    if start == end:
        return [(0, DAY_MINUTES)]
    if start < end:
        return [(start, end)]
    parts = [(start, DAY_MINUTES)]
    if end > 0:
        parts.append((0, end))
    return parts


def segment_intervals(segment: dict) -> list[tuple[int, int]]:
    return _linear(_to_minutes(segment["start"]), _to_minutes(segment["end"]))


def _subtract(parts: list[tuple[int, int]], cut: list[tuple[int, int]]) -> list[tuple[int, int]]:
    result = list(parts)
    for cut_start, cut_end in cut:
        next_result = []
        for start, end in result:
            if cut_end <= start or cut_start >= end:
                next_result.append((start, end))
                continue
            if start < cut_start:
                next_result.append((start, cut_start))
            if cut_end < end:
                next_result.append((cut_end, end))
        result = next_result
    return sorted(result)


def _merge(parts: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[list[int]] = []
    for start, end in sorted(parts):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(a, b) for a, b in merged]


def _pieces(parts: list[tuple[int, int]], join_midnight: bool) -> list[tuple[int, int]]:
    """Отрезки → участки (start, end) в минутах; кусок через полночь склеивается обратно."""
    parts = _merge(parts)
    if join_midnight and len(parts) > 1 and parts[0][0] == 0 and parts[-1][1] == DAY_MINUTES:
        parts = parts[1:-1] + [(parts[-1][0], parts[0][1])]
    result = []
    for start, end in parts:
        if (start, end) == (0, DAY_MINUTES):
            result.append((0, 0))
        else:
            result.append((start, end % DAY_MINUTES))
    return result


def next_segment_id(schedule: list[dict]) -> int:
    return max((seg["id"] for seg in schedule), default=0) + 1


def find_segment(schedule: list[dict], segment_id: int) -> dict | None:
    return next((seg for seg in schedule if seg["id"] == int(segment_id)), None)


def make_segment(schedule: list[dict], start: int, end: int, position: int | None,
                 cooldown_minutes: int = DEFAULT_COOLDOWN_MINUTES, base: bool = False) -> dict:
    return normalize_segment({
        "id": next_segment_id(schedule),
        "start": _fmt_minutes(start),
        "end": _fmt_minutes(end),
        "position": position,
        "cooldown_minutes": cooldown_minutes,
        "base": base,
    })


def base_schedule(position: int) -> list[dict]:
    """Стартовое расписание при первом переключении на «По позиции»: весь день, кулдаун 10 мин."""
    return [make_segment([], 0, 0, position, DEFAULT_COOLDOWN_MINUTES, base=True)]


def _cut_by(schedule: list[dict], cut: list[tuple[int, int]], new_ids_from: int) -> tuple[list[dict], list[tuple[dict, list[dict]]]]:
    """
    Вырезает время cut из всех участков.
    :return: (новое расписание, [(старый участок, его куски), …] — только для изменённых не стартовых участков)
    """
    result: list[dict] = []
    changes: list[tuple[dict, list[dict]]] = []
    next_id = new_ids_from
    for segment in schedule:
        before = segment_intervals(segment)
        after = _subtract(before, cut)
        if _merge(after) == _merge(before):
            result.append(segment)
            continue
        start, end = _to_minutes(segment["start"]), _to_minutes(segment["end"])
        pieces = []
        # Куски — в порядке от начала исходного участка («23:00–02:00», потом «03:00–08:00»)
        ordered = sorted(_pieces(after, join_midnight=_wraps(start, end)),
                         key=lambda piece: (piece[0] - start) % DAY_MINUTES)
        for number, (piece_start, piece_end) in enumerate(ordered):
            piece = dict(segment, start=_fmt_minutes(piece_start), end=_fmt_minutes(piece_end))
            if number:
                piece["id"] = next_id
                next_id += 1
            pieces.append(piece)
        result.extend(pieces)
        if not segment["base"]:
            changes.append((segment, pieces))
    return result, changes


def add_segment(schedule: list[dict], segment: dict) -> tuple[list[dict], list[tuple[dict, list[dict]]]]:
    """
    Добавляет участок: он забирает своё время у всех, с кем пересекается.
    :return: (новое расписание, изменения не стартовых участков для уведомления)
    """
    others = [seg for seg in schedule if seg["id"] != segment["id"]]
    new_ids_from = max(next_segment_id(schedule), segment["id"] + 1)
    result, changes = _cut_by(others, segment_intervals(segment), new_ids_from)
    return sort_schedule(result + [segment]), changes


def set_segment_time(schedule: list[dict], segment_id: int, start: int, end: int):
    """Меняет время участка (с урезанием пересекающихся). Нет участка → (schedule, None)."""
    segment = find_segment(schedule, segment_id)
    if segment is None:
        return schedule, None
    updated = dict(segment, start=_fmt_minutes(start), end=_fmt_minutes(end))
    return add_segment(schedule, updated)


def delete_segment(schedule: list[dict], segment_id: int) -> tuple[list[dict], dict | None]:
    """Удаляет участок; его время остаётся пустым (никому не возвращается)."""
    segment = find_segment(schedule, segment_id)
    if segment is None:
        return schedule, None
    return [seg for seg in schedule if seg["id"] != segment["id"]], segment


def active_segment(schedule: list[dict], now_minutes: int) -> dict | None:
    """Участок, который действует в момент now_minutes (минуты от 00:00 МСК); None — пустое время."""
    for segment in schedule:
        if any(start <= now_minutes < end for start, end in segment_intervals(segment)):
            return segment
    return None


def schedule_gaps(schedule: list[dict]) -> list[tuple[int, int]]:
    """Пустое время (в него ничего не поднимается) как участки (start, end) в минутах."""
    covered = [part for seg in schedule for part in segment_intervals(seg)]
    gaps = _subtract([(0, DAY_MINUTES)], _merge(covered))
    if not gaps:
        return []
    return _pieces(gaps, join_midnight=True)


def schedule_entries(schedule: list[dict]) -> list[tuple[str, object]]:
    """Участки и пустое время по порядку суток: [("segment", seg) | ("gap", (start, end)), …]."""
    entries = [(_to_minutes(seg["start"]), "segment", seg) for seg in schedule]
    entries += [(start, "gap", (start, end)) for start, end in schedule_gaps(schedule)]
    entries.sort(key=lambda entry: entry[0])
    return [(kind, value) for _, kind, value in entries]


def has_raising_segments(schedule: list[dict]) -> bool:
    return any(seg["position"] is not None for seg in schedule)


# ── Режим «По позиции»: ввод и подписи ──

_RANGE_RE = re.compile(
    r"^(?:с\s*)?(\d{1,2})(?:[:.](\d{2}))?\s*(?:-|–|—|до|по)\s*(\d{1,2})(?:[:.](\d{2}))?$"
)
_FULL_DAY_WORDS = {"весь день", "целый день", "круглосуточно", "сутки", "0-24", "00:00-24:00", "00-24"}


def parse_time_range(text: str) -> tuple[int, int]:
    """
    «15-20», «15:30-20:00», «с 23 до 8», «весь день» → (start, end) в минутах.
    Весь день — (0, 0). Ошибка → ValueError с текстом для пользователя.
    """
    value = " ".join(str(text or "").lower().split())
    if value.replace(" ", "") in _FULL_DAY_WORDS or value in _FULL_DAY_WORDS:
        return 0, 0
    match = _RANGE_RE.match(value)
    if not match:
        raise ValueError(
            "❌ Не понял время. Примеры: <code>15-20</code>, <code>15:30-20:00</code>, "
            "<code>23-8</code> (через полночь), <code>весь день</code>"
        )
    start_h, start_m, end_h, end_m = (int(part) if part else 0 for part in match.groups())
    if not (0 <= start_h <= 23 and 0 <= start_m <= 59):
        raise ValueError("❌ Начало участка должно быть от 00:00 до 23:59")
    if not (0 <= end_h <= 24 and 0 <= end_m <= 59) or (end_h == 24 and end_m):
        raise ValueError("❌ Конец участка должен быть от 00:00 до 24:00")
    start = start_h * 60 + start_m
    end = (end_h * 60 + end_m) % DAY_MINUTES
    if start == end and not (start == 0 and end_h == 24):
        raise ValueError("❌ Начало и конец совпадают. Для всего дня напишите <code>весь день</code>")
    return start, end


def parse_position(text: str) -> int:
    value = str(text or "").strip().lstrip("№#").strip()
    if not value.isdigit():
        raise ValueError("❌ Введите место числом, например <code>10</code>")
    position = int(value)
    if not 1 <= position <= MAX_POSITION:
        raise ValueError(f"❌ Место должно быть от 1 до {MAX_POSITION}")
    return position


def parse_cooldown(text: str) -> int:
    value = str(text or "").strip().lower()
    for suffix in ("минуты", "минут", "минута", "мин.", "мин", "м"):
        if value.endswith(suffix):
            value = value[: -len(suffix)].strip()
            break
    if not value.isdigit():
        raise ValueError("❌ Введите кулдаун в минутах целым числом, например <code>10</code>")
    minutes = int(value)
    if minutes < MIN_COOLDOWN_MINUTES:
        raise ValueError(f"❌ Кулдаун не может быть меньше {MIN_COOLDOWN_MINUTES} минут")
    if minutes > MAX_COOLDOWN_MINUTES:
        raise ValueError(f"❌ Кулдаун не может быть больше {MAX_COOLDOWN_MINUTES // 60 // 24} дней")
    return minutes


def cooldown_needs_confirm(minutes: int) -> bool:
    return minutes < CONFIRM_COOLDOWN_BELOW_MINUTES


def format_range(start, end) -> str:
    """Участок для показа: «15:00–20:00», «20:00–24:00», «весь день»."""
    start_min = start if isinstance(start, int) else _to_minutes(start)
    end_min = end if isinstance(end, int) else _to_minutes(end)
    if start_min == end_min:
        return "весь день" if start_min == 0 else f"весь день с {_fmt_minutes(start_min)}"
    end_text = "24:00" if end_min == 0 else _fmt_minutes(end_min)
    return f"{_fmt_minutes(start_min)}–{end_text}"


def segment_range(segment: dict) -> str:
    return format_range(segment["start"], segment["end"])


def format_cooldown(minutes: int) -> str:
    minutes = int(minutes)
    hours, rest = divmod(minutes, 60)
    if not hours:
        return f"{rest} мин"
    return f"{hours} ч" + (f" {rest} мин" if rest else "")


def segment_summary(segment: dict) -> str:
    if segment["position"] is None:
        return "🚫 не поднимать"
    return f"место ≤ {segment['position']}, кулдаун {format_cooldown(segment['cooldown_minutes'])}"


def describe_changes(changes: list[tuple[dict, list[dict]]]) -> list[str]:
    """Строки уведомления: как урезались другие (не стартовые) участки."""
    lines = []
    for old, pieces in changes:
        old_range = segment_range(old)
        if not pieces:
            lines.append(f"• {old_range} — удалён (перекрыт полностью)")
        elif len(pieces) == 1:
            lines.append(f"• {old_range} → {segment_range(pieces[0])}")
        else:
            parts = [segment_range(piece) for piece in pieces]
            lines.append(f"• {old_range} → разделён на {', '.join(parts[:-1])} и {parts[-1]}")
    return lines


def pause_left_seconds(pack: dict, now: float | None = None) -> float:
    """Сколько ещё длится пауза после изменения настроек (0 — пак работает)."""
    now = time.time() if now is None else now
    return max(0.0, pack.get("changed_at", 0.0) + SETTINGS_PAUSE_SECONDS - now)


def paused_seconds(pack: dict, start: float, end: float) -> float:
    """Сколько секунд из промежутка [start, end] пак простоял на паузе после изменений."""
    total = 0.0
    for window_start, window_end in pack.get("pause_windows") or []:
        total += max(0.0, min(end, window_end) - max(start, window_start))
    return total


def cooldown_left_seconds(pack: dict, last_raise: float | None, cooldown_minutes: int,
                          now: float | None = None) -> float:
    """
    Сколько ещё длится кулдаун лота. Время пауз после изменения настроек пака не засчитывается:
    если до изменения оставалось 4 минуты кулдауна, после 3-минутной паузы останутся те же 4 минуты.
    """
    if last_raise is None:
        return 0.0
    now = time.time() if now is None else now
    passed = now - last_raise - paused_seconds(pack, last_raise, now)
    return max(0.0, cooldown_minutes * 60 - passed)


def cooldown_hourly_max(minutes: int) -> int:
    """Сколько раз в час лот может подняться при таком кулдауне (проверка — раз в минуту)."""
    return max(1, 60 // max(int(minutes), 1))
