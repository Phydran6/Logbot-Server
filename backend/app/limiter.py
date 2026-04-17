# ==============================================================================
# Name:        Phydran6
# Kontakt:     Phydran6
# Version:     2026.04.17.15.17.18
# Beschreibung: LogBot - Rate Limiter (slowapi)
# ==============================================================================

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
