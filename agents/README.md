# LogBot Agent v2026.01.30.13.30.00

**Log-Forwarder für Linux und Windows - Keine Abhängigkeiten!**

Sendet System-Logs an den LogBot Server.

Entwickelt von Philipp Fischer  
Kontakt: p.fischer@itconex.de

## Features

- 📋 **Linux:** Nutzt vorhandenes rsyslog - kein Python nötig!
- 📋 **Windows:** Reines PowerShell - kein Python nötig!
- ⚡ **Sofort einsatzbereit** - Ein Befehl pro Plattform
- 🔄 **Auto-Start** - Startet automatisch beim Boot
- 🔧 **Keine Abhängigkeiten** - Nutzt nur vorhandene System-Tools

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
tar -xzf logbot-agent-v2026.01.30.13.30.00.tar.gz
cd logbot-agent-v2026.01.30.13.30.00
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
2. **Rechtsklick** auf `install-windows.bat` → **"Als Administrator ausführen"**
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

### Windows (PowerShell als Admin)
```powershell
.\install-windows.ps1 -Test
```

## Deinstallation

### Linux
```bash
sudo bash install-linux.sh uninstall
```

### Windows (PowerShell als Admin)
```powershell
.\install-windows.ps1 -Uninstall
```

## Verwaltung

### Linux (rsyslog)
```bash
# Status
systemctl status rsyslog

# Neustart (nach Konfigurationsänderung)
sudo systemctl restart rsyslog

# Konfiguration anzeigen
cat /etc/rsyslog.d/99-logbot.conf

# Logs
journalctl -u rsyslog -f
```

### Windows (Scheduled Task)
```powershell
# Status
Get-ScheduledTask -TaskName LogBotAgent

# Starten
Start-ScheduledTask -TaskName LogBotAgent

# Stoppen
Stop-ScheduledTask -TaskName LogBotAgent

# Konfiguration anzeigen
Get-Content "$env:ProgramData\LogBot-Agent\config.json"
```

## Fehlerbehebung

### Logs kommen nicht an

1. **Server erreichbar?**
   ```bash
   # Linux
   nc -zvu LOGBOT_SERVER 514
   
   # Windows (PowerShell)
   Test-NetConnection -ComputerName LOGBOT_SERVER -Port 514
   ```

2. **Firewall?**
   - Linux: `sudo ufw allow 514/udp`
   - Windows: Port 514 UDP ausgehend erlauben

3. **LogBot Server läuft?**
   ```bash
   # Auf dem Server
   docker compose ps
   docker compose logs -f syslog
   ```

### Linux: rsyslog startet nicht
```bash
# Konfiguration testen
sudo rsyslogd -N1

# Fehler anzeigen
sudo journalctl -u rsyslog -n 50
```

### Windows: Task läuft nicht
```powershell
# Task-Status prüfen
Get-ScheduledTaskInfo -TaskName LogBotAgent

# Manuell starten und Fehler sehen
powershell.exe -File "C:\ProgramData\LogBot-Agent\LogBotAgent.ps1"
```

## Konfiguration anpassen

### Linux

Datei bearbeiten: `/etc/rsyslog.d/99-logbot.conf`

```bash
# Beispiel: Nur Errors senden
*.err @logbot-server:514

# Beispiel: TCP statt UDP
*.* @@logbot-server:514

# Nach Änderung:
sudo systemctl restart rsyslog
```

### Windows

Datei bearbeiten: `C:\ProgramData\LogBot-Agent\config.json`

```json
{
    "server_host": "logbot-server",
    "server_port": 514,
    "hostname": "MEIN-PC",
    "log_sources": ["Application", "System", "Security"],
    "min_level": "warning"
}
```

Nach Änderung Task neustarten:
```powershell
Stop-ScheduledTask -TaskName LogBotAgent
Start-ScheduledTask -TaskName LogBotAgent
```

## Changelog

### v2026.01.30.13.30.00 (2026-01-30)
- Komplette Neuentwicklung ohne Python
- Linux: Native rsyslog-Integration
- Windows: Reines PowerShell
- Keine externen Abhängigkeiten mehr

## Support

Bei Fragen: p.fischer@itconex.de
