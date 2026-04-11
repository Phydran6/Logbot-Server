# ==============================================================================
# Name:        Philipp Fischer
# Kontakt:     p.fischer@itconex.de
# Version:     2026.04.11.13.38.42
# Beschreibung: LogBot - Backend Konfiguration
# ==============================================================================

import logging
import sys
from typing import List
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "logbot"
    db_password: str = ""
    db_name: str = "logbot"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    app_version: str = "2026.04.11.13.38.42"
    caddy_admin_url: str = "http://caddy:2019"
    caddy_certs_dir: str = "/caddy-certs"
    # CORS: Komma-getrennte Liste erlaubter Origins, z.B. "https://logbot.example.com"
    # Leer lassen = nur same-origin (empfohlen für Caddy-Deployments)
    cors_origins: str = ""
    # Öffentliche URL des Servers (für QR-Code-Generierung), z.B. "https://logbot.example.com"
    site_url: str = ""

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def cors_origins_list(self) -> List[str]:
        if not self.cors_origins:
            return []
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    class Config:
        extra = "ignore"


settings = Settings()


def validate_security_settings() -> None:
    """Warnt beim Start bei unsicheren Standardwerten."""
    logger = logging.getLogger("logbot.security")
    if settings.jwt_secret == "change-me":
        logger.critical(
            "SICHERHEITSWARNUNG: JWT_SECRET ist noch der Standardwert 'change-me'! "
            "Setze die Umgebungsvariable JWT_SECRET auf einen langen zufälligen Wert."
        )
        # In Produktionsumgebungen Startup verweigern
        import os
        if os.getenv("LOGBOT_ENV", "").lower() == "production":
            logger.critical("LOGBOT_ENV=production – Startup abgebrochen wegen unsicherem JWT_SECRET.")
            sys.exit(1)
