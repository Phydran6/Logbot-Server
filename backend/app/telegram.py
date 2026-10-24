# ==============================================================================
# Name:        Phydran6
# Kontakt:     Phydran6
# Changelog:   ../../CHANGELOG/backend.md
# Beschreibung: LogBot - Telegram-Bot fuer Meldungen (Einrichtung und Versand)
# ==============================================================================
"""
Meldungen per Telegram.

Einrichten in drei Schritten (Meldungen → Kanäle → Telegram):

1. Bei @BotFather einen Bot anlegen (`/newbot`) und den Token einfuegen. Der
   Server prueft ihn sofort (`getMe`) und zeigt Name und @Benutzernamen.
2. "Chat verbinden": LogBot erzeugt einen Einmal-Code und einen Link
   `t.me/<bot>?start=<code>` (auch als QR-Code fuers Handy). Man tippt in
   Telegram auf "Starten" - der Server sieht die Nachricht `/start <code>` und
   merkt sich diesen Chat. Fuer Gruppen: Bot in die Gruppe aufnehmen und dort
   `/start@<bot> <code>` schicken.
3. Testnachricht.

Der Bot-Token ist der Schluessel zum Bot und liegt verschluesselt in der
Datenbank. Er steht in jeder Adresse der Telegram-API - deshalb ist das
Anfrageprotokoll von httpx abgeschaltet (main.py), sonst stuende der Token im
Container-Log und damit, ueber die Container-Erfassung, in LogBot selbst.
"""

from __future__ import annotations

import html
import logging
import re
import secrets
import time
from typing import List, Optional

import httpx

from . import secretbox

logger = logging.getLogger("logbot.telegram")

API = "https://api.telegram.org"
TOKEN_RE = re.compile(r"^\d{5,15}:[A-Za-z0-9_-]{30,60}$")
LINK_TTL = 900


class TelegramError(Exception):
    pass


def _url(token: str, method: str) -> str:
    return f"{API}/bot{token}/{method}"


async def call(token: str, method: str, payload: Optional[dict] = None, timeout: float = 20.0) -> dict:
    if not token:
        raise TelegramError("Es ist kein Bot-Token hinterlegt.")
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(_url(token, method), json=payload or {})
    except httpx.HTTPError as exc:
        # Die Ausnahme nennt die Adresse - und darin den Token. Nicht weiterreichen.
        raise TelegramError(f"Telegram ist nicht erreichbar ({type(exc).__name__}).") from None
    try:
        data = response.json()
    except ValueError:
        raise TelegramError(f"Telegram antwortet mit HTTP {response.status_code}.") from None
    if not data.get("ok"):
        description = str(data.get("description") or f"HTTP {response.status_code}")
        if response.status_code == 401:
            description = "Der Bot-Token stimmt nicht (oder der Bot wurde gelöscht)."
        raise TelegramError(description[:300])
    return data.get("result")


def bot_token(config: dict) -> str:
    return secretbox.open_((config.get("telegram") or {}).get("bot_token") or "")


async def verify_token(token: str) -> dict:
    token = (token or "").strip()
    if not TOKEN_RE.match(token):
        raise TelegramError("Das sieht nicht wie ein Bot-Token aus (Form: 123456789:ABC…).")
    me = await call(token, "getMe")
    # Fuer die Chat-Verbindung lesen wir Updates selbst ab. Ein gesetzter
    # Webhook wuerde das verhindern.
    try:
        await call(token, "deleteWebhook", {"drop_pending_updates": False})
    except TelegramError:
        pass
    return {"id": me.get("id"), "username": me.get("username"), "name": me.get("first_name")}


def new_link_code() -> dict:
    return {"code": secrets.token_urlsafe(9).replace("-", "x").replace("_", "y"),
            "expires": time.time() + LINK_TTL}


async def poll_link(token: str, code: str, offset: int) -> tuple:
    """Sucht in den neuen Nachrichten an den Bot nach '/start <code>'.

    Gibt (gefundener Chat oder None, neuer offset) zurueck.
    """
    updates = await call(token, "getUpdates", {"offset": offset, "timeout": 0,
                                               "allowed_updates": ["message", "my_chat_member"]})
    found = None
    for update in updates or []:
        offset = max(offset, int(update.get("update_id", 0)) + 1)
        message = update.get("message") or {}
        text = (message.get("text") or "").strip()
        if not text.startswith("/start"):
            continue
        parts = text.split()
        if len(parts) >= 2 and secrets.compare_digest(parts[1], code):
            chat = message.get("chat") or {}
            sender = message.get("from") or {}
            found = {
                "id": chat.get("id"),
                "type": chat.get("type"),
                "title": chat.get("title") or " ".join(
                    p for p in (chat.get("first_name"), chat.get("last_name")) if p)
                or chat.get("username") or str(chat.get("id")),
                "linked_by": sender.get("username") or sender.get("first_name") or "",
                "linked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
    return found, offset


def format_message(*, severity: str, title: str, body: str, hostname: str = "",
                   link: str = "", count: int = 1) -> str:
    icon = {"critical": "🚨", "error": "❗", "warning": "⚠️"}.get(severity, "ℹ️")
    lines = [f"{icon} <b>{html.escape(title)}</b>"]
    if hostname:
        lines.append(f"🖥 <code>{html.escape(hostname)}</code>")
    if body:
        lines.append(html.escape(body[:3000]))
    if count > 1:
        lines.append(f"<i>… und {count - 1} weitere gleichartige Ereignisse</i>")
    if link:
        lines.append(f'<a href="{html.escape(link, quote=True)}">In LogBot öffnen</a>')
    return "\n".join(lines)


async def send(token: str, chat_ids: List[int], text: str) -> dict:
    results = {}
    for chat_id in chat_ids:
        try:
            await call(token, "sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                                              "disable_web_page_preview": True})
            results[str(chat_id)] = "ok"
        except TelegramError as exc:
            results[str(chat_id)] = str(exc)
    return results
