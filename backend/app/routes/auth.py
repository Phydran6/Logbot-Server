# ==============================================================================
# Name:        Phydran6
# Kontakt:     Phydran6
# Version:     2026.10.22.23.00.00
# Beschreibung: LogBot - Auth API Endpoints + App-Login (QR-Code) + MFA-Login
# ==============================================================================

import io
import json
import base64
import hashlib
import logging
import secrets
from datetime import datetime, timedelta
from typing import Union
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
import qrcode

from ..database import get_db
from ..limiter import limiter
from ..models import User, AppLoginToken
from ..schemas import (
    Token,
    UserResponse,
    AppTokenResponse,
    AppTokenExchangeRequest,
    AppQRResponse,
    LoginMFARequired,
    MFALoginRequest,
    check_email,
    check_password_strength,
)
from .. import journal, ldap_auth
from ..limiter import client_ip as real_client_ip
from ..auth import (
    burn_password_check,
    find_user_by_login,
    verify_password,
    get_password_hash,
    create_access_token,
    create_mfa_pending_token,
    decode_mfa_pending_token,
    is_user_mfa_locked,
    register_mfa_failure,
    clear_mfa_failures,
    get_current_user,
    MFA_PENDING_TOKEN_MINUTES,
)
from ..config import settings
from .mfa import consume_totp_or_backup

router = APIRouter(prefix="/api/auth", tags=["Auth"])

_APP_TOKEN_TTL_MINUTES = 15


async def _login_via_ldap(db: AsyncSession, username: str, password: str):
    """Anmeldung am Verzeichnis; legt den Benutzer bei Bedarf an. None = kein Zugang.

    Ein bereits vorhandenes **lokales** Konto gleichen Namens wird nicht
    übernommen: sonst könnte ein gleichnamiges Verzeichniskonto das lokale
    Admin-Konto kapern. Solche Fälle müssen die Admins selbst auflösen.
    """
    config = await ldap_auth.load_config(db)
    if not config.get("enabled"):
        return None

    ok, details = await ldap_auth.authenticate(config, username, password)
    if not ok:
        return None

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if user:
        if (user.auth_source or "local") != "ldap":
            logging.getLogger("logbot.ldap").warning(
                "LDAP-Anmeldung für '%s' abgelehnt: es gibt bereits ein lokales Konto mit diesem Namen",
                username,
            )
            return None
        # Stammdaten bei jeder Anmeldung nachziehen - Gruppenwechsel wirken sofort.
        user.role = details.get("role", "user")
        if details.get("email"):
            user.email = details["email"]
    else:
        if not config.get("auto_create_users", True):
            return None
        user = User(
            username=username,
            email=details.get("email"),
            # Unbrauchbarer Hash: Anmeldung ist nur über das Verzeichnis möglich.
            password_hash=get_password_hash(secrets.token_urlsafe(32)),
            role=details.get("role", "user"),
            is_active=True,
            auth_source="ldap",
        )
        db.add(user)

    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=None)
@limiter.limit("10/minute")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> Union[Token, LoginMFARequired]:
    # Benutzername ODER E-Mail-Adresse. Gibt es das Konto nicht, wird trotzdem
    # ein Passwort-Hash geprueft - sonst verriete die kuerzere Antwortzeit,
    # welche Namen es gibt.
    user = await find_user_by_login(db, form_data.username)
    if user is None:
        burn_password_check()

    if not user or not verify_password(form_data.password, user.password_hash):
        # Zweiter Versuch über das Verzeichnis, falls eingerichtet.
        user = await _login_via_ldap(db, form_data.username, form_data.password)

    source_ip = real_client_ip(request)

    # Gleiche Fehlermeldung für "User existiert nicht" und "Passwort falsch"
    # verhindert User-Enumeration
    if not user:
        # Ins Systemtagebuch gehoert der Fehlversuch trotzdem: dort faellt eine
        # Reihe von Versuchen aus demselben Netz sofort auf.
        await journal.record(
            db, category="auth", event="login.failed", level="warning",
            message=f"Fehlgeschlagene Anmeldung für '{form_data.username}'.",
            actor=form_data.username, source_ip=source_ip, ok=False)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Falsche Anmeldedaten")
    if not user.is_active:
        await journal.record(
            db, category="auth", event="login.disabled", level="warning",
            message=f"Anmeldung abgelehnt: '{user.username}' ist deaktiviert.",
            actor=user.username, source_ip=source_ip, ok=False)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Benutzer deaktiviert")

    # MFA aktiv → kein Vollzugriffs-Token, sondern Pending-Token zurückgeben
    if user.mfa_enabled:
        if is_user_mfa_locked(user):
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"MFA gesperrt bis {user.mfa_locked_until.isoformat()}Z",
            )
        return LoginMFARequired(
            mfa_token=create_mfa_pending_token(user.username),
            expires_in_seconds=MFA_PENDING_TOKEN_MINUTES * 60,
        )

    await journal.record(
        db, category="auth", event="login.ok",
        message=f"'{user.username}' hat sich angemeldet.",
        actor=user.username, source_ip=source_ip,
        detail={"role": user.role, "source": user.auth_source or "local", "mfa": False})
    return Token(access_token=create_access_token(data={"sub": user.username}))


@router.post("/login/mfa", response_model=Token)
@limiter.limit("10/minute")
async def login_mfa(
    request: Request,
    data: MFALoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Zweiter Login-Schritt: Pending-Token + TOTP/Backup-Code → Access-Token."""
    username = decode_mfa_pending_token(data.mfa_token)
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user or not user.is_active or not user.mfa_enabled:
        raise HTTPException(status_code=401, detail="MFA-Token ungültig")

    if is_user_mfa_locked(user):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"MFA gesperrt bis {user.mfa_locked_until.isoformat()}Z",
        )

    if not await consume_totp_or_backup(db, user, data.code):
        register_mfa_failure(user)
        await db.commit()
        await journal.record(
            db, category="auth", event="mfa.failed", level="warning",
            message=f"Falscher Zweitfaktor für '{user.username}'.",
            actor=user.username, source_ip=real_client_ip(request), ok=False)
        raise HTTPException(status_code=401, detail="Code ungültig")

    clear_mfa_failures(user)
    await db.commit()
    await journal.record(
        db, category="auth", event="login.ok",
        message=f"'{user.username}' hat sich angemeldet (mit Zweitfaktor).",
        actor=user.username, source_ip=real_client_ip(request),
        detail={"role": user.role, "mfa": True})
    return Token(access_token=create_access_token(data={"sub": user.username}))


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


# =============================================================================
# App-Authentifizierung (Android App via URL oder QR-Code)
# =============================================================================

@router.post("/app-token", response_model=AppTokenResponse)
async def create_app_token(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Erstellt einen kurzlebigen Einmal-Token (15 min) für die App-Authentifizierung.
    Alle noch nicht verwendeten alten Tokens des Users werden dabei invalidiert.
    """
    # Alte, ungenutzte Tokens für diesen User löschen
    await db.execute(
        delete(AppLoginToken).where(
            AppLoginToken.user_id == current_user.id,
            AppLoginToken.used_at == None,  # noqa: E711
        )
    )

    token = secrets.token_hex(32)  # 64 Hex-Zeichen = 256 bit Entropie
    expires_at = datetime.utcnow() + timedelta(minutes=_APP_TOKEN_TTL_MINUTES)

    app_token = AppLoginToken(
        user_id=current_user.id,
        token=token,
        expires_at=expires_at,
    )
    db.add(app_token)
    await db.commit()

    return AppTokenResponse(
        token=token,
        expires_at=expires_at,
        expires_in_seconds=_APP_TOKEN_TTL_MINUTES * 60,
    )


@router.post("/app-token/exchange", response_model=Token)
@limiter.limit("20/minute")
async def exchange_app_token(
    request: Request,
    data: AppTokenExchangeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Tauscht einen App-Einmal-Token gegen einen vollwertigen JWT aus.
    Öffentlicher Endpoint – wird von der Android-App nach QR-Code-Scan aufgerufen.
    """
    result = await db.execute(
        select(AppLoginToken).where(
            AppLoginToken.token == data.token,
            AppLoginToken.used_at == None,  # noqa: E711
            AppLoginToken.expires_at > datetime.utcnow(),
        )
    )
    app_token = result.scalar_one_or_none()
    if not app_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token ungültig oder abgelaufen")

    # Token sofort als benutzt markieren (verhindert Replay)
    app_token.used_at = datetime.utcnow()

    user = await db.get(User, app_token.user_id)
    if not user or not user.is_active:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Benutzer nicht verfügbar")

    await db.commit()

    return Token(access_token=create_access_token(data={"sub": user.username}))


@router.get("/app-qr", response_model=AppQRResponse)
async def get_app_qr(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generiert einen QR-Code für die App-Authentifizierung.
    Der QR-Code enthält die API-URL und einen kurzlebigen Einmal-Token.
    Die App scannt den Code und ruft /api/auth/app-token/exchange auf.
    """
    # Alte, ungenutzte Tokens invalidieren
    await db.execute(
        delete(AppLoginToken).where(
            AppLoginToken.user_id == current_user.id,
            AppLoginToken.used_at == None,  # noqa: E711
        )
    )

    token = secrets.token_hex(32)
    expires_at = datetime.utcnow() + timedelta(minutes=_APP_TOKEN_TTL_MINUTES)

    app_token = AppLoginToken(
        user_id=current_user.id,
        token=token,
        expires_at=expires_at,
    )
    db.add(app_token)
    await db.commit()

    # API-URL ermitteln: SITE_URL hat Vorrang, sonst aus Request ableiten
    api_url = settings.site_url
    if not api_url:
        forwarded_proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        forwarded_host = request.headers.get("x-forwarded-host", request.url.netloc)
        api_url = f"{forwarded_proto}://{forwarded_host}"

    # QR-Code-Payload (JSON, damit die App es parsen kann)
    qr_payload = json.dumps({
        "url": api_url,
        "token": token,
        "type": "logbot_app_auth_v1",
    }, separators=(",", ":"))

    # QR-Code als PNG generieren
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=4,
    )
    qr.add_data(qr_payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    qr_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    return AppQRResponse(
        qr_image=f"data:image/png;base64,{qr_b64}",
        token=token,
        expires_at=expires_at,
        expires_in_seconds=_APP_TOKEN_TTL_MINUTES * 60,
        api_url=api_url,
    )


# =============================================================================
# Kurzzeit-Tickets fuer Ereignisstroeme, Terminal und Downloads
# =============================================================================
class TicketRequest(BaseModel):
    purpose: str = Field(..., pattern="^(stream|shell|download)$")


@router.post("/ticket")
async def create_stream_ticket(data: TicketRequest, current_user: User = Depends(get_current_user)):
    """Ein Ticket, das 60 Sekunden gilt und genau einmal benutzt werden kann.

    Statt des Zugangstokens steht dieses Ticket in der Adresse eines
    Ereignisstroms, des Terminals oder eines Download-Links - landet die
    Adresse in einem Protokoll, ist sie dort nichts mehr wert.
    """
    from ..auth import TICKET_SECONDS, create_ticket
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin erforderlich")
    return {"ticket": create_ticket(current_user, data.purpose), "expires_in": TICKET_SECONDS}


@router.post("/logout-all", status_code=204)
async def logout_everywhere(request: Request, db: AsyncSession = Depends(get_db),
                            current_user: User = Depends(get_current_user)):
    """Meldet das Konto auf allen Geräten ab (auch diesem)."""
    from ..auth import revoke_sessions
    revoke_sessions(current_user)
    await db.commit()
    await journal.record(db, category="auth", event="sessions.revoked", level="notice",
                         message=f"'{current_user.username}' hat sich überall abgemeldet.",
                         actor=current_user.username, source_ip=real_client_ip(request))


# =============================================================================
# Konto-Zustand: E-Mail-Pflicht, Passwortwechsel
# =============================================================================
@router.get("/account")
async def account_status(db: AsyncSession = Depends(get_db),
                         current_user: User = Depends(get_current_user)):
    """Was muss dieses Konto noch erledigen, bevor es weitergeht?

    Ab 2026.10.22 braucht jedes Konto eine E-Mail-Adresse: fuer den
    Passwort-Reset, die Anmeldung per Mail-Link in der App und Meldungen.
    """
    from .. import mail as mail_module
    config = await mail_module.load_config(db)
    has_email = mail_module.valid_address(current_user.email or "")
    return {
        "username": current_user.username,
        "email": current_user.email if has_email else "",
        "email_verified": bool(has_email and current_user.email_verified_at),
        "needs_email": not has_email,
        "must_change_password": bool(current_user.must_change_password),
        "mail_ready": mail_module.is_ready(config),
        "auth_source": current_user.auth_source or "local",
        "can_reset_password": (current_user.auth_source or "local") == "local",
    }


class PasswordChange(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def strong(cls, v: str) -> str:
        return check_password_strength(v)


@router.post("/password/change")
@limiter.limit("10/minute")
async def change_password(request: Request, data: PasswordChange, db: AsyncSession = Depends(get_db),
                          current_user: User = Depends(get_current_user)):
    """Eigenes Passwort ändern. Alle anderen Sitzungen werden beendet."""
    from ..auth import revoke_sessions
    if (current_user.auth_source or "local") != "local":
        raise HTTPException(status_code=400, detail="Dieses Konto hat hier kein Passwort.")
    if not verify_password(data.current_password, current_user.password_hash):
        await journal.record(db, category="auth", event="password.change.failed", level="warning",
                             message=f"Passwortänderung für '{current_user.username}' abgelehnt: "
                                     f"altes Passwort falsch.",
                             actor=current_user.username, source_ip=real_client_ip(request), ok=False)
        raise HTTPException(status_code=403, detail="Das aktuelle Passwort stimmt nicht.")
    if verify_password(data.new_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Das neue Passwort muss sich vom alten unterscheiden.")
    current_user.password_hash = get_password_hash(data.new_password)
    current_user.must_change_password = False
    revoke_sessions(current_user)
    await db.commit()
    await journal.record(db, category="auth", event="password.changed", level="notice",
                         message=f"'{current_user.username}' hat das Passwort geändert; "
                                 f"andere Sitzungen wurden beendet.",
                         actor=current_user.username, source_ip=real_client_ip(request))
    # Neues Token fuer dieses Fenster - das alte gilt ab jetzt nicht mehr.
    return Token(access_token=create_access_token(data={"sub": current_user.username}))


# =============================================================================
# E-Mail-Adresse setzen und bestätigen
# =============================================================================
VERIFY_MINUTES = 30
RESET_MINUTES = 30
MAX_CODE_ATTEMPTS = 5


def _digest(value: str) -> str:
    return hashlib.sha256(value.strip().encode("utf-8")).hexdigest()


class EmailSet(BaseModel):
    email: str = Field(..., max_length=254)
    current_password: str = Field(default="", max_length=128)

    @field_validator("email")
    @classmethod
    def valid(cls, v: str) -> str:
        return check_email(v)


class EmailVerify(BaseModel):
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


async def _send_verification(db: AsyncSession, user: User, source_ip: str) -> dict:
    """Schickt einen sechsstelligen Code an die neue Adresse."""
    from .. import mail as mail_module
    from ..models import UserToken

    config = await mail_module.load_config(db)
    if not mail_module.is_ready(config):
        return {"sent": False, "reason": "mail_not_configured",
                "message": "Die Adresse ist gespeichert. Bestätigt wird sie, sobald ein "
                           "Administrator den Mailversand eingerichtet hat."}
    await db.execute(delete(UserToken).where(UserToken.user_id == user.id,
                                             UserToken.purpose == "verify_email"))
    code = f"{secrets.randbelow(1_000_000):06d}"
    db.add(UserToken(user_id=user.id, purpose="verify_email", token_hash=_digest(f"{user.id}:{code}"),
                     target=user.email, expires_at=datetime.utcnow() + timedelta(minutes=VERIFY_MINUTES),
                     requested_ip=source_ip))
    await db.commit()
    body = (f"Hallo {user.username},\n\n"
            f"dein Bestätigungscode für LogBot lautet:\n\n    {code}\n\n"
            f"Er gilt {VERIFY_MINUTES} Minuten. Gib ihn in LogBot ein, um diese Adresse zu bestätigen.\n\n"
            "Warst du das nicht? Dann ignoriere diese Mail - ohne den Code passiert nichts.\n")
    try:
        await mail_module.send(config, [user.email], "LogBot — Bestätigungscode", body)
    except Exception as exc:
        logging.getLogger("logbot.auth").warning("Bestätigungsmail nicht verschickt: %s", exc)
        return {"sent": False, "reason": "send_failed",
                "message": f"Die Mail ließ sich nicht verschicken: {exc}"}
    return {"sent": True, "message": f"Ein Code ist unterwegs an {user.email}."}


@router.post("/email")
@limiter.limit("5/minute")
async def set_email(request: Request, data: EmailSet, db: AsyncSession = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    """Eigene E-Mail-Adresse setzen und einen Bestätigungscode anfordern.

    Wer ein lokales Konto hat und schon eine bestätigte Adresse, muss das
    Passwort nennen: sonst koennte ein entwendetes Sitzungstoken die Adresse
    umbiegen - und damit den naechsten Passwort-Reset.
    """
    from sqlalchemy import func as _func
    email = data.email.strip()
    local = (current_user.auth_source or "local") == "local"
    if local and current_user.email_verified_at:
        if not data.current_password or not verify_password(data.current_password,
                                                             current_user.password_hash):
            raise HTTPException(status_code=403,
                                detail="Zum Ändern einer bestätigten Adresse das Passwort angeben.")
    taken = (await db.execute(select(User).where(_func.lower(User.email) == email.lower(),
                                                 User.id != current_user.id))).scalars().first()
    if taken:
        raise HTTPException(status_code=409, detail="Diese Adresse gehört bereits zu einem anderen Konto.")
    changed = (current_user.email or "").lower() != email.lower()
    current_user.email = email
    if changed:
        current_user.email_verified_at = None
    await db.commit()
    await journal.record(db, category="auth", event="email.set",
                         message=f"'{current_user.username}' hat die E-Mail-Adresse hinterlegt.",
                         actor=current_user.username, source_ip=real_client_ip(request))
    if current_user.email_verified_at:
        return {"sent": False, "verified": True, "message": "Adresse ist bereits bestätigt."}
    result = await _send_verification(db, current_user, real_client_ip(request))
    result["verified"] = False
    return result


@router.post("/email/resend")
@limiter.limit("3/minute")
async def resend_verification(request: Request, db: AsyncSession = Depends(get_db),
                              current_user: User = Depends(get_current_user)):
    from .. import mail as mail_module
    if not mail_module.valid_address(current_user.email or ""):
        raise HTTPException(status_code=400, detail="Zuerst eine E-Mail-Adresse hinterlegen.")
    if current_user.email_verified_at:
        return {"sent": False, "verified": True}
    return await _send_verification(db, current_user, real_client_ip(request))


@router.post("/email/verify")
@limiter.limit("10/minute")
async def verify_email(request: Request, data: EmailVerify, db: AsyncSession = Depends(get_db),
                       current_user: User = Depends(get_current_user)):
    from ..models import UserToken
    row = (await db.execute(select(UserToken).where(
        UserToken.user_id == current_user.id, UserToken.purpose == "verify_email",
        UserToken.used_at.is_(None)).order_by(UserToken.id.desc()))).scalars().first()
    if row is None or row.expires_at < datetime.utcnow() or row.attempts >= MAX_CODE_ATTEMPTS \
            or (row.target or "").lower() != (current_user.email or "").lower():
        raise HTTPException(status_code=410, detail="Der Code ist abgelaufen - bitte neu anfordern.")
    if not secrets.compare_digest(row.token_hash, _digest(f"{current_user.id}:{data.code}")):
        row.attempts += 1
        await db.commit()
        raise HTTPException(status_code=400, detail="Der Code stimmt nicht.")
    row.used_at = datetime.utcnow()
    current_user.email_verified_at = datetime.utcnow()
    await db.commit()
    await journal.record(db, category="auth", event="email.verified",
                         message=f"'{current_user.username}' hat die E-Mail-Adresse bestätigt.",
                         actor=current_user.username, source_ip=real_client_ip(request))
    return {"verified": True}


# =============================================================================
# Passwort vergessen
# =============================================================================
class ForgotRequest(BaseModel):
    login: str = Field(..., min_length=1, max_length=254)


class ResetRequest(BaseModel):
    token: str = Field(..., min_length=20, max_length=200)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def strong(cls, v: str) -> str:
        return check_password_strength(v)


_reset_tasks: set = set()


@router.post("/password/forgot", status_code=202)
@limiter.limit("5/minute")
async def forgot_password(request: Request, data: ForgotRequest, db: AsyncSession = Depends(get_db)):
    """Schickt einen Link zum Zurücksetzen - sofern Konto und Adresse passen.

    Die Antwort ist IMMER dieselbe, egal ob es das Konto gibt: so laesst sich
    nicht abfragen, welche Namen oder Adressen existieren. Die Mail geht im
    Hintergrund raus, damit auch die Antwortzeit nichts verraet.
    Zurueckgesetzt werden nur lokale Konten mit bestaetigter Adresse.
    """
    import asyncio
    from .. import mail as mail_module, publicurl
    from ..models import UserToken

    generic = {"accepted": True,
               "message": "Wenn es zu dieser Angabe ein Konto mit bestätigter E-Mail-Adresse gibt, "
                          "ist ein Link zum Zurücksetzen unterwegs."}
    source_ip = real_client_ip(request)
    user = await find_user_by_login(db, data.login)
    if (user is None or not user.is_active or (user.auth_source or "local") != "local"
            or not user.email_verified_at or not mail_module.valid_address(user.email or "")):
        return generic
    recent = (await db.execute(select(UserToken).where(
        UserToken.user_id == user.id, UserToken.purpose == "password_reset",
        UserToken.created_at > datetime.utcnow() - timedelta(hours=1)))).scalars().all()
    if len(recent) >= 3:
        return generic
    base = await publicurl.get(db)
    config = await mail_module.load_config(db)
    if not base or not mail_module.is_ready(config):
        await journal.record(db, category="auth", event="password.reset.unavailable", level="warning",
                             message=("Passwort-Reset angefordert, aber "
                                      + ("keine öffentliche Adresse" if not base else "kein Mailversand")
                                      + " eingerichtet."),
                             actor=user.username, source_ip=source_ip, ok=False)
        return generic

    token = secrets.token_urlsafe(32)
    db.add(UserToken(user_id=user.id, purpose="password_reset", token_hash=_digest(token),
                     target=user.email, expires_at=datetime.utcnow() + timedelta(minutes=RESET_MINUTES),
                     requested_ip=source_ip))
    await db.commit()
    link = f"{base}/reset-password?token={token}"
    body = (f"Hallo {user.username},\n\n"
            f"für dein LogBot-Konto wurde ein neues Passwort angefordert (von IP {source_ip}).\n\n"
            f"Zum Festlegen eines neuen Passworts:\n\n{link}\n\n"
            f"Der Link gilt {RESET_MINUTES} Minuten und nur einmal. Danach sind alle bisherigen "
            f"Anmeldungen beendet.\n\n"
            "Warst du das nicht? Dann ignoriere diese Mail - dein Passwort bleibt, wie es ist.\n")
    username, address = user.username, user.email

    async def runner():
        try:
            await mail_module.send(config, [address], "LogBot — Passwort zurücksetzen", body)
        except Exception as exc:                                    # defensiv
            await journal.write(category="auth", event="password.reset.mail_failed", level="warning",
                                message=f"Reset-Mail für '{username}' nicht verschickt: {exc}",
                                actor="system", ok=False)
    task = asyncio.get_running_loop().create_task(runner())
    _reset_tasks.add(task)
    task.add_done_callback(_reset_tasks.discard)
    await journal.record(db, category="auth", event="password.reset.requested", level="notice",
                         message=f"Passwort-Reset für '{username}' angefordert.",
                         actor=username, source_ip=source_ip)
    return generic


@router.post("/password/reset")
@limiter.limit("10/minute")
async def reset_password(request: Request, data: ResetRequest, db: AsyncSession = Depends(get_db)):
    """Neues Passwort mit dem Link aus der Mail setzen."""
    from ..auth import revoke_sessions
    from ..models import UserToken
    row = (await db.execute(select(UserToken).where(
        UserToken.token_hash == _digest(data.token), UserToken.purpose == "password_reset")
    )).scalar_one_or_none()
    if row is None or row.used_at or row.expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="Der Link ist abgelaufen oder wurde schon benutzt.")
    user = await db.get(User, row.user_id)
    if user is None or not user.is_active or (user.auth_source or "local") != "local" \
            or (row.target or "").lower() != (user.email or "").lower():
        raise HTTPException(status_code=410, detail="Der Link ist abgelaufen oder wurde schon benutzt.")
    row.used_at = datetime.utcnow()
    await db.execute(delete(UserToken).where(UserToken.user_id == user.id,
                                             UserToken.purpose == "password_reset",
                                             UserToken.id != row.id))
    user.password_hash = get_password_hash(data.new_password)
    user.must_change_password = False
    clear_mfa_failures(user)
    revoke_sessions(user)
    await db.commit()
    await journal.record(db, category="auth", event="password.reset.done", level="warning",
                         message=f"Passwort von '{user.username}' per Mail-Link neu gesetzt; "
                                 f"alle Sitzungen beendet.",
                         actor=user.username, source_ip=real_client_ip(request))
    return {"reset": True, "username": user.username,
            "message": "Das Passwort ist geändert. Bitte neu anmelden."}
