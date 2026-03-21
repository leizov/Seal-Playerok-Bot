from __future__ import annotations

import base64
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from typing import Any

import paths


BACKUP_SCHEMA = "seal_config_backup"
BACKUP_VERSION = 1

_BOT_SETTINGS_EXCLUDED_EXTENSIONS = {".py", ".pyc", ".pyo"}
_PLUGIN_EXCLUDED_EXTENSIONS = {".log"}


def _normalize_rel_path(path: str) -> str:
    return path.replace("\\", "/").strip("/")


def _is_safe_relative_path(path: str) -> bool:
    if not isinstance(path, str) or not path.strip():
        return False
    if path.startswith(("/", "\\")):
        return False
    if re.match(r"^[A-Za-z]:", path):
        return False

    normalized = _normalize_rel_path(path)
    if not normalized:
        return False

    parts = normalized.split("/")
    for part in parts:
        if not part or part in {".", ".."}:
            return False
        if ":" in part or "\x00" in part:
            return False
    return True


def _resolve_path_inside_root(root: str, rel_path: str) -> str:
    normalized = _normalize_rel_path(rel_path)
    if not _is_safe_relative_path(normalized):
        raise ValueError(f"Unsafe relative path: {rel_path!r}")

    root_abs = os.path.abspath(root)
    target_abs = os.path.abspath(os.path.join(root_abs, *normalized.split("/")))
    if os.path.commonpath([root_abs, target_abs]) != root_abs:
        raise ValueError(f"Path escapes backup scope: {rel_path!r}")
    return target_abs


def _iter_scope_files(root: str, excluded_extensions: set[str]) -> list[tuple[str, str]]:
    if not os.path.isdir(root):
        return []

    result: list[tuple[str, str]] = []
    for current_root, _, files in os.walk(root):
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext in excluded_extensions:
                continue
            abs_path = os.path.join(current_root, filename)
            rel_path = os.path.relpath(abs_path, root).replace("\\", "/")
            result.append((rel_path, abs_path))
    result.sort(key=lambda item: item[0])
    return result


def _serialize_file(abs_path: str) -> dict[str, str]:
    with open(abs_path, "rb") as f:
        payload = f.read()

    try:
        return {"encoding": "utf-8", "content": payload.decode("utf-8")}
    except UnicodeDecodeError:
        return {"encoding": "base64", "content": base64.b64encode(payload).decode("ascii")}


def _decode_entry(entry: dict[str, Any]) -> bytes:
    encoding = entry.get("encoding")
    content = entry.get("content")
    if encoding not in {"utf-8", "base64"}:
        raise ValueError(f"Unsupported entry encoding: {encoding!r}")
    if not isinstance(content, str):
        raise ValueError("Entry content must be a string")

    if encoding == "utf-8":
        return content.encode("utf-8")

    try:
        return base64.b64decode(content.encode("ascii"), validate=True)
    except Exception as e:
        raise ValueError(f"Invalid base64 file payload: {e}") from e


def _validate_entry(entry: Any, context: str) -> None:
    if not isinstance(entry, dict):
        raise ValueError(f"{context}: file entry must be an object")
    encoding = entry.get("encoding")
    content = entry.get("content")
    if encoding not in {"utf-8", "base64"}:
        raise ValueError(f"{context}: unsupported encoding {encoding!r}")
    if not isinstance(content, str):
        raise ValueError(f"{context}: content must be a string")


def _write_file_atomic(abs_path: str, raw_data: bytes) -> None:
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".cfg_backup_", dir=os.path.dirname(abs_path))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(raw_data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, abs_path)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def _cleanup_empty_dirs(root: str) -> None:
    if not os.path.isdir(root):
        return
    for current_root, dirs, files in os.walk(root, topdown=False):
        if current_root == root:
            continue
        if dirs or files:
            continue
        try:
            os.rmdir(current_root)
        except OSError:
            pass


def _safe_remove_file(abs_path: str) -> None:
    if os.path.isfile(abs_path):
        os.remove(abs_path)


def create_backup_payload() -> dict[str, Any]:
    bot_settings: dict[str, dict[str, str]] = {}
    plugin_storage: dict[str, dict[str, dict[str, str]]] = {}

    for rel_path, abs_path in _iter_scope_files(paths.BOT_SETTINGS_DIR, _BOT_SETTINGS_EXCLUDED_EXTENSIONS):
        bot_settings[rel_path] = _serialize_file(abs_path)

    plugins_root = os.path.join(paths.STORAGE_DIR, "plugins")
    os.makedirs(plugins_root, exist_ok=True)
    plugin_entries = sorted(
        [entry for entry in os.scandir(plugins_root) if entry.is_dir()],
        key=lambda entry: entry.name.lower(),
    )

    excluded_logs = 0
    plugin_file_count = 0
    for plugin_entry in plugin_entries:
        plugin_name = plugin_entry.name
        plugin_files: dict[str, dict[str, str]] = {}
        for rel_path, abs_path in _iter_scope_files(plugin_entry.path, _PLUGIN_EXCLUDED_EXTENSIONS):
            plugin_files[rel_path] = _serialize_file(abs_path)
            plugin_file_count += 1

        # Count excluded logs for metadata/debugging.
        for _, _, files in os.walk(plugin_entry.path):
            for filename in files:
                if os.path.splitext(filename)[1].lower() in _PLUGIN_EXCLUDED_EXTENSIONS:
                    excluded_logs += 1

        plugin_storage[plugin_name] = plugin_files

    payload: dict[str, Any] = {
        "schema": BACKUP_SCHEMA,
        "version": BACKUP_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "bot_settings": bot_settings,
        "plugins_storage": plugin_storage,
        "meta": {
            "bot_settings_files": len(bot_settings),
            "plugin_folders": len(plugin_storage),
            "plugin_files": plugin_file_count,
            "excluded_logs": excluded_logs,
        },
    }
    return payload


def load_backup_payload(raw_bytes: bytes) -> dict[str, Any]:
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as e:
        raise ValueError("Backup file must be UTF-8 JSON") from e

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format: {e}") from e

    if not isinstance(payload, dict):
        raise ValueError("Backup root must be a JSON object")
    return payload


def validate_backup_payload(payload: dict[str, Any]) -> tuple[bool, str]:
    try:
        ensure_valid_backup_payload(payload)
        return True, ""
    except Exception as e:
        return False, str(e)


def ensure_valid_backup_payload(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ValueError("Backup root must be an object")

    schema = payload.get("schema")
    version = payload.get("version")
    if schema != BACKUP_SCHEMA:
        raise ValueError(f"Unsupported backup schema: {schema!r}")
    if version != BACKUP_VERSION:
        raise ValueError(f"Unsupported backup version: {version!r}")

    bot_settings = payload.get("bot_settings")
    plugins_storage = payload.get("plugins_storage")

    if not isinstance(bot_settings, dict):
        raise ValueError("`bot_settings` must be an object")
    if not isinstance(plugins_storage, dict):
        raise ValueError("`plugins_storage` must be an object")

    for rel_path, entry in bot_settings.items():
        if not _is_safe_relative_path(rel_path):
            raise ValueError(f"Unsafe bot_settings path: {rel_path!r}")
        _validate_entry(entry, f"bot_settings/{rel_path}")

    for plugin_name, files_map in plugins_storage.items():
        if not isinstance(plugin_name, str) or not plugin_name.strip():
            raise ValueError("Plugin folder name must be a non-empty string")
        if "/" in plugin_name or "\\" in plugin_name:
            raise ValueError(f"Plugin folder must be first-level only: {plugin_name!r}")
        if not isinstance(files_map, dict):
            raise ValueError(f"plugins_storage/{plugin_name}: value must be an object")

        for rel_path, entry in files_map.items():
            if not _is_safe_relative_path(rel_path):
                raise ValueError(f"Unsafe plugins_storage path: {plugin_name}/{rel_path}")
            _validate_entry(entry, f"plugins_storage/{plugin_name}/{rel_path}")


def backup_summary(payload: dict[str, Any]) -> dict[str, int]:
    bot_settings = payload.get("bot_settings", {})
    plugins_storage = payload.get("plugins_storage", {})
    plugin_files = 0
    for files_map in plugins_storage.values():
        if isinstance(files_map, dict):
            plugin_files += len(files_map)

    return {
        "bot_settings_files": len(bot_settings) if isinstance(bot_settings, dict) else 0,
        "plugin_folders": len(plugins_storage) if isinstance(plugins_storage, dict) else 0,
        "plugin_files": plugin_files,
    }


def format_backup_summary(payload: dict[str, Any]) -> str:
    summary = backup_summary(payload)
    return (
        f"⚙️ Файлов в <code>bot_settings</code>: <b>{summary['bot_settings_files']}</b>\n"
        f"🧩 Папок плагинов: <b>{summary['plugin_folders']}</b>\n"
        f"📄 Файлов плагинов: <b>{summary['plugin_files']}</b>"
    )

def save_backup_payload_to_file(payload: dict[str, Any], prefix: str = "seal_config_backup") -> str:
    ensure_valid_backup_payload(payload)

    target_dir = os.path.join(paths.CACHE_DIR, "config_backups")
    os.makedirs(target_dir, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    fd, temp_path = tempfile.mkstemp(prefix=f"{prefix}_{ts}_", suffix=".json", dir=target_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        return temp_path
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


def apply_backup_payload(payload: dict[str, Any]) -> None:
    ensure_valid_backup_payload(payload)

    bot_settings_payload: dict[str, dict[str, str]] = payload["bot_settings"]
    plugins_payload: dict[str, dict[str, dict[str, str]]] = payload["plugins_storage"]

    # Sync bot_settings scope.
    bot_settings_root = paths.BOT_SETTINGS_DIR
    os.makedirs(bot_settings_root, exist_ok=True)
    existing_bot_files = {rel for rel, _ in _iter_scope_files(bot_settings_root, _BOT_SETTINGS_EXCLUDED_EXTENSIONS)}
    target_bot_files = set(bot_settings_payload.keys())

    for rel_path in sorted(existing_bot_files - target_bot_files):
        _safe_remove_file(_resolve_path_inside_root(bot_settings_root, rel_path))

    for rel_path, entry in bot_settings_payload.items():
        raw_data = _decode_entry(entry)
        _write_file_atomic(_resolve_path_inside_root(bot_settings_root, rel_path), raw_data)

    _cleanup_empty_dirs(bot_settings_root)

    # Sync plugins storage by first-level folder names.
    plugins_root = os.path.join(paths.STORAGE_DIR, "plugins")
    os.makedirs(plugins_root, exist_ok=True)

    existing_plugin_dirs = {
        entry.name: entry.path
        for entry in os.scandir(plugins_root)
        if entry.is_dir()
    }
    target_plugin_dirs = set(plugins_payload.keys())

    # For removed plugins: remove only data scope (logs are intentionally untouched).
    for plugin_name in sorted(set(existing_plugin_dirs.keys()) - target_plugin_dirs):
        plugin_path = existing_plugin_dirs[plugin_name]
        existing_data_files = [rel for rel, _ in _iter_scope_files(plugin_path, _PLUGIN_EXCLUDED_EXTENSIONS)]
        for rel_path in existing_data_files:
            _safe_remove_file(_resolve_path_inside_root(plugin_path, rel_path))
        _cleanup_empty_dirs(plugin_path)
        try:
            if os.path.isdir(plugin_path) and not os.listdir(plugin_path):
                os.rmdir(plugin_path)
        except OSError:
            pass

    for plugin_name, files_map in plugins_payload.items():
        plugin_root = os.path.join(plugins_root, plugin_name)
        os.makedirs(plugin_root, exist_ok=True)

        existing_data_files = {rel for rel, _ in _iter_scope_files(plugin_root, _PLUGIN_EXCLUDED_EXTENSIONS)}
        target_data_files = set(files_map.keys())

        for rel_path in sorted(existing_data_files - target_data_files):
            _safe_remove_file(_resolve_path_inside_root(plugin_root, rel_path))

        for rel_path, entry in files_map.items():
            raw_data = _decode_entry(entry)
            _write_file_atomic(_resolve_path_inside_root(plugin_root, rel_path), raw_data)

        _cleanup_empty_dirs(plugin_root)

