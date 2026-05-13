# ==============================================================================
# Name:        Phydran6
# Kontakt:     Phydran6
# Version:     2026.05.13.20.58.33
# Beschreibung: LogBot - Rate Limiter (slowapi)
# ==============================================================================

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
