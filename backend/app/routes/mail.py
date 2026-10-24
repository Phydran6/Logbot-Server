# ==============================================================================
# Name:        Phydran6
# Kontakt:     Phydran6
# Version:     2026.10.22.23.00.00
# Changelog:   ../../../CHANGELOG/backend.md
# Beschreibung: LogBot - Endpunkte fuer den Mailversand und die Mail-Assistenten
# ==============================================================================
"""
Meldungen → Kanäle → E-Mail. Nur fuer Administratoren - hier stehen Zugangsdaten.

Neben der klassischen Einstellung (SMTP, Postfix) gibt es hier die Schritte der
Assistenten: Google- und Microsoft-Anmeldung per OAuth, der Geraetecode fuer
Microsoft und das automatische Anlegen der App-Registrierung in Microsoft 365
(app/mailoauth.py erklaert die Ablaeufe).
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from .. import journal, mail, mailoauth, publicurl
from ..auth import get_current_admin
from ..database import get_db
from ..limiter import client_ip as real_client_ip, limiter

logger = logging.getLogger("logbot.routes.mail")

router = APIRouter(prefix="/api/mail", tags=["Mail"])


class ConfigRequest(BaseModel):
    mode: Optional[str] = Field(default=None, description="off | google | microsoft | relay | container")
    from_address: Optional[str] = Field(default=None, max_length=254)
    from_name: Optional[str] = Field(default=None, max_length=100)
    preset: Optional[str] = Field(default=None, max_length=30)
    smtp_host: Optional[str] = Field(default=None, max_length=253)
    smtp_port: Optional[int] = Field(default=None, ge=1, le=65535)
    smtp_user: Optional[str] = Field(default=None, max_length=254)
    smtp_password: Optional[str] = Field(default=None, max_length=500,
                                         description="Leer = bestehendes Passwort behalten")
    clear_smtp_password: bool = False
    encryption: Optional[str] = Field(default=None, description="none | starttls | tls")
    verify_certificate: Optional[bool] = None
    myhostname: Optional[str] = Field(default=None, max_length=253)
    relay_host: Optional[str] = Field(default=None, max_length=253)
    relay_port: Optional[int] = Field(default=None, ge=1, le=65535)
    relay_user: Optional[str] = Field(default=None, max_length=254)
    relay_password: Optional[str] = Field(default=None, max_length=500)
    clear_relay_password: bool = False
    default_recipients: Optional[List[str]] = None


class TestRequest(BaseModel):
    recipient: str = Field(default="", max_length=254, description="Leer = die hinterlegten Empfänger")


class PublicUrlRequest(BaseModel):
    public_url: str = Field(..., max_length=300)


class GoogleStart(BaseModel):
    client_id: str = Field(..., min_length=10, max_length=200)
    client_secret: str = Field(default="", max_length=200)
    return_mode: str = Field(default="auto", pattern="^(auto|paste)$")


class MicrosoftStart(BaseModel):
    client_id: str = Field(default="", max_length=100, description="Leer = die vom Assistenten angelegte App")
    tenant: str = Field(default="", max_length=100)
    account_type: str = Field(default="work", pattern="^(work|personal)$")
    method: str = Field(default="device", pattern="^(device|browser)$")
    return_mode: str = Field(default="paste", pattern="^(auto|paste)$")


class RegisterStart(BaseModel):
    method: str = Field(default="device", pattern="^(device|browser)$")
    personal_accounts: bool = False


class FlowRequest(BaseModel):
    flow_id: str = Field(..., min_length=10, max_length=100)
    pasted: str = Field(default="", max_length=4000)


# =============================================================================
# Einstellung
# =============================================================================
@router.get("/config")
async def get_config(db: AsyncSession = Depends(get_db), _=Depends(get_current_admin)):
    """Aktuelle Einstellung — ohne Passwörter und Token."""
    config = await mail.load_config(db)
    return {
        "config": mail.public_config(config),
        "public_url": await publicurl.get(db),
        "modes": [{"id": key, **value} for key, value in mail.MODES.items()],
        "presets": mail.SMTP_PRESETS,
        "encryptions": [{"id": key, "label": label} for key, label in mail.ENCRYPTIONS.items()],
        "google_loopback": mailoauth.GOOGLE_LOOPBACK,
        "microsoft_loopback": mailoauth.MS_LOOPBACK,
    }


@router.put("/config")
async def put_config(data: ConfigRequest, request: Request, db: AsyncSession = Depends(get_db),
                     admin=Depends(get_current_admin)):
    """Speichert die Einstellung (und schreibt bei Postfix die Datei neu)."""
    try:
        result = await mail.save_config(db, data.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await journal.record(db, category="mail", event="mail.config.changed",
                         message=f"Mailversand eingestellt: {mail.MODES[result['mode']]['label']}.",
                         actor=admin.username, source_ip=real_client_ip(request))
    return {"config": result}


@router.put("/public-url")
async def put_public_url(data: PublicUrlRequest, request: Request,
                         db: AsyncSession = Depends(get_db), admin=Depends(get_current_admin)):
    """Die Adresse, die in Mails als Link steht (Passwort-Reset, Bestätigung, App)."""
    try:
        value = await publicurl.put(db, data.public_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await journal.record(db, category="settings", event="public_url.changed",
                         message=f"Öffentliche Adresse gesetzt: {value or '(leer)'}",
                         actor=admin.username, source_ip=real_client_ip(request), target=value)
    return {"public_url": value}


@router.get("/preview")
async def preview(db: AsyncSession = Depends(get_db), _=Depends(get_current_admin)):
    """Was steht in der Postfix-Datei? (Passwörter sind darin ersetzt.)"""
    config = await mail.load_config(db)
    rendered = mail.render_postfix_env(config)
    secret = mail.secretbox.open_(config.get("relay_password") or "")
    if secret:
        rendered = rendered.replace(secret, "********")
    return {"path": mail.POSTFIX_ENV_RELATIVE, "content": rendered, "applies_to": "container",
            "note": "Diese Datei schreibt LogBot bei jedem Speichern neu."}


@router.post("/test")
async def test(data: TestRequest, request: Request, db: AsyncSession = Depends(get_db),
               admin=Depends(get_current_admin)):
    """Verschickt eine Probemail."""
    config = await mail.load_config(db)
    try:
        result = await mail.send_test(config, data.recipient or admin.email or "")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (RuntimeError, mailoauth.OAuthError) as exc:
        await journal.record(db, category="mail", event="mail.test.failed", level="warning",
                             message=f"Probemail fehlgeschlagen: {exc}", actor=admin.username,
                             source_ip=real_client_ip(request), ok=False)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    await journal.record(db, category="mail", event="mail.test.ok",
                         message=f"Probemail an {', '.join(result['recipients'])} verschickt.",
                         actor=admin.username, source_ip=real_client_ip(request))
    return result


# =============================================================================
# Assistenten: Anmeldung per OAuth
# =============================================================================
async def _callback_url(db: AsyncSession, return_mode: str) -> str:
    """Rueckweg in den Server - nur mit oeffentlicher HTTPS-Adresse moeglich."""
    if return_mode != "auto":
        return ""
    base = await publicurl.get(db)
    return f"{base}/api/mail/oauth/callback" if base.startswith("https://") else ""


@router.post("/oauth/google/start")
async def google_start(data: GoogleStart, db: AsyncSession = Depends(get_db),
                       admin=Depends(get_current_admin)):
    try:
        return mailoauth.start_authorize(
            provider="google", user_id=admin.id, client_id=data.client_id,
            client_secret=data.client_secret.strip(),
            callback_url=await _callback_url(db, data.return_mode))
    except mailoauth.OAuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/oauth/microsoft/start")
async def microsoft_start(data: MicrosoftStart, db: AsyncSession = Depends(get_db),
                          admin=Depends(get_current_admin)):
    config = await mail.load_config(db)
    app = config.get("ms_app") or {}
    client_id = data.client_id.strip() or app.get("app_id", "")
    if not client_id:
        raise HTTPException(status_code=400,
                            detail="Es fehlt die Anwendungs-ID - zuerst die App-Registrierung "
                                   "anlegen lassen oder eine vorhandene eintragen.")
    if data.account_type == "personal":
        tenant = "consumers"
    else:
        tenant = data.tenant.strip() or (app.get("tenant_id") if app.get("app_id") == client_id else "") \
            or "organizations"
    try:
        if data.method == "device":
            return await mailoauth.start_device(
                user_id=admin.id, client_id=client_id, tenant=tenant,
                scopes=mailoauth.MS_MAIL_SCOPES, purpose="mailbox", retries=8)
        return mailoauth.start_authorize(
            provider="microsoft", user_id=admin.id, client_id=client_id, tenant=tenant,
            callback_url=await _callback_url(db, data.return_mode))
    except mailoauth.OAuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/oauth/microsoft/register/start")
async def register_start(data: RegisterStart, admin=Depends(get_current_admin)):
    """Schritt 1 der automatischen App-Registrierung: Administrator anmelden."""
    try:
        if data.method == "device":
            result = await mailoauth.start_device(
                user_id=admin.id, client_id=mailoauth.MS_GRAPH_CLI_CLIENT, tenant="organizations",
                scopes=mailoauth.MS_ADMIN_SCOPES, purpose="register")
        else:
            result = mailoauth.start_register_authorize(user_id=admin.id)
    except mailoauth.OAuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    mailoauth.flows.get(result["flow_id"])["personal_accounts"] = data.personal_accounts
    return result


async def _store_mailbox(db: AsyncSession, flow: dict, result: dict, admin, request) -> dict:
    config_public = await mail.save_oauth(db, flow["provider"], result, activate=True)
    await journal.record(
        db, category="mail", event="mail.oauth.connected", level="notice",
        message=f"Mailversand über {mail.MODES[flow['provider']]['label']} eingerichtet "
                f"(Absender {result.get('account')}).",
        actor=getattr(admin, "username", "admin"),
        source_ip=real_client_ip(request) if request else "",
        target=result.get("account") or "")
    return {"status": "connected", "account": result.get("account"), "config": config_public}


async def _do_register(db: AsyncSession, flow: dict, tokens: dict, admin, request) -> dict:
    callback = await _callback_url(db, "auto")
    report = await mailoauth.register_app(tokens["access_token"],
                                          personal_accounts=bool(flow.get("personal_accounts")),
                                          callback_url=callback)
    config = await mail.load_config(db)
    config["ms_app"] = {k: report[k] for k in ("app_id", "object_id", "tenant_id", "tenant_name",
                                              "display_name", "personal_accounts",
                                              "consent_granted", "registered_by")}
    await mail._store(db, config)
    await journal.record(
        db, category="mail", event="mail.ms_app.registered", level="warning",
        message=(f"App-Registrierung „{report['display_name']}“ im Mandanten "
                 f"„{report['tenant_name']}“ angelegt (von {report['registered_by']})."),
        actor=admin.username, source_ip=real_client_ip(request), target=report["app_id"],
        detail={"steps": report["steps"]})
    return {"status": "registered", **report}


@router.post("/oauth/poll")
async def poll(data: FlowRequest, request: Request, db: AsyncSession = Depends(get_db),
               admin=Depends(get_current_admin)):
    """Geraetecode: ist die Anmeldung erledigt?"""
    try:
        flow = mailoauth.flows.get(data.flow_id, admin.id)
        if flow.get("kind") != "device":
            raise mailoauth.OAuthError("Dieser Vorgang wird nicht per Gerätecode abgeschlossen.")
        tokens = await mailoauth.poll_device(flow)
        if tokens is None:
            return {"status": "pending"}
        mailoauth.flows.drop(data.flow_id)
        if flow["purpose"] == "register":
            return await _do_register(db, flow, tokens, admin, request)
        result = await mailoauth.finish_mailbox_device(flow, tokens)
        return await _store_mailbox(db, flow, result, admin, request)
    except mailoauth.OAuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/oauth/complete")
async def complete(data: FlowRequest, request: Request, db: AsyncSession = Depends(get_db),
                   admin=Depends(get_current_admin)):
    """Browserweg: die zurueckkopierte Adresse einloesen."""
    try:
        flow = mailoauth.flows.get(data.flow_id, admin.id)
        code, state = mailoauth.parse_pasted(data.pasted)
        if flow["kind"] == "register_authorize":
            tokens = await mailoauth.admin_token_from_code(flow, code, state)
            mailoauth.flows.drop(data.flow_id)
            return await _do_register(db, flow, tokens, admin, request)
        if flow["kind"] != "authorize":
            raise mailoauth.OAuthError("Dieser Vorgang wird per Gerätecode abgeschlossen.")
        result = await mailoauth.complete_authorize(flow, code, state)
        mailoauth.flows.drop(data.flow_id)
        return await _store_mailbox(db, flow, result, admin, request)
    except mailoauth.OAuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/oauth/callback", include_in_schema=False)
@limiter.limit("20/minute")
async def callback(request: Request, code: str = Query(""), state: str = Query(""),
                   error: str = Query(""), error_description: str = Query(""),
                   db: AsyncSession = Depends(get_db)):
    """Rueckweg vom Anbieter (nur mit oeffentlicher HTTPS-Adresse).

    Ohne Anmeldung erreichbar - der Browser kommt vom Anbieter zurueck und
    bringt keinen Zugangstoken mit. Ausweis ist der `state`: unratbar, an den
    Vorgang eines Administrators gebunden und nur einmal gueltig.
    """
    target = "/notifications/mail"
    try:
        flow_id, flow = mailoauth.flows.by_state(state)
    except mailoauth.OAuthError:
        return RedirectResponse(f"{target}?oauth=expired", status_code=303)
    mailoauth.flows.drop(flow_id)
    if error or not code:
        logger.warning("OAuth-Rückweg mit Fehler: %s %s", error, error_description[:200])
        return RedirectResponse(f"{target}?oauth=denied", status_code=303)
    try:
        result = await mailoauth.complete_authorize(flow, code, state)

        class _Actor:
            username = f"user#{flow.get('user_id')}"
        await _store_mailbox(db, flow, result, _Actor(), request)
    except mailoauth.OAuthError as exc:
        logger.warning("OAuth-Rückweg fehlgeschlagen: %s", exc)
        return RedirectResponse(f"{target}?oauth=failed", status_code=303)
    return RedirectResponse(f"{target}?oauth=connected", status_code=303)


@router.post("/oauth/disconnect")
async def disconnect(request: Request, db: AsyncSession = Depends(get_db),
                     admin=Depends(get_current_admin)):
    result = await mail.disconnect_oauth(db)
    await journal.record(db, category="mail", event="mail.oauth.disconnected", level="notice",
                         message="Anmeldung beim Mail-Anbieter entfernt.",
                         actor=admin.username, source_ip=real_client_ip(request))
    return {"config": result}
