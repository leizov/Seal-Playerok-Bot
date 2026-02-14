"""
Модуль мониторинга отзывов после подтверждения сделки.

Фоновая задача, которая:
1. Хранит информацию о подтвержденных сделках в файле
2. Периодически проверяет наличие отзывов
3. Отправляет сообщение покупателю после получения отзыва
4. Удаляет сделку из мониторинга после истечения срока ожидания
"""

from __future__ import annotations
import os
import json
import asyncio
import time
from datetime import datetime, timezone, timedelta
from logging import getLogger
from typing import TYPE_CHECKING

# Импорт путей из центрального модуля
import paths

if TYPE_CHECKING:
    from playerokapi.account import Account
    from playerokapi.types import ItemDeal


logger = getLogger("seal.review_monitor")

# Путь к файлу с мониторингом сделок
DEALS_FILE = paths.DEALS_MONITOR_FILE


def load_deals() -> dict:
    """Загружает сделки из файла"""
    if not os.path.exists(DEALS_FILE):
        return {}
    
    try:
        with open(DEALS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки файла мониторинга сделок: {e}")
        return {}


def save_deals(deals: dict):
    """Сохраняет сделки в файл"""
    os.makedirs(os.path.dirname(DEALS_FILE), exist_ok=True)
    
    try:
        with open(DEALS_FILE, "w", encoding="utf-8") as f:
            json.dump(deals, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения файла мониторинга сделок: {e}")


def add_deal_to_monitor(deal: ItemDeal, chat_id: str):
    """
    Добавляет сделку в мониторинг после подтверждения.
    
    :param deal: Объект сделки
    :param chat_id: ID чата
    """
    deals = load_deals()
    
    deal_data = {
        "chat_id": chat_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "deal_id": deal.id,
        "user_username": deal.user.username,
        "item_name": deal.item.name,
        "last_check": None
    }
    
    deals[str(deal.id)] = deal_data
    save_deals(deals)
    
    logger.info(f"Сделка {deal.id} добавлена в мониторинг отзывов")


def remove_deal_from_monitor(deal_id: str):
    """
    Удаляет сделку из мониторинга.
    
    :param deal_id: ID сделки
    """
    deals = load_deals()
    
    if str(deal_id) in deals:
        del deals[str(deal_id)]
        save_deals(deals)
        logger.info(f"Сделка {deal_id} удалена из мониторинга отзывов")


async def check_reviews_task(account: Account, send_message_callback, msg_callback, config: dict, log_new_review_callback=None):
    """
    Фоновая задача для проверки отзывов.
    
    :param account: Аккаунт Playerok
    :param send_message_callback: Функция для отправки сообщения в чат
    :param msg_callback: Функция для получения текста сообщения
    :param config: Конфигурация бота
    :param log_new_review_callback: Функция для логирования нового отзыва (отправка в TG)
    """
    # logger.info("Фоновая задача мониторинга отзывов запущена")
    
    while True:
        try:
            # Проверяем, включен ли мониторинг
            review_config = config.get("playerok", {}).get("review_monitoring", {})
            if not review_config.get("enabled", False):
                await asyncio.sleep(60)  # Если выключен - ждем минуту и проверяем снова
                continue
            
            wait_days = review_config.get("wait_days", 7)
            check_interval = review_config.get("check_interval", 120)
            
            deals = load_deals()
            current_time = datetime.now(timezone.utc)
            
            for deal_id, deal_data in list(deals.items()):
                try:
                    started_at = datetime.fromisoformat(deal_data["started_at"])
                    time_elapsed = current_time - started_at
                    
                    # Если прошло больше времени, чем wait_days - удаляем из мониторинга
                    if time_elapsed > timedelta(days=wait_days):
                        logger.info(
                            f"Сделка {deal_id}: превышен лимит ожидания "
                            f"({wait_days} дней), удаляем из мониторинга"
                        )
                        remove_deal_from_monitor(deal_id)
                        continue
                    
                    # Получаем актуальную информацию о сделке
                    deal = account.get_deal(deal_id)
                    
                    # Проверяем наличие отзыва
                    if deal.review is not None:
                        logger.info(
                            f"Сделка {deal_id}: обнаружен отзыв от {deal.review.creator.username}"
                        )
                        
                        # Отправляем уведомление в Telegram (если включено)
                        if log_new_review_callback:
                            try:
                                await log_new_review_callback(deal, deal_data["chat_id"])
                                
                            except Exception as e:
                                logger.error(f"Ошибка отправки уведомления о отзыве в Telegram: {e}")
                        
                        # Отправляем сообщение благодарности покупателю
                        message_text = msg_callback("new_review_response")
                        if message_text:
                            send_message_callback(deal_data["chat_id"], message_text)
                            logger.info(
                                f"Сделка {deal_id}: отправлено сообщение благодарности за отзыв"
                            )
                        
                        # Удаляем из мониторинга
                        remove_deal_from_monitor(deal_id)
                    else:
                        # Обновляем время последней проверки
                        deal_data["last_check"] = current_time.isoformat()
                        deals[deal_id] = deal_data
                        
                except Exception as e:
                    logger.error(f"Ошибка проверки сделки {deal_id}: {e}")
                    continue

            
            # Ждем перед следующей проверкой
            await asyncio.sleep(check_interval)
            
        except Exception as e:
            logger.error(f"Критическая ошибка в мониторинге отзывов: {e}")
            await asyncio.sleep(60)


def get_monitoring_stats() -> dict:
    """
    Возвращает статистику по мониторингу отзывов.
    
    :return: Словарь со статистикой
    """
    deals = load_deals()
    
    if not deals:
        return {
            "total": 0,
            "deals": []
        }
    
    current_time = datetime.now(timezone.utc)
    deals_list = []
    
    for deal_id, deal_data in deals.items():
        started_at = datetime.fromisoformat(deal_data["started_at"])
        time_elapsed = current_time - started_at
        
        deals_list.append({
            "deal_id": deal_id,
            "user": deal_data["user_username"],
            "item": deal_data["item_name"],
            "days_elapsed": time_elapsed.days,
            "started_at": started_at.strftime("%d.%m.%Y %H:%M")
        })
    
    return {
        "total": len(deals),
        "deals": deals_list
    }
