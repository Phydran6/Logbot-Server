#!/bin/bash
# ==============================================================================
# Name:        Phydran6
# Kontakt:     Phydran6
# Version:     2026.10.23.12.00.00
# Changelog:   ../CHANGELOG/agents.md
# Beschreibung: LogBot Linux Agent - Installer (teilautomatisch)
#
#   Standard = HTTPS: ein schlanker Python-systemd-Dienst sendet ALLE Logs
#   (journald) verschluesselt + Token an  https://<FQDN>/api/agents/ingest
#   Alternativ Syslog (rsyslog -> UDP/TCP). Keine externen Abhaengigkeiten.
#
#   TEILAUTOMATISCH: Am Anfang laeuft ein 5s-Countdown. Wird eine Taste gedrueckt,
#   schaltet der Installer auf MANUELL und fragt ab da alle Werte blockierend ab
#   (kein Timeout). Ohne Tastendruck / ohne Terminal (Pipe/cron) laeuft alles
#   automatisch mit Standardwerten durch.
#
#   One-Liner (GitHub Raw), Werte per Umgebungsvariable:
#     curl -sSL https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/agents/install-linux.sh \
#       | LOGBOT_FQDN=logbot.example.com LOGBOT_TOKEN=xxxx sudo -E bash
#
#   ...oder per Parameter:
#     curl -sSL https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/agents/install-linux.sh \
#       | sudo bash -s -- --fqdn logbot.example.com --token xxxx
#
#   Deinstallieren:  sudo bash install-linux.sh uninstall
#   Testen:          sudo bash install-linux.sh test
# ==============================================================================

set -e

# ------------------------------------------------------------------------------
# PLATZHALTER (optional): Zum fest Eintragen einfach das fuehrende '#' entfernen
# und den Wert setzen. Dann laeuft der One-Liner voll automatisch - ohne dass
# man beim Start noch etwas eingeben muss. Parameter/Umgebungsvariablen haben
# Vorrang vor diesen Platzhaltern.
# ------------------------------------------------------------------------------
#PLACEHOLDER_FQDN="logbot.example.com"
#PLACEHOLDER_TOKEN="hier-agent-token-eintragen"
#PLACEHOLDER_MODE="https"      # https (Standard) oder syslog
#PLACEHOLDER_PORT="443"
#PLACEHOLDER_MINLEVEL="info"   # info | warning | error

# Farben
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

AGENT_VERSION="2026.10.23.12.00.00"

# --- Pfade: Syslog-Modus (rsyslog) ---
CONFIG_FILE="/etc/rsyslog.d/99-logbot.conf"
QUEUE_PREFIX="/var/spool/rsyslog/logbot_queue"

# --- Pfade: HTTPS-Modus (alles unter /opt/logbot-agent/*) ---
AGENT_DIR="/opt/logbot-agent"
AGENT_SCRIPT="${AGENT_DIR}/logbot_agent.py"
AGENT_CONFIG="${AGENT_DIR}/config.json"
AGENT_CURSOR="${AGENT_DIR}/cursor"
SERVICE_NAME="logbot-agent"
SYSTEMD_UNIT="/etc/systemd/system/${SERVICE_NAME}.service"

# --- Defaults / Verhalten ---
PROMPT_TIMEOUT="${LOGBOT_TIMEOUT:-5}"   # Sekunden Countdown bis Auto-Start
ASSUME_YES="false"                      # true => nie fragen, immer Default
MANUAL="false"                          # true => alle Werte werden abgefragt (kein Timeout)
GATE_DONE="false"                       # interactive_gate nur einmal ausfuehren
ACTION="install"

# --- Konfiguration (Vorrang: Parameter > Umgebungsvariable > Platzhalter) ---
MODE="${LOGBOT_MODE:-${PLACEHOLDER_MODE:-https}}"
FQDN="${LOGBOT_FQDN:-${PLACEHOLDER_FQDN:-}}"
IPFB="${LOGBOT_IP:-}"
PORT="${LOGBOT_PORT:-${PLACEHOLDER_PORT:-}}"
TOKEN="${LOGBOT_TOKEN:-${PLACEHOLDER_TOKEN:-}}"
MINLEVEL="${LOGBOT_MINLEVEL:-${PLACEHOLDER_MINLEVEL:-info}}"
INSECURE="${LOGBOT_INSECURE:-false}"
PROTO="${LOGBOT_PROTO:-udp}"            # nur Syslog-Modus: udp | tcp
DOCKER_MODE="${LOGBOT_DOCKER:-auto}"    # auto = Container erfassen, wenn Docker da ist | off
REMOTE_UPDATE="${LOGBOT_REMOTE_UPDATE:-true}"   # false = Server darf diesen Agent nicht aktualisieren

# ==============================================================================
# Hilfsfunktionen
# ==============================================================================

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
fail() { log_error "$1"; exit 1; }

require_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "Dieses Script muss als root ausgeführt werden!"
        log_info "Aufruf: sudo bash $0   (bzw. '| sudo -E bash' beim One-Liner)"
        exit 1
    fi
}

# true nur, wenn /dev/tty wirklich geoeffnet werden kann (nicht nur -r).
# Sonst wuerde 'read </dev/tty' bei Pipe ohne Terminal eine Fehlermeldung werfen.
have_tty() { true 2>/dev/null </dev/tty; }

# Fragt einen Wert ab. Nur im MANUELLEN Modus (nach Tastendruck im Gate) wird
# tatsächlich gefragt. Im automatischen Modus wird still der Default genommen.
#
# WICHTIG - Zeitlimit: früher wartete diese Funktion unbegrenzt. Lief das Skript
# über eine Pipe (curl | sudo bash), über SSH ohne echtes Terminal oder aus
# einem Automatismus heraus, blieb es an der ersten Frage einfach stehen. Genau
# das war der Grund, warum die Deinstallation "an vielen Stellen hängt".
# Jetzt gilt: keine Eingabe innerhalb von ASK_TIMEOUT Sekunden -> Default.
# Ein Terminal steht ohnehin nicht zur Verfügung -> sofort Default.
# ask VARNAME "Frage" "default"
ASK_TIMEOUT="${LOGBOT_ASK_TIMEOUT:-60}"

ask() {
    local __name="$1" prompt="$2" def="$3" ans=""
    if [[ "$MANUAL" == "true" ]] && have_tty; then
        if ! read -r -t "$ASK_TIMEOUT" -p "$prompt [${def:-leer}] (Enter = Default): " ans </dev/tty; then
            ans=""
            echo ""
            log_warn "Keine Eingabe innerhalb von ${ASK_TIMEOUT}s - nehme Standardwert."
        fi
        echo ""
    fi
    [[ -z "$ans" ]] && ans="$def"
    printf -v "$__name" '%s' "$ans"
}

# Einmaliges "Gate" am Anfang: kurzer Countdown. Wird EINE Taste gedrückt, schaltet
# der Installer auf MANUELL (alle folgenden Abfragen blockieren, kein Timeout mehr).
# Keine Eingabe / kein Terminal / --yes => automatischer Ablauf mit Standardwerten.
interactive_gate() {
    [[ "$GATE_DONE" == "true" ]] && return 0
    GATE_DONE="true"
    [[ "$ASSUME_YES" == "true" ]] && return 0
    have_tty || return 0
    echo ""
    log_info "Automatischer Start in ${PROMPT_TIMEOUT}s. Für MANUELLE Eingabe jetzt eine Taste drücken..."
    local _k=""
    if read -rsN1 -t "$PROMPT_TIMEOUT" _k </dev/tty; then
        MANUAL="true"
        # Restliche gepufferte Zeichen (z.B. Enter nach dem Aufweck-Tastendruck)
        # verwerfen, damit die erste echte Abfrage nicht sofort den Default nimmt.
        while read -rsN1 -t 0.05 _k </dev/tty 2>/dev/null; do :; done
        echo ""
        log_success "Manueller Modus aktiv - alle Werte werden abgefragt (kein Timeout)."
    else
        echo ""
        log_info "Keine Eingabe - automatischer Ablauf mit Standardwerten."
    fi
    return 0
}

show_help() {
    cat <<EOF
LogBot Linux Agent Installer v${AGENT_VERSION}

Aufruf:   sudo bash install-linux.sh [aktion] [optionen]
Aktionen: install (Standard) | uninstall | uninstall-purge | test | upgrade

Optionen (auch als Umgebungsvariable LOGBOT_*):
  --fqdn <name>       Server-FQDN            (LOGBOT_FQDN)   [Pflicht bei https]
  --token <token>     Agent-Token (Bearer)  (LOGBOT_TOKEN)  [Pflicht bei https]
  --mode <https|syslog>  Modus (Standard https)  (LOGBOT_MODE)
  --port <n>          Port (https=443, syslog=514)  (LOGBOT_PORT)
  --proto <udp|tcp>   Protokoll im Syslog-Modus (Standard udp)  (LOGBOT_PROTO)
  --ip <ip>           Optionale IP als Fallback     (LOGBOT_IP)
  --min-level <info|warning|error>            (LOGBOT_MINLEVEL)
  --insecure          Selbstsignierte TLS-Zerts akzeptieren  (LOGBOT_INSECURE=true)
                      Updates bleiben trotzdem geschuetzt: sie sind vom Server
                      unterschrieben und werden vor dem Einspielen geprueft.
  --no-docker         Docker-Container NICHT erfassen        (LOGBOT_DOCKER=off)
  --no-remote-update  Server darf diesen Agent nicht aktualisieren (LOGBOT_REMOTE_UPDATE=false)
  --yes, --unattended Keine Rueckfragen, alles Default        (ASSUME_YES)
  --timeout <sek>     Countdown bis Auto-Start (Standard 5)  (LOGBOT_TIMEOUT)
                      Taste druecken => manueller Modus (alle Werte, kein Timeout)

Beispiel (One-Liner):
  curl -sSL <URL> | sudo bash -s -- --fqdn logbot.example.com --token xxxx
EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            install)         ACTION="install" ;;
            uninstall|remove) ACTION="uninstall" ;;
            uninstall-purge|purge) ACTION="uninstall-purge" ;;
            test)            ACTION="test" ;;
            upgrade)         ACTION="upgrade" ;;
            --no-docker)     DOCKER_MODE="off" ;;
            --no-remote-update) REMOTE_UPDATE="false" ;;
            --fqdn)          FQDN="${2:-}"; shift ;;
            --fqdn=*)        FQDN="${1#*=}" ;;
            --token)         TOKEN="${2:-}"; shift ;;
            --token=*)       TOKEN="${1#*=}" ;;
            --ip)            IPFB="${2:-}"; shift ;;
            --ip=*)          IPFB="${1#*=}" ;;
            --port)          PORT="${2:-}"; shift ;;
            --port=*)        PORT="${1#*=}" ;;
            --proto)         PROTO="${2:-}"; shift ;;
            --proto=*)       PROTO="${1#*=}" ;;
            --mode)          MODE="${2:-}"; shift ;;
            --mode=*)        MODE="${1#*=}" ;;
            --min-level)     MINLEVEL="${2:-}"; shift ;;
            --min-level=*)   MINLEVEL="${1#*=}" ;;
            --insecure|-k)   INSECURE="true" ;;
            --yes|-y|--unattended) ASSUME_YES="true" ;;
            --timeout)       PROMPT_TIMEOUT="${2:-5}"; shift ;;
            --timeout=*)     PROMPT_TIMEOUT="${1#*=}" ;;
            --help|-h)       show_help; exit 0 ;;
            *)               log_warn "Unbekannter Parameter: $1" ;;
        esac
        shift || true
    done
}

# ==============================================================================
# Installationsstatus erkennen
# ==============================================================================

syslog_installed() { [[ -f "$CONFIG_FILE" ]] && grep -q "LogBot Agent v" "$CONFIG_FILE"; }
https_installed()  { [[ -f "$SYSTEMD_UNIT" ]] || [[ -f "$AGENT_SCRIPT" ]]; }
is_installed()     { syslog_installed || https_installed; }

# ==============================================================================
# Server-Konfig aus vorhandener Installation lesen (fuer Purge-Defaults)
# ==============================================================================

read_agent_config() {
    local key="$1"
    [[ -f "$AGENT_CONFIG" ]] || return 0
    command -v python3 >/dev/null 2>&1 || return 0
    python3 - "$AGENT_CONFIG" "$key" <<'PYEOF' 2>/dev/null || true
import json, sys
try:
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    v = d.get(sys.argv[2], "")
    print("" if v is None else v)
except Exception:
    pass
PYEOF
}

detect_server_from_config() {
    if [[ -f "$AGENT_CONFIG" ]]; then
        SERVER_HOST_DETECTED="$(read_agent_config server_fqdn)"
        [[ -z "$SERVER_HOST_DETECTED" ]] && SERVER_HOST_DETECTED="$(read_agent_config server_ip)"
        SERVER_PORT_DETECTED="$(read_agent_config server_port)"
        TOKEN_DETECTED="$(read_agent_config agent_token)"
        return
    fi
    if [[ -f "$CONFIG_FILE" ]]; then
        local line target host_port
        line=$(grep -E 'target=' "$CONFIG_FILE" | tail -1 || true)
        if [[ -n "$line" ]]; then
            SERVER_HOST_DETECTED=$(echo "$line" | sed -n 's/.*target="\([^"]*\)".*/\1/p')
            SERVER_PORT_DETECTED=$(grep -E 'port=' "$CONFIG_FILE" | sed -n 's/.*port="\([^"]*\)".*/\1/p' | tail -1)
        fi
    fi
}

# ==============================================================================
# DNS-Aufloesung + Erreichbarkeit (FQDN und IP gleichermassen)
# ==============================================================================

resolve_host() {
    local host="$1"
    if [[ "$host" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        return 0
    fi
    if command -v getent >/dev/null 2>&1; then
        getent ahosts "$host" >/dev/null 2>&1 && return 0
    fi
    if command -v python3 >/dev/null 2>&1; then
        python3 -c 'import socket,sys; socket.getaddrinfo(sys.argv[1], None)' "$host" >/dev/null 2>&1 && return 0
    fi
    if command -v dig >/dev/null 2>&1; then
        [[ -n "$(dig +short "$host" 2>/dev/null)" ]] && return 0
    fi
    if command -v host >/dev/null 2>&1; then
        host "$host" >/dev/null 2>&1 && return 0
    fi
    return 1
}

check_tcp_reachable() {
    local host="$1" port="$2" tmo="${3:-3}"
    if timeout "$tmo" bash -c "exec 3<>/dev/tcp/${host}/${port}" 2>/dev/null; then
        return 0
    fi
    if command -v nc >/dev/null 2>&1; then
        nc -z -w "$tmo" "$host" "$port" >/dev/null 2>&1 && return 0
    fi
    return 1
}

# ==============================================================================
#  SYSLOG-MODUS  (rsyslog -> UDP/TCP)
# ==============================================================================

ensure_rsyslog() {
    if ! command -v rsyslogd &> /dev/null; then
        log_warn "rsyslog nicht gefunden, installiere..."
        if command -v apt-get &> /dev/null; then
            apt-get update && apt-get install -y rsyslog
        elif command -v dnf &> /dev/null; then
            dnf install -y rsyslog
        elif command -v yum &> /dev/null; then
            yum install -y rsyslog
        else
            fail "Paketmanager nicht erkannt. Bitte rsyslog manuell installieren."
        fi
    fi
    if ! systemctl is-active --quiet rsyslog 2>/dev/null; then
        systemctl enable rsyslog && systemctl start rsyslog
    fi
}

configure_syslog() {
    ensure_rsyslog
    log_info "Konfiguriere rsyslog (Syslog-Modus)..."

    ask FQDN "LogBot Server Adresse (FQDN oder IP)" "$FQDN"
    [[ -z "$FQDN" ]] && fail "Server-Adresse fehlt. Per --fqdn / LOGBOT_FQDN / Platzhalter setzen."
    [[ -z "$PORT" ]] && PORT="514"
    ask PORT "LogBot Server Port" "$PORT"

    local proto="$PROTO"
    ask proto "Protokoll (udp/tcp)" "$PROTO"
    case "$proto" in tcp|TCP|2) proto="tcp" ;; *) proto="udp" ;; esac

    if resolve_host "$FQDN"; then
        log_success "Adresse auflösbar: $FQDN"
    else
        log_warn "\"$FQDN\" derzeit nicht per DNS auflösbar - rsyslog versucht es zur Laufzeit erneut."
    fi
    if [[ "$proto" == "tcp" ]]; then
        check_tcp_reachable "$FQDN" "$PORT" && log_success "TCP ${FQDN}:${PORT} erreichbar" \
            || log_warn "TCP ${FQDN}:${PORT} derzeit nicht erreichbar - Konfiguration wird dennoch geschrieben."
    fi

    [[ -f "$CONFIG_FILE" ]] && cp "$CONFIG_FILE" "${CONFIG_FILE}.backup.$(date +%Y%m%d_%H%M%S)"

    cat > "$CONFIG_FILE" << EOF
# ==============================================================================
# LogBot Agent v${AGENT_VERSION} - rsyslog Konfiguration (Syslog-Modus)
# Erstellt: $(date)
# Server: ${FQDN}:${PORT} (${proto})
# ==============================================================================
action(
  type="omfwd"
  target="${FQDN}"
  port="${PORT}"
  protocol="${proto}"
  Template="RSYSLOG_TraditionalForwardFormat"
  action.resumeRetryCount="-1"
  queue.type="LinkedList"
  queue.filename="logbot_queue"
  queue.maxDiskSpace="100m"
  queue.saveOnShutdown="on"
)
EOF
    log_success "Konfiguration erstellt: $CONFIG_FILE"
}

restart_rsyslog() {
    log_info "Starte rsyslog neu..."
    if rsyslogd -N1 2>/dev/null; then
        systemctl restart rsyslog
        sleep 2
        systemctl is-active --quiet rsyslog && log_success "rsyslog läuft" \
            || fail "rsyslog konnte nicht gestartet werden. Prüfe: journalctl -u rsyslog -n 50"
    else
        fail "rsyslog Konfiguration fehlerhaft! Prüfe: rsyslogd -N1"
    fi
}

# ==============================================================================
#  HTTPS-MODUS  (Python systemd-Dienst -> /api/agents/ingest)
# ==============================================================================

PYTHON_BIN=""

ensure_https_deps() {
    PYTHON_BIN="$(command -v python3 || true)"
    if [[ -z "$PYTHON_BIN" ]]; then
        log_warn "python3 nicht gefunden, installiere..."
        if command -v apt-get &> /dev/null; then
            apt-get update && apt-get install -y python3
        elif command -v dnf &> /dev/null; then
            dnf install -y python3
        elif command -v yum &> /dev/null; then
            yum install -y python3
        else
            fail "Paketmanager nicht erkannt. Bitte python3 manuell installieren."
        fi
        PYTHON_BIN="$(command -v python3 || true)"
    fi
    [[ -z "$PYTHON_BIN" ]] && fail "python3 weiterhin nicht verfügbar."
    command -v systemctl >/dev/null 2>&1 || fail "systemd (systemctl) nicht gefunden - HTTPS-Modus benötigt systemd."
    command -v journalctl >/dev/null 2>&1 || fail "journalctl nicht gefunden - HTTPS-Agent liest Logs aus journald."
}

write_agent_script() {
    mkdir -p "$AGENT_DIR"
    cat > "$AGENT_SCRIPT" << 'PYEOF'
#!/usr/bin/env python3
# ==============================================================================
# LogBot Linux Agent - HTTPS Log Forwarder
# Liest ALLE Logs aus journald und - falls vorhanden - aus Docker-Containern und
# sendet sie verschlüsselt + Token-authentifiziert an
#   https://<FQDN>/api/agents/ingest  (Pakete von max. 500 Events, Cursor
# rueckt nach jedem angekommenen Paket vor, Rueckstand wird gedrosselt geholt).
# Meldet sich jede Minute beim Server (Heartbeat: Fassung, Container-Inventar)
# und aktualisiert sich auf Anweisung selbst - nur mit gültiger Unterschrift.
# Nur Python-Standardbibliothek - keine externen Abhängigkeiten.
# ==============================================================================
import base64
import hashlib
import http.client
import json
import os
import platform
import re
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

AGENT_VERSION = "__AGENT_VERSION__"

CONFIG_FILE = os.environ.get("LOGBOT_CONFIG", "/opt/logbot-agent/config.json")
CURSOR_FILE = os.environ.get("LOGBOT_CURSOR", "/opt/logbot-agent/cursor")
# Hier merkt sich der Agent, welcher Geraeteeintrag auf dem Server ihm gehoert.
AGENT_ID_FILE = os.environ.get("LOGBOT_AGENT_ID", "/opt/logbot-agent/agent_id")
DOCKER_STATE_FILE = "/opt/logbot-agent/docker_state.json"
PUBKEY_FILE = "/opt/logbot-agent/update_pubkey.pem"
UPDATE_DIR = "/opt/logbot-agent/update"
# Pro Anfrage bis zu 500 Eintraege (der Server nimmt bis 5000). Weniger
# Anfragen = weit weg vom Limit des Servers (600 Anfragen/Minute).
BATCH_SIZE = 500
MSG_MAX = 2048
SOURCE_MAX = 100          # Feldgrenze des Servers
MAX_LINES = 5000          # Journal-Zeilen pro Durchlauf (begrenzt Speicher + Paketzahl)
CATCHUP_PAUSE = 2         # Sekunden zwischen Durchlaeufen, solange Rueckstand anliegt
MAX_BACKOFF = 300         # laengste Pause nach Sendefehlern (Sekunden)
HEARTBEAT_SECONDS = 60
DOCKER_POLL = 5
MAX_LINES_PER_CONTAINER = 2000
MAX_LOG_BYTES = 4 * 1024 * 1024

# journald PRIORITY (syslog severity 0-7) -> Level-String
PRIO_TO_LEVEL = {0: "critical", 1: "critical", 2: "critical", 3: "error",
                 4: "warning", 5: "notice", 6: "info", 7: "debug"}
# Numerische Schwelle je min_level (kleiner = schwerwiegender)
MIN_PRIO = {"debug": 7, "info": 6, "notice": 5, "warning": 4, "error": 3, "critical": 2}
LEVEL_PRIO = {"critical": 2, "error": 3, "warning": 4, "notice": 5, "info": 6, "debug": 7}


def log(msg):
    print("[logbot-agent] " + msg, flush=True)


def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


CFG = load_config()
SERVER_FQDN = (CFG.get("server_fqdn") or "").strip()
SERVER_IP = (CFG.get("server_ip") or "").strip()
SERVER_PORT = int(CFG.get("server_port") or 443)
TOKEN = (CFG.get("agent_token") or "").strip()
SKIP_TLS = bool(CFG.get("skip_tls_verify"))
MIN_LEVEL = (CFG.get("min_level") or "info").lower()
HOSTNAME = (CFG.get("hostname") or "").strip() or socket.gethostname()
POLL = int(CFG.get("poll_interval") or 5)
MIN_PRIO_NUM = MIN_PRIO.get(MIN_LEVEL, 6)
# "auto" = Docker erfassen, wenn vorhanden; "off" = nie.
DOCKER_MODE = (CFG.get("docker") or "auto").lower()
# Darf der Server diesen Agent aktualisieren? Auf dem Geraet abschaltbar.
REMOTE_UPDATE = CFG.get("remote_update", True) is not False
# LogBots eigene Container (Label de.logbot.stack) werden nicht erfasst: ihre
# Zugriffsprotokolle wuerden jede Lieferung erneut erzeugen - eine Schleife.
INCLUDE_LOGBOT = bool(CFG.get("docker_include_logbot"))

STARTED_AT = time.time()
SEND_LOCK = threading.Lock()


def build_ctx():
    ctx = ssl.create_default_context()
    if SKIP_TLS:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def resolvable(host):
    try:
        socket.getaddrinfo(host, None)
        return True
    except Exception:
        return False


def target_host():
    # FQDN zuerst (DNS-basiert), IP als Fallback
    if SERVER_FQDN and resolvable(SERVER_FQDN):
        return SERVER_FQDN
    if SERVER_IP:
        return SERVER_IP
    return SERVER_FQDN


def base_url():
    host = target_host()
    if not host:
        return None
    if SERVER_PORT == 443:
        return "https://%s" % host
    return "https://%s:%d" % (host, SERVER_PORT)


def local_ip():
    # Eigene IP Richtung Server melden: steht ein Reverse Proxy (NPM, Caddy)
    # dazwischen, sieht der Server sonst nur dessen IP.
    if (CFG.get("ip_address") or "").strip():
        return CFG["ip_address"].strip()
    host = target_host()
    if not host:
        return ""
    try:
        family, _, _, _, addr = socket.getaddrinfo(host, SERVER_PORT, 0, socket.SOCK_DGRAM)[0]
        s = socket.socket(family, socket.SOCK_DGRAM)
        try:
            s.connect(addr)
            return s.getsockname()[0]
        finally:
            s.close()
    except Exception:
        return ""


def api(method, path, body=None, timeout=20, raw=False):
    """Ein Aufruf an den Server. Gibt (status, daten) zurueck; status 0 = nicht erreichbar."""
    base = base_url()
    if not base:
        return 0, None
    data = None
    headers = {"Authorization": "Bearer " + TOKEN, "User-Agent": "LogBot-Agent/" + AGENT_VERSION}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=build_ctx()) as r:
            content = r.read()
            if raw:
                return r.status, (content, dict(r.headers))
            try:
                return r.status, json.loads(content.decode("utf-8", "replace") or "null")
            except ValueError:
                return r.status, None
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        log("Server nicht erreichbar (%s): %s" % (path, e))
        return 0, None


def remember_agent_id(payload):
    """Merkt sich die Geraetenummer, die der Server zurueckmeldet."""
    try:
        agent_id = (payload or {}).get("agent_id")
        if not agent_id or read_agent_id() == str(agent_id):
            return
        os.makedirs(os.path.dirname(AGENT_ID_FILE), exist_ok=True)
        tmp = AGENT_ID_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(str(agent_id))
        os.replace(tmp, AGENT_ID_FILE)
        log("Geraetenummer auf dem Server: %s" % agent_id)
    except Exception as e:
        log("Geraetenummer nicht gespeichert: %s" % e)


def read_agent_id():
    try:
        with open(AGENT_ID_FILE, "r", encoding="utf-8") as f:
            return f.read().strip() or None
    except Exception:
        return None


def _retry_after(e):
    try:
        return max(1, min(int(e.headers.get("Retry-After") or 0), MAX_BACKOFF))
    except Exception:
        return 0


def send(events):
    """Ein Paket senden. Rueckgabe: (ergebnis, wartezeit).

    ergebnis "ok"    - angekommen (auch: vom Server als Duplikat erkannt)
             "retry" - spaeter GENAU DIESES Paket nochmal (Netz, Server weg,
                       429/5xx, Schluessel abgelehnt)
             "drop"  - der Server lehnt den Inhalt dauerhaft ab (400/413/422).
                       Erneut schicken wuerde ewig scheitern und alles
                       dahinter blockieren - also protokollieren und weiter.
    """
    if not events:
        return "ok", 0
    base = base_url()
    if not base:
        log("Kein Ziel (FQDN/IP) konfiguriert")
        return "retry", 0
    body = {"hostname": HOSTNAME, "device_type": "linux_agent", "agent_version": AGENT_VERSION,
            "events": events}
    ip = local_ip()
    if ip:
        body["ip_address"] = ip
    req = urllib.request.Request(base + "/api/agents/ingest", data=json.dumps(body).encode("utf-8"),
                                 method="POST", headers={
                                     "Authorization": "Bearer " + TOKEN,
                                     "Content-Type": "application/json",
                                     "User-Agent": "LogBot-Agent/" + AGENT_VERSION})
    try:
        with SEND_LOCK:
            with urllib.request.urlopen(req, timeout=30, context=build_ctx()) as r:
                if not 200 <= r.status < 300:
                    log("HTTP %s beim Senden" % r.status)
                    return "retry", 0
                try:
                    remember_agent_id(json.loads(r.read().decode("utf-8", "replace")))
                except Exception:
                    pass
                return "ok", 0
    except urllib.error.HTTPError as e:
        if e.code in (400, 413, 422):
            detail = ""
            try:
                detail = e.read().decode("utf-8", "replace")[:300]
            except Exception:
                pass
            log("HTTP %s - Paket mit %d Eintraegen verworfen: %s" % (e.code, len(events), detail))
            return "drop", 0
        log("HTTP %s beim Senden" % e.code)
        return "retry", _retry_after(e)
    except Exception as e:
        log("Sendefehler: %s" % e)
        return "retry", 0


def send_chunks(events):
    """Mehrere Pakete; True, wenn alle angekommen (oder dauerhaft verworfen) sind."""
    for i in range(0, len(events), BATCH_SIZE):
        result, _ = send(events[i:i + BATCH_SIZE])
        if result == "retry":
            return False
    return True


# ==============================================================================
# Schweregrad aus dem Text erkennen (Container-Logs haben keinen)
# ==============================================================================
_LEVEL_PATTERNS = [
    ("critical", re.compile(r"\b(panic|fatal|emerg(ency)?|crit(ical)?|out of memory|oom-?kill)", re.I)),
    ("error", re.compile(r"(\b(error|err|exception|traceback|failed|failure)\b|\[E\]|\bE\d{4} )", re.I)),
    ("warning", re.compile(r"\b(warn(ing)?|deprecated)\b|\[W\]", re.I)),
    ("debug", re.compile(r"\b(debug|trace)\b", re.I)),
]
_JSON_LEVEL = re.compile(r'"(?:level|severity|lvl|log\.level)"\s*:\s*"([A-Za-z]+)"')
_KV_LEVEL = re.compile(r"\blevel=\"?([A-Za-z]+)")
_NORMALIZE = {"fatal": "critical", "panic": "critical", "crit": "critical", "critical": "critical",
              "emerg": "critical", "alert": "critical", "err": "error", "error": "error",
              "warn": "warning", "warning": "warning", "notice": "notice", "info": "info",
              "information": "info", "debug": "debug", "trace": "debug"}


def detect_level(message, stream="stdout"):
    m = _JSON_LEVEL.search(message) or _KV_LEVEL.search(message)
    if m and m.group(1).lower() in _NORMALIZE:
        return _NORMALIZE[m.group(1).lower()]
    head = message[:160]
    for level, pattern in _LEVEL_PATTERNS:
        if pattern.search(head):
            return level
    return "info"


def decode_message(m):
    if isinstance(m, list):
        try:
            m = bytes(m).decode("utf-8", "replace")
        except Exception:
            m = str(m)
    if m is None:
        return ""
    m = " ".join(str(m).split())
    if len(m) > MSG_MAX:
        m = m[:MSG_MAX]
    return m


# ==============================================================================
# journald
# ==============================================================================
def read_cursor():
    try:
        with open(CURSOR_FILE, "r", encoding="utf-8") as f:
            return f.read().strip() or None
    except Exception:
        return None


def write_cursor(cursor):
    if not cursor:
        return
    try:
        os.makedirs(os.path.dirname(CURSOR_FILE), exist_ok=True)
        tmp = CURSOR_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(cursor)
        os.replace(tmp, CURSOR_FILE)
    except Exception as e:
        log("Cursor konnte nicht gespeichert werden: %s" % e)


def latest_cursor():
    # Cursor des letzten Journal-Eintrags -> Start "ab jetzt" (keine History-Flut)
    try:
        out = subprocess.run(["journalctl", "-o", "json", "-n", "1", "--no-pager"],
                             capture_output=True, text=True, timeout=30)
        for line in out.stdout.splitlines():
            try:
                j = json.loads(line)
            except Exception:
                continue
            if "__CURSOR" in j:
                return j["__CURSOR"]
    except Exception as e:
        log("latest_cursor Fehler: %s" % e)
    return None


def event_time(j):
    # Zeitpunkt des Ereignisses (nicht der Zustellung). Damit erkennt der
    # Server doppelt gelieferte Eintraege und verwirft sie, und nachgeholte
    # Logs landen zur richtigen Zeit statt alle "jetzt".
    try:
        us = int(j.get("__REALTIME_TIMESTAMP"))
        return datetime.fromtimestamp(us / 1000000.0, timezone.utc).isoformat()
    except Exception:
        return None


def to_event(j):
    try:
        prio = int(j.get("PRIORITY", 6))
    except Exception:
        prio = 6
    message = decode_message(j.get("MESSAGE"))
    if not message:
        return None
    container = j.get("CONTAINER_NAME")
    if container and DOCKER_MODE != "off":
        # Docker mit journald-Treiber: die Zeile gehoert zum Container.
        level = detect_level(message)
        if prio <= 3 and LEVEL_PRIO.get(level, 6) > 3:
            level = "error"
        if LEVEL_PRIO.get(level, 6) > MIN_PRIO_NUM:
            return None
        ev = {"level": level, "message": message, "container": container[:200],
              "stream": "stderr" if prio <= 3 else "stdout"}
    else:
        if prio > MIN_PRIO_NUM:
            return None
        level = PRIO_TO_LEVEL.get(prio, "info")
        ident = j.get("SYSLOG_IDENTIFIER") or j.get("_COMM") or "journal"
        unit = j.get("_SYSTEMD_UNIT")
        source = ("%s/%s" % (unit, ident)) if unit else ident
        # Der Server nimmt hoechstens 100 Zeichen - ein laengerer Unit-Name liess
        # frueher das ganze Paket abweisen.
        ev = {"level": level, "source": str(source)[:SOURCE_MAX], "message": message}
        try:
            facility = int(j.get("SYSLOG_FACILITY"))
            if 0 <= facility <= 23:
                ev["facility"] = facility
        except Exception:
            pass
    ts = event_time(j)
    if ts:
        ev["timestamp"] = ts
    return ev


def collect_since(cursor):
    """Hoechstens MAX_LINES Journal-Zeilen nach `cursor` lesen.

    Rueckgabe: (batches, ok, more)
      batches - Liste von (events, cursor_danach). Jedes Paket traegt die
                Position, bis zu der es reicht - so rueckt der Cursor nach
                JEDEM angekommenen Paket vor und ein Fehler wiederholt nur
                dieses eine Paket, nie alles davor.
      ok      - False: journalctl hat den Cursor abgelehnt -> neu aufsetzen
      more    - True: es liegt noch Rueckstand an (MAX_LINES erreicht)
    """
    args = ["journalctl", "-o", "json", "--no-pager", "--after-cursor", cursor]
    try:
        # stderr verwerfen: gelesen wird nur stdout, ein volles stderr-Rohr
        # wuerde journalctl sonst blockieren.
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                text=True, errors="replace")
    except Exception as e:
        log("journalctl Fehler: %s" % e)
        return [], True, False
    batches = []
    events = []
    last = cursor
    lines = 0
    more = False
    try:
        for line in proc.stdout:
            try:
                j = json.loads(line)
            except Exception:
                continue
            if "__CURSOR" not in j:
                continue
            last = j["__CURSOR"]
            lines += 1
            ev = to_event(j)
            if ev:
                events.append(ev)
                if len(events) >= BATCH_SIZE:
                    batches.append((events, last))
                    events = []
            if lines >= MAX_LINES:
                more = True
                break
    finally:
        if more:
            proc.kill()
        try:
            proc.communicate(timeout=30)
        except Exception:
            proc.kill()
    if not more and proc.returncode not in (0, None) and lines == 0:
        log("journalctl rc=%s (Cursor ungueltig/rotiert?) - setze neu auf" % proc.returncode)
        return [], False, False
    # Rest - auch ganz ohne Events (alles unter MinLevel), damit der Cursor
    # trotzdem ueber die gefilterten Zeilen hinweg vorrueckt.
    if events or last != cursor:
        batches.append((events, last))
    return batches, True, more


def journal_loop():
    cursor = read_cursor()
    failures = 0
    while True:
        if not cursor:
            cursor = latest_cursor()
            if cursor:
                write_cursor(cursor)
            else:
                time.sleep(POLL)
                continue

        batches, ok, more = collect_since(cursor)
        if not ok:
            # journalctl-Fehler (evtl. ungueltiger/rotierter Cursor) -> neu setzen
            cursor = None
            time.sleep(POLL)
            continue

        wait = 0
        for events, upto in batches:
            result, wait = send(events)
            if result == "retry":
                break
            # "ok" oder "drop": dieses Paket ist erledigt -> Position merken.
            cursor = upto
            write_cursor(cursor)
            failures = 0
        else:
            if more:
                # Rueckstand gedrosselt abarbeiten, nicht im Dauerfeuer.
                time.sleep(CATCHUP_PAUSE)
                continue
            time.sleep(POLL)
            continue

        # Senden gescheitert: nur ab dem gescheiterten Paket neu versuchen,
        # mit wachsender Pause (5 s, 10 s, 20 s ... bis 5 min), damit ein
        # angeschlagener Server nicht zusaetzlich unter Beschuss geraet.
        failures += 1
        backoff = min(POLL * (2 ** min(failures - 1, 10)), MAX_BACKOFF)
        time.sleep(max(wait, backoff))


# ==============================================================================
# Docker (und Podman mit Docker-kompatiblem Socket)
# ==============================================================================
SOCKETS = ["/var/run/docker.sock", "/run/docker.sock", "/run/podman/podman.sock"]


class UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, path, timeout=15):
        http.client.HTTPConnection.__init__(self, "localhost", timeout=timeout)
        self.unix_path = path

    def connect(self):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect(self.unix_path)
        self.sock = sock


def docker_socket():
    for path in SOCKETS:
        if os.path.exists(path):
            return path
    return None


def docker_get(path, timeout=15, limit=None):
    sock = docker_socket()
    if not sock:
        return 0, b""
    conn = UnixHTTPConnection(sock, timeout=timeout)
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        data = resp.read(limit) if limit else resp.read()
        return resp.status, data
    except Exception as e:
        log("Docker-API (%s): %s" % (path.split("?")[0], e))
        return 0, b""
    finally:
        conn.close()


def docker_json(path, timeout=15):
    status, data = docker_get(path, timeout)
    if status != 200:
        return None
    try:
        return json.loads(data.decode("utf-8", "replace"))
    except ValueError:
        return None


def cli_version(cmd):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if out.returncode == 0:
            return (out.stdout or out.stderr).strip().splitlines()[0][:120]
    except Exception:
        pass
    return ""


def docker_info():
    """Ist Docker da, welche Fassung, gibt es Compose?"""
    info = {"installed": False}
    if not docker_socket() and not shutil.which("docker"):
        return info
    info["installed"] = True
    info["socket"] = docker_socket() or ""
    version = docker_json("/version", timeout=8) or {}
    info["engine"] = version.get("Version") or ""
    info["api"] = version.get("ApiVersion") or ""
    info["podman"] = "podman" in (info["socket"] or "") or "Podman" in json.dumps(version.get("Components") or [])
    compose = ""
    if shutil.which("docker"):
        compose = cli_version(["docker", "compose", "version", "--short"])
    if not compose and shutil.which("docker-compose"):
        compose = cli_version(["docker-compose", "--version"])
    info["compose"] = compose
    info["reachable"] = bool(version)
    return info


def ts_ns(text):
    """RFC3339Nano -> Nanosekunden seit 1970 (ohne Zeitzonen-Bibliothek)."""
    m = re.match(r"(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)(?:\.(\d+))?(Z|[+-]\d\d:\d\d)?", text or "")
    if not m:
        return 0
    import calendar
    secs = calendar.timegm((int(m.group(1)), int(m.group(2)), int(m.group(3)),
                            int(m.group(4)), int(m.group(5)), int(m.group(6))))
    frac = (m.group(7) or "0")[:9].ljust(9, "0")
    tz = m.group(8) or "Z"
    if tz != "Z":
        sign = 1 if tz[0] == "+" else -1
        secs -= sign * (int(tz[1:3]) * 3600 + int(tz[4:6]) * 60)
    return secs * 1000000000 + int(frac)


def iso(ns):
    secs, rest = divmod(ns, 1000000000)
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(secs)) + ".%09dZ" % rest


def demux(data, tty):
    """Docker-Logstrom zerlegen: ohne TTY mit 8-Byte-Kopf je Rahmen."""
    if tty:
        for line in data.decode("utf-8", "replace").splitlines():
            yield "stdout", line
        return
    pos = 0
    buffers = {1: "", 2: ""}
    while pos + 8 <= len(data):
        kind = data[pos]
        size = int.from_bytes(data[pos + 4:pos + 8], "big")
        chunk = data[pos + 8:pos + 8 + size].decode("utf-8", "replace")
        pos += 8 + size
        stream = 2 if kind == 2 else 1
        buffers[stream] += chunk
        while "\n" in buffers[stream]:
            line, buffers[stream] = buffers[stream].split("\n", 1)
            yield ("stderr" if stream == 2 else "stdout"), line
    for stream, rest in buffers.items():
        if rest:
            yield ("stderr" if stream == 2 else "stdout"), rest


def load_docker_state():
    try:
        with open(DOCKER_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"containers": {}, "events_since": int(time.time())}


def save_docker_state(state):
    try:
        tmp = DOCKER_STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f)
        os.replace(tmp, DOCKER_STATE_FILE)
    except Exception as e:
        log("Docker-Zustand nicht gespeichert: %s" % e)


INVENTORY = {"docker": None, "containers": []}
INSPECT_CACHE = {}


def excluded(labels, name):
    labels = labels or {}
    if str(labels.get("de.logbot.collect", "")).lower() in ("false", "0", "no", "off"):
        return True
    if not INCLUDE_LOGBOT and (labels.get("de.logbot.stack") or name.startswith(("logbot-app-", "logbot-ext-"))):
        return True
    return False


def inventory():
    """Alle Container mit dem, was man zum Einordnen braucht."""
    listing = docker_json("/containers/json?all=1") or []
    result = []
    for c in listing:
        cid = c.get("Id") or ""
        name = ((c.get("Names") or ["/?"])[0] or "/?").lstrip("/")
        labels = c.get("Labels") or {}
        state = c.get("State") or ""
        key = (cid, state, c.get("Status", "").split(" ")[0])
        cached = INSPECT_CACHE.get(cid)
        if not cached or cached[0] != key:
            detail = docker_json("/containers/%s/json" % cid) or {}
            INSPECT_CACHE[cid] = (key, detail)
        detail = INSPECT_CACHE[cid][1]
        dstate = detail.get("State") or {}
        driver = ((detail.get("HostConfig") or {}).get("LogConfig") or {}).get("Type") or ""
        ports = []
        for p in c.get("Ports") or []:
            if p.get("PublicPort"):
                ports.append("%s:%s/%s" % (p.get("PublicPort"), p.get("PrivatePort"), p.get("Type", "tcp")))
        result.append({
            "id": cid[:64], "name": name, "image": c.get("Image") or "",
            "state": state, "status": c.get("Status") or "",
            "health": (dstate.get("Health") or {}).get("Status") or "",
            "compose_project": labels.get("com.docker.compose.project") or "",
            "compose_service": labels.get("com.docker.compose.service") or "",
            "compose_dir": labels.get("com.docker.compose.project.working_dir") or "",
            "started_at": dstate.get("StartedAt") or "",
            "restart_count": detail.get("RestartCount") or 0,
            "log_driver": driver,
            "logs_readable": driver in ("json-file", "local", "journald", ""),
            "excluded": excluded(labels, name),
            "tty": bool((detail.get("Config") or {}).get("Tty")),
            "ports": sorted(set(ports)),
        })
    for cid in list(INSPECT_CACHE):
        if cid not in {c.get("Id") for c in listing}:
            INSPECT_CACHE.pop(cid, None)
    return result


EVENT_TEXT = {
    "start": ("info", "Container gestartet"),
    "restart": ("warning", "Container neu gestartet"),
    "stop": ("notice", "Container angehalten"),
    "kill": ("notice", "Container beendet (Signal)"),
    "oom": ("critical", "Speicher erschöpft (OOM) - Prozess vom Kernel beendet"),
    "pause": ("notice", "Container pausiert"),
    "unpause": ("info", "Container fortgesetzt"),
    "destroy": ("notice", "Container entfernt"),
}


def docker_events(state):
    """Zustandswechsel der Container (Start, Absturz, OOM, Healthcheck)."""
    since = int(state.get("events_since") or time.time())
    until = int(time.time())
    if until <= since:
        return []
    filters = urllib.parse.quote(json.dumps({"type": ["container"]}))
    status, data = docker_get("/events?since=%d&until=%d&filters=%s" % (since, until, filters), timeout=15)
    state["events_since"] = until
    if status != 200:
        return []
    events = []
    for line in data.decode("utf-8", "replace").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        attrs = (e.get("Actor") or {}).get("Attributes") or {}
        name = attrs.get("name") or ""
        action = (e.get("Action") or e.get("status") or "").split(":")[0].strip()
        if not name or excluded(attrs, name):
            continue
        when = int(e.get("timeNano") or 0) or int(e.get("time") or until) * 1000000000
        if action == "die":
            code = attrs.get("exitCode", "?")
            level = "info" if str(code) in ("0", "143") else "error"
            text = "Container beendet (Exit-Code %s)" % code
        elif action == "health_status":
            health = (e.get("Action") or "").split(":", 1)[-1].strip()
            level = "warning" if health == "unhealthy" else "info"
            text = "Healthcheck: %s" % health
        elif action in EVENT_TEXT:
            level, text = EVENT_TEXT[action]
        else:
            continue
        if LEVEL_PRIO.get(level, 6) > MIN_PRIO_NUM:
            continue
        image = attrs.get("image") or ""
        events.append({"level": level, "message": "%s%s" % (text, (" - " + image) if image else ""),
                       "container": name[:200], "stream": "event", "timestamp": iso(when),
                       "source": "docker-events"})
    return events


def container_logs(state, item):
    """Neue Zeilen eines Containers seit dem letzten Blick."""
    cid = item["id"]
    entry = state["containers"].get(item["name"]) or {}
    if entry.get("id") != cid:
        # Neuer oder neu erzeugter Container (z.B. nach "compose up").
        started = ts_ns(item.get("started_at"))
        if started and started > (STARTED_AT - 10) * 1000000000:
            last = started - 1
        elif entry.get("last_ns"):
            last = entry["last_ns"]
        else:
            last = int(time.time() * 1000000000)
        entry = {"id": cid, "last_ns": last}
    since = "%d.%09d" % divmod(entry["last_ns"], 1000000000)
    status, data = docker_get("/containers/%s/logs?stdout=1&stderr=1&timestamps=1&since=%s"
                              % (cid, since), timeout=20, limit=MAX_LOG_BYTES)
    if status != 200:
        state["containers"][item["name"]] = entry
        return []
    events = []
    skipped = 0
    for stream, line in demux(data, item.get("tty")):
        stamp, _, text = line.partition(" ")
        ns = ts_ns(stamp)
        if not ns or ns <= entry["last_ns"]:
            continue
        entry["last_ns"] = ns
        text = decode_message(text)
        if not text:
            continue
        if len(events) >= MAX_LINES_PER_CONTAINER:
            skipped += 1
            continue
        level = detect_level(text, stream)
        if LEVEL_PRIO.get(level, 6) > MIN_PRIO_NUM:
            continue
        events.append({"level": level, "message": text, "container": item["name"][:200],
                       "stream": stream, "timestamp": iso(ns)})
    if skipped:
        events.append({"level": "warning", "container": item["name"][:200], "stream": "event",
                       "message": "%d weitere Zeilen übersprungen (Container schreibt zu viel)" % skipped,
                       "source": "logbot-agent"})
    state["containers"][item["name"]] = entry
    return events


def docker_loop():
    state = load_docker_state()
    state.setdefault("containers", {})
    last_inventory = 0
    last_save = 0
    while True:
        try:
            if docker_socket():
                now = time.time()
                if now - last_inventory >= 30 or INVENTORY["docker"] is None:
                    INVENTORY["docker"] = docker_info()
                    INVENTORY["containers"] = inventory()
                    last_inventory = now
                events = docker_events(state)
                for item in INVENTORY["containers"]:
                    if item["state"] != "running" or item["excluded"] or not item["logs_readable"]:
                        continue
                    if item["log_driver"] == "journald":
                        continue        # kommt schon ueber journald
                    events.extend(container_logs(state, item))
                if events:
                    pending = state.get("pending") or []
                    if not send_chunks(pending + events):
                        # Server weg: die letzten Zeilen aufheben, nicht ins Unendliche.
                        state["pending"] = (pending + events)[-2000:]
                    else:
                        state["pending"] = []
                if now - last_save >= 10:
                    save_docker_state(state)
                    last_save = now
            else:
                INVENTORY["docker"] = {"installed": bool(shutil.which("docker")), "reachable": False}
                INVENTORY["containers"] = []
        except Exception as e:
            log("Docker-Erfassung: %s" % e)
        time.sleep(DOCKER_POLL)


# ==============================================================================
# Heartbeat und Selbst-Aktualisierung
# ==============================================================================
def os_name():
    try:
        with open("/etc/os-release", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    return line.split("=", 1)[1].strip().strip('"')[:120]
    except Exception:
        pass
    return platform.platform()[:120]


def report(state, version="", message=""):
    api("POST", "/api/agents/update/report", {"hostname": HOSTNAME, "state": state,
                                               "version": version, "message": message[:1900]})


def verify_signature(content, signature_b64):
    """True, wenn die Unterschrift des Servers stimmt. None, wenn nicht pruefbar."""
    if not os.path.exists(PUBKEY_FILE) or not shutil.which("openssl"):
        return None
    with tempfile.TemporaryDirectory() as tmp:
        data = os.path.join(tmp, "p")
        sig = os.path.join(tmp, "s")
        with open(data, "wb") as f:
            f.write(content)
        with open(sig, "wb") as f:
            f.write(base64.b64decode(signature_b64))
        out = subprocess.run(["openssl", "dgst", "-sha256", "-verify", PUBKEY_FILE, "-signature", sig, data],
                             capture_output=True, text=True, timeout=30)
        return out.returncode == 0


def perform_update(update):
    version = update.get("version") or ""
    if not REMOTE_UPDATE:
        report("failed", version, "Fernaktualisierung ist auf diesem Gerät abgeschaltet.")
        return
    log("Update auf %s angefordert - lade Paket" % version)
    report("downloading", version)
    status, result = api("GET", update.get("url") or "", timeout=60, raw=True)
    if status != 200 or not result:
        report("failed", version, "Paket nicht ladbar (HTTP %s)." % status)
        return
    content = result[0]
    if hashlib.sha256(content).hexdigest() != update.get("sha256"):
        report("failed", version, "Prüfsumme stimmt nicht - Paket verworfen.")
        return
    verified = verify_signature(content, update.get("signature") or "")
    if verified is False:
        report("failed", version, "Unterschrift ungültig - Paket verworfen.")
        log("WARNUNG: Update-Paket mit ungueltiger Unterschrift verworfen")
        return
    if verified is None and SKIP_TLS:
        report("failed", version, "Unterschrift nicht prüfbar (openssl oder Schlüssel fehlt) und "
                                  "TLS ohne Zertifikatsprüfung - aus Sicherheitsgründen abgelehnt. "
                                  "Agent einmal neu installieren.")
        return
    os.makedirs(UPDATE_DIR, exist_ok=True)
    os.chmod(UPDATE_DIR, 0o700)
    path = os.path.join(UPDATE_DIR, "install-linux.sh")
    with open(path, "wb") as f:
        f.write(content)
    os.chmod(path, 0o700)
    report("installing", version)
    unit = "logbot-agent-upgrade-%d" % int(time.time())
    # Eigene Unit: der Installer startet diesen Dienst neu - als Kindprozess
    # wuerde er dabei selbst mit beendet.
    cmd = ["systemd-run", "--unit", unit, "--collect", "--quiet", "/bin/bash", path, "upgrade"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if out.returncode != 0:
            report("failed", version, "Installer nicht startbar: %s" % (out.stderr or out.stdout).strip()[:300])
    except Exception as e:
        report("failed", version, "Installer nicht startbar: %s" % e)


def heartbeat_loop():
    time.sleep(3)
    while True:
        body = {"hostname": HOSTNAME, "device_type": "linux_agent", "agent_version": AGENT_VERSION,
                "os": os_name(), "remote_update": REMOTE_UPDATE,
                "capabilities": ["heartbeat", "self-update", "docker", "signed-update"]}
        ip = local_ip()
        if ip:
            body["ip_address"] = ip
        if DOCKER_MODE != "off":
            body["docker"] = INVENTORY.get("docker") or {"installed": False}
            body["containers"] = [{k: v for k, v in c.items() if k != "tty"}
                                  for c in INVENTORY.get("containers") or []]
        status, data = api("POST", "/api/agents/heartbeat", body, timeout=30)
        if status == 404:
            # Aelterer Server ohne Heartbeat - dann eben nur Logs liefern.
            time.sleep(3600)
            continue
        if 200 <= status < 300 and isinstance(data, dict):
            remember_agent_id(data)
            if data.get("update"):
                try:
                    perform_update(data["update"])
                except Exception as e:
                    report("failed", data["update"].get("version", ""), "Update-Fehler: %s" % e)
        time.sleep(HEARTBEAT_SECONDS)


def main():
    if not TOKEN:
        log("FEHLER: agent_token fehlt in config.json")
        sys.exit(1)
    log("gestartet v%s - Ziel: %s Port %s Hostname %s MinLevel %s Docker %s"
        % (AGENT_VERSION, SERVER_FQDN or SERVER_IP, SERVER_PORT, HOSTNAME, MIN_LEVEL, DOCKER_MODE))
    threading.Thread(target=heartbeat_loop, name="heartbeat", daemon=True).start()
    if DOCKER_MODE != "off":
        threading.Thread(target=docker_loop, name="docker", daemon=True).start()
    journal_loop()


if __name__ == "__main__":
    main()
PYEOF
    sed -i "s/__AGENT_VERSION__/${AGENT_VERSION}/" "$AGENT_SCRIPT"
    chmod 700 "$AGENT_SCRIPT"
}

write_agent_config() {
    local skip="false"
    [[ "$INSECURE" == "true" ]] && skip="true"
    cat > "$AGENT_CONFIG" << EOF
{
  "mode": "https",
  "server_fqdn": "${FQDN}",
  "server_ip": "${IPFB}",
  "server_port": ${PORT},
  "agent_token": "${TOKEN}",
  "skip_tls_verify": ${skip},
  "min_level": "${MINLEVEL}",
  "hostname": "$(hostname)",
  "poll_interval": 5,
  "docker": "${DOCKER_MODE}",
  "remote_update": ${REMOTE_UPDATE}
}
EOF
    chmod 600 "$AGENT_CONFIG"
}

write_systemd_unit() {
    cat > "$SYSTEMD_UNIT" << EOF
[Unit]
Description=LogBot Agent v${AGENT_VERSION} (HTTPS Log Forwarder, Container, Selbst-Update)
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=simple
ExecStart=${PYTHON_BIN} ${AGENT_SCRIPT}
Restart=always
RestartSec=10
User=root
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
}

configure_https() {
    ensure_https_deps
    log_info "Konfiguriere HTTPS-Agent (Python systemd-Dienst)..."

    # FQDN (Pflicht, DNS-basiert) - wird auch teilautomatisch immer noch abgefragt
    ask FQDN "LogBot Server FQDN (DNS, z.B. logbot.example.com)" "$FQDN"
    FQDN="${FQDN#http://}"; FQDN="${FQDN#https://}"; FQDN="${FQDN%%/*}"
    [[ -z "$FQDN" ]] && fail "FQDN fehlt. Per --fqdn / LOGBOT_FQDN / Platzhalter setzen (HTTPS ist DNS-basiert)."

    [[ -z "$PORT" ]] && PORT="443"
    ask PORT "Server Port" "$PORT"
    ask IPFB "Optionale IP als Fallback (leer = keine)" "$IPFB"

    # Der hier eingegebene Schluessel ist nur die Eintrittskarte: er wird gleich
    # gegen einen eigenen getauscht (siehe enroll_own_token). Am besten eine
    # Einladung aus dem Web-UI unter "Zugangsschlüssel" - die laeuft ab und
    # gilt nur einmal.
    ask TOKEN "Zugangsschlüssel (Einladung oder Generalschlüssel, im Web-UI erstellt)" "$TOKEN"
    [[ -z "$TOKEN" ]] && fail "Zugangsschlüssel fehlt. Per --token / LOGBOT_TOKEN / Platzhalter setzen."

    local ins="$INSECURE"
    ask ins "Selbstsignierte TLS-Zertifikate akzeptieren? (true/false)" "$INSECURE"
    case "$ins" in true|TRUE|j|J|y|Y|1) INSECURE="true" ;; *) INSECURE="false" ;; esac

    ask MINLEVEL "Log-Level (info/warning/error)" "$MINLEVEL"
    case "$MINLEVEL" in warning|error) : ;; *) MINLEVEL="info" ;; esac

    # DNS/Erreichbarkeit informativ pruefen (kein harter Abbruch)
    if resolve_host "$FQDN"; then
        log_success "FQDN auflösbar: $FQDN"
    else
        log_warn "\"$FQDN\" derzeit nicht per DNS auflösbar - der Dienst versucht es zur Laufzeit erneut."
    fi
    check_tcp_reachable "$FQDN" "$PORT" && log_success "HTTPS ${FQDN}:${PORT} erreichbar" \
        || log_warn "HTTPS ${FQDN}:${PORT} derzeit nicht erreichbar - Dienst wird dennoch eingerichtet."

    # Eigenen Schluessel holen, bevor die Konfiguration geschrieben wird.
    enroll_own_token

    write_agent_script
    write_agent_config
    write_systemd_unit
    log_success "HTTPS-Agent eingerichtet: $AGENT_DIR"
}

# ==============================================================================
# Eigenen Geraeteschluessel holen
# ==============================================================================
# Frueher lag auf jedem Rechner derselbe Schluessel. Wer einen davon aufmachte,
# hatte den Schluessel fuer alle Geraete - und konnte im Namen jedes beliebigen
# Rechners Logzeilen erfinden oder Geraete samt Logs loeschen.
#
# Jetzt tauscht der Agent den mitgegebenen Schluessel beim Installieren gegen
# einen EIGENEN, der nur fuer diesen Rechner gilt. Der mitgegebene darf eine
# kurzlebige Einladung sein (empfohlen) - dann liegt der Generalschluessel
# nirgends mehr herum.
#
# Wichtig: Faellt das Anmelden aus - weil der Server noch eine aeltere Fassung
# faehrt und den Endpunkt nicht kennt -, laeuft die Installation mit dem
# mitgegebenen Schluessel weiter. Ein Agent, der sich wegen einer Neuerung
# gar nicht erst installieren laesst, waere die schlechtere Loesung.
# Umgesetzt mit python3 statt curl: python3 ist fuer den Agenten ohnehin
# Voraussetzung (ensure_https_deps stellt es sicher), curl ist auf manchen
# Minimal-Installationen nicht dabei. Ein Abhaengigkeitsproblem weniger.
enroll_own_token() {
    local host; host="$(hostname)"
    log_info "Melde diesen Rechner am Server an (eigener Schlüssel)..."

    local result
    mkdir -p "$AGENT_DIR"
    result="$("$PYTHON_BIN" - "$FQDN" "$PORT" "$TOKEN" "$host" "$INSECURE" "$AGENT_DIR/update_pubkey.pem" <<'PYENROLL'
import json
import os
import ssl
import sys
import urllib.error
import urllib.request

fqdn, port, token, hostname, insecure, pubkey_path = sys.argv[1:7]

context = None
if insecure == "true":
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

payload = json.dumps({"hostname": hostname, "device_type": "linux_agent"}).encode()
request = urllib.request.Request(
    f"https://{fqdn}:{port}/api/agents/enroll",
    data=payload,
    method="POST",
    headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
)

try:
    with urllib.request.urlopen(request, timeout=20, context=context) as response:
        data = json.loads(response.read().decode("utf-8", "replace"))
    own = (data.get("token") or "").strip()
    pem = data.get("update_pubkey_pem") or ""
    if pem.startswith("-----BEGIN PUBLIC KEY-----"):
        # Damit prueft der Agent spaeter jedes Update auf die Unterschrift des Servers.
        with open(pubkey_path, "w", encoding="utf-8") as handle:
            handle.write(pem)
        os.chmod(pubkey_path, 0o644)
    print("OK " + own if own else "EMPTY")
except urllib.error.HTTPError as exc:
    print(f"HTTP {exc.code}")
except Exception as exc:                                    # Netz, TLS, DNS
    print(f"UNREACHABLE {exc}")
PYENROLL
)" || result="UNREACHABLE"

    case "$result" in
        OK\ *)
            TOKEN="${result#OK }"
            log_success "Eigener Geräteschlüssel erhalten - der mitgegebene wird nicht gespeichert."
            ;;
        "HTTP 404")
            log_warn "Der Server kennt die Anmeldung noch nicht (ältere Fassung). Nehme den mitgegebenen Schlüssel."
            ;;
        "HTTP 401"|"HTTP 403")
            fail "Der Server hat den Schlüssel abgelehnt. Stimmt er noch, oder ist die Einladung abgelaufen?"
            ;;
        UNREACHABLE*)
            log_warn "Server nicht erreichbar - es wird der mitgegebene Schlüssel eingetragen."
            ;;
        *)
            log_warn "Anmeldung nicht möglich (${result}). Nehme den mitgegebenen Schlüssel."
            ;;
    esac
}

start_https_service() {
    log_info "Starte LogBot Agent-Dienst..."
    systemctl enable "$SERVICE_NAME" >/dev/null 2>&1 || true
    systemctl restart "$SERVICE_NAME"
    sleep 2
    systemctl is-active --quiet "$SERVICE_NAME" && log_success "Dienst läuft: $SERVICE_NAME" \
        || fail "Dienst konnte nicht gestartet werden. Prüfe: journalctl -u ${SERVICE_NAME} -n 50"
}

# ==============================================================================
# Test
# ==============================================================================

send_test_message() {
    if [[ -f "$AGENT_CONFIG" ]] && command -v python3 >/dev/null 2>&1; then
        log_info "Sende HTTPS-Test-Nachrichten..."
        if python3 - "$AGENT_CONFIG" "$(hostname)" "$AGENT_VERSION" <<'PYEOF'
import json, ssl, socket, sys, urllib.request, urllib.error
cfg = json.load(open(sys.argv[1], encoding="utf-8"))
hostname, version = sys.argv[2], sys.argv[3]
fqdn = (cfg.get("server_fqdn") or "").strip()
ip = (cfg.get("server_ip") or "").strip()
port = int(cfg.get("server_port") or 443)
token = (cfg.get("agent_token") or "").strip()
skip = bool(cfg.get("skip_tls_verify"))

def resolvable(h):
    try:
        socket.getaddrinfo(h, None); return True
    except Exception:
        return False

host = fqdn if (fqdn and resolvable(fqdn)) else (ip or fqdn)
url = "https://%s/api/agents/ingest" % host if port == 443 else "https://%s:%d/api/agents/ingest" % (host, port)
ctx = ssl.create_default_context()
if skip:
    ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
def local_ip():
    try:
        family, _, _, _, addr = socket.getaddrinfo(host, port, 0, socket.SOCK_DGRAM)[0]
        s = socket.socket(family, socket.SOCK_DGRAM)
        try:
            s.connect(addr); return s.getsockname()[0]
        finally:
            s.close()
    except Exception:
        return ""

data = {"hostname": hostname, "device_type": "linux_agent", "events": [
    {"level": "info", "source": "logbot-test", "message": "LogBot Agent v%s - Installation erfolgreich" % version},
    {"level": "warning", "source": "logbot-test", "message": "LogBot Agent v%s - Test Warning" % version},
    {"level": "error", "source": "logbot-test", "message": "LogBot Agent v%s - Test Error" % version},
]}
ip_addr = (cfg.get("ip_address") or "").strip() or local_ip()
if ip_addr:
    data["ip_address"] = ip_addr
body = json.dumps(data).encode("utf-8")
req = urllib.request.Request(url, data=body, method="POST", headers={
    "Authorization": "Bearer " + token, "Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
        print("accepted=%s" % r.read().decode("utf-8", "replace"))
    sys.exit(0)
except urllib.error.HTTPError as e:
    print("HTTP %s: %s" % (e.code, e.read().decode("utf-8", "replace")[:200])); sys.exit(1)
except Exception as e:
    print("Fehler: %s" % e); sys.exit(1)
PYEOF
        then
            log_success "HTTPS-Test-Nachrichten gesendet"
        else
            log_warn "HTTPS-Test fehlgeschlagen - Server/Token/TLS prüfen."
        fi
        log_info "Prüfe im LogBot Web-Interface ob die Nachrichten angekommen sind"
        return
    fi

    log_info "Sende Test-Nachricht (Syslog)..."
    logger -p user.info -t "logbot-test" "LogBot Agent v${AGENT_VERSION} - Installation erfolgreich auf $(hostname)"
    logger -p user.warning -t "logbot-test" "LogBot Agent v${AGENT_VERSION} - Test Warning"
    logger -p user.err -t "logbot-test" "LogBot Agent v${AGENT_VERSION} - Test Error"
    log_success "Test-Nachrichten gesendet"
    log_info "Prüfe im LogBot Web-Interface ob die Nachrichten angekommen sind"
}

# ==============================================================================
# Vorhandene Installation
# ==============================================================================

handle_existing_installation() {
    is_installed || return 0
    log_warn "Es scheint bereits eine LogBot-Installation vorhanden zu sein."
    syslog_installed && echo "  - Syslog-Konfiguration: $CONFIG_FILE"
    https_installed && echo "  - HTTPS-Dienst: $SERVICE_NAME ($AGENT_DIR)"
    local choice="1"
    ask choice "1) Neu konfigurieren  2) Deinstallieren  3) Abbrechen" "1"
    case "$choice" in
        2) uninstall ""; exit 0 ;;
        3) log_info "Abgebrochen."; exit 0 ;;
        *) log_info "Neuinstallation - vorhandene Konfiguration wird ersetzt." ;;
    esac
}

# ==============================================================================
# Installations-Ablauf
# ==============================================================================

do_install() {
    require_root
    interactive_gate
    handle_existing_installation

    # Modus (Standard: https)
    ask MODE "Modus (https/syslog)" "$MODE"
    case "$MODE" in syslog|SYSLOG|2) MODE="syslog" ;; *) MODE="https" ;; esac

    if [[ "$MODE" == "https" ]]; then
        configure_https
        start_https_service
        send_test_message
        print_summary "https"
    else
        configure_syslog
        restart_rsyslog
        send_test_message
        print_summary "syslog"
    fi
}

# ==============================================================================
# Deinstallation
# ==============================================================================

uninstall() {
    local mode="${1:-}"
    local do_purge_server=false
    interactive_gate
    log_info "Deinstalliere LogBot Agent..."

    if [[ "$mode" == "purge" ]]; then
        do_purge_server=true
    elif [[ -z "$mode" ]]; then
        local rm_mode="1"
        ask rm_mode "Was entfernen? 1) Nur lokal  2) Vollständig (inkl. Server-Eintrag + Logs)" "1"
        [[ "$rm_mode" == "2" ]] && do_purge_server=true
    fi

    # Server-Purge zuerst, solange Token/Config noch vorhanden sind
    [[ "$do_purge_server" == true ]] && purge_server_entry

    # HTTPS-Dienst + Verzeichnis (inkl. cursor) entfernen.
    # `timeout` davor: reagiert der Dienst nicht mehr, wartet systemctl sonst
    # bis zu 90 Sekunden pro Aufruf - und die Deinstallation sieht aus, als
    # haenge sie. Nach 20 s wird nachgeholfen.
    if [[ -f "$SYSTEMD_UNIT" ]] || systemctl list-unit-files 2>/dev/null | grep -q "^${SERVICE_NAME}.service"; then
        if ! timeout 20 systemctl stop "$SERVICE_NAME" 2>/dev/null; then
            log_warn "Der Dienst liess sich nicht sauber stoppen - wird abgeschossen."
            timeout 10 systemctl kill -s KILL "$SERVICE_NAME" 2>/dev/null || true
        fi
        timeout 15 systemctl disable "$SERVICE_NAME" 2>/dev/null || true
        rm -f "$SYSTEMD_UNIT"
        timeout 15 systemctl daemon-reload 2>/dev/null || true
        timeout 15 systemctl reset-failed "$SERVICE_NAME" 2>/dev/null || true
        log_info "HTTPS-Dienst entfernt: $SERVICE_NAME"
    fi
    if [[ -d "$AGENT_DIR" ]]; then
        rm -rf "$AGENT_DIR"
        log_info "Agent-Verzeichnis entfernt: $AGENT_DIR"
    fi
    rm -rf "/var/lib/logbot-agent" 2>/dev/null || true   # Altstand vor v2026.07.18.16

    # Syslog-Konfiguration entfernen
    if [[ -f "$CONFIG_FILE" ]]; then
        rm -f "$CONFIG_FILE"
        log_info "rsyslog-Konfiguration entfernt: $CONFIG_FILE"
    fi
    rm -f "${CONFIG_FILE}.backup."* 2>/dev/null || true
    rm -f "${QUEUE_PREFIX}"* 2>/dev/null || true
    if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet rsyslog 2>/dev/null; then
        timeout 30 systemctl restart rsyslog || log_warn "rsyslog liess sich nicht neu starten - bitte selbst nachsehen."
    fi

    log_success "LogBot Agent wurde entfernt (lokal)."
}

# Meldet den Agent auf dem Server ab und laesst dort Eintrag und Logs loeschen.
#
# Zwei Dinge, die hier frueher schiefgingen:
#   1. Drei blockierende Rueckfragen. Ohne Terminal blieb die Deinstallation
#      hier stehen - die Werte stehen aber ohnehin in der Konfiguration.
#   2. `curl` ohne Zeitlimit. War der Server nicht erreichbar (abgebaut, Firewall,
#      falscher FQDN), haing der Aufruf minutenlang. Jetzt: hoechstens 20 s.
#
# Neu ist ausserdem die Zuordnung ueber die gespeicherte Geraetenummer: der
# Server loescht damit genau den Eintrag dieses Rechners. Fehlt sie, greift der
# Hostname - dann aber gleich fuer alle Eintraege dieses Namens, damit keine
# Karteileichen aus frueheren IP-Wechseln liegen bleiben.
purge_server_entry() {
    detect_server_from_config
    local api_host="${FQDN:-$SERVER_HOST_DETECTED}"
    local api_port="${PORT:-${SERVER_PORT_DETECTED:-443}}"
    local api_token="${TOKEN:-$TOKEN_DETECTED}"

    # Nur nachfragen, was tatsaechlich fehlt - und auch das nur mit Zeitlimit.
    [[ -z "$api_host" ]]  && ask api_host  "Server Host/FQDN"      "$api_host"
    [[ -z "$api_port" ]]  && ask api_port  "Server Port"           "443"
    [[ -z "$api_token" ]] && ask api_token "Agent Token (Bearer)"  "$api_token"

    if [[ -z "$api_token" || -z "$api_host" ]]; then
        log_warn "Kein Token/Host bekannt - der Server-Eintrag bleibt stehen."
        log_info "Nachholen im Web-UI unter 'Geräte': dort das Gerät löschen (mit Logs)."
        return 0
    fi

    if ! command -v curl >/dev/null 2>&1; then
        log_warn "curl nicht gefunden - der Server-Eintrag bleibt stehen."
        return 0
    fi

    local host_ip mac_addr agent_id
    host_ip=$(hostname -I 2>/dev/null | awk '{print $1}')
    mac_addr=$(ip link show 2>/dev/null | awk '$1=="link/ether"{print $2; exit}')
    [[ -z "$mac_addr" ]] && mac_addr=$(cat /sys/class/net/*/address 2>/dev/null | grep -v '^00:00:00:00:00:00$' | head -1)
    agent_id="$(cat "${AGENT_DIR}/agent_id" 2>/dev/null | tr -dc '0-9')"

    local url_base
    [[ "$api_port" == "443" ]] && url_base="https://${api_host}" || url_base="https://${api_host}:${api_port}"

    # agent_id nur mitschicken, wenn es eine gibt - sonst waere es JSON-null.
    local id_field=""
    [[ -n "$agent_id" ]] && id_field="\"agent_id\":${agent_id},"

    local payload
    payload="{${id_field}\"hostname\":\"$(hostname)\",\"ip_address\":\"${host_ip:-}\",\"mac_address\":\"${mac_addr:-}\",\"purge\":true,\"all_for_hostname\":true}"

    local curl_opts=(-sS --connect-timeout 8 --max-time 20)
    [[ "$INSECURE" == "true" ]] && curl_opts+=(-k)

    log_info "Melde den Agent auf dem Server ab (${url_base})..."

    local response http_code
    response="$(curl "${curl_opts[@]}" -w '\n%{http_code}' -X POST \
        "${url_base}/api/agents/decommission" \
        -H "Authorization: Bearer $api_token" \
        -H "Content-Type: application/json" \
        -d "$payload" 2>&1)" || true

    http_code="$(printf '%s' "$response" | tail -n1)"
    local body
    body="$(printf '%s' "$response" | sed '$d')"

    case "$http_code" in
        2*)
            log_success "Auf dem Server abgeräumt: ${body}"
            ;;
        404)
            log_info "Auf dem Server gab es dazu keinen Eintrag (mehr) - nichts zu tun."
            ;;
        401|403)
            log_warn "Der Server hat den Token abgelehnt - der Eintrag bleibt stehen."
            log_info "Im Web-UI unter 'Geräte' von Hand löschen."
            ;;
        *)
            log_warn "Der Server war nicht erreichbar (${http_code:-keine Antwort}) - der Eintrag bleibt stehen."
            log_info "Im Web-UI unter 'Geräte' von Hand löschen."
            ;;
    esac
    return 0
}

# ==============================================================================
# Upgrade: vom Agent selbst angestossen (Selbst-Aktualisierung)
# ==============================================================================
# Laeuft als eigene systemd-Unit (systemd-run), damit der Neustart des Dienstes
# den Installer nicht mitreisst. Konfiguration, Schluessel und Cursor bleiben;
# ersetzt werden Agent-Skript und Dienstdatei. Startet die neue Fassung nicht,
# wird die alte zurueckgelegt und der Fehlschlag an den Server gemeldet.
report_update() {
    local state="$1" message="$2"
    [[ -f "$AGENT_CONFIG" ]] || return 0
    python3 - "$AGENT_CONFIG" "$state" "$AGENT_VERSION" "$message" <<'PYREPORT' 2>/dev/null || true
import json, socket, ssl, sys, urllib.request
cfg = json.load(open(sys.argv[1], encoding="utf-8"))
state, version, message = sys.argv[2:5]
host = (cfg.get("server_fqdn") or "").strip()
try:
    socket.getaddrinfo(host, None)
except Exception:
    host = (cfg.get("server_ip") or host).strip()
port = int(cfg.get("server_port") or 443)
url = ("https://%s" % host if port == 443 else "https://%s:%d" % (host, port)) + "/api/agents/update/report"
ctx = ssl.create_default_context()
if cfg.get("skip_tls_verify"):
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
body = json.dumps({"hostname": cfg.get("hostname") or socket.gethostname(), "state": state,
                   "version": version, "message": message[:1900]}).encode()
req = urllib.request.Request(url, data=body, method="POST", headers={
    "Authorization": "Bearer " + (cfg.get("agent_token") or ""), "Content-Type": "application/json"})
urllib.request.urlopen(req, timeout=15, context=ctx).read()
PYREPORT
}

do_upgrade() {
    require_root
    ASSUME_YES="true"
    [[ -f "$AGENT_CONFIG" ]] || fail "Kein HTTPS-Agent installiert (${AGENT_CONFIG} fehlt) - bitte normal installieren."
    PYTHON_BIN="$(command -v python3 || true)"
    [[ -z "$PYTHON_BIN" ]] && fail "python3 fehlt."
    log_info "Aktualisiere LogBot Agent auf v${AGENT_VERSION}..."

    # Neue Schluessel in der Konfiguration ergaenzen, vorhandene nie anfassen.
    python3 - "$AGENT_CONFIG" <<'PYCFG' || true
import json, sys
path = sys.argv[1]
cfg = json.load(open(path, encoding="utf-8"))
cfg.setdefault("docker", "auto")
cfg.setdefault("remote_update", True)
json.dump(cfg, open(path, "w", encoding="utf-8"), indent=2)
PYCFG
    chmod 600 "$AGENT_CONFIG"

    local backup="${AGENT_SCRIPT}.bak" unit_backup="${SYSTEMD_UNIT}.bak"
    cp -f "$AGENT_SCRIPT" "$backup" 2>/dev/null || true
    cp -f "$SYSTEMD_UNIT" "$unit_backup" 2>/dev/null || true

    write_agent_script
    write_systemd_unit
    systemctl restart "$SERVICE_NAME" || true
    sleep 15
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        rm -f "$backup" "$unit_backup"
        log_success "Agent laeuft in Fassung ${AGENT_VERSION}."
        report_update "done" "Aktualisiert auf ${AGENT_VERSION}."
        return 0
    fi

    local why
    why="$(journalctl -u "$SERVICE_NAME" -n 15 --no-pager 2>/dev/null | tail -n 8 | tr '\n' ' ' | cut -c1-900)"
    log_error "Die neue Fassung startet nicht - nehme die alte zurueck."
    [[ -f "$backup" ]] && mv -f "$backup" "$AGENT_SCRIPT"
    [[ -f "$unit_backup" ]] && mv -f "$unit_backup" "$SYSTEMD_UNIT"
    systemctl daemon-reload || true
    systemctl restart "$SERVICE_NAME" || true
    report_update "rolled_back" "Neue Fassung startete nicht, alte wiederhergestellt: ${why}"
    exit 1
}

# ==============================================================================
# Zusammenfassung
# ==============================================================================

print_summary() {
    local mode="${1:-https}"
    echo ""
    echo "=============================================="
    echo -e "${GREEN}LogBot Agent v${AGENT_VERSION} installiert!${NC}"
    echo "=============================================="
    if [[ "$mode" == "https" ]]; then
        local url_host="$FQDN"
        [[ "${PORT:-443}" != "443" ]] && url_host="${FQDN}:${PORT}"
        echo "Modus:         HTTPS (verschlüsselt + Token)"
        echo "Container:     $([[ "$DOCKER_MODE" == "off" ]] && echo "nicht erfasst (--no-docker)" || echo "werden erfasst, sobald Docker/Podman da ist")"
        echo "Updates:       $([[ "$REMOTE_UPDATE" == "false" ]] && echo "nur von Hand (--no-remote-update)" || echo "vom Server gesteuert, signiert geprüft")"
        echo "Ziel:          https://${url_host}/api/agents/ingest"
        echo "Installation:  $AGENT_DIR"
        echo "Dienst:        $SERVICE_NAME"
        echo ""
        echo "  systemctl status ${SERVICE_NAME}     # Status"
        echo "  journalctl -u ${SERVICE_NAME} -f     # Dienst-Logs"
    else
        echo "Modus:         Syslog (rsyslog)"
        echo "Konfiguration: $CONFIG_FILE"
        echo ""
        echo "  systemctl status rsyslog     # Status"
    fi
    echo ""
    echo "Deinstallation:  sudo bash $0 uninstall"
    echo ""
}

# ==============================================================================
# Hauptprogramm
# ==============================================================================

main() {
    parse_args "$@"

    echo ""
    echo "=============================================="
    echo "  LogBot Agent v${AGENT_VERSION} - Linux"
    echo "  Modus: ${MODE}  |  Auto-Start in ${PROMPT_TIMEOUT}s (Taste = manuell)"
    echo "=============================================="

    case "$ACTION" in
        uninstall)        require_root; uninstall "" ;;
        uninstall-purge)  require_root; uninstall "purge" ;;
        test)             send_test_message ;;
        upgrade)          do_upgrade ;;
        *)                do_install ;;
    esac
}

main "$@"
