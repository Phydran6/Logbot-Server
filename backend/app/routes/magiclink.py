# ==============================================================================
# Name:        Phydran6
# Kontakt:     Phydran6
# Changelog:   ../../../CHANGELOG/backend.md
# Beschreibung: LogBot - Anmeldung per E-Mail-Link (fuer die Handy-App)
# ==============================================================================
"""
Anmelden ohne Passwort: E-Mail-Adresse eingeben, Link aus der Mail antippen.

Der Ablauf, und warum er so aussieht:

1. Die App wuerfelt ein Geheimnis (`code_verifier`) und schickt nur dessen
   SHA-256-Abdruck (`code_challenge`) mit der Anfrage. Das Geheimnis verlaesst
   das Handy erst beim Einloesen.
2. Der Server verschickt einen Link. Gespeichert wird nur sein Abdruck.
3. Antippen des Links auf dem Handy oeffnet sofort die App: Android-Browser
   bekommen eine Weiterleitung auf `intent://`, ohne Zwischenseite und ohne
   zweiten Klick. Die App loest den Link zusammen mit dem Geheimnis ein. Wer
   nur die Mail abfaengt, hat das Geheimnis nicht - der Link allein oeffnet
   nichts.
4. Eine Anmeldung im Browser gibt es hier bewusst nicht. Wird der Link an
   einem Rechner geoeffnet, sagt eine kurze Seite, dass er aufs Handy gehoert.

Was sonst noch gilt:

* Unbekannte Adresse, deaktiviertes Konto, LDAP-Konto: dieselbe Antwort wie
  bei Erfolg, nur geht keine Mail raus. So laesst sich nicht abfragen, welche
  Adressen ein Konto haben. Die Mail geht im Hintergrund raus, damit auch die
  Antwortzeit nichts verraet.
* LDAP-Konten sind ausgenommen: ihr Zugang haengt am Verzeichnis, und ein dort
  gesperrtes Konto bliebe hier sonst per Mail erreichbar.
* Ist MFA eingeschaltet, folgt nach dem Link der zweite Faktor wie beim
  Passwort - der Link ersetzt das Passwort, nicht den zweiten Faktor.
* Ein GET auf den Link loest nichts aus. Mailprogramme und Virenscanner rufen
  Links vorab auf; eingeloest wird nur von der App, mit dem Geheimnis.
"""

import asyncio
import base64
import hashlib
import hmac
import html
import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import journal, mail
from ..auth import (MFA_PENDING_TOKEN_MINUTES, create_access_token,
                    create_mfa_pending_token, is_user_mfa_locked)
from ..config import settings
from ..database import get_db
from ..limiter import client_ip as real_client_ip
from ..limiter import limiter
from ..models import MagicLinkRequest, Setting, User

logger = logging.getLogger("logbot.magiclink")

router = APIRouter(prefix="/api/auth/magic-link", tags=["Auth"])

TTL_MINUTES = 15
POLL_SECONDS = 3
# So viele offene Anfragen pro Konto in einem Zeitfenster - danach geht keine
# weitere Mail raus. Sonst laesst sich ein Postfach per Knopfdruck fluten.
MAX_OPEN_PER_USER = 3
ENABLED_SETTING = "magic_link_enabled"

# Deep-Link in die App. Das Schema ist im Manifest der Android-App eingetragen.
APP_SCHEME = "logbot"
APP_PACKAGE = "de.phytech.logbot"

# Mail-Versand im Hintergrund; Referenzen halten, damit der Garbage Collector
# keine laufende Aufgabe einsammelt.
_pending_mails: set = set()


class LinkRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    code_challenge: str = Field(..., min_length=43, max_length=128,
                                pattern=r"^[A-Za-z0-9_-]+$")
    device_name: Optional[str] = Field(default=None, max_length=80)


class ExchangeRequest(BaseModel):
    request_id: str = Field(..., min_length=16, max_length=64)
    code_verifier: str = Field(..., min_length=43, max_length=128)
    # Nur beim Oeffnen auf demselben Geraet: der Token aus dem Link.
    token: Optional[str] = Field(default=None, max_length=128)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _challenge_of(verifier: str) -> str:
    """PKCE S256: base64url(sha256(verifier)) ohne Auffuellzeichen."""
    raw = hashlib.sha256(verifier.encode("ascii", errors="ignore")).digest()
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


async def _base_url(db: AsyncSession) -> str:
    """Die eingestellte oeffentliche Adresse - nie der Host aus der Anfrage.

    Den Host-Kopf bestimmt der Absender; ein Link darauf waere ein Link auf
    eine Seite seiner Wahl (Host-Header-Injection).
    """
    from .. import publicurl
    return await publicurl.get(db)


async def _enabled(db: AsyncSession) -> bool:
    row = (await db.execute(
        select(Setting).where(Setting.key == ENABLED_SETTING))).scalar_one_or_none()
    if row is None:
        return True
    return row.value not in (False, "false", "0", 0, "off")


async def _find_user(db: AsyncSession, email: str) -> Optional[User]:
    """Genau ein aktives, lokales Konto mit dieser Adresse - sonst keins."""
    rows = (await db.execute(
        select(User).where(func.lower(User.email) == email.strip().lower())
    )).scalars().all()
    candidates = [u for u in rows if u.is_active and (u.auth_source or "local") == "local"]
    if len(candidates) != 1:
        if len(candidates) > 1:
            logger.warning("E-Mail-Link: Adresse ist mehreren Konten zugeordnet - nichts verschickt")
        return None
    return candidates[0]


def _send_in_background(config: dict, recipient: str, subject: str, body: str) -> None:
    async def runner():
        try:
            await mail.send(config, [recipient], subject, body)
        except Exception as exc:                                    # defensiv
            logger.warning("Anmelde-Mail nicht verschickt: %s", exc)
            await journal.write(category="auth", event="magiclink.mail_failed", level="warning",
                                message="Die Mail mit dem Anmelde-Link ließ sich nicht verschicken.",
                                actor="system", ok=False, detail={"error": str(exc)[:300]})
    task = asyncio.get_running_loop().create_task(runner())
    _pending_mails.add(task)
    task.add_done_callback(_pending_mails.discard)


# =============================================================================
# Anfordern
# =============================================================================
@router.post("/request", status_code=202)
@limiter.limit("5/minute")
async def request_link(request: Request, data: LinkRequest, db: AsyncSession = Depends(get_db)):
    """Schickt einen Anmelde-Link an die Adresse - sofern ein Konto dazu passt."""
    mail_config = await mail.load_config(db)
    if not mail.is_ready(mail_config):
        raise HTTPException(
            status_code=409,
            detail=("Auf diesem Server ist kein Mailversand eingerichtet. Anmeldung per "
                    "E-Mail-Link geht erst, wenn ein Administrator unter Meldungen → Kanäle → E-Mail "
                    "den Versand einrichtet."))
    if not await _base_url(db):
        raise HTTPException(
            status_code=409,
            detail=("Auf diesem Server ist keine öffentliche Adresse eingetragen. Ein "
                    "Administrator setzt sie unter Meldungen → Kanäle → E-Mail."))
    if not await _enabled(db):
        raise HTTPException(status_code=409,
                            detail="Die Anmeldung per E-Mail-Link ist auf diesem Server abgeschaltet.")

    now = datetime.utcnow()
    # Aufraeumen nebenbei: was seit einem Tag abgelaufen ist, braucht niemand mehr.
    await db.execute(delete(MagicLinkRequest).where(
        MagicLinkRequest.expires_at < now - timedelta(days=1)))

    user = await _find_user(db, data.email)
    source_ip = real_client_ip(request)
    device = (data.device_name or "").strip()[:80] or "unbekanntes Gerät"

    send = user is not None
    if user is not None:
        open_count = (await db.execute(select(func.count(MagicLinkRequest.id)).where(
            MagicLinkRequest.user_id == user.id,
            MagicLinkRequest.status == "pending",
            MagicLinkRequest.expires_at > now,
        ))).scalar() or 0
        if open_count >= MAX_OPEN_PER_USER:
            send = False
            logger.info("E-Mail-Link für '%s': schon %s offene Anfragen, keine weitere Mail",
                        user.username, open_count)

    token = secrets.token_urlsafe(32)
    row = MagicLinkRequest(
        request_id=secrets.token_urlsafe(24),
        user_id=user.id if send else None,
        token_hash=_digest(token),
        code_challenge=data.code_challenge,
        # Die Spalte stammt aus der Fassung mit Bestaetigung im Browser.
        match_code="",
        device_name=device,
        source_ip=source_ip,
        status="pending",
        expires_at=now + timedelta(minutes=TTL_MINUTES),
    )
    db.add(row)
    await db.commit()

    if send:
        base = await _base_url(db)
        link = f"{base}/api/auth/magic-link/open?rid={quote(row.request_id)}&t={quote(token)}"
        body = (
            f"Hallo {user.username},\n\n"
            f"für dein Konto auf {base} wurde gerade die Anmeldung in der Logbot-App "
            f"angefordert — vom Gerät „{device}“ (IP {source_ip}).\n\n"
            f"Zum Anmelden diesen Link auf dem Handy antippen – die App öffnet sich und "
            f"meldet dich an:\n\n{link}\n\n"
            f"Der Link gilt {TTL_MINUTES} Minuten und nur ein einziges Mal, und nur auf dem "
            "Handy, auf dem die Anmeldung angefordert wurde.\n\n"
            "Warst du das nicht? Dann ignoriere diese Mail. Ohne die App, die die Anmeldung "
            "angefordert hat, lässt sich mit dem Link nichts anfangen.\n"
        )
        _send_in_background(mail_config, user.email, "LogBot — Anmelde-Link für die App", body)
        await journal.record(
            db, category="auth", event="magiclink.requested",
            message=f"Anmelde-Link für '{user.username}' angefordert ({device}).",
            actor=user.username, source_ip=source_ip, detail={"device": device})

    return {
        "request_id": row.request_id,
        "expires_in_seconds": TTL_MINUTES * 60,
        "poll_interval_seconds": POLL_SECONDS,
    }


# =============================================================================
# Einloesen (App)
# =============================================================================
async def _load(db: AsyncSession, request_id: str) -> Optional[MagicLinkRequest]:
    return (await db.execute(select(MagicLinkRequest).where(
        MagicLinkRequest.request_id == request_id).with_for_update())).scalar_one_or_none()


@router.post("/exchange")
@limiter.limit("40/minute")
async def exchange(request: Request, data: ExchangeRequest, db: AsyncSession = Depends(get_db)):
    """Loest den Link ein (Token aus dem Link plus Geheimnis der App).

    Antwort `status`:
      * `pending`       - ohne Token: der Link wurde noch nicht geoeffnet
      * `ok`            - `access_token` liegt bei
      * `mfa_required`  - weiter mit `/api/auth/login/mfa` und `mfa_token`
    Abgelaufen, schon benutzt oder gesperrt: HTTP 410.
    """
    row = await _load(db, data.request_id)
    gone = HTTPException(status_code=status.HTTP_410_GONE,
                         detail="Dieser Anmelde-Link ist abgelaufen oder wurde schon benutzt. "
                                "Bitte einen neuen anfordern.")
    if row is None or row.status in ("consumed", "blocked") or row.expires_at < datetime.utcnow():
        raise gone

    if not hmac.compare_digest(_challenge_of(data.code_verifier), row.code_challenge):
        await journal.record(
            db, category="auth", event="magiclink.verifier_mismatch", level="warning",
            message="Ein Anmelde-Link wurde von einem fremden Gerät eingelöst — abgewiesen.",
            source_ip=real_client_ip(request), ok=False)
        raise HTTPException(status_code=401,
                            detail="Dieser Link gehört zu einer Anmeldung auf einem anderen Gerät.")

    if data.token:
        if not hmac.compare_digest(_digest(data.token), row.token_hash):
            raise HTTPException(status_code=401, detail="Der Link ist unvollständig oder falsch.")
    else:
        return {"status": "pending", "poll_interval_seconds": POLL_SECONDS}

    # Unbekannte Adresse: verhaelt sich wie eine Anfrage, die nie bestaetigt
    # wird. Mit dem richtigen Token kann man hier gar nicht ankommen.
    user = await db.get(User, row.user_id) if row.user_id else None
    if user is None or not user.is_active:
        raise gone

    row.status = "consumed"
    row.consumed_at = datetime.utcnow()
    await db.commit()

    source_ip = real_client_ip(request)
    if user.mfa_enabled:
        if is_user_mfa_locked(user):
            raise HTTPException(status_code=status.HTTP_423_LOCKED,
                                detail=f"MFA gesperrt bis {user.mfa_locked_until.isoformat()}Z")
        return {"status": "mfa_required",
                "mfa_token": create_mfa_pending_token(user.username),
                "expires_in_seconds": MFA_PENDING_TOKEN_MINUTES * 60}

    await journal.record(
        db, category="auth", event="login.ok",
        message=f"'{user.username}' hat sich per E-Mail-Link angemeldet.",
        actor=user.username, source_ip=source_ip,
        detail={"role": user.role, "method": "magic-link", "mfa": False,
                "device": row.device_name})
    return {"status": "ok", "access_token": create_access_token(data={"sub": user.username}),
            "token_type": "bearer"}


# =============================================================================
# Die Seite hinter dem Link (Browser)
# =============================================================================
_PAGE = """<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>LogBot — Anmeldung</title>
<style>
:root {{ color-scheme: light dark; --bg:#f6f7fb; --card:#fff; --fg:#1a1c1e; --muted:#5b6170;
        --accent:#2d7ff9; --border:#dde1ea; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#000820; --card:#10182e; --fg:#e2e2e6;
        --muted:#9aa3b5; --border:#24304d; }} }}
body {{ margin:0; background:var(--bg); color:var(--fg);
       font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; }}
main {{ max-width:440px; margin:0 auto; padding:32px 16px; }}
.card {{ background:var(--card); border:1px solid var(--border); border-radius:14px;
        padding:22px; margin-bottom:16px; }}
h1 {{ font-size:22px; margin:0 0 8px; }}
p {{ margin:6px 0; }} .muted {{ color:var(--muted); font-size:14px; }}
a {{ color:var(--accent); }}
</style></head><body><main>{body}</main></body></html>"""


def _page(body: str, code: int = 200) -> HTMLResponse:
    response = HTMLResponse(_PAGE.format(body=body), status_code=code)
    # Der Token steht in der Adresse: nicht zwischenspeichern, nicht weiterreichen.
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'unsafe-inline'; form-action 'none'; "
        "base-uri 'none'; frame-ancestors 'none'")
    return response


def _invalid_page() -> HTMLResponse:
    return _page('<div class="card"><h1>Link ungültig</h1>'
                 '<p>Dieser Anmelde-Link ist abgelaufen, wurde schon benutzt oder ist unvollständig.</p>'
                 '<p class="muted">In der App lässt sich jederzeit ein neuer anfordern.</p></div>', 410)


async def _valid_row(db: AsyncSession, rid: str, token: str) -> Optional[MagicLinkRequest]:
    if not rid or not token or len(rid) > 64 or len(token) > 128:
        return None
    row = (await db.execute(select(MagicLinkRequest).where(
        MagicLinkRequest.request_id == rid))).scalar_one_or_none()
    if (row is None or row.user_id is None or row.status != "pending"
            or row.expires_at < datetime.utcnow()
            or not hmac.compare_digest(_digest(token), row.token_hash)):
        return None
    return row


def _is_android(request: Request) -> bool:
    return "android" in (request.headers.get("user-agent") or "").lower()


@router.get("/open", include_in_schema=False)
@limiter.limit("30/minute")
async def open_link(request: Request, rid: str = "", t: str = "", fallback: int = 0,
                    db: AsyncSession = Depends(get_db)):
    """Fuehrt vom Link in der Mail direkt in die App. Loest selbst nichts ein.

    Android: Weiterleitung auf `intent://` - der Browser oeffnet die App sofort,
    ohne Zwischenseite. Ist die App nicht installiert, schickt Chrome hierher
    zurueck (`fallback=1`), und es gibt eine kurze Erklaerung statt einer
    Endlosschleife. Andere Geraete: Hinweis, dass der Link aufs Handy gehoert.
    """
    row = await _valid_row(db, rid, t)
    if row is None:
        return _invalid_page()

    query = f"rid={quote(rid)}&t={quote(t)}"
    if _is_android(request) and not fallback:
        back = quote(f"{await _base_url(db)}/api/auth/magic-link/open?{query}&fallback=1", safe="")
        target = (f"intent://magic-login?{query}#Intent;scheme={APP_SCHEME};package={APP_PACKAGE};"
                  f"S.browser_fallback_url={back};end")
        response = RedirectResponse(target, status_code=302)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    if fallback:
        text = ("<p>Die Logbot-App ist auf diesem Gerät nicht installiert – oder der Link wurde "
                "nicht auf dem Handy geöffnet, auf dem die Anmeldung angefordert wurde.</p>")
    else:
        text = ("<p>Dieser Link meldet dich in der <b>Logbot-App</b> an. Öffne ihn auf dem "
                "Handy, auf dem du die Anmeldung angefordert hast – dort öffnet sich die App "
                "von selbst.</p>")
    scheme_url = f"{APP_SCHEME}://magic-login?{query}"
    return _page(f'''<div class="card"><h1>Anmeldung in der Logbot-App</h1>{text}
<p class="muted">Bist du schon auf dem richtigen Handy? <a href="{html.escape(scheme_url)}">App öffnen</a></p></div>''')
