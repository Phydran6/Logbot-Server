# Changelog — Datenbank / Deployment

Datenbank-Image & Deploy-Konfiguration (`docker-compose.yml`, `db/`, `install.sh`).
Versionsformat: `YYYY.MM.DD.HH.MM.SS`.

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
