from aiogram.filters.callback_data import CallbackData


class RememberUsername(CallbackData, prefix="rech"):
    name: str
    do: str


class RememberDealId(CallbackData, prefix="rede"):
    de_id: str
    do: str


class DeleteIncludedRestoreItem(CallbackData, prefix="delinre"):
    index: int


class DeleteExcludedRestoreItem(CallbackData, prefix="delexre"):
    index: int


class AutoResponseToggle(CallbackData, prefix="artog"):
    message_type: str  # greeting, confirmation_seller, confirmation_buyer, review


class AutoResponseEdit(CallbackData, prefix="aredit"):
    message_type: str  # greeting, confirmation_seller, confirmation_buyer, review


class LogsAction(CallbackData, prefix="logact"):
    action: str


class ChatHistory(CallbackData, prefix="chath"):
    chat_id: str


class QuickReplySelect(CallbackData, prefix="qrsel"):
    username: str
    reply_name: str


class QuickReplyAction(CallbackData, prefix="qract"):
    action: str  # add, edit, delete
    reply_name: str | None = None


class ReviewMonitorToggle(CallbackData, prefix="rmtog"):
    pass  # Просто переключение вкл/выкл


class ReviewMonitorAction(CallbackData, prefix="rmact"):
    action: str  # set_days


class SetWatermark(CallbackData, prefix="setwm"):
    value: str


class GreetingCooldownEdit(CallbackData, prefix="grcool"):
    pass  # Активирует режим ввода нового интервала