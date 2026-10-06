from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .. import callback_datas as calls


def item_card_kb(
    back_cb: str,
    item_url: str,
    is_owner: bool,
    item_status: str | None = None,
    back_text: str | None = None,
    keep_in_sale: bool | None = None,
    keep_in_sale_available: bool = False,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    status_name = str(item_status or "").upper()
    can_restore = status_name in {"SOLD", "EXPIRED"}
    can_publish = status_name == "DRAFT" or can_restore

    if is_owner and keep_in_sale_available and status_name != "BLOCKED":
        rows.append(
            [
                InlineKeyboardButton(
                    text=(
                        "🔄 Оставлять в продаже: ✅"
                        if keep_in_sale
                        else "🔄 Оставлять в продаже: ❌"
                    ),
                    callback_data=calls.ItemsAction(
                        action="item_keep_in_sale",
                        value="0" if keep_in_sale else "1",
                    ).pack(),
                )
            ]
        )

    if is_owner:
        delete_button = InlineKeyboardButton(
            text="🗑 Удалить товар",
            callback_data=calls.ItemsAction(action="item_delete_prompt").pack(),
        )

        if status_name == "BLOCKED":
            rows.append([delete_button])
        else:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=(
                            "♻️ Восстановить товар"
                            if can_restore
                            else "📤 Опубликовать товар"
                            if can_publish
                            else "📈 Поднять товар"
                        ),
                        callback_data=(
                            calls.ItemsAction(action="item_publish_prompt").pack()
                            if can_publish
                            else calls.ItemsAction(action="item_raise_prompt").pack()
                        ),
                    ),
                    delete_button,
                ]
            )

    rows.append(
        [
            InlineKeyboardButton(
                text=back_text or "⬅️ Назад к списку",
                callback_data=back_cb,
            ),
            InlineKeyboardButton(text="🔗 Открыть товар", url=item_url),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def item_card_confirm_kb(confirm_action: str, cancel_action: str = "item_action_cancel") -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="✅ Подтвердить",
                callback_data=calls.ItemsAction(action=confirm_action).pack(),
            ),
            InlineKeyboardButton(
                text="❌ Отменить",
                callback_data=calls.ItemsAction(action=cancel_action).pack(),
            ),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _fmt_price(value) -> str:
    if value is None:
        return "0 ₽"
    try:
        return f"{float(value):.2f} ₽"
    except Exception:
        return f"{value} ₽"


def item_publish_confirm_kb(
    has_default: bool,
    has_premium: bool,
    default_price=None,
    premium_price=None,
    cancel_action: str = "item_action_cancel",
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    if has_default:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"✅ Обычный ({_fmt_price(default_price)})",
                    callback_data=calls.ItemsAction(action="item_publish_confirm", value="DEFAULT").pack(),
                )
            ]
        )

    if has_premium:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"🚀 Премиум ({_fmt_price(premium_price)})",
                    callback_data=calls.ItemsAction(action="item_publish_confirm", value="PREMIUM").pack(),
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="❌ Отменить",
                callback_data=calls.ItemsAction(action=cancel_action).pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
