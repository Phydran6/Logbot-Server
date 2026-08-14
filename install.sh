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
# Autor:        Phydran6
# Kontakt:      Phydran6
# Version:      2026.07.31.21.40.00
# Erstellt:     Januar 2026
#
# Beschreibung:
#   Installiert / aktualisiert / entfernt LogBot via Docker Compose.
#   Funktioniert lokal aus dem Repo UND als One-Liner direkt von GitHub
#   (dann holt sich das Script die Quellen selbst per git clone).
#
# Voraussetzungen:
#   - Linux System (Debian/Ubuntu empfohlen)
#   - Root-Rechte
#   - Internetzugang (fuer Docker-/Repo-Installation)
#
# Verwendung:
#   sudo bash install.sh                # lokal aus dem Repo
#   curl -sSL <RAW-URL>/install.sh | sudo bash            # One-Liner
#   curl -sSL <RAW-URL>/install.sh | sudo bash -s -- -y   # ohne Rueckfragen
#   sudo bash install.sh update|uninstall|uninstall-purge
#
# ==============================================================================

set -e

# Farben für Output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ==============================================================================
# Konfiguration (Vorrang: Parameter > Umgebungsvariable > Default)
# ==============================================================================

LOGBOT_VERSION="2026.08.14.14.00.00"

INSTALL_DIR="${LOGBOT_DIR:-/opt/logbot}"
REPO_URL="${LOGBOT_REPO:-https://github.com/Phydran6/Logbot-Server.git}"
REPO_BRANCH="${LOGBOT_BRANCH:-main}"
PROMPT_TIMEOUT="${LOGBOT_TIMEOUT:-5}"

ACTION="install"
ASSUME_YES="${LOGBOT_YES:-false}"   # true => nie fragen
MANUAL="false"                      # true => Rueckfragen werden gestellt (kein Timeout)
GATE_DONE="false"
NO_BUILD="false"                    # true => Images nicht neu bauen

SRC_DIR=""        # Quelle der Dateien (lokales Repo oder frischer Clone)
TMP_CLONE=""      # temporaerer Clone, wird am Ende aufgeraeumt

# ==============================================================================
# Hilfsfunktionen
# ==============================================================================

log_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }
fail()        { log_error "$1"; exit 1; }

cleanup() {
    [[ -n "$TMP_CLONE" && -d "$TMP_CLONE" ]] && rm -rf "$TMP_CLONE"
    return 0
}
trap cleanup EXIT

# true nur, wenn /dev/tty wirklich geoeffnet werden kann (nicht nur -r).
# Sonst wuerde 'read </dev/tty' bei einer Pipe ohne Terminal eine Fehlermeldung werfen.
have_tty() { true 2>/dev/null </dev/tty; }

# Einmaliges "Gate" am Anfang: kurzer Countdown. Wird EINE Taste gedrueckt, schaltet
# der Installer auf MANUELL (alle folgenden Rueckfragen blockieren, kein Timeout).
# Keine Eingabe / kein Terminal / --yes => automatischer Ablauf mit Standardwerten.
interactive_gate() {
    [[ "$GATE_DONE" == "true" ]] && return 0
    GATE_DONE="true"
    [[ "$ASSUME_YES" == "true" ]] && return 0
    have_tty || return 0
    echo ""
    log_info "Automatischer Start in ${PROMPT_TIMEOUT}s. Für Rückfragen jetzt eine Taste drücken..."
    local _k=""
    if read -rsN1 -t "$PROMPT_TIMEOUT" _k </dev/tty; then
        MANUAL="true"
        # Restliche gepufferte Zeichen verwerfen, sonst nimmt die erste Abfrage sofort den Default.
        while read -rsN1 -t 0.05 _k </dev/tty 2>/dev/null; do :; done
        echo ""
        log_success "Manueller Modus aktiv - Rückfragen werden gestellt."
    else
        echo ""
        log_info "Keine Eingabe - automatischer Ablauf mit Standardwerten."
    fi
    return 0
}

# Ja/Nein-Rueckfrage. Im automatischen Modus gilt der uebergebene Default.
# confirm "Frage" "j|n"
confirm() {
    local prompt="$1" def="${2:-n}" ans=""
    if [[ "$MANUAL" == "true" ]]; then
        read -r -p "$prompt [$( [[ "$def" == "j" ]] && echo "J/n" || echo "j/N" )] " ans </dev/tty || true
        echo ""
    fi
    [[ -z "$ans" ]] && ans="$def"
    [[ "$ans" == "j" || "$ans" == "J" || "$ans" == "y" || "$ans" == "Y" ]]
}

generate_password() {
    if command -v openssl &> /dev/null; then
        openssl rand -base64 48 | tr -dc 'a-zA-Z0-9' | head -c 32
    else
        tr -dc 'a-zA-Z0-9' < /dev/urandom | head -c 32
    fi
}

show_help() {
    cat <<EOF
LogBot Installer v${LOGBOT_VERSION}

Aufruf:   sudo bash install.sh [aktion] [optionen]
          curl -sSL ${REPO_URL%.git}/raw/${REPO_BRANCH}/install.sh | sudo bash

Aktionen: install (Standard) | update | uninstall | uninstall-purge

Optionen (auch als Umgebungsvariable LOGBOT_*):
  --dir <pfad>       Installationsverzeichnis   (LOGBOT_DIR)    [${INSTALL_DIR}]
  --repo <url>       Git-Repository             (LOGBOT_REPO)   [${REPO_URL}]
  --branch <name>    Branch                     (LOGBOT_BRANCH) [${REPO_BRANCH}]
  --no-build         Images nicht neu bauen (nur starten)
  --yes, -y          Keine Rückfragen (unattended)
  --timeout <sek>    Wartezeit des Start-Gates  (LOGBOT_TIMEOUT) [${PROMPT_TIMEOUT}]
  --help, -h         Diese Hilfe

Hinweise:
  * uninstall        stoppt und entfernt die Container, Daten (Volumes) bleiben.
  * uninstall-purge  löscht zusätzlich Volumes UND ${INSTALL_DIR} - Logs sind dann weg.
  * Eine vorhandene .env wird nie überschrieben (Datenbank-Passwort bleibt gültig).
EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            install)                ACTION="install" ;;
            update|upgrade)         ACTION="update" ;;
            uninstall|remove)       ACTION="uninstall" ;;
            uninstall-purge|purge)  ACTION="uninstall-purge" ;;
            --dir)                  INSTALL_DIR="${2:-}"; shift ;;
            --dir=*)                INSTALL_DIR="${1#*=}" ;;
            --repo)                 REPO_URL="${2:-}"; shift ;;
            --repo=*)               REPO_URL="${1#*=}" ;;
            --branch)               REPO_BRANCH="${2:-}"; shift ;;
            --branch=*)             REPO_BRANCH="${1#*=}" ;;
            --timeout)              PROMPT_TIMEOUT="${2:-5}"; shift ;;
            --timeout=*)            PROMPT_TIMEOUT="${1#*=}" ;;
            --no-build)             NO_BUILD="true" ;;
            --yes|-y|--unattended)  ASSUME_YES="true" ;;
            --help|-h)              show_help; exit 0 ;;
            *)                      log_warn "Unbekannter Parameter: $1" ;;
        esac
        shift || true
    done
}

# ==============================================================================
# Voraussetzungen prüfen
# ==============================================================================

check_requirements() {
    log_info "Prüfe Voraussetzungen..."

    if [[ $EUID -ne 0 ]]; then
        log_error "Dieses Script muss als root ausgeführt werden!"
        log_info "Aufruf: sudo bash install.sh   (bzw. '| sudo bash' beim One-Liner)"
        exit 1
    fi

    if ! command -v git &> /dev/null; then
        log_warn "git nicht gefunden - installiere..."
        apt-get update && apt-get install -y git
    fi

    if ! command -v curl &> /dev/null; then
        log_warn "curl nicht gefunden - installiere..."
        apt-get update && apt-get install -y curl
    fi

    if ! command -v docker &> /dev/null; then
        log_warn "Docker nicht gefunden - installiere automatisch..."
        curl -fsSL https://get.docker.com | sh
        systemctl enable docker
        systemctl start docker
        log_success "Docker installiert"
    fi

    if ! docker compose version &> /dev/null; then
        fail "Docker Compose (Plugin) nicht verfügbar!"
    fi

    log_success "Alle Voraussetzungen erfüllt"
}

# ==============================================================================
# Quelle bestimmen: lokales Repo oder frischer Clone von GitHub
# ==============================================================================

resolve_source() {
    # Liegt das Script neben einer docker-compose.yml, ist das Repo schon lokal da.
    local script_path script_dir
    script_path="${BASH_SOURCE[0]:-}"
    if [[ -n "$script_path" && -f "$script_path" ]]; then
        script_dir="$(cd "$(dirname "$script_path")" && pwd)"
        if [[ -f "$script_dir/docker-compose.yml" ]]; then
            SRC_DIR="$script_dir"
            log_info "Quelle: lokales Verzeichnis $SRC_DIR"
            return 0
        fi
    fi

    # One-Liner-Fall (curl | bash): Quellen selbst holen.
    TMP_CLONE="$(mktemp -d /tmp/logbot-src.XXXXXX)"
    log_info "Quelle: $REPO_URL (Branch $REPO_BRANCH) wird geklont..."
    git clone --depth 1 --branch "$REPO_BRANCH" "$REPO_URL" "$TMP_CLONE/repo" \
        || fail "git clone fehlgeschlagen - Repo/Branch/Netzwerk prüfen."
    [[ -f "$TMP_CLONE/repo/docker-compose.yml" ]] \
        || fail "Im geklonten Repo fehlt docker-compose.yml."
    SRC_DIR="$TMP_CLONE/repo"
    log_success "Quellen geladen"
}

# ==============================================================================
# .env sicherstellen (bestehende NIE überschreiben)
# ==============================================================================

ensure_env() {
    local env_file="$INSTALL_DIR/.env"

    if [[ -f "$env_file" ]]; then
        log_info "Bestehende .env bleibt unverändert (Datenbank-Passwort bleibt gültig)"
        return 0
    fi

    log_info "Erstelle .env..."
    local db_password jwt_secret
    db_password="$(generate_password)"
    jwt_secret="$(generate_password)"

    cat > "$env_file" << EOF
# LogBot v${LOGBOT_VERSION} Konfiguration
# Automatisch generiert am $(date)

# Datenbank
DB_USER=logbot
DB_PASSWORD=${db_password}
DB_NAME=logbot

# PostgreSQL-Major-Version (Docker-Tag). Standard: 17 (neu + stabil).
POSTGRES_VERSION=17

# JWT Secret für API Authentifizierung
JWT_SECRET=${jwt_secret}
EOF
    chmod 600 "$env_file"
    log_success ".env erstellt"
}

# ==============================================================================
# Installation / Update
# ==============================================================================

copy_files() {
    mkdir -p "$INSTALL_DIR"

    # Wird das Script direkt aus dem Installationsverzeichnis gestartet, waere
    # das Kopieren ein "same file"-Fehler - dann ist ohnehin nichts zu tun.
    if [[ "$(cd "$SRC_DIR" && pwd)" == "$(cd "$INSTALL_DIR" && pwd)" ]]; then
        log_info "Quelle ist bereits das Installationsverzeichnis - kein Kopieren nötig."
        return 0
    fi

    log_info "Kopiere Dateien nach $INSTALL_DIR..."
    # Punkt am Ende: Inhalt kopieren, nicht das Verzeichnis selbst.
    # .env liegt nicht in der Quelle und bleibt dadurch erhalten.
    cp -a "$SRC_DIR/." "$INSTALL_DIR/"
    log_success "Dateien aktualisiert"
}

install_logbot() {
    if [[ -d "$INSTALL_DIR" && -f "$INSTALL_DIR/docker-compose.yml" ]]; then
        log_warn "In $INSTALL_DIR ist LogBot bereits installiert."
        if confirm "Vorhandene Installation aktualisieren (Daten und .env bleiben)?" "j"; then
            log_info "Wechsle auf Update..."
            update_logbot
            return 0
        fi

        local backup_dir="${INSTALL_DIR}.backup.$(date +%Y%m%d_%H%M%S)"
        log_info "Erstelle Backup: $backup_dir"
        mv "$INSTALL_DIR" "$backup_dir"
        mkdir -p "$INSTALL_DIR"
        # Lag die Quelle im verschobenen Verzeichnis (Script aus /opt/logbot
        # gestartet), zeigt SRC_DIR jetzt ins Backup.
        if [[ "$SRC_DIR" == "$INSTALL_DIR" || "$SRC_DIR" == "$INSTALL_DIR"/* ]]; then
            SRC_DIR="${backup_dir}${SRC_DIR#"$INSTALL_DIR"}"
        fi
        # .env mitnehmen: sonst passt das Passwort nicht mehr zum bestehenden
        # Postgres-Volume und das Backend kommt nicht mehr an die Datenbank.
        if [[ -f "$backup_dir/.env" ]]; then
            cp -a "$backup_dir/.env" "$INSTALL_DIR/.env"
            log_info ".env aus dem Backup übernommen"
        fi
    fi

    copy_files
    ensure_env
    log_success "LogBot v${LOGBOT_VERSION} installiert nach $INSTALL_DIR"
}

update_logbot() {
    [[ -d "$INSTALL_DIR" ]] || fail "$INSTALL_DIR existiert nicht - erst installieren."

    local updated="false"
    if [[ -d "$INSTALL_DIR/.git" ]]; then
        log_info "Aktualisiere per git pull..."
        if git -C "$INSTALL_DIR" pull --ff-only; then
            updated="true"
        else
            log_warn "git pull fehlgeschlagen - kopiere stattdessen die Quellen."
        fi
    fi

    # Kein Git-Repo (oder pull fehlgeschlagen): Dateien aus der Quelle druebersetzen.
    if [[ "$updated" != "true" ]]; then
        [[ -n "$SRC_DIR" ]] || resolve_source
        copy_files
    fi

    ensure_env
    log_success "LogBot aktualisiert"
}

# ==============================================================================
# Docker Build und Start
# ==============================================================================

build_and_start() {
    cd "$INSTALL_DIR"

    if [[ "$NO_BUILD" != "true" ]]; then
        log_info "Baue Docker Images..."
        docker compose build
        log_success "Docker Images gebaut"
    fi

    log_info "Starte Container..."
    # --remove-orphans raeumt Container weg, die nicht mehr in der Compose-Datei
    # stehen (z.B. den frueheren portainer-agent).
    docker compose up -d --remove-orphans

    log_info "Warte auf Services..."
    sleep 10

    if docker compose ps | grep -q "Up"; then
        log_success "Alle Container laufen"
    else
        log_error "Einige Container sind nicht gestartet"
        docker compose ps
        exit 1
    fi
}

# ==============================================================================
# Deinstallation
# ==============================================================================

uninstall_logbot() {
    local purge="$1"

    [[ -d "$INSTALL_DIR" ]] || fail "$INSTALL_DIR existiert nicht - nichts zu entfernen."

    if [[ "$purge" == "true" ]]; then
        log_warn "PURGE: Container, Volumes (= ALLE Logs!) und $INSTALL_DIR werden gelöscht."
        # Ohne --yes ist der Default "nein"; wer unattended purged, meint es ernst.
        if [[ "$ASSUME_YES" != "true" ]] && ! confirm "Wirklich alles löschen?" "n"; then
            log_info "Abgebrochen."
            exit 0
        fi
        (cd "$INSTALL_DIR" && docker compose down -v --remove-orphans) || log_warn "docker compose down meldete einen Fehler"
        rm -rf "$INSTALL_DIR"
        log_success "LogBot vollständig entfernt"
    else
        (cd "$INSTALL_DIR" && docker compose down --remove-orphans) || log_warn "docker compose down meldete einen Fehler"
        log_success "Container gestoppt und entfernt. Daten und $INSTALL_DIR bleiben erhalten."
        log_info "Wieder starten: cd $INSTALL_DIR && docker compose up -d"
    fi
}

# ==============================================================================
# Abschluss
# ==============================================================================

print_summary() {
    local local_ip
    local_ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
    [[ -z "$local_ip" ]] && local_ip="<server-ip>"

    echo ""
    echo "=============================================="
    echo -e "${GREEN}LogBot v${LOGBOT_VERSION} ist bereit!${NC}"
    echo "=============================================="
    echo ""
    echo "Web-Interface:"
    echo "  http://${local_ip}"
    echo "  (HTTPS im UI unter Einstellungen -> Netzwerk -> Reverse Proxy aktivieren)"
    echo ""
    echo "Standard-Login:"
    echo "  Benutzer: admin"
    echo "  Passwort: admin"
    echo ""
    echo -e "${YELLOW}WICHTIG: Passwort nach dem ersten Login ändern!${NC}"
    echo ""
    echo "Syslog-Empfang:  Port 514 (UDP/TCP)"
    echo "API-Doku:        http://${local_ip}/api/docs"
    echo "PostgreSQL:      ${local_ip}:5432 (Zugangsdaten in $INSTALL_DIR/.env)"
    echo ""
    echo "Updates:"
    echo "  In der Oberfläche unter System -> Updates (mit Rückfall-Option)"
    echo "  oder als Einzeiler:"
    echo "  curl -sSL ${REPO_URL%.git}/raw/${REPO_BRANCH}/install.sh | sudo bash -s -- update -y"
    echo ""
    echo "Nützliche Befehle:"
    echo "  cd $INSTALL_DIR"
    echo "  docker compose logs -f        # Logs anzeigen"
    echo "  docker compose restart        # Neustart"
    echo "  docker compose down           # Stoppen"
    echo "  sudo bash install.sh update   # Aktualisieren"
    echo ""
}

# ==============================================================================
# Hauptprogramm
# ==============================================================================

main() {
    parse_args "$@"

    echo ""
    echo "=============================================="
    echo "  LogBot v${LOGBOT_VERSION} Installer"
    echo "  Aktion: ${ACTION}"
    echo "=============================================="

    case "$ACTION" in
        uninstall)
            interactive_gate
            [[ $EUID -eq 0 ]] || fail "Bitte als root ausführen (sudo)."
            uninstall_logbot "false"
            ;;
        uninstall-purge)
            interactive_gate
            [[ $EUID -eq 0 ]] || fail "Bitte als root ausführen (sudo)."
            uninstall_logbot "true"
            ;;
        update)
            interactive_gate
            check_requirements
            # Quellen nur holen, wenn kein Git-Repo im Zielverzeichnis liegt.
            [[ -d "$INSTALL_DIR/.git" ]] || resolve_source
            update_logbot
            build_and_start
            print_summary
            ;;
        install)
            interactive_gate
            check_requirements
            resolve_source
            install_logbot
            build_and_start
            print_summary
            ;;
        *)
            fail "Unbekannte Aktion: $ACTION"
            ;;
    esac
}

# Script starten
main "$@"
