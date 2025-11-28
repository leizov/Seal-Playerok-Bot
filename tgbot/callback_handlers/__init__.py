from aiogram import Router
from .navigation import router as navigation_router
from .actions_switch import router as actions_switch_router
from .user_management import router as user_management_router
from .pagination import router as pagination_router
from .actions_enter import router as actions_enter_router
from .actions_other import router as actions_other_router
from .page import router as page_router
from .quick_replies import router as quick_replies_router
from .chat_history import router as chat_history_router
from .review_monitor import router as review_monitor_router
from .proxy_management import router as proxy_management_router

router = Router()
router.include_routers(
    page_router,
    navigation_router,
    actions_switch_router,
    user_management_router,
    pagination_router,
    actions_enter_router,
    actions_other_router,
    quick_replies_router,
    chat_history_router,
    review_monitor_router,
    proxy_management_router
)