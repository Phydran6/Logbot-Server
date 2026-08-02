# LogBot v2026.08.02.20.00.00
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

**One-Liner direkt von GitHub** (holt sich die Quellen selbst, installiert nach `/opt/logbot`):
```bash
curl -sSL https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/install.sh | sudo bash
```
Der Installer wartet 5 Sekunden: **eine Taste drücken** → Rückfragen werden gestellt, sonst
läuft er automatisch durch. Ganz ohne Rückfragen:
```bash
curl -sSL https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/install.sh | sudo bash -s -- -y
```

**Oder aus dem geklonten Repository:**
```bash
# Repository klonen
git clone https://github.com/Phydran6/Logbot-Server.git
cd Logbot-Server

# Installer ausführen (erstellt .env automatisch)
sudo bash install.sh
```

**Weitere Aktionen** (`sudo bash install.sh <aktion>` bzw. `| sudo bash -s -- <aktion>`):

| Aktion | Wirkung |
|--------|---------|
| `install` (Standard) | Installiert; bestehende Installation wird auf Wunsch aktualisiert |
| `update` | Aktualisiert Quellen (`git pull`) und startet neu gebaute Container |
| `uninstall` | Stoppt und entfernt die Container – **Daten bleiben** |
| `uninstall-purge` | Löscht zusätzlich Volumes **und alle Logs** sowie `/opt/logbot` |

Optionen: `--dir <pfad>`, `--repo <url>`, `--branch <name>`, `--no-build`, `--yes`, `--timeout <s>`
(auch als `LOGBOT_DIR`, `LOGBOT_REPO`, `LOGBOT_BRANCH`, `LOGBOT_YES`, `LOGBOT_TIMEOUT`).
Eine vorhandene `.env` wird nie überschrieben – das Datenbank-Passwort bleibt zum bestehenden
Postgres-Volume passend.

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
### Linux-Agent (empfohlen, One-Liner)
Teilautomatischer Installer – **Standard = HTTPS** (verschlüsselt + Token, DNS/FQDN, funktioniert auch übers Internet). Details: [agents/README.md](agents/README.md).

```bash
# Voll automatisch (FQDN + Token mitgeben):
curl -sSL https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/agents/install-linux.sh \
  | sudo bash -s -- --fqdn logbot.example.com --token DEIN-AGENT-TOKEN

# Interaktiv (fragt FQDN/Token, je Abfrage 5 s Timeout, sonst Default):
curl -sSL https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/agents/install-linux.sh | sudo bash
```
Deinstallieren: `sudo bash install-linux.sh uninstall` · Testen: `sudo bash install-linux.sh test`

### Linux (rsyslog, manuell)
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
> ⚠️ **PostgreSQL-Major-Upgrade (z. B. 16 → 17)?** Ein reiner Image-Tausch reicht **nicht** –
> die alte 16er-Datenbank ist nicht mit einem 17er-Server kompatibel. Vorgehen: siehe
> [Update / PostgreSQL-Major-Upgrade](#update--postgresql-major-upgrade).

## Datenbank-Backup
```bash
# Backup erstellen
docker compose exec postgres pg_dump -U logbot logbot > backup.sql

# Backup einspielen
docker compose exec -T postgres psql -U logbot logbot < backup.sql
```

## Update / PostgreSQL-Major-Upgrade
Ab v2026.07.19 nutzt LogBot standardmäßig **PostgreSQL 17-alpine** (vorher 16-alpine).
Die Version ist über `POSTGRES_VERSION` in der `.env` steuerbar (`postgres:${POSTGRES_VERSION:-17}-alpine`).

**Wichtig:** PostgreSQL-Datenverzeichnisse sind zwischen Major-Versionen **nicht** kompatibel.
Ein bestehendes 16er-Volume startet unter einem 17er-Image **nicht** – deshalb gibt es drei
klare Wege statt eines blinden Tausches:

### 🟢 Notbremse (falls schon aktualisiert und die DB nicht mehr startet)
Läuft dein Container nach `git pull` in eine Fehlerschleife, kommst du mit **einer Zeile** sofort
wieder online – ganz ohne Datenverlust:
```bash
echo "POSTGRES_VERSION=16" >> .env    # oder in .env auf 16 setzen
docker compose up -d
```
Danach in Ruhe migrieren (Weg 1).

### Weg 1 – Bestehende Instanz, Daten behalten (Migration)
Automatisch per Skript: sichert die DB, baut das Volume mit der neuen Version neu auf und spielt
die Daten wieder ein. Die Sicherung bleibt danach als `.dump` liegen.
```bash
# im Projektverzeichnis (z. B. /opt/logbot):
git pull
sudo bash db/migrate.sh          # Ziel = POSTGRES_VERSION aus .env (Default 17)
# optional andere Version:  sudo bash db/migrate.sh 18
```
**Oder als One-Liner direkt von GitHub** (findet `/opt/logbot` automatisch, kein `git pull` nötig):
```bash
curl -sSL https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/db/migrate.sh | sudo bash
# Zielversion + ohne Rückfrage:
curl -sSL https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/db/migrate.sh | sudo bash -s -- 18 -y
```

### Weg 2 – Bestehende Instanz, Daten NICHT nötig (frische DB)
Alte DB verwerfen und mit der neuen Version frisch aufsetzen (Login wieder `admin`/`admin`):
```bash
git pull
docker compose down -v           # löscht die Volumes inkl. alter DB
docker compose up -d --build     # frische DB auf PostgreSQL 17 (init.sql läuft neu)
```

### Weg 3 – Neuinstallation
Nichts zu migrieren – der Installer zieht direkt die neue Version (17-alpine), kein 16 mehr:
```bash
git clone https://github.com/Phydran6/Logbot-Server.git
cd Logbot-Server
sudo bash install.sh
```

## Changelog
### v2026.08.02.20.00.00 (2026-08-02)
- FIX: **Backend startete nicht, alles antwortete mit HTTP 502** (Oberfläche, Login und Agenten-Ingest). `backend/app/branding.py` lag als Windows-1252 statt UTF-8 vor — ein einzelnes Byte statt „ü". Python liest Quelldateien immer als UTF-8 und brach beim Import ab. Datei zurück auf UTF-8 gebracht; alle übrigen Dateien wurden byteweise geprüft.

### v2026.08.02.18.00.00 (2026-08-02)
- **Anmeldung mit Passkey** (Windows Hello, Face ID, Fingerabdruck, Sicherheitsschlüssel). Einrichten unter *System → Anmeldesicherheit*, anmelden über den Knopf auf der Login-Seite. Der geheime Teil bleibt auf dem Gerät, die Signatur gilt nur für diese Adresse — eine nachgebaute Anmeldeseite bekommt nichts Verwertbares. Voraussetzung: HTTPS mit gültigem Zertifikat.
- SICHERHEIT: **PostgreSQL war auf allen Netzwerkschnittstellen erreichbar** — der Port ist jetzt auf `127.0.0.1` beschränkt (`DB_BIND=0.0.0.0` hebt das bewusst wieder auf).
- SICHERHEIT: Neues **`docker-compose.hardened.yml`** nimmt dem Backend die weitreichenden Container-Rechte (`privileged`, `pid: host`, `SYS_BOOT`). Sie existieren nur für den Neustart-Knopf und die DNS-Übernahme, heben aber die Trennung zwischen Container und Server praktisch auf. Start: `docker compose -f docker-compose.yml -f docker-compose.hardened.yml up -d`.
- PERFORMANCE: Die Systemzustand-Seite zählt die Logzeilen nicht mehr einzeln durch, sondern nimmt die Schätzung der Datenbank.

### v2026.08.02.16.00.00 (2026-08-02)
- **Externe Datenbank:** LogBot kann die Daten auf einem eigenen Datenbankserver ablegen und selbst nur noch als Anwendung laufen. Konfiguration über `DATABASE_URL` (oder `DB_HOST`/`DB_PORT`) und `DB_SSLMODE` in der `.env`, Start mit `docker compose -f docker-compose.yml -f docker-compose.external-db.yml up -d`. Der mitgelieferte Postgres-Container bleibt dabei stehen, das Volume unangetastet — der Rückweg ist offen. Unter *Systemzustand* steht, welche Datenbank tatsächlich aktiv ist und ob die Verbindung verschlüsselt läuft.
- **Anmeldung über LDAP / Active Directory** (optional, unter *System → Verzeichnis*): Schlägt die lokale Anmeldung fehl, wird zusätzlich das Verzeichnis gefragt — lokale Konten bleiben unberührt. Gruppen lassen sich auf Rollen abbilden, eine Pflichtgruppe kann den Zugang begrenzen, neue Benutzer werden auf Wunsch beim ersten Anmelden angelegt. Ein Testfeld spielt eine echte Anmeldung durch und zeigt Gruppen und Rolle.
- **Archivierung alter Logs** (unter *System → Archivierung*): Logs ab einem einstellbaren Alter werden gepackt auf **SFTP, FTPS, FTP, SMB** oder in einen eingebundenen Ordner geschrieben — täglich zur festgelegten Stunde oder auf Knopfdruck, auf Wunsch mit anschließendem Löschen in der Datenbank. Mit Verbindungstest und Historie der letzten Läufe.

### v2026.08.02.14.00.00 (2026-08-02)
- **Oberfläche neu gestaltet.** Neues Design-System (Farb-Tokens, Karten, Knöpfe, Formularfelder, Abzeichen, Tabellen) — die Zustandsfarben leiten sich aus der Markenfarbe ab, eine im Branding geänderte Primärfarbe zieht überall mit. Dunkles Schema kontrastreicher, helles ruhiger.
- **Seitenmenü** mit gruppierter Navigation (Überwachung / Verwaltung / System), eigenen Icons statt Emoji und klar erkennbarem aktivem Eintrag — auch im angedockten Zustand. Darüber eine Kopfleiste mit dem Titel der aktuellen Seite.
- **Anmeldung** zweispaltig mit Markenseite; **Dashboard** mit Kennzahl-Kacheln, die in die passend gefilterte Log-Ansicht führen, plus Verteilung nach Schweregrad und aktivsten Quellen; **Geräte** als Karten mit Statuspunkt.
- SICHERHEIT: **Branding-Endpunkte waren ohne Anmeldung beschreibbar** — inklusive `custom_css`, das jedem Besucher ausgeliefert wird. Jetzt nur noch für Admins. Ebenfalls behoben: Pfad-Ausbruch beim Asset-Abruf und Uploads ohne Größenlimit.
- FIX: Zoom auf Mobilgeräten war gesperrt; weißes Aufblitzen beim Start; Tastatur-Fokus jetzt durchgängig sichtbar.
- PERFORMANCE: Der globale CSS-Übergang galt für jedes Element im Dokument und bremste lange Loglisten — gilt jetzt nur noch für die Bausteine, die beim Theme-Wechsel wirklich umfärben.

### v2026.07.31.23.30.00 (2026-07-31)
- **FRITZ!Box-Logs anbindbar:** `POST /api/agents/ingest` nimmt jetzt Lieferungen von Sammlern (z. B. n8n) an — `ip_address`, `device_type` und pro Eintrag `timestamp`/`event_id`/`group`/`facility`. Das gemeldete Gerät erscheint mit eigener IP und eigenem Namen in der Geräteliste statt unter der IP des Sammlers. Paketgröße 50 → 1000.
- **Keine doppelten Logs mehr:** Einträge mit eigenem Zeitstempel bekommen einen `dedup_key`; wiederholte Lieferungen derselben Ereignisse werden verworfen (`ON CONFLICT DO NOTHING`). Die Antwort meldet `accepted` und `duplicates`. Bestands-Datenbanken bekommen Spalte + Index beim Start automatisch.
- **Einstufung von FRITZ!Box-Ereignissen** (`backend/app/fritzbox.py`): die Box liefert keinen Schweregrad — bekannte Ereignis-IDs werden über eine Tabelle eingestuft, unbekannte über Stichwörter. Die Dienstnamen (`fritzbox-net`, `-wlan`, `-sys`, `-auth`, `-audit`) zählen zu den vorhandenen Logtyp-Kategorien.
- **UI:** Geräteart „FRITZ!Box" mit Klarnamen in Geräteliste, Geräte-Ansicht und Log-Filter.

### v2026.07.31.23.00.00 (2026-07-31)
- **Reverse Proxy:** Port 80 bleibt in jeder Konfiguration ein vollwertiger Zugang (kein Zwangs-Redirect mehr) – IP und FQDN funktionieren parallel auf 80 und 443. Konfiguration wird vor dem Anwenden geprüft, bei Fehler automatischer Rollback. Neu: selbstsigniertes HTTPS (interne CA), zusätzliche HTTPS-Adressen, „Zurück auf HTTP" und Notausstieg `CADDY_FORCE_HTTP=true`. FIX: manuelle Änderungen im Caddyfile-Editor wurden verworfen.
- **Logs:** Filter nach **Logtypen** – Schweregrad-Gruppen, Kategorie (Auth, Kernel, Netzwerk, Firewall, Container, Cron, Mail, System, Audit), Syslog-Facility und Geräteart. Filter stehen in der URL und gelten auch für den Export.
- **Log-Ansicht pro Gerät** unter `/devices/<hostname>` mit Steckbrief; erreichbar per Klick auf Agent-Karte, Dashboard- oder Listen-Hostname.
- **UI:** Seitenmenü lässt sich zur Icon-Leiste einklappen (Zustand wird gemerkt); Hinweisbalken bei unverschlüsselter Verbindung.
- **Installation:** `install.sh` als One-Liner (`curl … | sudo bash`) mit `install`/`update`/`uninstall`/`uninstall-purge`. FIX: bestehende `.env` wird nicht mehr überschrieben (das neue DB-Passwort passte nicht zum vorhandenen Postgres-Volume).
- **Aufräumen:** `portainer-agent` ist nicht mehr Teil des Stacks (mountete den Docker-Socket = Root-Zugriff auf den Host).
- FIX: CSV-/JSON-Export der Logs funktionierte nicht – der Endpoint `/api/logs/export` fehlte im Backend.

### v2026.07.18.18.30.00 (2026-07-18)
- FIX: **Linux-Installer ignorierte Tastatureingabe beim One-Liner.** Statt 5-s-Timeout pro Abfrage jetzt **ein** Countdown am Start: Taste drücken = manueller Modus (alle Werte werden blockierend abgefragt), sonst automatischer Ablauf. Details: [CHANGELOG/agents.md](CHANGELOG/agents.md).

### v2026.07.18.16.00.00 (2026-07-18)
- NEU: **Linux-Agent One-Liner-Installation** (`curl … | sudo bash`), teilautomatisch (5 s-Timeout je Abfrage), **Standard = HTTPS** (verschlüsselt + Token, DNS/FQDN, auch übers Internet). FQDN/Token via Parameter, Env-Variable oder Platzhalter. Alle Agent-Daten unter `/opt/logbot-agent/*`. Details: [agents/README.md](agents/README.md).
- FIX: Linux-Installer Deinstallation/Menü (fehlerhafte Umlaut-Ausgaben, kaputte awk-MAC-Regex); Uninstall räumt Syslog- **und** HTTPS-Modus auf.
- BACKEND: Ingest setzt `device_type` dynamisch aus dem Agent-Token (`linux` → Linux-Agent). UI: Gerätetyp „Linux-Agent" ergänzt.

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
