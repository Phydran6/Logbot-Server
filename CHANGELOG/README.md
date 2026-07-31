# Changelog

Änderungen werden **pro Bereich** dokumentiert. Versionsformat: `YYYY.MM.DD.HH.MM.SS`.

**Aktuelle Projekt-/Release-Version:** `2026.07.31.23.00.00` (Root-README, `backend/app/config.py` → `app_version`, `frontend/package.json`). Die Tabelle unten führt die Stände der einzelnen Bereiche.
Die Agents-README trägt weiterhin `2026.07.18.18.30.00` — der Agent-Bereich wurde seitdem nicht geändert.

| Bereich | Changelog | Aktuelle Version |
|---------|-----------|------------------|
| Agents (Linux/Windows Installer & Forwarder) | [agents.md](agents.md) | 2026.07.18.18.30.00 |
| Backend (FastAPI API) | [backend.md](backend.md) | 2026.07.31.23.00.00 |
| Frontend (Vue UI) | [frontend.md](frontend.md) | 2026.07.31.23.00.00 |
| Syslog-Server | [syslog.md](syslog.md) | 2026.05.13.20.58.33 |
| Datenbank / Deployment (Postgres-Image, Compose, install.sh) | [database.md](database.md) | 2026.07.31.21.40.00 |

## Konventionen
- Neueste Version steht oben.
- Kategorien: **Added**, **Changed**, **Fixed**, **Removed**, **Security**.
- Ein Änderungsblock pro Version; die Version entspricht dem `Version:`-Zeitstempel im Datei-Header des jeweiligen Bereichs.
- Nur den Bereich versionieren/eintragen, der tatsächlich geändert wurde.
