# ==============================================================================
# Name:        Philipp Fischer
# Kontakt:     p.fischer@itconex.de
# Version:     2026.03.31.17.26.46
# Beschreibung: LogBot v2026.03.31.17.26.46 - Routes Package
# ==============================================================================

from .auth import router as auth_router
from .health import router as health_router
from .users import router as users_router
from .agents import router as agents_router, token_router as agent_tokens_router
from .logs import router as logs_router
from .webhooks import router as webhooks_router
from .settings import router as settings_router
from . import caddy

__all__ = ["auth_router", "health_router", "users_router", "agents_router",
           "agent_tokens_router", "logs_router", "webhooks_router", "settings_router", "caddy"]
