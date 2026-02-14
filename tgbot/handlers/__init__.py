from aiogram import Router
from .commands import router as commands_router
from .log_commands import router as log_commands_router
from .states_system import router as states_system_router
from .states_settings import router as states_settings_router
from .states_actions import router as states_actions_router
from .states_restore import router as states_restore_router
from .states_raise import router as states_raise_router
from .states_comms import router as states_comms_router
from .states_delivs import router as states_delivs_router
from .states_autoresponse import router as states_autoresponse_router
from .states_review_monitor import router as states_review_monitor_router
from .states_quick_replies import router as states_quick_replies_router

router = Router()
router.include_routers(
    commands_router,
    log_commands_router,
    states_system_router,
    states_settings_router,
    states_actions_router,
    states_restore_router,
    states_raise_router,
    states_comms_router,
    states_delivs_router,
    states_autoresponse_router,
    states_review_monitor_router,
    states_quick_replies_router
)