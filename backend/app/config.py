# ==============================================================================
# Name:        Philipp Fischer
# Kontakt:     p.fischer@itconex.de
# Version:     2026.04.02.16.32.39
# Beschreibung: LogBot v2026.03.31.17.26.46 - Backend Konfiguration
# ==============================================================================

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
    app_version: str = "2026.04.02.16.32.39"
    caddy_admin_url: str = "http://caddy:2019"
    caddy_certs_dir: str = "/caddy-certs"
    
    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
    
    class Config:
        extra = "ignore"

settings = Settings()
