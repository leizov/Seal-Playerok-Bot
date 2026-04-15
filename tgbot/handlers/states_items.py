from aiogram import Router, types
from aiogram.fsm.context import FSMContext

from .. import states


router = Router()


@router.message(states.ItemsStates.waiting_for_name_query)
async def handler_waiting_for_items_name_query(message: types.Message, state: FSMContext):
    query = (message.text or "").strip()
    await state.set_state(None)

    data = await state.get_data()
    filters = data.get("items_filters") if isinstance(data.get("items_filters"), dict) else {}
    ui_state = data.get("items_ui") if isinstance(data.get("items_ui"), dict) else {}

    filters["name_query"] = query
    ui_state["screen"] = "list"
    ui_state["page"] = 0
    await state.update_data(items_filters=filters, items_ui=ui_state)

    from ..callback_handlers.items import show_items_menu

    await show_items_menu(message=message, state=state, force_reload=True)
