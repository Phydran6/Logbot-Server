# ==============================================================================
# Name:        Phydran6
# Kontakt:     Phydran6
# Version:     2026.05.30.17.22.26
# Beschreibung: LogBot - Pydantic Schemas
# ==============================================================================

import re
from datetime import datetime
from typing import Optional, List, Any, Dict, Union, Literal
from pydantic import BaseModel, Field, field_validator

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# -----------------------------------------------------------------------------
# MFA / TOTP
# -----------------------------------------------------------------------------
class LoginMFARequired(BaseModel):
    """Antwort auf /api/auth/login wenn der User MFA aktiviert hat."""
    mfa_required: Literal[True] = True
    mfa_token: str
    expires_in_seconds: int


class MFALoginRequest(BaseModel):
    mfa_token: str = Field(..., min_length=10)
    code: str = Field(..., min_length=6, max_length=16)  # 6-stellig TOTP oder 10-stelliger Backup-Code


class MFASetupResponse(BaseModel):
    secret: str               # Base32 zum manuellen Eintippen
    otpauth_uri: str          # otpauth://totp/...
    qr_image: str             # data:image/png;base64,...


class MFAVerifyRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=8)  # frisch eingerichteter TOTP


class MFAVerifyResponse(BaseModel):
    enabled: bool = True
    backup_codes: List[str]   # Klartext, EINMALIG nach Setup zurückgegeben


class MFADisableRequest(BaseModel):
    password: str = Field(..., min_length=1)
    code: str = Field(..., min_length=6, max_length=16)


class MFARegenerateRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=16)


class MFARegenerateResponse(BaseModel):
    backup_codes: List[str]


class MFAStatusResponse(BaseModel):
    enabled: bool
    backup_codes_remaining: int = 0
    locked_until: Optional[datetime] = None

class TokenData(BaseModel):
    username: Optional[str] = None

class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[str] = None
    role: str = Field(default="user")

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Passwort muss mindestens einen Großbuchstaben enthalten")
        if not re.search(r"[0-9]", v):
            raise ValueError("Passwort muss mindestens eine Ziffer enthalten")
        return v

class UserUpdate(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not re.search(r"[A-Z]", v):
            raise ValueError("Passwort muss mindestens einen Großbuchstaben enthalten")
        if not re.search(r"[0-9]", v):
            raise ValueError("Passwort muss mindestens eine Ziffer enthalten")
        return v

class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    class Config:
        from_attributes = True

class AgentResponse(BaseModel):
    id: int
    hostname: str
    ip_address: Optional[str]
    mac_address: Optional[str]
    device_type: str
    last_seen: datetime
    first_seen: datetime
    extra_data: Dict[str, Any] = {}
    metadata: Dict[str, Any] = {}
    is_online: Optional[bool] = None
    log_count: Optional[int] = None
    retention_max_logs: Optional[int] = None
    retention_days: Optional[int] = None
    class Config:
        from_attributes = True

class AgentRetentionUpdate(BaseModel):
    retention_max_logs: Optional[int] = Field(default=None, ge=1000, le=10_000_000)
    retention_days: Optional[int] = Field(default=None, ge=1, le=3650)

class AgentListResponse(BaseModel):
    items: List[AgentResponse]
    total: int
    page: int
    page_size: int

class LogResponse(BaseModel):
    id: int
    hostname: Optional[str]
    ip_address: Optional[str]
    timestamp: datetime
    level: Optional[str]
    source: Optional[str]
    message: Optional[str]
    class Config:
        from_attributes = True

class LogDetailResponse(LogResponse):
    agent_id: Optional[int]
    facility: Optional[int]
    raw_message: Optional[str]
    extra_data: Dict[str, Any] = {}

class LogListResponse(BaseModel):
    items: List[LogResponse]
    total: int
    page: int
    page_size: int

class LogStatsResponse(BaseModel):
    total_logs: int
    logs_today: int
    logs_by_level: Dict[str, int]
    logs_by_source: Dict[str, int]
    unique_hosts: int

class WebhookFilters(BaseModel):
    hostname: Optional[str] = None
    source: Optional[str] = None
    level: Optional[List[str]] = None

class WebhookBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    filters: WebhookFilters = WebhookFilters()
    max_results: int = Field(default=100, ge=1, le=1000)
    include_raw: bool = False
    is_active: bool = True

class WebhookCreate(WebhookBase):
    pass

class WebhookUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    filters: Optional[WebhookFilters] = None
    max_results: Optional[int] = None
    include_raw: Optional[bool] = None
    is_active: Optional[bool] = None

class WebhookResponse(WebhookBase):
    id: int
    token: str
    call_count: int
    last_called_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True

class AgentTokenCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    device_type: Optional[str] = Field(default=None, pattern="^(linux|windows)$")

class AgentTokenResponse(BaseModel):
    id: int
    name: str
    token: str
    device_type: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True

class LogIngestEntry(BaseModel):
    level: str = Field(default="info")
    source: str = Field(default="unknown")
    message: str

class LogIngestRequest(BaseModel):
    hostname: str
    events: List[LogIngestEntry] = Field(..., max_length=50)

class LogIngestResponse(BaseModel):
    accepted: int
    message: str = "ok"

class AgentDecommissionRequest(BaseModel):
    hostname: Optional[str] = None
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    purge: bool = False

class SettingsResponse(BaseModel):
    settings: Dict[str, Any]

class SettingUpdate(BaseModel):
    value: Any

class RetentionResponse(BaseModel):
    logs_to_delete: Optional[int] = None
    deleted_count: Optional[int] = None
    oldest_log_date: Optional[datetime] = None
    message: Optional[str] = None

class DatabaseSettingsResponse(BaseModel):
    host: str
    port: int
    user: str
    name: str
    password: str

class HealthResponse(BaseModel):
    status: str
    version: str

class HealthDetailedResponse(HealthResponse):
    uptime_seconds: float
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    database_connected: bool
    logs_total: int
    logs_last_24h: int
    agents_total: int
    agents_online: int

# Caddy management
class CaddyConfigResponse(BaseModel):
    running_config: Dict[str, Any] = {}
    saved_caddyfile: str = ""
    cert_present: bool = False
    last_error: Optional[str] = None

class CaddyApplyRequest(BaseModel):
    caddyfile: str
    save: bool = True
    mode: Optional[str] = Field(default=None, pattern="^(http|letsencrypt|custom)$")
    domain: Optional[str] = None
    letsencrypt_email: Optional[str] = None

class CaddyTemplateRequest(BaseModel):
    domain: Optional[str] = None
    mode: str = Field(..., pattern="^(http|letsencrypt|custom)$")
    letsencrypt_email: Optional[str] = None

# App-Login (QR-Code / Token-Exchange für Android-App)
class AppTokenResponse(BaseModel):
    token: str
    expires_at: datetime
    expires_in_seconds: int

class AppTokenExchangeRequest(BaseModel):
    token: str = Field(..., min_length=64, max_length=64)

class AppQRResponse(BaseModel):
    qr_image: str          # data:image/png;base64,...
    token: str
    expires_at: datetime
    expires_in_seconds: int
    api_url: str
