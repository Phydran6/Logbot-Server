# ==============================================================================
# Name:        Phydran6
# Kontakt:     Phydran6
# Version:     2026.07.31.23.30.00
# Beschreibung: LogBot - SQLAlchemy Models
# ==============================================================================

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100))
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="user")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # MFA / TOTP
    mfa_enabled = Column(Boolean, default=False, nullable=False)
    mfa_secret = Column(String(64), nullable=True)                # Base32, erst nach erfolgreichem Verify gesetzt
    mfa_failed_count = Column(Integer, default=0, nullable=False)
    mfa_locked_until = Column(DateTime, nullable=True)
    app_login_tokens = relationship("AppLoginToken", back_populates="user", passive_deletes=True)
    mfa_backup_codes = relationship("MFABackupCode", back_populates="user", passive_deletes=True)


class MFABackupCode(Base):
    """Einmal-Backup-Code für TOTP-Recovery. code_hash = bcrypt."""
    __tablename__ = "mfa_backup_codes"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    code_hash = Column(String(255), nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="mfa_backup_codes")

class Agent(Base):
    __tablename__ = "agents"
    id = Column(Integer, primary_key=True)
    hostname = Column(String(255), nullable=False)
    ip_address = Column(String(45))
    mac_address = Column(String(17))
    device_type = Column(String(50), default="unknown")
    last_seen = Column(DateTime, default=datetime.utcnow)
    first_seen = Column(DateTime, default=datetime.utcnow)
    extra_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Retention-Policy pro Gerät (NULL = kein Limit)
    retention_max_logs = Column(Integer, nullable=True)
    retention_days = Column(Integer, nullable=True)
    logs = relationship("Log", back_populates="agent", passive_deletes=True)

class Log(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True)
    agent_id = Column(Integer, ForeignKey("agents.id", ondelete="SET NULL"))
    hostname = Column(String(255))
    ip_address = Column(String(45))
    timestamp = Column(DateTime, default=datetime.utcnow)
    facility = Column(Integer)
    level = Column(String(20))
    source = Column(String(100))
    message = Column(Text)
    raw_message = Column(Text)
    extra_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Duplikat-Erkennung beim HTTPS-Ingest (SHA256 aus Host/Zeit/Ereignis/Text).
    # NULL = keine Pruefung (z.B. Syslog), Unique-Index greift nur auf NOT NULL.
    dedup_key = Column(String(64), nullable=True)
    agent = relationship("Agent", back_populates="logs")

class Webhook(Base):
    __tablename__ = "webhooks"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    token = Column(String(64), unique=True, nullable=False)
    description = Column(Text)
    filters = Column(JSON, default=dict)
    max_results = Column(Integer, default=100)
    include_raw = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    call_count = Column(Integer, default=0)
    last_called_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AgentToken(Base):
    __tablename__ = "agent_tokens"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    token = Column(String(64), unique=True, nullable=False)
    device_type = Column(String(50))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Setting(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(JSON, nullable=False)
    description = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AppLoginToken(Base):
    """Kurzlebiger Einmal-Token für die App-Authentifizierung via QR-Code."""
    __tablename__ = "app_login_tokens"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token = Column(String(64), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="app_login_tokens")
