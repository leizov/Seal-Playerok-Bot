from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .. import callback_datas as calls


def item_card_kb(
    back_cb: str,
    item_url: str,
    is_owner: bool,
    item_status: str | None = None,
    back_text: str | None = None,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    status_name = str(item_status or "").upper()
    can_publish = status_name in {"DRAFT", "EXPIRED"}

    if is_owner:
        delete_button = InlineKeyboardButton(
            text="\U0001F5D1 \u0423\u0434\u0430\u043B\u0438\u0442\u044C \u0442\u043E\u0432\u0430\u0440",
            callback_data=calls.ItemsAction(action="item_delete_prompt").pack(),
        )

        if status_name == "BLOCKED":
            rows.append([delete_button])
        else:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=(
                            "\U0001F4E4 \u041E\u043F\u0443\u0431\u043B\u0438\u043A\u043E\u0432\u0430\u0442\u044C \u0442\u043E\u0432\u0430\u0440"
                            if can_publish
                            else "\U0001F4C8 \u041F\u043E\u0434\u043D\u044F\u0442\u044C \u0442\u043E\u0432\u0430\u0440"
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
                text=back_text or "\u2B05\uFE0F \u041D\u0430\u0437\u0430\u0434 \u043A \u0441\u043F\u0438\u0441\u043A\u0443",
                callback_data=back_cb,
            ),
            InlineKeyboardButton(text="\U0001F517 \u041E\u0442\u043A\u0440\u044B\u0442\u044C \u0442\u043E\u0432\u0430\u0440", url=item_url),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def item_card_confirm_kb(confirm_action: str, cancel_action: str = "item_action_cancel") -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="\u2705 \u041F\u043E\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u044C",
                callback_data=calls.ItemsAction(action=confirm_action).pack(),
            ),
            InlineKeyboardButton(
                text="\u274C \u041E\u0442\u043C\u0435\u043D\u0438\u0442\u044C",
                callback_data=calls.ItemsAction(action=cancel_action).pack(),
            ),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _fmt_price(value) -> str:
    if value is None:
        return "0 \u20BD"
    try:
        return f"{float(value):.2f} \u20BD"
    except Exception:
        return f"{value} \u20BD"


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
                    text=f"\u2705 \u041E\u0431\u044B\u0447\u043D\u044B\u0439 ({_fmt_price(default_price)})",
                    callback_data=calls.ItemsAction(action="item_publish_confirm", value="DEFAULT").pack(),
                )
            ]
        )

    if has_premium:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"\U0001F680 \u041F\u0440\u0435\u043C\u0438\u0443\u043C ({_fmt_price(premium_price)})",
                    callback_data=calls.ItemsAction(action="item_publish_confirm", value="PREMIUM").pack(),
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="\u274C \u041E\u0442\u043C\u0435\u043D\u0438\u0442\u044C",
                callback_data=calls.ItemsAction(action=cancel_action).pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
