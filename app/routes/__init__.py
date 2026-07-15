from .health import bp as health_bp
from .analytics import bp as analytics_bp
from .generate import bp as generate_bp
from .dashboards import bp as dashboards_bp
from .chat import bp as chat_bp
from .llm import bp as llm_bp
from .settings import bp as settings_bp

blueprints = (health_bp, analytics_bp, generate_bp, dashboards_bp, chat_bp, llm_bp, settings_bp)
