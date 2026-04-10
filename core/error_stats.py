from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import paths


RETENTION_DAYS = 10
MAX_EVENTS_PER_DAY = 5000
MAX_TEXT_SAMPLE_LEN = 300
PLAYEROK_HEALTH_WINDOW_SECONDS = 10 * 60
PLAYEROK_HEALTH_FATAL_STREAK_THRESHOLD = 5
PLAYEROK_HEALTH_MAX_ERRORS = 2000
PLAYEROK_HEALTH_VERSION = 1

_LOCK = threading.RLock()
_DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SPACE_RE = re.compile(r"\s+")
_HEALTH_GREEN_CIRCLE = "\U0001F7E2"
_HEALTH_WHITE_CIRCLE = "\u26AA"

_KIND_TIMEOUT = "timeout"
_KIND_HTTP_429 = "http_429"
_KIND_HTTP_5XX = "http_5xx"
_KIND_GRAPHQL_429 = "graphql_429"
_KIND_GRAPHQL_5XX = "graphql_5xx"
_KIND_CLOUDFLARE = "cloudflare"
_KIND_OTHER = "other"

_BY_KIND_KEYS = (
    _KIND_TIMEOUT,
    _KIND_HTTP_429,
    _KIND_HTTP_5XX,
    _KIND_GRAPHQL_429,
    _KIND_GRAPHQL_5XX,
    _KIND_CLOUDFLARE,
    _KIND_OTHER,
)

_SANITIZE_PATTERNS = (
    (re.compile(r"(?i)(token=)[^;\s]+"), r"\1***"),
    (re.compile(r"(?i)(authorization:\s*bearer\s+)[^\s]+"), r"\1***"),
    (re.compile(r"(?i)(cookie:\s*)[^\n]+"), r"\1***"),
)


def _playerok_health_path() -> str:
    configured = getattr(paths, "PLAYEROK_CONNECTION_HEALTH_FILE", None)
    if configured:
        return configured
    base = getattr(paths, "BOT_DATA_DIR", ".")
    return os.path.join(base, "playerok_connection_health.json")


def _default_playerok_health_payload(now: datetime | None = None) -> dict[str, Any]:
    ts = (now or _now()).isoformat(timespec="seconds")
    return {
        "version": PLAYEROK_HEALTH_VERSION,
        "window_seconds": PLAYEROK_HEALTH_WINDOW_SECONDS,
        "errors": [],
        "fatal_streak": 0,
        "incident_active": False,
        "updated_at": ts,
    }


def _safe_ts(dt: datetime | None) -> float | None:
    if dt is None:
        return None
    try:
        return dt.timestamp()
    except Exception:
        return None


def _prune_health_errors(payload: dict[str, Any], now: datetime | None = None) -> None:
    ts_now = _safe_ts(now or _now())
    if ts_now is None:
        payload["errors"] = []
        return

    min_ts = ts_now - float(PLAYEROK_HEALTH_WINDOW_SECONDS)
    cleaned: list[str] = []
    raw_errors = payload.get("errors", [])
    if not isinstance(raw_errors, list):
        raw_errors = []

    for item in raw_errors:
        parsed = _parse_iso(str(item))
        ts_item = _safe_ts(parsed)
        if ts_item is None:
            continue
        if ts_item >= min_ts:
            cleaned.append(datetime.fromtimestamp(ts_item).isoformat(timespec="seconds"))

    if len(cleaned) > PLAYEROK_HEALTH_MAX_ERRORS:
        cleaned = cleaned[-PLAYEROK_HEALTH_MAX_ERRORS:]
    payload["errors"] = cleaned


def _load_playerok_health(now: datetime | None = None) -> dict[str, Any]:
    path = _playerok_health_path()
    payload = _default_playerok_health_payload(now)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                payload.update(loaded)
        except Exception:
            pass

    payload["version"] = PLAYEROK_HEALTH_VERSION
    payload["window_seconds"] = PLAYEROK_HEALTH_WINDOW_SECONDS
    payload["fatal_streak"] = max(0, _safe_int(payload.get("fatal_streak")) or 0)
    payload["incident_active"] = bool(payload.get("incident_active"))
    _prune_health_errors(payload, now)
    return payload


def _save_playerok_health(payload: dict[str, Any]) -> None:
    path = _playerok_health_path()
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _health_level(errors_10m: int, incident_active: bool) -> int:
    if incident_active or errors_10m >= 25:
        return 1
    if errors_10m >= 13:
        return 2
    if errors_10m >= 6:
        return 3
    if errors_10m >= 1:
        return 4
    return 5


def _health_circles(level: int) -> str:
    normalized = max(1, min(5, int(level)))
    return (_HEALTH_GREEN_CIRCLE * normalized) + (_HEALTH_WHITE_CIRCLE * (5 - normalized))


def _health_snapshot(payload: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    _prune_health_errors(payload, now)
    errors_10m = len(payload.get("errors", []))
    fatal_streak = max(0, _safe_int(payload.get("fatal_streak")) or 0)
    incident_active = bool(payload.get("incident_active"))
    level = _health_level(errors_10m, incident_active)
    return {
        "window_minutes": int(PLAYEROK_HEALTH_WINDOW_SECONDS / 60),
        "errors_10m": errors_10m,
        "fatal_streak": fatal_streak,
        "incident_active": incident_active,
        "level": level,
        "circles": _health_circles(level),
        "updated_at": payload.get("updated_at"),
    }


def _now() -> datetime:
    return datetime.now()


def _ensure_dir() -> None:
    os.makedirs(_error_stats_dir(), exist_ok=True)


def _error_stats_dir() -> str:
    configured = getattr(paths, "ERROR_STATS_DIR", None)
    if configured:
        return configured
    base = getattr(paths, "BOT_DATA_DIR", ".")
    return os.path.join(base, "error_stats")


def _day_key(dt: datetime | None = None) -> str:
    return (dt or _now()).strftime("%Y-%m-%d")


def _day_path(day: str) -> str:
    return os.path.join(_error_stats_dir(), f"{day}.json")


def _is_valid_day(day: str) -> bool:
    return bool(_DAY_RE.match(day))


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _sanitize_text(text: str) -> str:
    sanitized = text
    for pattern, replacement in _SANITIZE_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    sanitized = _SPACE_RE.sub(" ", sanitized).strip()
    return sanitized


def _sanitize_url(url: str) -> str:
    try:
        parsed = urlparse(url or "")
        host = parsed.netloc or ""
        path = parsed.path or ""
        if host or path:
            return f"{host}{path}"
    except Exception:
        pass
    return (url or "").strip()


def _normalize_for_fp(text: str) -> str:
    return _SPACE_RE.sub(" ", (text or "").lower()).strip()


def _build_fingerprint(
    *,
    kind: str,
    method: str,
    url: str,
    status_code: int | None,
    error_code: str | None,
    error_text: str,
) -> str:
    base = "|".join(
        [
            kind,
            method.upper(),
            _sanitize_url(url),
            str(status_code or ""),
            str(error_code or ""),
            _normalize_for_fp(error_text)[:350],
        ]
    )
    return hashlib.sha1(base.encode("utf-8", errors="ignore")).hexdigest()[:20]


def _default_day_payload(day: str) -> dict[str, Any]:
    return {
        "date": day,
        "total_events": 0,
        "unique_errors": 0,
        "by_kind": {k: 0 for k in _BY_KIND_KEYS},
        "errors": {},
        "events": [],
    }


def _load_day(day: str) -> dict[str, Any]:
    path = _day_path(day)
    if not os.path.exists(path):
        return _default_day_payload(day)
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if not isinstance(payload, dict):
            return _default_day_payload(day)
        payload.setdefault("date", day)
        payload.setdefault("total_events", 0)
        payload.setdefault("unique_errors", 0)
        payload.setdefault("errors", {})
        payload.setdefault("events", [])
        by_kind = payload.setdefault("by_kind", {})
        for k in _BY_KIND_KEYS:
            by_kind.setdefault(k, 0)
        return payload
    except Exception:
        return _default_day_payload(day)


def _save_day(day: str, payload: dict[str, Any]) -> None:
    _ensure_dir()
    with open(_day_path(day), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _cleanup_old_files(now: datetime | None = None) -> None:
    _ensure_dir()
    reference = (now or _now()).date()
    oldest_keep = reference - timedelta(days=RETENTION_DAYS - 1)
    stats_dir = _error_stats_dir()
    for file_name in os.listdir(stats_dir):
        if not file_name.endswith(".json"):
            continue
        day = file_name[:-5]
        if not _is_valid_day(day):
            continue
        try:
            day_date = datetime.strptime(day, "%Y-%m-%d").date()
        except Exception:
            continue
        if day_date < oldest_keep:
            try:
                os.remove(os.path.join(stats_dir, file_name))
            except Exception:
                pass


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def _normalize_kind(kind: str | None) -> str:
    if kind in _BY_KIND_KEYS:
        return kind  # type: ignore[return-value]
    return _KIND_OTHER


def _record_playerok_health_error(*, now: datetime, retry_exhausted: bool) -> None:
    payload = _load_playerok_health(now)
    errors = payload.get("errors", [])
    if not isinstance(errors, list):
        errors = []
    errors.append(now.isoformat(timespec="seconds"))
    payload["errors"] = errors

    if retry_exhausted:
        payload["fatal_streak"] = max(0, _safe_int(payload.get("fatal_streak")) or 0) + 1

    payload["incident_active"] = bool(payload.get("incident_active")) or (
        max(0, _safe_int(payload.get("fatal_streak")) or 0) >= PLAYEROK_HEALTH_FATAL_STREAK_THRESHOLD
    )
    payload["updated_at"] = now.isoformat(timespec="seconds")
    _prune_health_errors(payload, now)
    _save_playerok_health(payload)


def record_playerok_request_error(
    *,
    kind: str,
    error_text: str,
    method: str,
    url: str,
    status_code: int | None = None,
    error_code: str | None = None,
    attempt: int | None = None,
    max_attempts: int | None = None,
    retryable: bool = False,
    retry_exhausted: bool = False,
    session_recreated: bool = False,
) -> None:
    now = _now()
    attempt_int = _safe_int(attempt)
    max_attempts_int = _safe_int(max_attempts)
    fatal_for_streak = bool(retry_exhausted)
    if attempt_int is not None and max_attempts_int is not None:
        fatal_for_streak = bool(retry_exhausted) and attempt_int >= max_attempts_int

    day = _day_key(now)
    norm_kind = _normalize_kind(kind)
    clean_text = _sanitize_text(str(error_text or ""))[:MAX_TEXT_SAMPLE_LEN]
    clean_method = (method or "").upper()
    clean_url = _sanitize_url(url or "")
    status_int = _safe_int(status_code)
    fingerprint = _build_fingerprint(
        kind=norm_kind,
        method=clean_method,
        url=clean_url,
        status_code=status_int,
        error_code=error_code,
        error_text=clean_text,
    )

    event = {
        "timestamp": now.isoformat(timespec="seconds"),
        "kind": norm_kind,
        "method": clean_method,
        "url": clean_url,
        "status_code": status_int,
        "error_code": str(error_code or ""),
        "error_text": clean_text,
        "fingerprint": fingerprint,
        "attempt": attempt_int,
        "max_attempts": max_attempts_int,
        "retryable": bool(retryable),
        "retry_exhausted": bool(retry_exhausted),
        "session_recreated": bool(session_recreated),
    }

    with _LOCK:
        try:
            _cleanup_old_files(now)
            payload = _load_day(day)

            payload["total_events"] = int(payload.get("total_events", 0)) + 1
            payload["by_kind"][norm_kind] = int(payload["by_kind"].get(norm_kind, 0)) + 1

            errors = payload.setdefault("errors", {})
            row = errors.get(fingerprint)
            if row is None:
                row = {
                    "fingerprint": fingerprint,
                    "kind": norm_kind,
                    "method": clean_method,
                    "url": clean_url,
                    "status_code": status_int,
                    "error_code": str(error_code or ""),
                    "text_sample": clean_text,
                    "count": 1,
                    "first_seen": event["timestamp"],
                    "last_seen": event["timestamp"],
                    "avg_interval_sec": None,
                    "min_interval_sec": None,
                    "max_interval_sec": None,
                    "_interval_count": 0,
                }
            else:
                row["count"] = int(row.get("count", 0)) + 1
                previous_last = _parse_iso(row.get("last_seen"))
                row["last_seen"] = event["timestamp"]
                if previous_last is not None:
                    interval = max(0.0, (now - previous_last).total_seconds())
                    interval_count = int(row.get("_interval_count", 0)) + 1
                    prev_avg = _safe_float(row.get("avg_interval_sec"))
                    if prev_avg is None:
                        row["avg_interval_sec"] = round(interval, 3)
                    else:
                        row["avg_interval_sec"] = round(
                            ((prev_avg * (interval_count - 1)) + interval) / interval_count,
                            3,
                        )
                    prev_min = _safe_float(row.get("min_interval_sec"))
                    prev_max = _safe_float(row.get("max_interval_sec"))
                    row["min_interval_sec"] = round(interval if prev_min is None else min(prev_min, interval), 3)
                    row["max_interval_sec"] = round(interval if prev_max is None else max(prev_max, interval), 3)
                    row["_interval_count"] = interval_count

            errors[fingerprint] = row
            payload["unique_errors"] = len(errors)

            events = payload.setdefault("events", [])
            events.append(event)
            if len(events) > MAX_EVENTS_PER_DAY:
                payload["events"] = events[-MAX_EVENTS_PER_DAY:]

            _save_day(day, payload)
            _record_playerok_health_error(now=now, retry_exhausted=fatal_for_streak)
        except Exception:
            # Никогда не ломаем основной pipeline из-за статистики ошибок.
            pass


def record_playerok_request_success() -> None:
    now = _now()
    with _LOCK:
        try:
            payload = _load_playerok_health(now)
            payload["fatal_streak"] = 0
            payload["incident_active"] = False
            payload["updated_at"] = now.isoformat(timespec="seconds")
            _prune_health_errors(payload, now)
            _save_playerok_health(payload)
        except Exception:
            # Не прерываем основной workflow из-за метрик стабильности.
            pass


def mark_playerok_startup_fatal_incident() -> None:
    now = _now()
    with _LOCK:
        try:
            payload = _load_playerok_health(now)
            errors = payload.get("errors", [])
            if not isinstance(errors, list):
                errors = []
            errors.append(now.isoformat(timespec="seconds"))
            payload["errors"] = errors
            payload["fatal_streak"] = max(
                PLAYEROK_HEALTH_FATAL_STREAK_THRESHOLD,
                max(0, _safe_int(payload.get("fatal_streak")) or 0),
            )
            payload["incident_active"] = True
            payload["updated_at"] = now.isoformat(timespec="seconds")
            _prune_health_errors(payload, now)
            _save_playerok_health(payload)
        except Exception:
            # Не прерываем основной workflow из-за метрик стабильности.
            pass


def get_playerok_connection_health() -> dict[str, Any]:
    now = _now()
    with _LOCK:
        try:
            payload = _load_playerok_health(now)
            return _health_snapshot(payload, now)
        except Exception:
            fallback = _default_playerok_health_payload(now)
            return _health_snapshot(fallback, now)


def _list_day_files() -> list[str]:
    _ensure_dir()
    stats_dir = _error_stats_dir()
    days: list[str] = []
    for file_name in os.listdir(stats_dir):
        if not file_name.endswith(".json"):
            continue
        day = file_name[:-5]
        if _is_valid_day(day):
            days.append(day)
    days.sort(reverse=True)
    return days


def get_error_stats_overview(days: int = RETENTION_DAYS) -> list[dict[str, Any]]:
    with _LOCK:
        _cleanup_old_files()
        result: list[dict[str, Any]] = []
        for day in _list_day_files()[: max(1, days)]:
            payload = _load_day(day)
            events = payload.get("events", [])
            last_error_time = events[-1]["timestamp"] if events else None
            result.append(
                {
                    "date": day,
                    "total_events": int(payload.get("total_events", 0)),
                    "unique_errors": int(payload.get("unique_errors", 0)),
                    "by_kind": payload.get("by_kind", {}),
                    "last_error_time": last_error_time,
                }
            )
        return result


def get_error_stats_by_date(day: str) -> dict[str, Any]:
    with _LOCK:
        _cleanup_old_files()
        if not _is_valid_day(day):
            return _default_day_payload(_day_key())

        payload = _load_day(day)
        errors_map = payload.get("errors", {})
        errors_list: list[dict[str, Any]] = []
        if isinstance(errors_map, dict):
            for row in errors_map.values():
                if not isinstance(row, dict):
                    continue
                clean_row = dict(row)
                clean_row.pop("_interval_count", None)
                errors_list.append(clean_row)
        errors_list.sort(key=lambda r: int(r.get("count", 0)), reverse=True)

        events = payload.get("events", [])
        recent_events = events[-50:] if isinstance(events, list) else []

        return {
            "date": payload.get("date", day),
            "total_events": int(payload.get("total_events", 0)),
            "unique_errors": int(payload.get("unique_errors", 0)),
            "by_kind": payload.get("by_kind", {k: 0 for k in _BY_KIND_KEYS}),
            "errors": errors_list,
            "recent_events": recent_events,
        }
