#!/bin/bash
# ==============================================================================
# Name:        Philipp Fischer
# Kontakt:     p.fischer@itconex.de
# Version:     2026.01.30.13.30.00
# Beschreibung: LogBot Agent v2026.01.30.13.30.00 - Linux Installer
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

AGENT_VERSION="2026.01.30.13.30.00"
CONFIG_FILE="/etc/rsyslog.d/99-logbot.conf"

# ==============================================================================
# Hilfsfunktionen
# ==============================================================================

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

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
# Konfiguration
# ==============================================================================

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
# Name:        Philipp Fischer
# Kontakt:     p.fischer@itconex.de
# ==============================================================================

# Queue für zuverlässige Übertragung (bei Verbindungsproblemen)
\$ActionQueueType LinkedList
\$ActionQueueFileName logbot_queue
\$ActionQueueMaxDiskSpace 100m
\$ActionQueueSaveOnShutdown on
\$ActionResumeRetryCount -1

# Logs an LogBot Server weiterleiten
${LOG_SELECTOR} ${PROTOCOL}${SERVER_HOST}:${SERVER_PORT}
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
    log_info "Deinstalliere LogBot Agent..."
    
    if [[ -f "$CONFIG_FILE" ]]; then
        rm -f "$CONFIG_FILE"
        systemctl restart rsyslog
        log_success "LogBot Agent Konfiguration entfernt"
    else
        log_warn "Keine LogBot Konfiguration gefunden"
    fi
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
    echo "  sudo bash $0 uninstall"
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
    
    case "${1:-}" in
        uninstall|remove)
            check_requirements
            uninstall
            exit 0
            ;;
        test)
            send_test_message
            exit 0
            ;;
    esac
    
    check_requirements
    configure_rsyslog
    restart_rsyslog
    send_test_message
    print_summary
}

main "$@"
