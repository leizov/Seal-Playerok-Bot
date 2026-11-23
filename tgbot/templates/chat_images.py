"""🖼 Картинки в сообщениях (автоответы, авто-выдача): тексты и клавиатуры."""
from html import escape

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from core.chat_images import (
    ALLOWED_FORMATS_TEXT,
    MAX_IMAGE_BYTES,
    MAX_IMAGES,
    format_size,
    image_file_size,
    resolve_image,
)

from .. import callback_datas as calls


def _cb(owner, action: str, index: int = -1) -> str:
    return calls.ChatImagesAction(owner=owner.owner, key=owner.key, action=action, index=index).pack()


def _image_line(number: int, ref: str) -> str:
    if resolve_image(ref) is None:
        return f"{number}. ❌ файл не найден — не отправится"
    ext = ref.rsplit(".", 1)[-1].upper()
    return f"{number}. {ext} · {format_size(image_file_size(ref))}"


def chat_images_limits_text() -> str:
    return f"До {MAX_IMAGES} картинок: {ALLOWED_FORMATS_TEXT}, каждая до {format_size(MAX_IMAGE_BYTES)}."


def chat_images_text(owner, notice: str = "") -> str:
    refs = owner.refs
    lines = [
        f"{owner.header} → 🖼 <b>Картинки</b>",
        "",
        owner.when_sent,
        chat_images_limits_text(),
        "",
        f"<b>Прикреплено:</b> {len(refs)} из {MAX_IMAGES}",
    ]
    if refs:
        lines += [_image_line(number, ref) for number, ref in enumerate(refs, start=1)]
    else:
        lines.append("Картинок пока нет.")
    if notice:
        lines += ["", notice]

    lines.append("")
    if len(refs) < MAX_IMAGES:
        lines.append("➕ <b>Добавить картинки</b> — прислать фото или файлы, можно сразу альбомом")
    if refs:
        lines.append("👁 <b>Картинка N</b> — прислать картинку сюда, чтобы посмотреть")
        lines.append("🗑 <b>Удалить N</b> — убрать картинку из сообщения")
    if refs or owner.preview_text:
        lines.append("👀 <b>Предпросмотр</b> — прислать сюда сообщение так, как его увидит покупатель")
    if refs:
        lines.append("🧹 <b>Удалить все</b> — убрать все картинки")
    lines.append(f"⬅️ <b>Назад</b> — {owner.back_hint}")
    return "\n".join(lines)


def chat_images_kb(owner) -> InlineKeyboardMarkup:
    refs = owner.refs
    rows = []
    for number, _ref in enumerate(refs, start=1):
        rows.append([
            InlineKeyboardButton(text=f"👁 Картинка {number}", callback_data=_cb(owner, "show", number - 1)),
            InlineKeyboardButton(text=f"🗑 Удалить {number}", callback_data=_cb(owner, "del", number - 1)),
        ])
    if len(refs) < MAX_IMAGES:
        rows.append([InlineKeyboardButton(text="➕ Добавить картинки", callback_data=_cb(owner, "add"))])
    if refs or owner.preview_text:
        rows.append([InlineKeyboardButton(text="👀 Предпросмотр", callback_data=_cb(owner, "preview"))])
    if refs:
        rows.append([InlineKeyboardButton(text="🧹 Удалить все", callback_data=_cb(owner, "clear"))])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=owner.back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def chat_images_add_text(owner, added: int = 0, notice: str = "") -> str:
    free = max(0, MAX_IMAGES - len(owner.refs))
    lines = [
        f"{owner.header} → 🖼 <b>Картинки</b> → ➕ <b>Добавление</b>",
        "",
        "📎 Отправьте картинку — как фото или файлом.",
        "Можно сразу несколько — альбомом.",
        chat_images_limits_text(),
        "",
        f"<b>Свободно мест:</b> {free} из {MAX_IMAGES}",
    ]
    if added:
        lines.append(f"✅ Добавлено сейчас: <b>{added}</b>")
    if notice:
        lines += ["", notice]
    lines += ["", "✅ <b>Готово</b> — вернуться к списку картинок"]
    return "\n".join(lines)


def chat_images_add_kb(owner) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Готово", callback_data=_cb(owner, "menu"))],
    ])


def chat_images_clear_text(owner) -> str:
    count = len(owner.refs)
    return "\n".join([
        f"{owner.header} → 🖼 <b>Картинки</b>",
        "",
        f"🧹 Удалить все картинки (<b>{count}</b> шт.) из {owner.name_gen}?",
        "Файлы удалятся с диска — вернуть их можно, только загрузив заново.",
        "",
        "✅ <b>Да, удалить все</b> — удалить картинки",
        "❌ <b>Отмена</b> — вернуться к списку картинок",
    ])


def chat_images_clear_kb(owner) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да, удалить все", callback_data=_cb(owner, "clear_yes")),
        InlineKeyboardButton(text="❌ Отмена", callback_data=_cb(owner, "menu")),
    ]])


def chat_images_photo_caption(owner, number: int) -> str:
    ref = owner.refs[number - 1]
    ext = ref.rsplit(".", 1)[-1].upper()
    return (
        f"🖼 <b>Картинка {number} из {len(owner.refs)}</b> — {owner.name}\n"
        f"{ext} · {format_size(image_file_size(ref))}"
    )


def chat_images_preview_caption(owner, text: str, limit: int) -> str | None:
    """Подпись предпросмотра; None, если текст не помещается в подпись и уйдёт отдельным сообщением."""
    head = f"👀 <b>Предпросмотр</b> — так покупатель увидит {owner.name_acc}"
    if not text:
        return head + "\n<i>Без текста — только картинки</i>"
    caption = f"{head}:\n<blockquote>{escape(text)}</blockquote>"
    # Лимит подписи считается по тексту без HTML-разметки
    plain_len = len(head) + len(text) + 2
    return caption if plain_len <= limit else None


def chat_images_preview_text(owner, text: str) -> str:
    return f"👀 <b>Предпросмотр</b> — так покупатель увидит {owner.name_acc}:\n<blockquote>{escape(text)}</blockquote>"


def chat_images_count_label(refs: list) -> str:
    return f"🖼 Картинки ({len(refs)}/{MAX_IMAGES})"
