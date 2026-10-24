# ==============================================================================
# Name:        Phydran6
# Kontakt:     Phydran6
# Version:     2026.10.23.12.00.00
# Beschreibung: LogBot - Users API Endpoints (inkl. Admin-MFA-Reset)
# ==============================================================================
"""
Konten verwalten.

Geaendert 2026.10.22 (Sicherheit):

* Die Kontoliste sehen nur noch Administratoren. Vorher bekam jedes
  angemeldete Konto alle Benutzernamen, Rollen und E-Mail-Adressen - eine
  fertige Zielliste fuer Passwort-Raten und Phishing.
* Rollen sind nur noch "admin" oder "user" (vorher beliebiger Text).
* Der letzte aktive Administrator laesst sich weder loeschen, deaktivieren
  noch herabstufen - sonst sperrt man sich selbst aus.
* Passwortwechsel, Deaktivierung und Rollenwechsel beenden alle Sitzungen des
  Kontos sofort.
* Jede Aenderung steht im Systemtagebuch, auch Anlegen und Loeschen.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..models import User, MFABackupCode
from ..schemas import UserCreate, UserUpdate, UserResponse
from ..auth import (get_current_user, get_current_admin, get_password_hash,
                    revoke_sessions, verify_password)
from ..limiter import client_ip as real_client_ip
from .. import journal

router = APIRouter(prefix="/api/users", tags=["Users"])


async def _other_active_admins(db: AsyncSession, user_id: int) -> int:
    return (await db.execute(select(func.count(User.id)).where(
        User.role == "admin", User.is_active.is_(True), User.id != user_id))).scalar() or 0


async def _email_taken(db: AsyncSession, email: str, user_id: int = 0) -> bool:
    if not email:
        return False
    return (await db.execute(select(User.id).where(
        func.lower(User.email) == email.strip().lower(), User.id != user_id))).first() is not None


@router.get("", response_model=List[UserResponse])
async def list_users(db: AsyncSession = Depends(get_db), _=Depends(get_current_admin)):
    result = await db.execute(select(User).order_by(User.username))
    return result.scalars().all()


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Keine Berechtigung")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User nicht gefunden")
    return user


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(data: UserCreate, request: Request, db: AsyncSession = Depends(get_db),
                      admin=Depends(get_current_admin)):
    exists = (await db.execute(select(User).where(User.username == data.username))).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=400, detail="Username existiert bereits")
    if await _email_taken(db, data.email):
        raise HTTPException(status_code=409, detail="Diese E-Mail-Adresse gehört bereits zu einem anderen Konto.")
    user = User(username=data.username, email=data.email, password_hash=get_password_hash(data.password),
                role=data.role,
                # Ein vom Administrator vergebenes Passwort kennt der Administrator -
                # beim ersten Anmelden setzt der Benutzer sein eigenes.
                must_change_password=True)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    await journal.record(db, category="auth", event="user.created", level="notice",
                         message=f"Konto '{user.username}' ({user.role}) angelegt.",
                         actor=admin.username, source_ip=real_client_ip(request), target=user.username)
    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(user_id: int, data: UserUpdate, request: Request,
                      db: AsyncSession = Depends(get_db),
                      current_user: User = Depends(get_current_user)):
    """Konto ändern.

    * **Administratoren** dürfen jedes Konto ändern, samt Rolle und Zustand.
    * **Alle anderen** dürfen nur ihr eigenes Konto anfassen, und davon nur
      das Passwort (mit dem alten). Die E-Mail-Adresse läuft über
      /api/auth/email - mit Bestätigungscode.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User nicht gefunden")

    is_admin = current_user.role == "admin"
    is_self = current_user.id == user_id

    if not is_self and not is_admin:
        raise HTTPException(status_code=403, detail="Keine Berechtigung")
    if data.role is not None and not is_admin:
        raise HTTPException(status_code=403, detail="Rollenänderung nur durch Admin")
    if data.is_active is not None and not is_admin:
        raise HTTPException(status_code=403,
                            detail="Den Aktiv-Zustand setzt nur ein Administrator.")
    if data.email is not None and not is_admin:
        raise HTTPException(status_code=403,
                            detail="Die eigene Adresse wird unter „Mein Konto“ mit Bestätigungscode geändert.")

    # Den letzten Administrator nicht wegnehmen.
    demoting = (data.role is not None and data.role != "admin" and user.role == "admin")
    disabling = (data.is_active is False and user.is_active and user.role == "admin")
    if (demoting or disabling) and await _other_active_admins(db, user.id) == 0:
        raise HTTPException(status_code=409,
                            detail="Das ist der letzte aktive Administrator - erst einen weiteren anlegen.")

    if data.password and is_self:
        if (user.auth_source or "local") != "local":
            raise HTTPException(
                status_code=400,
                detail=("Dieses Konto kommt aus dem Verzeichnis bzw. von einem "
                        "Anmeldedienst - ein Passwort gibt es hier nicht zu ändern."))
        if not data.current_password:
            raise HTTPException(
                status_code=400,
                detail="Zum Ändern des eigenen Passworts das aktuelle mit angeben.")
        if not verify_password(data.current_password, user.password_hash):
            await journal.record(
                db, category="auth", event="password.change.failed", level="warning",
                message=f"Passwortänderung für '{user.username}' abgelehnt: altes Passwort falsch.",
                actor=current_user.username, source_ip=real_client_ip(request), ok=False)
            raise HTTPException(status_code=403, detail="Das aktuelle Passwort stimmt nicht.")

    if data.email is not None and await _email_taken(db, data.email, user.id):
        raise HTTPException(status_code=409, detail="Diese E-Mail-Adresse gehört bereits zu einem anderen Konto.")

    changed = []
    revoke = False
    if data.email is not None and (user.email or "").lower() != data.email.lower():
        user.email = data.email
        user.email_verified_at = None
        changed.append("E-Mail")
    if data.role is not None and data.role != user.role:
        user.role = data.role
        changed.append(f"Rolle → {data.role}")
        revoke = True
    if data.is_active is not None and data.is_active != user.is_active:
        user.is_active = data.is_active
        changed.append("aktiv" if data.is_active else "deaktiviert")
        revoke = revoke or not data.is_active
    if data.password:
        user.password_hash = get_password_hash(data.password)
        # Setzt ein Administrator ein fremdes Passwort, muss es beim naechsten
        # Anmelden ersetzt werden.
        user.must_change_password = not is_self
        changed.append("Passwort")
        revoke = True
    if revoke:
        revoke_sessions(user)

    await db.commit()
    await db.refresh(user)

    if changed:
        await journal.record(
            db, category="auth", event="user.updated", level="warning",
            message=f"Konto '{user.username}' geändert: {', '.join(changed)}.",
            actor=current_user.username, source_ip=real_client_ip(request),
            target=user.username, detail={"changed": changed, "self": is_self,
                                          "sessions_revoked": revoke})
    return user


@router.delete("/{user_id}", status_code=204)
async def delete_user(user_id: int, request: Request, db: AsyncSession = Depends(get_db),
                      current_user: User = Depends(get_current_admin)):
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="Selbst löschen nicht möglich")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User nicht gefunden")
    if user.role == "admin" and user.is_active and await _other_active_admins(db, user.id) == 0:
        raise HTTPException(status_code=409, detail="Der letzte aktive Administrator lässt sich nicht löschen.")
    name = user.username
    await db.delete(user)
    await db.commit()
    await journal.record(db, category="auth", event="user.deleted", level="warning",
                         message=f"Konto '{name}' gelöscht.", actor=current_user.username,
                         source_ip=real_client_ip(request), target=name)


@router.post("/{user_id}/mfa/reset", status_code=204)
async def admin_reset_mfa(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Notfall-Reset: Admin kann MFA für andere User deaktivieren (z. B. bei verlorenem Handy).
    Eigenen Account aus Sicherheitsgründen NICHT über diesen Endpoint resetbar."""
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="Eigenes MFA bitte über /api/auth/mfa/disable deaktivieren")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User nicht gefunden")
    user.mfa_enabled = False
    user.mfa_secret = None
    user.mfa_failed_count = 0
    user.mfa_locked_until = None
    revoke_sessions(user)
    await db.execute(delete(MFABackupCode).where(MFABackupCode.user_id == user_id))
    await db.commit()
    await journal.record(db, category="auth", event="mfa.reset", level="warning",
                         message=f"Zweitfaktor von '{user.username}' zurückgesetzt.",
                         actor=current_user.username, source_ip=real_client_ip(request),
                         target=user.username)
