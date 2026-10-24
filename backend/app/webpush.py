# ==============================================================================
# Name:        Phydran6
# Kontakt:     Phydran6
# Changelog:   ../../CHANGELOG/backend.md
# Beschreibung: LogBot - Push an die App (UnifiedPush / WebPush, RFC 8291 + 8292)
# ==============================================================================
"""
Push-Nachrichten an Handys - ohne Google-Konto, ohne Firebase.

Die App meldet sich mit der Adresse ihres UnifiedPush-Verteilers an (z.B. ntfy,
selbst betrieben oder ntfy.sh) und mit ihrem oeffentlichen Schluessel. Der
Server verschluesselt jede Nachricht nach RFC 8291 (aes128gcm) - der Verteiler
sieht nur Rauschen - und unterschreibt die Zustellung nach RFC 8292 (VAPID).

Inhalt bewusst minimal: ``{"type":"notification","id":…,"severity":…,
"title":…}``. Den Rest holt die App angemeldet ueber `/api/app/notifications`.

Schutz gegen SSRF: Die Adresse waehlt die App (also jeder angemeldete
Benutzer). Deshalb nur `https`, nur Namen mit Punkt, keine Weiterleitungen,
und vor jedem Versand wird geprueft, wohin der Name zeigt - Loopback,
Link-Local und (fuer Nicht-Administratoren) private Netze sind ausgeschlossen.
"""

from __future__ import annotations

import asyncio
import base64
import ipaddress
import json
import os
import socket
import struct
import time
from typing import Optional, Tuple
from urllib.parse import urlsplit

import httpx
import jwt
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import secretbox
from .models import Setting

VAPID_KEY = "push_vapid"
RECORD_SIZE = 4096
TTL_SECONDS = 86400


def b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def unb64u(value: str) -> bytes:
    value = (value or "").strip()
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


# =============================================================================
# Adresse pruefen
# =============================================================================
class EndpointRejected(ValueError):
    pass


def _blocked(ip: ipaddress._BaseAddress, allow_private: bool) -> bool:
    if ip.is_loopback or ip.is_link_local or ip.is_unspecified or ip.is_multicast or ip.is_reserved:
        return True
    if not allow_private and (ip.is_private or ip.is_global is False):
        return True
    return False


def check_endpoint_syntax(url: str) -> str:
    parts = urlsplit((url or "").strip())
    if parts.scheme != "https":
        raise EndpointRejected("Push-Adressen müssen mit https:// beginnen.")
    host = parts.hostname or ""
    if not host or "." not in host or parts.username or parts.password:
        raise EndpointRejected("Die Push-Adresse braucht einen vollständigen Servernamen.")
    if len(url) > 2000:
        raise EndpointRejected("Die Push-Adresse ist zu lang.")
    return url.strip()


async def check_endpoint_target(url: str, allow_private: bool) -> None:
    """Wohin zeigt der Name gerade? Vor jedem Versand - gegen DNS-Tricks."""
    parts = urlsplit(url)
    host = parts.hostname or ""
    try:
        literal = ipaddress.ip_address(host)
        addresses = [literal]
    except ValueError:
        loop = asyncio.get_running_loop()
        try:
            infos = await loop.getaddrinfo(host, parts.port or 443, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise EndpointRejected(f"Der Name {host} lässt sich nicht auflösen.") from exc
        addresses = [ipaddress.ip_address(info[4][0]) for info in infos]
    for ip in addresses:
        if _blocked(ip, allow_private):
            raise EndpointRejected(f"Die Push-Adresse zeigt auf ein internes Ziel ({ip}) - "
                                   f"das ist nicht erlaubt.")


# =============================================================================
# VAPID-Schluessel des Servers
# =============================================================================
_vapid_cache: Optional[Tuple[ec.EllipticCurvePrivateKey, str]] = None


async def vapid_keys(db: AsyncSession) -> Tuple[ec.EllipticCurvePrivateKey, str]:
    """(privater Schluessel, oeffentlicher Schluessel als base64url)."""
    global _vapid_cache
    if _vapid_cache:
        return _vapid_cache
    row = (await db.execute(select(Setting).where(Setting.key == VAPID_KEY))).scalar_one_or_none()
    private = None
    if row and isinstance(row.value, dict) and row.value.get("private_pem"):
        pem = secretbox.open_(row.value["private_pem"])
        if pem:
            private = serialization.load_pem_private_key(pem.encode(), password=None)
    if private is None:
        private = ec.generate_private_key(ec.SECP256R1())
        pem = private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption()).decode()
        value = {"private_pem": secretbox.seal(pem)}
        if row:
            row.value = value
        else:
            db.add(Setting(key=VAPID_KEY, value=value, description="Schlüssel für Push (VAPID)"))
        await db.commit()
    public = private.public_key().public_bytes(serialization.Encoding.X962,
                                               serialization.PublicFormat.UncompressedPoint)
    _vapid_cache = (private, b64u(public))
    return _vapid_cache


def _vapid_header(private: ec.EllipticCurvePrivateKey, public_b64: str, endpoint: str,
                  contact: str) -> str:
    parts = urlsplit(endpoint)
    claims = {"aud": f"{parts.scheme}://{parts.netloc}", "exp": int(time.time()) + 12 * 3600,
              "sub": contact or "mailto:logbot@localhost.invalid"}
    token = jwt.encode(claims, private, algorithm="ES256")
    return f"vapid t={token}, k={public_b64}"


# =============================================================================
# Verschluesselung nach RFC 8291 (aes128gcm, ein Datensatz)
# =============================================================================
def encrypt(payload: bytes, p256dh: str, auth: str) -> bytes:
    ua_public = unb64u(p256dh)
    auth_secret = unb64u(auth)
    if len(ua_public) != 65 or len(auth_secret) < 16:
        raise ValueError("Ungültiger Push-Schlüssel der App.")
    receiver = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_public)
    sender = ec.generate_private_key(ec.SECP256R1())
    as_public = sender.public_key().public_bytes(serialization.Encoding.X962,
                                                 serialization.PublicFormat.UncompressedPoint)
    shared = sender.exchange(ec.ECDH(), receiver)
    ikm = HKDF(algorithm=hashes.SHA256(), length=32, salt=auth_secret,
               info=b"WebPush: info\x00" + ua_public + as_public).derive(shared)
    salt = os.urandom(16)
    cek = HKDF(algorithm=hashes.SHA256(), length=16, salt=salt,
               info=b"Content-Encoding: aes128gcm\x00").derive(ikm)
    nonce = HKDF(algorithm=hashes.SHA256(), length=12, salt=salt,
                 info=b"Content-Encoding: nonce\x00").derive(ikm)
    if len(payload) > RECORD_SIZE - 17 - 1:
        raise ValueError("Push-Inhalt zu groß.")
    ciphertext = AESGCM(cek).encrypt(nonce, payload + b"\x02", None)
    header = salt + struct.pack("!I", RECORD_SIZE) + bytes([len(as_public)]) + as_public
    return header + ciphertext


# =============================================================================
# Senden
# =============================================================================
async def send(db: AsyncSession, *, endpoint: str, p256dh: Optional[str], auth: Optional[str],
               message: dict, allow_private: bool, contact: str = "",
               urgency: str = "normal") -> Tuple[bool, str, bool]:
    """Schickt eine Push-Nachricht. Gibt (ok, Meldung, Adresse-weg) zurueck.

    "Adresse weg" (HTTP 404/410) heisst: die App hat sich abgemeldet - der
    Aufrufer loescht den Eintrag.
    """
    try:
        check_endpoint_syntax(endpoint)
        await check_endpoint_target(endpoint, allow_private)
    except EndpointRejected as exc:
        return False, str(exc), False

    body = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    headers = {"TTL": str(TTL_SECONDS), "Urgency": urgency}
    if p256dh and auth:
        try:
            body = encrypt(body, p256dh, auth)
        except ValueError as exc:
            return False, str(exc), False
        headers["Content-Encoding"] = "aes128gcm"
        headers["Content-Type"] = "application/octet-stream"
    else:
        headers["Content-Type"] = "application/json"
    private, public_b64 = await vapid_keys(db)
    headers["Authorization"] = _vapid_header(private, public_b64, endpoint, contact)

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=False) as client:
            response = await client.post(endpoint, content=body, headers=headers)
    except httpx.HTTPError as exc:
        return False, f"Verteiler nicht erreichbar: {exc}", False
    if response.status_code in (404, 410):
        return False, "Die App hat sich vom Verteiler abgemeldet.", True
    if response.status_code >= 300:
        return False, f"Verteiler antwortet mit HTTP {response.status_code}", False
    return True, "", False
