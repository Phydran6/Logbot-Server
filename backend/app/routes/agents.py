# ==============================================================================
# Name:        Phydran6
# Kontakt:     Phydran6
# Version:     2026.04.11.13.38.42
# Beschreibung: LogBot v2026.04.11.13.38.42 - Agents API Endpoints
# ==============================================================================

import secrets
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Header
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..models import Agent, AgentToken, Log, User, Setting
from ..schemas import AgentResponse, AgentListResponse, AgentTokenCreate, AgentTokenResponse, AgentDecommissionRequest, AgentRetentionUpdate
from ..auth import get_current_user
from fastapi import status

router = APIRouter(prefix="/api/agents", tags=["Agents"])

@router.get("", response_model=AgentListResponse)
async def list_agents(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: Optional[str] = None,
    device_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user)
):
    query = select(Agent)
    count_query = select(func.count(Agent.id))
    
    if search:
        f = f"%{search}%"
        query = query.where((Agent.hostname.ilike(f)) | (Agent.ip_address.ilike(f)) | (Agent.mac_address.ilike(f)))
        count_query = count_query.where((Agent.hostname.ilike(f)) | (Agent.ip_address.ilike(f)) | (Agent.mac_address.ilike(f)))
    if device_type:
        query = query.where(Agent.device_type == device_type)
        count_query = count_query.where(Agent.device_type == device_type)
    
    total = (await db.execute(count_query)).scalar() or 0
    offset = (page - 1) * page_size
    result = await db.execute(query.order_by(Agent.last_seen.desc()).offset(offset).limit(page_size))

    # Offline-Timeout aus Settings (Fallback 300s)
    offline_timeout = 300
    setting_row = await db.execute(select(Setting).where(Setting.key == "agent_offline_timeout"))
    s = setting_row.scalar_one_or_none()
    if s:
        try:
            offline_timeout = int(s.value)
        except Exception:
            pass
    cutoff = datetime.utcnow() - timedelta(seconds=offline_timeout)

    items = []
    for agent in result.scalars().all():
        is_online = bool(agent.last_seen and agent.last_seen >= cutoff)
        items.append(AgentResponse(
            id=agent.id,
            hostname=agent.hostname,
            ip_address=agent.ip_address,
            mac_address=agent.mac_address,
            device_type=agent.device_type,
            last_seen=agent.last_seen,
            first_seen=agent.first_seen,
            extra_data=getattr(agent, "extra_data", {}) or {},
            metadata=getattr(agent, "extra_data", {}) or {},
            is_online=is_online
        ))

    return AgentListResponse(items=items, total=total, page=page, page_size=page_size)

@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent nicht gefunden")
    log_count = (await db.execute(select(func.count(Log.id)).where(Log.agent_id == agent_id))).scalar() or 0

    offline_timeout = 300
    setting_row = await db.execute(select(Setting).where(Setting.key == "agent_offline_timeout"))
    s = setting_row.scalar_one_or_none()
    if s:
        try:
            offline_timeout = int(s.value)
        except Exception:
            pass
    cutoff = datetime.utcnow() - timedelta(seconds=offline_timeout)
    is_online = bool(agent.last_seen and agent.last_seen >= cutoff)

    return AgentResponse(
        id=agent.id, hostname=agent.hostname, ip_address=agent.ip_address,
        mac_address=agent.mac_address, device_type=agent.device_type,
        last_seen=agent.last_seen, first_seen=agent.first_seen,
        extra_data=getattr(agent, "extra_data", {}) or {},
        metadata=getattr(agent, "extra_data", {}) or {},
        is_online=is_online,
        log_count=log_count,
        retention_max_logs=agent.retention_max_logs,
        retention_days=agent.retention_days,
    )


@router.put("/{agent_id}/retention")
async def set_agent_retention(
    agent_id: int,
    data: AgentRetentionUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Setzt die Retention-Policy für einen einzelnen Agent."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent nicht gefunden")
    agent.retention_max_logs = data.retention_max_logs
    agent.retention_days = data.retention_days
    await db.commit()
    return {
        "agent_id": agent_id,
        "retention_max_logs": agent.retention_max_logs,
        "retention_days": agent.retention_days,
    }


@router.post("/{agent_id}/retention/execute")
async def execute_agent_retention(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Führt die Retention-Policy für einen Agent sofort aus."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent nicht gefunden")

    deleted = 0
    if agent.retention_days:
        cutoff = datetime.utcnow() - timedelta(days=agent.retention_days)
        r = await db.execute(delete(Log).where(Log.agent_id == agent_id, Log.timestamp < cutoff))
        deleted += r.rowcount or 0

    if agent.retention_max_logs:
        count = (await db.execute(
            select(func.count(Log.id)).where(Log.agent_id == agent_id)
        )).scalar() or 0
        excess = count - agent.retention_max_logs
        if excess > 0:
            subq = (
                select(Log.id)
                .where(Log.agent_id == agent_id)
                .order_by(Log.timestamp.asc())
                .limit(excess)
                .scalar_subquery()
            )
            r = await db.execute(delete(Log).where(Log.id.in_(subq)))
            deleted += r.rowcount or 0

    await db.commit()
    return {"agent_id": agent_id, "deleted_count": deleted}


@router.post("/decommission", status_code=status.HTTP_200_OK)
async def decommission_agent(
    payload: AgentDecommissionRequest,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Wird vom Agent bei \"vollst\u00e4ndig entfernen\" aufgerufen."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer Token erforderlich")
    token_value = authorization[7:]

    result = await db.execute(
        select(AgentToken).where(AgentToken.token == token_value, AgentToken.is_active == True))
    agent_token = result.scalar_one_or_none()
    if not agent_token:
        raise HTTPException(status_code=401, detail="Ung\u00fcltiger Agent-Token")

    agent = None
    if payload.mac_address:
        agent = (await db.execute(select(Agent).where(Agent.mac_address == payload.mac_address))).scalar_one_or_none()
    if not agent and payload.hostname and payload.ip_address:
        agent = (await db.execute(
            select(Agent).where(Agent.hostname == payload.hostname, Agent.ip_address == payload.ip_address)
        )).scalar_one_or_none()
    if not agent and payload.hostname:
        agent = (await db.execute(select(Agent).where(Agent.hostname == payload.hostname))).scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent nicht gefunden")

    if payload.purge:
        await db.execute(delete(Log).where(Log.agent_id == agent.id))
        await db.delete(agent)
        await db.commit()
        return {"status": "purged", "agent_id": agent.id}

    # Markiere als decommissioned und setze last_seen zur\u00fcck
    extra = getattr(agent, "extra_data", {}) or {}
    extra.update({
        "decommissioned": True,
        "decommissioned_at": datetime.utcnow().isoformat(),
        "decommissioned_token": agent_token.name,
        "decommissioned_token_type": agent_token.device_type
    })
    agent.extra_data = extra
    agent.last_seen = None
    await db.commit()
    return {"status": "decommissioned", "agent_id": agent.id}

@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: int,
    purge_logs: bool = Query(False, description="Logs des Agents mit l\u00f6schen"),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user)
):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent nicht gefunden")

    if purge_logs:
        await db.execute(delete(Log).where(Log.agent_id == agent_id))

    await db.delete(agent)
    await db.commit()

# ==============================================================================
# Agent Token CRUD
# ==============================================================================

token_router = APIRouter(prefix="/api/agent-tokens", tags=["Agent Tokens"])

@token_router.get("", response_model=List[AgentTokenResponse])
async def list_agent_tokens(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(AgentToken).order_by(AgentToken.created_at.desc()))
    return result.scalars().all()

@token_router.post("", response_model=AgentTokenResponse, status_code=201)
async def create_agent_token(data: AgentTokenCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    token = AgentToken(name=data.name, token=secrets.token_hex(32), device_type=data.device_type)
    db.add(token)
    await db.commit()
    await db.refresh(token)
    return token

@token_router.post("/{token_id}/regenerate", response_model=AgentTokenResponse)
async def regenerate_agent_token(token_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(AgentToken).where(AgentToken.id == token_id))
    token = result.scalar_one_or_none()
    if not token:
        raise HTTPException(status_code=404, detail="Token nicht gefunden")
    token.token = secrets.token_hex(32)
    await db.commit()
    await db.refresh(token)
    return token

@token_router.delete("/{token_id}", status_code=204)
async def delete_agent_token(token_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(AgentToken).where(AgentToken.id == token_id))
    token = result.scalar_one_or_none()
    if not token:
        raise HTTPException(status_code=404, detail="Token nicht gefunden")
    await db.delete(token)
    await db.commit()
