from aiogram.filters.callback_data import CallbackData


class PluginsPagination(CallbackData, prefix="plgpag"):
    page: int


class IncludedRestoreItemsPagination(CallbackData, prefix="inrepag"):
    page: int


class ExcludedRestoreItemsPagination(CallbackData, prefix="exrepag"):
    page: int


class CustomCommandsPagination(CallbackData, prefix="cucopag"):
    page: int


class AutoDeliveriesPagination(CallbackData, prefix="audepag"):
    page: int


class MessagesPagination(CallbackData, prefix="messpag"):
    page: int


class MenuPagination(CallbackData, prefix="mainpag"):
    page: int


class ProxyListPagination(CallbackData, prefix="proxpag"):
    page: int