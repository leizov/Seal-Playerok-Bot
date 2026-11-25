"""
Паки автоподнятия.

Пак — группа лотов со своими ключевыми фразами и своим расписанием (интервал или тайминги).
Лот попадает в пак, если в его названии есть хотя бы одна фраза пака (регистр не важен).
Если лот подходит под несколько паков, работает первый включённый пак по порядку в списке.

Файл: bot_settings/auto_raise_packs.json — список паков:
    {"id": "1a2b3c4d", "name": "Duolingo", "enabled": true, "keyphrases": ["duolingo"],
     "mode": "interval", "interval_hours": 24.0, "timings": ["12:00"]}
"""

from __future__ import annotations

import uuid

from settings import Settings as sett


SETTINGS_NAME = "auto_raise_packs"

SOURCE_LOTS = "lots"
SOURCE_PACKS = "packs"

MODE_INTERVAL = "interval"
MODE_TIMING = "timing"

DEFAULT_INTERVAL_HOURS = 24.0
MAX_INTERVAL_HOURS = 8760.0
MAX_NAME_LENGTH = 40
TIMING_WINDOW_MINUTES = 5


# ── Нормализация ──

def normalize_source(raw) -> str:
    """Тип настройки автоподнятия: «Все лоты» (lots) или «Паки» (packs)."""
    value = str(raw or "").strip().lower()
    return SOURCE_PACKS if value == SOURCE_PACKS else SOURCE_LOTS


def normalize_mode(raw) -> str:
    value = str(raw or "").strip().lower()
    return MODE_TIMING if value == MODE_TIMING else MODE_INTERVAL


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
    }


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


def save_packs(packs: list[dict]):
    sett.set(SETTINGS_NAME, normalize_packs(packs))


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

def schedule_label(pack: dict, max_timings: int = 3) -> str:
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
