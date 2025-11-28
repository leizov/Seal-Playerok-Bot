from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from datetime import datetime

from .. import callback_datas as calls
from ..helpful import get_playerok_bot
from ..templates.main import destroy_kb
from ..utils.message_formatter import format_system_message

router = Router()


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
                    emoji = "👤"  # Вы (продавец)
                else:
                    emoji = "💬"  # Покупатель
                
                # Форматируем время
                try:
                    msg_time = datetime.fromisoformat(msg.created_at).strftime("%d.%m %H:%M")
                except:
                    msg_time = "??:??"
                
                # Формируем текст сообщения
                msg_text = msg.text or ""
                if msg.file:
                    msg_text += f" [📎 {msg.file.filename}]"
                
                # Ограничиваем длину сообщения
                if len(msg_text) > 100:
                    msg_text = msg_text[:100] + "..."
                
                line = f"{emoji} <b>{msg.user.username}</b> ({msg_time}):\n{msg_text}\n\n"
            
            # Проверяем, не превысит ли общая длина 4000 символов (лимит Telegram)
            if total_length + len(line) > 3900:
                messages_text.append("<i>⚠️ Сообщения слишком крупные, показаны не все</i>")
                break
            
            messages_text.append(line)
            total_length += len(line)
        
        history_text += "".join(messages_text)
        
        await callback.message.edit_text(
            history_text,
            reply_markup=destroy_kb(),
            disable_web_page_preview=True,
            parse_mode="HTML"
        )
        
    except Exception as e:
        await callback.answer(f"❌ Ошибка загрузки истории: {str(e)}", show_alert=True)
