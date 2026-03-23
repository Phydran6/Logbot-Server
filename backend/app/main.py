# ==============================================================================
# Name:        Philipp Fischer
# Kontakt:     p.fischer@itconex.de
# Version:     2026.03.19.13.26.52
# Beschreibung: LogBot v2026.03.19.13.26.52 - FastAPI Hauptanwendung
# ==============================================================================

from datetime import datetime
import secrets
import logging
from fastapi import FastAPI, HTTPException, Query, Header, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from .config import settings
from .database import get_db, async_session
from .models import Webhook, Log, Agent, AgentToken
from .schemas import LogResponse, LogDetailResponse, LogIngestRequest, LogIngestResponse
from .routes import auth_router, health_router, users_router, agents_router, agent_tokens_router, logs_router, webhooks_router, settings_router
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

# Sicherstellen, dass mindestens ein Agent-Token existiert (fuer HTTPS-Agent-Installationen)
@app.on_event("startup")
async def ensure_default_agent_token():
    logger = logging.getLogger("logbot.startup")
    try:
        async with async_session() as session:
            existing = await session.execute(select(AgentToken.id))
            if existing.scalar_one_or_none():
                return
            default_token = AgentToken(
                name="default-windows-agent",
                token=secrets.token_hex(32),
                is_active=True,
            )
            session.add(default_token)
            await session.commit()
            logger.info("Default agent token created")
    except Exception as exc:
        # Nicht den gesamten Service kippen, falls DB noch nicht bereit ist
        logger.warning("Default agent token init skipped: %s", exc)

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
