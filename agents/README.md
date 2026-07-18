# LogBot Agent v2026.07.18.16.00.00

Log-Forwarder für Linux und Windows – keine zusätzlichen Abhängigkeiten.
Zwei Modi je Plattform: **Syslog** (rsyslog/UDP-TCP) oder **HTTPS** (verschlüsselt + Token, DNS/FQDN).
Der Linux-Installer ist **teilautomatisch**: Standard = HTTPS, jede Abfrage hat 5 s Timeout und läuft sonst auf Default – ohne Terminal (Pipe/cron) läuft alles ohne Rückfrage.

Entwickelt von Phydran6  
Kontakt: Phydran6

📓 Changelog: [../CHANGELOG/agents.md](../CHANGELOG/agents.md)

## Features
- Linux: nutzt vorhandenes rsyslog – kein Python nötig
- Windows: reines PowerShell – kein Python nötig
- Schnell einsatzbereit: ein Befehl pro Plattform
- Auto-Start: startet automatisch beim Boot
- Keine Zusatzsoftware: nur System-Tools

## Installation

### Linux (One-Liner, empfohlen)

**Voll automatisch** – FQDN + Token gleich mitgeben, keine Rückfragen:
```bash
curl -sSL https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/agents/install-linux.sh \
  | sudo bash -s -- --fqdn logbot.example.com --token DEIN-AGENT-TOKEN
```

**Oder Werte per Umgebungsvariable** (`sudo -E` reicht die Variablen durch):
```bash
curl -sSL https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/agents/install-linux.sh \
  | LOGBOT_FQDN=logbot.example.com LOGBOT_TOKEN=xxxx sudo -E bash
```

**Interaktiv** – der Installer fragt FQDN/Token ab (jede Abfrage 5 s Timeout, sonst Default):
```bash
curl -sSL https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/agents/install-linux.sh | sudo bash
```

> Token im Web-UI unter **Agent-Tokens** erstellen – am besten mit Typ **linux**, dann erscheint der Host korrekt als „Linux-Agent". Den Token nicht in Shell-History/Logs stehen lassen; wo möglich per Prompt oder Env statt Klartext-Parameter.

#### Ablauf & Verhalten
- **Standard = HTTPS**: ein schlanker **Python-systemd-Dienst** (`logbot-agent`, nur Python-Standardbibliothek) liest **alle** Logs aus journald und sendet sie verschlüsselt + Token als JSON-Batches (max. 50) an `https://<FQDN>/api/agents/ingest`. DNS-basiert (FQDN Pflicht, IP nur optionaler Laufzeit-Fallback).
- **Teilautomatisch**: jede Rückfrage wartet max. 5 s und nimmt sonst den Default. Über eine SSH-Sitzung fragt auch der `curl | bash`-Weg dank `/dev/tty` nach; ganz ohne Terminal (cron) läuft alles ohne Eingabe.
- **Zwingend nötig** sind bei HTTPS nur **FQDN** und **Token** – per Parameter, Env-Variable oder Platzhalter im Skript (siehe unten). Fehlen sie komplett, bricht der Installer mit klarer Meldung ab.
- **Syslog-Alternative**: `--mode syslog` (rsyslog → UDP/TCP, Standard-Port 514) statt HTTPS.

#### Parameter (Kurzform)
| Parameter | Env-Variable | Bedeutung |
|---|---|---|
| `--fqdn <name>` | `LOGBOT_FQDN` | Server-FQDN (Pflicht bei https) |
| `--token <tok>` | `LOGBOT_TOKEN` | Agent-Token (Pflicht bei https) |
| `--mode https\|syslog` | `LOGBOT_MODE` | Modus (Standard `https`) |
| `--port <n>` | `LOGBOT_PORT` | Port (https=443, syslog=514) |
| `--ip <ip>` | `LOGBOT_IP` | Optionale IP als Fallback |
| `--min-level info\|warning\|error` | `LOGBOT_MINLEVEL` | Ab welchem Level gesendet wird |
| `--insecure` | `LOGBOT_INSECURE=true` | Selbstsignierte TLS-Zerts akzeptieren |
| `--yes` / `--unattended` | – | Keine Rückfragen, alles Default |
| `--timeout <sek>` | `LOGBOT_TIMEOUT` | Wartezeit je Abfrage (Standard 5) |

`sudo bash install-linux.sh --help` zeigt die vollständige Übersicht.

#### FQDN/Token fest im Skript hinterlegen (optional)
Am Anfang von `install-linux.sh` stehen auskommentierte Platzhalter. Zum Aktivieren einfach das führende `#` entfernen und den Wert setzen – danach läuft `sudo bash install-linux.sh` voll automatisch ohne Eingabe:
```bash
#PLACEHOLDER_FQDN="logbot.example.com"
#PLACEHOLDER_TOKEN="hier-agent-token-eintragen"
#PLACEHOLDER_MODE="https"
```
Vorrang: **Parameter > Umgebungsvariable > Platzhalter > interaktive Abfrage > Default**.

> HTTPS ist auch der saubere Weg hinter einem Reverse-Proxy (z. B. Nginx Proxy Manager): rohes Syslog (514) wird von HTTP-Proxies nicht weitergeleitet, HTTPS über den FQDN dagegen schon. Für HTTPS im LogBot-Web-UI unter „Einstellungen → Reverse Proxy & TLS" FQDN + Zertifikat konfigurieren.

### Windows
1. Archiv entpacken (z.B. nach `C:\Temp\logbot-agent`)
2. Rechtsklick auf `install-windows.bat` → „Als Administrator ausführen“
3. Server-Adresse eingeben
4. Fertig!

Oder via PowerShell (als Admin):
```powershell
Set-ExecutionPolicy Bypass -Scope Process
.\install-windows.ps1
```

## Was wird installiert?

### Linux
**Syslog-Modus:**
- Konfigurationsdatei: `/etc/rsyslog.d/99-logbot.conf`
- Nutzt den vorhandenen rsyslog-Dienst
- Keine zusätzliche Software

**HTTPS-Modus (Standard):** – alles unter `/opt/logbot-agent/*`
- Agent-Script: `/opt/logbot-agent/logbot_agent.py`
- Konfiguration: `/opt/logbot-agent/config.json` (Rechte 600, enthält den Token)
- Journal-Cursor: `/opt/logbot-agent/cursor`
- systemd-Dienst: `/etc/systemd/system/logbot-agent.service` (läuft als root, liest journald)
- Nur Python-Standardbibliothek – keine externen Pakete

### Windows
- Installation: `C:\ProgramData\LogBot-Agent\`
- Scheduled Task: "LogBotAgent" (läuft als SYSTEM)
- Reines PowerShell-Script

## Test

### Linux
```bash
# Via Installer (erkennt Syslog- bzw. HTTPS-Installation automatisch)
sudo bash install-linux.sh test

# Syslog-Modus zusätzlich manuell testbar
logger -t test "Hallo LogBot"

# HTTPS-Dienst prüfen
systemctl status logbot-agent
journalctl -u logbot-agent -f
```

Hinweis: Nach einer frischen Server-Installation läuft LogBot zunächst nur über HTTP. HTTPS (Let’s Encrypt oder eigenes Zertifikat) kann im LogBot-Web-UI unter „Einstellungen → Reverse Proxy & TLS“ aktiviert werden. Für HTTPS-Agenten unbedingt FQDN + Zertifikat konfigurieren.

### Windows (PowerShell als Admin)
```powershell
.\install-windows.ps1 -Test
```
