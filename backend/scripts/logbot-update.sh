#!/bin/bash
# ==============================================================================
#  LogBot - Wartungsskript (Update / Rueckfall)
# ==============================================================================
#
# Autor:        Phydran6
# Version:      2026.08.14.12.00.00
#
# Beschreibung:
#   Aktualisiert eine LogBot-Installation aus dem Git-Repository und faehrt sie
#   im Fehlerfall wieder auf den vorherigen Stand zurueck.
#
#   Das Skript laeuft auf dem HOST, nicht im Container: waehrend des Updates
#   werden alle Container neu gebaut und ersetzt - inklusive des Backends, das
#   den Lauf angestossen hat. Gestartet wird es vom Backend ueber systemd-run
#   (siehe app/hostexec.py), das es dabei aus dem Image nach
#   <install>/scripts/logbot-update.sh schreibt - so passen Skript und Backend
#   immer zusammen.
#
#   Von Hand geht auch, direkt aus der Installation:
#
#     sudo bash /opt/logbot/backend/scripts/logbot-update.sh apply
#     sudo bash /opt/logbot/backend/scripts/logbot-update.sh rollback
#     sudo bash /opt/logbot/backend/scripts/logbot-update.sh status
#
#   Fortschritt und Ergebnis landen in <dir>/data/update-state.json, das
#   ausfuehrliche Protokoll in <dir>/data/update.log. Die Oberflaeche liest
#   beides aus.
#
# WICHTIG - Datenbestand:
#   Ein Update taucht den Code aus. Die Log-Datenbank liegt in einem Docker-
#   Volume und bleibt dabei normalerweise erhalten. Trotzdem wird vor jedem
#   Update gesichert (Dateien + optional ein Datenbank-Abzug), denn ein
#   Schema-Wechsel oder ein Rueckfall kann Daten kosten.
#
# ==============================================================================

# Bewusst kein "set -e": jeder Schritt wird einzeln geprueft, damit im
# Fehlerfall der Rueckfall noch laufen kann.
set -uo pipefail

# ==============================================================================
# Vorgaben und Parameter
# ==============================================================================

ACTION="${1:-status}"
[[ $# -gt 0 ]] && shift

DIR="/opt/logbot"
REPO="https://github.com/Phydran6/Logbot-Server.git"
BRANCH="main"
DB_BACKUP="true"
BACKUP_CHOICE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dir)           DIR="${2:-$DIR}"; shift ;;
        --repo)          REPO="${2:-$REPO}"; shift ;;
        --branch)        BRANCH="${2:-$BRANCH}"; shift ;;
        --backup)        BACKUP_CHOICE="${2:-}"; shift ;;
        --db-backup)     DB_BACKUP="true" ;;
        --no-db-backup)  DB_BACKUP="false" ;;
        *)               echo "Unbekannter Parameter: $1" ;;
    esac
    shift || true
done

DIR="${DIR%/}"
DATA_DIR="$DIR/data"
STATE_FILE="$DATA_DIR/update-state.json"
LOG_FILE="$DATA_DIR/update.log"
BACKUP_ROOT="${DIR}-backups"

# Wie lange darf ein Schritt dauern?
HEALTH_TIMEOUT="${LOGBOT_HEALTH_TIMEOUT:-420}"    # Sekunden bis die Oberflaeche antworten muss
DB_DUMP_TIMEOUT="${LOGBOT_DUMP_TIMEOUT:-3600}"    # Sekunden fuer den Datenbank-Abzug
KEEP_BACKUPS="${LOGBOT_KEEP_BACKUPS:-5}"          # Anzahl aufbewahrter Sicherungen

STARTED_AT="$(date -Is)"
PROGRESS=0
BACKUP_NAME=""
DB_DUMP_DONE="false"
ROLLED_BACK="false"
VERSION_BEFORE=""
VERSION_AFTER=""
COMMIT_BEFORE=""
COMMIT_AFTER=""

# ==============================================================================
# Hilfsfunktionen
# ==============================================================================

log() {
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

# Anfuehrungszeichen, Backslashes und Zeilenumbrueche fuer JSON entschaerfen.
esc() {
    printf '%s' "${1:-}" | tr '\n\r\t' '   ' | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'
}

write_state() {
    local status="$1" step="$2" message="$3"
    mkdir -p "$DATA_DIR" 2>/dev/null
    local tmp="$STATE_FILE.tmp"
    cat > "$tmp" <<EOF
{
  "status": "$(esc "$status")",
  "action": "$(esc "$ACTION")",
  "step": "$(esc "$step")",
  "message": "$(esc "$message")",
  "progress": $PROGRESS,
  "started_at": "$(esc "$STARTED_AT")",
  "updated_at": "$(date -Is)",
  "backup": "$(esc "$BACKUP_NAME")",
  "database_dump": $DB_DUMP_DONE,
  "rolled_back": $ROLLED_BACK,
  "version_before": "$(esc "$VERSION_BEFORE")",
  "version_after": "$(esc "$VERSION_AFTER")",
  "commit_before": "$(esc "$COMMIT_BEFORE")",
  "commit_after": "$(esc "$COMMIT_AFTER")",
  "install_dir": "$(esc "$DIR")",
  "log_file": "$(esc "$LOG_FILE")"
}
EOF
    mv -f "$tmp" "$STATE_FILE" 2>/dev/null || cp -f "$tmp" "$STATE_FILE" 2>/dev/null
    chmod 0644 "$STATE_FILE" 2>/dev/null
}

step() {
    PROGRESS="$1"
    log "== $2"
    write_state "running" "$2" "$3"
}

finish_ok() {
    PROGRESS=100
    log "FERTIG: $1"
    write_state "success" "Abgeschlossen" "$1"
    exit 0
}

finish_fail() {
    log "FEHLER: $1"
    write_state "failed" "Abgebrochen" "$1"
    exit 1
}

compose() {
    ( cd "$DIR" && docker compose "$@" )
}

read_version() {
    if [[ -f "$DIR/VERSION" ]]; then
        head -n1 "$DIR/VERSION" | tr -d '\r\n'
    fi
}

read_commit() {
    git -C "$DIR" rev-parse HEAD 2>/dev/null | tr -d '\r\n'
}

# HTTP-Abfrage mit dem, was auf dem System vorhanden ist.
http_ok() {
    local url="$1"
    if command -v curl >/dev/null 2>&1; then
        curl -fsS -L -k -m 10 -o /dev/null "$url" 2>/dev/null
        return $?
    fi
    if command -v wget >/dev/null 2>&1; then
        wget -q --no-check-certificate --timeout=10 -O /dev/null "$url" 2>/dev/null
        return $?
    fi
    return 2   # kein Werkzeug vorhanden
}

wait_healthy() {
    local deadline=$(( $(date +%s) + HEALTH_TIMEOUT ))
    local probe
    while [[ "$(date +%s)" -lt "$deadline" ]]; do
        http_ok "http://127.0.0.1/api/health"
        probe=$?
        if [[ $probe -eq 0 ]]; then
            log "Oberflaeche antwortet wieder."
            return 0
        fi
        if [[ $probe -eq 2 ]]; then
            # Weder curl noch wget: ersatzweise die Container-Zustaende ansehen.
            if ! compose ps 2>/dev/null | grep -qiE 'exit|restarting'; then
                log "Kein curl/wget vorhanden - pruefe nur die Container-Zustaende."
                return 0
            fi
        fi
        sleep 5
    done
    return 1
}

# ==============================================================================
# Voraussetzungen
# ==============================================================================

preflight() {
    mkdir -p "$DATA_DIR" 2>/dev/null

    if [[ $EUID -ne 0 ]]; then
        finish_fail "Das Wartungsskript braucht Root-Rechte."
    fi
    if [[ ! -d "$DIR" ]]; then
        finish_fail "Installationsverzeichnis $DIR existiert nicht."
    fi
    if [[ ! -f "$DIR/docker-compose.yml" ]]; then
        finish_fail "In $DIR liegt keine docker-compose.yml - falsches Verzeichnis?"
    fi
    if ! command -v docker >/dev/null 2>&1; then
        finish_fail "Docker ist auf diesem Host nicht installiert."
    fi
    if ! docker compose version >/dev/null 2>&1; then
        finish_fail "Docker Compose (Plugin) fehlt - Update nicht moeglich."
    fi
    if ! command -v git >/dev/null 2>&1; then
        finish_fail "git ist nicht installiert - der neue Stand kann nicht geholt werden."
    fi

    # Git meckert sonst ueber "dubious ownership", wenn root ein fremdes Repo anfasst.
    git config --global --add safe.directory "$DIR" >/dev/null 2>&1 || true
}

# ==============================================================================
# Sicherung
# ==============================================================================

create_backup() {
    BACKUP_NAME="$(date +%Y%m%d-%H%M%S)"
    local target="$BACKUP_ROOT/$BACKUP_NAME"

    mkdir -p "$target/files" || finish_fail "Sicherungsverzeichnis $target konnte nicht angelegt werden."

    # Dateien sichern. data/ bleibt aussen vor - das sind Protokolle dieses Skripts.
    if ! cp -a "$DIR/." "$target/files/" 2>>"$LOG_FILE"; then
        finish_fail "Die Dateien konnten nicht gesichert werden (Platz auf der Platte?)."
    fi
    rm -rf "$target/files/data" 2>/dev/null

    if [[ "$DB_BACKUP" == "true" ]]; then
        backup_database "$target"
    else
        log "Datenbank-Abzug abgewaehlt."
    fi

    cat > "$target/backup.json" <<EOF
{
  "created_at": "$(date -Is)",
  "version": "$(esc "$VERSION_BEFORE")",
  "commit": "$(esc "$COMMIT_BEFORE")",
  "branch": "$(esc "$BRANCH")",
  "database_dump": $DB_DUMP_DONE
}
EOF
    log "Sicherung liegt unter $target"
}

backup_database() {
    local target="$1"

    # Bei externer Datenbank gibt es keinen postgres-Container - dann kein Abzug.
    if ! compose ps --services 2>/dev/null | grep -qx "postgres"; then
        log "Kein postgres-Container in diesem Stack (externe Datenbank?) - kein Abzug."
        return 0
    fi

    log "Erstelle Datenbank-Abzug (kann bei vielen Logs dauern)..."
    # --clean --if-exists: der Abzug raeumt beim Einspielen selbst auf und laesst
    # sich damit ueber eine bestehende Datenbank legen.
    if timeout "$DB_DUMP_TIMEOUT" bash -c \
        "cd '$DIR' && docker compose exec -T postgres sh -c 'pg_dump --clean --if-exists -U \"\$POSTGRES_USER\" \"\$POSTGRES_DB\"'" \
        2>>"$LOG_FILE" | gzip > "$target/database.sql.gz"; then
        if [[ -s "$target/database.sql.gz" ]]; then
            DB_DUMP_DONE="true"
            log "Datenbank-Abzug fertig ($(du -sh "$target/database.sql.gz" 2>/dev/null | cut -f1))."
            return 0
        fi
    fi

    rm -f "$target/database.sql.gz" 2>/dev/null
    log "WARNUNG: Datenbank-Abzug fehlgeschlagen - das Update laeuft trotzdem weiter."
    return 0
}

prune_backups() {
    [[ -d "$BACKUP_ROOT" ]] || return 0
    local count
    count="$(ls -1 "$BACKUP_ROOT" 2>/dev/null | wc -l)"
    [[ "$count" -le "$KEEP_BACKUPS" ]] && return 0
    ls -1 "$BACKUP_ROOT" 2>/dev/null | sort | head -n "$(( count - KEEP_BACKUPS ))" | while read -r old; do
        [[ -n "$old" ]] || continue
        log "Entferne alte Sicherung $old"
        rm -rf "${BACKUP_ROOT:?}/$old"
    done
    return 0
}

# ==============================================================================
# Neuen Stand holen
# ==============================================================================

fetch_sources() {
    if [[ -d "$DIR/.git" ]]; then
        log "Hole neuen Stand per git (Branch $BRANCH)..."
        if ! git -C "$DIR" fetch --tags --prune origin "$BRANCH" >>"$LOG_FILE" 2>&1; then
            log "git fetch fehlgeschlagen - versuche es mit einem frischen Clone."
        else
            if git -C "$DIR" reset --hard FETCH_HEAD >>"$LOG_FILE" 2>&1; then
                return 0
            fi
            log "git reset fehlgeschlagen - versuche es mit einem frischen Clone."
        fi
    else
        log "Installation ist kein Git-Repository - hole die Dateien per Clone."
    fi

    local tmp
    tmp="$(mktemp -d /tmp/logbot-src.XXXXXX)" || return 1
    if ! git clone --depth 1 --branch "$BRANCH" "$REPO" "$tmp/repo" >>"$LOG_FILE" 2>&1; then
        rm -rf "$tmp"
        return 1
    fi
    if [[ ! -f "$tmp/repo/docker-compose.yml" ]]; then
        rm -rf "$tmp"
        log "Im geholten Stand fehlt docker-compose.yml."
        return 1
    fi
    # Ueberkopieren statt loeschen: .env und data/ liegen nicht im Repo und
    # bleiben damit unangetastet.
    cp -a "$tmp/repo/." "$DIR/" >>"$LOG_FILE" 2>&1
    local rc=$?
    rm -rf "$tmp"
    return $rc
}

rebuild_stack() {
    log "Baue Container neu..."
    if ! compose build --pull >>"$LOG_FILE" 2>&1; then
        log "Bauen mit --pull fehlgeschlagen - versuche es ohne."
        if ! compose build >>"$LOG_FILE" 2>&1; then
            return 1
        fi
    fi
    log "Starte Container..."
    if ! compose up -d --remove-orphans >>"$LOG_FILE" 2>&1; then
        return 1
    fi
    return 0
}

# ==============================================================================
# Rueckfall
# ==============================================================================

restore_backup() {
    local name="$1"
    local source="$BACKUP_ROOT/$name"

    [[ -d "$source/files" ]] || { log "Sicherung $name ist unvollstaendig."; return 1; }

    log "Stelle Dateien aus Sicherung $name wieder her..."
    compose down --remove-orphans >>"$LOG_FILE" 2>&1

    if ! cp -a "$source/files/." "$DIR/" >>"$LOG_FILE" 2>&1; then
        log "Dateien konnten nicht zurueckgespielt werden."
        return 1
    fi

    log "Starte Container mit dem alten Stand..."
    if ! compose build >>"$LOG_FILE" 2>&1; then
        log "Bauen des alten Standes fehlgeschlagen."
        return 1
    fi
    if ! compose up -d --remove-orphans >>"$LOG_FILE" 2>&1; then
        log "Start des alten Standes fehlgeschlagen."
        return 1
    fi

    if [[ -f "$source/database.sql.gz" ]]; then
        restore_database "$source/database.sql.gz"
    fi
    return 0
}

restore_database() {
    local dump="$1"

    log "Warte auf die Datenbank..."
    local deadline=$(( $(date +%s) + 120 ))
    while [[ "$(date +%s)" -lt "$deadline" ]]; do
        if compose exec -T postgres sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null 2>&1; then
            break
        fi
        sleep 3
    done

    log "Spiele Datenbank-Abzug ein..."
    if gunzip -c "$dump" | ( cd "$DIR" && docker compose exec -T postgres sh -c 'psql -q -U "$POSTGRES_USER" -d "$POSTGRES_DB"' ) >>"$LOG_FILE" 2>&1; then
        log "Datenbank zurueckgespielt."
        return 0
    fi
    log "WARNUNG: Der Datenbank-Abzug konnte nicht vollstaendig eingespielt werden."
    return 1
}

newest_backup() {
    ls -1 "$BACKUP_ROOT" 2>/dev/null | sort -r | head -n1
}

# ==============================================================================
# Aktionen
# ==============================================================================

do_apply() {
    preflight
    VERSION_BEFORE="$(read_version)"
    COMMIT_BEFORE="$(read_commit)"

    step 5 "Vorbereitung" "Installation wird geprueft."

    step 15 "Sicherung" "Dateien und - falls gewaehlt - die Datenbank werden gesichert."
    create_backup

    step 40 "Neuer Stand" "Der aktuelle Stand wird von GitHub geholt."
    if ! fetch_sources; then
        step 60 "Rueckfall" "Der neue Stand konnte nicht geholt werden - Rueckfall laeuft."
        ROLLED_BACK="true"
        restore_backup "$BACKUP_NAME"
        finish_fail "Der neue Stand konnte nicht von GitHub geholt werden (Netz, Repository oder Branch pruefen). Der alte Stand wurde wiederhergestellt."
    fi

    VERSION_AFTER="$(read_version)"
    COMMIT_AFTER="$(read_commit)"

    step 60 "Container" "Container werden neu gebaut und gestartet."
    if ! rebuild_stack; then
        step 75 "Rueckfall" "Der Neubau ist fehlgeschlagen - Rueckfall laeuft."
        ROLLED_BACK="true"
        if restore_backup "$BACKUP_NAME"; then
            finish_fail "Die neuen Container liessen sich nicht bauen bzw. starten. Der vorherige Stand laeuft wieder. Einzelheiten stehen im Protokoll."
        fi
        finish_fail "Die neuen Container liessen sich nicht bauen und der Rueckfall ist ebenfalls fehlgeschlagen. Bitte das Protokoll ansehen: $LOG_FILE"
    fi

    step 85 "Kontrolle" "Es wird geprueft, ob die Oberflaeche wieder antwortet."
    if ! wait_healthy; then
        step 90 "Rueckfall" "Die Oberflaeche antwortet nicht - Rueckfall laeuft."
        ROLLED_BACK="true"
        if restore_backup "$BACKUP_NAME"; then
            finish_fail "Nach dem Update hat die Oberflaeche nicht geantwortet. Der vorherige Stand laeuft wieder."
        fi
        finish_fail "Nach dem Update hat die Oberflaeche nicht geantwortet und der Rueckfall ist fehlgeschlagen. Bitte das Protokoll ansehen: $LOG_FILE"
    fi

    prune_backups
    finish_ok "Update erfolgreich. Installiert ist jetzt ${VERSION_AFTER:-$COMMIT_AFTER}."
}

do_rollback() {
    preflight
    VERSION_BEFORE="$(read_version)"
    COMMIT_BEFORE="$(read_commit)"

    local name="$BACKUP_CHOICE"
    [[ -n "$name" ]] || name="$(newest_backup)"
    [[ -n "$name" ]] || finish_fail "Es gibt keine Sicherung, auf die zurueckgefallen werden koennte."
    [[ -d "$BACKUP_ROOT/$name" ]] || finish_fail "Die Sicherung '$name' gibt es nicht."

    BACKUP_NAME="$name"
    step 10 "Rueckfall" "Sicherung $name wird wiederhergestellt."

    if ! restore_backup "$name"; then
        finish_fail "Der Rueckfall auf '$name' ist fehlgeschlagen. Bitte das Protokoll ansehen: $LOG_FILE"
    fi

    ROLLED_BACK="true"
    VERSION_AFTER="$(read_version)"
    COMMIT_AFTER="$(read_commit)"

    step 85 "Kontrolle" "Es wird geprueft, ob die Oberflaeche wieder antwortet."
    if ! wait_healthy; then
        finish_fail "Der alte Stand wurde eingespielt, aber die Oberflaeche antwortet nicht. Bitte das Protokoll ansehen: $LOG_FILE"
    fi

    finish_ok "Rueckfall auf ${VERSION_AFTER:-$name} abgeschlossen."
}

do_status() {
    if [[ -f "$STATE_FILE" ]]; then
        cat "$STATE_FILE"
    else
        echo '{"status":"idle","message":"Bisher kein Wartungslauf."}'
    fi
}

# ==============================================================================
# Start
# ==============================================================================

mkdir -p "$DATA_DIR" 2>/dev/null
case "$ACTION" in
    apply)     log "---- Update gestartet (Branch $BRANCH, Verzeichnis $DIR) ----"; do_apply ;;
    rollback)  log "---- Rueckfall gestartet (Verzeichnis $DIR) ----"; do_rollback ;;
    status)    do_status ;;
    *)         echo "Aufruf: $0 {apply|rollback|status} [--dir <pfad>] [--repo <url>] [--branch <name>] [--backup <name>] [--no-db-backup]"; exit 2 ;;
esac
