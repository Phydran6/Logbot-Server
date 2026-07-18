#!/bin/bash
# ==============================================================================
# Name:        Phydran6
# Kontakt:     Phydran6
# Version:     2026.07.18.16.00.00
# Changelog:   ../CHANGELOG/agents.md
# Beschreibung: LogBot Linux Agent - Installer (teilautomatisch)
#
#   Standard = HTTPS: ein schlanker Python-systemd-Dienst sendet ALLE Logs
#   (journald) verschluesselt + Token an  https://<FQDN>/api/agents/ingest
#   Alternativ Syslog (rsyslog -> UDP/TCP). Keine externen Abhaengigkeiten.
#
#   TEILAUTOMATISCH: Jede Abfrage wartet max. 5 s, sonst laeuft der Default.
#   Ohne Terminal (z.B. via Pipe/cron) laeuft alles automatisch mit Defaults.
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

AGENT_VERSION="2026.07.18.16.00.00"

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
PROMPT_TIMEOUT="${LOGBOT_TIMEOUT:-5}"   # Sekunden je Abfrage
ASSUME_YES="false"                      # true => nie fragen, immer Default
ACTION="install"

# --- Konfiguration (Vorrang: Parameter > Umgebungsvariable > Platzhalter) ---
MODE="${LOGBOT_MODE:-${PLACEHOLDER_MODE:-https}}"
FQDN="${LOGBOT_FQDN:-${PLACEHOLDER_FQDN:-}}"
IPFB="${LOGBOT_IP:-}"
PORT="${LOGBOT_PORT:-${PLACEHOLDER_PORT:-}}"
TOKEN="${LOGBOT_TOKEN:-${PLACEHOLDER_TOKEN:-}}"
MINLEVEL="${LOGBOT_MINLEVEL:-${PLACEHOLDER_MINLEVEL:-info}}"
INSECURE="${LOGBOT_INSECURE:-false}"

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

# Timeout-Abfrage: nutzt Default nach PROMPT_TIMEOUT Sekunden oder ohne Terminal.
# ask VARNAME "Frage" "default"
ask() {
    local __name="$1" prompt="$2" def="$3" ans=""
    if [[ "$ASSUME_YES" != "true" ]] && have_tty; then
        read -t "$PROMPT_TIMEOUT" -r -p "$prompt [${def:-leer}] (${PROMPT_TIMEOUT}s Timeout, Enter=Default): " ans </dev/tty || true
        echo ""
    fi
    [[ -z "$ans" ]] && ans="$def"
    printf -v "$__name" '%s' "$ans"
}

show_help() {
    cat <<EOF
LogBot Linux Agent Installer v${AGENT_VERSION}

Aufruf:   sudo bash install-linux.sh [aktion] [optionen]
Aktionen: install (Standard) | uninstall | uninstall-purge | test

Optionen (auch als Umgebungsvariable LOGBOT_*):
  --fqdn <name>       Server-FQDN            (LOGBOT_FQDN)   [Pflicht bei https]
  --token <token>     Agent-Token (Bearer)  (LOGBOT_TOKEN)  [Pflicht bei https]
  --mode <https|syslog>  Modus (Standard https)  (LOGBOT_MODE)
  --port <n>          Port (https=443, syslog=514)  (LOGBOT_PORT)
  --ip <ip>           Optionale IP als Fallback     (LOGBOT_IP)
  --min-level <info|warning|error>            (LOGBOT_MINLEVEL)
  --insecure          Selbstsignierte TLS-Zerts akzeptieren  (LOGBOT_INSECURE=true)
  --yes, --unattended Keine Rueckfragen, alles Default        (ASSUME_YES)
  --timeout <sek>     Wartezeit je Abfrage (Standard 5)      (LOGBOT_TIMEOUT)

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
            --fqdn)          FQDN="${2:-}"; shift ;;
            --fqdn=*)        FQDN="${1#*=}" ;;
            --token)         TOKEN="${2:-}"; shift ;;
            --token=*)       TOKEN="${1#*=}" ;;
            --ip)            IPFB="${2:-}"; shift ;;
            --ip=*)          IPFB="${1#*=}" ;;
            --port)          PORT="${2:-}"; shift ;;
            --port=*)        PORT="${1#*=}" ;;
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

    local proto="udp"
    ask proto "Protokoll (udp/tcp)" "udp"
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
# Liest ALLE Logs aus journald und sendet sie verschlüsselt + Token-authentifiziert
# an  https://<FQDN>/api/agents/ingest  (Batches von max. 50 Events).
# Nur Python-Standardbibliothek - keine externen Abhängigkeiten.
# ==============================================================================
import json
import os
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request

CONFIG_FILE = os.environ.get("LOGBOT_CONFIG", "/opt/logbot-agent/config.json")
CURSOR_FILE = os.environ.get("LOGBOT_CURSOR", "/opt/logbot-agent/cursor")
BATCH_SIZE = 50
MSG_MAX = 2048

# journald PRIORITY (syslog severity 0-7) -> Level-String
PRIO_TO_LEVEL = {0: "critical", 1: "critical", 2: "critical", 3: "error",
                 4: "warning", 5: "notice", 6: "info", 7: "debug"}
# Numerische Schwelle je min_level (kleiner = schwerwiegender)
MIN_PRIO = {"debug": 7, "info": 6, "notice": 5, "warning": 4, "error": 3, "critical": 2}


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


def ingest_url():
    host = target_host()
    if not host:
        return None
    if SERVER_PORT == 443:
        return "https://%s/api/agents/ingest" % host
    return "https://%s:%d/api/agents/ingest" % (host, SERVER_PORT)


def send(events):
    if not events:
        return True
    url = ingest_url()
    if not url:
        log("Kein Ziel (FQDN/IP) konfiguriert")
        return False
    body = json.dumps({"hostname": HOSTNAME, "events": events}).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": "Bearer " + TOKEN,
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=15, context=build_ctx()) as r:
            return 200 <= r.status < 300
    except urllib.error.HTTPError as e:
        log("HTTP %s von %s" % (e.code, url))
        return False
    except Exception as e:
        log("Sendefehler (%s): %s" % (url, e))
        return False


def read_cursor():
    try:
        with open(CURSOR_FILE, "r", encoding="utf-8") as f:
            return f.read().strip() or None
    except FileNotFoundError:
        return None
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


def to_event(j):
    try:
        prio = int(j.get("PRIORITY", 6))
    except Exception:
        prio = 6
    if prio > MIN_PRIO_NUM:
        return None
    level = PRIO_TO_LEVEL.get(prio, "info")
    ident = j.get("SYSLOG_IDENTIFIER") or j.get("_COMM") or "journal"
    unit = j.get("_SYSTEMD_UNIT")
    source = ("%s/%s" % (unit, ident)) if unit else ident
    message = decode_message(j.get("MESSAGE"))
    if not message:
        return None
    return {"level": level, "source": source, "message": message}


def collect_since(cursor):
    # Rückgabe: (events, new_cursor, ok)  - ok=False signalisiert Reseed
    args = ["journalctl", "-o", "json", "--no-pager", "--after-cursor", cursor]
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=60)
    except Exception as e:
        log("journalctl Fehler: %s" % e)
        return [], cursor, True
    if out.returncode != 0:
        log("journalctl rc=%s: %s" % (out.returncode, (out.stderr or "").strip()[:200]))
        return [], cursor, False
    events = []
    newcursor = cursor
    for line in out.stdout.splitlines():
        try:
            j = json.loads(line)
        except Exception:
            continue
        if "__CURSOR" in j:
            newcursor = j["__CURSOR"]
        ev = to_event(j)
        if ev:
            events.append(ev)
    return events, newcursor, True


def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def main():
    if not TOKEN:
        log("FEHLER: agent_token fehlt in config.json")
        sys.exit(1)
    log("gestartet - Ziel: %s Port %s Hostname %s MinLevel %s"
        % (SERVER_FQDN or SERVER_IP, SERVER_PORT, HOSTNAME, MIN_LEVEL))

    cursor = read_cursor()
    while True:
        if not cursor:
            cursor = latest_cursor()
            if cursor:
                write_cursor(cursor)
            else:
                time.sleep(POLL)
                continue

        events, newcursor, ok = collect_since(cursor)
        if not ok:
            # journalctl-Fehler (evtl. ungültiger/rotierter Cursor) -> neu setzen
            cursor = None
            time.sleep(POLL)
            continue

        if events:
            sent_ok = True
            for chunk in chunks(events, BATCH_SIZE):
                if not send(chunk):
                    sent_ok = False
                    break
            if sent_ok:
                cursor = newcursor
                write_cursor(cursor)
            # bei Sendefehler: Cursor NICHT vorrücken -> nächster Durchlauf erneut
        else:
            if newcursor and newcursor != cursor:
                cursor = newcursor
                write_cursor(cursor)

        time.sleep(POLL)


if __name__ == "__main__":
    main()
PYEOF
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
  "poll_interval": 5
}
EOF
    chmod 600 "$AGENT_CONFIG"
}

write_systemd_unit() {
    cat > "$SYSTEMD_UNIT" << EOF
[Unit]
Description=LogBot Agent v${AGENT_VERSION} (HTTPS Log Forwarder)
After=network-online.target
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

    ask TOKEN "Agent-Token (Bearer, im Web-UI erstellt)" "$TOKEN"
    [[ -z "$TOKEN" ]] && fail "Agent-Token fehlt. Per --token / LOGBOT_TOKEN / Platzhalter setzen."

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

    write_agent_script
    write_agent_config
    write_systemd_unit
    log_success "HTTPS-Agent eingerichtet: $AGENT_DIR"
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
body = json.dumps({"hostname": hostname, "events": [
    {"level": "info", "source": "logbot-test", "message": "LogBot Agent v%s - Installation erfolgreich" % version},
    {"level": "warning", "source": "logbot-test", "message": "LogBot Agent v%s - Test Warning" % version},
    {"level": "error", "source": "logbot-test", "message": "LogBot Agent v%s - Test Error" % version},
]}).encode("utf-8")
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

    # HTTPS-Dienst + Verzeichnis (inkl. cursor) entfernen
    if [[ -f "$SYSTEMD_UNIT" ]] || systemctl list-unit-files 2>/dev/null | grep -q "^${SERVICE_NAME}.service"; then
        systemctl stop "$SERVICE_NAME" 2>/dev/null || true
        systemctl disable "$SERVICE_NAME" 2>/dev/null || true
        rm -f "$SYSTEMD_UNIT"
        systemctl daemon-reload 2>/dev/null || true
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
        systemctl restart rsyslog || true
    fi

    log_success "LogBot Agent wurde entfernt (lokal)."
}

purge_server_entry() {
    detect_server_from_config
    local api_host="${FQDN:-$SERVER_HOST_DETECTED}"
    local api_port="${PORT:-${SERVER_PORT_DETECTED:-443}}"
    local api_token="${TOKEN:-$TOKEN_DETECTED}"

    ask api_host "Server Host/FQDN" "$api_host"
    ask api_port "Server Port" "$api_port"
    ask api_token "Agent Token (Bearer)" "$api_token"

    if [[ -z "$api_token" || -z "$api_host" ]]; then
        log_warn "Kein Token/Host - Server-Purge ausgelassen."
        return
    fi

    local curl_opts=()
    [[ "$INSECURE" == "true" ]] && curl_opts+=(-k)

    local host_ip mac_addr
    host_ip=$(hostname -I 2>/dev/null | awk '{print $1}')
    mac_addr=$(ip link show 2>/dev/null | awk '$1=="link/ether"{print $2; exit}')
    [[ -z "$mac_addr" ]] && mac_addr=$(cat /sys/class/net/*/address 2>/dev/null | grep -v '^00:00:00:00:00:00$' | head -1)

    local url_base
    [[ "$api_port" == "443" ]] && url_base="https://${api_host}" || url_base="https://${api_host}:${api_port}"
    local payload
    payload=$(cat <<EOF
{"hostname":"$(hostname)","ip_address":"${host_ip:-}","mac_address":"${mac_addr:-}","purge":true}
EOF
)

    if command -v curl >/dev/null 2>&1; then
        if curl -sSf "${curl_opts[@]}" -X POST "${url_base}/api/agents/decommission" \
            -H "Authorization: Bearer $api_token" \
            -H "Content-Type: application/json" \
            -d "$payload" >/dev/null; then
            log_success "Server-Purge angefordert (Agent + Logs)."
        else
            log_warn "Server-Purge fehlgeschlagen oder nicht erreichbar."
        fi
    else
        log_warn "curl nicht gefunden - Server-Purge ausgelassen."
    fi
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
    echo "  Modus: ${MODE} (teilautomatisch, ${PROMPT_TIMEOUT}s/Abfrage)"
    echo "=============================================="

    case "$ACTION" in
        uninstall)        require_root; uninstall "" ;;
        uninstall-purge)  require_root; uninstall "purge" ;;
        test)             send_test_message ;;
        *)                do_install ;;
    esac
}

main "$@"
