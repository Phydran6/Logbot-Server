# LogBot Agent v2026.03.31.17.26.46

Log-Forwarder für Linux und Windows – keine zusätzlichen Abhängigkeiten.

Entwickelt von Phydran6  
Kontakt: Phydran6

## Features
- Linux: nutzt vorhandenes rsyslog – kein Python nötig
- Windows: reines PowerShell – kein Python nötig
- Schnell einsatzbereit: ein Befehl pro Plattform
- Auto-Start: startet automatisch beim Boot
- Keine Zusatzsoftware: nur System-Tools

## Installation

### Linux
```bash
# Via Git
git clone https://github.com/DEIN-USERNAME/logbot-agent.git
cd logbot-agent
sudo bash install-linux.sh
```

**Oder manuell:**
```bash
tar -xzf logbot-agent-v2026.03.31.17.26.46.tar.gz
cd logbot-agent-v2026.03.31.17.26.46
sudo bash install-linux.sh
```

Der Installer:
1. Installiert rsyslog falls nicht vorhanden
2. Fragt nach Server-Adresse und Port
3. Fragt nach Protokoll (UDP/TCP) und Log-Level
4. Konfiguriert rsyslog automatisch
5. Sendet Test-Nachrichten

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
- Konfigurationsdatei: `/etc/rsyslog.d/99-logbot.conf`
- Nutzt den vorhandenen rsyslog-Dienst
- Keine zusätzliche Software

### Windows
- Installation: `C:\ProgramData\LogBot-Agent\`
- Scheduled Task: "LogBotAgent" (läuft als SYSTEM)
- Reines PowerShell-Script

## Test

### Linux
```bash
# Manuell Test-Nachricht senden
logger -t test "Hallo LogBot"

# Oder via Installer
sudo bash install-linux.sh test
```

Hinweis: Nach einer frischen Server-Installation läuft LogBot zunächst nur über HTTP. HTTPS (Let’s Encrypt oder eigenes Zertifikat) kann im LogBot-Web-UI unter „Einstellungen → Reverse Proxy & TLS“ aktiviert werden. Für HTTPS-Agenten unbedingt FQDN + Zertifikat konfigurieren.

### Windows (PowerShell als Admin)
```powershell
.\install-windows.ps1 -Test
```
