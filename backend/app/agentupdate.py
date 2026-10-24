# ==============================================================================
# Name:        Phydran6
# Kontakt:     Phydran6
# Changelog:   ../../CHANGELOG/backend.md
# Beschreibung: LogBot - Agent-Updates: steuerbar, signiert, im Wartungsfenster
# ==============================================================================
"""
Agents aktualisieren sich selbst - so, wie man es einstellt.

Wie es ablaeuft
---------------
1. Mit jedem Server-Update kommt auch eine neue Fassung der Agents mit
   (`agents/install-linux.sh`, `agents/install-windows.ps1`, im Backend-Image
   unter /app/agents). Deren Version steht im Kopf der Datei.
2. Jeder Agent meldet sich jede Minute beim Server (`/api/agents/heartbeat`)
   und nennt dabei seine Fassung.
3. Ist der Server neuer, entscheidet die **Update-Regel**:
   * ``manual`` - erst, wenn ein Administrator "Jetzt aktualisieren" klickt
     (fuer ein Geraet oder alle). Voreinstellung.
   * ``auto``   - von selbst, aber nur im **Wartungsfenster** (Wochentage und
     Uhrzeit), hoechstens N Geraete gleichzeitig, und nach X Fehlschlaegen
     haelt die Verteilung an und meldet sich.
   * ``off``    - nie.
   Jedes Geraet kann davon abweichen (immer manuell, immer automatisch, nie).
4. Der Agent laedt das Paket, prueft **SHA-256 und die RSA-Unterschrift** des
   Servers (den oeffentlichen Schluessel hat er beim Einrichten bekommen),
   installiert es neben dem laufenden Dienst, startet neu und meldet das
   Ergebnis. Startet die neue Fassung nicht, nimmt er die alte zurueck.

Warum signiert, obwohl es HTTPS ist: viele Installationen nutzen ein
selbstsigniertes Zertifikat und damit `--insecure`. Ohne Unterschrift koennte
sich dann jeder im Netz dazwischenschalten und jedem Agent - der als root
laeuft - beliebigen Code unterschieben. Mit Unterschrift nicht.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple
from zoneinfo import ZoneInfo

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from . import secretbox
from .models import Agent, Setting

logger = logging.getLogger("logbot.agentupdate")

CONFIG_KEY = "agent_updates"
KEY_SETTING = "agent_signing_key"
AGENTS_DIR = Path(os.getenv("LOGBOT_AGENTS_DIR", "/app/agents"))
OFFER_TIMEOUT = timedelta(minutes=20)

FILES = {"linux": "install-linux.sh", "windows": "install-windows.ps1"}
VERSION_RE = {
    "linux": re.compile(r'^AGENT_VERSION="([0-9.]+)"', re.M),
    "windows": re.compile(r'^\$AGENT_VERSION\s*=\s*"([0-9.]+)"', re.M),
}

DEFAULT_CONFIG = {
    "mode": "manual",                 # manual | auto | off
    "window_days": [0, 1, 2, 3, 4, 5, 6],   # Mo=0 … So=6
    "window_start": "02:00",
    "window_end": "05:00",
    "timezone": "Europe/Berlin",
    "max_parallel": 5,
    "pause_after_failures": 3,
    "paused": False,
    "paused_reason": "",
}

POLICIES = ("manual", "auto", "never")


def parse_version(value: Optional[str]) -> tuple:
    parts = re.findall(r"\d+", value or "")
    return tuple(int(p) for p in parts) if parts else ()


# =============================================================================
# Pakete und Unterschrift
# =============================================================================
_package_cache: Dict[str, tuple] = {}


async def _read_file(os_name: str) -> Optional[str]:
    path = AGENTS_DIR / FILES[os_name]
    if path.is_file():
        return path.read_text(encoding="utf-8")
    # Aeltere Images ohne /app/agents: vom Host lesen (privileged-Betrieb).
    from . import hostexec
    host = f"{hostexec.host_paths()['install_dir']}/agents/{FILES[os_name]}"
    return await hostexec.read_host_file(host)


async def package(db: AsyncSession, os_name: str) -> Optional[dict]:
    """Das aktuelle Paket fuer ein Betriebssystem - mit Version, Abdruck, Unterschrift."""
    if os_name not in FILES:
        return None
    text = await _read_file(os_name)
    if not text:
        return None
    text = text.replace("\r\n", "\n") if os_name == "linux" else text
    content = text.encode("utf-8")
    digest = hashlib.sha256(content).hexdigest()
    cached = _package_cache.get(os_name)
    if cached and cached[0] == digest:
        return cached[1]
    match = VERSION_RE[os_name].search(text)
    private, _ = await signing_keys(db)
    signature = private.sign(content, padding.PKCS1v15(), hashes.SHA256())
    result = {"os": os_name, "version": match.group(1) if match else "", "sha256": digest,
              "signature": base64.b64encode(signature).decode("ascii"), "content": content,
              "size": len(content), "file": FILES[os_name]}
    _package_cache[os_name] = (digest, result)
    return result


_keys_cache: Optional[tuple] = None


async def signing_keys(db: AsyncSession) -> Tuple[rsa.RSAPrivateKey, dict]:
    """(privater Schluessel, oeffentliche Darstellungen) - beim ersten Mal erzeugt."""
    global _keys_cache
    if _keys_cache:
        return _keys_cache
    row = (await db.execute(select(Setting).where(Setting.key == KEY_SETTING))).scalar_one_or_none()
    private = None
    if row and isinstance(row.value, dict) and row.value.get("private_pem"):
        pem = secretbox.open_(row.value["private_pem"])
        if pem:
            private = serialization.load_pem_private_key(pem.encode(), password=None)
    if private is None:
        private = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        pem = private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption()).decode()
        value = {"private_pem": secretbox.seal(pem), "created_at": datetime.utcnow().isoformat()}
        if row:
            row.value = value
        else:
            db.add(Setting(key=KEY_SETTING, value=value,
                           description="Schlüssel, mit dem Agent-Updates unterschrieben werden"))
        await db.commit()
    public = private.public_key()
    public_pem = public.public_bytes(serialization.Encoding.PEM,
                                     serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    numbers = public.public_numbers()

    def _b64(n: int) -> str:
        return base64.b64encode(n.to_bytes((n.bit_length() + 7) // 8, "big")).decode()
    xml = (f"<RSAKeyValue><Modulus>{_b64(numbers.n)}</Modulus>"
           f"<Exponent>{_b64(numbers.e)}</Exponent></RSAKeyValue>")
    der = public.public_bytes(serialization.Encoding.DER,
                              serialization.PublicFormat.SubjectPublicKeyInfo)
    info = {"pem": public_pem, "xml": xml,
            "fingerprint": "SHA256:" + base64.b64encode(hashlib.sha256(der).digest()).decode().rstrip("=")}
    _keys_cache = (private, info)
    return _keys_cache


# =============================================================================
# Regel und Wartungsfenster
# =============================================================================
async def load_config(db: AsyncSession) -> dict:
    row = (await db.execute(select(Setting).where(Setting.key == CONFIG_KEY))).scalar_one_or_none()
    config = dict(DEFAULT_CONFIG)
    if row and isinstance(row.value, dict):
        config.update({k: v for k, v in row.value.items() if k in DEFAULT_CONFIG})
    return config


def _hhmm(value: str) -> Tuple[int, int]:
    match = re.match(r"^(\d{1,2}):(\d{2})$", str(value or ""))
    if not match or int(match.group(1)) > 23 or int(match.group(2)) > 59:
        raise ValueError(f"Ungültige Uhrzeit '{value}' (Form HH:MM).")
    return int(match.group(1)), int(match.group(2))


async def save_config(db: AsyncSession, incoming: dict) -> dict:
    config = await load_config(db)
    if "mode" in incoming:
        if incoming["mode"] not in ("manual", "auto", "off"):
            raise ValueError("Update-Regel muss manual, auto oder off sein.")
        config["mode"] = incoming["mode"]
    if "window_days" in incoming:
        days = sorted({int(d) for d in incoming["window_days"] if 0 <= int(d) <= 6})
        if not days:
            raise ValueError("Mindestens ein Wochentag gehört ins Wartungsfenster.")
        config["window_days"] = days
    for key in ("window_start", "window_end"):
        if key in incoming:
            _hhmm(incoming[key])
            config[key] = incoming[key]
    if "timezone" in incoming:
        try:
            ZoneInfo(incoming["timezone"])
        except Exception as exc:
            raise ValueError(f"Unbekannte Zeitzone '{incoming['timezone']}'.") from exc
        config["timezone"] = incoming["timezone"]
    if "max_parallel" in incoming:
        config["max_parallel"] = max(1, min(int(incoming["max_parallel"]), 100))
    if "pause_after_failures" in incoming:
        config["pause_after_failures"] = max(0, min(int(incoming["pause_after_failures"]), 50))
    if "paused" in incoming:
        config["paused"] = bool(incoming["paused"])
        if not config["paused"]:
            config["paused_reason"] = ""
    row = (await db.execute(select(Setting).where(Setting.key == CONFIG_KEY))).scalar_one_or_none()
    if row:
        row.value = config
    else:
        db.add(Setting(key=CONFIG_KEY, value=config, description="Agent-Updates: Regel und Wartungsfenster"))
    await db.commit()
    return config


def in_window(config: dict, now: Optional[datetime] = None) -> bool:
    """Liegt `now` (UTC) im Wartungsfenster? Fenster ueber Mitternacht gehen auch."""
    tz = ZoneInfo(config.get("timezone") or "Europe/Berlin")
    local = (now or datetime.utcnow()).replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
    start = _hhmm(config.get("window_start", "02:00"))
    end = _hhmm(config.get("window_end", "05:00"))
    minutes = local.hour * 60 + local.minute
    s, e = start[0] * 60 + start[1], end[0] * 60 + end[1]
    days = config.get("window_days") or []
    if s <= e:
        return local.weekday() in days and s <= minutes < e
    # Ueber Mitternacht: der Abschnitt nach Mitternacht gehoert zum Vortag.
    if minutes >= s:
        return local.weekday() in days
    if minutes < e:
        return (local.weekday() - 1) % 7 in days
    return False


def os_of(agent: Agent) -> Optional[str]:
    if agent.device_type == "linux_agent":
        return "linux"
    if agent.device_type == "windows_agent":
        return "windows"
    return None


def supports_update(agent: Agent) -> bool:
    caps = ((agent.extra_data or {}).get("agent") or {}).get("capabilities") or []
    return "self-update" in caps


def effective_policy(agent: Agent, config: dict) -> str:
    if agent.update_policy in POLICIES:
        return agent.update_policy
    return {"manual": "manual", "auto": "auto", "off": "never"}.get(config.get("mode"), "manual")


async def running_count(db: AsyncSession) -> int:
    rows = (await db.execute(select(Agent.update_state).where(Agent.parent_id.is_(None)))).all()
    return sum(1 for (state,) in rows if (state or {}).get("state") in ("offered", "installing"))


async def decide(db: AsyncSession, agent: Agent, target: Optional[dict], config: dict) -> Tuple[bool, str]:
    """Soll dieser Agent jetzt aktualisieren? (ja/nein, Begruendung)"""
    if not target or not target.get("version"):
        return False, "Kein Paket auf dem Server."
    if not supports_update(agent):
        return False, "Diese Agent-Fassung kann sich noch nicht selbst aktualisieren."
    if (agent.extra_data or {}).get("agent", {}).get("remote_update") is False:
        return False, "Auf dem Gerät ist die Fernaktualisierung abgeschaltet."
    if parse_version(agent.agent_version) >= parse_version(target["version"]):
        return False, "Aktuell."
    state = agent.update_state or {}
    if state.get("state") in ("offered", "installing") and state.get("version") == target["version"]:
        offered = state.get("offered_at")
        if offered and datetime.utcnow() - datetime.fromisoformat(offered) < OFFER_TIMEOUT:
            return False, "Update läuft bereits."
    if state.get("state") == "failed" and state.get("version") == target["version"] \
            and not agent.update_requested_at:
        return False, "Letzter Versuch mit dieser Fassung ist gescheitert - erneut von Hand anstoßen."
    policy = effective_policy(agent, config)
    if agent.update_requested_at:
        return True, "Von Hand angestoßen."
    if policy != "auto":
        return False, "Wartet auf Freigabe (manuell)."
    if config.get("paused"):
        return False, f"Automatische Verteilung pausiert: {config.get('paused_reason') or 'von Hand'}."
    if not in_window(config):
        return False, "Außerhalb des Wartungsfensters."
    if await running_count(db) >= int(config.get("max_parallel") or 5):
        return False, "Zu viele gleichzeitige Updates - kommt in der nächsten Runde."
    return True, "Im Wartungsfenster."


def offer(agent: Agent, target: dict, base_path: str) -> dict:
    """Die Anweisung an den Agent - und der festgehaltene Zustand."""
    agent.update_state = {"state": "offered", "version": target["version"],
                          "from_version": agent.agent_version,
                          "offered_at": datetime.utcnow().isoformat(), "message": ""}
    return {"action": "update", "version": target["version"], "sha256": target["sha256"],
            "signature": target["signature"], "size": target["size"],
            "url": f"{base_path}/api/agents/update/package/{target['os']}"}


async def failures_since(db: AsyncSession, version: str) -> int:
    rows = (await db.execute(select(Agent.update_state).where(Agent.parent_id.is_(None)))).all()
    return sum(1 for (state,) in rows
               if (state or {}).get("state") == "failed" and (state or {}).get("version") == version)


async def overview(db: AsyncSession) -> dict:
    """Wie steht die Verteilung? Fuer die Oberflaeche."""
    config = await load_config(db)
    packages = {}
    for os_name in FILES:
        pkg = await package(db, os_name)
        packages[os_name] = {"version": pkg["version"], "sha256": pkg["sha256"]} if pkg else None
    hosts = (await db.execute(select(Agent).where(
        Agent.parent_id.is_(None), Agent.device_type.in_(("linux_agent", "windows_agent"))))).scalars().all()
    counts = {"current": 0, "outdated": 0, "legacy": 0, "running": 0, "failed": 0}
    for agent in hosts:
        target = packages.get(os_of(agent) or "")
        state = (agent.update_state or {}).get("state")
        if state in ("offered", "installing"):
            counts["running"] += 1
        if state == "failed":
            counts["failed"] += 1
        if not supports_update(agent):
            counts["legacy"] += 1
        elif target and parse_version(agent.agent_version) < parse_version(target["version"]):
            counts["outdated"] += 1
        else:
            counts["current"] += 1
    _, key = await signing_keys(db)
    return {"config": config, "packages": packages, "counts": counts,
            "in_window_now": in_window(config), "signing_key_fingerprint": key["fingerprint"]}


async def outdated_count(db: AsyncSession) -> int:
    return (await overview(db))["counts"]["outdated"]


async def requested_any(db: AsyncSession) -> int:
    return (await db.execute(select(func.count(Agent.id)).where(
        Agent.update_requested_at.is_not(None)))).scalar() or 0
