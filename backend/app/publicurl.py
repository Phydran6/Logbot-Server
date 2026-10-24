# ==============================================================================
# Name:        Phydran6
# Kontakt:     Phydran6
# Changelog:   ../../CHANGELOG/backend.md
# Beschreibung: LogBot - Die oeffentliche Adresse des Servers (fuer Links in Mails)
# ==============================================================================
"""
Unter welcher Adresse ist dieser Server erreichbar?

Gebraucht wird das fuer jeden Link, der den Server verlaesst: Passwort-Reset,
E-Mail-Bestaetigung, Anmelde-Link fuer die App, Verweise in Telegram-Meldungen.

**Nie aus der Anfrage.** Bis hierher bauten mehrere Stellen die Adresse aus dem
`Host`- bzw. `X-Forwarded-Host`-Kopf. Den bestimmt aber der Absender: wer eine
Reset-Mail fuer ein fremdes Konto anfordert und dabei `Host: angreifer.example`
mitschickt, haette dem Opfer einen echten Reset-Link auf die eigene Seite
geschickt ("Host header poisoning", vgl. BadHost / CVE-2026-48710).

Deshalb gibt es genau zwei Quellen, in dieser Reihenfolge:

1. die Einstellung ``public_url`` - gesetzt vom Administrator, im
   Mail-Assistenten mit der Adresse vorbelegt, ueber die er die Oberflaeche
   gerade benutzt;
2. ``SITE_URL`` aus der `.env`.

Ist beides leer, gibt es keinen Link - und der Aufrufer sagt das.
"""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .models import Setting

SETTING_KEY = "public_url"

_HOST_RE = re.compile(r"^[A-Za-z0-9.\-\[\]:]+$")


def normalize(value: str) -> str:
    """Prueft und vereinheitlicht eine Adresse. Wirft ValueError bei Unsinn."""
    raw = (value or "").strip().rstrip("/")
    if not raw:
        return ""
    parts = urlsplit(raw)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError("Die Adresse muss mit http:// oder https:// beginnen.")
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("Die Adresse darf keine Zugangsdaten, Parameter oder Anker enthalten.")
    if not _HOST_RE.match(parts.netloc):
        raise ValueError("Der Servername enthält unzulässige Zeichen.")
    path = parts.path.rstrip("/")
    return f"{parts.scheme}://{parts.netloc}{path}"


async def get(db: AsyncSession) -> str:
    """Die oeffentliche Adresse - oder leer."""
    row = (await db.execute(select(Setting).where(Setting.key == SETTING_KEY))).scalar_one_or_none()
    value = row.value if row and isinstance(row.value, str) else ""
    try:
        value = normalize(value)
    except ValueError:
        value = ""
    if value:
        return value
    try:
        return normalize(settings.site_url or "")
    except ValueError:
        return ""


async def put(db: AsyncSession, value: str) -> str:
    value = normalize(value)
    row = (await db.execute(select(Setting).where(Setting.key == SETTING_KEY))).scalar_one_or_none()
    if row:
        row.value = value
    else:
        db.add(Setting(key=SETTING_KEY, value=value,
                       description="Öffentliche Adresse für Links in Mails und Meldungen"))
    await db.commit()
    return value


async def link(db: AsyncSession, path: str) -> Optional[str]:
    """Ein absoluter Link auf diesen Server - oder None, wenn keine Adresse bekannt ist."""
    base = await get(db)
    if not base:
        return None
    return base + (path if path.startswith("/") else "/" + path)
