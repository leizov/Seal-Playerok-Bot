"""
Меню «📡 Подключение к Telegram»: выбор способа (напрямую / воркер / прокси),
ввод и удаление воркера и прокси. Любой способ проверяется до того, как бот на него перейдёт.
"""
import html
from logging import getLogger

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from settings import Settings as sett
from core import tg_connection as tgc

from .. import templates as templ
from .. import callback_datas as calls
from .. import states
from ..helpful import throw_float_message


logger = getLogger("tgbot.tg_connection")
router = Router()


def _tg_bot():
    from ..telegrambot import get_telegram_bot
    return get_telegram_bot()


async def _show_menu(state: FSMContext, message: Message, callback: CallbackQuery | None = None,
                     notice: str | None = None):
    await state.set_state(None)
    text = templ.settings_tgconn_text()
    if notice:
        text = f"{notice}\n{text}"
    await throw_float_message(
        state=state, message=message, text=text,
        reply_markup=templ.settings_tgconn_kb(), callback=callback,
    )


def _fail_text(route: str, result: tgc.ProbeResult) -> str:
    text = (
        f"❌ <b>Не переключаю: {tgc.ROUTE_TITLES[route]} Telegram не отвечает.</b>\n"
        f"Причина: {html.escape(tgc.describe_reason(result.reason))}."
    )
    if result.error:
        text += f"\n<code>{html.escape(result.error[:200])}</code>"
    text += "\nБот продолжает работать текущим способом.\n"
    return text


@router.callback_query(F.data.startswith("tgconn:use:"))
async def callback_tgconn_use(callback: CallbackQuery, state: FSMContext):
    route = callback.data.split(":", 2)[2]
    config = sett.get("config")
    if route not in tgc.ROUTES or not tgc.is_route_configured(route, config):
        await callback.answer("Этот способ ещё не настроен", show_alert=True)
        return
    tg_bot = _tg_bot()
    if tg_bot is None:
        await callback.answer("Telegram-бот не запущен", show_alert=True)
        return

    await callback.answer("Проверяю подключение…")
    await throw_float_message(
        state=state, message=callback.message,
        text=templ.settings_tgconn_float_text(
            f"⏳ Проверяю, отвечает ли Telegram {html.escape(tgc.describe_route(route, config))}…\n"
            f"Это займёт до 40 секунд."
        ),
    )
    result = await tg_bot.switch_route(route, make_preferred=True)
    if result.ok:
        notice = f"✅ <b>Основной способ: {tgc.ROUTE_TITLES[route]}.</b> Проверка пройдена.\n"
    else:
        notice = _fail_text(route, result)
    await _show_menu(state, callback.message, notice=notice)


@router.callback_query(F.data == "tgconn:set:worker")
async def callback_tgconn_set_worker(callback: CallbackQuery, state: FSMContext):
    await state.set_state(states.SettingsStates.waiting_for_tg_worker_url)
    await throw_float_message(
        state=state, message=callback.message,
        text=templ.tgconn_worker_instruction_text(),
        reply_markup=templ.tgconn_back_kb(), callback=callback,
    )


@router.callback_query(F.data == "tgconn:set:proxy")
async def callback_tgconn_set_proxy(callback: CallbackQuery, state: FSMContext):
    await state.set_state(states.SettingsStates.waiting_for_tg_proxy)
    await throw_float_message(
        state=state, message=callback.message,
        text=templ.tgconn_proxy_instruction_text(),
        reply_markup=templ.tgconn_back_kb(), callback=callback,
    )


async def _save_and_maybe_switch(state: FSMContext, message: Message, route: str, value: str,
                                 username: str | None):
    config = sett.get("config")
    # Если основной способ не задан явно, новое значение не должно тихо стать основным:
    # фиксируем тот способ, который был основным до сохранения.
    preferred_before = tgc.preferred_route(config)
    if not str(config["telegram"]["api"].get("mode") or "").strip():
        config["telegram"]["api"]["mode"] = preferred_before
    key = "custom_api_url" if route == tgc.ROUTE_WORKER else "proxy"
    config["telegram"]["api"][key] = value
    sett.set("config", config)

    tg_bot = _tg_bot()
    title = "Воркер" if route == tgc.ROUTE_WORKER else "Прокси"
    notice = f"✅ <b>{title} работает и сохранён</b> (Telegram ответил, бот @{html.escape(username or '')}).\n"
    if tg_bot is not None and tg_bot.active_route == route:
        # Изменили адрес способа, через который бот подключён сейчас, — переподключаемся.
        await tg_bot.switch_route(route, make_preferred=False)
        notice += "Бот переподключился с новыми настройками.\n"
    elif tgc.preferred_route(sett.get("config")) != route:
        notice += f"Чтобы сделать его основным, нажмите кнопку способа ниже. Пока он — запасной.\n"
    await _show_menu(state, message, notice=notice)


@router.message(states.SettingsStates.waiting_for_tg_worker_url, F.text)
async def handler_tg_worker_url(message: Message, state: FSMContext):
    try:
        url = tgc.normalize_worker_url(message.text)
    except ValueError as e:
        await throw_float_message(
            state=state, message=message,
            text=templ.settings_tgconn_float_text(
                f"❌ Адрес не подходит: {html.escape(str(e))}.\nОтправьте адрес ещё раз."
            ),
            reply_markup=templ.tgconn_back_kb(),
        )
        return

    await throw_float_message(
        state=state, message=message,
        text=templ.settings_tgconn_float_text(f"⏳ Проверяю Telegram через {html.escape(url)}…"),
    )
    config = sett.get("config")
    result = await tgc.probe_route_with_retries(
        config["telegram"]["api"]["token"], tgc.ROUTE_WORKER, config, worker_url=url, attempts=2
    )
    if not result.ok:
        await throw_float_message(
            state=state, message=message,
            text=templ.settings_tgconn_float_text(
                f"❌ Через воркер Telegram не отвечает: {html.escape(tgc.describe_reason(result.reason))}.\n\n"
                "Проверьте, что код воркера вставлен целиком и нажат Deploy, а адрес скопирован полностью. "
                "Адрес не сохранён — отправьте его ещё раз или вернитесь назад."
            ),
            reply_markup=templ.tgconn_back_kb(),
        )
        return
    await _save_and_maybe_switch(state, message, tgc.ROUTE_WORKER, url, result.username)


@router.message(states.SettingsStates.waiting_for_tg_proxy, F.text)
async def handler_tg_proxy(message: Message, state: FSMContext):
    try:
        _, normalized = tgc.build_proxy_url(message.text)
    except Exception as e:
        await throw_float_message(
            state=state, message=message,
            text=templ.settings_tgconn_float_text(
                f"❌ Неверный формат прокси: {html.escape(str(e))}.\nОтправьте прокси ещё раз."
            ),
            reply_markup=templ.tgconn_back_kb(),
        )
        return

    await throw_float_message(
        state=state, message=message,
        text=templ.settings_tgconn_float_text("⏳ Проверяю Telegram через прокси…"),
    )
    config = sett.get("config")
    result = await tgc.probe_route_with_retries(
        config["telegram"]["api"]["token"], tgc.ROUTE_PROXY, config, proxy=normalized, attempts=2
    )
    if not result.ok:
        await throw_float_message(
            state=state, message=message,
            text=templ.settings_tgconn_float_text(
                f"❌ Через прокси Telegram не отвечает: {html.escape(tgc.describe_reason(result.reason))}.\n\n"
                "Проверьте срок действия, логин/пароль, регион (не RU) и тип (для SOCKS5 — приставка socks5://). "
                "Прокси не сохранён — отправьте его ещё раз или вернитесь назад."
            ),
            reply_markup=templ.tgconn_back_kb(),
        )
        return
    await _save_and_maybe_switch(state, message, tgc.ROUTE_PROXY, normalized, result.username)


@router.callback_query(F.data.startswith("tgconn:del:"))
async def callback_tgconn_delete(callback: CallbackQuery, state: FSMContext):
    route = callback.data.split(":", 2)[2]
    if route not in (tgc.ROUTE_WORKER, tgc.ROUTE_PROXY):
        await callback.answer()
        return
    config = sett.get("config")
    token = config["telegram"]["api"]["token"]
    tg_bot = _tg_bot()
    active = tg_bot.active_route if tg_bot is not None else tgc.preferred_route(config)

    # Удаляем способ, через который бот работает сейчас, только если есть рабочая замена.
    remaining = dict(config)
    remaining["telegram"] = dict(config["telegram"])
    remaining["telegram"]["api"] = dict(config["telegram"]["api"])
    remaining["telegram"]["api"]["custom_api_url" if route == tgc.ROUTE_WORKER else "proxy"] = ""
    if remaining["telegram"]["api"].get("mode") == route:
        remaining["telegram"]["api"]["mode"] = ""

    if active == route and tg_bot is not None:
        await callback.answer("Ищу другой рабочий способ…")
        found, _ = await tgc.find_working_route(token, remaining)
        if not found:
            await _show_menu(
                state, callback.message,
                notice=(
                    "❌ <b>Не удаляю:</b> бот сейчас работает через этот способ, "
                    "а остальные способы не отвечают. Иначе бот потеряет связь с Telegram.\n"
                ),
            )
            return
        remaining["telegram"]["api"]["mode"] = found.route if not remaining["telegram"]["api"].get("mode") else remaining["telegram"]["api"]["mode"]
        sett.set("config", remaining)
        await tg_bot.switch_route(found.route, make_preferred=False)
        notice = f"🗑 Удалено. Бот переключился: {tgc.ROUTE_TITLES[found.route]}.\n"
    else:
        sett.set("config", remaining)
        await callback.answer("Удалено")
        notice = "🗑 Удалено.\n"
    await _show_menu(state, callback.message, notice=notice)


@router.callback_query(F.data == "tgconn:check")
async def callback_tgconn_check(callback: CallbackQuery, state: FSMContext):
    config = sett.get("config")
    token = config["telegram"]["api"]["token"]
    await callback.answer("Проверяю…")
    await throw_float_message(
        state=state, message=callback.message,
        text=templ.settings_tgconn_float_text("⏳ Проверяю все настроенные способы подключения…"),
    )
    lines = []
    for route in tgc.ROUTES:
        if not tgc.is_route_configured(route, config):
            lines.append(f"{tgc.ROUTE_EMOJI[route]} {tgc.ROUTE_TITLES[route]}: ➖ не настроен")
            continue
        result = await tgc.probe_route(token, route, config)
        mark = "✅ работает" if result.ok else f"❌ {html.escape(tgc.describe_reason(result.reason))}"
        lines.append(f"{tgc.ROUTE_EMOJI[route]} {tgc.ROUTE_TITLES[route]}: {mark}")
    await _show_menu(state, callback.message, notice="🩺 <b>Результат проверки</b>\n" + "\n".join(lines) + "\n")


@router.callback_query(F.data == "tgconn:toggle_fallback")
async def callback_tgconn_toggle_fallback(callback: CallbackQuery, state: FSMContext):
    config = sett.get("config")
    api = config["telegram"]["api"]
    api["auto_fallback"] = not api.get("auto_fallback", True)
    sett.set("config", config)
    await _show_menu(state, callback.message, callback=callback)
