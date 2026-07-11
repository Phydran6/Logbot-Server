# Changelog — Agents

Installer & Log-Forwarder für Linux/Windows (`agents/`). Versionsformat: `YYYY.MM.DD.HH.MM.SS`.

## 2026.07.11.13.35.01
### Fixed
- **Linux-Agent: Hostname statt IP im Web.** Die rsyslog-Weiterleitung nutzt jetzt `RSYSLOG_TraditionalForwardFormat` (enthält `<PRI>` + `%HOSTNAME%`) statt `RSYSLOG_TraditionalFileFormat`. Ohne `<PRI>` konnte der Syslog-Server die Nachricht nicht parsen und ordnete die Logs der Absender-IP statt dem Hostnamen zu. Bestehende Installationen einmal neu konfigurieren (Installer → Installieren), damit `/etc/rsyslog.d/99-logbot.conf` neu geschrieben wird.

## 2026.07.09.19.55.08
### Fixed
- **FQDN als LogBot-Server-Adresse** wird jetzt zuverlässig unterstützt (Linux-Installer): robuste DNS-Auflösung über mehrere Methoden (`getent ahosts` → `python3` → `dig`/`host`), zusätzlicher TCP-Reachability-Test. Kein harter Abbruch (`exit 1`) mehr bei nicht sofort auflösbarem Namen — es wird gewarnt und nachgefragt (rsyslog löst zur Laufzeit ohnehin erneut auf).
- Eingegebene IP-Adresse wird nicht mehr heimlich durch einen Reverse-DNS-Namen ersetzt.

### Removed
- `nslookup` als Resolver entfernt (liefert bei NXDOMAIN auf vielen Systemen rc=0 → Falsch-Positive).

_Vorherige Stände: Windows-Agent `2026.02.20.19.00.09`, Agents-README `2026.03.31.17.26.46`._
