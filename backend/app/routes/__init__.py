# ==============================================================================
# Name:        Phydran6
# Kontakt:     Phydran6
# Version:     2026.07.11.13.03.42
# Changelog:   ../../CHANGELOG/backend.md
# Beschreibung: LogBot - Routes Package
# ==============================================================================

from .auth import router as auth_router
from .mfa import router as mfa_router
from .health import router as health_router
from .users import router as users_router
from .agents import router as agents_router, token_router as agent_tokens_router
from .logs import router as logs_router
from .webhooks import router as webhooks_router
from .settings import router as settings_router
from .database import router as database_router
from .ldap import router as ldap_router
from .archiving import router as archiving_router
from .passkey import router as passkey_router
from . import caddy
from . import network

__all__ = ["auth_router", "mfa_router", "health_router", "users_router", "agents_router",
           "agent_tokens_router", "logs_router", "webhooks_router", "settings_router",
           "database_router", "ldap_router", "archiving_router", "passkey_router",
           "caddy", "network"]
