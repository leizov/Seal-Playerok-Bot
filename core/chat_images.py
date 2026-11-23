"""
Картинки, которые бот прикрепляет к своим сообщениям в чатах Playerok
(автоответы, авто-выдача и мультивыдача).

Файлы лежат в ``bot_settings/chat_images/``, а в настройках хранится ссылка вида
``chat_images/<id>.<ext>``. Папка внутри bot_settings, поэтому картинки попадают
в бэкап конфигурации и восстанавливаются из него вместе с настройками.
"""
from __future__ import annotations

import os
import re
import time
import uuid
from logging import getLogger
from typing import Any, Iterable

import paths


logger = getLogger("seal.chat_images")

IMAGES_DIR_NAME = "chat_images"
MAX_IMAGES = 5                      # картинок на одно сообщение
MAX_IMAGE_BYTES = 5 * 1024 * 1024   # 5 МБ на картинку
ALLOWED_EXTENSIONS = ("jpg", "png", "webp")
ALLOWED_FORMATS_TEXT = "JPG, PNG, WEBP"

# Неиспользуемые файлы моложе этого возраста не удаляем: их могли только что сохранить.
_CLEANUP_MIN_AGE_SECONDS = 120
_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}\.(?:jpg|png|webp)$")


class ChatImageError(ValueError):
    """Ошибка с текстом для пользователя (неверный формат, большой размер, лимит)."""


def images_dir() -> str:
    return os.path.join(paths.BOT_SETTINGS_DIR, IMAGES_DIR_NAME)


def detect_image_type(data: bytes) -> str | None:
    """Расширение картинки по первым байтам файла: jpg, png, webp, gif или None."""
    head = bytes(data[:12])
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    return None


def format_size(size: int | None) -> str:
    if size is None:
        return "?"
    if size < 1024 * 1024:
        return f"{max(1, round(size / 1024))} КБ"
    megabytes = size / (1024 * 1024)
    if megabytes == int(megabytes):
        return f"{int(megabytes)} МБ"
    return f"{megabytes:.1f} МБ".replace(".", ",")


def validate_image_bytes(data: bytes) -> str:
    """Проверяет картинку перед сохранением и возвращает её расширение."""
    if not data:
        raise ChatImageError("❌ Файл пустой")
    if len(data) > MAX_IMAGE_BYTES:
        raise ChatImageError(
            f"❌ Картинка слишком большая: {format_size(len(data))}. "
            f"Максимум — {format_size(MAX_IMAGE_BYTES)}"
        )
    ext = detect_image_type(data)
    if ext == "gif":
        raise ChatImageError(f"❌ GIF не поддерживается. Подойдут: {ALLOWED_FORMATS_TEXT}")
    if ext not in ALLOWED_EXTENSIONS:
        raise ChatImageError(f"❌ Это не картинка или формат не поддерживается. Подойдут: {ALLOWED_FORMATS_TEXT}")
    return ext


def _ref_name(ref: Any) -> str | None:
    """Имя файла из ссылки «chat_images/<имя>» (или просто «<имя>»); None, если ссылка некорректна."""
    if not isinstance(ref, str):
        return None
    value = ref.strip().replace("\\", "/")
    if value.startswith(IMAGES_DIR_NAME + "/"):
        value = value[len(IMAGES_DIR_NAME) + 1:]
    if not _NAME_RE.match(value):
        return None
    return value


def make_ref(name: str) -> str:
    return f"{IMAGES_DIR_NAME}/{name}"


def normalize_refs(value: Any) -> list[str]:
    """Список корректных ссылок на картинки без повторов, не больше MAX_IMAGES."""
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for ref in value:
        name = _ref_name(ref)
        if name is None:
            continue
        normalized = make_ref(name)
        if normalized not in result:
            result.append(normalized)
        if len(result) >= MAX_IMAGES:
            break
    return result


def resolve_image(ref: Any) -> str | None:
    """Абсолютный путь к файлу картинки или None, если ссылка некорректна или файла нет."""
    name = _ref_name(ref)
    if name is None:
        return None
    path = os.path.join(images_dir(), name)
    return path if os.path.isfile(path) else None


def existing_image_paths(refs: Any) -> list[str]:
    """Пути к картинкам, которые реально лежат на диске (пропавшие пропускаются)."""
    result = []
    for ref in normalize_refs(refs):
        path = resolve_image(ref)
        if path:
            result.append(path)
    return result


def missing_refs(refs: Any) -> list[str]:
    return [ref for ref in normalize_refs(refs) if resolve_image(ref) is None]


def image_file_size(ref: Any) -> int | None:
    path = resolve_image(ref)
    if not path:
        return None
    try:
        return os.path.getsize(path)
    except OSError:
        return None


def read_image(ref: Any) -> bytes | None:
    path = resolve_image(ref)
    if not path:
        return None
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return None


def save_image(data: bytes) -> str:
    """Проверяет и сохраняет картинку, возвращает ссылку для настроек."""
    ext = validate_image_bytes(data)
    folder = images_dir()
    os.makedirs(folder, exist_ok=True)
    name = f"{uuid.uuid4().hex}.{ext}"
    path = os.path.join(folder, name)
    tmp_path = path + ".tmp"
    with open(tmp_path, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)
    return make_ref(name)


def _refs_from_settings() -> set[str]:
    from settings import Settings as sett

    refs: set[str] = set()
    messages = sett.get("messages") or {}
    if isinstance(messages, dict):
        for message in messages.values():
            if isinstance(message, dict):
                refs.update(normalize_refs(message.get("images")))
    deliveries = sett.get("auto_deliveries") or []
    if isinstance(deliveries, list):
        for delivery in deliveries:
            if isinstance(delivery, dict):
                refs.update(normalize_refs(delivery.get("images")))
    return refs


def _refs_from_bot_cache() -> set[str]:
    refs: set[str] = set()
    try:
        from plbot.playerokbot import get_playerok_bot

        bot = get_playerok_bot()
    except Exception:
        return refs
    if bot is None:
        return refs
    for delivery in getattr(bot, "auto_deliveries", None) or []:
        if isinstance(delivery, dict):
            refs.update(normalize_refs(delivery.get("images")))
    messages = getattr(bot, "messages", None) or {}
    if isinstance(messages, dict):
        for message in messages.values():
            if isinstance(message, dict):
                refs.update(normalize_refs(message.get("images")))
    return refs


def referenced_refs() -> set[str]:
    """Все картинки, на которые ссылаются настройки (и кэш работающего бота)."""
    return _refs_from_settings() | _refs_from_bot_cache()


def delete_images(refs: Iterable[str]) -> int:
    """Удаляет файлы картинок, если на них больше никто не ссылается. Возвращает число удалённых."""
    still_used = referenced_refs()
    removed = 0
    for ref in refs:
        name = _ref_name(ref)
        if name is None or make_ref(name) in still_used:
            continue
        path = os.path.join(images_dir(), name)
        try:
            os.remove(path)
            removed += 1
        except FileNotFoundError:
            pass
        except OSError as e:
            logger.warning(f"Не удалось удалить картинку {name}: {e}")
    return removed


def cleanup_unused_images(min_age_seconds: int = _CLEANUP_MIN_AGE_SECONDS) -> int:
    """Удаляет из папки картинки, на которые не ссылается ни одна настройка."""
    folder = images_dir()
    if not os.path.isdir(folder):
        return 0
    used = {_ref_name(ref) for ref in referenced_refs()}
    now = time.time()
    removed = 0
    for entry in os.scandir(folder):
        if not entry.is_file():
            continue
        if entry.name in used:
            continue
        try:
            if now - entry.stat().st_mtime < min_age_seconds:
                continue
            os.remove(entry.path)
            removed += 1
        except OSError as e:
            logger.warning(f"Не удалось удалить неиспользуемую картинку {entry.name}: {e}")
    return removed
