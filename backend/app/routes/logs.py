# ==============================================================================
# Name:        Philipp Fischer
# Kontakt:     p.fischer@itconex.de
# Version:     2026.02.16.12.00.00
# Beschreibung: LogBot v2026.02.16.12.00.00 - Logs API Endpoints
# ==============================================================================

import logging
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc, text
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..models import Log, Agent, User
from ..schemas import LogResponse, LogDetailResponse, LogListResponse, LogStatsResponse
from ..auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/logs", tags=["Logs"])


def _apply_filters(query, hostname, level, source, search, start_date, end_date):
    """Filter-Bedingungen auf eine Query anwenden."""
    if hostname:
        query = query.where(Log.hostname.ilike(f"%{hostname}%"))
    if level:
        query = query.where(func.lower(Log.level) == level.lower())
    if source:
        query = query.where(Log.source.ilike(f"%{source}%"))
    if search:
        query = query.where(Log.message.ilike(f"%{search}%"))
    if start_date:
        query = query.where(Log.timestamp >= start_date)
    if end_date:
        query = query.where(Log.timestamp <= end_date)
    return query


@router.get("", response_model=LogListResponse)
async def list_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    hostname: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user)
):
    logger.info(f"Log-Filter: hostname={hostname}, level={level}, source={source}, search={search}, page={page}")

    query = select(Log)
    has_filters = any([hostname, level, source, search, start_date, end_date])
    query = _apply_filters(query, hostname, level, source, search, start_date, end_date)

    # Bei Filtern exakten Count, ohne Filter Schätzung aus pg_class
    if has_filters:
        count_query = _apply_filters(
            select(func.count(Log.id)), hostname, level, source, search, start_date, end_date
        )
        total = (await db.execute(count_query)).scalar() or 0
    else:
        total = (await db.execute(text(
            "SELECT GREATEST(reltuples::bigint, 0) FROM pg_class WHERE relname = 'logs'"
        ))).scalar() or 0

    logger.info(f"Log-Filter Ergebnis: {total} Treffer")

    offset = (page - 1) * page_size
    result = await db.execute(query.order_by(desc(Log.timestamp)).offset(offset).limit(page_size))

    return LogListResponse(items=result.scalars().all(), total=total, page=page, page_size=page_size)

@router.get("/filter-options")
async def get_filter_options(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    """Gibt die eindeutigen Werte für Hostname, Source und Level zurück (für Dropdown-Filter).
    Nutzt agents-Tabelle für Hostnames (wenige Zeilen statt 8M+ Logs zu scannen)."""
    # Hostnames aus agents-Tabelle (7 Zeilen statt DISTINCT über 8M Logs)
    hostnames = (await db.execute(
        select(Agent.hostname).where(Agent.hostname.isnot(None)).distinct().order_by(Agent.hostname)
    )).scalars().all()
    # Source/Level: DISTINCT nur über indizierte Spalten, schnell genug
    sources = (await db.execute(
        select(Log.source).where(Log.source.isnot(None)).distinct().order_by(Log.source)
    )).scalars().all()
    levels = (await db.execute(
        select(Log.level).where(Log.level.isnot(None)).distinct().order_by(Log.level)
    )).scalars().all()
    return {"hostnames": hostnames, "sources": sources, "levels": levels}

@router.get("/recent", response_model=List[LogResponse])
async def get_recent_logs(limit: int = Query(10, ge=1, le=100), db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(Log).order_by(desc(Log.timestamp)).limit(limit))
    return result.scalars().all()

@router.get("/stats", response_model=LogStatsResponse)
async def get_log_stats(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    # Nur Logs ab heute zählen für Level/Source Statistiken (nutzt timestamp-Index)
    today_count = (await db.execute(select(func.count(Log.id)).where(Log.timestamp >= today))).scalar() or 0
    by_level = dict((await db.execute(select(Log.level, func.count(Log.id)).where(Log.timestamp >= today).group_by(Log.level))).all())
    by_source = dict((await db.execute(select(Log.source, func.count(Log.id)).where(Log.timestamp >= today).group_by(Log.source).order_by(desc(func.count(Log.id))).limit(10))).all())

    # Gesamtzahl aus pg_class Statistik (sofort, kein Full-Scan über 8M+ Zeilen)
    total = (await db.execute(text(
        "SELECT GREATEST(reltuples::bigint, 0) FROM pg_class WHERE relname = 'logs'"
    ))).scalar() or 0

    # Unique Hosts aus agents-Tabelle (7 Zeilen statt 41k+ Logs scannen)
    unique = (await db.execute(select(func.count(Agent.id)))).scalar() or 0

    return LogStatsResponse(total_logs=total, logs_today=today_count, logs_by_level=by_level, logs_by_source=by_source, unique_hosts=unique)

@router.get("/{log_id}", response_model=LogDetailResponse)
async def get_log(log_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(Log).where(Log.id == log_id))
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Log nicht gefunden")
    return log
