from __future__ import annotations


COOKIE_SUPPORTED_INPUTS_TEXT = "ПОДДЕРЖИВАЕМЫЕ ФОРМАТЫ ОТПРАВКИ: ТЕКСТ, .TXT, .JSON."

COOKIE_COLLECTION_GUIDE_TEXT = (
    "ГАЙД НА УСТАНОВКУ КУКИ SEAL PLAYEROK\n\n"
    "1) КАЧАЕМ РАСШИРЕНИЕ Cookie Manager\n"
    "https://chromewebstore.google.com/detail/cookie-manager/kbnfbcpkiaganjpcanopcgeoehkleeck\n\n"
    "2) ЗАХОДИМ НА PLAYEROK - АВТОРИЗУЕМСЯ В СВОЁМ АККАУНТЕ И ОБНОВЛЯЕМ СТРАНИЦУ\n\n"
    "3) НАЖИМАЕТЕ НА ИКНОКУ РАСШИРЕНИЯ  НА КНОПКУ Export\n\n"
    "ПОСЛЕ ЧЕГО У НАС СКАЧАЕТСЯ ФАЙЛ\n"
    "ЭТОТ ФАЙЛ МЫ И ОТПРАВЛЯЕМ БОТУ В ТГ!!!"
)


def build_cookie_collection_instruction(title: str | None = None) -> str:
    parts: list[str] = []
    if title:
        parts.append(str(title).strip())
    parts.append(COOKIE_SUPPORTED_INPUTS_TEXT)
    parts.append(COOKIE_COLLECTION_GUIDE_TEXT)
    return "\n\n".join(parts)


def build_cookie_parse_error_text(reason: str) -> str:
    error_reason = str(reason or "").strip() or "Не удалось распознать cookies."
    if not error_reason.startswith("❌"):
        error_reason = f"❌ {error_reason}"
    return "\n\n".join([error_reason, COOKIE_SUPPORTED_INPUTS_TEXT, COOKIE_COLLECTION_GUIDE_TEXT])
