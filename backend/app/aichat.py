# ==============================================================================
# Name:        Phydran6
# Kontakt:     Phydran6
# Changelog:   ../../CHANGELOG/backend.md
# Beschreibung: LogBot - KI-Chat: Fragen in Alltagssprache, die KI prueft selbst
# ==============================================================================
"""
"Ist im WLAN alles gut?" - und die Antwort kommt aus den Logs, nicht aus dem Bauch.

`ai.py` beantwortet eine Frage zu einer *fertigen Auswahl* von Logzeilen. Hier
weiss niemand vorher, welche Zeilen die richtigen sind. Zwei Wege:

* **Werkzeuge** (Anthropic, OpenAI, OpenRouter, Open WebUI): Die KI bekommt eine Handvoll
  Abfragen in die Hand - Logs durchsuchen, Geraeteliste, Ueberblick, Zustand
  des Servers - und entscheidet selbst, was sie nachsieht. Das ist der gute
  Weg: sie fragt gezielt nach, statt hundert Zeilen auf Verdacht zu bekommen.
* **Vorab gesammelt** (n8n, oder wenn ein Modell keine Werkzeuge kann): Der
  Server sammelt vor der Anfrage, was zur Frage passen duerfte - Ueberblick,
  Geraete, und Zeilen zu den Stichworten der Frage (aus "WLAN" wird wlan,
  wifi, wpa, hostapd, ssid ...).

Was den Server verlaesst, ist in beiden Faellen gedeckelt: hoechstens
`max_logs` Logzeilen pro Frage, ueber alle Werkzeugaufrufe zusammen. Die
Antwort sagt, wie viele Zeilen von welchen Geraeten rausgingen.

Der Verlauf liegt in der App, nicht hier: jede Anfrage bringt das Gespraech
mit. Der Server merkt sich nichts.
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import httpx
import psutil
from sqlalchemy import desc, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from . import ai, logparse
from .models import Agent, Log, Setting

logger = logging.getLogger("logbot.aichat")

MAX_ROUNDS = 6                  # Werkzeug-Runden pro Frage
MAX_HISTORY = 20                # so viele Nachrichten des Verlaufs gehen mit
MAX_MESSAGE_CHARS = 4000
MAX_TOOL_CHARS = 12_000         # Laenge einer Werkzeug-Antwort
CHAT_MAX_TOKENS = 8000

SEVERITY_RANK = {
    "emergency": 0, "emerg": 0, "panic": 0, "alert": 1, "critical": 2, "crit": 2,
    "error": 3, "err": 3, "warning": 4, "warn": 4, "notice": 5, "info": 6,
    "informational": 6, "debug": 7,
}


def levels_up_to(max_rank: int) -> List[str]:
    return [name for name, rank in SEVERITY_RANK.items() if rank <= max_rank]


# =============================================================================
# Stichworte: aus der Alltagsfrage werden Suchbegriffe
# =============================================================================
# Ausloeser (regulaerer Ausdruck auf die kleingeschriebene Frage) -> Begriffe,
# nach denen in Nachricht und Quelle gesucht wird. Bewusst grosszuegig: lieber
# eine Zeile zu viel finden als das eigentliche Problem uebersehen.
TOPICS: List[Tuple[str, List[str]]] = [
    (r"wlan|wifi|wi-fi|funk|access ?point|\bap\b|repeater|mesh",
     ["wlan", "wifi", "wi-fi", "wpa", "hostapd", "ssid", "deauth", "disassoc",
      "associat", "802.11", "radio", "roam", "beacon", "mesh", "repeater"]),
    (r"internet|online|wan|dsl|glasfaser|provider|verbindung|pppoe|modem",
     ["wan", "pppoe", "dsl", "internet", "uplink", "link down", "link up",
      "connection lost", "verbindung", "dns", "gateway", "timeout", "unreachable"]),
    (r"dns|namensaufl|aufl[oö]s",
     ["dns", "resolv", "nxdomain", "servfail", "named", "unbound", "dnsmasq", "pihole"]),
    (r"dhcp|ip-adress|ip adress|lease",
     ["dhcp", "lease", "dhcpd", "dnsmasq", "dhcpack", "dhcpnak", "address conflict"]),
    (r"vpn|wireguard|openvpn|ipsec|tunnel",
     ["vpn", "wireguard", "wg0", "openvpn", "ipsec", "strongswan", "tunnel", "handshake"]),
    (r"firewall|angriff|blockiert|gesperrt|attack|scan|einbruch|hack",
     ["firewall", "blocked", "drop", "deny", "reject", "ufw", "iptables", "nft",
      "attack", "scan", "intrusion", "fail2ban", "ban"]),
    (r"anmeld|login|passwort|ssh|zugriff|brute",
     ["login", "logon", "auth", "failed password", "invalid user", "sshd", "sudo",
      "authentication failure", "4625", "4624", "4740"]),
    (r"festplatte|platte|disk|speicherplatz|smart|raid|nas|dateisystem|volume",
     ["disk", "smart", "raid", "degraded", "i/o error", "filesystem", "ext4", "btrfs",
      "zfs", "no space", "read-only", "sector", "mdadm"]),
    (r"backup|sicherung",
     ["backup", "sicherung", "restic", "borg", "veeam", "rsync", "snapshot", "vss"]),
    (r"docker|container|stack|compose",
     ["docker", "container", "oom", "restart", "unhealthy", "exited", "compose"]),
    (r"speicher|ram|arbeitsspeicher|memory|oom",
     ["out of memory", "oom", "memory", "swap", "killed process"]),
    (r"cpu|last|langsam|temperatur|hitze|l[uü]fter",
     ["cpu", "load", "temperature", "thermal", "throttl", "fan", "overheat"]),
    (r"update|patch|aktualis",
     ["update", "upgrade", "apt", "dnf", "windows update", "wsus", "patch", "reboot required"]),
    (r"mail|postfix|smtp|e-mail",
     ["postfix", "smtp", "mail", "dovecot", "bounce", "deferred", "relay"]),
    (r"drucker|printer|druck",
     ["printer", "cups", "print", "spooler", "drucker"]),
    (r"strom|usv|ups|stromausfall|power",
     ["ups", "usv", "power", "battery", "on battery", "apcupsd", "nut", "shutdown"]),
    (r"neustart|reboot|absturz|crash|abgest[uü]rzt|h[aä]ngt",
     ["reboot", "restart", "shutdown", "panic", "crash", "segfault", "watchdog", "bugcheck",
      "unexpected", "kernel"]),
    (r"zertifikat|tls|ssl|https",
     ["certificate", "cert", "tls", "ssl", "expired", "handshake"]),
]


def topic_terms(question: str) -> List[str]:
    """Suchbegriffe zu einer Frage in Alltagssprache."""
    lowered = (question or "").lower()
    terms: List[str] = []
    for trigger, words in TOPICS:
        if re.search(trigger, lowered):
            for word in words:
                if word not in terms:
                    terms.append(word)
    return terms[:24]


# =============================================================================
# Werkzeuge
# =============================================================================
TOOLS: List[dict] = [
    {
        "name": "search_logs",
        "description": (
            "Durchsucht die Logzeilen. Gibt die neuesten Treffer zurück (Zeit UTC | Level | "
            "Gerät | Quelle | Text). Mehrere Begriffe werden ODER-verknüpft und in Nachricht "
            "und Quelle gesucht. Ohne Begriffe: einfach die neuesten Zeilen. Für Fragen zu "
            "einem Bereich (z.B. WLAN) mehrere passende Fachbegriffe angeben."),
        "parameters": {
            "type": "object",
            "properties": {
                "terms": {"type": "array", "items": {"type": "string"},
                          "description": "Suchbegriffe, ODER-verknüpft, Groß/klein egal"},
                "hostname": {"type": "string", "description": "Nur dieses Gerät (exakt)"},
                "min_severity": {
                    "type": "string",
                    "enum": ["emergency", "alert", "critical", "error", "warning",
                             "notice", "info", "debug"],
                    "description": "Dieses Level und alles Dringendere"},
                "hours": {"type": "integer", "minimum": 1, "maximum": 720,
                          "description": "Zeitraum rückwärts in Stunden, Standard 24"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 60,
                          "description": "Höchstzahl Zeilen, Standard 30"},
            },
        },
    },
    {
        "name": "log_overview",
        "description": (
            "Überblick über einen Zeitraum: Anzahl Zeilen je Level, Geräte mit den meisten "
            "Fehlern und die häufigsten Fehler-/Warnmeldungen (gruppiert). Guter erster Schritt."),
        "parameters": {
            "type": "object",
            "properties": {
                "hours": {"type": "integer", "minimum": 1, "maximum": 720},
                "hostname": {"type": "string", "description": "Nur dieses Gerät (exakt)"},
            },
        },
    },
    {
        "name": "list_devices",
        "description": ("Die überwachten Geräte mit Typ, IP, zuletzt gesehen und ob sie gerade "
                        "online sind (liefern Logs)."),
        "parameters": {
            "type": "object",
            "properties": {
                "only_offline": {"type": "boolean"},
                "search": {"type": "string", "description": "Teil von Name, IP oder Typ"},
            },
        },
    },
    {
        "name": "server_health",
        "description": "Zustand des Logbot-Servers selbst: CPU, Arbeitsspeicher, Platte, Datenbank.",
        "parameters": {"type": "object", "properties": {}},
    },
]


class ToolBox:
    """Fuehrt die Werkzeuge aus und haelt fest, was dabei rausging."""

    def __init__(self, db: AsyncSession, budget: int, scope_host: Optional[str]):
        self.db = db
        self.budget = max(1, budget)          # Logzeilen insgesamt
        self.scope_host = (scope_host or "").strip() or None
        self.lines_sent = 0
        self.hosts: set = set()
        self.calls: List[dict] = []

    async def run(self, name: str, args: Dict[str, Any]) -> str:
        args = args if isinstance(args, dict) else {}
        try:
            if name == "search_logs":
                result = await self._search_logs(args)
            elif name == "log_overview":
                result = await self._overview(args)
            elif name == "list_devices":
                result = await self._devices(args)
            elif name == "server_health":
                result = await self._health()
            else:
                result = f"Unbekanntes Werkzeug '{name}'."
        except Exception as exc:                                    # defensiv
            logger.warning("Werkzeug %s fehlgeschlagen: %s", name, exc)
            await self.db.rollback()
            result = f"Fehler beim Ausführen: {exc}"
        self.calls.append({"tool": name, "args": args})
        return result[:MAX_TOOL_CHARS]

    def _host(self, args: Dict[str, Any]) -> Optional[str]:
        # Ist der Chat an ein Geraet gebunden, gilt das fuer jede Abfrage.
        return self.scope_host or (str(args.get("hostname") or "").strip() or None)

    @staticmethod
    def _hours(args: Dict[str, Any], default: int = 24) -> int:
        try:
            return max(1, min(int(args.get("hours") or default), 720))
        except (TypeError, ValueError):
            return default

    async def _search_logs(self, args: Dict[str, Any]) -> str:
        remaining = self.budget - self.lines_sent
        if remaining <= 0:
            return ("Die Grenze für Logzeilen pro Frage ist erreicht. Antworte mit dem, was "
                    "schon vorliegt.")
        try:
            limit = max(1, min(int(args.get("limit") or 30), 60, remaining))
        except (TypeError, ValueError):
            limit = min(30, remaining)
        hours = self._hours(args)
        query = select(Log).where(Log.timestamp >= datetime.utcnow() - timedelta(hours=hours))
        host = self._host(args)
        if host:
            query = query.where(func.lower(Log.hostname) == host.lower())
        severity = str(args.get("min_severity") or "").strip().lower()
        if severity in SEVERITY_RANK:
            query = query.where(func.lower(Log.level).in_(levels_up_to(SEVERITY_RANK[severity])))
        terms = [str(t).strip() for t in (args.get("terms") or []) if str(t).strip()][:12]
        if terms:
            conditions = []
            for term in terms:
                pattern = f"%{term[:60]}%"
                conditions.append(Log.message.ilike(pattern))
                conditions.append(Log.source.ilike(pattern))
            query = query.where(or_(*conditions))

        rows = (await self.db.execute(query.order_by(desc(Log.id)).limit(limit))).scalars().all()
        if not rows:
            return (f"Keine Treffer in den letzten {hours} h"
                    + (f" auf {host}" if host else "") + ".")
        self.lines_sent += len(rows)
        lines = []
        for row in rows:
            self.hosts.add(row.hostname or "?")
            parsed = logparse.parse_log_row(row)
            text_value = (parsed.get("summary") or row.message or "").replace("\n", " ")[:400]
            stamp = row.timestamp.strftime("%Y-%m-%d %H:%M:%S") if row.timestamp else "?"
            lines.append(" | ".join([stamp, (row.level or "").upper(), row.hostname or "?",
                                     row.source or "", text_value]))
        header = f"{len(rows)} Treffer (neueste zuerst, {hours} h"
        header += f", Gerät {host}" if host else ""
        header += ", es gibt evtl. weitere)" if len(rows) == limit else ")"
        return header + "\n" + "\n".join(lines)

    async def _overview(self, args: Dict[str, Any]) -> str:
        hours = self._hours(args)
        since = datetime.utcnow() - timedelta(hours=hours)
        host = self._host(args)
        base = [Log.timestamp >= since]
        if host:
            base.append(func.lower(Log.hostname) == host.lower())

        by_level = (await self.db.execute(
            select(func.lower(Log.level), func.count(Log.id)).where(*base)
            .group_by(func.lower(Log.level)))).all()
        problem_levels = levels_up_to(SEVERITY_RANK["error"])
        by_host = (await self.db.execute(
            select(Log.hostname, func.count(Log.id))
            .where(*base, func.lower(Log.level).in_(problem_levels))
            .group_by(Log.hostname).order_by(desc(func.count(Log.id))).limit(10))).all()
        snippet = func.left(Log.message, 120)
        top = (await self.db.execute(
            select(Log.hostname, func.lower(Log.level), snippet, func.count(Log.id),
                   func.max(Log.timestamp))
            .where(*base, func.lower(Log.level).in_(levels_up_to(SEVERITY_RANK["warning"])))
            .group_by(Log.hostname, func.lower(Log.level), snippet)
            .order_by(desc(func.count(Log.id))).limit(15))).all()

        out = [f"Zeitraum: letzte {hours} h" + (f", Gerät {host}" if host else "")]
        total = sum(count for _, count in by_level)
        out.append(f"Zeilen gesamt: {total}")
        out.append("Je Level: " + (", ".join(f"{lvl or '?'}={count}" for lvl, count in
                                            sorted(by_level, key=lambda r: -r[1])) or "keine"))
        out.append("Geräte mit Fehlern (error und dringender): "
                   + (", ".join(f"{h or '?'}={c}" for h, c in by_host) or "keine"))
        if top:
            out.append("Häufigste Fehler/Warnungen (Gerät | Level | Anzahl | zuletzt | Text):")
            for hostname, level, message, count, last in top:
                self.hosts.add(hostname or "?")
                stamp = last.strftime("%Y-%m-%d %H:%M") if last else "?"
                out.append(f"- {hostname or '?'} | {level} | {count}x | {stamp} | "
                           f"{(message or '').replace(chr(10), ' ')}")
        else:
            out.append("Keine Fehler oder Warnungen im Zeitraum.")
        return "\n".join(out)

    async def _devices(self, args: Dict[str, Any]) -> str:
        cutoff = datetime.utcnow() - timedelta(seconds=await offline_timeout_seconds(self.db))
        query = select(Agent).order_by(Agent.hostname).limit(200)
        search = str(args.get("search") or "").strip()
        if self.scope_host:
            query = query.where(func.lower(Agent.hostname) == self.scope_host.lower())
        elif search:
            pattern = f"%{search[:60]}%"
            query = query.where(or_(Agent.hostname.ilike(pattern), Agent.ip_address.ilike(pattern),
                                    Agent.device_type.ilike(pattern)))
        agents = (await self.db.execute(query)).scalars().all()
        only_offline = bool(args.get("only_offline"))
        lines = []
        online_count = 0
        for agent in agents:
            online = bool(agent.last_seen and agent.last_seen >= cutoff)
            online_count += online
            if only_offline and online:
                continue
            seen = agent.last_seen.strftime("%Y-%m-%d %H:%M") if agent.last_seen else "nie"
            lines.append(f"- {agent.hostname} | {agent.device_type or '?'} | "
                         f"{agent.ip_address or '?'} | {'online' if online else 'OFFLINE'} | "
                         f"zuletzt {seen}")
        head = f"{len(agents)} Geräte, davon {online_count} online."
        return head + ("\n" + "\n".join(lines) if lines else "\n(keine passenden Geräte)")

    async def _health(self) -> str:
        disk = psutil.disk_usage("/")
        try:
            await self.db.execute(text("SELECT 1"))
            db_state = "erreichbar"
        except Exception:
            db_state = "NICHT erreichbar"
        return (f"CPU {psutil.cpu_percent(interval=None):.0f} %, "
                f"Arbeitsspeicher {psutil.virtual_memory().percent:.0f} %, "
                f"Platte {disk.percent:.0f} % belegt ({disk.free // (1024 ** 3)} GB frei), "
                f"Datenbank {db_state}.")


async def offline_timeout_seconds(db: AsyncSession) -> int:
    """Ab wann ein Geraet als offline gilt (Einstellung `agent_offline_timeout`)."""
    row = (await db.execute(
        select(Setting).where(Setting.key == "agent_offline_timeout"))).scalar_one_or_none()
    try:
        return max(30, int(row.value)) if row else 300
    except (TypeError, ValueError):
        return 300


# =============================================================================
# Anweisungen
# =============================================================================
def _system_prompt(config: dict, scope_host: Optional[str], with_tools: bool) -> str:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    parts = [
        "Du bist der Assistent in der Logbot-App. Logbot ist ein zentraler Log-Server, "
        "der die Logs der Rechner, Container und Netzwerkgeräte des Nutzers sammelt. "
        "Der Nutzer fragt am Handy in Alltagssprache, ob etwas in Ordnung ist oder was los war.",
        (
            "Prüfe mit den Werkzeugen nach, bevor du antwortest — beginne meist mit "
            "log_overview und list_devices und suche dann gezielt mit search_logs. Für einen "
            "Bereich wie 'WLAN' suche nach mehreren Fachbegriffen (wlan, wifi, wpa, hostapd, "
            "ssid, deauth …). Rate nicht: was nicht in den Logs steht, behauptest du nicht."
            if with_tools else
            "Unten stehen ein Überblick, die Geräteliste und zur Frage passende Logzeilen, die "
            "der Server vorab gesammelt hat. Stütze dich nur darauf; was dort fehlt, sagst du "
            "offen, statt zu raten."),
        "Antworte auf Deutsch und knapp, für einen kleinen Bildschirm: zuerst ein klares "
        "Urteil in einem Satz (alles in Ordnung / Auffälligkeiten / Problem), dann die Belege "
        "mit Gerät und Uhrzeit, dann was zu tun ist. Keine Tabellen, kurze Absätze oder "
        "Stichpunkte. Zeiten in den Logs sind UTC.",
        f"Aktuelle Zeit: {now} UTC.",
    ]
    if scope_host:
        parts.append(f"Dieses Gespräch betrifft nur das Gerät '{scope_host}'. Alle Abfragen "
                     "sind darauf beschränkt.")
    extra = (config.get("system_prompt") or "").strip()
    if extra:
        parts.append("Zusätzliche Vorgaben des Betreibers:\n" + extra)
    return "\n\n".join(parts)


def _clean_history(messages: List[dict]) -> List[dict]:
    """Nur user/assistant, abwechselnd, mit Text - so wie es die APIs erwarten."""
    cleaned: List[dict] = []
    for message in messages[-MAX_HISTORY:]:
        role = message.get("role")
        content = str(message.get("content") or "").strip()[:MAX_MESSAGE_CHARS]
        if role not in ("user", "assistant") or not content:
            continue
        if cleaned and cleaned[-1]["role"] == role:
            cleaned[-1]["content"] += "\n\n" + content
        else:
            cleaned.append({"role": role, "content": content})
    while cleaned and cleaned[0]["role"] != "user":
        cleaned.pop(0)
    if not cleaned or cleaned[-1]["role"] != "user":
        raise ValueError("Die letzte Nachricht muss eine Frage sein.")
    return cleaned


# =============================================================================
# Anbieter mit Werkzeugen
# =============================================================================
async def _chat_anthropic(config: dict, history: List[dict], system: str, box: ToolBox) -> dict:
    spec = ai.PROVIDERS["anthropic"]
    model = config.get("model") or spec["default_model"]
    tools = [{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
             for t in TOOLS]
    messages: List[dict] = [dict(m) for m in history]
    headers = {"x-api-key": config["api_key"], "anthropic-version": "2023-06-01",
               "content-type": "application/json"}

    async with httpx.AsyncClient(timeout=ai.REQUEST_TIMEOUT) as client:
        for _ in range(MAX_ROUNDS):
            response = await client.post(spec["endpoint"], headers=headers, json={
                "model": model, "max_tokens": CHAT_MAX_TOKENS, "system": system,
                "tools": tools, "messages": messages})
            data = ai._json_or_error(response, "Anthropic")
            content = data.get("content") or []
            stop = data.get("stop_reason")
            text_out = "".join(b.get("text", "") for b in content if b.get("type") == "text").strip()

            if stop == "refusal":
                return {"answer": text_out or "Die KI hat diese Anfrage abgelehnt.", "model": model}
            tool_uses = [b for b in content if b.get("type") == "tool_use"]
            # Bei max_tokens kann ein Werkzeugaufruf abgeschnitten sein - dann nichts ausfuehren.
            if stop != "tool_use" or not tool_uses:
                return {"answer": text_out or "(keine Antwort)", "model": data.get("model", model)}

            # Die Antwort unveraendert zurueckgeben (auch Denk-Bloecke), dann alle
            # Ergebnisse in *einer* Nachricht.
            messages.append({"role": "assistant", "content": content})
            results = []
            for block in tool_uses:
                output = await box.run(block.get("name", ""), block.get("input") or {})
                results.append({"type": "tool_result", "tool_use_id": block.get("id"),
                                "content": output})
            messages.append({"role": "user", "content": results})

    return {"answer": "Ich habe nach mehreren Prüfschritten keine abschließende Antwort "
                      "gefunden. Bitte die Frage enger fassen.", "model": model}


async def _chat_openai_like(config: dict, history: List[dict], system: str, box: ToolBox,
                            endpoint: str, who: str, default_model: str,
                            extra_headers: Optional[Dict[str, str]] = None) -> dict:
    model = config.get("model") or default_model
    tools = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                               "parameters": t["parameters"]}} for t in TOOLS]
    messages: List[dict] = [{"role": "system", "content": system}] + [dict(m) for m in history]
    headers = {"Authorization": f"Bearer {config['api_key']}", "Content-Type": "application/json",
               **(extra_headers or {})}

    async with httpx.AsyncClient(timeout=ai.REQUEST_TIMEOUT) as client:
        for _ in range(MAX_ROUNDS):
            body = {"model": model, "messages": messages, "tools": tools}
            if who == "Open WebUI":
                body["stream"] = False
            response = await client.post(endpoint, headers=headers, json=body)
            data = ai._json_or_error(response, who)
            choice = (data.get("choices") or [{}])[0]
            message = choice.get("message") or {}
            calls = message.get("tool_calls") or []
            if not calls:
                answer = (message.get("content") or "").strip()
                return {"answer": answer or "(keine Antwort)", "model": data.get("model", model)}

            messages.append({"role": "assistant", "content": message.get("content") or "",
                             "tool_calls": calls})
            for call in calls:
                function = call.get("function") or {}
                try:
                    args = json.loads(function.get("arguments") or "{}")
                except ValueError:
                    args = {}
                output = await box.run(function.get("name", ""), args)
                messages.append({"role": "tool", "tool_call_id": call.get("id"), "content": output})

    return {"answer": "Ich habe nach mehreren Prüfschritten keine abschließende Antwort "
                      "gefunden. Bitte die Frage enger fassen.", "model": model}


# =============================================================================
# Ohne Werkzeuge: vorab sammeln
# =============================================================================
async def _collect_context(box: ToolBox, question: str) -> str:
    sections = ["## Überblick (24 h)", await box.run("log_overview", {"hours": 24}),
                "## Geräte", await box.run("list_devices", {})]
    terms = topic_terms(question)
    if terms:
        sections += [f"## Zeilen zu den Stichworten ({', '.join(terms[:10])} …)",
                     await box.run("search_logs", {"terms": terms, "hours": 48, "limit": 40})]
    sections += ["## Neueste Fehler und Warnungen",
                 await box.run("search_logs", {"min_severity": "warning", "hours": 24, "limit": 40})]
    return "\n\n".join(sections)


async def _chat_with_context(config: dict, history: List[dict], system: str, box: ToolBox) -> dict:
    context = await _collect_context(box, history[-1]["content"])
    provider = config["provider"]
    full_system = system + "\n\n# Daten vom Server\n\n" + context

    if provider in ("n8n_external", "n8n_local"):
        # Dieselbe Form wie bei der Auswertung, ergaenzt um Verlauf und Kontext:
        # bestehende Workflows lesen `question` und laufen weiter.
        payload = {"question": history[-1]["content"], "messages": history,
                   "system": full_system, "context": context, "mode": "chat",
                   "generated_at": datetime.utcnow().isoformat(), "count": box.lines_sent,
                   "logs": []}
        return await ai._ask_n8n(config, payload)

    endpoint, who, default_model, extra_headers = _openai_target(config)
    model = config.get("model") or default_model
    if provider == "anthropic":
        spec = ai.PROVIDERS["anthropic"]
        async with httpx.AsyncClient(timeout=ai.REQUEST_TIMEOUT) as client:
            response = await client.post(spec["endpoint"], headers={
                "x-api-key": config["api_key"], "anthropic-version": "2023-06-01",
                "content-type": "application/json"}, json={
                "model": model, "max_tokens": CHAT_MAX_TOKENS, "system": full_system,
                "messages": history})
            data = ai._json_or_error(response, "Anthropic")
        answer = "".join(b.get("text", "") for b in data.get("content", [])
                         if b.get("type") == "text").strip()
        return {"answer": answer or "(keine Antwort)", "model": data.get("model", model)}

    body = {"model": model, "messages": [{"role": "system", "content": full_system}] + history}
    if who == "Open WebUI":
        body["stream"] = False
    async with httpx.AsyncClient(timeout=ai.REQUEST_TIMEOUT) as client:
        response = await client.post(endpoint, headers={
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json", **extra_headers}, json=body)
        data = ai._json_or_error(response, who)
    choice = (data.get("choices") or [{}])[0]
    answer = ((choice.get("message") or {}).get("content") or "").strip()
    return {"answer": answer or "(keine Antwort)", "model": data.get("model", model)}


def _openai_target(config: dict) -> Tuple[str, str, str, Dict[str, str]]:
    """Adresse, Name, Standardmodell und Zusatz-Kopfzeilen der OpenAI-artigen Anbieter."""
    provider = config["provider"]
    if provider == "openwebui":
        base = (config.get("webhook_url") or "").rstrip("/")
        endpoint = base if base.endswith("/chat/completions") else f"{base}/api/chat/completions"
        return endpoint, "Open WebUI", ai.PROVIDERS["openwebui"]["default_model"], {}
    if provider == "openrouter":
        spec = ai.PROVIDERS.get("openrouter", {})
        make_headers = getattr(ai, "openrouter_headers", None)
        extra = make_headers(config) if callable(make_headers) else {}
        return (spec.get("endpoint", "https://openrouter.ai/api/v1/chat/completions"), "OpenRouter",
                spec.get("default_model", ""), dict(extra or {}))
    spec = ai.PROVIDERS["openai"]
    return spec["endpoint"], "OpenAI", spec.get("default_model", ""), {}


# =============================================================================
# Einstieg
# =============================================================================
async def chat(db: AsyncSession, config: dict, messages: List[dict],
               hostname: Optional[str] = None) -> dict:
    """Beantwortet die letzte Frage im Verlauf - mit Blick in die Logs."""
    provider = config.get("provider", "off")
    if provider == "off":
        raise ValueError("Die KI-Anbindung ist ausgeschaltet.")
    history = _clean_history(messages)
    budget = int(config.get("max_logs") or ai.DEFAULT_LOGS)
    box = ToolBox(db, budget, hostname)
    started = time.time()
    mode = "tools"

    try:
        if provider == "anthropic":
            result = await _chat_anthropic(config, history, _system_prompt(config, box.scope_host, True), box)
        elif provider in ("openai", "openwebui", "openrouter"):
            endpoint, who, default_model, extra_headers = _openai_target(config)
            try:
                result = await _chat_openai_like(config, history,
                                                 _system_prompt(config, box.scope_host, True),
                                                 box, endpoint, who, default_model, extra_headers)
            except RuntimeError as exc:
                # Manche lokalen Modelle koennen keine Werkzeuge - dann eben vorab sammeln.
                if provider != "openwebui" or "HTTP 4" not in str(exc):
                    raise
                logger.info("Open WebUI ohne Werkzeuge, sammle vorab: %s", exc)
                mode = "context"
                box = ToolBox(db, budget, hostname)
                result = await _chat_with_context(config, history,
                                                  _system_prompt(config, box.scope_host, False), box)
        else:
            mode = "context"
            result = await _chat_with_context(config, history,
                                              _system_prompt(config, box.scope_host, False), box)
    except httpx.TimeoutException as exc:
        raise RuntimeError(f"Keine Antwort der KI innerhalb von {ai.REQUEST_TIMEOUT:.0f} Sekunden. "
                           "Bitte später noch einmal fragen.") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Verbindung zur KI fehlgeschlagen: {exc}") from exc

    return {
        "answer": result.get("answer", ""),
        "model": result.get("model", ""),
        "provider": provider,
        "provider_label": ai.PROVIDERS.get(provider, {}).get("label", ""),
        "mode": mode,
        "logs_sent": box.lines_sent,
        "hosts": sorted(h for h in box.hosts if h)[:30],
        "tools_used": box.calls[:20],
        "duration_seconds": round(time.time() - started, 1),
        "answered_at": datetime.utcnow().isoformat(),
    }
