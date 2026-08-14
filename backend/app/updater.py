# ==============================================================================
# Name:        Phydran6
# Kontakt:     Phydran6
# Version:     2026.08.14.12.00.00
# Changelog:   ../../CHANGELOG/backend.md
# Beschreibung: LogBot - Patchmanagement: Versionsvergleich, Update, Rueckfall
# ==============================================================================
"""
Vergleicht den installierten Stand mit dem Stand auf GitHub und stoesst Update
bzw. Rueckfall an.

Aufgabenteilung:

* Dieses Modul redet mit GitHub, liest den Zustand vom Host und startet das
  Wartungsskript. Es fuehrt selbst *keine* Docker-Befehle aus.
* Das eigentliche Update macht `scripts/logbot-update.sh` auf dem Host. Das
  Skript wird bei jedem Lauf frisch aus dem Container auf den Host geschrieben,
  damit Skript und Backend nie auseinanderlaufen (und damit eine alte
  Installation ohne dieses Skript trotzdem aktualisiert werden kann).

Zustandsfuehrung: Das Skript schreibt fortlaufend nach
`<install>/data/update-state.json`. Die Oberflaeche fragt diesen Zustand ab.
Das ist bewusst eine Datei auf dem Host und keine Tabelle in der Datenbank -
waehrend eines Updates ist die Datenbank zeitweise nicht erreichbar.
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

import httpx

from .config import settings
from . import hostexec

logger = logging.getLogger("logbot.updater")

# Repository, gegen das geprueft wird. Ueberschreibbar fuer Forks/Testzweige.
REPO_SLUG = os.getenv("LOGBOT_REPO_SLUG", "Phydran6/Logbot-Server")
REPO_BRANCH = os.getenv("LOGBOT_BRANCH", "main")
REPO_URL = os.getenv("LOGBOT_REPO", f"https://github.com/{REPO_SLUG}.git")

_API = "https://api.github.com"

# GitHub erlaubt ohne Anmeldung 60 Anfragen pro Stunde - deshalb zwischenspeichern.
_REMOTE_CACHE_TTL = int(os.getenv("UPDATE_CHECK_CACHE_SECONDS", "900"))
_remote_cache: Optional[dict] = None
_remote_cache_expires: float = 0.0

# Das Wartungsskript liegt im Backend-Image und wird vor jedem Lauf auf den Host
# geschrieben.
SCRIPT_SOURCE = Path(__file__).resolve().parent.parent / "scripts" / "logbot-update.sh"


# =============================================================================
# Installierter Stand (Host)
# =============================================================================
async def local_state() -> dict:
    """Was ist gerade installiert? Version, Git-Stand, Verzeichnis."""
    paths = hostexec.host_paths()
    state = {
        "version": settings.app_version,
        "install_dir": paths["install_dir"],
        "branch": REPO_BRANCH,
        "commit": None,
        "commit_short": None,
        "commit_date": None,
        "is_git": False,
        "host_access": hostexec.nsenter_available(),
        "note": "",
    }

    if not state["host_access"]:
        state["note"] = ("Kein Zugriff auf den Host - Version stammt aus dem laufenden "
                         "Container. Update ueber die Oberflaeche ist nicht moeglich.")
        return state

    install_dir = paths["install_dir"]

    # Alles in einem Aufruf: drei einzelne Host-Befehle kosten sonst je nach Last
    # mehrere Sekunden, und der Systemcheck hat ein Zeitlimit.
    # `safe.directory` verhindert Gits Beschwerde ueber fremde Besitzverhaeltnisse.
    script = (
        f'head -n1 "{install_dir}/VERSION" 2>/dev/null; echo "---"; '
        f'git -c safe.directory="{install_dir}" -C "{install_dir}" rev-parse HEAD 2>/dev/null; echo "---"; '
        f'git -c safe.directory="{install_dir}" -C "{install_dir}" log -1 --format=%cI 2>/dev/null'
    )
    result = await hostexec.run_host(["sh", "-c", script], timeout=15.0)
    if not result.ok:
        state["note"] = ("Der Zustand der Installation auf dem Host war nicht lesbar: "
                         + (result.error or result.stderr or "unbekannter Fehler").strip())
        return state

    parts = (result.stdout or "").split("---")
    version = parts[0].strip() if len(parts) > 0 else ""
    commit = parts[1].strip() if len(parts) > 1 else ""
    commit_date = parts[2].strip() if len(parts) > 2 else ""

    if version:
        state["version"] = version.splitlines()[0].strip()
    if commit:
        state["is_git"] = True
        state["commit"] = commit
        state["commit_short"] = commit[:7]
        state["commit_date"] = commit_date or None
    else:
        state["note"] = ("Die Installation ist kein Git-Repository. Das Update holt die "
                         "Dateien dann per frischem Clone von GitHub.")

    return state


# =============================================================================
# Stand auf GitHub
# =============================================================================
async def remote_state(force: bool = False) -> dict:
    """Neuester Stand im Repository. Ergebnis wird zwischengespeichert."""
    global _remote_cache, _remote_cache_expires

    if not force and _remote_cache and time.time() < _remote_cache_expires:
        return _remote_cache

    info = {
        "repo": REPO_SLUG,
        "branch": REPO_BRANCH,
        "reachable": False,
        "commit": None,
        "commit_short": None,
        "commit_date": None,
        "commit_message": None,
        "version": None,
        "error": None,
        "checked_at": time.time(),
    }

    headers = {"Accept": "application/vnd.github+json", "User-Agent": "LogBot-Updater"}
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        async with httpx.AsyncClient(timeout=12.0, headers=headers) as client:
            response = await client.get(f"{_API}/repos/{REPO_SLUG}/commits/{REPO_BRANCH}")
            if response.status_code == 404:
                info["error"] = f"Repository oder Branch nicht gefunden ({REPO_SLUG}@{REPO_BRANCH})."
                return _cache_remote(info)
            if response.status_code == 403:
                info["error"] = ("GitHub hat die Anfrage abgelehnt (Limit fuer anonyme Abfragen). "
                                 "Spaeter erneut versuchen oder GITHUB_TOKEN setzen.")
                return _cache_remote(info)
            response.raise_for_status()
            data = response.json()

            info["reachable"] = True
            info["commit"] = data.get("sha")
            info["commit_short"] = (data.get("sha") or "")[:7] or None
            commit = data.get("commit") or {}
            info["commit_message"] = (commit.get("message") or "").strip().splitlines()[0] if commit.get("message") else None
            info["commit_date"] = ((commit.get("committer") or {}).get("date")
                                   or (commit.get("author") or {}).get("date"))

            # VERSION-Datei ist optional - fehlt sie, bleibt der Commit der Massstab.
            try:
                raw = await client.get(
                    f"https://raw.githubusercontent.com/{REPO_SLUG}/{REPO_BRANCH}/VERSION"
                )
                if raw.status_code == 200 and raw.text.strip():
                    info["version"] = raw.text.strip().splitlines()[0].strip()
            except httpx.HTTPError:
                pass

    except httpx.HTTPError as exc:
        info["error"] = f"GitHub nicht erreichbar: {exc}"
    except Exception as exc:                                   # defensiv
        info["error"] = f"Update-Pruefung fehlgeschlagen: {exc}"

    return _cache_remote(info)


def _cache_remote(info: dict) -> dict:
    global _remote_cache, _remote_cache_expires
    _remote_cache = info
    # Fehlschlaege nur kurz merken, damit ein Klick auf "Erneut pruefen" hilft.
    _remote_cache_expires = time.time() + (_REMOTE_CACHE_TTL if info.get("reachable") else 60)
    return info


# =============================================================================
# Gesamtbild
# =============================================================================
def compare(local: dict, remote: dict) -> tuple:
    """Ist ein Update da? Gibt (verfuegbar, Begruendung) zurueck."""
    if not remote.get("reachable"):
        return False, (remote.get("error") or "Stand auf GitHub unbekannt.")
    if local.get("commit") and remote.get("commit"):
        available = local["commit"] != remote["commit"]
        return available, ("Auf GitHub liegt ein neuerer Stand." if available
                           else "Der installierte Stand entspricht GitHub.")
    if remote.get("version"):
        available = remote["version"] != local.get("version")
        return available, ("Auf GitHub steht eine andere Version." if available
                           else "Die Version entspricht dem Stand auf GitHub.")
    return False, "Kein Vergleich moeglich (weder Commit noch VERSION-Datei lesbar)."


async def version_check(force: bool = False) -> dict:
    """Nur der Versionsvergleich - ohne Sicherungen und Laufzustand.

    Der Systemcheck nutzt diesen schlanken Weg; die Update-Seite das volle Bild.
    """
    local = await local_state()
    remote = await remote_state(force=force)
    available, reason = compare(local, remote)
    return {"local": local, "remote": remote,
            "update_available": available, "reason": reason}


async def update_status(force: bool = False) -> dict:
    """Installierter Stand + GitHub-Stand + Bewertung + laufender Vorgang."""
    local = await local_state()
    remote = await remote_state(force=force)
    run = await read_run_state()
    backups = await list_backups()
    available, reason = compare(local, remote)

    return {
        "local": local,
        "remote": remote,
        "update_available": available,
        "reason": reason,
        "repo_url": REPO_URL,
        "run": run,
        "backups": backups,
        "can_update": bool(local.get("host_access")),
        "oneliner": (
            f"curl -sSL https://raw.githubusercontent.com/{REPO_SLUG}/{REPO_BRANCH}/install.sh "
            f"| sudo bash -s -- update -y"
        ),
    }


# =============================================================================
# Laufender Vorgang
# =============================================================================
async def read_run_state() -> dict:
    """Liest den Zustand des letzten/laufenden Wartungslaufs vom Host."""
    paths = hostexec.host_paths()
    if not hostexec.nsenter_available():
        return {"status": "unknown", "message": "Kein Zugriff auf den Host."}

    raw = await hostexec.read_host_file(paths["state_file"])
    if not raw:
        return {"status": "idle", "message": "Bisher kein Update ueber die Oberflaeche gelaufen."}
    try:
        state = json.loads(raw)
    except json.JSONDecodeError:
        return {"status": "unknown", "message": "Zustandsdatei ist unlesbar."}
    if not isinstance(state, dict):
        return {"status": "unknown", "message": "Zustandsdatei hat ein unerwartetes Format."}
    return state


async def read_run_log(lines: int = 200) -> list:
    """Die letzten Zeilen des Wartungsprotokolls."""
    paths = hostexec.host_paths()
    raw = await hostexec.read_host_file(paths["log_file"], timeout=15.0)
    if raw is None:
        return []
    return hostexec.split_lines(raw, limit=lines)


async def list_backups() -> list:
    """Vorhandene Sicherungen (fuer den Rueckfall).

    Bewusst ein einziger Host-Aufruf: pro Sicherung einzeln nachzufragen dauert
    auf einem beschaeftigten Server zu lange. Jede Zeile ist
    `Name<TAB>Groesse<TAB>backup.json in einer Zeile`.
    """
    paths = hostexec.host_paths()
    if not hostexec.nsenter_available():
        return []

    root = paths["backup_dir"]
    script = (
        f'[ -d "{root}" ] || exit 0; '
        f'for name in $(ls -1 "{root}" 2>/dev/null | sort -r | head -n 20); do '
        f'  size=$(du -sh "{root}/$name" 2>/dev/null | cut -f1); '
        f'  meta=$(cat "{root}/$name/backup.json" 2>/dev/null | tr -d "\\n\\r"); '
        f'  printf "%s\\t%s\\t%s\\n" "$name" "$size" "$meta"; '
        f'done'
    )
    result = await hostexec.run_host(["sh", "-c", script], timeout=25.0)
    if not result.ok:
        return []

    backups = []
    for line in hostexec.split_lines(result.stdout, limit=20):
        parts = line.split("\t")
        name = parts[0].strip()
        if not name:
            continue
        entry = {"name": name, "created_at": None, "version": None, "commit": None,
                 "database_dump": False, "size": (parts[1].strip() if len(parts) > 1 else None)}
        if len(parts) > 2 and parts[2].strip():
            try:
                meta = json.loads(parts[2])
                entry.update({
                    "created_at": meta.get("created_at"),
                    "version": meta.get("version"),
                    "commit": meta.get("commit"),
                    "database_dump": bool(meta.get("database_dump")),
                })
            except (json.JSONDecodeError, TypeError):
                pass
        backups.append(entry)
    return backups


# =============================================================================
# Wartungslauf starten
# =============================================================================
async def _install_script() -> Optional[str]:
    """Legt das Wartungsskript auf dem Host ab. Gibt einen Fehlertext zurueck."""
    if not SCRIPT_SOURCE.exists():
        return f"Wartungsskript fehlt im Image ({SCRIPT_SOURCE})."
    content = SCRIPT_SOURCE.read_text(encoding="utf-8")
    # Zeilenenden vereinheitlichen - eine CRLF-Datei startet auf Linux nicht.
    content = content.replace("\r\n", "\n")
    paths = hostexec.host_paths()
    result = await hostexec.write_host_file(paths["script"], content, mode="0750")
    if not result.ok:
        return (result.error or result.stderr or "Unbekannter Fehler").strip()
    return None


async def start_run(action: str, database_backup: bool = True,
                    backup_name: str = "") -> dict:
    """Startet `apply` oder `rollback` auf dem Host.

    Kehrt sofort zurueck - der Lauf ersetzt waehrenddessen diesen Container.
    """
    if action not in ("apply", "rollback"):
        raise ValueError(f"Unbekannte Aktion: {action}")

    if not hostexec.nsenter_available():
        return {"started": False,
                "error": ("Kein Zugriff auf den Host. Update ueber die Oberflaeche ist nur "
                          "moeglich, wenn das Backend mit privileged/pid:host laeuft "
                          "(Standard-docker-compose.yml).")}

    running = await read_run_state()
    if running.get("status") == "running":
        return {"started": False,
                "error": "Es laeuft bereits ein Wartungsvorgang.",
                "run": running}

    script_error = await _install_script()
    if script_error:
        return {"started": False, "error": f"Wartungsskript konnte nicht abgelegt werden: {script_error}"}

    paths = hostexec.host_paths()
    command = [
        "/bin/bash", paths["script"], action,
        "--dir", paths["install_dir"],
        "--repo", REPO_URL,
        "--branch", REPO_BRANCH,
    ]
    if action == "apply":
        command.append("--db-backup" if database_backup else "--no-db-backup")
    if action == "rollback" and backup_name:
        command.extend(["--backup", backup_name])

    unit = f"logbot-{action}-{int(time.time())}"
    result = await hostexec.spawn_host(command, unit_name=unit, log_path=paths["log_file"])
    if not result.ok:
        return {"started": False,
                "error": (result.error or result.stderr or "Start fehlgeschlagen").strip()}

    logger.warning("Wartungslauf '%s' gestartet (Unit %s)", action, unit)
    return {"started": True, "action": action, "unit": unit,
            "message": ("Update laeuft. Die Oberflaeche ist waehrenddessen kurz nicht "
                        "erreichbar - diese Seite meldet sich von selbst zurueck."
                        if action == "apply" else
                        "Rueckfall laeuft. Die Oberflaeche ist waehrenddessen kurz nicht erreichbar.")}
