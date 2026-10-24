# ==============================================================================
# Name:        Phydran6
# Kontakt:     Phydran6
# Version:     2026.10.23.12.00.00
# Changelog:   ../../CHANGELOG/backend.md
# Beschreibung: LogBot - Mailversand: SMTP, Postfix, Google und Microsoft
# ==============================================================================
"""
Mailversand - eingerichtet im Browser, nicht in `main.cf`.

Fuenf Wege, eine Oberflaeche (Meldungen → Kanäle → E-Mail):

* **google**    - Gmail / Google Workspace ueber die Gmail-API, angemeldet per
                  OAuth ("Mit Google anmelden"). Kein Passwort auf dem Server.
* **microsoft** - Outlook.com und Microsoft 365 ueber Microsoft Graph, ebenfalls
                  per OAuth. Bei Microsoft 365 legt der Assistent die
                  App-Registrierung auf Wunsch selbst an (app/mailoauth.py).
* **relay**     - ein vorhandener Mailserver per SMTP. Mit Vorlagen fuer die
                  gaengigen Anbieter (GMX, WEB.DE, IONOS, Strato, T-Online,
                  Posteo, mailbox.org, iCloud, Yahoo und Gmail per App-Passwort).
* **container** - der mitgelieferte Postfix (`deploy/optional.yml`).
* **off**       - kein Versand.

Alle Geheimnisse (SMTP-Passwoerter, OAuth-Refresh-Token, Client-Geheimnisse)
liegen verschluesselt in der Datenbank (app/secretbox.py) und werden nie
zurueckgegeben - die Oberflaeche erfaehrt nur, *ob* eines hinterlegt ist.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import re
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import hostexec, secretbox
from .models import Setting

logger = logging.getLogger("logbot.mail")

SETTING_KEY = "mail_config"

# Wo die Datei fuer den Postfix-Container liegt (relativ zur Installation).
POSTFIX_ENV_RELATIVE = "data/postfix/settings.env"

MODES = {
    "off": {"label": "Aus", "label_en": "Off",
            "hint": "Der Server verschickt keine Mails."},
    "google": {"label": "Google (Gmail / Workspace)", "label_en": "Google (Gmail / Workspace)",
               "hint": "Mit dem Google-Konto anmelden - kein Passwort auf dem Server."},
    "microsoft": {"label": "Microsoft (Outlook.com / Microsoft 365)",
                  "label_en": "Microsoft (Outlook.com / Microsoft 365)",
                  "hint": "Mit dem Microsoft-Konto anmelden. Für Microsoft 365 legt der "
                          "Assistent die App-Registrierung selbst an."},
    "relay": {"label": "Mailserver per SMTP", "label_en": "Mail server via SMTP",
              "hint": "GMX, WEB.DE, IONOS, Strato, Firmen-Mailserver - oder Gmail mit App-Passwort."},
    "container": {"label": "Postfix-Container auf diesem Server",
                  "label_en": "Postfix container on this server",
                  "hint": "LogBot bringt seinen eigenen Mailserver mit (Zusatzdienst 'postfix')."},
}

# Vorlagen fuer gaengige Anbieter. Nur Vorbelegung - alles bleibt aenderbar.
SMTP_PRESETS: List[dict] = [
    {"id": "gmail", "label": "Gmail (App-Passwort)", "host": "smtp.gmail.com", "port": 587,
     "encryption": "starttls",
     "hint": "Braucht die Bestätigung in zwei Schritten und ein App-Passwort.",
     "help_url": "https://myaccount.google.com/apppasswords"},
    {"id": "gmx", "label": "GMX", "host": "mail.gmx.net", "port": 587, "encryption": "starttls",
     "hint": "In den GMX-Einstellungen „POP3/IMAP Abruf“ erlauben."},
    {"id": "webde", "label": "WEB.DE", "host": "smtp.web.de", "port": 587, "encryption": "starttls",
     "hint": "In den WEB.DE-Einstellungen „POP3/IMAP Abruf“ erlauben."},
    {"id": "ionos", "label": "IONOS (1&1)", "host": "smtp.ionos.de", "port": 587, "encryption": "starttls"},
    {"id": "strato", "label": "Strato", "host": "smtp.strato.de", "port": 465, "encryption": "tls"},
    {"id": "tonline", "label": "T-Online", "host": "securesmtp.t-online.de", "port": 587,
     "encryption": "starttls", "hint": "Braucht ein eigenes E-Mail-Passwort aus dem Kundencenter."},
    {"id": "posteo", "label": "Posteo", "host": "posteo.de", "port": 587, "encryption": "starttls"},
    {"id": "mailboxorg", "label": "mailbox.org", "host": "smtp.mailbox.org", "port": 587,
     "encryption": "starttls"},
    {"id": "icloud", "label": "iCloud Mail", "host": "smtp.mail.me.com", "port": 587,
     "encryption": "starttls", "hint": "Braucht ein app-spezifisches Passwort (appleid.apple.com)."},
    {"id": "yahoo", "label": "Yahoo Mail", "host": "smtp.mail.yahoo.com", "port": 587,
     "encryption": "starttls", "hint": "Braucht ein App-Passwort aus den Yahoo-Kontoeinstellungen."},
    {"id": "custom", "label": "Eigener Mailserver", "host": "", "port": 587, "encryption": "starttls"},
]

DEFAULT_CONFIG: Dict[str, Any] = {
    "mode": "off",
    "from_address": "",
    "from_name": "LogBot",
    "preset": "",
    "smtp_host": "",
    "smtp_port": 587,
    "smtp_user": "",
    "smtp_password": "",
    "encryption": "starttls",           # none | starttls | tls
    "verify_certificate": True,
    "myhostname": "",
    "relay_host": "",                    # nur fuer den Container: Smarthost
    "relay_port": 587,
    "relay_user": "",
    "relay_password": "",
    "default_recipients": [],
    # OAuth (google/microsoft). Geheimnisse verschluesselt.
    "oauth": {},
    # Vom Assistenten angelegte Microsoft-App-Registrierung (keine Geheimnisse).
    "ms_app": {},
    "last_test": {},
}

SECRET_FIELDS = ("smtp_password", "relay_password")
OAUTH_SECRET_FIELDS = ("refresh_token", "client_secret")

ENCRYPTIONS = {
    "none": "Unverschlüsselt (nur im eigenen Netz vertretbar)",
    "starttls": "STARTTLS (üblich, Port 587)",
    "tls": "TLS von Anfang an (Port 465)",
}

_EMAIL_RE = re.compile(r"^[^@\s<>\"',;]+@[^@\s<>\"',;]+\.[^@\s<>\"',;]{2,}$")


def valid_address(value: str) -> bool:
    """Eine E-Mail-Adresse, die man wirklich anschreiben kann (nicht admin@localhost)."""
    value = (value or "").strip()
    if not value or len(value) > 254 or not _EMAIL_RE.match(value):
        return False
    domain = value.rsplit("@", 1)[-1].lower()
    return not (domain == "localhost" or domain.endswith(".localhost")
                or domain.endswith(".local") or domain.endswith(".invalid"))


def _clean_line(value: Any, limit: int = 300) -> str:
    """Eine Zeile ohne Steuerzeichen - fuer Kopfzeilen und die Postfix-Datei.

    Ein Zeilenumbruch in einem Wert waere sonst eine zusaetzliche Zeile in der
    Konfiguration bzw. eine zusaetzliche Kopfzeile in der Mail.
    """
    return re.sub(r"[\x00-\x1f\x7f]", "", str(value or "")).strip()[:limit]


# =============================================================================
# Konfiguration
# =============================================================================
async def load_config(db: AsyncSession) -> dict:
    row = (await db.execute(select(Setting).where(Setting.key == SETTING_KEY))).scalar_one_or_none()
    config = _deep_default()
    if row and isinstance(row.value, dict):
        for key, value in row.value.items():
            if key in config:
                # Verschachteltes kopieren (notify_on, default_recipients):
                # save_config aendert es an Ort und Stelle. Teilt es sich das
                # Objekt mit der geladenen Zeile, sieht SQLAlchemy keinen
                # Unterschied und speichert die Aenderung nicht.
                if isinstance(value, dict):
                    value = dict(value)
                elif isinstance(value, list):
                    value = list(value)
                config[key] = value
    if config["mode"] not in MODES:
        config["mode"] = "off"
    if not isinstance(config.get("oauth"), dict):
        config["oauth"] = {}
    return config


def _deep_default() -> dict:
    config = dict(DEFAULT_CONFIG)
    config["default_recipients"] = []
    config["oauth"] = {}
    config["ms_app"] = {}
    config["last_test"] = {}
    return config


def is_ready(config: dict) -> bool:
    """Kann dieser Server gerade Mails verschicken?"""
    mode = config.get("mode", "off")
    if mode == "off" or not config.get("from_address"):
        return False
    if mode in ("google", "microsoft"):
        oauth = config.get("oauth") or {}
        return oauth.get("provider") == mode and secretbox.readable(oauth.get("refresh_token"))
    if mode == "relay":
        return bool(config.get("smtp_host"))
    return True


def public_config(config: dict) -> dict:
    """Ohne Geheimnisse - so geht es an die Oberflaeche."""
    safe = {k: v for k, v in config.items() if k not in SECRET_FIELDS and k != "oauth"}
    for key in SECRET_FIELDS:
        safe[f"{key}_set"] = bool(config.get(key))
        safe[f"{key}_readable"] = secretbox.readable(config.get(key)) if config.get(key) else True
    oauth = dict(config.get("oauth") or {})
    for key in OAUTH_SECRET_FIELDS:
        value = oauth.pop(key, "")
        oauth[f"{key}_set"] = bool(value)
        if value:
            oauth[f"{key}_readable"] = secretbox.readable(value)
    safe["oauth"] = oauth
    safe["ready"] = is_ready(config)
    return safe


async def _store(db: AsyncSession, config: dict) -> None:
    row = (await db.execute(select(Setting).where(Setting.key == SETTING_KEY))).scalar_one_or_none()
    if row:
        row.value = config
    else:
        db.add(Setting(key=SETTING_KEY, value=config, description="Mailversand"))
    await db.commit()


async def save_config(db: AsyncSession, incoming: dict) -> dict:
    """Prueft und speichert. Leere Passwortfelder lassen das alte stehen."""
    config = await load_config(db)
    mode = (incoming.get("mode") or config["mode"]).strip()
    if mode not in MODES:
        raise ValueError(f"Unbekannte Betriebsart '{mode}'. Erlaubt: {', '.join(MODES)}.")

    for key in ("from_address", "from_name", "smtp_host", "smtp_user", "preset",
                "myhostname", "relay_host", "relay_user", "encryption"):
        if incoming.get(key) is not None:
            config[key] = _clean_line(incoming[key], 254)
    for key in ("smtp_port", "relay_port"):
        if incoming.get(key) is not None:
            port = int(incoming[key])
            if not 1 <= port <= 65535:
                raise ValueError(f"'{key}' muss zwischen 1 und 65535 liegen.")
            config[key] = port
    if incoming.get("verify_certificate") is not None:
        config["verify_certificate"] = bool(incoming["verify_certificate"])
    if incoming.get("default_recipients") is not None:
        recipients = []
        for address in incoming["default_recipients"]:
            address = _clean_line(address, 254)
            if not address:
                continue
            if not valid_address(address):
                raise ValueError(f"'{address}' ist keine gültige E-Mail-Adresse.")
            recipients.append(address)
        config["default_recipients"] = recipients

    # Leeres Feld = unveraendert. Sonst waere das Passwort nach jedem Speichern
    # weg, weil die Oberflaeche es nie zurueckbekommt.
    for key in SECRET_FIELDS:
        value = (incoming.get(key) or "").strip()
        if value:
            config[key] = secretbox.seal(value)
        if incoming.get(f"clear_{key}"):
            config[key] = ""

    config["mode"] = mode
    if config["encryption"] not in ENCRYPTIONS:
        raise ValueError(f"Unbekannte Verschlüsselung. Erlaubt: {', '.join(ENCRYPTIONS)}.")

    if mode in ("google", "microsoft"):
        oauth = config.get("oauth") or {}
        if oauth.get("provider") != mode or not oauth.get("refresh_token"):
            raise ValueError("Zuerst im Assistenten mit dem Konto anmelden - dann ist der "
                             "Versand über diesen Weg eingerichtet.")
        config["from_address"] = oauth.get("account") or config["from_address"]

    if mode != "off":
        if not valid_address(config["from_address"]):
            raise ValueError("Es fehlt eine gültige Absenderadresse.")
        if mode == "relay" and not config["smtp_host"]:
            raise ValueError("Für einen vorhandenen Mailserver fehlt der Servername.")

    if mode == "container":
        # Der Container spricht intern immer unverschluesselt auf 587 - er steht
        # im selben Docker-Netz. Nach aussen verschluesselt Postfix selbst.
        config["smtp_host"] = "logbot-postfix"
        config["smtp_port"] = 587
        config["encryption"] = "none"
        config["smtp_user"] = ""
        config["smtp_password"] = ""

    await _store(db, config)

    written = None
    if mode == "container":
        written = await write_postfix_env(config)

    logger.warning("Mail-Einstellung gespeichert (Betriebsart: %s)", mode)
    result = public_config(config)
    result["postfix_file_written"] = written
    return result


async def save_oauth(db: AsyncSession, provider: str, oauth: dict, activate: bool = True) -> dict:
    """Haelt das Ergebnis einer OAuth-Anmeldung fest (vom Assistenten aufgerufen)."""
    config = await load_config(db)
    stored = dict(oauth)
    for key in OAUTH_SECRET_FIELDS:
        if stored.get(key):
            stored[key] = secretbox.seal(stored[key])
    stored["provider"] = provider
    stored["connected_at"] = datetime.utcnow().isoformat()
    config["oauth"] = stored
    if activate:
        config["mode"] = provider
        if stored.get("account"):
            config["from_address"] = stored["account"]
    await _store(db, config)
    return public_config(config)


async def disconnect_oauth(db: AsyncSession) -> dict:
    config = await load_config(db)
    if config["mode"] in ("google", "microsoft"):
        config["mode"] = "off"
    config["oauth"] = {}
    await _store(db, config)
    return public_config(config)


# =============================================================================
# Die Datei fuer den Postfix-Container
# =============================================================================
def render_postfix_env(config: dict) -> str:
    """Baut den Inhalt von data/postfix/settings.env.

    Jeder Wert geht durch `_clean_line`: ein Zeilenumbruch in einem Feld waere
    sonst eine zusaetzliche, frei gewaehlte Variable fuer den Container.
    """
    hostname = _clean_line(config.get("myhostname")) or "logbot.local"
    domain = _clean_line((config.get("from_address") or "@local").split("@", 1)[-1])

    lines = [
        "# ==========================================================================",
        "# Von LogBot erzeugt - NICHT von Hand bearbeiten.",
        "# Einzustellen unter Meldungen -> E-Mail. Diese Datei wird bei jedem",
        "# Speichern neu geschrieben; Aenderungen hier gehen verloren.",
        f"# Erzeugt: {datetime.utcnow().isoformat()}Z",
        "# ==========================================================================",
        f"POSTFIX_myhostname={hostname}",
        f"ALLOWED_SENDER_DOMAINS={domain}",
        # Der Container darf nur aus dem Docker-Netz annehmen. Ein offenes Relay
        # im Internet ist binnen Stunden als Spamschleuder in Benutzung.
        # (Der Port ist nur an 127.0.0.1 gebunden; die privaten Bereiche sind
        # noetig, weil Docker seine Netze je nach Host auch aus 192.168/16 nimmt.)
        "MYNETWORKS=127.0.0.0/8,172.16.0.0/12,192.168.0.0/16,10.0.0.0/8",
    ]

    # Smarthost: die meisten Anschluesse duerfen nicht selbst zustellen (Port 25
    # gesperrt, kein PTR-Eintrag). Dann uebergibt Postfix an den Provider.
    if config.get("relay_host"):
        lines.append(f"RELAYHOST={_clean_line(config['relay_host'])}:{int(config.get('relay_port', 587))}")
        if config.get("relay_user"):
            lines.append(f"RELAYHOST_USERNAME={_clean_line(config['relay_user'])}")
            lines.append(f"RELAYHOST_PASSWORD={_clean_line(secretbox.open_(config.get('relay_password', '')))}")
        lines.append("RELAYHOST_TLS_LEVEL=encrypt")

    lines.append("")
    return "\n".join(lines)


async def write_postfix_env(config: dict) -> dict:
    """Schreibt die Datei auf den Host, damit der Container sie lesen kann."""
    if not hostexec.nsenter_available():
        return {"written": False,
                "reason": ("Kein Zugriff auf den Host — die Postfix-Datei konnte nicht "
                           "geschrieben werden. Auf der Kommandozeile: den Inhalt aus "
                           "der Vorschau nach data/postfix/settings.env kopieren.")}

    path = f"{hostexec.host_paths()['install_dir']}/{POSTFIX_ENV_RELATIVE}"
    # 0600: da steht gegebenenfalls das Relay-Passwort drin.
    result = await hostexec.write_host_file(path, render_postfix_env(config), mode="0600")
    if not result.ok:
        return {"written": False,
                "reason": (result.error or result.stderr or "unbekannter Fehler").strip()}
    return {"written": True, "path": path,
            "note": "Damit es gilt, muss der Postfix-Container neu gestartet werden."}


# =============================================================================
# Nachricht bauen
# =============================================================================
def build_message(config: dict, recipients: List[str], subject: str, body: str,
                  html: Optional[str] = None) -> EmailMessage:
    message = EmailMessage()
    message["From"] = formataddr((_clean_line(config.get("from_name")) or "LogBot",
                                  _clean_line(config["from_address"])))
    message["To"] = ", ".join(_clean_line(r) for r in recipients)
    message["Subject"] = _clean_line(subject, 200)
    message["Date"] = formatdate(localtime=True)
    domain = (config.get("from_address") or "logbot.local").split("@")[-1]
    message["Message-ID"] = make_msgid(domain=_clean_line(domain) or "logbot.local")
    # Damit Abwesenheitsnotizen und Weiterleitungsschleifen nicht zurueckkommen.
    message["Auto-Submitted"] = "auto-generated"
    message.set_content(body)
    if html:
        message.add_alternative(html, subtype="html")
    return message


# =============================================================================
# Senden: SMTP
# =============================================================================
def _connect(config: dict) -> smtplib.SMTP:
    host = config["smtp_host"]
    port = int(config["smtp_port"])
    encryption = config.get("encryption", "starttls")
    timeout = 30

    context = ssl.create_default_context()
    if not config.get("verify_certificate", True):
        # Bewusste Ausnahme fuer interne Server mit eigenem Zertifikat.
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

    if encryption == "tls":
        server = smtplib.SMTP_SSL(host, port, timeout=timeout, context=context)
    else:
        server = smtplib.SMTP(host, port, timeout=timeout)
        if encryption == "starttls":
            server.starttls(context=context)

    if config.get("smtp_user"):
        server.login(config["smtp_user"], secretbox.open_(config.get("smtp_password", "")))
    return server


def _send_smtp(config: dict, message: EmailMessage) -> dict:
    try:
        server = _connect(config)
    except (OSError, smtplib.SMTPException, ssl.SSLError) as exc:
        raise RuntimeError(
            f"Der Mailserver {config['smtp_host']}:{config['smtp_port']} war nicht "
            f"erreichbar: {exc}") from exc
    try:
        refused = server.send_message(message)
    except smtplib.SMTPAuthenticationError as exc:
        raise RuntimeError(f"Anmeldung am Mailserver abgelehnt: {exc}") from exc
    except smtplib.SMTPException as exc:
        raise RuntimeError(f"Der Mailserver hat die Nachricht abgelehnt: {exc}") from exc
    finally:
        try:
            server.quit()
        except Exception:                                           # defensiv
            pass
    return {"refused": {a: str(r) for a, r in (refused or {}).items()},
            "via": f"{config['smtp_host']}:{config['smtp_port']}"}


# =============================================================================
# Senden: Google und Microsoft
# =============================================================================
async def _send_google(config: dict, message: EmailMessage) -> dict:
    from . import mailoauth

    token = await mailoauth.access_token(config)
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            headers={"Authorization": f"Bearer {token}"}, json={"raw": raw})
    if response.status_code >= 400:
        raise RuntimeError(f"Google hat den Versand abgelehnt (HTTP {response.status_code}): "
                           f"{mailoauth.error_text(response)}")
    return {"via": "Gmail-API", "id": (response.json() or {}).get("id")}


async def _send_microsoft(config: dict, recipients: List[str], subject: str, body: str,
                          html: Optional[str]) -> dict:
    from . import mailoauth

    token = await mailoauth.access_token(config)
    payload = {
        "message": {
            "subject": _clean_line(subject, 200),
            "body": {"contentType": "HTML" if html else "Text", "content": html or body},
            "toRecipients": [{"emailAddress": {"address": r}} for r in recipients],
        },
        "saveToSentItems": False,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post("https://graph.microsoft.com/v1.0/me/sendMail",
                                     headers={"Authorization": f"Bearer {token}"}, json=payload)
    if response.status_code >= 400:
        hint = ""
        if response.status_code in (401, 403):
            hint = (" Hat das Konto ein Postfach (Exchange-Lizenz) und wurde die Berechtigung "
                    "„Mail.Send“ erteilt?")
        raise RuntimeError(f"Microsoft hat den Versand abgelehnt (HTTP {response.status_code}): "
                           f"{mailoauth.error_text(response)}.{hint}")
    return {"via": "Microsoft Graph"}


async def send(config: dict, recipients: List[str], subject: str, body: str,
               html: Optional[str] = None) -> dict:
    """Verschickt eine Mail auf dem eingestellten Weg. Wirft bei Fehlern."""
    mode = config.get("mode", "off")
    if mode == "off":
        raise ValueError("Der Mailversand ist ausgeschaltet.")
    recipients = [r.strip() for r in recipients if r and r.strip()]
    if not recipients:
        raise ValueError("Es wurde kein Empfänger angegeben.")
    for recipient in recipients:
        if not valid_address(recipient):
            raise ValueError(f"'{recipient}' ist keine gültige E-Mail-Adresse.")

    message = build_message(config, recipients, subject, body, html)
    if mode == "google":
        result = await _send_google(config, message)
    elif mode == "microsoft":
        result = await _send_microsoft(config, recipients, subject, body, html)
    else:
        result = await asyncio.to_thread(_send_smtp, config, message)
    result.update({"sent": True, "recipients": recipients,
                   "at": datetime.utcnow().isoformat()})
    return result


async def send_test(config: dict, recipient: str = "") -> dict:
    """Verschickt eine Probemail."""
    targets = [recipient.strip()] if recipient.strip() else list(config.get("default_recipients") or [])
    if not targets:
        raise ValueError("Es fehlt ein Empfänger für die Probemail.")

    body = (
        "Das ist eine Probemail von LogBot.\n\n"
        f"Weg        : {MODES.get(config.get('mode', 'off'), {}).get('label', '?')}\n"
        f"Absender   : {config.get('from_address')}\n"
        f"Zeitpunkt  : {datetime.utcnow().isoformat()}Z\n\n"
        "Kommt diese Mail an, funktioniert der Versand.\n"
    )
    return await send(config, targets, "LogBot — Probemail", body)


async def send_system_mail(db: AsyncSession, recipients: List[str], subject: str, body: str,
                           html: Optional[str] = None) -> dict:
    """Fuer Konto-Mails (Reset, Bestaetigung): wirft, wenn kein Versand eingerichtet ist."""
    config = await load_config(db)
    if not is_ready(config):
        raise RuntimeError("Auf diesem Server ist noch kein Mailversand eingerichtet "
                           "(Meldungen → Kanäle → E-Mail).")
    return await send(config, recipients, subject, body, html)
