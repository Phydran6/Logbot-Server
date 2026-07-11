# LogBot v2026.07.11.14.08.15
Zentraler Log-Server für Linux/Windows-Systeme und Netzwerkgeräte.

Entwickelt von Phydran6

📓 Änderungen / Changelog: [CHANGELOG/](CHANGELOG/README.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub stars](https://img.shields.io/github/stars/Phydran6/Logbot-Server?style=social)](https://github.com/Phydran6/Logbot-Server/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/Phydran6/Logbot-Server?style=social)](https://github.com/Phydran6/Logbot-Server/network/members)
[![GitHub issues](https://img.shields.io/github/issues/Phydran6/Logbot-Server)](https://github.com/Phydran6/Logbot-Server/issues)
[![GitHub last commit](https://img.shields.io/github/last-commit/Phydran6/Logbot-Server)](https://github.com/Phydran6/Logbot-Server/commits/main)
[![GitHub release](https://img.shields.io/github/v/release/Phydran6/Logbot-Server?include_prereleases)](https://github.com/Phydran6/Logbot-Server/releases)


## Features
- Syslog-Empfang auf UDP/TCP Port 514
- Automatische Geräteerkennung (UniFi APs, Linux, Windows)
- Echtzeit Log-Suche mit Filtern
- Webhook-Integration für n8n, Make, Zapier (ohne Login)
- Dashboard mit Statistiken
- Benutzerverwaltung mit Rollen
- Health Monitoring für System-Ressourcen
- Whitelabel-System mit Dark/Light Mode
- Docker-basiert für einfache Installation

## Voraussetzungen
- Linux Server (Ubuntu 20.04+ empfohlen)
- Docker & Docker Compose
- Root-Zugriff

## Installation
```bash
# Repository klonen
git clone https://github.com/Phydran6/Logbot-Server.git
cd Logbot-Server

# Installer ausführen (erstellt .env automatisch)
sudo bash install.sh
```

**Oder manuell aus Archiv:**
```bash
tar -xzf logbot-v2026.05.30.18.02.35.tar.gz
cd logbot-v2026.05.30.18.02.35
sudo bash install.sh
```

**Oder direkt mit Docker Compose (ohne install.sh):**
```bash
git clone https://github.com/Phydran6/Logbot-Server.git
cd Logbot-Server

# .env aus Vorlage erstellen und Passwörter setzen
cp .env.example .env
sed -i "s/CHANGE_ME/$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 32)/g" .env

sudo docker compose up -d --build
```

## Zugriff
- Web-Interface: http://SERVER-IP  
  Hinweis: HTTPS ist nach der Grundinstallation noch aus. Aktiviere es im Web-UI unter „Einstellungen → Reverse Proxy & TLS“ (Let’s Encrypt oder eigenes Zertifikat).
- API Docs: http://SERVER-IP/api/docs
- Branding: http://SERVER-IP/settings/branding
- Login: admin / admin (bitte direkt ändern)

## Syslog-Quellen konfigurieren
### Linux (rsyslog)
```
# /etc/rsyslog.d/logbot.conf
*.* @LOGBOT-IP:514
```

### UniFi Controller
Settings → System → Remote Logging → Enable + LogBot IP

## Webhook-Nutzung
Webhooks erlauben Zugriff ohne Login:
```
GET /api/webhook/{id}/call?token={token}
```

Ideal für n8n-Workflows:
1. LogBot → Webhooks → Neuer Webhook
2. Filter konfigurieren (Hostname, Level, etc.)
3. URL in n8n HTTP Request Node einfügen

## Whitelabel / Branding
LogBot bietet ein Whitelabel-System zur Anpassung an deine Marke.

### Branding-Features
- Dark/Light Mode mit Toggle
- Farbschema anpassbar
- Firmenname & Logo austauschbar
- Favicon anpassbar
- Custom CSS für Erweiterungen

### Konfiguration
1. Navigiere zu **Settings → Branding** (`/settings/branding`)
2. Farben, Logo und Texte anpassen
3. Speichern klicken

### Einstellungen
| Einstellung      | Beschreibung                                  |
|------------------|-----------------------------------------------|
| Firmenname       | Anzeige im Header und Seitentitel             |
| Tagline          | Slogan unter dem Firmennamen                  |
| Logo             | PNG/JPG/SVG/WebP (empfohlen: 200x50 px)       |
| Favicon          | ICO/PNG/SVG (empfohlen: 32x32 px)             |
| Primärfarbe      | Buttons, Links, Akzente                       |
| Dark/Light Mode  | Standard-Theme und Toggle-Erlaubnis           |
| Custom CSS       | Eigene CSS-Regeln                             |

### Theme-Toggle Beispiel
```vue
<template>
  <ThemeToggle />
  <!-- oder mit Label -->
  <ThemeToggle :showLabel="true" />
</template>
```

## Verzeichnisstruktur (Standard-Install unter /opt/logbot)
```
/opt/logbot/
  docker-compose.yml
  .env                  # Zugangsdaten (geheim!)
  backend/              # FastAPI Backend
    app/
  frontend/             # Vue.js Frontend
    src/
  syslog/               # Syslog Server
  caddy/                # Reverse Proxy
  db/                   # Datenbank-Schema
```

## Befehle
```bash
cd /opt/logbot

# Status
docker compose ps

# Logs
docker compose logs -f

# Neustart
docker compose restart

# Stoppen
docker compose down

# Starten
docker compose up -d

# Update auf neue Version
docker compose pull
docker compose up -d --build
```

## Datenbank-Backup
```bash
# Backup erstellen
docker compose exec postgres pg_dump -U logbot logbot > backup.sql

# Backup einspielen
docker compose exec -T postgres psql -U logbot logbot < backup.sql
```

## Changelog
### v2026.05.30.18.02.35 (2026-05-30)
- UI: Benutzer-Bearbeiten-Modal scrollbar mit fixiertem Header & Footer (max. 90 % Viewport-Höhe) – verhindert dass MFA + App-QR den Bildschirm sprengen.

### v2026.05.30.17.22.26 (2026-05-30)
- NEU: MFA / 2FA via TOTP (Backend-Teil) – kompatibel mit allen gängigen Authenticator-Apps (Google Authenticator, Authy, 1Password, Aegis, Bitwarden, …)
  - Endpoints `/api/auth/mfa/setup`, `/verify`, `/disable`, `/status`, `/backup-codes/regenerate`
  - 10 Einmal-Backup-Codes (bcrypt-gehasht)
  - Zwei-Stufen-Login: `/api/auth/login` liefert bei aktivem MFA ein `mfa_token`, `POST /api/auth/login/mfa` tauscht es gegen Access-Token
  - Lockout: 10 Falschversuche → 15 Min Sperre
  - Admin-Notfall-Reset: `POST /api/users/{id}/mfa/reset`
  - Schema-Migrationen laufen automatisch beim Start

### v2026.05.13.20.58.33 (2026-05-13)
- NEU: MIT-Lizenz hinzugefügt
- DOCS: GitHub Badges in README (Stars, Forks, Issues, letzter Commit, Release)

### v2026.04.17.15.17.18 (2026-04-17)
- FIX: QR-Code App-Login Timezone-Bug (Countdown zeigte sofort "Abgelaufen")
- FIX: SITE_URL wird jetzt korrekt an Backend-Container weitergegeben (docker-compose)
- UI: App-Login QR-Code in Benutzer-Edit-Modal integriert (statt eigenem Nav-Tab)
- DOCS: SITE_URL in .env.example dokumentiert

### v2026.03.31.17.26.46 (2026-03-31)
- Version-Bump Settings-View + Backend-App-Version auf 2026.04.02.16.32.39.

### v2026.03.31.10.48.35 (2026-03-31)
- NEU: Agent-Decommission/Purge Endpoint + Installer-Option „Server + Logs entfernen“.
- NEU: Installer-Hauptmenü (Installieren/Deinstallieren/Test) und FQDN-Check.
- FIX: Umlaute/Encoding in README, Syslog-Server, Agents-UI.
- UI: Delete-Prompt + Label „Löschen“ korrigiert.

### v2026.03.30.10.40.54 (2026-03-19)
- Admin-Button „System neu starten“ ergänzt (Backend führt Reboot über SysRq/nsenter/reboot/shutdown aus; Container pid:host/privileged).
- Health-Uptime bleibt in der Health-Ansicht; System-Karte in den Einstellungen ohne Uptime.
- Backend/Frontend-Versionen auf 2026.03.19.13.26.52 angehoben.

### v2026.03.03.17.18.19 (2026-03-03)
- Datenbank-Passwort im Einstellungsbereich (nur Admins) anzeigen/ausblenden/kopieren; neuer API-Endpoint `/api/settings/database`.

### v2026.02.20 (2026-02-20)
- NEU: Web-UI Seite „Agent Token“ zeigt/erneuert den HTTPS-Agent-Token und Kopierlink.
- NEU: Backend erzeugt beim Start automatisch ein Default-Agent-Token (falls keins vorhanden).
- FIX: Robustere Login-Fehlerbehandlung im Frontend (verhindert JSON-Parse-Fehler).

### v2026.02.16 (2026-02-16)
- FIX: Agent löschen schlug fehl (async SQLAlchemy + FK-Konflikt)
- FIX: Health-Seite nicht erreichbar bei hoher DB-Last
- PERFORMANCE: Syslog Server überarbeitet
  - Agent-Cache im Speicher (vermeidet DB-Lookup pro Nachricht)
  - Batch-Inserts via PostgreSQL COPY
  - Gebündelte `last_seen` Updates (alle 2 s)
  - Ergebnis: ~96 DB-Ops/s → ~2 DB-Ops/s
- PERFORMANCE: Dashboard/Logs/Health `COUNT(*)` über Millionen Zeilen eliminiert
  - Gesamtzahl via `pg_class.reltuples` (Schätzung)
  - Unique Hosts aus `agents` statt `COUNT(DISTINCT)` über `logs`
  - Level/Source-Statistiken nur für heute (nutzt timestamp-Index)
- PERFORMANCE: Index `idx_logs_agent_id` ergänzt

### v2026.01.30.17.30.00 (2026-01-30)
- NEU: Whitelabel-System mit Dark/Light Mode
- NEU: Branding-Einstellungen im Web-Interface
- NEU: Logo- und Favicon-Upload
- NEU: Custom CSS Support
- NEU: Theme-Toggle Komponente

### v2026.01.30.13.30.00 (2026-01-30)
- UniFi Netconsole Parsing Fix (Hex-ID ≠ Hostname)
- Öffentliche Webhook-Endpoints ohne Bearer Token
- Verbessertes Health Monitoring
- Settings-Verwaltung im Web-Interface
- Log-Retention Funktion

### v1.1.0
- Webhook-Integration für n8n
- PostgreSQL statt SQLite
- Verbessertes Agent-Management

### v1.0.0
- Initiale Version
- Basis Syslog-Empfang
- Web-Interface

## Lizenz

Dieses Projekt steht unter der [MIT-Lizenz](LICENSE).
