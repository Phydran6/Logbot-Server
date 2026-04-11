# ==============================================================================
# Name:        Philipp Fischer
# Kontakt:     p.fischer@itconex.de
# Version:     2026.02.16.12.00.00
# Beschreibung: LogBot v2026.02.16.12.00.00 - Logs API Endpoints
# ==============================================================================

import logging
import os
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select, func, desc, text
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..models import Log, Agent, User
from ..schemas import LogResponse, LogDetailResponse, LogListResponse, LogStatsResponse
from ..auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/logs", tags=["Logs"])

# Columns die die Logliste wirklich braucht (reduziert I/O)
LIST_COLUMNS = (
    Log.id,
    Log.hostname,
    Log.ip_address,
    Log.timestamp,
    Log.level,
    Log.source,
    Log.message,
)

# Kleiner In-Memory-Cache für Dashboard-Stats, um wiederholte Aufrufe zu entlasten
_stats_cache = None
_stats_cache_expires = datetime.min
_stats_cache_lock = asyncio.Lock()
_stats_cache_ttl = int(os.getenv("LOG_STATS_CACHE_SECONDS", "30"))


_LIKE_ESCAPE_CHAR = "\\"
_LIKE_ESCAPE_TABLE = str.maketrans({
    _LIKE_ESCAPE_CHAR: _LIKE_ESCAPE_CHAR * 2,
    "%": f"{_LIKE_ESCAPE_CHAR}%",
    "_": f"{_LIKE_ESCAPE_CHAR}_",
})


def _escape_like(value: str) -> str:
    """Escapt LIKE-Sonderzeichen (%, _, \) damit User-Input nicht als Wildcard wirkt."""
    return value.translate(_LIKE_ESCAPE_TABLE)


def _apply_filters(query, hostname, level, source, search, start_date, end_date):
    """Filter-Bedingungen auf eine Query anwenden."""
    hostname = hostname.strip() if hostname else None
    level = level.strip() if level else None
    source = source.strip() if source else None
    search = search.strip() if search else None

    if hostname:
        query = query.where(Log.hostname.ilike(f"%{_escape_like(hostname)}%", escape=_LIKE_ESCAPE_CHAR))
    if level:
        query = query.where(func.lower(Log.level) == level.lower())
    if source:
        query = query.where(Log.source.ilike(f"%{_escape_like(source)}%", escape=_LIKE_ESCAPE_CHAR))
    if search:
        query = query.where(Log.message.ilike(f"%{_escape_like(search)}%", escape=_LIKE_ESCAPE_CHAR))
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

    query = select(*LIST_COLUMNS)
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

    items = [dict(row) for row in result.mappings().all()]

    return LogListResponse(items=items, total=total, page=page, page_size=page_size)


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
async def get_recent_logs(limit: int = Query(10, ge=1, le=100), db: AsyncSession = Depends(get_db), _=Depends(get_current_user), response: Response = None):
    query = select(*LIST_COLUMNS).order_by(desc(Log.timestamp)).limit(limit)
    result = await db.execute(query)
    items = [dict(row) for row in result.mappings().all()]
    if response is not None:
        response.headers["Cache-Control"] = "public, max-age=15"
    return items


@router.get("/stats", response_model=LogStatsResponse)
async def get_log_stats(db: AsyncSession = Depends(get_db), _=Depends(get_current_user), response: Response = None):
    """Schnelle Dashboard-Stats mit kurzem Cache, um DB-Last zu senken."""
    global _stats_cache, _stats_cache_expires

    now = datetime.utcnow()
    if _stats_cache and now < _stats_cache_expires:
        return _stats_cache

    async with _stats_cache_lock:
        now = datetime.utcnow()
        if _stats_cache and now < _stats_cache_expires:
            return _stats_cache

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

        stats = LogStatsResponse(
            total_logs=total,
            logs_today=today_count,
            logs_by_level=by_level,
            logs_by_source=by_source,
            unique_hosts=unique
        )

        _stats_cache = stats
        _stats_cache_expires = datetime.utcnow() + timedelta(seconds=_stats_cache_ttl)
        if response is not None:
            response.headers["Cache-Control"] = f"public, max-age={_stats_cache_ttl}"
        return stats


@router.get("/{log_id}", response_model=LogDetailResponse)
async def get_log(log_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(Log).where(Log.id == log_id))
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Log nicht gefunden")
    return log
