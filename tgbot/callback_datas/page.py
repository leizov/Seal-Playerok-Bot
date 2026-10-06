from aiogram.filters.callback_data import CallbackData
from uuid import UUID


class PluginPage(CallbackData, prefix="plgpage"):
    uuid: UUID


class PluginCommands(CallbackData, prefix="plgcmds"):
    uuid: UUID


class MessagePage(CallbackData, prefix="messpage"):
    message_id: str


class CustomCommandPage(CallbackData, prefix="cucopage"):
    command: str


class AutoDeliveryPage(CallbackData, prefix="audepage"):
    index: int


class DeliveryHistoryRecord(CallbackData, prefix="adhrec"):
    rec_id: int
    page: int


class ProxyPage(CallbackData, prefix="proxpage"):
    proxy_id: int