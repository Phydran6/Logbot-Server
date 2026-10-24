# ==============================================================================
# Name:        Phydran6
# Kontakt:     Phydran6
# Version:     2026.10.22.23.00.00
# Changelog:   ../../CHANGELOG/backend.md
# Beschreibung: LogBot - Auth Hilfsfunktionen (JWT, MFA-Pending-Token, Lockout,
#               Kurzzeit-Tickets fuer Ereignisstroeme und Terminal)
# ==============================================================================
"""
Anmeldung und Sitzungen.

Was sich 2026.10.22 geaendert hat:

* **PyJWT statt python-jose.** python-jose wird kaum noch gepflegt und hatte
  zwei Luecken (CVE-2024-33663 Algorithmus-Verwechslung, CVE-2024-33664
  JWE-Bombe). PyJWT ist der gepflegte Standard.
* **Sitzungen lassen sich entwerten.** Jedes Token traegt seinen
  Ausstellungszeitpunkt (`iat`). Aendert sich das Passwort, wird ein Konto
  deaktiviert oder die Rolle geaendert, setzt der Server
  `users.tokens_valid_after` - alle vorher ausgestellten Token gelten ab dann
  nicht mehr. Vorher lief ein gestohlenes Token nach dem Passwortwechsel noch
  bis zu 24 Stunden weiter.
* **Kein Zugangstoken mehr in Adressen.** Ereignisstrom (`EventSource`),
  Terminal (`WebSocket`) und Download-Links koennen keinen
  `Authorization`-Kopf mitschicken. Bisher stand dort deshalb das volle
  24-Stunden-Token in der Adresse - und damit im Zugriffsprotokoll des
  Servers. Jetzt holt die Oberflaeche vorher ein Ticket, das 60 Sekunden gilt
  und nur fuer genau einen Zweck taugt.
"""

from __future__ import annotations

import hashlib
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import get_db
from .models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Scope-Konstanten für JWTs
SCOPE_ACCESS = "access"
SCOPE_MFA_PENDING = "mfa_pending"
SCOPE_TICKET = "ticket"

# MFA-Pending-Token: 5 Minuten, reicht für Code-Eingabe
MFA_PENDING_TOKEN_MINUTES = 5

# Lockout-Politik: 10 Falschversuche → 15min Sperre, danach Reset
MFA_FAIL_THRESHOLD = 10
MFA_LOCKOUT_MINUTES = 15

# Tickets: kurz und zweckgebunden.
TICKET_SECONDS = 60
TICKET_PURPOSES = ("stream", "shell", "download")

# Ein gueltiger bcrypt-Hash ohne zugehoeriges Passwort. Wird geprueft, wenn es
# den Benutzer gar nicht gibt - sonst verraet die kuerzere Antwortzeit, welche
# Namen existieren.
_DUMMY_HASH = bcrypt.hashpw(secrets.token_bytes(16), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode('utf-8')[:72], hashed.encode('utf-8'))
    except ValueError:
        return False


def burn_password_check() -> None:
    """Gleich viel Rechenzeit wie eine echte Pruefung - gegen Benutzer-Erraten."""
    verify_password("x", _DUMMY_HASH)


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8')[:72], bcrypt.gensalt()).decode('utf-8')


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _encode(payload: dict) -> str:
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _decode(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm],
                          options={"require": ["exp", "sub"]})
    except jwt.PyJWTError:
        return None


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    # Default-Scope auf "access" setzen, falls nicht überschrieben
    to_encode.setdefault("scope", SCOPE_ACCESS)
    now = _now()
    expire = now + (expires_delta or timedelta(minutes=settings.jwt_expire_minutes))
    # iat in Millisekunden-Genauigkeit als eigener Anspruch: der Standard-"iat"
    # ist ganzzahlig, und ein Token, das in derselben Sekunde wie ein
    # Passwortwechsel ausgestellt wurde, soll eindeutig davor oder danach liegen.
    to_encode.update({"exp": expire, "iat": now, "iat_ms": int(now.timestamp() * 1000)})
    return _encode(to_encode)


def create_mfa_pending_token(username: str) -> str:
    """Kurzlebiger JWT, der nur am /login/mfa-Endpoint akzeptiert wird."""
    return create_access_token(
        {"sub": username, "scope": SCOPE_MFA_PENDING},
        expires_delta=timedelta(minutes=MFA_PENDING_TOKEN_MINUTES),
    )


def decode_mfa_pending_token(token: str) -> str:
    """Validiert den Pending-Token und gibt den Username zurück."""
    exc = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="MFA-Token ungültig oder abgelaufen")
    payload = _decode(token)
    if not payload or payload.get("scope") != SCOPE_MFA_PENDING:
        raise exc
    username = payload.get("sub")
    if not username:
        raise exc
    return username


def is_user_mfa_locked(user: User) -> bool:
    """True wenn der User aktuell wegen zu vieler Falschversuche gesperrt ist."""
    return bool(user.mfa_locked_until and user.mfa_locked_until > datetime.utcnow())


def register_mfa_failure(user: User) -> None:
    """Zählt einen MFA-Fehlversuch und sperrt ggf. den User. Caller committet."""
    user.mfa_failed_count = (user.mfa_failed_count or 0) + 1
    if user.mfa_failed_count >= MFA_FAIL_THRESHOLD:
        user.mfa_locked_until = datetime.utcnow() + timedelta(minutes=MFA_LOCKOUT_MINUTES)
        user.mfa_failed_count = 0


def clear_mfa_failures(user: User) -> None:
    """Reset nach erfolgreichem MFA-Login. Caller committet."""
    user.mfa_failed_count = 0
    user.mfa_locked_until = None


def revoke_sessions(user: User) -> None:
    """Alle bisher ausgestellten Token dieses Kontos ungueltig machen. Caller committet."""
    user.tokens_valid_after = datetime.utcnow()


def _issued_ms(payload: dict) -> int:
    if payload.get("iat_ms"):
        try:
            return int(payload["iat_ms"])
        except (TypeError, ValueError):
            return 0
    try:
        return int(payload.get("iat") or 0) * 1000
    except (TypeError, ValueError):
        return 0


def token_still_valid(user: User, payload: dict) -> bool:
    """Wurde das Token nach der letzten Entwertung ausgestellt?"""
    cutoff = getattr(user, "tokens_valid_after", None)
    if not cutoff:
        return True
    cutoff_ms = int(cutoff.replace(tzinfo=timezone.utc).timestamp() * 1000)
    return _issued_ms(payload) >= cutoff_ms


async def find_user_by_login(db: AsyncSession, login: str) -> Optional[User]:
    """Benutzer per Name - oder per E-Mail-Adresse, wenn sie eindeutig ist."""
    login = (login or "").strip()
    if not login:
        return None
    user = (await db.execute(select(User).where(User.username == login))).scalar_one_or_none()
    if user or "@" not in login:
        return user
    rows = (await db.execute(
        select(User).where(func.lower(User.email) == login.lower()))).scalars().all()
    return rows[0] if len(rows) == 1 else None


async def _user_from_payload(db: AsyncSession, payload: Optional[dict],
                             scope: str = SCOPE_ACCESS) -> Optional[User]:
    if not payload or payload.get("scope", SCOPE_ACCESS) != scope:
        return None
    username = payload.get("sub")
    if not username:
        return None
    user = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
    if user is None or not user.is_active or not token_still_valid(user, payload):
        return None
    return user


async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Ungültige Anmeldedaten",
        headers={"WWW-Authenticate": "Bearer"},
    )
    user = await _user_from_payload(db, _decode(token))
    if user is None:
        raise credentials_exception
    return user


async def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin erforderlich")
    return current_user


# =============================================================================
# Tickets: 60 Sekunden, ein Zweck, einmal benutzbar
# =============================================================================
_used_tickets: dict = {}


def create_ticket(user: User, purpose: str) -> str:
    if purpose not in TICKET_PURPOSES:
        raise ValueError(f"Unbekannter Zweck '{purpose}'.")
    return create_access_token(
        {"sub": user.username, "scope": SCOPE_TICKET, "purpose": purpose,
         "jti": secrets.token_urlsafe(12)},
        expires_delta=timedelta(seconds=TICKET_SECONDS),
    )


def _consume_jti(jti: str) -> bool:
    """Ein Ticket gilt genau einmal. Gemerkt wird nur der Abdruck, bis es ohnehin abliefe."""
    now = time.time()
    for key in [k for k, until in _used_tickets.items() if until < now]:
        _used_tickets.pop(key, None)
    digest = hashlib.sha256(jti.encode("utf-8")).hexdigest()
    if digest in _used_tickets:
        return False
    _used_tickets[digest] = now + TICKET_SECONDS + 5
    return True


async def user_from_ticket(ticket: str, purpose: str, admin_only: bool = True) -> Optional[User]:
    """Prueft ein Ticket. Kein HTTPException: SSE und WebSocket melden selbst."""
    from .database import async_session

    payload = _decode(ticket or "")
    if not payload or payload.get("purpose") != purpose or not payload.get("jti"):
        return None
    async with async_session() as session:
        user = await _user_from_payload(session, payload, scope=SCOPE_TICKET)
    if user is None or (admin_only and user.role != "admin"):
        return None
    if not _consume_jti(str(payload["jti"])):
        return None
    return user


async def admin_from_token(token: str) -> Optional[User]:
    """Prueft ein Ticket (oder - uebergangsweise - ein Zugangstoken) fuer Admins.

    Neue Oberflaechen schicken ein Ticket. Ein volles Zugangstoken wird nur
    noch angenommen, damit eine bereits offene, aeltere Oberflaeche nach dem
    Update nicht haengt; es landet dabei aber weiter im Zugriffsprotokoll -
    das Protokollfilter (main.py) schwaerzt es dort.
    """
    from .database import async_session

    payload = _decode(token or "")
    if payload and payload.get("scope") == SCOPE_TICKET:
        purpose = payload.get("purpose") or ""
        return await user_from_ticket(token, purpose, admin_only=True)
    async with async_session() as session:
        user = await _user_from_payload(session, payload)
    if not user or user.role != "admin":
        return None
    return user
