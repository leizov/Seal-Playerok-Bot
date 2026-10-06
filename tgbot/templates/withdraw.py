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


def _balance_lines(balance) -> list[str]:
    if balance is None:
        return []
    return [
        f"💰 <b>Баланс:</b> {_money(balance.value)}",
        f"┣ <b>Можно вывести:</b> {_money(balance.withdrawable)}",
        f"┣ <b>Доступно:</b> {_money(balance.available)}",
        f"┣ <b>Ожидается:</b> {_money(balance.pending_income)}",
        f"┗ <b>Заморожено:</b> {_money(balance.frozen)}",
        "",
    ]


def wallet_text(balance) -> str:
    lines = ["👛 <b>Кошелёк</b>", ""] + _balance_lines(balance)
    lines.append("Выберите действие ↓")
    return "\n".join(lines)


def wallet_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            # _btn("💸 Вывод", "withdraw"),
            _btn("📜 История транзакций", "history", "0")
        ],
        [_btn("🔄 Обновить", "open")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.ProfileNavigation(to="main").pack())],
    ])


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
    rows.append([_btn("🔄 Обновить", "withdraw")])
    rows.append([_btn("⬅️ В кошелёк", "open")])
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
        [_btn("❌ Отмена", "withdraw")],
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
        [_btn("❌ Отмена", "withdraw")],
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
    rows.append([_btn("❌ Отмена", "withdraw")])
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
        [_btn("✅ Подтвердить вывод", "confirm"), _btn("❌ Отмена", "withdraw")],
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
        [_btn("⬅️ В кошелёк", "open")],
    ])


TX_OPERATION_LABELS = {
    "DEPOSIT": "Пополнение",
    "BUY": "Покупка",
    "SELL": "Продажа",
    "ITEM_DEFAULT_PRIORITY": "Оплата выставления",
    "ITEM_PREMIUM_PRIORITY": "Оплата премиум/поднятия",
    "WITHDRAW": "Вывод",
    "MANUAL_BALANCE_INCREASE": "Зачисление",
    "MANUAL_BALANCE_DECREASE": "Списание",
    "REFERRAL_BONUS": "Реферальный бонус",
    "STEAM_DEPOSIT": "Пополнение Steam",
}

TX_HISTORY_FILTERS = {
    "all": "Все",
    "WITHDRAW": "Выводы",
    "SELL": "Продажи",
    "BUY": "Покупки",
    "PRIORITY": "Поднятия",
}

# Фильтры, объединяющие несколько операций Playerok.
TX_HISTORY_FILTER_OPERATIONS = {
    "PRIORITY": ("ITEM_DEFAULT_PRIORITY", "ITEM_PREMIUM_PRIORITY"),
}


def _enum_name(value) -> str:
    return getattr(value, "name", None) or (str(value) if value is not None else "")


def _short_date(value) -> str:
    text = str(value or "")
    # 2026-10-05T14:46:26.000Z -> 05.10.2026 14:46
    if len(text) >= 16 and text[4] == "-" and text[10] == "T":
        return f"{text[8:10]}.{text[5:7]}.{text[0:4]} {text[11:16]}"
    return html.escape(text) or "—"


def transaction_line(tx) -> str:
    operation = _enum_name(getattr(tx, "operation", None))
    status = _enum_name(getattr(tx, "status", None))
    direction = _enum_name(getattr(tx, "direction", None))
    sign = "−" if direction == "OUT" else "+" if direction == "IN" else ""
    label = TX_OPERATION_LABELS.get(operation, html.escape(operation or "Операция"))
    status_label = TX_STATUS_LABELS.get(status, html.escape(status or "—"))
    line = f"{sign}{_money(getattr(tx, 'value', None))} · <b>{label}</b> · {status_label}"
    details = [_short_date(getattr(tx, "created_at", None))]
    provider = getattr(getattr(tx, "provider", None), "name", None)
    if operation == "WITHDRAW" and provider:
        details.append(html.escape(str(provider)))
    bank = getattr(tx, "sbp_bank_name", None)
    if bank:
        details.append(html.escape(str(bank)))
    account_value = getattr(tx, "payment_account_value", None)
    if account_value:
        details.append(html.escape(str(account_value)))
    return line + "\n<i>" + " · ".join(details) + "</i>"


def transactions_text(transactions: list, page: int, total_count, filter_key: str) -> str:
    title = f"📜 <b>История транзакций</b> — {TX_HISTORY_FILTERS.get(filter_key, 'Все')}"
    if total_count is not None:
        title += f" ({total_count})"
    lines = [title, f"Страница {page + 1}", ""]
    if not transactions:
        lines.append("<i>Транзакций нет</i>")
    else:
        lines.append("\n\n".join(transaction_line(tx) for tx in transactions))
    return "\n".join(lines)


def transactions_kb(page: int, has_next: bool, filter_key: str, cancellable: list | None = None) -> InlineKeyboardMarkup:
    filter_buttons = [
        _btn(("• " if key == filter_key else "") + label, "hist_filter", key)
        for key, label in TX_HISTORY_FILTERS.items()
    ]
    rows = [filter_buttons[i:i + 3] for i in range(0, len(filter_buttons), 3)]
    for tx in cancellable or []:
        rows.append([_btn(f"🚫 Отменить вывод {_money(getattr(tx, 'value', None))}", "cancel_tx", str(tx.id))])
    nav = []
    if page > 0:
        nav.append(_btn("⬅️", "history", str(page - 1)))
    # nav.append(_btn("🔄", "history", str(page)))
    if has_next:
        nav.append(_btn("➡️", "history", str(page + 1)))
    rows.append(nav)
    rows.append([_btn("⬅️ В кошелёк", "open")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def withdraw_cancel_confirm_kb(tx_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("✅ Да, отменить", "cancel_tx_confirm", tx_id), _btn("⬅️ Нет", "open")],
    ])
