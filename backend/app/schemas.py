# ==============================================================================
# Name:        Philipp Fischer
# Kontakt:     p.fischer@itconex.de
# Version:     2026.03.03.17.18.19
# Beschreibung: LogBot v2026.03.03.17.18.19 - Pydantic Schemas
# ==============================================================================

from datetime import datetime
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    username: Optional[str] = None

class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[str] = None
    role: str = Field(default="user")

class UserCreate(UserBase):
    password: str = Field(..., min_length=6)

class UserUpdate(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None

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
    class Config:
        from_attributes = True

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

class AgentTokenResponse(BaseModel):
    id: int
    name: str
    token: str
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

class SettingsResponse(BaseModel):
    settings: Dict[str, Any]

class SettingUpdate(BaseModel):
    value: Any

class RetentionResponse(BaseModel):
    logs_to_delete: Optional[int] = None
    deleted_count: Optional[int] = None
    oldest_log_date: Optional[datetime] = None
    message: Optional[str] = None

# Database
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
