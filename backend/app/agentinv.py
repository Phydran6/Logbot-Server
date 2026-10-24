# ==============================================================================
# Name:        Phydran6
# Kontakt:     Phydran6
# Changelog:   ../../CHANGELOG/backend.md
# Beschreibung: LogBot - Geraete-Inventar: VM als Elternteil, Container als Kinder,
#               Drossel pro System
# ==============================================================================
"""
Eine VM und ihre Container.

Der Grundsatz: **die VM bleibt die Instanz** - mit ihrem Hostnamen, ihrer IP,
ihrem Schluessel. Laufen darauf Docker-Container, meldet der Linux-Agent sie
mit, und jeder Container wird eine eigene, lesbare Log-Instanz *unter* der VM:

    docker01                      <- die VM (Hostname, wie bisher)
    ├── compose: nextcloud        <- zusammengehoerige Container (Compose-Projekt)
    │   ├── docker01/nextcloud-app-1
    │   └── docker01/nextcloud-db-1
    └── docker01/portainer        <- einzelner Container

Technisch ist ein Container eine Zeile in `agents` mit `parent_id` = VM und
dem Hostnamen ``<vm>/<container>``. Der Schraegstrich macht ihn eindeutig
(zwei VMs duerfen beide einen Container "nginx" haben) und haelt die Ordnung:
wer nach "docker01" filtert, findet die VM und alles darunter.

Identitaet eines Containers ist sein **Name** auf dieser VM, nicht seine ID:
`docker compose up` erzeugt bei jeder Aenderung einen neuen Container mit
neuer ID, aber gleichem Namen - die Logs sollen dort weiterlaufen.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Agent, Setting

logger = logging.getLogger("logbot.agentinv")

CONTAINER_TYPE = "container"
DEFAULTS_KEY = "device_defaults"
MAX_CONTAINERS = 500


def child_hostname(host: str, container: str) -> str:
    return f"{host}/{container}"[:255]


def container_name(child: Agent) -> str:
    return ((child.extra_data or {}).get("container") or {}).get("name") \
        or child.hostname.split("/", 1)[-1]


async def device_defaults(db: AsyncSession) -> dict:
    row = (await db.execute(select(Setting).where(Setting.key == DEFAULTS_KEY))).scalar_one_or_none()
    value = row.value if row and isinstance(row.value, dict) else {}
    return {"retention_days": value.get("retention_days"),
            "retention_max_logs": value.get("retention_max_logs"),
            "ingest_limit_per_minute": value.get("ingest_limit_per_minute")}


async def children_of(db: AsyncSession, host: Agent) -> Dict[str, Agent]:
    rows = (await db.execute(select(Agent).where(Agent.parent_id == host.id))).scalars().all()
    return {container_name(row): row for row in rows}


async def child_for(db: AsyncSession, host: Agent, name: str,
                    cache: Optional[Dict[str, Agent]] = None, meta: Optional[dict] = None) -> Agent:
    """Die Kind-Instanz eines Containers - wird bei Bedarf angelegt."""
    if cache is not None and name in cache:
        return cache[name]
    hostname = child_hostname(host.hostname, name)
    child = (await db.execute(select(Agent).where(Agent.parent_id == host.id,
                                                  Agent.hostname == hostname))).scalars().first()
    if child is None:
        child = Agent(hostname=hostname, ip_address=host.ip_address, device_type=CONTAINER_TYPE,
                      parent_id=host.id, first_seen=datetime.utcnow(), last_seen=None,
                      extra_data={"container": {"name": name, **(meta or {})}})
        db.add(child)
        await db.flush()
    if cache is not None:
        cache[name] = child
    return child


async def sync_inventory(db: AsyncSession, host: Agent, docker: Optional[dict],
                         containers: List[dict]) -> dict:
    """Gleicht die gemeldeten Container mit den Kind-Instanzen ab.

    Was verschwunden ist, wird als "entfernt" markiert - die Logs bleiben, die
    Karte bleibt, bis jemand sie loescht. Ein Container, der wiederkommt,
    macht einfach dort weiter.
    """
    now = datetime.utcnow()
    extra = dict(host.extra_data or {})
    extra["docker"] = docker or {"installed": False}
    extra["docker_seen_at"] = now.isoformat()
    host.extra_data = extra

    existing = await children_of(db, host)
    seen = set()
    for item in containers[:MAX_CONTAINERS]:
        name = str(item.get("name") or "").strip().lstrip("/")[:200]
        if not name:
            continue
        seen.add(name)
        meta = {
            "name": name,
            "id": str(item.get("id") or "")[:64],
            "image": str(item.get("image") or "")[:255],
            "state": str(item.get("state") or "")[:30],
            "status": str(item.get("status") or "")[:120],
            "health": str(item.get("health") or "")[:30],
            "compose_project": str(item.get("compose_project") or "")[:120],
            "compose_service": str(item.get("compose_service") or "")[:120],
            "compose_dir": str(item.get("compose_dir") or "")[:300],
            "started_at": str(item.get("started_at") or "")[:40],
            "restart_count": int(item.get("restart_count") or 0),
            "log_driver": str(item.get("log_driver") or "")[:40],
            "logs_readable": bool(item.get("logs_readable", True)),
            "excluded": bool(item.get("excluded", False)),
            "ports": [str(p)[:40] for p in (item.get("ports") or [])][:20],
        }
        child = await child_for(db, host, name, existing, meta)
        child_extra = dict(child.extra_data or {})
        previous = dict(child_extra.get("container") or {})
        child_extra["container"] = {**previous, **meta}
        child_extra.pop("removed_at", None)
        child.extra_data = child_extra
        child.ip_address = host.ip_address
        if meta["state"] == "running":
            child.last_seen = now

    removed = 0
    for name, child in existing.items():
        if name in seen:
            continue
        child_extra = dict(child.extra_data or {})
        if not child_extra.get("removed_at"):
            child_extra["removed_at"] = now.isoformat()
            container = dict(child_extra.get("container") or {})
            container["state"] = "removed"
            child_extra["container"] = container
            child.extra_data = child_extra
            removed += 1
    return {"containers": len(seen), "removed": removed}


# =============================================================================
# Drossel: hoechstens N Logzeilen pro Minute je System (VM inkl. Container)
# =============================================================================
_buckets: Dict[int, Tuple[int, int]] = {}      # host_id -> (Minute, Anzahl)
_throttle_reported: Dict[int, float] = {}


def throttle(host_id: int, limit: Optional[int], wanted: int) -> int:
    """Wie viele der `wanted` Zeilen diese Minute noch durchduerfen."""
    if not limit or limit <= 0:
        return wanted
    minute = int(time.time() // 60)
    bucket_minute, used = _buckets.get(host_id, (minute, 0))
    if bucket_minute != minute:
        used = 0
    allowed = max(0, min(wanted, limit - used))
    _buckets[host_id] = (minute, used + allowed)
    return allowed


def should_report_throttle(host_id: int) -> bool:
    """Hoechstens einmal pro Stunde ins Tagebuch - sonst flutet die Drossel selbst."""
    now = time.time()
    if _throttle_reported.get(host_id, 0) > now - 3600:
        return False
    _throttle_reported[host_id] = now
    return True


def tree(agents: List[Agent], online_cutoff: datetime, log_counts: Optional[dict] = None) -> List[dict]:
    """VMs mit ihren Containern, Container nach Compose-Projekt gruppiert."""
    by_parent: Dict[int, List[Agent]] = {}
    hosts = []
    for agent in agents:
        if agent.parent_id:
            by_parent.setdefault(agent.parent_id, []).append(agent)
        else:
            hosts.append(agent)

    def node(agent: Agent) -> dict:
        extra = agent.extra_data or {}
        return {
            "id": agent.id, "hostname": agent.hostname, "ip_address": agent.ip_address,
            "device_type": agent.device_type, "parent_id": agent.parent_id,
            "last_seen": agent.last_seen.isoformat() if agent.last_seen else None,
            "is_online": bool(agent.last_seen and agent.last_seen >= online_cutoff),
            "agent_version": agent.agent_version,
            "log_count": (log_counts or {}).get(agent.id),
            "decommissioned": bool(extra.get("decommissioned")),
        }

    result = []
    for host in hosts:
        item = node(host)
        extra = host.extra_data or {}
        item["docker"] = extra.get("docker") or None
        projects: Dict[str, dict] = {}
        standalone = []
        for child in sorted(by_parent.get(host.id, []), key=lambda c: c.hostname):
            entry = node(child)
            container = (child.extra_data or {}).get("container") or {}
            entry.update({
                "name": container.get("name") or child.hostname.split("/", 1)[-1],
                "image": container.get("image"), "state": container.get("state"),
                "status": container.get("status"), "health": container.get("health"),
                "compose_service": container.get("compose_service"),
                "logs_readable": container.get("logs_readable", True),
                "excluded": container.get("excluded", False),
                "removed": bool((child.extra_data or {}).get("removed_at")),
            })
            project = container.get("compose_project")
            if project:
                group = projects.setdefault(project, {"name": project,
                                                      "dir": container.get("compose_dir"),
                                                      "containers": []})
                group["containers"].append(entry)
            else:
                standalone.append(entry)
        item["projects"] = sorted(projects.values(), key=lambda p: p["name"])
        item["standalone"] = standalone
        item["children_count"] = len(by_parent.get(host.id, []))
        result.append(item)
    return result
