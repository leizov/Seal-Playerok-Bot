from aiogram import Router
from .commands import router as commands_router
from .log_commands import router as log_commands_router
from .states_system import router as states_system_router
from .states_settings import router as states_settings_router
from .states_actions import router as states_actions_router
from .states_restore import router as states_restore_router
from .states_raise import router as states_raise_router
from .states_auto_complete import router as states_auto_complete_router
from .states_comms import router as states_comms_router
from .states_delivs import router as states_delivs_router
from .states_autoresponse import router as states_autoresponse_router
from .states_auto_reminder import router as states_auto_reminder_router
from .states_quick_replies import router as states_quick_replies_router
from .states_config_backup import router as states_config_backup_router
from .states_items import router as states_items_router
from .states_plugins import router as states_plugins_router

router = Router()
router.include_routers(
    commands_router,
    log_commands_router,
    states_system_router,
    states_settings_router,
    states_actions_router,
    states_restore_router,
    states_raise_router,
    states_auto_complete_router,
    states_comms_router,
    states_delivs_router,
    states_autoresponse_router,
    states_auto_reminder_router,
    states_quick_replies_router,
    states_config_backup_router,
    states_items_router,
    states_plugins_router,
)
