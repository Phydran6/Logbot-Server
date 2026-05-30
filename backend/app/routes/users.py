# ==============================================================================
# Name:        Phydran6
# Kontakt:     Phydran6
# Version:     2026.05.30.17.22.26
# Beschreibung: LogBot - Users API Endpoints (inkl. Admin-MFA-Reset)
# ==============================================================================

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..models import User, MFABackupCode
from ..schemas import UserCreate, UserUpdate, UserResponse
from ..auth import get_current_user, get_current_admin, get_password_hash

router = APIRouter(prefix="/api/users", tags=["Users"])

@router.get("", response_model=List[UserResponse])
async def list_users(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(User).order_by(User.username))
    return result.scalars().all()

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User nicht gefunden")
    return user

@router.post("", response_model=UserResponse, status_code=201)
async def create_user(data: UserCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_admin)):
    exists = (await db.execute(select(User).where(User.username == data.username))).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=400, detail="Username existiert bereits")
    user = User(username=data.username, email=data.email, password_hash=get_password_hash(data.password), role=data.role)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

@router.put("/{user_id}", response_model=UserResponse)
async def update_user(user_id: int, data: UserUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User nicht gefunden")
    if current_user.id != user_id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Keine Berechtigung")
    if data.role and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Rollenänderung nur durch Admin")
    if data.email is not None: user.email = data.email
    if data.role is not None: user.role = data.role
    if data.is_active is not None: user.is_active = data.is_active
    if data.password: user.password_hash = get_password_hash(data.password)
    await db.commit()
    await db.refresh(user)
    return user

@router.delete("/{user_id}", status_code=204)
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_admin)):
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="Selbst löschen nicht möglich")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User nicht gefunden")
    await db.delete(user)
    await db.commit()


@router.post("/{user_id}/mfa/reset", status_code=204)
async def admin_reset_mfa(
    user_id: int,
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
    await db.execute(delete(MFABackupCode).where(MFABackupCode.user_id == user_id))
    await db.commit()
