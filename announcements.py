"""
Система рассылки объявлений для Seal Playerok Bot.
Получает объявления с GitHub Gist и отправляет всем пользователям.
"""
from __future__ import annotations
from typing import TYPE_CHECKING
from logging import getLogger
import requests
import json
import os

# Импорт путей из центрального модуля
import paths

if TYPE_CHECKING:
    from tgbot.telegrambot import TelegramBot

logger = getLogger("seal.announcements")


REQUESTS_DELAY = 600  # 10 минут

GIST_ID = "37681cb21e62d15b501f23fa4c9d29f2" 


def get_cache_path() -> str:
    """Возвращает путь к файлу кэша."""
    os.makedirs(paths.CACHE_DIR, exist_ok=True)
    return paths.ANNOUNCEMENT_TAG_FILE


def get_last_tag() -> str | None:
    """
    Загружает тег последнего объявления из кэша.
    
    :return: тег последнего объявления или None
    """
    cache_path = get_cache_path()
    if not os.path.exists(cache_path):
        return None
    try:
        with open(cache_path, "r", encoding="UTF-8") as f:
            return f.read().strip()
    except:
        return None


def save_last_tag(tag: str):
    """
    Сохраняет тег последнего объявления в кэш.
    
    :param tag: тег объявления
    """
    cache_path = get_cache_path()
    try:
        with open(cache_path, "w", encoding="UTF-8") as f:
            f.write(tag)
    except Exception as e:
        logger.error(f"Ошибка сохранения тега объявления: {e}")


LAST_TAG = get_last_tag()


def get_announcement(ignore_last_tag: bool = False) -> dict | None:
    """
    Получает информацию об объявлении с GitHub Gist.
    
    :param ignore_last_tag: игнорировать сохранённый тег
    :return: словарь с данными объявления или None
    """
    global LAST_TAG, GIST_ID
    
    if not GIST_ID:
        return None
    
    headers = {
        'X-GitHub-Api-Version': '2022-11-28',
        'accept': 'application/vnd.github+json'
    }
    
    try:
        response = requests.get(
            f"https://api.github.com/gists/{GIST_ID}", 
            headers=headers,
            timeout=10
        )
        if response.status_code != 200:
            return None
        
        gist_data = response.json()
        files = gist_data.get("files", {})
        
        # Берём первый файл из Gist (любое имя)
        if not files:
            return None
        
        first_file = list(files.values())[0]
        content = json.loads(first_file.get("content", "{}"))
        
        # Проверяем тег
        if content.get("tag") == LAST_TAG and not ignore_last_tag:
            return None
        
        return content
        
    except Exception as e:
        logger.error(f"Ошибка получения объявления: {e}")
        return None


def download_photo(url: str) -> bytes | None:
    """
    Загружает фото по URL.
    
    :param url: URL фотографии
    :return: фотографию в байтах или None
    """
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            return response.content
    except:
        pass
    return None


def get_text(data: dict) -> str | None:
    """Получает текст объявления."""
    return data.get("text")


def get_photo_bytes(data: dict) -> bytes | None:
    """Получает фото объявления."""
    photo_url = data.get("photo")
    if photo_url:
        return download_photo(photo_url)
    return None


def get_pin(data: dict) -> bool:
    """Нужно ли закреплять сообщение."""
    return bool(data.get("pin", False))


def get_buttons(data: dict) -> list | None:
    """
    Получает кнопки для клавиатуры.
    Формат: [{"text": "Кнопка", "url": "https://..."}]
    """
    return data.get("buttons")


async def send_announcement_to_users(tg_bot: TelegramBot, data: dict):
    """
    Отправляет объявление всем авторизованным пользователям.
    
    :param tg_bot: экземпляр Telegram бота
    :param data: данные объявления
    """
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from settings import Settings as sett
    
    text = get_text(data)
    photo = get_photo_bytes(data)
    pin = get_pin(data)
    buttons_data = get_buttons(data)
    
    if not text and not photo:
        return
    
    # Формируем клавиатуру
    keyboard = None
    if buttons_data:
        rows = []
        for btn in buttons_data:
            if btn.get("text") and btn.get("url"):
                rows.append([InlineKeyboardButton(
                    text=btn["text"], 
                    url=btn["url"]
                )])
        if rows:
            keyboard = InlineKeyboardMarkup(inline_keyboard=rows)
    
    # Получаем список пользователей
    config = sett.get("config")
    users = config["telegram"]["bot"].get("signed_users", [])
    
    logger.info(f"📢 Отправка объявления {len(users)} пользователям...")
    
    for user_id in users:
        try:
            if photo:
                msg = await tg_bot.bot.send_photo(
                    chat_id=user_id,
                    photo=photo,
                    caption=text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                msg = await tg_bot.bot.send_message(
                    chat_id=user_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            
            # Закрепляем если нужно
            if pin and msg:
                try:
                    await tg_bot.bot.pin_chat_message(
                        chat_id=user_id,
                        message_id=msg.message_id,
                        disable_notification=True
                    )
                except:
                    pass
                    
            logger.info(f"✅ Объявление отправлено пользователю {user_id}")
            
        except Exception as e:
            logger.warning(f"❌ Не удалось отправить объявление пользователю {user_id}: {e}")
        
        # Небольшая задержка между отправками
        await asyncio.sleep(0.1)


async def check_and_send_announcement(tg_bot: TelegramBot, ignore_last_tag: bool = False):
    """
    Проверяет наличие нового объявления и отправляет его.
    
    :param tg_bot: экземпляр Telegram бота
    :param ignore_last_tag: игнорировать сохранённый тег
    """
    global LAST_TAG
    
    data = get_announcement(ignore_last_tag=ignore_last_tag)
    if not data:
        return
    
    # Если это первый запуск - просто сохраняем тег
    if not LAST_TAG and not ignore_last_tag:
        LAST_TAG = data.get("tag", "")
        save_last_tag(LAST_TAG)
        return
    
    # Сохраняем новый тег
    if not ignore_last_tag:
        LAST_TAG = data.get("tag", "")
        save_last_tag(LAST_TAG)
    
    # Отправляем объявление
    await send_announcement_to_users(tg_bot, data)


import asyncio

async def announcements_loop(tg_bot: TelegramBot):
    """
    Бесконечный цикл проверки объявлений.
    
    :param tg_bot: экземпляр Telegram бота
    """
    global GIST_ID
    
    if not GIST_ID:
        logger.info("📢 Система объявлений отключена (GIST_ID не задан)")
        return
    
    # logger.info("📢 Система объявлений запущена")
    
    while True:
        try:
            await check_and_send_announcement(tg_bot)
        except Exception as e:
            logger.error(f"Ошибка в цикле объявлений: {e}")
        
        await asyncio.sleep(REQUESTS_DELAY)


async def start_announcements_loop(tg_bot: TelegramBot):
    """
    Запускает цикл проверки объявлений как asyncio task в текущем event loop.
    
    :param tg_bot: экземпляр Telegram бота
    """
    asyncio.create_task(announcements_loop(tg_bot))


