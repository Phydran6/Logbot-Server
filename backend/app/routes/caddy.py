# ==============================================================================
# Name:        Phydran6
# Kontakt:     Phydran6
# Version:     2026.03.31.17.26.46
# Beschreibung: LogBot - Caddy Management API (Config Apply + Cert Upload)
# ==============================================================================

import logging
import socket
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_admin
from ..config import settings
from ..database import get_db, async_session
from ..models import Setting
from ..schemas import (
    CaddyApplyRequest,
    CaddyConfigResponse,
    CaddyTemplateRequest,
)

router = APIRouter(prefix="/api/caddy", tags=["Caddy"])
logger = logging.getLogger("logbot.caddy")

# Simple base template if nothing was stored yet
DEFAULT_CADDYFILE = """{
    admin 0.0.0.0:2019
}

:80 {
    handle /api/* {
        reverse_proxy backend:8000
    }
    handle {
        reverse_proxy frontend:80
    }
}
"""


def _build_template(domain: str, mode: str, letsencrypt_email: Optional[str]) -> str:
    domain = domain.strip() if domain else ""
    admin_block = "{\n    admin 0.0.0.0:2019\n}\n\n"

    if mode == "http":
        if domain:
            raise HTTPException(status_code=400, detail="HTTP ist nur ohne FQDN (per IP/:80) erlaubt.")
        host = ":80"
        site_block = (
            f"{host} {{\n"
            "    handle /api/* {\n"
            "        reverse_proxy backend:8000\n"
            "    }\n"
            "    handle {\n"
            "        reverse_proxy frontend:80\n"
            "    }\n"
            "}\n"
        )
        return admin_block + site_block

    # HTTPS modes require FQDN
    if not domain or "." not in domain:
        raise HTTPException(status_code=400, detail="FQDN erforderlich für HTTPS")

    # DNS-Check (Resolver/hosts) - Fail fast wenn nicht auflösbar
    try:
        socket.getaddrinfo(domain, None)
    except socket.gaierror:
        raise HTTPException(status_code=400, detail=f"FQDN '{domain}' ist nicht auflösbar (DNS)")

    redirect_block = f":80 {{\n    redir https://{domain}{{uri}}\n}}\n\n"

    if mode == "custom":
        tls_line = "    tls /etc/caddy/certs/custom.crt /etc/caddy/certs/custom.key"
    elif mode == "letsencrypt":
        if not letsencrypt_email:
            raise HTTPException(status_code=400, detail="E-Mail für Let's Encrypt erforderlich")
        tls_line = f"    tls {letsencrypt_email}"
    else:
        raise HTTPException(status_code=400, detail="Unbekannter Modus")

    site_block = (
        f"{domain} {{\n"
        f"{tls_line}\n"
        "    handle /api/* {\n"
        "        reverse_proxy backend:8000\n"
        "    }\n"
        "    handle {\n"
        "        reverse_proxy frontend:80\n"
        "    }\n"
        "}\n"
    )
    return admin_block + redirect_block + site_block


async def _save_setting(db: AsyncSession, key: str, value) -> None:
    result = await db.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = value
    else:
        setting = Setting(key=key, value=value)
        db.add(setting)
    await db.commit()


async def _apply_caddyfile(caddyfile: str) -> None:
    url = settings.caddy_admin_url.rstrip("/") + "/load"
    headers = {"Content-Type": "text/caddyfile"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, content=caddyfile.encode("utf-8"), headers=headers)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Caddy Admin API nicht erreichbar: {exc}") from exc

    if resp.status_code >= 400:
        # give back caddy error body
        raise HTTPException(status_code=resp.status_code, detail=resp.text or "Caddy-Fehler beim Laden")


async def _get_saved_caddyfile(db: AsyncSession) -> Optional[str]:
    result = await db.execute(select(Setting).where(Setting.key == "caddy_caddyfile"))
    setting = result.scalar_one_or_none()
    return setting.value if setting else None


@router.get("/config", response_model=CaddyConfigResponse)
async def get_caddy_config(db: AsyncSession = Depends(get_db), _=Depends(get_current_admin)):
    saved = await _get_saved_caddyfile(db)
    running_config = {}
    last_error = None
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(settings.caddy_admin_url.rstrip("/") + "/config")
            if resp.status_code < 400:
                running_config = resp.json()
            else:
                last_error = f"Caddy antwortet mit HTTP {resp.status_code}"
    except Exception as exc:  # broad: wir zeigen nur Status
        last_error = f"Caddy nicht erreichbar: {exc}"

    cert_dir = Path(settings.caddy_certs_dir)
    cert_present = (cert_dir / "custom.crt").exists() and (cert_dir / "custom.key").exists()

    return CaddyConfigResponse(
        running_config=running_config,
        saved_caddyfile=saved or DEFAULT_CADDYFILE,
        cert_present=cert_present,
        last_error=last_error,
    )


@router.post("/apply")
async def apply_caddy_config(
    data: CaddyApplyRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    caddyfile_raw = data.caddyfile.strip() if data.caddyfile else ""

    # Wenn ein Modus mitgeschickt wird, erzwinge eine passende Vorlage
    if data.mode:
        mode = data.mode
        if mode == "http":
            effective = _build_template("", "http", None)
        elif mode in ("letsencrypt", "custom"):
            if not data.domain:
                raise HTTPException(status_code=400, detail="FQDN ist für HTTPS erforderlich")
            effective = _build_template(data.domain, mode, data.letsencrypt_email)
        else:
            raise HTTPException(status_code=400, detail="Unbekannter Modus")
    else:
        effective = caddyfile_raw

    if not effective:
        raise HTTPException(status_code=400, detail="Caddyfile darf nicht leer sein")

    await _apply_caddyfile(effective)

    if data.save:
        await _save_setting(db, "caddy_caddyfile", effective)

    return {"message": "Caddy-Konfiguration geladen", "saved": data.save}


@router.post("/template")
async def build_caddy_template(
    req: CaddyTemplateRequest,
    _=Depends(get_current_admin),
):
    caddyfile = _build_template(req.domain, req.mode, req.letsencrypt_email)
    return {"caddyfile": caddyfile}


@router.post("/certificates")
async def upload_certificates(
    cert_file: UploadFile = File(...),
    key_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    cert_dir = Path(settings.caddy_certs_dir)
    cert_dir.mkdir(parents=True, exist_ok=True)

    cert_path = cert_dir / "custom.crt"
    key_path = cert_dir / "custom.key"

    cert_bytes = await cert_file.read()
    key_bytes = await key_file.read()

    if len(cert_bytes) < 32 or len(key_bytes) < 32:
        raise HTTPException(status_code=400, detail="Zertifikat/Key scheinen zu klein oder leer")

    cert_path.write_bytes(cert_bytes)
    key_path.write_bytes(key_bytes)

    await _save_setting(db, "caddy_cert_uploaded", True)

    return {"message": "Zertifikat gespeichert", "cert_path": str(cert_path), "key_path": str(key_path)}


async def ensure_caddy_config_on_startup(session_factory=None):
    """
    Laedt die gespeicherte Caddyfile beim App-Start.
    session_factory: optional dependency injection fuer Tests.
    """
    session_factory = session_factory or async_session
    saved: Optional[str] = None
    try:
        async with session_factory() as db:
            saved = await _get_saved_caddyfile(db)
    except Exception as exc:
        logger.warning("Caddy-Config konnte nicht geladen werden (DB): %s", exc)
        return

    if not saved:
        return

    try:
        await _apply_caddyfile(saved)
        logger.info("Gespeicherte Caddy-Konfiguration wurde beim Start angewendet.")
    except Exception as exc:
        logger.error("Caddy-Konfiguration beim Start fehlgeschlagen: %s", exc)
