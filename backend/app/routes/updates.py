# ==============================================================================
# Name:        Phydran6
# Kontakt:     Phydran6
# Version:     2026.08.14.12.00.00
# Changelog:   ../../../CHANGELOG/backend.md
# Beschreibung: LogBot - Patchmanagement: Stand pruefen, Update, Rueckfall
# ==============================================================================
"""
Endpunkte fuer den Bereich "Updates".

Alles hier ist Administratoren vorbehalten. Update und Rueckfall greifen tief
ins System ein, deshalb muss die Oberflaeche zusaetzlich ein Bestaetigungswort
mitschicken - ein versehentlicher Klick loest damit kein Update aus.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..auth import get_current_admin
from .. import updater

logger = logging.getLogger("logbot.updates")

router = APIRouter(prefix="/api/updates", tags=["Updates"])


class UpdateRequest(BaseModel):
    """Bestaetigung und Wunsch nach einem Datenbank-Abzug."""
    confirm: str = Field(..., description="Muss 'UPDATE' lauten")
    database_backup: bool = True


class RollbackRequest(BaseModel):
    """Bestaetigung und - optional - die gewuenschte Sicherung."""
    confirm: str = Field(..., description="Muss 'ROLLBACK' lauten")
    backup: str = ""


@router.get("/status")
async def get_status(force: bool = Query(False, description="GitHub erneut abfragen"),
                     _=Depends(get_current_admin)):
    """Installierter Stand, Stand auf GitHub, laufender Vorgang und Sicherungen."""
    return await updater.update_status(force=force)


@router.post("/check")
async def check_now(_=Depends(get_current_admin)):
    """Fragt GitHub sofort erneut ab (umgeht den Zwischenspeicher)."""
    return await updater.update_status(force=True)


@router.get("/log")
async def get_log(lines: int = Query(200, ge=10, le=2000), _=Depends(get_current_admin)):
    """Die letzten Zeilen des Wartungsprotokolls vom Host."""
    return {"lines": await updater.read_run_log(lines=lines)}


@router.post("/apply")
async def apply_update(data: UpdateRequest, _=Depends(get_current_admin)):
    """Spielt den Stand von GitHub ein.

    Der eigentliche Lauf passiert auf dem Host - dieser Aufruf kehrt sofort
    zurueck. Waehrend des Updates ist die Oberflaeche kurz nicht erreichbar.
    """
    if data.confirm != "UPDATE":
        raise HTTPException(status_code=400,
                            detail="Bestaetigung fehlt: 'confirm' muss 'UPDATE' lauten.")

    status = await updater.update_status()
    if not status["local"].get("host_access"):
        raise HTTPException(
            status_code=409,
            detail=("Kein Zugriff auf den Host. Das Update ueber die Oberflaeche braucht ein "
                    "Backend mit privileged/pid:host (Standard-docker-compose.yml). "
                    "Alternativ per Kommandozeile: " + status["oneliner"]),
        )

    result = await updater.start_run("apply", database_backup=data.database_backup)
    if not result.get("started"):
        raise HTTPException(status_code=409, detail=result.get("error", "Start fehlgeschlagen"))
    logger.warning("Update ueber die Oberflaeche gestartet (Datenbank-Abzug: %s)",
                   data.database_backup)
    return result


@router.post("/rollback")
async def rollback(data: RollbackRequest, _=Depends(get_current_admin)):
    """Faehrt auf eine vorherige Sicherung zurueck."""
    if data.confirm != "ROLLBACK":
        raise HTTPException(status_code=400,
                            detail="Bestaetigung fehlt: 'confirm' muss 'ROLLBACK' lauten.")

    backups = await updater.list_backups()
    if not backups:
        raise HTTPException(status_code=404,
                            detail="Es gibt keine Sicherung, auf die zurueckgefallen werden koennte.")
    if data.backup and data.backup not in [b["name"] for b in backups]:
        raise HTTPException(status_code=404, detail=f"Sicherung '{data.backup}' gibt es nicht.")

    result = await updater.start_run("rollback", backup_name=data.backup)
    if not result.get("started"):
        raise HTTPException(status_code=409, detail=result.get("error", "Start fehlgeschlagen"))
    logger.warning("Rueckfall ueber die Oberflaeche gestartet (Sicherung: %s)",
                   data.backup or "neueste")
    return result
