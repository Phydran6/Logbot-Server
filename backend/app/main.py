# ==============================================================================
# Name:        Philipp Fischer
# Kontakt:     p.fischer@itconex.de
# Version:     2026.03.31.17.26.46
# Beschreibung: LogBot v2026.03.31.17.26.46 - FastAPI Hauptanwendung
# ==============================================================================

from datetime import datetime, timedelta
import secrets
import logging
import asyncio
import shutil
import os
from fastapi import FastAPI, HTTPException, Query, Header, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, desc, delete, text
from sqlalchemy.ext.asyncio import AsyncSession
from .config import settings
from .database import get_db, async_session, engine
from .models import Webhook, Log, Agent, AgentToken
from .schemas import LogResponse, LogDetailResponse, LogIngestRequest, LogIngestResponse
from .routes import auth_router, health_router, users_router, agents_router, agent_tokens_router, logs_router, webhooks_router, settings_router, caddy as caddy_router
from .branding import branding_router

app = FastAPI(
    title="LogBot",
    description="Zentraler Log-Server",
    version=settings.app_version,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json"
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Routes registrieren
app.include_router(auth_router)
app.include_router(health_router)
app.include_router(users_router)
app.include_router(agents_router)
app.include_router(agent_tokens_router)
app.include_router(logs_router)
app.include_router(webhooks_router)
app.include_router(branding_router)
app.include_router(settings_router)
app.include_router(caddy_router.router)

# Sicherstellen, dass mindestens ein Agent-Token existiert (fuer HTTPS-Agent-Installationen)
@app.on_event("startup")
async def ensure_default_agent_token():
    logger = logging.getLogger("logbot.startup")
    try:
        async with async_session() as session:
            # Schema-Sicherung: device_type Column hinzufügen falls fehlt (PostgreSQL >=9.6)
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
        # Nicht den gesamten Service kippen, falls DB noch nicht bereit ist
        logger.warning("Default agent token init skipped: %s", exc)


@app.on_event("startup")
async def apply_saved_caddy_config():
    """Laedt eine gespeicherte Caddyfile (falls vorhanden) nach dem Start."""
    try:
        await caddy_router.ensure_caddy_config_on_startup()
    except Exception as exc:
        logging.getLogger("logbot.startup").warning("Caddy-Config beim Start nicht geladen: %s", exc)

# Öffentlicher Webhook Endpoint - KEINE Auth!
@app.get("/api/webhook/{webhook_id}/call", tags=["Webhooks"])
async def call_webhook(webhook_id: int, token: str = Query(...), db: AsyncSession = Depends(get_db)):
    """Öffentlicher Webhook-Endpoint für n8n/externe Tools. Auth via Token-Parameter."""
    result = await db.execute(select(Webhook).where(Webhook.id == webhook_id, Webhook.token == token, Webhook.is_active == True))
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
                raw_message=l.raw_message, metadata=l.metadata or {}) for l in logs]
    return [LogResponse(id=l.id, hostname=l.hostname, ip_address=l.ip_address, timestamp=l.timestamp,
            level=l.level, source=l.source, message=l.message) for l in logs]

# Öffentlicher Ingest-Endpoint - Auth via Agent-Token (Bearer)
@app.post("/api/agents/ingest", response_model=LogIngestResponse, tags=["Agent Ingest"])
async def ingest_logs(
    data: LogIngestRequest,
    request: Request,
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db)
):
    """Empfängt Logs von authentifizierten Agents via HTTPS."""
    # Token aus Bearer Header extrahieren
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer Token erforderlich")
    token_value = authorization[7:]

    # Token validieren
    result = await db.execute(
        select(AgentToken).where(AgentToken.token == token_value, AgentToken.is_active == True))
    agent_token = result.scalar_one_or_none()
    if not agent_token:
        raise HTTPException(status_code=401, detail="Ungültiger Agent-Token")

    # Agent finden oder erstellen
    client_ip = request.client.host if request.client else "unknown"
    result = await db.execute(
        select(Agent).where(Agent.hostname == data.hostname, Agent.ip_address == client_ip))
    agent = result.scalar_one_or_none()
    if agent:
        agent.last_seen = datetime.utcnow()
    else:
        agent = Agent(
            hostname=data.hostname, ip_address=client_ip,
            device_type="windows_agent",
            extra_data={"auth": "token", "token_name": agent_token.name})
        db.add(agent)
        await db.flush()

    # Logs einfügen
    for event in data.events:
        log = Log(
            agent_id=agent.id, hostname=data.hostname, ip_address=client_ip,
            facility=1, level=event.level, source=event.source,
            message=event.message, raw_message=event.message,
            extra_data={"ingested_via": "https"})
        db.add(log)

    await db.commit()
    return LogIngestResponse(accepted=len(data.events))

@app.get("/api")
async def root():
    return {"name": "LogBot", "version": settings.app_version, "docs": "/api/docs"}

# =============================================================================
# Automatisches Disk-Cleanup bei hoher Auslastung
# =============================================================================
DISK_CHECK_INTERVAL = int(os.getenv("DISK_MONITOR_INTERVAL", "300"))  # Sekunden
DISK_THRESHOLD = float(os.getenv("DISK_USAGE_THRESHOLD", "95"))       # %
DISK_MONITOR_PATH = os.getenv("DISK_MONITOR_PATH", "/")
DISK_RETENTION_DAYS = int(os.getenv("DISK_CLEANUP_RETENTION_DAYS", "30"))


def _current_disk_usage_pct() -> float:
    usage = shutil.disk_usage(DISK_MONITOR_PATH)
    return usage.used / usage.total * 100.0


async def _delete_logs_older_than(days: int, logger: logging.Logger) -> int:
    cutoff = datetime.utcnow() - timedelta(days=days)
    try:
        async with async_session() as session:
            result = await session.execute(delete(Log).where(Log.timestamp < cutoff))
            await session.commit()
            deleted = result.rowcount if result.rowcount not in (None, -1) else 0
            logger.warning("Auto-cleanup: %s logs (> %s Tage) geloescht", deleted, days)
            return deleted
    except Exception as exc:
        logger.error("Auto-cleanup Fehler beim Loeschen alter Logs: %s", exc)
        return 0


async def _truncate_logs(logger: logging.Logger) -> None:
    try:
        async with async_session() as session:
            await session.execute(text("TRUNCATE TABLE logs RESTART IDENTITY"))
            await session.commit()
        logger.warning("Auto-cleanup: logs Tabelle TRUNCATE ausgefuehrt")
    except Exception as exc:
        logger.error("Auto-cleanup Fehler bei TRUNCATE logs: %s", exc)


async def _vacuum_logs(logger: logging.Logger) -> None:
    try:
        async with engine.connect() as conn:
            conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
            await conn.exec_driver_sql("VACUUM (FULL, ANALYZE) logs")
        logger.warning("Auto-cleanup: VACUUM FULL logs abgeschlossen")
    except Exception as exc:
        logger.error("Auto-cleanup Fehler bei VACUUM FULL: %s", exc)


async def disk_monitor():
    logger = logging.getLogger("logbot.disk_monitor")
    while True:
        await asyncio.sleep(DISK_CHECK_INTERVAL)
        try:
            pct = _current_disk_usage_pct()
        except Exception as exc:
            logger.error("Disk-Check fehlgeschlagen: %s", exc)
            continue

        if pct < DISK_THRESHOLD:
            continue

        logger.warning("Disk %.2f%% >= Schwelle %.1f%% – starte Auto-Cleanup", pct, DISK_THRESHOLD)

        await _delete_logs_older_than(DISK_RETENTION_DAYS, logger)

        try:
            pct = _current_disk_usage_pct()
        except Exception:
            pct = DISK_THRESHOLD

        if pct < DISK_THRESHOLD - 2:  # etwas Puffer
            logger.warning("Disk nach Log-Loeschung bei %.2f%%", pct)
            continue

        await _truncate_logs(logger)
        await _vacuum_logs(logger)

        try:
            pct = _current_disk_usage_pct()
            logger.warning("Disk nach TRUNCATE/VACUUM bei %.2f%%", pct)
        except Exception:
            pass


@app.on_event("startup")
async def start_disk_monitor():
    asyncio.create_task(disk_monitor())
