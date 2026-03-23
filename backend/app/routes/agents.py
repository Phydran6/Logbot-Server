# ==============================================================================
# Name:        Philipp Fischer
# Kontakt:     p.fischer@itconex.de
# Version:     2026.02.11.18.30.00
# Beschreibung: LogBot v2026.02.11.18.30.00 - Agents API Endpoints
# ==============================================================================

import secrets
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..models import Agent, AgentToken, Log, User, Setting
from ..schemas import AgentResponse, AgentListResponse, AgentTokenCreate, AgentTokenResponse
from ..auth import get_current_user

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
        log_count=log_count
    )

@router.delete("/{agent_id}", status_code=204)
async def delete_agent(agent_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent nicht gefunden")
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
    token = AgentToken(name=data.name, token=secrets.token_hex(32))
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
