# ==============================================================================
# Name:        Philipp Fischer
# Kontakt:     p.fischer@itconex.de
# Version:     2026.04.11.00.00.00
# Beschreibung: LogBot - Rate Limiter (slowapi)
# ==============================================================================

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
