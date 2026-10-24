# ==============================================================================
# Name:        Phydran6
# Kontakt:     Phydran6
# Changelog:   ../../CHANGELOG/backend.md
# Beschreibung: LogBot - Geheimnisse verschluesselt in der Datenbank ablegen
# ==============================================================================
"""
Geheimnisse, die LogBot selbst braucht - Bot-Token, OAuth-Refresh-Token,
API-Schluessel -, liegen nicht im Klartext in der Datenbank.

Warum: Ein Datenbankabzug, eine Sicherung ohne Passwort oder ein Blick mit
`psql` haette sonst gereicht, um im Namen des Servers Mails zu verschicken oder
den Telegram-Bot zu uebernehmen.

Wie: Fernet (AES-128-CBC + HMAC-SHA256) aus `cryptography`. Der Schluessel wird
per HKDF aus `JWT_SECRET` abgeleitet - der steht in der `.env` auf dem Server
und nicht in der Datenbank. Wer nur die Datenbank hat, hat damit nur Rauschen.

Gespeichert wird ``enc:v1:<token>``. Werte ohne diese Kennung gelten als
Altbestand im Klartext und werden unveraendert zurueckgegeben - beim naechsten
Speichern werden sie verschluesselt.

Kann ein Wert nicht entschluesselt werden (Sicherung von einem anderen Server
eingespielt, `JWT_SECRET` geaendert), kommt ein leerer String zurueck. Die
Oberflaeche zeigt dann "neu eingeben" - lieber das als ein Absturz.
"""

from __future__ import annotations

import base64
import logging
from functools import lru_cache
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .config import settings

logger = logging.getLogger("logbot.secretbox")

PREFIX = "enc:v1:"


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    secret = (settings.jwt_secret or "change-me").encode("utf-8")
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=b"logbot-secretbox",
               info=b"logbot-secrets-v1").derive(secret)
    return Fernet(base64.urlsafe_b64encode(key))


def seal(value: Optional[str]) -> str:
    """Verschluesselt einen Wert. Leer bleibt leer, Verschluesseltes bleibt, wie es ist."""
    if not value:
        return ""
    if is_sealed(value):
        return value
    return PREFIX + _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def open_(value: Optional[str]) -> str:
    """Entschluesselt einen Wert. Klartext (Altbestand) kommt unveraendert zurueck."""
    if not value:
        return ""
    if not is_sealed(value):
        return value
    try:
        return _fernet().decrypt(value[len(PREFIX):].encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        logger.warning("Ein gespeichertes Geheimnis ließ sich nicht entschlüsseln "
                       "(anderer Server oder geändertes JWT_SECRET) - bitte neu eingeben.")
        return ""


def is_sealed(value: Optional[str]) -> bool:
    return isinstance(value, str) and value.startswith(PREFIX)


def readable(value: Optional[str]) -> bool:
    """Ist ein gesetzter Wert auch wirklich benutzbar?"""
    return bool(value) and bool(open_(value))
