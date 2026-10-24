# ==============================================================================
# Name:        Phydran6
# Kontakt:     Phydran6
# Changelog:   ../../../CHANGELOG/backend.md
# Beschreibung: LogBot - Endpunkte fuer Meldungen (Eingang, Regeln, Telegram,
#               Push) - fuer die Oberflaeche und die App
# ==============================================================================
"""
Zwei Router:

* ``/api/notifications`` - die Oberflaeche: Eingang (alle Angemeldeten),
  Regeln und Kanaele (Administratoren), Telegram-Assistent.
* ``/api/app/notifications`` und ``/api/app/push`` - die Handy-App: Eingang per
  Cursor, gelesen markieren, Push-Geraete an- und abmelden.

Was ein Benutzer sieht: Administratoren alles, alle anderen nur Meldungen zu
Logzeilen und Geraeten (``audience = all``) - Systemmeldungen ueber LogBot
selbst bleiben bei den Administratoren.
"""

import base64
import hashlib
import io
import logging
from typing import List, Optional

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import journal, mail, notify, secretbox, telegram, webpush
from ..auth import get_current_admin, get_current_user
from ..database import get_db
from ..limiter import client_ip as real_client_ip, limiter
from ..models import Notification, PushEndpoint, User

logger = logging.getLogger("logbot.routes.notifications")

router = APIRouter(prefix="/api/notifications", tags=["Meldungen"])
app_router = APIRouter(prefix="/api/app", tags=["Mobile App"])


class RulesRequest(BaseModel):
    rules: List[dict] = Field(..., max_length=50)
    mail_admins: Optional[bool] = None
    mail_extra: Optional[List[str]] = Field(default=None, max_length=20)
    push_contact: Optional[str] = Field(default=None, max_length=200)


class ReadRequest(BaseModel):
    up_to_id: int = Field(..., ge=0)


class TelegramTokenRequest(BaseModel):
    bot_token: str = Field(..., min_length=20, max_length=100)


class ChatRemove(BaseModel):
    chat_id: int


class TestRequest(BaseModel):
    channels: List[str] = Field(default_factory=lambda: ["app", "mail", "telegram"])


class PushRegister(BaseModel):
    endpoint: str = Field(..., min_length=10, max_length=2000)
    p256dh: Optional[str] = Field(default=None, max_length=200)
    auth: Optional[str] = Field(default=None, max_length=100)
    device_name: Optional[str] = Field(default=None, max_length=80)
    min_severity: Optional[str] = Field(default="warning", pattern="^(critical|error|warning|info)$")


class PushRemove(BaseModel):
    endpoint: str = Field(..., min_length=10, max_length=2000)


# =============================================================================
# Eingang (alle Angemeldeten)
# =============================================================================
@router.get("")
async def inbox(limit: int = Query(50, ge=1, le=200),
                before_id: Optional[int] = Query(None), since_id: Optional[int] = Query(None),
                severity: str = Query("", pattern="^(|critical|error|warning)$"),
                only_unread: bool = Query(False),
                db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return await notify.page(db, user, limit=limit, before_id=before_id, since_id=since_id,
                             severity=severity, only_unread=only_unread,
                             full=user.role == "admin")


@router.get("/unread")
async def unread(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return {"unread_count": await notify.unread_count(db, user)}


@router.post("/read")
async def read(data: ReadRequest, db: AsyncSession = Depends(get_db),
               user: User = Depends(get_current_user)):
    return {"last_read_id": await notify.mark_read(db, user, data.up_to_id),
            "unread_count": await notify.unread_count(db, user)}


# =============================================================================
# Regeln und Kanaele (Administratoren)
# =============================================================================
async def _overview(db: AsyncSession) -> dict:
    config = await notify.load_config(db)
    mail_config = await mail.load_config(db)
    _, vapid_public = await webpush.vapid_keys(db)
    devices = (await db.execute(select(PushEndpoint))).scalars().all()
    admins = (await db.execute(select(User).where(User.role == "admin", User.is_active.is_(True)))).scalars().all()
    tg = config.get("telegram") or {}
    return {
        "config": notify.public_config(config),
        "channels": {
            "mail": {"ready": mail.is_ready(mail_config), "mode": mail_config.get("mode"),
                     "from_address": mail_config.get("from_address"),
                     "recipients": await notify.mail_recipients(db, config, "admin"),
                     "admins_without_verified_mail": [a.username for a in admins
                                                      if not a.email_verified_at]},
            "telegram": {"ready": bool(tg.get("bot_token")) and bool(tg.get("chats")),
                         "bot_username": tg.get("bot_username"), "chats": len(tg.get("chats") or [])},
            "app": {"ready": True, "devices": len(devices), "vapid_public_key": vapid_public},
        },
        "severities": ["critical", "error", "warning", "notice", "info"],
        "categories": [{"key": k, "label": v} for k, v in journal.CATEGORIES.items()],
    }


@router.get("/config")
async def get_config(db: AsyncSession = Depends(get_db), _=Depends(get_current_admin)):
    return await _overview(db)


@router.put("/rules")
async def put_rules(data: RulesRequest, request: Request, db: AsyncSession = Depends(get_db),
                    admin=Depends(get_current_admin)):
    config = await notify.load_config(db)
    try:
        rules = [notify.validate_rule(rule) for rule in data.rules]
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    ids = [r["id"] for r in rules]
    if len(ids) != len(set(ids)):
        raise HTTPException(status_code=400, detail="Zwei Regeln haben dieselbe Kennung.")
    config["rules"] = rules
    if data.mail_admins is not None:
        config["mail_admins"] = data.mail_admins
    if data.mail_extra is not None:
        extra = []
        for address in data.mail_extra:
            address = address.strip()
            if not address:
                continue
            if not mail.valid_address(address):
                raise HTTPException(status_code=400, detail=f"'{address}' ist keine gültige Adresse.")
            extra.append(address)
        config["mail_extra"] = extra
    if data.push_contact is not None:
        config["push_contact"] = data.push_contact.strip()
    await notify.store_config(db, config)
    await journal.record(db, category="notify", event="notify.rules.changed",
                         message=f"Meldungsregeln gespeichert ({len(rules)} Regeln).",
                         actor=admin.username, source_ip=real_client_ip(request))
    return await _overview(db)


@router.post("/test")
async def test(data: TestRequest, db: AsyncSession = Depends(get_db),
               admin=Depends(get_current_admin)):
    channels = [c for c in data.channels if c in notify.CHANNELS]
    row = await notify.emit(db, severity="warning", category="test", audience="admin",
                            title="Testmeldung von LogBot",
                            body=f"Ausgelöst von {admin.username}. Kommt diese Meldung an, "
                                 f"funktioniert der Kanal.",
                            channels=channels)
    return {"id": row.id, "delivery": row.delivery}


# =============================================================================
# Telegram-Assistent
# =============================================================================
@router.post("/telegram/token")
async def telegram_token(data: TelegramTokenRequest, request: Request,
                         db: AsyncSession = Depends(get_db), admin=Depends(get_current_admin)):
    try:
        bot = await telegram.verify_token(data.bot_token)
    except telegram.TelegramError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    config = await notify.load_config(db)
    tg = config.get("telegram") or {}
    previous_bot = tg.get("bot_username")
    tg.update({"bot_token": secretbox.seal(data.bot_token.strip()), "bot_username": bot["username"],
               "bot_name": bot["name"], "offset": 0})
    if previous_bot and previous_bot != bot["username"]:
        tg["chats"] = []                      # anderer Bot: alte Chats gehoeren nicht dazu
    config["telegram"] = tg
    await notify.store_config(db, config)
    await journal.record(db, category="notify", event="telegram.bot.set", level="notice",
                         message=f"Telegram-Bot @{bot['username']} hinterlegt.",
                         actor=admin.username, source_ip=real_client_ip(request))
    return {"bot": bot}


@router.post("/telegram/link/start")
async def telegram_link_start(db: AsyncSession = Depends(get_db), _=Depends(get_current_admin)):
    config = await notify.load_config(db)
    tg = config.get("telegram") or {}
    if not tg.get("bot_username") or not telegram.bot_token(config):
        raise HTTPException(status_code=400, detail="Zuerst den Bot-Token hinterlegen.")
    link = telegram.new_link_code()
    tg["link"] = link
    config["telegram"] = tg
    await notify.store_config(db, config)
    url = f"https://t.me/{tg['bot_username']}?start={link['code']}"
    image = qrcode.make(url, box_size=6, border=2)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return {"url": url, "code": link["code"], "group_command": f"/start@{tg['bot_username']} {link['code']}",
            "expires_in": telegram.LINK_TTL,
            "qr_image": "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()}


@router.post("/telegram/link/poll")
async def telegram_link_poll(request: Request, db: AsyncSession = Depends(get_db),
                             admin=Depends(get_current_admin)):
    import time as _time
    config = await notify.load_config(db)
    tg = config.get("telegram") or {}
    link = tg.get("link") or {}
    if not link or link.get("expires", 0) < _time.time():
        raise HTTPException(status_code=410, detail="Der Verbindungscode ist abgelaufen - bitte neu starten.")
    try:
        found, offset = await telegram.poll_link(telegram.bot_token(config), link["code"],
                                                 int(tg.get("offset") or 0))
    except telegram.TelegramError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    tg["offset"] = offset
    if found:
        chats = [c for c in tg.get("chats") or [] if c.get("id") != found["id"]]
        chats.append(found)
        tg["chats"] = chats
        tg.pop("link", None)
    config["telegram"] = tg
    await notify.store_config(db, config)
    if not found:
        return {"status": "pending"}
    try:
        await telegram.send(telegram.bot_token(config), [found["id"]],
                            "✅ <b>LogBot ist verbunden.</b>\nHier kommen ab jetzt die Meldungen an, "
                            "die unter Meldungen → Regeln für Telegram eingestellt sind.")
    except Exception:                                               # defensiv
        pass
    await journal.record(db, category="notify", event="telegram.chat.linked", level="notice",
                         message=f"Telegram-Chat „{found['title']}“ verbunden.",
                         actor=admin.username, source_ip=real_client_ip(request))
    return {"status": "linked", "chat": found}


@router.post("/telegram/chat/remove")
async def telegram_chat_remove(data: ChatRemove, db: AsyncSession = Depends(get_db),
                               _=Depends(get_current_admin)):
    config = await notify.load_config(db)
    tg = config.get("telegram") or {}
    tg["chats"] = [c for c in tg.get("chats") or [] if c.get("id") != data.chat_id]
    config["telegram"] = tg
    await notify.store_config(db, config)
    return {"chats": tg["chats"]}


@router.delete("/telegram")
async def telegram_remove(request: Request, db: AsyncSession = Depends(get_db),
                          admin=Depends(get_current_admin)):
    config = await notify.load_config(db)
    config["telegram"] = {"bot_token": "", "bot_username": "", "bot_name": "", "chats": []}
    await notify.store_config(db, config)
    await journal.record(db, category="notify", event="telegram.removed", level="notice",
                         message="Telegram-Bot entfernt.", actor=admin.username,
                         source_ip=real_client_ip(request))
    return {"removed": True}


# =============================================================================
# App: Eingang und Push
# =============================================================================
@app_router.get("/notifications")
async def app_inbox(limit: int = Query(30, ge=1, le=100),
                    before_id: Optional[int] = Query(None), since_id: Optional[int] = Query(None),
                    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Eingang fuer die App: neueste zuerst, Blaettern per before_id, Nachlaufen per since_id."""
    return await notify.page(db, user, limit=limit, before_id=before_id, since_id=since_id,
                             full=False)


@app_router.get("/notifications/{notification_id}")
async def app_notification(notification_id: int, db: AsyncSession = Depends(get_db),
                           user: User = Depends(get_current_user)):
    row = await db.get(Notification, notification_id)
    if row is None or (user.role != "admin" and row.audience != "all"):
        raise HTTPException(status_code=404, detail="Diese Meldung gibt es nicht.")
    return notify.as_dict(row, await notify.last_read(db, user), full=user.role == "admin")


@app_router.post("/notifications/read")
async def app_read(data: ReadRequest, db: AsyncSession = Depends(get_db),
                   user: User = Depends(get_current_user)):
    return {"last_read_id": await notify.mark_read(db, user, data.up_to_id),
            "unread_count": await notify.unread_count(db, user)}


@app_router.get("/push/vapid")
async def push_vapid(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    _, public = await webpush.vapid_keys(db)
    return {"public_key": public}


def _hash(endpoint: str) -> str:
    return hashlib.sha256(endpoint.strip().encode("utf-8")).hexdigest()


@app_router.get("/push")
async def push_list(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (await db.execute(select(PushEndpoint).where(PushEndpoint.user_id == user.id))).scalars().all()
    return {"items": [{"id": r.id, "device_name": r.device_name, "min_severity": r.min_severity,
                       "created_at": r.created_at, "last_ok_at": r.last_ok_at,
                       "last_error": r.last_error, "encrypted": bool(r.p256dh and r.auth)}
                      for r in rows]}


@app_router.post("/push")
@limiter.limit("20/minute")
async def push_register(request: Request, data: PushRegister, db: AsyncSession = Depends(get_db),
                        user: User = Depends(get_current_user)):
    try:
        endpoint = webpush.check_endpoint_syntax(data.endpoint)
        await webpush.check_endpoint_target(endpoint, allow_private=user.role == "admin")
        if bool(data.p256dh) != bool(data.auth):
            raise webpush.EndpointRejected("p256dh und auth gehören zusammen.")
        if data.p256dh:
            webpush.encrypt(b"{}", data.p256dh, data.auth)       # Schluessel pruefen
    except (webpush.EndpointRejected, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    digest = _hash(endpoint)
    row = (await db.execute(select(PushEndpoint).where(PushEndpoint.endpoint_hash == digest))).scalar_one_or_none()
    if row is None:
        count = len((await db.execute(select(PushEndpoint.id).where(PushEndpoint.user_id == user.id))).all())
        if count >= 10:
            raise HTTPException(status_code=409, detail="Höchstens 10 Geräte pro Konto.")
        row = PushEndpoint(user_id=user.id, endpoint=endpoint, endpoint_hash=digest)
        db.add(row)
    row.user_id = user.id
    row.p256dh = data.p256dh or None
    row.auth = data.auth or None
    row.device_name = (data.device_name or "").strip()[:80] or None
    row.min_severity = data.min_severity or "warning"
    row.failures = 0
    row.last_error = None
    await db.commit()
    await db.refresh(row)
    await journal.record(db, category="notify", event="push.registered",
                         message=f"Push-Gerät „{row.device_name or 'ohne Namen'}“ angemeldet.",
                         actor=user.username, source_ip=real_client_ip(request))
    return {"id": row.id}


@app_router.delete("/push")
async def push_remove(data: PushRemove, db: AsyncSession = Depends(get_db),
                      user: User = Depends(get_current_user)):
    row = (await db.execute(select(PushEndpoint).where(
        PushEndpoint.endpoint_hash == _hash(data.endpoint), PushEndpoint.user_id == user.id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Dieses Gerät ist nicht angemeldet.")
    await db.delete(row)
    await db.commit()
    return {"removed": True}


@app_router.post("/push/test")
@limiter.limit("6/minute")
async def push_test(request: Request, db: AsyncSession = Depends(get_db),
                    user: User = Depends(get_current_user)):
    rows = (await db.execute(select(PushEndpoint).where(PushEndpoint.user_id == user.id))).scalars().all()
    if not rows:
        raise HTTPException(status_code=404, detail="Für dieses Konto ist kein Gerät angemeldet.")
    config = await notify.load_config(db)
    results = []
    for row in rows:
        ok, message, gone = await webpush.send(
            db, endpoint=row.endpoint, p256dh=row.p256dh, auth=row.auth,
            message={"type": "test", "id": 0, "severity": "info", "title": "Testmeldung von LogBot"},
            allow_private=user.role == "admin", contact=config.get("push_contact") or "")
        results.append({"id": row.id, "device_name": row.device_name, "ok": ok, "message": message})
        if gone:
            await db.delete(row)
        elif ok:
            from datetime import datetime as _dt
            row.last_ok_at = _dt.utcnow()
        else:
            row.last_error = message[:500]
    await db.commit()
    return {"results": results}
