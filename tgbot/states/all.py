from aiogram.fsm.state import State, StatesGroup
from .quick_replies import QuickReplyStates


class SystemStates(StatesGroup):
    waiting_for_password = State()


class ActionsStates(StatesGroup):
    waiting_for_message_text = State()


class SettingsStates(StatesGroup):
    waiting_for_token = State()
    waiting_for_user_agent = State()

    waiting_for_requests_timeout = State()
    waiting_for_listener_requests_delay = State()
    waiting_for_proxy = State()
    waiting_for_new_proxy = State()

    waiting_for_tg_logging_chat_id = State()
    waiting_for_watermark_value = State()


class MessagesStates(StatesGroup):
    waiting_for_page = State()
    waiting_for_message_text = State()


class RestoreItemsStates(StatesGroup):
    waiting_for_new_included_restore_item_keyphrases = State()
    waiting_for_new_included_restore_items_keyphrases_file = State()
    waiting_for_new_excluded_restore_item_keyphrases = State()
    waiting_for_new_excluded_restore_items_keyphrases_file = State()


class CustomCommandsStates(StatesGroup):
    waiting_for_page = State()
    waiting_for_new_custom_command = State()
    waiting_for_new_custom_command_answer = State()
    waiting_for_custom_command_answer = State()


class AutoDeliveriesStates(StatesGroup):
    waiting_for_page = State()
    waiting_for_new_auto_delivery_keyphrases = State()
    waiting_for_new_auto_delivery_message = State()
    waiting_for_new_auto_delivery_multi_items = State()
    waiting_for_auto_delivery_keyphrases = State()
    waiting_for_auto_delivery_message = State()
    waiting_for_auto_delivery_add_items = State()
    waiting_for_auto_delivery_replace_items = State()


class AutoResponseStates(StatesGroup):
    waiting_for_greeting_text = State()
    waiting_for_greeting_cooldown = State()  # Ожидание ввода интервала приветствий (дней)
    waiting_for_confirmation_seller_text = State()
    waiting_for_confirmation_buyer_text = State()
    waiting_for_deal_has_problem_text = State()
    waiting_for_deal_problem_resolved_text = State()
    waiting_for_review_text = State()


class ReviewMonitorStates(StatesGroup):
    waiting_for_days = State()


class AutoReminderStates(StatesGroup):
    waiting_for_interval_hours = State()
    waiting_for_max_reminders = State()
    waiting_for_message_text = State()


class RaiseItemsStates(StatesGroup):
    waiting_for_new_included_raise_item_keyphrases = State()
    waiting_for_new_included_raise_items_keyphrases_file = State()
    waiting_for_new_excluded_raise_item_keyphrases = State()
    waiting_for_new_excluded_raise_items_keyphrases_file = State()
    waiting_for_raise_interval = State()


class ConfigBackupStates(StatesGroup):
    waiting_for_backup_file = State()
    waiting_for_restore_confirmation = State()
