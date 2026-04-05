# ==============================================================================
# Name:        Philipp Fischer
# Kontakt:     p.fischer@itconex.de
# Version:     2026.03.31.17.26.46
# Beschreibung: LogBot v2026.03.31.17.26.46 - Settings API Endpoints
# ==============================================================================

import asyncio
import platform
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, delete, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db, engine
from ..models import Setting, Log, User
from ..config import settings as app_settings
from ..schemas import SettingsResponse, SettingUpdate, RetentionResponse, DatabaseSettingsResponse
from ..auth import get_current_user, get_current_admin

router = APIRouter(prefix="/api/settings", tags=["Settings"])


def _choose_reboot_command():
    """Ermittelt ein geeignetes Reboot-Kommando je nach Plattform."""
    if platform.system().lower() == "windows":
        return ["shutdown", "/r", "/t", "0"]

    candidates = [
        ["systemctl", "reboot"],
        ["/bin/systemctl", "reboot"],
        ["nsenter", "-t", "1", "-m", "-u", "-i", "-n", "-p", "/sbin/reboot"],
        ["nsenter", "-t", "1", "-m", "-u", "-i", "-n", "-p", "/sbin/reboot", "-f"],
        ["reboot"],
        ["reboot", "-f"],
        ["/sbin/reboot"],
        ["/usr/sbin/reboot"],
        ["shutdown", "-r", "now"],
        ["/sbin/shutdown", "-r", "now"],
        ["/usr/sbin/shutdown", "-r", "now"],
        ["busybox", "reboot"],
        ["busybox", "reboot", "-f"],
        ["/bin/busybox", "reboot"],
        ["/bin/busybox", "reboot", "-f"],
    ]

    for cmd in candidates:
        exe = cmd[0]
        if shutil.which(exe) or Path(exe).exists():
            return cmd
    return None


def _try_sysrq_reboot() -> bool:
    """Versucht einen direkten SysRq-Reboot auszulösen. Gibt True bei Erfolg."""
    try:
        # sysrq einschalten (idempotent)
        Path("/proc/sys/kernel/sysrq").write_text("1")
        Path("/proc/sysrq-trigger").write_text("b")
        return True
    except Exception:
        return False

@router.get("", response_model=SettingsResponse)
async def get_settings(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(Setting))
    return SettingsResponse(settings={s.key: s.value for s in result.scalars().all()})

@router.get("/database", response_model=DatabaseSettingsResponse)
async def get_database_settings(_=Depends(get_current_admin)):
    return DatabaseSettingsResponse(
        host=app_settings.db_host,
        port=app_settings.db_port,
        user=app_settings.db_user,
        name=app_settings.db_name,
        password=app_settings.db_password or ""
    )

@router.get("/{key}")
async def get_setting(key: str, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()
    if not setting:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' nicht gefunden")
    return {"key": setting.key, "value": setting.value}

@router.put("/{key}")
async def update_setting(key: str, data: SettingUpdate, db: AsyncSession = Depends(get_db), _=Depends(get_current_admin)):
    result = await db.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = data.value
    else:
        setting = Setting(key=key, value=data.value)
        db.add(setting)
    await db.commit()
    await db.refresh(setting)
    return {"key": setting.key, "value": setting.value}

@router.post("/retention/preview", response_model=RetentionResponse)
async def preview_retention(days: int = Query(..., ge=1), db: AsyncSession = Depends(get_db), _=Depends(get_current_admin)):
    cutoff = datetime.utcnow() - timedelta(days=days)
    count = (await db.execute(select(func.count(Log.id)).where(Log.timestamp < cutoff))).scalar() or 0
    oldest = (await db.execute(select(func.min(Log.timestamp)))).scalar()
    return RetentionResponse(logs_to_delete=count, oldest_log_date=oldest)

@router.post("/retention/execute", response_model=RetentionResponse)
async def execute_retention(days: int = Query(..., ge=1), db: AsyncSession = Depends(get_db), _=Depends(get_current_admin)):
    cutoff = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(delete(Log).where(Log.timestamp < cutoff))
    await db.commit()
    return RetentionResponse(deleted_count=result.rowcount, message=f"{result.rowcount} Logs geloescht")

@router.delete("/logs/all", response_model=RetentionResponse)
async def delete_all_logs(
    confirm: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    """
    Loescht saemtliche Log-Eintraege via TRUNCATE und gibt Speicher sofort frei.
    Erfordert Bestaetigung "DELETE_ALL_LOGS".
    """
    if confirm != "DELETE_ALL_LOGS":
        raise HTTPException(status_code=400, detail="Bestaetigung fehlt oder ist falsch")

    total_logs = (await db.execute(select(func.count(Log.id)))).scalar() or 0

    # TRUNCATE innerhalb der laufenden Transaktion ausfuehren
    await db.execute(text("TRUNCATE TABLE logs RESTART IDENTITY"))
    await db.commit()

    return RetentionResponse(
        deleted_count=total_logs,
        message=f"{total_logs} Logs geloescht (TRUNCATE)" if total_logs else "Keine Logs vorhanden"
    )

@router.post("/logs/compact")
async def compact_logs(
    confirm: str = Query(..., min_length=1),
    _=Depends(get_current_admin),
):
    """
    Fuehrt VACUUM FULL + ANALYZE auf der Tabelle logs aus, um belegten Plattenplatz zurueckzugeben.
    Exklusiver Lock -> kurze Downtime fuer Schreib/Lesezugriffe.
    """
    if confirm != "COMPACT_LOGS":
        raise HTTPException(status_code=400, detail="Bestaetigung fehlt oder ist falsch")

    try:
        async with engine.connect() as conn:
            conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
            await conn.exec_driver_sql("VACUUM (FULL, ANALYZE) logs")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"VACUUM fehlgeschlagen: {exc}")

    return {"message": "VACUUM FULL logs abgeschlossen"}

@router.post("/reboot")
async def reboot_system(_=Depends(get_current_admin)):
    if _try_sysrq_reboot():
        return {"message": "SysRq-Reboot wurde ausgeloest", "method": "sysrq-trigger"}

    cmd = _choose_reboot_command()
    if not cmd:
        raise HTTPException(status_code=500, detail="Kein Neustart-Kommando gefunden")

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Reboot fehlgeschlagen: {exc}")

    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=2)
        if process.returncode not in (0, None):
            error_output = (stderr or stdout or b"").decode().strip()
            detail = error_output or f"Exit-Code: {process.returncode}"
            raise HTTPException(status_code=500, detail=f"Neustart-Kommando fehlgeschlagen: {detail}")
    except asyncio.TimeoutError:
        # Kommando laeuft noch (System faehrt vermutlich herunter) - trotzdem Erfolg melden
        pass

    return {"message": "Systemneustart wurde ausgeloest", "command": " ".join(cmd)}

