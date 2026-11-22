"""
Выгрузка и загрузка авто-выдач (без привязки к Telegram).

Форматы:
• .json — {"schema": "seal_auto_deliveries", "version": 1, "auto_deliveries": [...]};
  при загрузке также принимается «сырой» bot_settings/auto_deliveries.json (просто список).
• .txt  — читаемый файл: блоки [МУЛЬТИВЫДАЧА] / [ОБЫЧНАЯ] с ключевыми фразами,
  статусом, форматом (для мультивыдачи) и товарами / текстом сообщения.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from typing import Any

from core.auto_deliveries import (
    AUTO_DELIVERY_KIND_MULTI,
    AUTO_DELIVERY_KIND_STATIC,
    GOOD_PLACEHOLDER,
    LEGACY_MULTI_FORMAT,
    LINE_BREAK_TOKEN,
    normalize_auto_delivery,
)


EXPORT_SCHEMA = "seal_auto_deliveries"
EXPORT_VERSION = 1

TXT_MULTI_MARKER = "[МУЛЬТИВЫДАЧА]"
TXT_STATIC_MARKER = "[ОБЫЧНАЯ]"

_MARKERS = {
    "[МУЛЬТИВЫДАЧА]": AUTO_DELIVERY_KIND_MULTI,
    "[МУЛЬТИ]": AUTO_DELIVERY_KIND_MULTI,
    "[MULTI]": AUTO_DELIVERY_KIND_MULTI,
    "[ОБЫЧНАЯ]": AUTO_DELIVERY_KIND_STATIC,
    "[STATIC]": AUTO_DELIVERY_KIND_STATIC,
}

_FIELD_KEYPHRASES = "ключевые фразы"
_FIELD_STATUS = "статус"
_FIELD_FORMAT = "формат"
_ITEMS_HEADER_RE = re.compile(r"^товары\s*(\(\s*\d+\s*\))?\s*:\s*$", re.IGNORECASE)
_MESSAGE_HEADER_RE = re.compile(r"^сообщение\s*:\s*$", re.IGNORECASE)

_STATUS_ON = {"включена", "включено", "вкл", "да", "on", "true", "1", "enabled"}
_STATUS_OFF = {"выключена", "выключено", "выкл", "нет", "off", "false", "0", "disabled"}

DECISION_REPLACE = "replace"
DECISION_SKIP = "skip"


class AutoDeliveryImportError(ValueError):
    """Файл загрузки не удалось разобрать. Текст ошибки показывается пользователю."""


# ───────────────────────── общие помощники ─────────────────────────

def is_multi(delivery: dict) -> bool:
    return delivery.get("kind") == AUTO_DELIVERY_KIND_MULTI


def keyphrase_key(phrase: str) -> str:
    return " ".join(str(phrase or "").split()).casefold()


def delivery_signature(delivery: dict) -> list[str]:
    """Отпечаток авто-выдачи: тип + ключевые фразы (без учёта регистра и порядка)."""
    phrases = sorted({keyphrase_key(p) for p in delivery.get("keyphrases", []) if keyphrase_key(p)})
    return [str(delivery.get("kind"))] + phrases


def summarize(deliveries: list[dict]) -> dict[str, int]:
    multi = [d for d in deliveries if is_multi(d)]
    return {
        "total": len(deliveries),
        "static": len(deliveries) - len(multi),
        "multi": len(multi),
        "items": sum(len(d.get("items", [])) for d in multi),
    }


def _decode_bytes(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="ignore")


def export_file_name(extension: str, now: datetime | None = None, suffix: str = "") -> str:
    now = now or datetime.now()
    safe_suffix = re.sub(r"[^\w\-]+", "_", suffix, flags=re.UNICODE).strip("_")[:40]
    middle = f"_{safe_suffix}" if safe_suffix else ""
    return f"auto_deliveries{middle}_{now.strftime('%Y-%m-%d_%H-%M')}.{extension}"


# ───────────────────────── выгрузка ─────────────────────────

def export_entry(delivery: dict) -> dict[str, Any]:
    """Чистая запись для файла: без счётчиков выдачи."""
    d = normalize_auto_delivery(delivery)
    entry: dict[str, Any] = {
        "kind": d["kind"],
        "enabled": d["enabled"],
        "keyphrases": list(d["keyphrases"]),
    }
    if is_multi(d):
        entry["format"] = d["format"]
        entry["items"] = list(d["items"])
    else:
        entry["message"] = list(d["message"])
    return entry


def build_export_json(deliveries: list[dict], now: datetime | None = None) -> str:
    now = now or datetime.now()
    payload = {
        "schema": EXPORT_SCHEMA,
        "version": EXPORT_VERSION,
        "exported_at": now.isoformat(timespec="seconds"),
        "auto_deliveries": [export_entry(d) for d in deliveries],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _one_line(text: str) -> str:
    """Многострочное значение → одна строка с \\n (бот всё равно раскрывает \\n при выдаче)."""
    return LINE_BREAK_TOKEN.join(str(text or "").splitlines())


def build_export_txt(deliveries: list[dict], now: datetime | None = None) -> str:
    now = now or datetime.now()
    stats = summarize(deliveries)
    lines = [
        "# Seal Playerok Bot — выгрузка авто-выдач",
        f"# Дата выгрузки: {now.strftime('%d.%m.%Y %H:%M')}",
        f"# Авто-выдач: {stats['total']} (обычных: {stats['static']}, мультивыдач: {stats['multi']}), "
        f"товаров в мультивыдачах: {stats['items']}",
        "#",
        "# Как устроен файл (его можно править и загружать обратно):",
        f"#  • каждая авто-выдача начинается со строки {TXT_MULTI_MARKER} или {TXT_STATIC_MARKER},",
        "#    перед ней — пустая строка;",
        "#  • «Ключевые фразы:» — через запятую;",
        "#  • «Статус:» — включена / выключена;",
        f"#  • «Формат:» (мультивыдача) — сообщение покупателю, {GOOD_PLACEHOLDER} = товар, {LINE_BREAK_TOKEN} = перенос строки;",
        "#  • после «Товары:» — по одному товару в строке;",
        "#  • после «Сообщение:» — текст сообщения обычной авто-выдачи.",
        "#  Строки с # в начале файла — комментарии.",
    ]
    for delivery in deliveries:
        d = export_entry(delivery)
        lines.append("")
        lines.append(TXT_MULTI_MARKER if is_multi(d) else TXT_STATIC_MARKER)
        lines.append(f"Ключевые фразы: {', '.join(d['keyphrases'])}")
        lines.append(f"Статус: {'включена' if d['enabled'] else 'выключена'}")
        if is_multi(d):
            lines.append(f"Формат: {_one_line(d['format'])}")
            lines.append(f"Товары ({len(d['items'])}):")
            lines.extend(d["items"])
        else:
            lines.append("Сообщение:")
            lines.extend(d["message"])
    return "\n".join(lines) + "\n"


def plain_text_lines(delivery: dict) -> list[str]:
    """«Текстом»: только товары (мультивыдача) или только текст сообщения (обычная)."""
    d = normalize_auto_delivery(delivery)
    return list(d["items"]) if is_multi(d) else list(d["message"])


# ───────────────────────── загрузка: разбор ─────────────────────────

def _import_entry(raw: Any, number: int) -> dict[str, Any]:
    """Проверяет и нормализует одну авто-выдачу из файла. number — её номер в файле (с 1)."""
    if not isinstance(raw, dict):
        raise AutoDeliveryImportError(f"❌ Авто-выдача №{number}: ожидался объект, а не {type(raw).__name__}")

    kind = str(raw.get("kind") or "").strip().lower()
    if not kind:
        kind = AUTO_DELIVERY_KIND_MULTI if "items" in raw else AUTO_DELIVERY_KIND_STATIC
    if kind not in (AUTO_DELIVERY_KIND_MULTI, AUTO_DELIVERY_KIND_STATIC):
        raise AutoDeliveryImportError(f"❌ Авто-выдача №{number}: неизвестный тип «{kind}»")

    entry = normalize_auto_delivery({**raw, "kind": kind})
    entry["keyphrases"] = [" ".join(p.split()) for p in entry["keyphrases"] if " ".join(p.split())]
    if not entry["keyphrases"]:
        raise AutoDeliveryImportError(f"❌ Авто-выдача №{number}: не указаны ключевые фразы")

    if kind == AUTO_DELIVERY_KIND_MULTI:
        if GOOD_PLACEHOLDER not in entry["format"]:
            raise AutoDeliveryImportError(
                f"❌ Авто-выдача №{number}: в формате выдачи нет <code>{GOOD_PLACEHOLDER}</code>"
            )
        entry["issued_total"] = 0
        entry["issued_current_batch"] = 0
    elif not entry["message"]:
        raise AutoDeliveryImportError(f"❌ Авто-выдача №{number}: пустой текст сообщения")
    return entry


def parse_import_json(text: str) -> list[dict]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as e:
        raise AutoDeliveryImportError(f"❌ Файл не является корректным JSON (строка {e.lineno}, позиция {e.colno})")

    if isinstance(payload, dict):
        schema = payload.get("schema")
        if schema == "seal_config_backup":
            raise AutoDeliveryImportError(
                "❌ Это backup всей конфигурации. Его загружают в разделе «Backup конфигурации», а не здесь"
            )
        if schema not in (None, EXPORT_SCHEMA):
            raise AutoDeliveryImportError(f"❌ Неизвестный формат файла: <code>{schema}</code>")
        entries = payload.get("auto_deliveries")
    elif isinstance(payload, list):
        entries = payload
    else:
        entries = None

    if not isinstance(entries, list):
        raise AutoDeliveryImportError("❌ В файле не найден список авто-выдач")
    if not entries:
        raise AutoDeliveryImportError("❌ В файле нет ни одной авто-выдачи")
    return [_import_entry(raw, number) for number, raw in enumerate(entries, start=1)]


def _parse_status(value: str, line_no: int) -> bool:
    key = value.strip().casefold()
    if key in _STATUS_ON:
        return True
    if key in _STATUS_OFF:
        return False
    raise AutoDeliveryImportError(f"❌ Строка {line_no}: непонятный статус «{value.strip()}» (нужно: включена / выключена)")


def parse_import_txt(text: str) -> list[dict]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if not any(line.strip().upper() in _MARKERS for line in lines):
        raise AutoDeliveryImportError(
            "❌ В файле не найдено ни одной авто-выдачи.\n"
            f"Каждая авто-выдача должна начинаться со строки <code>{TXT_MULTI_MARKER}</code> или <code>{TXT_STATIC_MARKER}</code>.\n\n"
            "💡 Если это просто список товаров — откройте карточку мультивыдачи и нажмите «➕ Добавить товары»"
        )

    blocks: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    prev_blank = True

    for line_no, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        # Маркер распознаётся в начале файла или после пустой строки: внутри списка товаров
        # пустых строк нет, поэтому товар, похожий на маркер, блок не разорвёт.
        marker_kind = _MARKERS.get(line.upper()) if (prev_blank or current is None) else None
        prev_blank = not line

        if marker_kind:
            current = {"kind": marker_kind, "line": line_no, "fields": {}, "body": None}
            blocks.append(current)
            continue

        if current is None:
            if not line or line.startswith("#"):
                continue
            raise AutoDeliveryImportError(
                f"❌ Строка {line_no}: ожидалось начало авто-выдачи "
                f"(<code>{TXT_MULTI_MARKER}</code> или <code>{TXT_STATIC_MARKER}</code>)"
            )

        if current["body"] is not None:
            if line:
                current["body"].append(line)
            continue

        if not line:
            continue
        if (current["kind"] == AUTO_DELIVERY_KIND_MULTI and _ITEMS_HEADER_RE.match(line)) or (
            current["kind"] == AUTO_DELIVERY_KIND_STATIC and _MESSAGE_HEADER_RE.match(line)
        ):
            current["body"] = []
            continue

        key, sep, value = line.partition(":")
        key = key.strip().casefold()
        if not sep or key not in (_FIELD_KEYPHRASES, _FIELD_STATUS, _FIELD_FORMAT):
            expected = "«Товары:»" if current["kind"] == AUTO_DELIVERY_KIND_MULTI else "«Сообщение:»"
            raise AutoDeliveryImportError(
                f"❌ Строка {line_no}: непонятная строка <code>{_cut_for_error(line)}</code>. "
                f"Ожидались поля «Ключевые фразы:», «Статус:»"
                + (", «Формат:»" if current["kind"] == AUTO_DELIVERY_KIND_MULTI else "")
                + f" и затем {expected}"
            )
        if key == _FIELD_FORMAT and current["kind"] != AUTO_DELIVERY_KIND_MULTI:
            raise AutoDeliveryImportError(f"❌ Строка {line_no}: «Формат:» бывает только у мультивыдачи")
        current["fields"][key] = (value.strip(), line_no)

    result = []
    for number, block in enumerate(blocks, start=1):
        fields = block["fields"]
        if _FIELD_KEYPHRASES not in fields:
            raise AutoDeliveryImportError(f"❌ Авто-выдача №{number} (строка {block['line']}): нет строки «Ключевые фразы:»")
        raw: dict[str, Any] = {
            "kind": block["kind"],
            "keyphrases": [p.strip() for p in fields[_FIELD_KEYPHRASES][0].split(",") if p.strip()],
        }
        if _FIELD_STATUS in fields:
            raw["enabled"] = _parse_status(*fields[_FIELD_STATUS])
        body = block["body"] or []
        if block["kind"] == AUTO_DELIVERY_KIND_MULTI:
            raw["format"] = fields[_FIELD_FORMAT][0] if _FIELD_FORMAT in fields else LEGACY_MULTI_FORMAT
            raw["items"] = body
        else:
            if block["body"] is None:
                raise AutoDeliveryImportError(f"❌ Авто-выдача №{number} (строка {block['line']}): нет строки «Сообщение:»")
            raw["message"] = body
        result.append(_import_entry(raw, number))
    return result


def _cut_for_error(text: str, limit: int = 60) -> str:
    from html import escape

    return escape(text if len(text) <= limit else text[: limit - 1] + "…")


def parse_import_file(file_name: str, content: bytes) -> list[dict]:
    name = (file_name or "").lower()
    text = _decode_bytes(content)
    if name.endswith(".json"):
        return parse_import_json(text)
    if name.endswith(".txt"):
        return parse_import_txt(text)
    raise AutoDeliveryImportError("❌ Поддерживаются только файлы <b>.txt</b> и <b>.json</b>")


# ───────────────────────── загрузка: пересечения и применение ─────────────────────────

def find_conflicts(current: list[dict], imported: list[dict]) -> list[dict]:
    """
    Пересечение — общая ключевая фраза (без учёта регистра) у загружаемой и существующей авто-выдачи.
    Возвращает [{"import_index": i, "existing": [j, ...], "common": [фразы]}] по порядку файла.
    """
    current_keys = [{keyphrase_key(p) for p in d.get("keyphrases", [])} for d in current]
    conflicts = []
    for i, entry in enumerate(imported):
        imported_keys = {keyphrase_key(p): p for p in entry.get("keyphrases", [])}
        existing, common = [], []
        for j, keys in enumerate(current_keys):
            shared = [phrase for key, phrase in imported_keys.items() if key in keys]
            if shared:
                existing.append(j)
                common.extend(p for p in shared if p not in common)
        if existing:
            conflicts.append({"import_index": i, "existing": existing, "common": common})
    return conflicts


def find_internal_duplicates(imported: list[dict]) -> list[tuple[int, int]]:
    """Пары (i, j) авто-выдач внутри файла с общей ключевой фразой."""
    keys = [{keyphrase_key(p) for p in d.get("keyphrases", [])} for d in imported]
    return [(i, j) for i in range(len(keys)) for j in range(i + 1, len(keys)) if keys[i] & keys[j]]


def apply_import(current: list[dict], imported: list[dict], decisions: dict[int, str]) -> tuple[list[dict], dict[str, int]]:
    """
    Применяет загрузку к актуальному списку.
    • без пересечений — авто-выдача добавляется в конец;
    • «заменить» — встаёт на место первой пересекающейся, все пересекающиеся удаляются;
    • «пропустить» — ничего не меняется.
    Если появилось пересечение, по которому не было решения, — ошибка (список изменился).
    """
    conflicts = {c["import_index"]: c["existing"] for c in find_conflicts(current, imported)}
    removed: set[int] = set()
    insert_at: dict[int, list[dict]] = {}
    appended: list[dict] = []
    stats = {"added": 0, "replaced": 0, "skipped": 0, "removed_existing": 0}

    for i, entry in enumerate(imported):
        targets = conflicts.get(i)
        if not targets:
            appended.append(entry)
            stats["added"] += 1
            continue
        decision = decisions.get(i)
        if decision == DECISION_REPLACE:
            insert_at.setdefault(min(targets), []).append(entry)
            removed.update(targets)
            stats["replaced"] += 1
        elif decision == DECISION_SKIP:
            stats["skipped"] += 1
        else:
            raise AutoDeliveryImportError(
                "❌ Пока вы выбирали, список авто-выдач изменился и появились новые пересечения. "
                "Загрузите файл ещё раз"
            )

    result: list[dict] = []
    for j, delivery in enumerate(current):
        result.extend(insert_at.get(j, []))
        if j not in removed:
            result.append(delivery)
    result.extend(appended)
    stats["removed_existing"] = len(removed)
    return result, stats


# ───────────────────────── удаление выгруженных товаров ─────────────────────────

def remove_items_by_value(items: list[str], to_remove: list[str]) -> tuple[list[str], list[str]]:
    """Убирает из items ровно те строки (с учётом повторов), что есть в to_remove."""
    pending = Counter(to_remove)
    kept, removed = [], []
    for item in items:
        if pending[item] > 0:
            pending[item] -= 1
            removed.append(item)
        else:
            kept.append(item)
    return kept, removed


def find_delivery_index(deliveries: list[dict], signature: list[str], hint: int | None = None) -> int | None:
    """Ищет авто-выдачу по отпечатку; сначала проверяет индекс-подсказку."""
    if hint is not None and 0 <= hint < len(deliveries) and delivery_signature(deliveries[hint]) == signature:
        return hint
    for idx, delivery in enumerate(deliveries):
        if delivery_signature(delivery) == signature:
            return idx
    return None


def remove_exported_items(deliveries: list[dict], snapshot: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    snapshot: [{"index": int, "signature": [...], "items": [...]}] — что попало в выгрузку.
    Возвращает (новый список, отчёт [{"index", "signature", "keyphrases", "removed": [...], "remaining": int}]).
    """
    report = []
    for snap in snapshot:
        idx = find_delivery_index(deliveries, snap["signature"], snap.get("index"))
        if idx is None or not is_multi(deliveries[idx]):
            report.append({**snap, "keyphrases": snap["signature"][1:], "removed": [], "remaining": 0, "missing": True})
            continue
        delivery = deliveries[idx]
        kept, removed = remove_items_by_value(delivery.get("items", []), snap["items"])
        delivery["items"] = kept
        report.append({
            "index": idx,
            "signature": snap["signature"],
            "keyphrases": list(delivery.get("keyphrases", [])),
            "removed": removed,
            "remaining": len(kept),
            "missing": False,
        })
    return deliveries, report


def restore_removed_items(deliveries: list[dict], report: list[dict]) -> list[dict]:
    """Откат удаления (если файл не удалось отправить): возвращает строки в начало остатка."""
    for entry in report:
        if not entry.get("removed"):
            continue
        idx = find_delivery_index(deliveries, entry["signature"], entry.get("index"))
        if idx is None or not is_multi(deliveries[idx]):
            continue
        deliveries[idx]["items"] = list(entry["removed"]) + list(deliveries[idx].get("items", []))
    return deliveries
