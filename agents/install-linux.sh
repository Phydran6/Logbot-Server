#!/bin/bash
# ==============================================================================
# Name:        Phydran6
# Kontakt:     Phydran6
# Version:     2026.07.09.19.55.08
# Changelog:   ../CHANGELOG/agents.md
# Beschreibung: Linux Installer
#               Konfiguriert rsyslog zum Weiterleiten an LogBot Server
#               Keine zusätzlichen Abhängigkeiten erforderlich!
# ==============================================================================

set -e

# Farben
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

AGENT_VERSION="2026.07.09.19.55.08"
CONFIG_FILE="/etc/rsyslog.d/99-logbot.conf"
QUEUE_PREFIX="/var/spool/rsyslog/logbot_queue"

# ==============================================================================
# Hilfsfunktionen
# ==============================================================================

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ==============================================================================
# Server-Konfig lesen
# ==============================================================================

detect_server_from_config() {
    if [[ ! -f "$CONFIG_FILE" ]]; then
        return
    fi
    local line target host_port
    line=$(grep -E '@@?' "$CONFIG_FILE" | tail -1 || true)
    if [[ -z "$line" ]]; then
        return
    fi
    target="${line##*@}"
    host_port="${target%% *}"
    SERVER_HOST_DETECTED="${host_port%:*}"
    SERVER_PORT_DETECTED="${host_port##*:}"
}

# ==============================================================================
# Voraussetzungen
# ==============================================================================

check_requirements() {
    log_info "Prüfe Voraussetzungen..."
    
    # Root-Check
    if [[ $EUID -ne 0 ]]; then
        log_error "Dieses Script muss als root ausgeführt werden!"
        log_info "Aufruf: sudo bash $0"
        exit 1
    fi
    
    # rsyslog prüfen
    if ! command -v rsyslogd &> /dev/null; then
        log_warn "rsyslog nicht gefunden, installiere..."
        
        if command -v apt-get &> /dev/null; then
            apt-get update && apt-get install -y rsyslog
        elif command -v yum &> /dev/null; then
            yum install -y rsyslog
        elif command -v dnf &> /dev/null; then
            dnf install -y rsyslog
        else
            log_error "Paketmanager nicht erkannt. Bitte rsyslog manuell installieren."
            exit 1
        fi
    fi
    
    # rsyslog Service prüfen
    if ! systemctl is-active --quiet rsyslog 2>/dev/null; then
        log_info "Starte rsyslog Service..."
        systemctl enable rsyslog
        systemctl start rsyslog
    fi
    
    log_success "Voraussetzungen erfüllt"
}

# ==============================================================================
# Installation erkennen / Auswahl
# ==============================================================================

is_installed() {
    [[ -f "$CONFIG_FILE" ]] && grep -q "LogBot Agent v" "$CONFIG_FILE"
}

handle_existing_installation() {
    if is_installed; then
        echo ""
        log_warn "Es scheint bereits eine LogBot Konfiguration vorhanden zu sein: $CONFIG_FILE"
        echo "Optionen:"
        echo "  1) Neu installieren (Konfiguration wird ueberschrieben)"
        echo "  2) Deinstallieren"
        echo "  3) Abbrechen"
        read -p "Auswahl [1]: " EXISTING_CHOICE
        
        case "$EXISTING_CHOICE" in
            2)
                uninstall
                exit 0
                ;;
            3)
                log_info "Abgebrochen."
                exit 0
                ;;
            *)
                log_info "Neuinstallation ausgewaehlt - vorhandene Konfiguration wird ersetzt."
                ;;
        esac
    fi
}

# ==============================================================================
# Server-Adresse: DNS-Aufloesung + Erreichbarkeit pruefen
# FQDN (z.B. logbot.phytech.de) und IP werden gleichermassen unterstuetzt.
# ==============================================================================

# Prueft, ob ein Host (FQDN oder IP) aufloesbar ist. Nutzt mehrere Methoden,
# damit nicht eine einzelne getent-Eigenheit zum Abbruch fuehrt.
resolve_host() {
    local host="$1"

    # Reine IPv4-Adresse gilt immer als aufloesbar
    if [[ "$host" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        return 0
    fi

    # 1) getent ahosts - respektiert nsswitch inkl. DNS (A + AAAA)
    if command -v getent >/dev/null 2>&1; then
        getent ahosts "$host" >/dev/null 2>&1 && return 0
    fi

    # 2) python3 socket.getaddrinfo (falls vorhanden)
    if command -v python3 >/dev/null 2>&1; then
        python3 -c 'import socket,sys; socket.getaddrinfo(sys.argv[1], None)' "$host" >/dev/null 2>&1 && return 0
    fi

    # 3) dig / host als weitere Fallbacks (verlaessliche Exit-Codes).
    #    nslookup wird bewusst NICHT genutzt: liefert auf vielen Systemen
    #    auch bei NXDOMAIN rc=0 und wuerde falsch-positiv "aufloesbar" melden.
    if command -v dig >/dev/null 2>&1; then
        [[ -n "$(dig +short "$host" 2>/dev/null)" ]] && return 0
    fi
    if command -v host >/dev/null 2>&1; then
        host "$host" >/dev/null 2>&1 && return 0
    fi

    return 1
}

# Testet TCP-Erreichbarkeit host:port - dependency-frei via /dev/tcp, sonst nc.
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

# Prueft die eingegebene Server-Adresse. Bricht NICHT hart ab - der Nutzer
# entscheidet, denn rsyslog loest den Namen zur Laufzeit ohnehin erneut auf.
verify_server_address() {
    local host="$SERVER_HOST" port="$SERVER_PORT"
    [[ -z "$host" ]] && return

    if resolve_host "$host"; then
        log_success "Adresse aufloesbar: $host"
    else
        log_warn "\"$host\" konnte aktuell nicht per DNS aufgeloest werden."
        log_info "Ursachen: DNS/hosts-Eintrag fehlt, Tippfehler, oder Name nur intern gueltig."
        read -p "Trotzdem verwenden? rsyslog versucht die Aufloesung zur Laufzeit erneut. [J/n] " ans
        if [[ "$ans" =~ ^[Nn]$ ]]; then
            log_error "Abgebrochen. Bitte Adresse/DNS pruefen."
            exit 1
        fi
    fi

    # Erreichbarkeit nur bei TCP sinnvoll testbar (UDP ist verbindungslos)
    if [[ "${PROTO_NAME:-UDP}" == "TCP" ]]; then
        if check_tcp_reachable "$host" "$port"; then
            log_success "TCP ${host}:${port} erreichbar"
        else
            log_warn "TCP ${host}:${port} derzeit nicht erreichbar (Firewall/Server?). Konfiguration wird dennoch geschrieben."
        fi
    fi
}

configure_rsyslog() {
    log_info "Konfiguriere rsyslog..."
    
    # Server-Adresse abfragen
    echo ""
    read -p "LogBot Server Adresse: " SERVER_HOST
    if [[ -z "$SERVER_HOST" ]]; then
        log_error "Server-Adresse ist erforderlich!"
        exit 1
    fi
    
    read -p "LogBot Server Port [514]: " SERVER_PORT
    SERVER_PORT=${SERVER_PORT:-514}

    echo ""
    echo "Protokoll:"
    echo "  1) UDP (Standard, schneller)"
    echo "  2) TCP (zuverlässiger)"
    read -p "Auswahl [1]: " PROTO_CHOICE

    if [[ "$PROTO_CHOICE" == "2" ]]; then
        PROTOCOL="@@"  # @@ = TCP in rsyslog
        PROTO_NAME="TCP"
    else
        PROTOCOL="@"   # @ = UDP in rsyslog
        PROTO_NAME="UDP"
    fi
    PROTOCOL_LOWER=$(echo "$PROTO_NAME" | tr 'A-Z' 'a-z')

    # Server-Adresse pruefen (DNS + Erreichbarkeit) - bricht nicht hart ab
    verify_server_address
    
    # Welche Logs weiterleiten?
    echo ""
    echo "Welche Logs sollen weitergeleitet werden?"
    echo "  1) Alle Logs (empfohlen)"
    echo "  2) Nur wichtige (warning und höher)"
    echo "  3) Nur Fehler (error und höher)"
    read -p "Auswahl [1]: " LOG_LEVEL_CHOICE
    
    case "$LOG_LEVEL_CHOICE" in
        2) LOG_SELECTOR="*.warning" ;;
        3) LOG_SELECTOR="*.err" ;;
        *) LOG_SELECTOR="*.*" ;;
    esac
    
    # Backup falls vorhanden
    if [[ -f "$CONFIG_FILE" ]]; then
        cp "$CONFIG_FILE" "${CONFIG_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
        log_info "Backup der alten Konfiguration erstellt"
    fi
    
    # Konfiguration schreiben
    cat > "$CONFIG_FILE" << EOF
# ==============================================================================
# LogBot Agent v${AGENT_VERSION} - rsyslog Konfiguration
# Erstellt: $(date)
# Server: ${SERVER_HOST}:${SERVER_PORT} (${PROTO_NAME})
#
# Name:        Phydran6
# Kontakt:     Phydran6
# ==============================================================================

# Queue für zuverlässige Übertragung (bei Verbindungsproblemen)
action(
  type="omfwd"
  target="${SERVER_HOST}"
  port="${SERVER_PORT}"
  protocol="${PROTOCOL_LOWER}"
  Template="RSYSLOG_TraditionalFileFormat"
  action.resumeRetryCount="-1"
  queue.type="LinkedList"
  queue.filename="logbot_queue"
  queue.maxDiskSpace="100m"
  queue.saveOnShutdown="on"
)
EOF
    
    log_success "Konfiguration erstellt: $CONFIG_FILE"
}

# ==============================================================================
# Service neustarten
# ==============================================================================

restart_rsyslog() {
    log_info "Starte rsyslog neu..."
    
    # Konfiguration testen
    if rsyslogd -N1 2>/dev/null; then
        systemctl restart rsyslog
        sleep 2
        
        if systemctl is-active --quiet rsyslog; then
            log_success "rsyslog läuft"
        else
            log_error "rsyslog konnte nicht gestartet werden"
            log_info "Prüfe: journalctl -u rsyslog -n 50"
            exit 1
        fi
    else
        log_error "rsyslog Konfiguration fehlerhaft!"
        log_info "Prüfe: rsyslogd -N1"
        exit 1
    fi
}

# ==============================================================================
# Test
# ==============================================================================

send_test_message() {
    log_info "Sende Test-Nachricht..."
    
    # Test-Log via logger senden
    logger -p user.info -t "logbot-test" "LogBot Agent v${AGENT_VERSION} - Installation erfolgreich auf $(hostname)"
    logger -p user.warning -t "logbot-test" "LogBot Agent v${AGENT_VERSION} - Test Warning"
    logger -p user.err -t "logbot-test" "LogBot Agent v${AGENT_VERSION} - Test Error"
    
    log_success "Test-Nachrichten gesendet"
    log_info "Prüfe im LogBot Web-Interface ob die Nachrichten angekommen sind"
}

# ==============================================================================
# Deinstallation
# ==============================================================================

uninstall() {
    # Argument: "purge" => Server-Purge ohne zweite Nachfrage
    local mode="${1:-}"
    local do_purge_server=false
    log_info "Deinstalliere LogBot Agent..."

    if [[ -z "$mode" ]]; then
        echo ""
        echo "Was soll entfernt werden?"
        echo "  1) Nur lokale Agentdaten / Konfiguration"
        echo "  2) Vollst\u00e4ndig (inkl. Server-Eintrag + Logs)"
        read -p "Auswahl [1]: " REMOVE_MODE
        REMOVE_MODE=${REMOVE_MODE:-1}
        [[ "$REMOVE_MODE" == "2" ]] && do_purge_server=true
    elif [[ "$mode" == "purge" ]]; then
        do_purge_server=true
    fi

    # Lokale Dateien entfernen
    if [[ -f "$CONFIG_FILE" ]]; then
        rm -f "$CONFIG_FILE"
        log_info "Konfiguration entfernt: $CONFIG_FILE"
    else
        log_warn "Keine LogBot Konfiguration gefunden"
    fi

    rm -f "${CONFIG_FILE}.backup."* 2>/dev/null || true
    rm -f "${QUEUE_PREFIX}"* 2>/dev/null || true

    systemctl restart rsyslog || true

    if [[ "$do_purge_server" == true ]]; then
        detect_server_from_config
        local default_host="$SERVER_HOST_DETECTED"
        local default_port="${SERVER_PORT_DETECTED:-443}"
        echo ""
        echo "Server-Bereinigung (API-Aufruf)"
        read -p "Server Host [${default_host:-<erforderlich>}]: " API_HOST
        API_HOST=${API_HOST:-$default_host}
        read -p "Server Port [${default_port}]: " API_PORT
        API_PORT=${API_PORT:-$default_port}
        read -p "Agent Token (Bearer) [leer = abbrechen Server-Call]: " AGENT_TOKEN
        read -p "Unsichere Zertifikate erlauben? (self-signed) [y/N]: " SSL_INSECURE

        if [[ -n "$AGENT_TOKEN" && -n "$API_HOST" ]]; then
            local curl_opts=""
            [[ "$SSL_INSECURE" =~ ^[Yy]$ ]] && curl_opts="-k"
            local host_ip
            host_ip=$(hostname -I | awk '{print $1}')
            local mac_addr
            mac_addr=$(ip -o link show | awk '$3=="ether"{print $4; exit}')
            if [[ -z "$mac_addr" ]]; then
                mac_addr=$(ip link show | awk '/link\\/ether/ {print $2; exit}')
            fi
            local payload
            payload=$(cat <<EOF
{"hostname":"$(hostname)","ip_address":"${host_ip:-}","mac_address":"${mac_addr:-}","purge":true}
EOF
)
            local api_url="https://${API_HOST}:${API_PORT}/api/agents/decommission"
            if curl -sSf $curl_opts -X POST "$api_url" \
                -H "Authorization: Bearer $AGENT_TOKEN" \
                -H "Content-Type: application/json" \
                -d "$payload" >/dev/null; then
                log_success "Server-Purge angefordert (Agent + Logs)."
            else
                log_warn "Server-Purge fehlgeschlagen oder nicht erreichbar."
            fi
        else
            log_warn "Kein Token/Host angegeben - Server-Purge ausgelassen."
        fi
    fi

    log_success "LogBot Agent wurde entfernt (lokal)."
}

# ==============================================================================
# Zusammenfassung
# ==============================================================================

print_summary() {
    echo ""
    echo "=============================================="
    echo -e "${GREEN}LogBot Agent v${AGENT_VERSION} installiert!${NC}"
    echo "=============================================="
    echo ""
    echo "Konfiguration: $CONFIG_FILE"
    echo ""
    echo "Test-Befehl:"
    echo "  logger -t test 'Hallo LogBot'"
    echo ""
    echo "Nützliche Befehle:"
    echo "  systemctl status rsyslog      # Status"
    echo "  systemctl restart rsyslog     # Neustart"
    echo "  journalctl -u rsyslog -f      # Logs"
    echo ""
    echo "Deinstallation:"
    echo "  Script ohne Parameter starten und Option w\u00e4hlen."
    echo ""
}

# ==============================================================================
# Hauptprogramm
# ==============================================================================

main() {
    echo ""
    echo "=============================================="
    echo "  LogBot Agent v${AGENT_VERSION} - Linux"
    echo "  (rsyslog Konfiguration)"
    echo "=============================================="
    echo ""
    
    if [[ $# -gt 0 ]]; then
        case "${1:-}" in
            uninstall|remove)
                check_requirements
                uninstall "${2:-}"
                exit 0
                ;;
            test)
                send_test_message
                exit 0
                ;;
        esac
    fi

    echo "Aktion w\u00e4hlen:"
    echo "  1) Installieren / Neu konfigurieren"
    echo "  2) Deinstallieren (nur lokal)"
    echo "  3) Deinstallieren (Server + Logs)"
    echo "  4) Testnachricht senden"
    echo "  5) Abbrechen"
    read -p "Auswahl [1]: " MAIN_CHOICE
    MAIN_CHOICE=${MAIN_CHOICE:-1}

    case "$MAIN_CHOICE" in
        2)
            check_requirements
            uninstall "local"
            ;;
        3)
            check_requirements
            uninstall "purge"
            ;;
        4)
            send_test_message
            ;;
        5)
            log_info "Abgebrochen."
            exit 0
            ;;
        *)
            check_requirements
            handle_existing_installation
            configure_rsyslog
            restart_rsyslog
            send_test_message
            print_summary
            ;;
    esac
}

main "$@"
