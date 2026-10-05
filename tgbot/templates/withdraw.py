import html

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .. import callback_datas as calls

TX_STATUS_LABELS = {
    "PENDING": "⏳ В обработке",
    "PROCESSING": "⏳ В обработке",
    "CONFIRMED": "✅ Выполнен",
    "ROLLED_BACK": "↩️ Отменён",
    "FAILED": "❌ Ошибка",
}


def _btn(text: str, action: str, value: str | None = None) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=calls.WithdrawAction(action=action, value=value).pack())


def _money(value) -> str:
    if value is None:
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return f"{html.escape(str(value))} ₽"
    return f"{number:.2f}".rstrip("0").rstrip(".") + " ₽"


def mask_requisite(value) -> str:
    """Показывает только последние 4 символа реквизита."""
    text = str(value or "").strip()
    if len(text) <= 4:
        return html.escape(text) or "—"
    return "…" + html.escape(text[-4:])


def _fee_text(fee, min_fee) -> str:
    if fee is None:
        return "—"
    text = f"{fee}%"
    if min_fee:
        text += f", не менее {_money(min_fee)}"
    return text


def _limits_text(provider) -> str:
    outgoing = getattr(getattr(provider, "limits", None), "outgoing", None)
    if outgoing is None:
        return "—"
    return f"{_money(outgoing.min)} – {_money(outgoing.max)}"


def withdraw_main_text(balance, providers: list) -> str:
    lines = ["💸 <b>Вывод средств</b>", ""]
    if balance is not None:
        lines += [
            f"💰 <b>Баланс:</b> {_money(balance.value)}",
            f"┣ <b>Можно вывести:</b> {_money(balance.withdrawable)}",
            f"┣ <b>Доступно:</b> {_money(balance.available)}",
            f"┣ <b>Ожидается:</b> {_money(balance.pending_income)}",
            f"┗ <b>Заморожено:</b> {_money(balance.frozen)}",
            "",
        ]

    sbp = next((p for p in providers if _provider_id(p) == "SBP"), None)
    if sbp is not None:
        saved = getattr(getattr(sbp, "account", None), "value", None)
        lines += [
            "<b>⚡ СБП</b>",
            f"┣ <b>Комиссия:</b> {_fee_text(sbp.fee, sbp.min_fee_amount)}",
            f"┣ <b>Лимиты:</b> {_limits_text(sbp)}",
            f"┗ <b>Сохранённый номер:</b> {mask_requisite(saved) if saved else 'нет'}",
            "",
        ]

    others = [p for p in providers if _provider_id(p) not in ("SBP", "LOCAL")]
    if others:
        lines.append("<i>Другие способы (" + html.escape(", ".join(str(p.name) for p in others))
                     + ") пока доступны только на сайте.</i>")
    return "\n".join(lines)


def _provider_id(provider) -> str:
    pid = getattr(provider, "id", None)
    return getattr(pid, "name", None) or str(pid or "")


def withdraw_main_kb(has_sbp: bool) -> InlineKeyboardMarkup:
    rows = []
    if has_sbp:
        rows.append([_btn("⚡ Вывести через СБП", "sbp")])
    rows.append([_btn("🔄 Обновить", "open")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.ProfileNavigation(to="main").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def withdraw_phone_choice_text(saved_phone: str) -> str:
    return (
        "⚡ <b>Вывод через СБП</b>\n\n"
        f"Использовать сохранённый номер <b>{mask_requisite(saved_phone)}</b> или указать другой?"
    )


def withdraw_phone_choice_kb(saved_phone: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn(f"📱 Номер {mask_requisite(saved_phone)}", "phone_saved")],
        [_btn("✏️ Другой номер", "phone_new")],
        [_btn("❌ Отмена", "open")],
    ])


def withdraw_enter_phone_text(error: str | None = None) -> str:
    text = (
        "📱 <b>Введите номер телефона для СБП</b>\n\n"
        "Формат: <code>+79991234567</code> или <code>89991234567</code>.\n"
        "Playerok сохранит этот номер как реквизит для следующих выводов."
    )
    if error:
        text = f"❌ {html.escape(error)}\n\n" + text
    return text


def withdraw_bank_choice_text(bank_name: str) -> str:
    return f"🏦 <b>Банк получателя</b>\n\nВывести в <b>{html.escape(bank_name)}</b>, как в прошлый раз?"


def withdraw_bank_choice_kb(bank_name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn(f"🏦 {bank_name[:40]}", "bank_saved")],
        [_btn("🔎 Другой банк", "bank_search")],
        [_btn("❌ Отмена", "open")],
    ])


def withdraw_enter_bank_text(error: str | None = None) -> str:
    text = "🏦 <b>Введите название банка</b>\n\nНапример: <code>Т-Банк</code>, <code>Сбер</code>, <code>Альфа</code>."
    if error:
        text = f"❌ {html.escape(error)}\n\n" + text
    return text


def withdraw_bank_results_text(query: str, count: int) -> str:
    return f"🏦 Банки по запросу «{html.escape(query)}»: {count}\n\nВыберите банк ↓"


def withdraw_bank_results_kb(banks: list) -> InlineKeyboardMarkup:
    rows = [[_btn(f"🏦 {str(b.name)[:40]}", "bank_pick", str(b.id))] for b in banks]
    rows.append([_btn("🔎 Искать заново", "bank_search")])
    rows.append([_btn("❌ Отмена", "open")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def withdraw_enter_amount_text(ctx: dict, error: str | None = None) -> str:
    text = (
        "💰 <b>Введите сумму вывода в рублях</b> (целое число)\n\n"
        f"┣ <b>Можно вывести:</b> {_money(ctx.get('withdrawable'))}\n"
        f"┣ <b>Лимиты СБП:</b> {_money(ctx.get('min'))} – {_money(ctx.get('max'))}\n"
        f"┗ <b>Комиссия:</b> {_fee_text(ctx.get('fee'), ctx.get('min_fee'))}"
    )
    if error:
        text = f"❌ {html.escape(error)}\n\n" + text
    return text


def withdraw_confirm_text(ctx: dict) -> str:
    return (
        "❗ <b>Проверьте вывод</b>\n\n"
        f"┣ <b>Способ:</b> СБП\n"
        f"┣ <b>Номер:</b> {mask_requisite(ctx.get('phone'))}\n"
        f"┣ <b>Банк:</b> {html.escape(str(ctx.get('bank_name') or '—'))}\n"
        f"┣ <b>Сумма:</b> {_money(ctx.get('amount'))}\n"
        f"┗ <b>Комиссия Playerok:</b> {_fee_text(ctx.get('fee'), ctx.get('min_fee'))}\n\n"
        "После подтверждения заявка уйдёт в Playerok."
    )


def withdraw_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("✅ Подтвердить вывод", "confirm"), _btn("❌ Отмена", "open")],
    ])


def withdraw_result_text(tx) -> str:
    status = getattr(getattr(tx, "status", None), "name", None) or "—"
    lines = [
        "✅ <b>Заявка на вывод создана</b>",
        "",
        f"┣ <b>ID:</b> <code>{html.escape(str(getattr(tx, 'id', '—')))}</code>",
        f"┣ <b>Статус:</b> {TX_STATUS_LABELS.get(status, html.escape(status))}",
        f"┣ <b>Сумма:</b> {_money(getattr(tx, 'value', None))}",
    ]
    bank = getattr(tx, "sbp_bank_name", None)
    if bank:
        lines.append(f"┣ <b>Банк:</b> {html.escape(str(bank))}")
    account_value = getattr(tx, "payment_account_value", None)
    lines.append(f"┗ <b>Реквизит:</b> {html.escape(str(account_value)) if account_value else '—'}")
    if getattr(tx, "is_suspicious", None):
        lines += ["", "<i>Playerok отправил заявку на дополнительную проверку — это может занять больше времени.</i>"]
    return "\n".join(lines)


def withdraw_result_kb(tx_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("🚫 Отменить заявку", "cancel_tx", tx_id)],
        [_btn("⬅️ К выводу", "open")],
    ])


def withdraw_cancel_confirm_kb(tx_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("✅ Да, отменить", "cancel_tx_confirm", tx_id), _btn("⬅️ Нет", "open")],
    ])
