from aiogram import Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from datetime import datetime, timezone
import html

from .. import callback_datas as calls
from ..helpful import get_playerok_bot
from ..utils.message_formatter import format_system_message
from playerokapi.enums import ItemDealStatuses
from playerokapi.types import ChatMessage, ItemDeal

router = Router()


def _resolve_recipient_username(messages: list[ChatMessage], seller_id: str | None) -> str | None:
    seller_id_str = str(seller_id) if seller_id is not None else None
    for msg in messages:
        user = getattr(msg, "user", None)
        if not user:
            continue
        username = getattr(user, "username", None)
        user_id = getattr(user, "id", None)
        if not username:
            continue
        if seller_id_str is not None and str(user_id) == seller_id_str:
            continue
        if username in ("Playerok.com", "Поддержка"):
            continue
        return username
    return None


def _parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime.min
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        return datetime.min


def _select_chat_deal(message_deals: list[ItemDeal], chat_deals: list[ItemDeal]) -> ItemDeal | None:
    candidates: dict[str, ItemDeal] = {}
    for deal in [*(message_deals or []), *(chat_deals or [])]:
        deal_id = getattr(deal, "id", None)
        if not deal_id:
            continue
        prev = candidates.get(deal_id)
        if prev is None or _parse_dt(getattr(deal, "created_at", None)) >= _parse_dt(getattr(prev, "created_at", None)):
            candidates[deal_id] = deal

    if not candidates:
        return None

    ordered = sorted(
        candidates.values(),
        key=lambda d: _parse_dt(getattr(d, "created_at", None)),
        reverse=True
    )
    for deal in ordered:
        if getattr(deal, "status", None) in (ItemDealStatuses.PAID, ItemDealStatuses.PENDING, ItemDealStatuses.SENT):
            return deal
    return ordered[0]


def _chat_history_kb(chat_id: str, username: str | None = None, deal_id: str | None = None) -> InlineKeyboardMarkup:
    rows = []
    if username:
        rows.append(
            [
                InlineKeyboardButton(
                    text="💬 Написать",
                    callback_data=calls.RememberUsername(name=username, do="send_mess").pack(),
                )
            ]
        )
    if deal_id:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🧾 Просмотр сделки",
                    callback_data=calls.DealView(de_id=deal_id).pack(),
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="🔗 Открыть чат", url=f"https://playerok.com/chats/{chat_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(calls.ChatHistory.filter())
async def callback_show_chat_history(callback: CallbackQuery, callback_data: calls.ChatHistory, state: FSMContext):
    """Показывает последние 10 сообщений из чата"""
    try:
        playerok_bot = get_playerok_bot()
        
        # Получаем сообщения чата (последние 24)
        msg_list = playerok_bot.account.get_chat_messages(callback_data.chat_id, count=24)
        
        if not msg_list or not msg_list.messages:
            await callback.answer("❌ Не удалось загрузить историю чата", show_alert=True)
            return

        chat_obj = None
        chat_deals = []
        try:
            chat_obj = playerok_bot.account.get_chat(callback_data.chat_id)
            chat_deals = list(getattr(chat_obj, "deals", []) or [])
        except Exception:
            pass

        message_deals = [msg.deal for msg in msg_list.messages if getattr(msg, "deal", None)]
        selected_deal = _select_chat_deal(message_deals, chat_deals)
        if selected_deal is None:
            try:
                deals_page = playerok_bot.account.get_deals(count=24)
                deals_for_chat = []
                for deal in getattr(deals_page, "deals", []) or []:
                    deal_chat_id = getattr(getattr(deal, "chat", None), "id", None)
                    if deal_chat_id == callback_data.chat_id:
                        deals_for_chat.append(deal)
                selected_deal = _select_chat_deal(deals_for_chat, [])
            except Exception:
                pass
        selected_deal_id = getattr(selected_deal, "id", None)
        
        # Берем последние 10 сообщений (список отсортирован по убыванию)
        messages = list(msg_list.messages)[:10]
        # Переворачиваем для хронологического порядка
        messages.reverse()
        # Формируем текст с историей
        history_text = f"📜 <b>История чата (последние {len(messages)} сообщений)</b>\n"
        history_text += f"<b>Ссылка:</b> <a href='https://playerok.com/chats/{callback_data.chat_id}'>Открыть чат</a>\n\n"
        
        total_length = len(history_text)
        messages_text = []

        for msg in messages:
            msg: ChatMessage
            # Проверяем, является ли сообщение системным
            emoji, formatted_msg = format_system_message(msg.text, msg.deal)
            
            if formatted_msg:
                # Системное сообщение
                try:
                    msg_time = datetime.fromisoformat(msg.created_at).strftime("%d.%m %H:%M")
                except:
                    msg_time = "??:??"
                
                line = f"{formatted_msg} <i>({msg_time})</i>\n\n"
            else:
                # Обычное сообщение от пользователя
                # Определяем эмодзи отправителя
                if msg.user.username in ["Playerok.com", "Поддержка"]:
                    emoji = "🆘"
                elif msg.user.id == playerok_bot.account.id:
                    emoji = "🤖"  # Вы (продавец)
                else:
                    emoji = "👤"  # Покупатель
                
                # Форматируем время
                try:
                    msg_time = datetime.fromisoformat(msg.created_at).strftime("%d.%m %H:%M")
                except:
                    msg_time = "??:??"

                msg_text = html.escape(msg.text) if msg.text else ""
                # if msg.file:
                #     msg_text += f" [📎 {html.escape(msg.file.filename) if msg.file.filename else ''}]"

                if msg_text:
                    # Ограничиваем длину сообщения
                    if len(msg_text) > 100:
                        msg_text = msg_text[:100] + "..."

                    # убираем лишние \n для компактности и крутости
                    lines = msg_text.split('\n')
                    split_text = []
                    for line in lines:
                        if line:
                            split_text.append(line)
                        else:
                            pass
                    if split_text[0] == '\n':
                        split_text.pop(0)
                    if split_text[-1] == '\n':
                        split_text.pop(-1)
                    final_text = '\n'.join(split_text)
                else:
                    final_text = ''

                images_ix = 1
                image_row = ''
                if msg.images:
                    for image in msg.images.image_list:
                        image_row += f'<a href="{image.url}">фото_{images_ix}</a> '
                        images_ix += 1
                if msg.file:
                    image_row += f'<a href="{msg.file.url}">фото_{images_ix}</a> '
                    images_ix += 1

                if not final_text and not image_row:
                    continue

                if msg_text:
                    line = f"{emoji} <b>{html.escape(msg.user.username)}</b> ({msg_time}):\n<blockquote>{final_text}</blockquote>\n"
                else:
                    line = f"{emoji} <b>{html.escape(msg.user.username)}</b> ({msg_time}):\n"
                if image_row:
                    line += image_row
                    line += '\n'
                line += '\n'
            
            # Проверяем, не превысит ли общая длина 4000 символов (лимит Telegram)
            if total_length + len(line) > 3900:
                messages_text.append("<i>⚠️ Сообщения слишком крупные, показаны не все</i>")
                break
            
            messages_text.append(line)
            total_length += len(line)
        
        history_text += "".join(messages_text)

        recipient_username = _resolve_recipient_username(list(msg_list.messages), playerok_bot.account.id)
        if not recipient_username:
            try:
                if chat_obj is None:
                    chat_obj = playerok_bot.account.get_chat(callback_data.chat_id)
                seller_id_str = str(playerok_bot.account.id) if playerok_bot.account.id is not None else None
                for user in chat_obj.users:
                    username = getattr(user, "username", None)
                    user_id = getattr(user, "id", None)
                    if not username:
                        continue
                    if seller_id_str is not None and str(user_id) == seller_id_str:
                        continue
                    if username in ("Playerok.com", "Поддержка"):
                        continue
                    recipient_username = username
                    break
            except Exception:
                pass
        
        await callback.message.edit_text(
            history_text,
            reply_markup=_chat_history_kb(callback_data.chat_id, recipient_username, selected_deal_id),
            disable_web_page_preview=True,
            parse_mode="HTML"
        )
        
    except Exception as e:
        await callback.answer(f"❌ Ошибка загрузки истории: {str(e)}", show_alert=True)
