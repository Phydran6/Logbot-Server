# ==============================================================================
# Name:        Phydran6
# Kontakt:     Phydran6
# Version:     2026.10.22.23.00.00
# Beschreibung: LogBot - Agents API Endpoints (Geraete-Baum, Heartbeat, Agent-Updates)
# ==============================================================================

from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Header, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..models import Agent, AgentToken, Log, User, Setting
from ..schemas import (AgentResponse, AgentListResponse, AgentDecommissionRequest,
                       AgentRetentionUpdate)
from ..auth import get_current_user, get_current_admin
from ..limiter import limiter, client_ip as real_client_ip
from .. import agentinv, agentupdate, journal, tokens

router = APIRouter(prefix="/api/agents", tags=["Agents"])

async def _offline_cutoff(db: AsyncSession) -> datetime:
    offline_timeout = 300
    s = (await db.execute(select(Setting).where(Setting.key == "agent_offline_timeout"))).scalar_one_or_none()
    if s:
        try:
            offline_timeout = int(s.value)
        except Exception:
            pass
    return datetime.utcnow() - timedelta(seconds=offline_timeout)


def _agent_response(agent: Agent, cutoff: datetime, **more) -> AgentResponse:
    extra = getattr(agent, "extra_data", {}) or {}
    return AgentResponse(
        id=agent.id, hostname=agent.hostname, ip_address=agent.ip_address,
        mac_address=agent.mac_address, device_type=agent.device_type or "unknown",
        last_seen=agent.last_seen, first_seen=agent.first_seen,
        extra_data=extra, metadata=extra,
        is_online=bool(agent.last_seen and agent.last_seen >= cutoff),
        retention_max_logs=agent.retention_max_logs, retention_days=agent.retention_days,
        parent_id=agent.parent_id, agent_version=agent.agent_version,
        update_policy=agent.update_policy, update_state=agent.update_state or {},
        ingest_limit_per_minute=agent.ingest_limit_per_minute, **more)


@router.get("", response_model=AgentListResponse)
async def list_agents(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    search: Optional[str] = None,
    device_type: Optional[str] = None,
    include_children: bool = Query(False, description="Container-Instanzen mitliefern"),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user)
):
    """Geraete - standardmaessig nur die eigentlichen Systeme (VMs, Rechner, Netzgeraete).

    Container haengen darunter (``children_count``); mit ``include_children``
    kommen sie als eigene Eintraege mit, ``/api/agents/tree`` liefert den Baum.
    """
    query = select(Agent)
    count_query = select(func.count(Agent.id))
    if not include_children:
        query = query.where(Agent.parent_id.is_(None))
        count_query = count_query.where(Agent.parent_id.is_(None))
    if search:
        f = f"%{search}%"
        cond = (Agent.hostname.ilike(f)) | (Agent.ip_address.ilike(f)) | (Agent.mac_address.ilike(f))
        query = query.where(cond)
        count_query = count_query.where(cond)
    if device_type:
        query = query.where(Agent.device_type == device_type)
        count_query = count_query.where(Agent.device_type == device_type)

    total = (await db.execute(count_query)).scalar() or 0
    offset = (page - 1) * page_size
    rows = (await db.execute(query.order_by(Agent.last_seen.desc().nullslast())
                             .offset(offset).limit(page_size))).scalars().all()
    counts = dict((await db.execute(
        select(Agent.parent_id, func.count(Agent.id)).where(Agent.parent_id.is_not(None))
        .group_by(Agent.parent_id))).all())
    cutoff = await _offline_cutoff(db)
    items = [_agent_response(agent, cutoff, children_count=counts.get(agent.id, 0)) for agent in rows]
    return AgentListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/tree")
async def agent_tree(with_counts: bool = Query(False), db: AsyncSession = Depends(get_db),
                     _=Depends(get_current_user)):
    """Alle Geraete als Baum: VM → Compose-Projekt → Container."""
    agents = (await db.execute(select(Agent).order_by(Agent.hostname))).scalars().all()
    counts = None
    if with_counts:
        counts = dict((await db.execute(select(Log.agent_id, func.count(Log.id))
                                        .group_by(Log.agent_id))).all())
    return {"items": agentinv.tree(agents, await _offline_cutoff(db), counts)}


@router.get("/{agent_id:int}", response_model=AgentResponse)
async def get_agent(agent_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent nicht gefunden")
    log_count = (await db.execute(select(func.count(Log.id)).where(Log.agent_id == agent_id))).scalar() or 0
    children = (await db.execute(select(func.count(Agent.id)).where(Agent.parent_id == agent_id))).scalar() or 0
    return _agent_response(agent, await _offline_cutoff(db), log_count=log_count, children_count=children)


@router.put("/{agent_id:int}/retention")
async def set_agent_retention(
    agent_id: int,
    data: AgentRetentionUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    """Setzt die Aufbewahrung für ein einzelnes Gerät.

    Nur Administratoren: hier wird festgelegt, ab wann Logzeilen verschwinden —
    das ist keine Anzeigeeinstellung, das ist Datenverlust auf Ansage.
    """
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent nicht gefunden")
    agent.retention_max_logs = data.retention_max_logs
    agent.retention_days = data.retention_days
    agent.ingest_limit_per_minute = data.ingest_limit_per_minute
    await db.commit()
    return {
        "agent_id": agent_id,
        "retention_max_logs": agent.retention_max_logs,
        "retention_days": agent.retention_days,
        "ingest_limit_per_minute": agent.ingest_limit_per_minute,
    }


@router.post("/{agent_id:int}/retention/execute")
async def execute_agent_retention(
    agent_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """Führt die Aufbewahrung für ein Gerät sofort aus (löscht Logzeilen)."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent nicht gefunden")

    # Die VM und - mit den geerbten Werten - ihre Container.
    from ..main import _enforce_agent_retention
    import logging as _logging
    defaults = await agentinv.device_defaults(db)
    targets = [agent] + list((await db.execute(
        select(Agent).where(Agent.parent_id == agent.id))).scalars().all())
    deleted = 0
    for target in targets:
        deleted += await _enforce_agent_retention(db, target, _logging.getLogger("logbot.agent_retention"),
                                                  parent=agent if target is not agent else None,
                                                  defaults=defaults)
    await db.commit()
    if deleted:
        await journal.record(
            db, category="retention", event="agent.retention.manual", level="notice",
            message=f"{deleted} Logzeilen von '{agent.hostname}' von Hand entfernt.",
            actor=admin.username, source_ip=real_client_ip(request), target=agent.hostname,
            detail={"agent_id": agent_id, "deleted": deleted})
    return {"agent_id": agent_id, "deleted_count": deleted}


@router.post("/decommission", status_code=status.HTTP_200_OK)
@limiter.limit("30/minute")
async def decommission_agent(
    payload: AgentDecommissionRequest,
    request: Request,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Wird vom Agent beim vollständigen Entfernen aufgerufen."""
    source_ip = real_client_ip(request)
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer Token erforderlich")

    # Neu: ein GERAETESCHLUESSEL darf nur sein eigenes Geraet abmelden. Vorher
    # konnte jeder gueltige Schluessel jedes beliebige Geraet samt Logs
    # loeschen - auf einem Netz mit hundert Agents war das eine Einladung.
    # Der Generalschluessel darf weiterhin alles; er ist der des Administrators.
    agent_token, deny_reason = await tokens.resolve(db, authorization[7:], source_ip)
    if not agent_token:
        await journal.record(
            db, category="agent", event="decommission.rejected", level="warning",
            message=f"Abmeldung abgelehnt: {deny_reason}",
            actor="agent", source_ip=source_ip, target=payload.hostname or "", ok=False)
        raise HTTPException(status_code=401, detail="Ungültiger Agent-Token")

    # Zuordnung, vom Genauesten zum Ungenauesten. `matched_by` wandert in die
    # Antwort - der Agent kann dann sagen, ob wirklich sein eigener Eintrag
    # getroffen wurde oder nur einer, der zufaellig so heisst.
    agents: List[Agent] = []
    matched_by = ""

    if payload.agent_id:
        hit = (await db.execute(select(Agent).where(Agent.id == payload.agent_id))).scalar_one_or_none()
        if hit:
            agents, matched_by = [hit], "agent_id"

    if not agents and payload.mac_address:
        hit = (await db.execute(
            select(Agent).where(Agent.mac_address == payload.mac_address)
        )).scalar_one_or_none()
        if hit:
            agents, matched_by = [hit], "mac_address"

    if not agents and payload.hostname and payload.ip_address:
        hit = (await db.execute(
            select(Agent).where(Agent.hostname == payload.hostname,
                                Agent.ip_address == payload.ip_address)
        )).scalar_one_or_none()
        if hit:
            agents, matched_by = [hit], "hostname+ip"

    if not agents and payload.hostname:
        # Ein Rechner, der die IP gewechselt hat (DHCP, NAT, Umzug), steht hier
        # mehrfach. Beim Abraeumen sollen alle mitgehen - sonst bleiben
        # Karteileichen mit ihren Logs liegen.
        rows = (await db.execute(
            select(Agent).where(Agent.hostname == payload.hostname)
        )).scalars().all()
        if rows:
            agents = list(rows) if payload.all_for_hostname else [rows[0]]
            matched_by = "hostname"

    if not agents:
        raise HTTPException(
            status_code=404,
            detail=("Zu dieser Angabe gibt es auf dem Server kein Geraet. "
                    "Moeglicherweise wurde es schon entfernt."))

    # Beim Deinstallieren soll wirklich alles weg sein, was zu diesem Rechner
    # gehoert. Ein Treffer ueber die Geraetenummer ist zwar genau - er findet
    # aber nur EINEN Eintrag. Hat der Rechner zwischendurch die IP gewechselt,
    # steht er mehrfach in der Liste, und der Rest bliebe als Karteileiche mit
    # seinen Logs zurueck. Also: gefundene Eintraege um die gleichnamigen ergaenzen.
    if payload.all_for_hostname and payload.hostname:
        known = {a.id for a in agents}
        extra = (await db.execute(
            select(Agent).where(Agent.hostname == payload.hostname)
        )).scalars().all()
        for candidate in extra:
            if candidate.id not in known:
                agents.append(candidate)
                known.add(candidate.id)

    ids = [a.id for a in agents]

    # Darf dieser Schluessel diese Geraete ueberhaupt anfassen? Ein
    # Geraeteschluessel darf genau eines: sich selbst abmelden.
    for agent in agents:
        allowed, why = tokens.may_decommission(agent_token, agent.id)
        if not allowed:
            await journal.record(
                db, category="agent", event="decommission.denied", level="warning",
                message=f"Abmeldung von '{agent.hostname}' verweigert: {why}",
                actor=agent_token.name, source_ip=source_ip, target=agent.hostname, ok=False)
            raise HTTPException(status_code=403, detail=why)

    # Der Schluessel des Geraets wird beim Abmelden entwertet. Ein
    # deinstallierter Agent laesst keinen gueltigen Schluessel zurueck.
    revoked = 0
    for agent in agents:
        for stale in (await db.execute(
            select(AgentToken).where(AgentToken.kind == "agent",
                                     AgentToken.agent_id == agent.id,
                                     AgentToken.revoked_at.is_(None))
        )).scalars().all():
            tokens.revoke(stale, reason=f"{agent.hostname} wurde abgemeldet")
            revoked += 1
    tokens.note_use(agent_token, source_ip)

    if payload.purge:
        deleted_logs = 0
        hostnames = [a.hostname for a in agents]
        for agent in agents:
            # Container der VM gehen mit - samt ihren Logs.
            child_ids = [cid for (cid,) in (await db.execute(
                select(Agent.id).where(Agent.parent_id == agent.id))).all()]
            result = await db.execute(delete(Log).where(Log.agent_id.in_([agent.id] + child_ids)))
            deleted_logs += result.rowcount or 0
            await db.delete(agent)
        await db.commit()
        await journal.record(
            db, category="agent", event="decommission.purged", level="warning",
            message=(f"{len(ids)} Geraet(e) restlos entfernt ({', '.join(hostnames)}), "
                     f"{deleted_logs} Logzeilen geloescht."),
            actor=agent_token.name, source_ip=source_ip,
            target=", ".join(hostnames)[:200],
            detail={"agent_ids": ids, "deleted_logs": deleted_logs,
                    "revoked_tokens": revoked, "matched_by": matched_by})
        return {"status": "purged", "agent_id": ids[0], "agent_ids": ids,
                "deleted_agents": len(ids), "deleted_logs": deleted_logs,
                "revoked_tokens": revoked,
                "matched_by": matched_by,
                "message": (f"{len(ids)} Geraet(e) und {deleted_logs} Logzeilen geloescht.")}

    # Nur abmelden: Eintrag und Logs bleiben, das Geraet gilt aber als stillgelegt.
    for agent in agents:
        # Kopie: dasselbe Objekt geaendert und wieder zugewiesen erkennt
        # SQLAlchemy nicht als Aenderung - die Stilllegung wurde nie gespeichert.
        extra = dict(getattr(agent, "extra_data", {}) or {})
        extra.update({
            "decommissioned": True,
            "decommissioned_at": datetime.utcnow().isoformat(),
            "decommissioned_token": agent_token.name,
            "decommissioned_token_type": agent_token.device_type,
        })
        agent.extra_data = extra
        agent.last_seen = None
    await db.commit()
    await journal.record(
        db, category="agent", event="decommission.ok",
        message=(f"{len(ids)} Geraet(e) stillgelegt. Logs und Eintrag bleiben erhalten."),
        actor=agent_token.name, source_ip=source_ip,
        target=", ".join(a.hostname for a in agents)[:200],
        detail={"agent_ids": ids, "revoked_tokens": revoked, "matched_by": matched_by})
    return {"status": "decommissioned", "agent_id": ids[0], "agent_ids": ids,
            "matched_by": matched_by, "revoked_tokens": revoked,
            "message": (f"{len(ids)} Geraet(e) stillgelegt. Logs und Eintrag bleiben "
                        f"erhalten.")}


@router.delete("/{agent_id:int}", status_code=204)
async def delete_agent(
    agent_id: int,
    request: Request,
    purge_logs: bool = Query(False, description="Logs des Agents mit loeschen"),
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """Entfernt ein Geraet. Nur Administratoren - es ist nicht umkehrbar."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent nicht gefunden")

    hostname = agent.hostname
    deleted_logs = 0
    if purge_logs:
        child_ids = [cid for (cid,) in (await db.execute(
            select(Agent.id).where(Agent.parent_id == agent_id))).all()]
        outcome = await db.execute(delete(Log).where(Log.agent_id.in_([agent_id] + child_ids)))
        deleted_logs = outcome.rowcount or 0

    await db.delete(agent)
    await db.commit()
    await journal.record(
        db, category="agent", event="agent.deleted", level="warning",
        message=(f"Geraet '{hostname}' geloescht"
                 + (f", dazu {deleted_logs} Logzeilen." if purge_logs else ".")),
        actor=admin.username, source_ip=real_client_ip(request), target=hostname,
        detail={"agent_id": agent_id, "deleted_logs": deleted_logs})

# ==============================================================================
# Schluesselverwaltung
# ==============================================================================
"""
Die Endpunkte zur Schluesselverwaltung.

**Zwei Dinge haben sich gegenueber frueher geaendert, und beide sind wichtig.**

1. *Nur noch Administratoren.* Vorher reichte ein beliebiges angemeldetes
   Konto, um alle Agent-Schluessel im Klartext zu lesen, neue anzulegen und
   vorhandene zu loeschen. Ein Benutzer mit reinen Leserechten auf die Logs
   konnte sich damit den Generalschluessel besorgen. Das war eine Luecke, und
   sie ist zu.
2. *Der Schluessel wird genau einmal angezeigt.* Danach gibt es ihn nirgends
   mehr zu lesen - er liegt nur noch als Pruefsumme in der Datenbank. Wer ihn
   verlegt, erneuert ihn; das ist eine Sache von zwei Klicks und besser als ein
   Schluesselbund, den jeder Datenbankabzug mitnimmt.
"""

token_router = APIRouter(prefix="/api/agent-tokens", tags=["Agent Tokens"])


class TokenCreateRequest(BaseModel):
    """Ein neuer Schluessel."""
    name: str = Field(..., min_length=1, max_length=100)
    kind: str = Field(default="agent", pattern="^(global|agent|enroll)$")
    device_type: Optional[str] = Field(default=None, pattern="^(linux|windows)$")
    agent_id: Optional[int] = None
    allowed_cidrs: str = Field(default="", max_length=500,
                               description="Absenderbereiche, z.B. '10.0.0.0/8'. Leer = ueberall.")
    expires_in_hours: Optional[int] = Field(default=None, ge=1, le=24 * 365 * 5)
    max_uses: Optional[int] = Field(default=None, ge=1, le=10000)
    note: str = Field(default="", max_length=500)


class TokenUpdateRequest(BaseModel):
    """Was sich nachtraeglich noch aendern laesst - der Schluessel selbst nie."""
    name: Optional[str] = Field(default=None, max_length=100)
    is_active: Optional[bool] = None
    allowed_cidrs: Optional[str] = Field(default=None, max_length=500)
    note: Optional[str] = Field(default=None, max_length=500)


class EnrollRequest(BaseModel):
    """Ein Agent meldet sich an und bittet um einen eigenen Schluessel."""
    hostname: str = Field(..., min_length=1, max_length=255)
    device_type: Optional[str] = Field(default=None, pattern="^[a-z0-9_-]{1,50}$")
    ip_address: Optional[str] = Field(default=None, max_length=45)
    mac_address: Optional[str] = Field(default=None, max_length=17)


@token_router.get("")
async def list_agent_tokens(db: AsyncSession = Depends(get_db), _=Depends(get_current_admin)):
    """Alle Schlüssel — ohne die Schlüssel selbst."""
    return {
        "items": await tokens.list_all(db),
        "note": ("Ein Schlüssel wird genau einmal angezeigt: direkt nach dem Anlegen. "
                 "Danach steht er nur noch als Prüfsumme in der Datenbank und lässt "
                 "sich nicht mehr auslesen — auch von hier nicht."),
    }


@token_router.post("", status_code=201)
async def create_agent_token(data: TokenCreateRequest, request: Request,
                             db: AsyncSession = Depends(get_db),
                             admin=Depends(get_current_admin)):
    """Legt einen Schlüssel an und zeigt ihn **einmalig** an."""
    if data.kind == "global":
        existing = (await db.execute(
            select(AgentToken).where(AgentToken.kind == "global",
                                     AgentToken.revoked_at.is_(None))
        )).scalars().first()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=("Es gibt bereits einen Generalschlüssel. Absichtlich nur einer — "
                        "zwei davon heißt, dass niemand mehr weiß, welcher wo liegt. "
                        "Zum Austauschen: 'Neu würfeln'."))

    try:
        row, plain = await tokens.create(
            db, name=data.name, kind=data.kind, device_type=data.device_type,
            agent_id=data.agent_id, allowed_cidrs=data.allowed_cidrs,
            expires_in_hours=(data.expires_in_hours
                              or (tokens.DEFAULT_ENROLL_HOURS if data.kind == "enroll" else None)),
            max_uses=(data.max_uses
                      or (tokens.DEFAULT_ENROLL_USES if data.kind == "enroll" else None)),
            created_by=admin.username, note=data.note)
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await journal.record(
        db, category="token", event="token.created", level="warning",
        message=f"Schlüssel '{row.name}' ({data.kind}) angelegt.",
        actor=admin.username, source_ip=real_client_ip(request), target=row.name,
        detail={"kind": data.kind, "prefix": row.prefix})

    return {
        **tokens.public(row),
        "token": plain,
        "shown_once": True,
        "warning": "Jetzt notieren oder eintragen — danach ist der Schlüssel nicht mehr lesbar.",
    }


@token_router.put("/{token_id}")
async def update_agent_token(token_id: int, data: TokenUpdateRequest, request: Request,
                             db: AsyncSession = Depends(get_db),
                             admin=Depends(get_current_admin)):
    """Name, Zustand, Absenderbereich und Vermerk ändern."""
    row = (await db.execute(select(AgentToken).where(AgentToken.id == token_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Diesen Schlüssel gibt es nicht.")

    if data.name is not None:
        row.name = data.name.strip()[:100] or row.name
    if data.is_active is not None:
        row.is_active = data.is_active
    if data.allowed_cidrs is not None:
        row.allowed_cidrs = data.allowed_cidrs.strip() or None
    if data.note is not None:
        row.note = data.note.strip() or None
    await db.commit()

    await journal.record(db, category="token", event="token.updated",
                         message=f"Schlüssel '{row.name}' geändert.",
                         actor=admin.username, source_ip=real_client_ip(request),
                         target=row.name)
    return tokens.public(row)


@token_router.post("/{token_id}/regenerate")
async def regenerate_agent_token(token_id: int, request: Request,
                                 db: AsyncSession = Depends(get_db),
                                 admin=Depends(get_current_admin)):
    """Würfelt den Schlüssel neu. Der alte gilt ab diesem Moment nicht mehr."""
    row = (await db.execute(select(AgentToken).where(AgentToken.id == token_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Diesen Schlüssel gibt es nicht.")

    plain = await tokens.rotate(db, row, created_by=admin.username)
    await db.commit()

    await journal.record(
        db, category="token", event="token.rotated", level="warning",
        message=(f"Schlüssel '{row.name}' neu gewürfelt. Jedes Gerät, das den alten "
                 f"benutzt, kommt ab sofort nicht mehr durch."),
        actor=admin.username, source_ip=real_client_ip(request), target=row.name)

    return {
        **tokens.public(row),
        "token": plain,
        "shown_once": True,
        "warning": ("Jetzt eintragen. Geräte mit dem alten Schlüssel liefern ab sofort "
                    "nichts mehr."),
    }


@token_router.post("/harden")
async def harden_legacy_tokens(request: Request, db: AsyncSession = Depends(get_db),
                               admin=Depends(get_current_admin)):
    """Überführt Alt-Schlüssel in den geschützten Speicher.

    Schlüssel aus früheren Fassungen liegen noch im Klartext in der Datenbank.
    Dieser Aufruf trägt ihre Prüfsumme nach und löscht den Klartext. Die
    Schlüssel selbst bleiben gültig — auf den Geräten ändert sich nichts. Was
    verloren geht, ist nur die Möglichkeit, sie hier noch einmal abzulesen.
    """
    rows = (await db.execute(
        select(AgentToken).where(AgentToken.token.is_not(None))
    )).scalars().all()

    hardened = []
    for row in rows:
        if not row.token_hash:
            row.token_hash = tokens.digest(row.token)
        if not row.prefix:
            row.prefix = row.token[:10]
        if row.name == tokens.GLOBAL_TOKEN_NAME:
            row.kind = "global"
        elif not row.kind:
            row.kind = "agent"
        row.token = None
        hardened.append(row.name)
    await db.commit()

    if hardened:
        await journal.record(
            db, category="token", event="token.hardened", level="warning",
            message=f"{len(hardened)} Alt-Schlüssel in den geschützten Speicher überführt.",
            actor=admin.username, source_ip=real_client_ip(request),
            detail={"names": hardened})

    return {
        "hardened": len(hardened),
        "names": hardened,
        "message": (f"{len(hardened)} Schlüssel überführt. Sie gelten unverändert weiter, "
                    f"sind hier aber nicht mehr lesbar."
                    if hardened else "Es lag nichts mehr im Klartext."),
    }


@token_router.delete("/{token_id}", status_code=204)
async def delete_agent_token(token_id: int, request: Request,
                             db: AsyncSession = Depends(get_db),
                             admin=Depends(get_current_admin)):
    row = (await db.execute(select(AgentToken).where(AgentToken.id == token_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Diesen Schlüssel gibt es nicht.")
    if (row.kind or "").lower() == "global":
        raise HTTPException(
            status_code=409,
            detail=("Der Generalschlüssel lässt sich nicht löschen — ohne ihn kommt kein "
                    "Agent mehr durch, und ein neuer wäre beim nächsten Start ohnehin da. "
                    "Zum Austauschen: 'Neu würfeln'."))

    name = row.name
    await db.delete(row)
    await db.commit()
    await journal.record(db, category="token", event="token.deleted", level="warning",
                         message=f"Schlüssel '{name}' gelöscht.",
                         actor=admin.username, source_ip=real_client_ip(request), target=name)


# ==============================================================================
# Anmelden: ein Agent holt sich seinen eigenen Schluessel
# ==============================================================================
@router.post("/enroll", status_code=201)
@limiter.limit("30/minute")
async def enroll_agent(data: EnrollRequest, request: Request,
                       authorization: str = Header(...),
                       db: AsyncSession = Depends(get_db)):
    """Ein Agent tauscht eine Einladung (oder den Generalschlüssel) gegen seinen eigenen.

    Damit muss der Generalschlüssel nicht mehr auf jeden Rechner kopiert werden.
    Der Rechner bekommt einen Schlüssel, der nur für ihn gilt; geht das Gerät
    verloren, entwertet man genau diesen einen.

    Wird zweimal für denselben Hostnamen aufgerufen (Neuinstallation), entsteht
    ein neuer Schlüssel und der vorherige dieses Geräts wird zurückgezogen —
    sonst sammelt sich mit der Zeit ein Schlüsselbund an, den keiner mehr kennt.
    """
    source_ip = real_client_ip(request)
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer Token erforderlich")

    presenter, reason = await tokens.resolve(db, authorization[7:], source_ip)
    if not presenter or not tokens.may_enroll(presenter):
        await journal.record(
            db, category="token", event="enroll.rejected", level="warning",
            message=f"Anmeldung von {data.hostname} abgelehnt: {reason or 'nicht berechtigt'}",
            actor="agent", source_ip=source_ip, target=data.hostname, ok=False)
        raise HTTPException(status_code=401, detail="Ungültiger oder nicht berechtigter Schlüssel")

    hostname = data.hostname.strip()

    # Gibt es das Geraet schon? Dann bindet der neue Schluessel daran.
    agent = (await db.execute(
        select(Agent).where(Agent.hostname == hostname)
        .order_by(Agent.last_seen.desc().nullslast())
    )).scalars().first()

    # Alten Schluessel dieses Geraets zurueckziehen.
    replaced = 0
    if agent is not None:
        previous = (await db.execute(
            select(AgentToken).where(AgentToken.kind == "agent",
                                     AgentToken.agent_id == agent.id,
                                     AgentToken.revoked_at.is_(None))
        )).scalars().all()
        for old in previous:
            tokens.revoke(old, reason=f"Ersetzt bei Neuanmeldung von {hostname}")
            replaced += 1

    row, plain = await tokens.create(
        db,
        name=f"agent:{hostname}"[:100],
        kind="agent",
        device_type=data.device_type,
        agent_id=agent.id if agent else None,
        created_by=f"enroll:{presenter.name}"[:50],
        note=f"Automatisch beim Anmelden von {hostname} erzeugt.")

    tokens.note_use(presenter, source_ip)
    await db.commit()

    await journal.record(
        db, category="token", event="enroll.ok",
        message=(f"{hostname} hat einen eigenen Schlüssel bekommen"
                 + (f" (ersetzt {replaced} alten)." if replaced else ".")),
        actor=f"enroll:{presenter.name}", source_ip=source_ip, target=hostname,
        detail={"prefix": row.prefix, "replaced": replaced})

    _, update_key = await agentupdate.signing_keys(db)
    return {
        "token": plain,
        "name": row.name,
        "prefix": row.prefix,
        "agent_id": agent.id if agent else None,
        "replaced_previous": replaced,
        # Damit prueft der Agent spaeter die Unterschrift jedes Updates.
        "update_pubkey_pem": update_key["pem"],
        "update_pubkey_xml": update_key["xml"],
        "update_pubkey_fingerprint": update_key["fingerprint"],
        "message": ("Dieser Schlüssel gilt nur für dieses Gerät. Er wird nur jetzt "
                    "ausgegeben."),
    }


# ==============================================================================
# Wer liefert? - gemeinsam fuer Ingest und Heartbeat
# ==============================================================================
def _agent_type_fallback(token_type: Optional[str], user_agent: Optional[str]) -> str:
    """Geraeteart, wenn der Agent selbst keine mitschickt (Agents vor 2026.09.15).

    Reihenfolge: Typ des Tokens, dann der User-Agent (der Linux-Agent sendet per
    Python-urllib, der Windows-Agent per PowerShell), sonst "unknown".
    """
    mapped = {"linux": "linux_agent", "windows": "windows_agent"}.get(token_type or "")
    if mapped:
        return mapped
    ua = (user_agent or "").lower()
    if "powershell" in ua:
        return "windows_agent"
    if "python-urllib" in ua:
        return "linux_agent"
    return "unknown"


async def resolve_host_agent(db: AsyncSession, authorization: str, hostname: str,
                             reported_ip: Optional[str], device_type: Optional[str],
                             request: Request, event_prefix: str = "ingest",
                             agent_version: Optional[str] = None):
    """Prueft den Schluessel und findet (oder legt an) das liefernde Geraet.

    Gibt (Schluessel, Geraet, Absender-IP) zurueck; wirft 401/403 wie bisher
    der Ingest. Container sind nie das "liefernde Geraet" - das ist immer die
    VM, die Container haengen darunter.
    """
    source_ip = real_client_ip(request)
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer Token erforderlich")

    from ..main import _rejection_due

    agent_token, deny_reason = await tokens.resolve(db, authorization[7:], source_ip)
    if not agent_token:
        # Nach aussen immer dieselbe Antwort; der Grund steht im Systemtagebuch -
        # hoechstens alle 10 Minuten je Absender und Grund (ein Agent mit
        # zurueckgezogenem Schluessel versucht es alle paar Sekunden).
        suppressed = _rejection_due(("rejected", source_ip, hostname, deny_reason))
        if suppressed is not None:
            await journal.record(
                db, category="token", event=f"{event_prefix}.rejected", level="warning",
                message=(f"Lieferung von '{hostname}' abgewiesen: {deny_reason}"
                         + (f" (dazu {suppressed} weitere seit dem letzten Eintrag)" if suppressed else "")),
                actor="agent", source_ip=source_ip, target=hostname, ok=False)
        raise HTTPException(status_code=401, detail="Ungültiger Agent-Token")
    if "/" in hostname:
        raise HTTPException(status_code=400, detail="Ein Hostname darf keinen Schrägstrich enthalten.")

    device_ip = (reported_ip or "").strip() or source_ip
    proxy_ip = request.client.host if request.client else None
    resolved_type = device_type or _agent_type_fallback(
        agent_token.device_type, request.headers.get("user-agent"))

    agent = None
    if agent_token.kind == "agent" and agent_token.agent_id:
        # Geraeteschluessel: das Geraet ist bekannt - auch nach einem IP-Wechsel.
        bound = await db.get(Agent, agent_token.agent_id)
        if bound is not None and bound.hostname == hostname and bound.parent_id is None:
            agent = bound
            if device_ip and bound.ip_address != device_ip:
                clash = (await db.execute(select(Agent.id).where(
                    Agent.hostname == hostname, Agent.ip_address == device_ip,
                    Agent.id != bound.id))).first()
                if not clash:
                    bound.ip_address = device_ip
    if agent is None:
        agent = (await db.execute(select(Agent).where(
            Agent.hostname == hostname, Agent.ip_address == device_ip,
            Agent.parent_id.is_(None)))).scalars().first()

    if agent is None and proxy_ip and proxy_ip != device_ip:
        # Altbestand: bis 2026.09.15 wurde bei HTTPS-Agents die IP von Caddy
        # gespeichert statt der Geraete-IP. Solche Eintraege uebernehmen.
        agent = (await db.execute(select(Agent).where(
            Agent.hostname == hostname, Agent.ip_address == proxy_ip))).scalars().first()
        if agent:
            agent.ip_address = device_ip
            if resolved_type != "unknown":
                agent.device_type = resolved_type

    if agent:
        agent.last_seen = datetime.utcnow()
        if device_type:
            agent.device_type = device_type
        elif agent.device_type in (None, "unknown"):
            agent.device_type = resolved_type
    else:
        agent = Agent(
            hostname=hostname, ip_address=device_ip, device_type=resolved_type,
            extra_data={"auth": "token", "token_name": agent_token.name})
        db.add(agent)
        await db.flush()

    # Darf dieser Schluessel fuer dieses Geraet liefern? Der Generalschluessel
    # darf fuer alle; ein Geraeteschluessel nur fuer sein eigenes.
    allowed, why = tokens.may_ingest(agent_token, hostname, agent.id)
    if not allowed:
        token_name = agent_token.name          # nach dem rollback ist das Objekt abgelaufen
        await db.rollback()
        suppressed = _rejection_due(("denied", token_name, hostname, why))
        if suppressed is not None:
            await journal.record(
                db, category="token", event=f"{event_prefix}.denied", level="warning",
                message=(f"'{token_name}' wollte für '{hostname}' liefern: {why}"
                         + (f" (dazu {suppressed} weitere seit dem letzten Eintrag)" if suppressed else "")),
                actor=token_name, source_ip=source_ip, target=hostname, ok=False)
        raise HTTPException(status_code=403, detail=why)

    tokens.bind_to_agent(agent_token, agent.id)
    tokens.touch(agent_token, source_ip)

    if agent_version:
        previous = agent.agent_version
        agent.agent_version = agent_version[:40]
        state = dict(agent.update_state or {})
        if state.get("state") in ("offered", "installing") and \
                agentupdate.parse_version(agent_version) >= agentupdate.parse_version(state.get("version")):
            # Die neue Fassung meldet sich - das Update hat geklappt.
            state.update({"state": "done", "finished_at": datetime.utcnow().isoformat(),
                          "message": f"Aktualisiert von {previous or '?'} auf {agent_version}."})
            agent.update_state = state
            agent.update_requested_at = None
            await journal.record(
                db, category="agent_update", event="agent.update.done", level="notice", commit=False,
                message=f"Agent auf {hostname} aktualisiert: {previous or '?'} → {agent_version}.",
                actor="agent", source_ip=source_ip, target=hostname)
    return agent_token, agent, source_ip


# ==============================================================================
# Heartbeat: Lebenszeichen, Inventar (Docker), Update-Anweisung
# ==============================================================================
class HeartbeatRequest(BaseModel):
    hostname: str = Field(..., min_length=1, max_length=255)
    ip_address: Optional[str] = Field(default=None, max_length=45)
    device_type: Optional[str] = Field(default=None, pattern="^[a-z0-9_-]{1,50}$")
    agent_version: Optional[str] = Field(default=None, max_length=40, pattern=r"^[0-9A-Za-z.+_-]+$")
    os: Optional[str] = Field(default=None, max_length=120)
    capabilities: List[str] = Field(default_factory=list, max_length=30)
    remote_update: bool = True
    docker: Optional[dict] = None
    containers: Optional[List[dict]] = Field(default=None, max_length=agentinv.MAX_CONTAINERS)


@router.post("/heartbeat")
@limiter.limit("120/minute")
async def heartbeat(data: HeartbeatRequest, request: Request,
                    authorization: str = Header(None), db: AsyncSession = Depends(get_db)):
    """Der Agent meldet sich (jede Minute): Fassung, Faehigkeiten, Container.

    Antwort: die Geraetenummer, ggf. eine Update-Anweisung und Einstellungen
    vom Server. So gilt ein Geraet auch ohne Logzeilen als erreichbar.
    """
    agent_token, agent, source_ip = await resolve_host_agent(
        db, authorization or "", data.hostname, data.ip_address, data.device_type, request,
        event_prefix="heartbeat", agent_version=data.agent_version)

    extra = dict(agent.extra_data or {})
    extra["agent"] = {"version": data.agent_version, "os": (data.os or "")[:120],
                      "capabilities": [c[:40] for c in data.capabilities][:30],
                      "remote_update": bool(data.remote_update),
                      "heartbeat_at": datetime.utcnow().isoformat()}
    agent.extra_data = extra

    inventory = None
    if data.containers is not None or data.docker is not None:
        inventory = await agentinv.sync_inventory(db, agent, data.docker, data.containers or [])

    # Update?
    update = None
    os_name = agentupdate.os_of(agent)
    if os_name:
        config = await agentupdate.load_config(db)
        target = await agentupdate.package(db, os_name)
        go, reason = await agentupdate.decide(db, agent, target, config)
        if go:
            update = agentupdate.offer(agent, target, "")
            await journal.record(
                db, category="agent_update", event="agent.update.offered", level="notice", commit=False,
                message=(f"Update für {agent.hostname}: {agent.agent_version or '?'} → "
                         f"{target['version']} ({reason})"),
                actor="system", source_ip=source_ip, target=agent.hostname)
        else:
            state = dict(agent.update_state or {})
            if state.get("state") != "done" or state.get("reason") != reason:
                state["reason"] = reason
                agent.update_state = state
    await db.commit()

    defaults = await agentinv.device_defaults(db)
    return {
        "agent_id": agent.id,
        "server_time": datetime.utcnow().isoformat() + "Z",
        "update": update,
        "inventory": inventory,
        "config": {
            "heartbeat_seconds": 60,
            "ingest_limit_per_minute": agent.ingest_limit_per_minute or defaults.get("ingest_limit_per_minute"),
        },
    }


# ==============================================================================
# Agent-Updates
# ==============================================================================
class UpdateConfigRequest(BaseModel):
    mode: Optional[str] = Field(default=None, pattern="^(manual|auto|off)$")
    window_days: Optional[List[int]] = None
    window_start: Optional[str] = Field(default=None, max_length=5)
    window_end: Optional[str] = Field(default=None, max_length=5)
    timezone: Optional[str] = Field(default=None, max_length=60)
    max_parallel: Optional[int] = Field(default=None, ge=1, le=100)
    pause_after_failures: Optional[int] = Field(default=None, ge=0, le=50)
    paused: Optional[bool] = None


class UpdateRequestBody(BaseModel):
    agent_ids: List[int] = Field(default_factory=list, max_length=5000)
    all_outdated: bool = False


class PolicyRequest(BaseModel):
    policy: Optional[str] = Field(default=None, pattern="^(manual|auto|never)$")


class ReportRequest(BaseModel):
    hostname: str = Field(..., min_length=1, max_length=255)
    state: str = Field(..., pattern="^(downloading|installing|done|failed|rolled_back)$")
    version: Optional[str] = Field(default=None, max_length=40)
    message: str = Field(default="", max_length=2000)


class DeviceDefaults(BaseModel):
    retention_days: Optional[int] = Field(default=None, ge=1, le=3650)
    retention_max_logs: Optional[int] = Field(default=None, ge=1000, le=100_000_000)
    ingest_limit_per_minute: Optional[int] = Field(default=None, ge=10, le=1_000_000)


@router.get("/updates")
async def updates_overview(db: AsyncSession = Depends(get_db), _=Depends(get_current_admin)):
    """Stand der Agent-Verteilung: Pakete, Regel, Geraete."""
    overview = await agentupdate.overview(db)
    config = overview["config"]
    hosts = (await db.execute(select(Agent).where(
        Agent.parent_id.is_(None), Agent.device_type.in_(("linux_agent", "windows_agent")))
        .order_by(Agent.hostname))).scalars().all()
    cutoff = await _offline_cutoff(db)
    items = []
    for agent in hosts:
        target = overview["packages"].get(agentupdate.os_of(agent) or "") or {}
        extra = agent.extra_data or {}
        items.append({
            "id": agent.id, "hostname": agent.hostname, "device_type": agent.device_type,
            "ip_address": agent.ip_address,
            "version": agent.agent_version, "target_version": target.get("version"),
            "outdated": bool(target.get("version") and agentupdate.parse_version(agent.agent_version)
                             < agentupdate.parse_version(target.get("version"))),
            "self_update": agentupdate.supports_update(agent),
            "remote_update": (extra.get("agent") or {}).get("remote_update", True),
            "policy": agent.update_policy, "effective_policy": agentupdate.effective_policy(agent, config),
            "requested": bool(agent.update_requested_at),
            "state": agent.update_state or {},
            "is_online": bool(agent.last_seen and agent.last_seen >= cutoff),
            "decommissioned": bool(extra.get("decommissioned")),
        })
    overview["items"] = items
    return overview


@router.put("/updates/config")
async def updates_config(data: UpdateConfigRequest, request: Request, db: AsyncSession = Depends(get_db),
                         admin=Depends(get_current_admin)):
    try:
        config = await agentupdate.save_config(db, data.model_dump(exclude_none=True))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    mode_label = {"manual": "manuell", "auto": "automatisch im Wartungsfenster", "off": "aus"}[config["mode"]]
    await journal.record(db, category="agent_update", event="agent.update.config", level="notice",
                         message=(f"Agent-Updates: {mode_label}, Fenster {config['window_start']}–"
                                  f"{config['window_end']} ({config['timezone']})."),
                         actor=admin.username, source_ip=real_client_ip(request), detail=config)
    return config


@router.post("/updates/request")
async def updates_request(data: UpdateRequestBody, request: Request, db: AsyncSession = Depends(get_db),
                          admin=Depends(get_current_admin)):
    """"Jetzt aktualisieren" - fuer ausgewaehlte Geraete oder alle veralteten."""
    query = select(Agent).where(Agent.parent_id.is_(None),
                                Agent.device_type.in_(("linux_agent", "windows_agent")))
    if not data.all_outdated:
        if not data.agent_ids:
            raise HTTPException(status_code=400, detail="Keine Geräte ausgewählt.")
        query = query.where(Agent.id.in_(data.agent_ids))
    marked = []
    skipped = []
    for agent in (await db.execute(query)).scalars().all():
        target = await agentupdate.package(db, agentupdate.os_of(agent) or "")
        if not agentupdate.supports_update(agent):
            skipped.append({"hostname": agent.hostname, "reason": "Agent-Fassung ohne Selbst-Update - "
                                                                   "einmal neu installieren."})
            continue
        if target and agentupdate.parse_version(agent.agent_version) >= agentupdate.parse_version(target["version"]):
            if data.all_outdated:
                continue
            skipped.append({"hostname": agent.hostname, "reason": "Bereits aktuell."})
            continue
        agent.update_requested_at = datetime.utcnow()
        state = dict(agent.update_state or {})
        if state.get("state") == "failed":
            state["state"] = "pending"
        state["requested_by"] = admin.username
        agent.update_state = state
        marked.append(agent.hostname)
    await db.commit()
    if marked:
        await journal.record(db, category="agent_update", event="agent.update.requested", level="notice",
                             message=f"Agent-Update angestoßen für {len(marked)} Gerät(e).",
                             actor=admin.username, source_ip=real_client_ip(request),
                             detail={"hosts": marked[:200]})
    return {"requested": marked, "skipped": skipped,
            "message": (f"{len(marked)} Gerät(e) aktualisieren sich beim nächsten Lebenszeichen "
                        f"(spätestens in einer Minute).")}


@router.post("/updates/cancel")
async def updates_cancel(data: UpdateRequestBody, db: AsyncSession = Depends(get_db),
                         _=Depends(get_current_admin)):
    rows = (await db.execute(select(Agent).where(Agent.id.in_(data.agent_ids or [0])))).scalars().all()
    for agent in rows:
        agent.update_requested_at = None
    await db.commit()
    return {"cancelled": len(rows)}


@router.put("/{agent_id:int}/update-policy")
async def update_policy(agent_id: int, data: PolicyRequest, db: AsyncSession = Depends(get_db),
                        _=Depends(get_current_admin)):
    agent = await db.get(Agent, agent_id)
    if not agent or agent.parent_id:
        raise HTTPException(status_code=404, detail="Gerät nicht gefunden")
    agent.update_policy = data.policy
    await db.commit()
    return {"agent_id": agent_id, "policy": agent.update_policy}


@router.get("/update/pubkey")
async def update_pubkey(db: AsyncSession = Depends(get_db)):
    """Oeffentlicher Schluessel, mit dem Agent-Updates unterschrieben sind (oeffentlich)."""
    _, key = await agentupdate.signing_keys(db)
    return key


@router.get("/update/package/{os_name}")
@limiter.limit("30/minute")
async def update_package(os_name: str, request: Request, authorization: str = Header(None),
                         db: AsyncSession = Depends(get_db)):
    """Das Update-Paket - nur mit gueltigem Agent-Schluessel."""
    from starlette.responses import Response as _Response
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer Token erforderlich")
    token, _ = await tokens.resolve(db, authorization[7:], real_client_ip(request))
    if not token or (token.kind or "agent") == "enroll":
        raise HTTPException(status_code=401, detail="Ungültiger Agent-Token")
    pkg = await agentupdate.package(db, os_name)
    if not pkg:
        raise HTTPException(status_code=404, detail="Kein Paket für dieses Betriebssystem.")
    return _Response(content=pkg["content"], media_type="application/octet-stream", headers={
        "X-LogBot-Version": pkg["version"], "X-LogBot-SHA256": pkg["sha256"],
        "X-LogBot-Signature": pkg["signature"], "Cache-Control": "no-store"})


@router.post("/update/report")
@limiter.limit("30/minute")
async def update_report(data: ReportRequest, request: Request, authorization: str = Header(None),
                        db: AsyncSession = Depends(get_db)):
    """Der Agent berichtet, wie es laeuft."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer Token erforderlich")
    source_ip = real_client_ip(request)
    token, _ = await tokens.resolve(db, authorization[7:], source_ip)
    if not token:
        raise HTTPException(status_code=401, detail="Ungültiger Agent-Token")
    agent = None
    if token.agent_id:
        agent = await db.get(Agent, token.agent_id)
    if agent is None and (token.kind or "") == "global":
        agent = (await db.execute(select(Agent).where(Agent.hostname == data.hostname,
                                                      Agent.parent_id.is_(None)))).scalars().first()
    if agent is None or agent.hostname != data.hostname:
        raise HTTPException(status_code=404, detail="Gerät unbekannt")
    state = dict(agent.update_state or {})
    state.update({"state": "done" if data.state == "done" else
                  ("failed" if data.state in ("failed", "rolled_back") else data.state),
                  "reported": data.state, "message": data.message[:500],
                  "reported_at": datetime.utcnow().isoformat()})
    if data.version:
        state["version"] = data.version
    agent.update_state = state
    if data.state in ("failed", "rolled_back", "done"):
        agent.update_requested_at = None
    await db.commit()

    if data.state in ("failed", "rolled_back"):
        await journal.record(db, category="agent_update", event="agent.update.failed", level="error",
                             message=f"Agent-Update auf {agent.hostname} gescheitert: {data.message[:300]}",
                             actor="agent", source_ip=source_ip, target=agent.hostname, ok=False)
        config = await agentupdate.load_config(db)
        limit = int(config.get("pause_after_failures") or 0)
        if limit and config.get("mode") == "auto" and not config.get("paused") and data.version:
            if await agentupdate.failures_since(db, data.version) >= limit:
                await agentupdate.save_config(db, {"paused": True})
                config = await agentupdate.load_config(db)
                config["paused_reason"] = f"{limit} Fehlschläge mit Fassung {data.version}"
                from ..models import Setting as _Setting
                row = (await db.execute(select(_Setting).where(
                    _Setting.key == agentupdate.CONFIG_KEY))).scalar_one()
                row.value = config
                await db.commit()
                await journal.record(db, category="agent_update", event="agent.update.paused",
                                     level="critical",
                                     message=(f"Automatische Agent-Updates angehalten: {limit} Geräte "
                                              f"sind mit Fassung {data.version} gescheitert."),
                                     actor="system", ok=False)
    return {"ok": True}


@router.get("/defaults")
async def get_defaults(db: AsyncSession = Depends(get_db), _=Depends(get_current_admin)):
    return await agentinv.device_defaults(db)


@router.put("/defaults")
async def put_defaults(data: DeviceDefaults, request: Request, db: AsyncSession = Depends(get_db),
                       admin=Depends(get_current_admin)):
    """Vorgaben fuer alle Geraete ohne eigene Werte (auch selbst eingebundene)."""
    value = data.model_dump()
    row = (await db.execute(select(Setting).where(Setting.key == agentinv.DEFAULTS_KEY))).scalar_one_or_none()
    if row:
        row.value = value
    else:
        db.add(Setting(key=agentinv.DEFAULTS_KEY, value=value,
                       description="Vorgaben für Geräte: Aufbewahrung und Drossel"))
    await db.commit()
    await journal.record(db, category="settings", event="device.defaults.changed", level="notice",
                         message="Vorgaben für Geräte geändert (Aufbewahrung/Drossel).",
                         actor=admin.username, source_ip=real_client_ip(request), detail=value)
    return value
