# ==============================================================================
# Name:        Phydran6
# Kontakt:     Phydran6
# Changelog:   ../../CHANGELOG/backend.md
# Beschreibung: LogBot - Verbindung zur Caddy-Admin-Schnittstelle (Unix-Socket)
# ==============================================================================
"""
Wie das Backend mit Caddy spricht.

Bis 2026.10.22 lauschte Caddys Admin-Schnittstelle auf ``0.0.0.0:2019`` - ohne
Anmeldung. Erreichbar war sie damit fuer *jeden* Container im Docker-Netz:
n8n, Open WebUI, Portainer, Postfix. Wer einen davon uebernahm (n8n hatte 2026
mehrere kritische Luecken), konnte Caddy umkonfigurieren und den gesamten
Verkehr zu LogBot mitlesen oder umleiten - Anmeldedaten inklusive.

Jetzt lauscht sie auf einem Unix-Socket in einem Volume, das nur Caddy und das
Backend eingehaengt haben (``caddy_admin`` → ``/run/caddy-admin``). Andere
Container sehen ihn gar nicht.

Die Admin-Zeile in einer Caddyfile setzt ausschliesslich LogBot: beim Anwenden
wird sie ersetzt, beim Speichern entfernt. So kann auch eine von Hand
bearbeitete Caddyfile die Schnittstelle nicht wieder ins Netz haengen, und ein
Rueckfall auf eine aeltere LogBot-Fassung findet keine fremde Admin-Zeile vor.
"""

from __future__ import annotations

import os
import re

import httpx

from .config import settings

SOCKET_PATH = "/run/caddy-admin/admin.sock"
LEGACY_URL = "http://caddy:2019"

_ADMIN_LINE = re.compile(r"^[ \t]*admin(?:[ \t]+[^\n{]*)?(?:\{[^}]*\})?[ \t]*\n?", re.M)


def _target() -> tuple:
    """(uds-Pfad oder None, Basis-URL)."""
    url = (settings.caddy_admin_url or "").strip()
    if url.startswith("unix://"):
        return url[len("unix://"):], "http://127.0.0.1"
    # Alte .env mit fest eingetragenem http://caddy:2019: liegt der Socket da,
    # gilt er - Caddy lauscht ab dieser Fassung nicht mehr per TCP.
    if url.rstrip("/") == LEGACY_URL and os.path.exists(SOCKET_PATH):
        return SOCKET_PATH, "http://127.0.0.1"
    return None, url.rstrip("/") or LEGACY_URL


def client(timeout: float = 10.0) -> httpx.AsyncClient:
    path, base = _target()
    if path:
        return httpx.AsyncClient(timeout=timeout, base_url=base,
                                 transport=httpx.AsyncHTTPTransport(uds=path))
    return httpx.AsyncClient(timeout=timeout, base_url=base)


def describe() -> str:
    path, base = _target()
    return f"unix://{path}" if path else base


def admin_directive() -> str:
    path, base = _target()
    if path:
        return f"admin unix/{path}"
    # TCP nur noch, wenn ausdruecklich so eingestellt (CADDY_ADMIN_URL).
    host = base.split("://", 1)[-1]
    return f"admin {host}"


def strip_admin(caddyfile: str) -> str:
    """Entfernt jede Admin-Zeile (zum Speichern)."""
    head, sep, rest = _split_global(caddyfile)
    if sep:
        head = _ADMIN_LINE.sub("", head)
        cleaned = head.strip("\n")
        if cleaned.strip() in ("{", "{\n}", "{}") or re.fullmatch(r"\{\s*\}", cleaned or ""):
            return rest.lstrip("\n")
        return head + rest
    return caddyfile


def with_admin(caddyfile: str) -> str:
    """Setzt LogBots Admin-Zeile in den globalen Block (zum Anwenden)."""
    stripped = strip_admin(caddyfile)
    directive = admin_directive()
    head, sep, rest = _split_global(stripped)
    if sep:
        return head.replace("{", "{\n    " + directive, 1) + rest
    return "{\n    " + directive + "\n}\n\n" + stripped.lstrip("\n")


def _split_global(text: str) -> tuple:
    """(globaler Block, Kennung, Rest). Der globale Block ist ein '{' ganz am Anfang."""
    stripped = text.lstrip()
    if not stripped.startswith("{"):
        return "", "", text
    depth = 0
    start = len(text) - len(stripped)
    for index in range(start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[:index + 1], "global", text[index + 1:]
    return "", "", text
