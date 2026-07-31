# Changelog — Datenbank / Deployment

Datenbank-Image & Deploy-Konfiguration (`docker-compose.yml`, `db/`, `install.sh`).
Versionsformat: `YYYY.MM.DD.HH.MM.SS`.

## 2026.07.31.21.40.00
### Added
- **`install.sh` als One-Liner nutzbar**: `curl -sSL .../install.sh | sudo bash`. Fehlt das
  Repo lokal, klont der Installer es selbst (`--repo`/`--branch`, Default `main`).
- **Aktionen** `install` (Standard), `update`, `uninstall`, `uninstall-purge` sowie Optionen
  `--dir`, `--repo`, `--branch`, `--no-build`, `--yes`, `--timeout` (auch als `LOGBOT_*`).
- **Start-Gate wie beim Agent-Installer**: 5 s Countdown, Tastendruck schaltet auf Rückfragen,
  sonst läuft alles automatisch durch (`read </dev/tty`, funktioniert auch hinter der Pipe).
- `docker compose up -d` läuft jetzt mit **`--remove-orphans`**, damit beim Update Container
  verschwinden, die nicht mehr in der Compose-Datei stehen (z. B. der alte portainer-agent).

### Fixed
- **Bestehende `.env` wird nicht mehr überschrieben.** Bisher erzeugte eine erneute
  Installation neue Zufallspasswörter, während das Postgres-Volume die alten behielt —
  das Backend kam danach nicht mehr an die Datenbank. Beim Ersetzen einer Installation
  wird die `.env` zusätzlich aus dem Backup übernommen.
- Installation aus dem Zielverzeichnis heraus (`/opt/logbot/install.sh`) bricht nicht mehr
  mit „same file" ab; das Kopieren entfällt dann bzw. folgt dem verschobenen Backup.
- `generate_password` fällt ohne `openssl` auf `/dev/urandom` zurück.

## 2026.07.31.20.06.53
### Removed
- **`portainer-agent` aus `docker-compose.yml` entfernt** (Container `logbot-portainer-agent`,
  Port `9001`). LogBot bringt damit kein Fremd-/Management-System mehr mit; Verwaltungs-
  werkzeuge betreibt man getrennt vom LogBot-Stack.

### Security
- Der Portainer-Agent mountete `/var/run/docker.sock` und `/var/lib/docker/volumes`.
  Ein Zugriff auf den Docker-Socket entspricht faktisch Root-Rechten auf dem Host —
  diese Angriffsfläche entfällt jetzt.

### Hinweis (Update auf Bestandssystemen)
- Der alte Container läuft nach `git pull` noch weiter. Einmalig aufräumen mit:
  `docker compose up -d --remove-orphans` (bzw. `docker rm -f logbot-portainer-agent`).
- Falls Portainer weiter genutzt wird: den Agent separat starten, z. B.
  `docker run -d -p 9001:9001 --name portainer-agent --restart=always -v /var/run/docker.sock:/var/run/docker.sock -v /var/lib/docker/volumes:/var/lib/docker/volumes portainer/agent:latest`

## 2026.07.19.16.00.00
### Added
- `db/migrate.sh` **curl-fest**: findet das Projektverzeichnis selbst
  (aktuelles Verzeichnis → skriptrelativ → `/opt/logbot`), Rückfrage über `/dev/tty`.
  One-Liner: `curl -sSL .../db/migrate.sh | sudo bash` (bzw. `| sudo bash -s -- 18 -y`).
- Robustere Parameter (`[Ziel-Major] [-y]`, Reihenfolge egal).

## 2026.07.19.15.00.00
### Changed
- **PostgreSQL-Image von `16-alpine` auf `17-alpine` (neu + stabil) angehoben.**
- Version über `POSTGRES_VERSION` in `.env` steuerbar: `image: postgres:${POSTGRES_VERSION:-17}-alpine`.
  Neuinstallationen bekommen direkt 17. Bestehende 16er-DBs können als **Notbremse**
  `POSTGRES_VERSION=16` setzen und laufen sofort weiter.

### Added
- `db/migrate.sh` — datenerhaltendes Major-Upgrade (Dump → Volume neu → Restore),
  Zielversion als Parameter (`sudo bash db/migrate.sh [17|18] [-y]`).
- README-Abschnitt „Update / PostgreSQL-Major-Upgrade" mit **drei Wegen**
  (Daten behalten / frische DB / Neuinstallation) + Notbremse.
- `POSTGRES_VERSION` in `.env.example` und im vom `install.sh` generierten `.env`.
- `.gitignore`: Migrations-Dumps (`logbot-db-backup-*.dump`, `*.dump`, `backup.sql`).

### Hinweis
- PostgreSQL-Datenverzeichnisse sind zwischen Major-Versionen **nicht** kompatibel –
  ein reiner Image-Tausch von 16 auf 17 startet nicht. Deshalb Migration bzw. Notbremse nutzen.

_Änderungen vor Einführung des Changelogs wurden nicht einzeln erfasst._
