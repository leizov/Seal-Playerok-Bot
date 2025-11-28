from aiogram.filters.callback_data import CallbackData


class MenuNavigation(CallbackData, prefix="menpag"):
    to: str


class SettingsNavigation(CallbackData, prefix="sepag"):
    to: str


class BotSettingsNavigation(CallbackData, prefix="bspag"):
    to: str


class ItemsSettingsNavigation(CallbackData, prefix="ispag"):
    to: str


class InstructionNavigation(CallbackData, prefix="inspag"):
    to: str


class ProfileNavigation(CallbackData, prefix="propag"):
    to: str


class MessagesNavigation(CallbackData, prefix="mespag"):
    to: str


class StatsNavigation(CallbackData, prefix="stapag"):
    to: str


class LogsNavigation(CallbackData, prefix="lopag"):
    to: str


class ReviewMonitorNavigation(CallbackData, prefix="rmpag"):
    to: str