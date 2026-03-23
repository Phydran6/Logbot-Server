#!/bin/bash
# ==============================================================================
#  _                 ____        _
# | |    ___   __ _ | __ )  ___ | |_
# | |   / _ \ / _` ||  _ \ / _ \| __|
# | |__| (_) | (_| || |_) | (_) | |_
# |_____\___/ \__, ||____/ \___/ \__|
#             |___/
# ==============================================================================
# INSTALLATIONS-SCRIPT
# ==============================================================================
#
# Autor:        Philipp Fischer
# Kontakt:      p.fischer@itconex.de
# Version:      2026.01.30.13.30.00
# Erstellt:     Januar 2026
#
# Beschreibung:
#   Automatisiertes Installations-Script für LogBot.
#   Installiert alle erforderlichen Komponenten via Docker Compose.
#
# Voraussetzungen:
#   - Linux System (Debian/Ubuntu empfohlen)
#   - Root-Rechte
#   - Internetzugang (für Docker Installation)
#
# Verwendung:
#   sudo bash install.sh
#
# ==============================================================================

set -e

# Farben für Output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Konfiguration
INSTALL_DIR="/opt/logbot"
LOGBOT_VERSION="2026.01.30.13.30.00"

# ==============================================================================
# Hilfsfunktionen
# ==============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

generate_password() {
    openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 32
}

# ==============================================================================
# Voraussetzungen prüfen
# ==============================================================================

check_requirements() {
    log_info "Prüfe Voraussetzungen..."
    
    # Root-Rechte
    if [[ $EUID -ne 0 ]]; then
        log_error "Dieses Script muss als root ausgeführt werden!"
        exit 1
    fi
    
    # git installieren wenn nicht vorhanden
    if ! command -v git &> /dev/null; then
        log_warn "git nicht gefunden - installiere..."
        sudo apt-get update && sudo apt-get install -y git
    fi
    
    # curl installieren wenn nicht vorhanden
    if ! command -v curl &> /dev/null; then
        log_warn "curl nicht gefunden - installiere..."
        sudo apt-get update && sudo apt-get install -y curl
    fi
    
    # Docker - automatisch installieren wenn nicht vorhanden
    if ! command -v docker &> /dev/null; then
        log_warn "Docker nicht gefunden - installiere automatisch..."
        curl -fsSL https://get.docker.com | sudo sh
        sudo systemctl enable docker
        sudo systemctl start docker
        log_success "Docker installiert"
    fi
    
    # Docker Compose prüfen
    if ! docker compose version &> /dev/null; then
        log_error "Docker Compose nicht verfügbar!"
        exit 1
    fi
    
    log_success "Alle Voraussetzungen erfüllt"
}

# ==============================================================================
# Installation
# ==============================================================================

install_logbot() {
    log_info "Installiere LogBot v${LOGBOT_VERSION}..."
    
    # Installationsverzeichnis erstellen
    if [[ -d "$INSTALL_DIR" ]]; then
        log_warn "Verzeichnis $INSTALL_DIR existiert bereits"
        read -p "Bestehende Installation überschreiben? [j/N] " confirm
        if [[ "$confirm" != "j" && "$confirm" != "J" ]]; then
            log_error "Installation abgebrochen"
            exit 1
        fi
        # Backup erstellen
        BACKUP_DIR="${INSTALL_DIR}.backup.$(date +%Y%m%d_%H%M%S)"
        log_info "Erstelle Backup: $BACKUP_DIR"
        mv "$INSTALL_DIR" "$BACKUP_DIR"
    fi
    
    # Dateien kopieren
    log_info "Kopiere Dateien nach $INSTALL_DIR..."
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    cp -r "$SCRIPT_DIR" "$INSTALL_DIR"
    
    # .env Datei erstellen
    if [[ ! -f "$INSTALL_DIR/.env" ]]; then
        log_info "Erstelle .env Datei..."
        DB_PASSWORD=$(generate_password)
        JWT_SECRET=$(generate_password)
        
        cat > "$INSTALL_DIR/.env" << EOF
# LogBot v${LOGBOT_VERSION} Konfiguration
# Automatisch generiert am $(date)

# Datenbank
DB_USER=logbot
DB_PASSWORD=${DB_PASSWORD}
DB_NAME=logbot

# JWT Secret für API Authentifizierung
JWT_SECRET=${JWT_SECRET}
EOF
        chmod 600 "$INSTALL_DIR/.env"
        log_success ".env Datei erstellt"
    fi
    
    log_success "Dateien installiert"
}

# ==============================================================================
# Docker Build und Start
# ==============================================================================

build_and_start() {
    log_info "Baue Docker Images..."
    cd "$INSTALL_DIR"
    
    docker compose build --no-cache
    log_success "Docker Images gebaut"
    
    log_info "Starte Container..."
    docker compose up -d
    
    # Warten bis Services bereit sind
    log_info "Warte auf Services..."
    sleep 10
    
    # Health Check
    if docker compose ps | grep -q "Up"; then
        log_success "Alle Container laufen"
    else
        log_error "Einige Container sind nicht gestartet"
        docker compose ps
        exit 1
    fi
}

# ==============================================================================
# Abschluss
# ==============================================================================

print_summary() {
    # IP-Adresse ermitteln
    LOCAL_IP=$(hostname -I | awk '{print $1}')
    
    echo ""
    echo "=============================================="
    echo -e "${GREEN}LogBot v${LOGBOT_VERSION} Installation erfolgreich!${NC}"
    echo "=============================================="
    echo ""
    echo "Web-Interface:"
    echo "  http://${LOCAL_IP}"
    echo "  http://localhost"
    echo ""
    echo "Standard-Login:"
    echo "  Benutzer: admin"
    echo "  Passwort: admin"
    echo ""
    echo -e "${YELLOW}WICHTIG: Passwort nach dem ersten Login ändern!${NC}"
    echo ""
    echo "Syslog-Empfang:"
    echo "  Port 514 (UDP/TCP)"
    echo ""
    echo "API Dokumentation:"
    echo "  http://${LOCAL_IP}/api/docs"
    echo ""
    echo "PostgreSQL Datenbank:"
    echo "  Host: ${LOCAL_IP}"
    echo "  Port: 5432"
    echo "  (Zugangsdaten in $INSTALL_DIR/.env)"
    echo ""
    echo "Nützliche Befehle:"
    echo "  cd $INSTALL_DIR"
    echo "  docker compose logs -f        # Logs anzeigen"
    echo "  docker compose restart        # Neustart"
    echo "  docker compose down           # Stoppen"
    echo "  docker compose up -d          # Starten"
    echo ""
}

# ==============================================================================
# Hauptprogramm
# ==============================================================================

main() {
    echo ""
    echo "=============================================="
    echo "  LogBot v${LOGBOT_VERSION} Installer"
    echo "=============================================="
    echo ""
    
    check_requirements
    install_logbot
    build_and_start
    print_summary
}

# Script starten
main "$@"
