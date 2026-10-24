# ==============================================================================
# Name:        Phydran6
# Kontakt:     Phydran6
# Changelog:   ../../CHANGELOG/backend.md
# Beschreibung: LogBot - Meldungen: Regeln, Eingang, Verteilung an Mail,
#               Telegram und die App
# ==============================================================================
"""
Meldungen - wenn etwas passiert, das jemand wissen muss.

Woher Meldungen kommen
----------------------
* **Logzeilen.** Ein Waechter liest alle paar Sekunden die neuen Zeilen der
  `logs`-Tabelle (egal ob per HTTPS-Agent, Syslog oder Container gekommen) und
  prueft sie gegen die Regeln. Ab Werk: alles ab "kritisch".
* **Das Systemtagebuch.** Was LogBot selbst tut und was dabei schiefgeht
  (Update fehlgeschlagen, Sicherung fehlgeschlagen, Platte voll, Agent-Update
  gescheitert) - ab Werk alles ab "Fehler".
* **Geraete, die sich nicht mehr melden** - ab Werk aus (Laptops gehen abends
  eben aus).

Wohin sie gehen
---------------
Jede Meldung landet im **Eingang** (Tabelle `notifications`) - in der
Oberflaeche und in der App, mit Gelesen-Zeiger pro Benutzer. Zusaetzlich je
nach Regel: **E-Mail** (an alle Administratoren mit bestaetigter Adresse und/
oder feste Empfaenger), **Telegram** (alle verbundenen Chats) und **Push** an
die Handys (WebPush, app/webpush.py).

Gegen Meldungsfluten
--------------------
Pro Regel und Geraet hoechstens eine Meldung je Ruhezeit (Vorgabe 15
Minuten). Was in der Ruhezeit dazukommt, wird gezaehlt und mit der naechsten
Meldung als "… und 37 weitere" genannt.
"""

from __future__ import annotations

import asyncio
import copy
import logging
import re
import secrets
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from . import logparse, mail, publicurl, telegram, webpush
from .models import Agent, Log, Notification, NotificationReadState, PushEndpoint, Setting, User

logger = logging.getLogger("logbot.notify")

CONFIG_KEY = "notify_config"
STATE_KEY = "notify_state"

SEVERITY_RANK = {
    "emergency": 0, "emerg": 0, "panic": 0, "alert": 1, "critical": 2, "crit": 2,
    "error": 3, "err": 3, "warning": 4, "warn": 4, "notice": 5,
    "info": 6, "information": 6, "informational": 6, "debug": 7,
}
# Wie Meldungen selbst eingestuft werden (einfacher als die Syslog-Stufen).
NOTIFY_SEVERITY = {0: "critical", 1: "critical", 2: "critical", 3: "error", 4: "warning"}
JOURNAL_RANK = {"debug": 7, "info": 6, "notice": 5, "warning": 4, "error": 3, "critical": 2}

CHANNELS = ("mail", "telegram", "app")
LOG_POLL_SECONDS = 10
MAX_LOGS_PER_POLL = 3000

DEFAULT_RULES: List[dict] = [
    {"id": "critical-logs", "name": "Kritische Logereignisse", "enabled": True, "type": "log",
     "min_severity": "critical", "hosts": [], "include_containers": True, "keywords": [],
     "exclude": [], "channels": ["telegram", "mail", "app"], "cooldown_minutes": 15},
    {"id": "error-logs", "name": "Fehler in Logs (nur App)", "enabled": False, "type": "log",
     "min_severity": "error", "hosts": [], "include_containers": True, "keywords": [],
     "exclude": [], "channels": ["app"], "cooldown_minutes": 30},
    # Platte, Datenbank, Stille und Fluten meldet der Systemwaechter
    # (app/alerts.py) selbst - auch ohne Datenbank. Diese Regel nimmt sich der
    # uebrigen Fehler an: Update, Sicherung, Agent-Updates, Mail, Archivierung.
    {"id": "system-errors", "name": "LogBot selbst: Fehler", "enabled": True, "type": "system",
     "min_severity": "error",
     "categories": ["update", "backup", "agent_update", "mail", "notify", "archiving", "container", "token"],
     "channels": ["mail", "telegram", "app"], "cooldown_minutes": 5},
    {"id": "device-offline", "name": "Gerät meldet sich nicht mehr", "enabled": False,
     "type": "offline", "hosts": [], "channels": ["mail", "app"], "cooldown_minutes": 60},
]

DEFAULT_CONFIG: Dict[str, Any] = {
    "rules": DEFAULT_RULES,
    "mail_admins": True,          # Mails an alle Administratoren mit bestaetigter Adresse
    "mail_extra": [],             # zusaetzliche feste Empfaenger
    "telegram": {"bot_token": "", "bot_username": "", "bot_name": "", "chats": []},
    "push_contact": "",           # Kontaktadresse in der VAPID-Unterschrift
}

_RULE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,38}$")


# =============================================================================
# Konfiguration
# =============================================================================
async def _row(db: AsyncSession, key: str) -> Optional[Setting]:
    return (await db.execute(select(Setting).where(Setting.key == key))).scalar_one_or_none()


async def load_config(db: AsyncSession) -> dict:
    row = await _row(db, CONFIG_KEY)
    config = copy.deepcopy(DEFAULT_CONFIG)
    if row and isinstance(row.value, dict):
        for key in config:
            if key in row.value:
                config[key] = row.value[key]
    if not isinstance(config.get("rules"), list):
        config["rules"] = copy.deepcopy(DEFAULT_RULES)
    if not isinstance(config.get("telegram"), dict):
        config["telegram"] = copy.deepcopy(DEFAULT_CONFIG["telegram"])
    return config


async def store_config(db: AsyncSession, config: dict) -> None:
    row = await _row(db, CONFIG_KEY)
    if row:
        row.value = config
    else:
        db.add(Setting(key=CONFIG_KEY, value=config, description="Meldungen: Regeln und Kanäle"))
    await db.commit()


def public_config(config: dict) -> dict:
    safe = copy.deepcopy(config)
    tg = safe.get("telegram") or {}
    token = tg.pop("bot_token", "")
    tg.pop("link", None)
    tg["bot_token_set"] = bool(token)
    tg["bot_token_readable"] = secretbox_readable(token)
    safe["telegram"] = tg
    return safe


def secretbox_readable(value: str) -> bool:
    from . import secretbox
    return secretbox.readable(value) if value else True


def validate_rule(rule: dict) -> dict:
    """Prueft eine Regel aus der Oberflaeche und bringt sie in Form."""
    rule_type = rule.get("type")
    if rule_type not in ("log", "system", "offline"):
        raise ValueError("Unbekannte Regelart.")
    rule_id = str(rule.get("id") or "").strip().lower()
    if not _RULE_ID_RE.match(rule_id):
        rule_id = f"rule-{secrets.token_hex(4)}"
    severity = str(rule.get("min_severity") or ("critical" if rule_type == "log" else "error")).lower()
    if severity not in SEVERITY_RANK:
        raise ValueError(f"Unbekannter Schweregrad '{severity}'.")

    def _list(value, limit=50, length=200):
        if isinstance(value, str):
            value = [v for v in re.split(r"[,\n]", value)]
        return [str(v).strip()[:length] for v in (value or []) if str(v).strip()][:limit]

    channels = [c for c in _list(rule.get("channels")) if c in CHANNELS]
    return {
        "id": rule_id,
        "name": (str(rule.get("name") or "").strip() or "Regel")[:80],
        "enabled": bool(rule.get("enabled", True)),
        "type": rule_type,
        "min_severity": severity,
        "hosts": _list(rule.get("hosts")),
        "include_containers": bool(rule.get("include_containers", True)),
        "keywords": _list(rule.get("keywords")),
        "exclude": _list(rule.get("exclude")),
        "categories": _list(rule.get("categories")),
        "channels": channels,
        "cooldown_minutes": max(0, min(int(rule.get("cooldown_minutes") or 0), 24 * 60)),
    }


# =============================================================================
# Laufzustand (Cursor, Ruhezeiten) - im Speicher, Cursor auch in der DB
# =============================================================================
_cooldowns: Dict[tuple, float] = {}
_suppressed: Dict[tuple, int] = {}
_offline_seen: Dict[int, bool] = {}
_dispatch_lock = asyncio.Lock()


def _gate(rule: dict, subject: str) -> Optional[int]:
    """Darf diese Regel fuer dieses Geraet jetzt melden? Gibt die Anzahl (inkl. unterdrueckter)."""
    key = (rule["id"], subject)
    now = time.time()
    cooldown = rule.get("cooldown_minutes", 15) * 60
    if cooldown and _cooldowns.get(key, 0) > now:
        _suppressed[key] = _suppressed.get(key, 0) + 1
        return None
    _cooldowns[key] = now + cooldown
    return 1 + _suppressed.pop(key, 0)


# =============================================================================
# Ausloesen und verteilen
# =============================================================================
async def emit(db: AsyncSession, *, severity: str, category: str, title: str, body: str = "",
               audience: str = "admin", channels: Optional[List[str]] = None,
               rule_id: Optional[str] = None, hostname: str = "", agent_id: Optional[int] = None,
               log_id: Optional[int] = None, count: int = 1, data: Optional[dict] = None) -> Notification:
    """Legt eine Meldung an und verteilt sie auf die gewuenschten Kanaele."""
    row = Notification(
        created_at=datetime.utcnow(), severity=severity, category=category,
        title=title[:200], body=(body or "")[:4000], audience=audience,
        rule_id=rule_id, hostname=(hostname or None), agent_id=agent_id, log_id=log_id,
        count=max(1, count), data=data or {}, delivery={},
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    try:
        from .events import bus
        bus.publish("notification.new", {"id": row.id, "severity": severity, "title": row.title,
                                          "audience": audience}, sticky=False)
    except Exception:                                               # defensiv
        pass
    if channels:
        await _deliver(db, row, channels)
    return row


async def _deliver(db: AsyncSession, row: Notification, channels: List[str]) -> None:
    config = await load_config(db)
    delivery: Dict[str, Any] = {}
    link = await publicurl.link(db, f"/notifications?id={row.id}") or ""

    if "telegram" in channels:
        tg = config.get("telegram") or {}
        token = telegram.bot_token(config)
        chats = [c.get("id") for c in tg.get("chats") or [] if c.get("id") is not None]
        if token and chats:
            text = telegram.format_message(severity=row.severity, title=row.title, body=row.body,
                                           hostname=row.hostname or "", link=link, count=row.count)
            results = await telegram.send(token, chats, text)
            delivery["telegram"] = {"ok": all(v == "ok" for v in results.values()),
                                    "results": results, "at": datetime.utcnow().isoformat()}
        else:
            delivery["telegram"] = {"ok": False, "skipped": "nicht eingerichtet"}

    if "mail" in channels:
        try:
            recipients = await mail_recipients(db, config, row.audience)
            mail_config = await mail.load_config(db)
            if not mail.is_ready(mail_config):
                delivery["mail"] = {"ok": False, "skipped": "Mailversand nicht eingerichtet"}
            elif not recipients:
                delivery["mail"] = {"ok": False, "skipped": "keine Empfänger mit bestätigter Adresse"}
            else:
                body = row.body or ""
                if row.hostname:
                    body = f"Gerät: {row.hostname}\n\n{body}"
                if row.count > 1:
                    body += f"\n\n… und {row.count - 1} weitere gleichartige Ereignisse."
                if link:
                    body += f"\n\nIn LogBot öffnen: {link}"
                body += "\n\n-- \nDiese Mail kommt von LogBot (Meldungen). Regeln und Empfänger: " \
                        "Meldungen → Regeln."
                prefix = {"critical": "[KRITISCH] ", "error": "[FEHLER] ",
                          "warning": "[WARNUNG] "}.get(row.severity, "")
                await mail.send(mail_config, recipients, f"{prefix}{row.title}", body)
                delivery["mail"] = {"ok": True, "recipients": len(recipients),
                                    "at": datetime.utcnow().isoformat()}
        except Exception as exc:                                    # defensiv
            delivery["mail"] = {"ok": False, "error": str(exc)[:300]}

    if "app" in channels:
        delivery["app"] = await _push(db, row, config)

    row.delivery = delivery
    await db.commit()
    failed = [name for name, item in delivery.items() if item.get("error")]
    if failed:
        logger.warning("Meldung %s: Zustellung fehlgeschlagen über %s", row.id, ", ".join(failed))


async def mail_recipients(db: AsyncSession, config: dict, audience: str) -> List[str]:
    recipients: List[str] = []
    if config.get("mail_admins", True):
        # Mails gehen an die Administratoren - auch bei Log-Meldungen, die im
        # Eingang alle sehen. Wer sonst noch Mails will, steht in mail_extra.
        query = select(User).where(User.is_active.is_(True), User.email_verified_at.is_not(None),
                                   User.role == "admin")
        for user in (await db.execute(query)).scalars().all():
            if user.email and mail.valid_address(user.email):
                recipients.append(user.email)
    for address in config.get("mail_extra") or []:
        if mail.valid_address(address) and address not in recipients:
            recipients.append(address)
    return recipients


async def _push(db: AsyncSession, row: Notification, config: dict) -> dict:
    query = select(PushEndpoint, User).join(User, User.id == PushEndpoint.user_id).where(
        User.is_active.is_(True))
    if row.audience == "admin":
        query = query.where(User.role == "admin")
    sent = failed = 0
    rank = SEVERITY_RANK.get(row.severity, 6)
    for endpoint, user in (await db.execute(query)).all():
        if rank > SEVERITY_RANK.get(endpoint.min_severity or "warning", 4):
            continue
        ok, message, gone = await webpush.send(
            db, endpoint=endpoint.endpoint, p256dh=endpoint.p256dh, auth=endpoint.auth,
            message={"type": "notification", "id": row.id, "severity": row.severity,
                     "title": row.title[:120]},
            allow_private=user.role == "admin", contact=config.get("push_contact") or "",
            urgency="high" if row.severity == "critical" else "normal")
        if gone:
            await db.delete(endpoint)
            continue
        if ok:
            sent += 1
            endpoint.last_ok_at = datetime.utcnow()
            endpoint.failures = 0
            endpoint.last_error = None
        else:
            failed += 1
            endpoint.failures = (endpoint.failures or 0) + 1
            endpoint.last_error = message[:500]
    await db.commit()
    return {"ok": failed == 0, "inbox": True, "pushed": sent, "failed": failed}


# =============================================================================
# Regeln: Logzeilen
# =============================================================================
def _host_matches(patterns: List[str], hostname: str, include_containers: bool) -> bool:
    hostname = (hostname or "").lower()
    if not include_containers and "/" in hostname:
        return False
    if not patterns:
        return True
    for pattern in patterns:
        pattern = pattern.lower()
        if pattern.endswith("*"):
            if hostname.startswith(pattern[:-1]):
                return True
        elif hostname == pattern or hostname.startswith(pattern + "/"):
            # "docker01" trifft die VM und - sofern erlaubt - ihre Container.
            return True
    return False


def log_matches(rule: dict, log: dict) -> bool:
    level = (log.get("level") or "info").lower()
    if SEVERITY_RANK.get(level, 6) > SEVERITY_RANK.get(rule.get("min_severity", "critical"), 2):
        return False
    if not _host_matches(rule.get("hosts") or [], log.get("hostname") or "",
                         rule.get("include_containers", True)):
        return False
    text = f"{log.get('source') or ''} {log.get('message') or ''}".lower()
    keywords = [k.lower() for k in rule.get("keywords") or []]
    if keywords and not any(k in text for k in keywords):
        return False
    if any(k.lower() in text for k in rule.get("exclude") or []):
        return False
    return True


async def _log_cursor(db: AsyncSession) -> Optional[int]:
    row = await _row(db, STATE_KEY)
    if row and isinstance(row.value, dict) and isinstance(row.value.get("log_cursor"), int):
        return row.value["log_cursor"]
    return None


async def _save_cursor(db: AsyncSession, cursor: int) -> None:
    row = await _row(db, STATE_KEY)
    value = dict(row.value) if row and isinstance(row.value, dict) else {}
    value["log_cursor"] = cursor
    if row:
        row.value = value
    else:
        db.add(Setting(key=STATE_KEY, value=value, description="Meldungen: Lesezeiger"))
    await db.commit()


async def scan_logs(db: AsyncSession) -> int:
    """Ein Durchgang ueber die neuen Logzeilen. Gibt die Zahl der Meldungen zurueck."""
    config = await load_config(db)
    rules = [r for r in config["rules"] if r.get("enabled") and r.get("type") == "log"]
    cursor = await _log_cursor(db)
    if cursor is None:
        # Erster Lauf: ab jetzt, nicht die ganze Vergangenheit melden.
        newest = (await db.execute(select(func.max(Log.id)))).scalar() or 0
        await _save_cursor(db, int(newest))
        return 0
    if not rules:
        newest = (await db.execute(select(func.max(Log.id)))).scalar() or cursor
        if newest != cursor:
            await _save_cursor(db, int(newest))
        return 0

    worst = min(SEVERITY_RANK.get(r.get("min_severity", "critical"), 2) for r in rules)
    levels = [name for name, rank in SEVERITY_RANK.items() if rank <= worst]
    rows = (await db.execute(
        select(Log.id, Log.hostname, Log.level, Log.source, Log.message, Log.agent_id,
               Log.timestamp, Log.facility, Log.raw_message, Log.extra_data)
        .where(Log.id > cursor, func.lower(Log.level).in_(levels))
        .order_by(Log.id).limit(MAX_LOGS_PER_POLL))).mappings().all()
    if len(rows) == MAX_LOGS_PER_POLL:
        new_cursor = rows[-1]["id"]
    else:
        # Bis zum neuesten Eintrag vorruecken - auch ueber Zeilen, die keine
        # Regel interessieren.
        new_cursor = (await db.execute(select(func.max(Log.id)))).scalar() or cursor
        if rows:
            new_cursor = max(new_cursor, rows[-1]["id"])

    groups: Dict[tuple, dict] = {}
    for log in rows:
        for rule in rules:
            if log_matches(rule, log):
                key = (rule["id"], (log["hostname"] or "").lower())
                entry = groups.setdefault(key, {"rule": rule, "first": log, "count": 0, "worst": log})
                entry["count"] += 1
                if SEVERITY_RANK.get((log["level"] or "").lower(), 6) < \
                        SEVERITY_RANK.get((entry["worst"]["level"] or "").lower(), 6):
                    entry["worst"] = log
    await _save_cursor(db, int(new_cursor))

    emitted = 0
    for (rule_id, host), entry in groups.items():
        rule = entry["rule"]
        log = entry["worst"]
        allowed = _gate(rule, host)
        if allowed is None:
            _suppressed[(rule_id, host)] = _suppressed.get((rule_id, host), 0) + entry["count"] - 1
            continue
        parsed = logparse.parse_log_row(dict(log))
        summary = parsed.get("summary") or log["message"] or ""
        severity = NOTIFY_SEVERITY.get(SEVERITY_RANK.get((log["level"] or "").lower(), 6), "warning")
        title = f"{(log['level'] or '').upper()} auf {log['hostname']}"
        body = (f"{summary}\n\nQuelle: {log['source'] or '–'}\n"
                f"Zeit: {log['timestamp'].strftime('%d.%m.%Y %H:%M:%S')} UTC")
        await emit(db, severity=severity, category="log", title=title[:200], body=body,
                   audience="all", channels=rule.get("channels"), rule_id=rule_id,
                   hostname=log["hostname"] or "", agent_id=log["agent_id"], log_id=log["id"],
                   count=allowed - 1 + entry["count"],
                   data={"rule": rule["name"], "source": log["source"]})
        emitted += 1
    return emitted


# =============================================================================
# Regeln: Systemtagebuch
# =============================================================================
async def on_journal(event: dict) -> None:
    """Aufgerufen fuer jede neue Zeile im Systemtagebuch (app/journal.py)."""
    from .database import async_session

    level = (event.get("level") or "info").lower()
    if JOURNAL_RANK.get(level, 6) > JOURNAL_RANK["warning"]:
        return
    try:
        async with async_session() as db:
            config = await load_config(db)
            for rule in config["rules"]:
                if not rule.get("enabled") or rule.get("type") != "system":
                    continue
                if JOURNAL_RANK.get(level, 6) > JOURNAL_RANK.get(rule.get("min_severity", "error"), 3):
                    continue
                categories = rule.get("categories") or []
                if categories and event.get("category") not in categories:
                    continue
                if _gate(rule, f"{event.get('category')}:{event.get('event')}") is None:
                    continue
                severity = "critical" if level == "critical" else ("error" if level == "error" else "warning")
                await emit(db, severity=severity, category="system",
                           title=f"LogBot: {event.get('message', '')[:150]}",
                           body=(f"Bereich: {event.get('category')}\nVorgang: {event.get('event')}\n"
                                 f"Wer: {event.get('actor') or 'system'}"
                                 + (f"\nZiel: {event['target']}" if event.get("target") else "")),
                           audience="admin", channels=rule.get("channels"), rule_id=rule["id"],
                           data={"journal_event": event.get("event")})
    except Exception as exc:                                        # defensiv
        logger.warning("Meldung zum Tagebucheintrag nicht erzeugt: %s", exc)


# =============================================================================
# Regeln: Geraete offline
# =============================================================================
async def scan_offline(db: AsyncSession) -> int:
    config = await load_config(db)
    rules = [r for r in config["rules"] if r.get("enabled") and r.get("type") == "offline"]
    timeout = 300
    row = await _row(db, "agent_offline_timeout")
    if row is not None:
        try:
            timeout = max(60, int(row.value))
        except (TypeError, ValueError):
            pass
    cutoff = datetime.utcnow() - timedelta(seconds=timeout)
    hosts = (await db.execute(select(Agent).where(Agent.parent_id.is_(None)))).scalars().all()
    emitted = 0
    for agent in hosts:
        extra = agent.extra_data or {}
        if extra.get("decommissioned"):
            continue
        online = bool(agent.last_seen and agent.last_seen >= cutoff)
        before = _offline_seen.get(agent.id)
        _offline_seen[agent.id] = online
        if before is None or before == online:
            continue
        for rule in rules:
            if not _host_matches(rule.get("hosts") or [], agent.hostname, False):
                continue
            if online:
                await emit(db, severity="info", category="agent", audience="all",
                           title=f"{agent.hostname} meldet sich wieder",
                           body="Das Gerät liefert wieder Lebenszeichen.",
                           channels=[c for c in rule.get("channels") or [] if c != "mail"],
                           rule_id=rule["id"], hostname=agent.hostname, agent_id=agent.id)
            elif _gate(rule, agent.hostname) is not None:
                await emit(db, severity="warning", category="agent", audience="all",
                           title=f"{agent.hostname} meldet sich nicht mehr",
                           body=(f"Letztes Lebenszeichen: "
                                 f"{agent.last_seen.strftime('%d.%m.%Y %H:%M') if agent.last_seen else 'nie'} UTC"),
                           channels=rule.get("channels"), rule_id=rule["id"],
                           hostname=agent.hostname, agent_id=agent.id)
                emitted += 1
    return emitted


# =============================================================================
# Eingang lesen (Web und App)
# =============================================================================
def _visible(query, user: User):
    if user.role != "admin":
        query = query.where(Notification.audience == "all")
    return query


async def last_read(db: AsyncSession, user: User) -> int:
    row = await db.get(NotificationReadState, user.id)
    return row.last_read_id if row else 0


async def mark_read(db: AsyncSession, user: User, up_to_id: int) -> int:
    row = await db.get(NotificationReadState, user.id)
    if row is None:
        row = NotificationReadState(user_id=user.id, last_read_id=0)
        db.add(row)
    row.last_read_id = max(row.last_read_id or 0, int(up_to_id))
    row.updated_at = datetime.utcnow()
    await db.commit()
    return row.last_read_id


async def unread_count(db: AsyncSession, user: User) -> int:
    pointer = await last_read(db, user)
    query = _visible(select(func.count(Notification.id)).where(Notification.id > pointer), user)
    return (await db.execute(query)).scalar() or 0


def as_dict(row: Notification, pointer: int, full: bool = True) -> dict:
    item = {
        "id": row.id,
        "created_at": row.created_at.isoformat() + "Z" if row.created_at else None,
        "severity": row.severity, "category": row.category, "title": row.title,
        "body": row.body or "", "hostname": row.hostname, "log_id": row.log_id,
        "agent_id": row.agent_id, "count": row.count, "read": row.id <= pointer,
    }
    if full:
        item["delivery"] = row.delivery or {}
        item["rule_id"] = row.rule_id
        item["data"] = row.data or {}
    return item


async def page(db: AsyncSession, user: User, *, limit: int = 50, before_id: Optional[int] = None,
               since_id: Optional[int] = None, severity: str = "", only_unread: bool = False,
               full: bool = True) -> dict:
    pointer = await last_read(db, user)
    query = _visible(select(Notification), user)
    if before_id:
        query = query.where(Notification.id < before_id)
    if since_id:
        query = query.where(Notification.id > since_id)
    if severity:
        allowed = {"critical": ["critical"], "error": ["critical", "error"],
                   "warning": ["critical", "error", "warning"]}.get(severity)
        if allowed:
            query = query.where(Notification.severity.in_(allowed))
    if only_unread:
        query = query.where(Notification.id > pointer)
    rows = (await db.execute(query.order_by(desc(Notification.id)).limit(limit + 1))).scalars().all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [as_dict(row, pointer, full) for row in rows]
    return {
        "items": items,
        "unread_count": await unread_count(db, user),
        "has_more": has_more,
        "next_before_id": items[-1]["id"] if items and has_more else None,
        "newest_id": items[0]["id"] if items else (since_id or None),
        "last_read_id": pointer,
    }


async def prune(db: AsyncSession, days: int = 90) -> int:
    from sqlalchemy import delete
    result = await db.execute(delete(Notification).where(
        Notification.created_at < datetime.utcnow() - timedelta(days=days)))
    await db.commit()
    return result.rowcount or 0


# =============================================================================
# Hintergrund
# =============================================================================
async def watch_task() -> None:
    """Liest neue Logzeilen, prueft Geraete und haelt die Mail-Anmeldung frisch."""
    from .database import async_session
    from . import mailoauth

    await asyncio.sleep(20)
    last_offline = 0.0
    last_keepalive = 0.0
    last_prune = 0.0
    while True:
        try:
            async with async_session() as db:
                async with _dispatch_lock:
                    await scan_logs(db)
                now = time.time()
                if now - last_offline >= 60:
                    last_offline = now
                    await scan_offline(db)
                if now - last_prune >= 24 * 3600:
                    last_prune = now
                    await prune(db)
            if time.time() - last_keepalive >= 24 * 3600:
                last_keepalive = time.time()
                problem = await mailoauth.keepalive()
                if problem:
                    from . import journal
                    await journal.write(category="mail", event="mail.oauth.expired", level="error",
                                        message=f"Mailversand gestört: {problem}", actor="system",
                                        ok=False)
        except Exception as exc:                                    # defensiv
            logger.warning("Meldungs-Wächter: %s", exc)
        await asyncio.sleep(LOG_POLL_SECONDS)
