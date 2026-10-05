"""Вывод средств через СБП из Telegram-бота.

Подтверждено реальными запросами: viewerBalance, transactionProviders(OUT),
requestWithdrawal с provider=SBP. Остальные способы вывода не реализованы,
так как их запросы не проверены.
"""
from __future__ import annotations

import asyncio
import logging
import re

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from playerokapi.enums import TransactionProviderDirections, TransactionProviderIds

from .. import callback_datas as calls
from .. import states
from .. import templates as templ
from ..helpful import get_playerok_bot, throw_float_message


router = Router()
logger = logging.getLogger("seal.telegram.withdraw")

CTX_KEY = "withdraw_ctx"
BANKS_SHOW_LIMIT = 8


def _get_account():
    plbot = get_playerok_bot()
    if not plbot:
        return None
    return getattr(plbot, "account", None) or getattr(plbot, "playerok_account", None)


def normalize_phone(raw: str) -> str | None:
    """Приводит номер РФ к виду +7XXXXXXXXXX. Возвращает None, если номер некорректный."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 10 and digits.startswith("9"):
        digits = "7" + digits
    elif len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) != 11 or not digits.startswith("7"):
        return None
    return "+" + digits


def _is_full_phone(value) -> bool:
    """Сохранённый реквизит можно использовать, только если он пришёл полностью, а не маской."""
    return normalize_phone(str(value or "")) is not None and "*" not in str(value)


def _provider_id(provider) -> str:
    pid = getattr(provider, "id", None)
    return getattr(pid, "name", None) or str(pid or "")


def parse_amount(raw: str) -> int | None:
    text = (raw or "").strip().replace(" ", "").replace("₽", "")
    if not text.isdigit():
        return None
    return int(text)


def validate_amount(amount: int, ctx: dict) -> str | None:
    """Возвращает текст ошибки или None, если сумма подходит."""
    if amount <= 0:
        return "Сумма должна быть больше нуля."
    min_v, max_v = ctx.get("min"), ctx.get("max")
    if min_v is not None and amount < float(min_v):
        return f"Минимальная сумма вывода через СБП — {min_v} ₽."
    if max_v is not None and amount > float(max_v):
        return f"Максимальная сумма вывода через СБП — {max_v} ₽."
    withdrawable = ctx.get("withdrawable")
    if withdrawable is not None and amount > float(withdrawable):
        return f"Можно вывести не больше {withdrawable} ₽."
    return None


def _load_overview(account):
    balance = account.get_balance()
    providers = account.get_transaction_providers(direction=TransactionProviderDirections.OUT)
    return balance, providers


async def _get_ctx(state: FSMContext) -> dict:
    data = await state.get_data()
    ctx = data.get(CTX_KEY)
    return dict(ctx) if isinstance(ctx, dict) else {}


async def _set_ctx(state: FSMContext, ctx: dict):
    await state.update_data(**{CTX_KEY: ctx})


async def show_withdraw_menu(message: Message, state: FSMContext, callback: CallbackQuery | None = None):
    await state.set_state(None)
    account = _get_account()
    if account is None:
        await throw_float_message(state=state, message=message, callback=callback,
                                  text=templ.do_action_text("❌ Нет подключения к Playerok"),
                                  reply_markup=templ.withdraw_main_kb(has_sbp=False))
        return
    try:
        balance, providers = await asyncio.to_thread(_load_overview, account)
    except Exception as e:
        logger.warning("Не удалось загрузить данные для вывода: %s", e)
        await throw_float_message(state=state, message=message, callback=callback,
                                  text=templ.do_action_text(f"❌ Не удалось загрузить баланс: {e}"),
                                  reply_markup=templ.withdraw_main_kb(has_sbp=False))
        return

    sbp = next((p for p in providers if _provider_id(p) == "SBP"), None)
    old = await _get_ctx(state)
    ctx = {
        "bank_id": old.get("bank_id"),
        "bank_name": old.get("bank_name"),
        "withdrawable": getattr(balance, "withdrawable", None),
    }
    if sbp is not None:
        outgoing = getattr(getattr(sbp, "limits", None), "outgoing", None)
        saved = getattr(getattr(sbp, "account", None), "value", None)
        ctx.update({
            "fee": sbp.fee,
            "min_fee": sbp.min_fee_amount,
            "min": getattr(outgoing, "min", None),
            "max": getattr(outgoing, "max", None),
            "saved_phone": normalize_phone(saved) if _is_full_phone(saved) else None,
        })
    await _set_ctx(state, ctx)

    await throw_float_message(state=state, message=message, callback=callback,
                              text=templ.withdraw_main_text(balance, providers),
                              reply_markup=templ.withdraw_main_kb(has_sbp=sbp is not None))


async def _ask_bank(message: Message, state: FSMContext, callback: CallbackQuery | None = None):
    ctx = await _get_ctx(state)
    if ctx.get("bank_id") and ctx.get("bank_name"):
        await state.set_state(None)
        await throw_float_message(state=state, message=message, callback=callback,
                                  text=templ.withdraw_bank_choice_text(ctx["bank_name"]),
                                  reply_markup=templ.withdraw_bank_choice_kb(ctx["bank_name"]))
        return
    await _ask_bank_query(message, state, callback)


async def _ask_bank_query(message: Message, state: FSMContext, callback: CallbackQuery | None = None,
                          error: str | None = None):
    await state.set_state(states.WithdrawStates.waiting_for_bank_query)
    await throw_float_message(state=state, message=message, callback=callback,
                              text=templ.withdraw_enter_bank_text(error),
                              reply_markup=templ.back_kb(calls.WithdrawAction(action="open").pack()))


async def _ask_amount(message: Message, state: FSMContext, callback: CallbackQuery | None = None,
                      error: str | None = None):
    ctx = await _get_ctx(state)
    await state.set_state(states.WithdrawStates.waiting_for_amount)
    await throw_float_message(state=state, message=message, callback=callback,
                              text=templ.withdraw_enter_amount_text(ctx, error),
                              reply_markup=templ.back_kb(calls.WithdrawAction(action="open").pack()))


@router.callback_query(calls.WithdrawAction.filter())
async def callback_withdraw_action(callback: CallbackQuery, callback_data: calls.WithdrawAction, state: FSMContext):
    action = callback_data.action
    message = callback.message

    if action == "open":
        await show_withdraw_menu(message, state, callback=callback)
        return

    ctx = await _get_ctx(state)

    if action == "sbp":
        ctx.pop("phone", None)
        ctx.pop("amount", None)
        await _set_ctx(state, ctx)
        if ctx.get("saved_phone"):
            await throw_float_message(state=state, message=message, callback=callback,
                                      text=templ.withdraw_phone_choice_text(ctx["saved_phone"]),
                                      reply_markup=templ.withdraw_phone_choice_kb(ctx["saved_phone"]))
            return
        action = "phone_new"

    if action == "phone_saved":
        if not ctx.get("saved_phone"):
            await callback.answer("Сохранённый номер не найден", show_alert=True)
            return
        ctx["phone"] = ctx["saved_phone"]
        await _set_ctx(state, ctx)
        await _ask_bank(message, state, callback)
        return

    if action == "phone_new":
        await state.set_state(states.WithdrawStates.waiting_for_phone)
        await throw_float_message(state=state, message=message, callback=callback,
                                  text=templ.withdraw_enter_phone_text(),
                                  reply_markup=templ.back_kb(calls.WithdrawAction(action="open").pack()))
        return

    if action == "bank_saved":
        if not ctx.get("bank_id"):
            await _ask_bank_query(message, state, callback)
            return
        await _ask_amount(message, state, callback)
        return

    if action == "bank_search":
        await _ask_bank_query(message, state, callback)
        return

    if action == "bank_pick":
        names = ctx.get("bank_results") or {}
        bank_id = callback_data.value
        if not bank_id or bank_id not in names:
            await callback.answer("Банк не найден, повторите поиск", show_alert=True)
            return
        ctx["bank_id"] = bank_id
        ctx["bank_name"] = names[bank_id]
        ctx.pop("bank_results", None)
        await _set_ctx(state, ctx)
        await _ask_amount(message, state, callback)
        return

    if action == "confirm":
        await _do_withdraw(callback, state, ctx)
        return

    if action == "cancel_tx":
        await throw_float_message(state=state, message=message, callback=callback,
                                  text="🚫 <b>Отменить заявку на вывод?</b>\n\nДеньги вернутся на баланс Playerok.",
                                  reply_markup=templ.withdraw_cancel_confirm_kb(callback_data.value or ""))
        return

    if action == "cancel_tx_confirm":
        await _do_cancel(callback, state, callback_data.value)
        return

    await callback.answer()


async def _do_withdraw(callback: CallbackQuery, state: FSMContext, ctx: dict):
    phone, bank_id, amount = ctx.get("phone"), ctx.get("bank_id"), ctx.get("amount")
    if not (phone and bank_id and amount):
        await callback.answer("Данные вывода устарели, начните заново", show_alert=True)
        await show_withdraw_menu(callback.message, state, callback=callback)
        return

    # Защита от повторного нажатия: данные сбрасываются ДО отправки запроса.
    ctx.pop("amount", None)
    await _set_ctx(state, ctx)

    account = _get_account()
    if account is None:
        await callback.answer("Нет подключения к Playerok", show_alert=True)
        return

    await callback.answer("Отправляю заявку…")
    try:
        tx = await asyncio.to_thread(
            account.request_withdrawal,
            provider=TransactionProviderIds.SBP,
            account=phone,
            value=amount,
            payment_method_id=None,
            sbp_bank_member_id=bank_id,
        )
    except Exception as e:
        logger.warning("Ошибка вывода через СБП: %s", e)
        await throw_float_message(state=state, message=callback.message,
                                  text=templ.do_action_text(f"❌ Playerok не принял заявку на вывод: {e}"),
                                  reply_markup=templ.back_kb(calls.WithdrawAction(action="open").pack()))
        return

    logger.info("Создана заявка на вывод %s ₽ через СБП (id=%s)", amount, getattr(tx, "id", None))
    tx_id = str(getattr(tx, "id", "") or "")
    await throw_float_message(state=state, message=callback.message,
                              text=templ.withdraw_result_text(tx),
                              reply_markup=templ.withdraw_result_kb(tx_id) if tx_id
                              else templ.back_kb(calls.WithdrawAction(action="open").pack()))


async def _do_cancel(callback: CallbackQuery, state: FSMContext, tx_id: str | None):
    account = _get_account()
    if account is None or not tx_id:
        await callback.answer("Не удалось отменить заявку", show_alert=True)
        return
    try:
        tx = await asyncio.to_thread(account.remove_transaction, tx_id)
    except Exception as e:
        logger.warning("Ошибка отмены вывода %s: %s", tx_id, e)
        await callback.answer(f"Playerok не отменил заявку: {e}"[:190], show_alert=True)
        return
    status = getattr(getattr(tx, "status", None), "name", None) or "—"
    await callback.answer("Заявка отменена" if status != "PENDING" else "Запрос на отмену отправлен", show_alert=True)
    await show_withdraw_menu(callback.message, state, callback=callback)


@router.message(states.WithdrawStates.waiting_for_phone)
async def handler_withdraw_phone(message: Message, state: FSMContext):
    phone = normalize_phone(message.text or "")
    if phone is None:
        await throw_float_message(state=state, message=message,
                                  text=templ.withdraw_enter_phone_text("Не похоже на номер РФ."),
                                  reply_markup=templ.back_kb(calls.WithdrawAction(action="open").pack()))
        return
    ctx = await _get_ctx(state)
    ctx["phone"] = phone
    await _set_ctx(state, ctx)
    await _ask_bank(message, state)


def _search_banks(account, query: str):
    q = query.casefold().replace("-", "").replace(" ", "")
    members = account.get_sbp_bank_members() or []
    return [m for m in members
            if m and q in str(m.name or "").casefold().replace("-", "").replace(" ", "")]


@router.message(states.WithdrawStates.waiting_for_bank_query)
async def handler_withdraw_bank_query(message: Message, state: FSMContext):
    query = (message.text or "").strip()
    if len(query) < 2:
        await _ask_bank_query(message, state, error="Введите хотя бы 2 символа.")
        return
    account = _get_account()
    if account is None:
        await _ask_bank_query(message, state, error="Нет подключения к Playerok.")
        return
    try:
        banks = await asyncio.to_thread(_search_banks, account, query)
    except Exception as e:
        logger.warning("Не удалось получить список банков СБП: %s", e)
        await _ask_bank_query(message, state, error=f"Не удалось получить список банков: {e}")
        return
    if not banks:
        await _ask_bank_query(message, state, error=f"Банк «{query}» не найден.")
        return

    shown = banks[:BANKS_SHOW_LIMIT]
    ctx = await _get_ctx(state)
    ctx["bank_results"] = {str(b.id): str(b.name) for b in shown}
    await _set_ctx(state, ctx)
    await state.set_state(None)
    await throw_float_message(state=state, message=message,
                              text=templ.withdraw_bank_results_text(query, len(banks)),
                              reply_markup=templ.withdraw_bank_results_kb(shown))


@router.message(states.WithdrawStates.waiting_for_amount)
async def handler_withdraw_amount(message: Message, state: FSMContext):
    amount = parse_amount(message.text or "")
    if amount is None:
        await _ask_amount(message, state, error="Введите целое число рублей, например 500.")
        return
    ctx = await _get_ctx(state)
    error = validate_amount(amount, ctx)
    if error:
        await _ask_amount(message, state, error=error)
        return
    ctx["amount"] = amount
    await _set_ctx(state, ctx)
    await state.set_state(None)
    await throw_float_message(state=state, message=message,
                              text=templ.withdraw_confirm_text(ctx),
                              reply_markup=templ.withdraw_confirm_kb())
