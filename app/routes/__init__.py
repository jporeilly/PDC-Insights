from .health import router as health_router
from .analytics import router as analytics_router
from .generate import router as generate_router
from .dashboards import router as dashboards_router
from .chat import router as chat_router
from .llm import router as llm_router
from .settings import router as settings_router

routers = (health_router, analytics_router, generate_router, dashboards_router,
           chat_router, llm_router, settings_router)
