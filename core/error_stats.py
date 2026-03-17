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

_LOCK = threading.RLock()
_DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SPACE_RE = re.compile(r"\s+")

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
        "attempt": _safe_int(attempt),
        "max_attempts": _safe_int(max_attempts),
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
        except Exception:
            # Никогда не ломаем основной pipeline из-за статистики ошибок.
            pass


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
