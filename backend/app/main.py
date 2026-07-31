# ==============================================================================
# Name:        Phydran6
# Kontakt:     Phydran6
# Version:     2026.07.18.16.00.00
# Changelog:   ../../CHANGELOG/backend.md
# Beschreibung: LogBot - FastAPI Hauptanwendung
# ==============================================================================

from datetime import datetime, timedelta, timezone
from typing import Optional
import hashlib
import secrets
import logging
import asyncio
import shutil
import os
from fastapi import FastAPI, HTTPException, Query, Header, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select, desc, delete, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from . import fritzbox
from .config import settings, validate_security_settings
from .database import get_db, async_session, engine
from .limiter import limiter
from .models import Webhook, Log, Agent, AgentToken
from sqlalchemy import func
from .schemas import LogResponse, LogDetailResponse, LogIngestRequest, LogIngestResponse
from .routes import auth_router, mfa_router, health_router, users_router, agents_router, agent_tokens_router, logs_router, webhooks_router, settings_router, caddy as caddy_router, network as network_router
from .branding import branding_router

# =============================================================================
# Security-Headers Middleware
# =============================================================================
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response


# =============================================================================
# App-Instanz
# =============================================================================
app = FastAPI(
    title="LogBot",
    description="Zentraler Log-Server",
    version=settings.app_version,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    # Swagger/ReDoc nur mit Auth erreichbar machen würde redoc_url/docs_url=None erfordern
    # Für interne Tools lassen wir es offen, aber per Caddy-Auth absicherbar
)

# Rate-Limiter am App registrieren
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# GZip für alle Responses > 1 KB
app.add_middleware(GZipMiddleware, minimum_size=1024)

# CORS: erlaubte Origins aus Konfiguration, niemals Credentials + Wildcard
_cors_origins = settings.cors_origins_list or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,      # Bearer-Token in Header, kein Cookie-basiertes Auth
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# Security-Headers zuletzt (werden nach CORS-Middleware eingefügt)
app.add_middleware(SecurityHeadersMiddleware)

# =============================================================================
# Routes registrieren
# =============================================================================
app.include_router(auth_router)
app.include_router(mfa_router)
app.include_router(health_router)
app.include_router(users_router)
app.include_router(agents_router)
app.include_router(agent_tokens_router)
app.include_router(logs_router)
app.include_router(webhooks_router)
app.include_router(branding_router)
app.include_router(settings_router)
app.include_router(caddy_router.router)
app.include_router(network_router.router)


# =============================================================================
# Startup Events
# =============================================================================
@app.on_event("startup")
async def startup_security_check():
    validate_security_settings()


@app.on_event("startup")
async def ensure_default_agent_token():
    logger = logging.getLogger("logbot.startup")
    try:
        async with async_session() as session:
            # Schema-Sicherung: device_type Column hinzufügen falls fehlt
            try:
                await session.execute(text("ALTER TABLE agent_tokens ADD COLUMN IF NOT EXISTS device_type VARCHAR(50)"))
                await session.commit()
            except Exception:
                await session.rollback()
            existing_global = await session.execute(
                select(AgentToken.id).where(AgentToken.name == "global-agent")
            )
            if existing_global.scalar_one_or_none():
                return
            default_token = AgentToken(
                name="global-agent",
                token=secrets.token_hex(32),
                device_type=None,
                is_active=True,
            )
            session.add(default_token)
            await session.commit()
            logger.info("Default agent token created")
    except Exception as exc:
        logger.warning("Default agent token init skipped: %s", exc)


@app.on_event("startup")
async def ensure_agent_retention_columns():
    """Fügt retention_max_logs / retention_days zu agents hinzu falls noch nicht vorhanden."""
    logger = logging.getLogger("logbot.startup")
    try:
        async with engine.connect() as conn:
            conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
            await conn.exec_driver_sql(
                "ALTER TABLE agents ADD COLUMN IF NOT EXISTS retention_max_logs INTEGER"
            )
            await conn.exec_driver_sql(
                "ALTER TABLE agents ADD COLUMN IF NOT EXISTS retention_days INTEGER"
            )
        logger.info("agents retention columns ready")
    except Exception as exc:
        logger.warning("agents retention migration skipped: %s", exc)


@app.on_event("startup")
async def ensure_mfa_schema():
    """Fügt MFA-Spalten zu users hinzu und legt mfa_backup_codes-Tabelle an (Migration)."""
    logger = logging.getLogger("logbot.startup")
    try:
        async with engine.connect() as conn:
            conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
            await conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS mfa_enabled BOOLEAN NOT NULL DEFAULT FALSE"
            )
            await conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS mfa_secret VARCHAR(64)"
            )
            await conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS mfa_failed_count INTEGER NOT NULL DEFAULT 0"
            )
            await conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS mfa_locked_until TIMESTAMP"
            )
            await conn.exec_driver_sql("""
                CREATE TABLE IF NOT EXISTS mfa_backup_codes (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    code_hash VARCHAR(255) NOT NULL,
                    used_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS idx_mfa_backup_codes_user_id ON mfa_backup_codes(user_id)"
            )
        logger.info("MFA schema ready")
    except Exception as exc:
        logger.warning("MFA schema migration skipped: %s", exc)


@app.on_event("startup")
async def ensure_app_login_tokens_table():
    """Erstellt die app_login_tokens-Tabelle falls sie noch nicht existiert (Migration)."""
    logger = logging.getLogger("logbot.startup")
    try:
        async with engine.connect() as conn:
            conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
            await conn.exec_driver_sql("""
                CREATE TABLE IF NOT EXISTS app_login_tokens (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    token VARCHAR(64) UNIQUE NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    used_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS idx_app_login_tokens_token ON app_login_tokens(token)"
            )
            await conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS idx_app_login_tokens_user_id ON app_login_tokens(user_id)"
            )
        logger.info("app_login_tokens table ready")
    except Exception as exc:
        logger.warning("app_login_tokens migration skipped: %s", exc)


@app.on_event("startup")
async def ensure_log_indexes():
    """Index fuer den Facility-Filter der Log-Ansicht (Migration fuer Bestands-DBs).

    CONCURRENTLY, damit der Aufbau auf einer grossen logs-Tabelle keine Schreib-
    zugriffe blockiert. Faellt der Aufbau aus, bleibt nur der Filter langsamer.
    """
    logger = logging.getLogger("logbot.startup")
    try:
        async with engine.connect() as conn:
            conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
            await conn.exec_driver_sql(
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_logs_facility ON logs(facility)"
            )
        logger.info("logs indexes ready")
    except Exception as exc:
        logger.warning("logs index migration skipped: %s", exc)


@app.on_event("startup")
async def ensure_log_dedup_key():
    """Spalte + Unique-Index fuer die Duplikat-Erkennung beim HTTPS-Ingest.

    Der Index ist partiell (nur WHERE dedup_key IS NOT NULL), damit die bestehenden
    Millionen Syslog-Zeilen ohne Schluessel unberuehrt bleiben. CONCURRENTLY, damit
    der Aufbau keine Schreibzugriffe blockiert.
    """
    logger = logging.getLogger("logbot.startup")
    try:
        async with engine.connect() as conn:
            conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
            await conn.exec_driver_sql(
                "ALTER TABLE logs ADD COLUMN IF NOT EXISTS dedup_key VARCHAR(64)"
            )
            await conn.exec_driver_sql(
                "CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_logs_dedup_key "
                "ON logs(dedup_key) WHERE dedup_key IS NOT NULL"
            )
        logger.info("logs dedup_key ready")
    except Exception as exc:
        logger.warning("logs dedup_key migration skipped: %s", exc)


@app.on_event("startup")
async def apply_saved_caddy_config():
    """Laedt eine gespeicherte Caddyfile (falls vorhanden) nach dem Start."""
    try:
        await caddy_router.ensure_caddy_config_on_startup()
    except Exception as exc:
        logging.getLogger("logbot.startup").warning("Caddy-Config beim Start nicht geladen: %s", exc)


@app.on_event("startup")
async def apply_saved_dns_config():
    """Wendet eine gespeicherte DNS-Konfiguration (falls vorhanden) nach dem Start erneut an."""
    try:
        await network_router.ensure_dns_config_on_startup()
    except Exception as exc:
        logging.getLogger("logbot.startup").warning("DNS-Config beim Start nicht geladen: %s", exc)


# =============================================================================
# Öffentlicher Webhook Endpoint
# =============================================================================
@app.get("/api/webhook/{webhook_id}/call", tags=["Webhooks"])
async def call_webhook(webhook_id: int, token: str = Query(...), db: AsyncSession = Depends(get_db)):
    """Öffentlicher Webhook-Endpoint für n8n/externe Tools. Auth via Token-Parameter."""
    result = await db.execute(
        select(Webhook).where(Webhook.id == webhook_id, Webhook.token == token, Webhook.is_active == True)
    )
    webhook = result.scalar_one_or_none()
    if not webhook:
        raise HTTPException(status_code=401, detail="Ungültiger Webhook oder Token")

    filters = webhook.filters or {}
    query = select(Log)

    if filters.get("hostname"):
        query = query.where(Log.hostname.ilike(f"%{filters['hostname']}%"))
    if filters.get("source"):
        query = query.where(Log.source.ilike(f"%{filters['source']}%"))
    if filters.get("level"):
        query = query.where(Log.level.in_(filters["level"]))

    query = query.order_by(desc(Log.timestamp)).limit(webhook.max_results)
    result = await db.execute(query)
    logs = result.scalars().all()

    webhook.call_count += 1
    webhook.last_called_at = datetime.utcnow()
    await db.commit()

    if webhook.include_raw:
        return [LogDetailResponse(id=l.id, hostname=l.hostname, ip_address=l.ip_address, timestamp=l.timestamp,
                level=l.level, source=l.source, message=l.message, agent_id=l.agent_id, facility=l.facility,
                raw_message=l.raw_message, extra_data=l.extra_data or {}) for l in logs]
    return [LogResponse(id=l.id, hostname=l.hostname, ip_address=l.ip_address, timestamp=l.timestamp,
            level=l.level, source=l.source, message=l.message) for l in logs]


# =============================================================================
# Agent Ingest Endpoint
# =============================================================================
def _to_naive_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Zeitstempel mit Zeitzone auf UTC ohne tzinfo bringen (die DB speichert naiv/UTC)."""
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _dedup_key(hostname: str, timestamp: datetime, event_id: Optional[int], message: str) -> str:
    """Fingerabdruck eines Ereignisses. Gleiche Box + Zeit + Ereignis + Text = gleicher Eintrag."""
    raw = f"{hostname}|{timestamp.isoformat()}|{'' if event_id is None else event_id}|{message}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@app.post("/api/agents/ingest", response_model=LogIngestResponse, tags=["Agent Ingest"])
async def ingest_logs(
    data: LogIngestRequest,
    request: Request,
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db)
):
    """Empfängt Logs von authentifizierten Agents via HTTPS.

    Sammler (z.B. n8n, das die FRITZ!Box abfragt) duerfen hostname, ip_address und
    device_type des gemeldeten Geraets mitschicken - dann taucht die Box mit eigener
    IP und eigenem Hostnamen auf und nicht mit der IP des Sammlers.

    Eintraege mit eigenem Zeitstempel bekommen einen dedup_key: wiederholte Lieferungen
    derselben Ereignisse (die FRITZ!Box liefert immer ihren kompletten Puffer) werden
    von der Datenbank verworfen statt doppelt gespeichert.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer Token erforderlich")
    token_value = authorization[7:]

    result = await db.execute(
        select(AgentToken).where(AgentToken.token == token_value, AgentToken.is_active == True)
    )
    agent_token = result.scalar_one_or_none()
    if not agent_token:
        raise HTTPException(status_code=401, detail="Ungültiger Agent-Token")

    client_ip = request.client.host if request.client else "unknown"
    device_ip = (data.ip_address or "").strip() or client_ip

    result = await db.execute(
        select(Agent).where(Agent.hostname == data.hostname, Agent.ip_address == device_ip)
    )
    agent = result.scalar_one_or_none()
    if agent:
        agent.last_seen = datetime.utcnow()
        if data.device_type and agent.device_type in (None, "unknown"):
            agent.device_type = data.device_type
    else:
        # device_type aus dem Payload, sonst aus dem Token (linux/windows) ableiten
        _dt_map = {"linux": "linux_agent", "windows": "windows_agent"}
        agent = Agent(
            hostname=data.hostname, ip_address=device_ip,
            device_type=data.device_type or _dt_map.get(agent_token.device_type, "windows_agent"),
            extra_data={"auth": "token", "token_name": agent_token.name})
        db.add(agent)
        await db.flush()

    is_fritzbox = (data.device_type or "").lower() == "fritzbox"
    now = datetime.utcnow()
    unique_rows = {}   # dedup_key -> Zeile, entfernt Doppelte schon innerhalb einer Lieferung
    plain_rows = []    # ohne Zeitstempel: keine Duplikatpruefung moeglich

    for event in data.events:
        level = (event.level or "").strip().lower() or None
        source = (event.source or "").strip() or None
        if is_fritzbox and (level is None or source is None):
            mapped_level, mapped_source = fritzbox.classify(event.event_id, event.group, event.message)
            level = level or mapped_level
            source = source or mapped_source

        extra = {"ingested_via": "https"}
        if event.event_id is not None:
            extra["event_id"] = event.event_id
        if event.group:
            extra["group"] = event.group

        ts = _to_naive_utc(event.timestamp)
        row = {
            "agent_id": agent.id,
            "hostname": data.hostname,
            "ip_address": device_ip,
            "timestamp": ts or now,
            "facility": 1 if event.facility is None else event.facility,
            "level": level or "info",
            "source": source or "unknown",
            "message": event.message,
            "raw_message": event.message,
            "extra_data": extra,
            "created_at": now,
            "dedup_key": None,
        }
        if ts is None:
            plain_rows.append(row)
        else:
            key = _dedup_key(data.hostname, ts, event.event_id, event.message)
            row["dedup_key"] = key
            unique_rows[key] = row

    rows = plain_rows + list(unique_rows.values())
    inserted = 0
    if rows:
        stmt = (
            pg_insert(Log).values(rows)
            .on_conflict_do_nothing(
                index_elements=[Log.dedup_key],
                index_where=Log.dedup_key.isnot(None),
            )
            .returning(Log.id)
        )
        inserted = len((await db.execute(stmt)).scalars().all())

    await db.commit()
    return LogIngestResponse(accepted=inserted, duplicates=len(data.events) - inserted)


@app.get("/api")
async def root():
    return {"name": "LogBot", "version": settings.app_version, "docs": "/api/docs"}


# =============================================================================
# Disk-Monitoring & Auto-Cleanup (3 Stufen: 80 / 90 / 95 %)
# =============================================================================
DISK_CHECK_INTERVAL   = int(os.getenv("DISK_MONITOR_INTERVAL",        "300"))
DISK_THRESHOLD_WARN   = float(os.getenv("DISK_USAGE_WARN",            "80"))   # Stufe 1: unnötiges bereinigen
DISK_THRESHOLD_HIGH   = float(os.getenv("DISK_USAGE_HIGH",            "90"))   # Stufe 2: älteste Logs löschen
DISK_THRESHOLD_CRIT   = float(os.getenv("DISK_USAGE_THRESHOLD",       "95"))   # Stufe 3: alles löschen
DISK_MONITOR_PATH     = os.getenv("DISK_MONITOR_PATH",                "/")
DISK_RETENTION_DAYS   = int(os.getenv("DISK_CLEANUP_RETENTION_DAYS",  "30"))


def _current_disk_usage_pct() -> float:
    usage = shutil.disk_usage(DISK_MONITOR_PATH)
    return usage.used / usage.total * 100.0


async def _vacuum(table: str, full: bool, logger: logging.Logger) -> None:
    cmd = f"VACUUM (FULL, ANALYZE) {table}" if full else f"VACUUM (ANALYZE) {table}"
    try:
        async with engine.connect() as conn:
            conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
            await conn.exec_driver_sql(cmd)
        logger.info("Auto-cleanup: %s abgeschlossen", cmd)
    except Exception as exc:
        logger.error("Auto-cleanup VACUUM Fehler: %s", exc)


# Stufe 1 – 80 %: Abgelaufene / verbrauchte App-Login-Tokens und sonstige Housekeeping-Daten löschen
async def _cleanup_expired_tokens(logger: logging.Logger) -> int:
    try:
        from .models import AppLoginToken
        async with async_session() as session:
            r = await session.execute(
                delete(AppLoginToken).where(
                    (AppLoginToken.expires_at < datetime.utcnow()) |
                    (AppLoginToken.used_at != None)  # noqa: E711
                )
            )
            await session.commit()
            n = r.rowcount or 0
            if n:
                logger.info("Auto-cleanup (80%%): %s abgelaufene App-Tokens gelöscht", n)
            return n
    except Exception as exc:
        logger.error("Auto-cleanup Token-Cleanup Fehler: %s", exc)
        return 0


# Stufe 2 – 90 %: Älteste Logs löschen (nach globaler Retention-Einstellung) und Platz freigeben
async def _cleanup_old_logs(logger: logging.Logger) -> int:
    try:
        async with async_session() as session:
            # Retention-Tage aus Settings lesen (Fallback: DISK_RETENTION_DAYS)
            from .models import Setting
            s = (await session.execute(
                select(Setting).where(Setting.key == "log_retention_days")
            )).scalar_one_or_none()
            days = DISK_RETENTION_DAYS
            if s:
                try:
                    days = int(s.value)
                except Exception:
                    pass
            cutoff = datetime.utcnow() - timedelta(days=days)
            r = await session.execute(delete(Log).where(Log.timestamp < cutoff))
            await session.commit()
            n = r.rowcount if r.rowcount not in (None, -1) else 0
            logger.warning("Auto-cleanup (90%%): %s Logs älter als %s Tage gelöscht", n, days)
            return n
    except Exception as exc:
        logger.error("Auto-cleanup Log-Cleanup Fehler: %s", exc)
        return 0


# Stufe 3 – 95 %: Alle Logs per TRUNCATE löschen (schnellste Methode, gibt Speicher sofort frei)
async def _truncate_logs(logger: logging.Logger) -> None:
    try:
        async with async_session() as session:
            await session.execute(text("TRUNCATE TABLE logs RESTART IDENTITY"))
            await session.commit()
        logger.warning("Auto-cleanup (95%%): logs TRUNCATE ausgefuehrt")
    except Exception as exc:
        logger.error("Auto-cleanup TRUNCATE Fehler: %s", exc)


async def disk_monitor():
    logger = logging.getLogger("logbot.disk_monitor")
    while True:
        await asyncio.sleep(DISK_CHECK_INTERVAL)
        try:
            pct = _current_disk_usage_pct()
        except Exception as exc:
            logger.error("Disk-Check fehlgeschlagen: %s", exc)
            continue

        if pct < DISK_THRESHOLD_WARN:
            continue

        logger.warning("Disk %.1f%% – prüfe Auto-Cleanup-Stufen", pct)

        # Stufe 1: ab 80 % – abgelaufene Tokens und Housekeeping-Daten löschen
        if pct >= DISK_THRESHOLD_WARN:
            await _cleanup_expired_tokens(logger)
            await _vacuum("app_login_tokens", full=False, logger=logger)
            try:
                pct = _current_disk_usage_pct()
            except Exception:
                pass

        # Stufe 2: ab 90 % – älteste Logs löschen + VACUUM FULL (gibt Speicher frei)
        if pct >= DISK_THRESHOLD_HIGH:
            await _cleanup_old_logs(logger)
            await _vacuum("logs", full=True, logger=logger)
            try:
                pct = _current_disk_usage_pct()
                logger.warning("Disk nach Stufe-2-Cleanup: %.1f%%", pct)
            except Exception:
                pass

        # Stufe 3: ab 95 % – alles per TRUNCATE löschen + VACUUM FULL
        if pct >= DISK_THRESHOLD_CRIT:
            await _truncate_logs(logger)
            await _vacuum("logs", full=True, logger=logger)
            try:
                pct = _current_disk_usage_pct()
                logger.warning("Disk nach Stufe-3-Cleanup: %.1f%%", pct)
            except Exception:
                pass


# =============================================================================
# Per-Agent Retention Background-Task (stündlich)
# =============================================================================
AGENT_RETENTION_INTERVAL = int(os.getenv("AGENT_RETENTION_INTERVAL", "3600"))


async def _enforce_agent_retention(session, agent, logger: logging.Logger) -> int:
    """Retention-Policy für einen Agent durchsetzen. Gibt Anzahl gelöschter Logs zurück."""
    deleted = 0

    if agent.retention_days:
        cutoff = datetime.utcnow() - timedelta(days=agent.retention_days)
        r = await session.execute(
            delete(Log).where(Log.agent_id == agent.id, Log.timestamp < cutoff)
        )
        n = r.rowcount or 0
        deleted += n
        if n:
            logger.info("Agent %s (%s): %s Logs älter als %s Tage gelöscht",
                        agent.id, agent.hostname, n, agent.retention_days)

    if agent.retention_max_logs:
        count = (await session.execute(
            select(func.count(Log.id)).where(Log.agent_id == agent.id)
        )).scalar() or 0
        excess = count - agent.retention_max_logs
        if excess > 0:
            subq = (
                select(Log.id)
                .where(Log.agent_id == agent.id)
                .order_by(Log.timestamp.asc())
                .limit(excess)
                .scalar_subquery()
            )
            r = await session.execute(delete(Log).where(Log.id.in_(subq)))
            n = r.rowcount or 0
            deleted += n
            if n:
                logger.info("Agent %s (%s): %s älteste Logs gelöscht (Limit: %s)",
                            agent.id, agent.hostname, n, agent.retention_max_logs)

    return deleted


async def agent_retention_task():
    """Stündliche Überprüfung und Durchsetzung der per-Agent-Retention-Policies."""
    logger = logging.getLogger("logbot.agent_retention")
    while True:
        await asyncio.sleep(AGENT_RETENTION_INTERVAL)
        try:
            async with async_session() as session:
                result = await session.execute(
                    select(Agent).where(
                        (Agent.retention_max_logs != None) |  # noqa: E711
                        (Agent.retention_days != None)         # noqa: E711
                    )
                )
                agents = result.scalars().all()
                if not agents:
                    continue
                total_deleted = 0
                for agent in agents:
                    total_deleted += await _enforce_agent_retention(session, agent, logger)
                if total_deleted:
                    await session.commit()
                    logger.info("Agent-Retention: insgesamt %s Logs gelöscht", total_deleted)
        except Exception as exc:
            logger.error("Agent-Retention-Task Fehler: %s", exc)


@app.on_event("startup")
async def start_background_tasks():
    asyncio.create_task(disk_monitor())
    asyncio.create_task(agent_retention_task())
