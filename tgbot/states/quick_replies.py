from aiogram.fsm.state import State, StatesGroup


class QuickReplyStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_text = State()
    editing_text = State()
