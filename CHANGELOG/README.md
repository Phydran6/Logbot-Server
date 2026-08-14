# Changelog

Änderungen werden **pro Bereich** dokumentiert. Versionsformat: `YYYY.MM.DD.HH.MM.SS`.

**Aktuelle Projekt-/Release-Version:** `2026.08.14.12.00.00` (Datei `VERSION` im Wurzelverzeichnis, Root-README, `backend/app/config.py` → `app_version`, `frontend/package.json`, `install.sh` → `LOGBOT_VERSION`). Die Tabelle unten führt die Stände der einzelnen Bereiche.
Die Agents-README trägt weiterhin `2026.07.18.18.30.00` — der Agent-Bereich wurde seitdem nicht geändert.

> Die Datei `VERSION` ist der Massstab für die Update-Prüfung (*System → Updates*): sie wird
> gegen den Stand auf GitHub verglichen. Bei jedem Release mit anheben.

| Bereich | Changelog | Aktuelle Version |
|---------|-----------|------------------|
| Agents (Linux/Windows Installer & Forwarder) | [agents.md](agents.md) | 2026.07.18.18.30.00 |
| Backend (FastAPI API) | [backend.md](backend.md) | 2026.08.14.12.00.00 |
| Frontend (Vue UI) | [frontend.md](frontend.md) | 2026.08.14.12.00.00 |
| Syslog-Server | [syslog.md](syslog.md) | 2026.05.13.20.58.33 |
| Datenbank / Deployment (Postgres-Image, Compose, install.sh) | [database.md](database.md) | 2026.08.14.12.00.00 |

## Konventionen
- Neueste Version steht oben.
- Kategorien: **Added**, **Changed**, **Fixed**, **Removed**, **Security**.
- Ein Änderungsblock pro Version; die Version entspricht dem `Version:`-Zeitstempel im Datei-Header des jeweiligen Bereichs.
- Nur den Bereich versionieren/eintragen, der tatsächlich geändert wurde.
