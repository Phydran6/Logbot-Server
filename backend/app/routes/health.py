# ==============================================================================
# Name:        Philipp Fischer
# Kontakt:     p.fischer@itconex.de
# Version:     2026.02.16.12.00.00
# Beschreibung: LogBot v2026.02.16.12.00.00 - Health API Endpoints
# ==============================================================================

import time
from datetime import datetime, timedelta
import psutil
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from ..config import settings
from ..database import get_db
from ..models import Log, Agent
from ..schemas import HealthResponse, HealthDetailedResponse
from ..auth import get_current_user

router = APIRouter(prefix="/api/health", tags=["Health"])
SERVER_START = time.time()

@router.get("", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="healthy", version=settings.app_version)

@router.get("/detailed", response_model=HealthDetailedResponse)
async def health_detailed(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    db_ok = True
    logs_total = logs_24h = agents_total = agents_online = 0
    try:
        logs_total = (await db.execute(text(
            "SELECT GREATEST(reltuples::bigint, 0) FROM pg_class WHERE relname = 'logs'"
        ))).scalar() or 0
        yesterday = datetime.utcnow() - timedelta(hours=24)
        logs_24h = (await db.execute(select(func.count(Log.id)).where(Log.timestamp >= yesterday))).scalar() or 0
        agents_total = (await db.execute(select(func.count(Agent.id)))).scalar() or 0
        five_min = datetime.utcnow() - timedelta(minutes=5)
        agents_online = (await db.execute(select(func.count(Agent.id)).where(Agent.last_seen >= five_min))).scalar() or 0
    except:
        db_ok = False
    
    return HealthDetailedResponse(
        status="healthy" if db_ok else "degraded",
        version=settings.app_version,
        uptime_seconds=time.time() - SERVER_START,
        cpu_percent=psutil.cpu_percent(interval=0.1),
        memory_percent=psutil.virtual_memory().percent,
        disk_percent=psutil.disk_usage('/').percent,
        database_connected=db_ok,
        logs_total=logs_total,
        logs_last_24h=logs_24h,
        agents_total=agents_total,
        agents_online=agents_online
    )
