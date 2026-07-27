# Changelog — Agents

Installer & Log-Forwarder für Linux/Windows (`agents/`). Versionsformat: `YYYY.MM.DD.HH.MM.SS`.

## 2026.07.18.18.30.00
### Fixed
- **Linux-Installer: Tastatureingabe wurde beim One-Liner ignoriert.** Vorher hatte jede Abfrage einen eigenen 5-s-Timeout – bei `curl … | bash` rauschten die Abfragen durch und eine Eingabe innerhalb der 5 s lief ins Leere. Jetzt gibt es **einen** Countdown am Anfang (`interactive_gate`): Wird eine Taste gedrückt, schaltet der Installer auf **manuell** und fragt ab da **alle** Werte blockierend ab (kein Timeout, Eingabe wird abgewartet). Ohne Tastendruck / ohne Terminal (Pipe/cron) läuft alles automatisch mit Standardwerten. Der Tastaturpuffer wird nach dem Aufweck-Tastendruck geleert, damit die erste echte Abfrage nicht sofort den Default nimmt.
- Robustheit: `interactive_gate` liefert im Kein-Terminal-Fall sauber `return 0` – kein `set -e`-Abbruch mehr im vollautomatischen Lauf.

## 2026.07.18.16.00.00
### Added
- **Linux-Agent: One-Liner-Installation (`curl … | bash`).** Der Installer ist jetzt **teilautomatisch** und pipe-tauglich: `curl -sSL <URL> | sudo bash -s -- --fqdn logbot.example.com --token xxxx`. Werte kommen aus **Parametern**, **Umgebungsvariablen** (`LOGBOT_FQDN`, `LOGBOT_TOKEN`, `LOGBOT_MODE`, …) oder auskommentierten **Platzhaltern** im Skript. Vorrang: Parameter > Env > Platzhalter > Abfrage > Default.
- **Teilautomatischer Ablauf:** Jede Rückfrage hat **5 s Timeout** (via `LOGBOT_TIMEOUT` änderbar) und läuft sonst auf Default. Prompts werden aus `/dev/tty` gelesen → auch der `curl | bash`-Weg fragt in einer SSH-Sitzung nach; ohne Terminal (cron) läuft alles ohne Eingabe. `--yes`/`--unattended` unterdrückt alle Rückfragen.
- **Standard ist jetzt HTTPS** (nicht mehr Syslog) – sinnvoll, weil der Server oft nicht lokal liegt. FQDN + Token sind bei HTTPS zwingend (aus Param/Env/Platzhalter), sonst klarer Abbruch. Syslog weiterhin via `--mode syslog`.
- `--help` zeigt alle Aktionen/Parameter.

### Changed
- **Alle Agent-Daten liegen unter `/opt/logbot-agent/*`** – der Journal-Cursor wanderte von `/var/lib/logbot-agent/cursor` nach `/opt/logbot-agent/cursor` (überschreibbar via `LOGBOT_CURSOR`). Deinstallation räumt Altstände unter `/var/lib/logbot-agent` mit auf.
- Kein blockierendes Startmenü mehr: Standardaktion ist direkt `install`; `uninstall` / `uninstall-purge` / `test` als Argument.
- README (Agents + Haupt-README) um One-Liner, Parameter-Tabelle und Platzhalter-Anleitung erweitert.

_Windows-Agent: gleiche One-Liner-/Teilautomatik-Idee ist als Follow-up vorgesehen (noch offen)._

## 2026.07.18.12.00.00
### Added
- **Linux-Agent: HTTPS-Modus.** Der Installer (`install-linux.sh`) fragt jetzt bei der Installation den **Verbindungsmodus** ab: `1) Syslog (rsyslog UDP/TCP)` wie bisher **oder** `2) HTTPS`. Im HTTPS-Modus wird ein schlanker **Python-systemd-Dienst** (`logbot-agent`) eingerichtet, der **alle** Logs aus journald liest und als JSON-Batches (max. 50) verschlüsselt + Token-authentifiziert an `https://<FQDN>/api/agents/ingest` sendet. Nur Python-Standardbibliothek – keine externen Pakete.
- **DNS-/FQDN-basiert:** HTTPS verlangt bei der Installation die Angabe des **FQDN** (optionale IP als Laufzeit-Fallback). Der Dienst löst den FQDN zur Laufzeit erneut auf (DNS-first, IP-Fallback). Damit funktioniert der Weg auch hinter einem Reverse-Proxy (NPM), durch den rohes Syslog nicht geht.
- Robuster Journal-Cursor (`/var/lib/logbot-agent/cursor`): Start „ab jetzt" (keine History-Flut), at-least-once-Auslieferung, überlebt Neustarts, re-seedet bei rotiertem/ungültigem Cursor.
- **Server-Ingest** setzt `device_type` jetzt dynamisch aus dem Agent-Token (`linux` → `linux_agent`, `windows` → `windows_agent`) statt hart `windows_agent`. Frontend zeigt „Linux-Agent" als Typ/Filter.

### Fixed
- **Deinstallation/Menü (Linux):** Fehlerhafte `ä`-Escapes in `echo`-Ausgaben (wurden wörtlich als `ä` statt `ä` ausgegeben) durch echte Umlaute ersetzt. Fehlerhafte awk-Regex `/link\\/ether/` im MAC-Fallback der Server-Purge korrigiert (`$1=="link/ether"`). Server-Purge nutzt jetzt ein curl-Options-**Array** statt einer Wort-Split-anfälligen Zeichenkette.
- Deinstallation entfernt jetzt **beide** Modi sauber: rsyslog-Konfig + Queue **und** systemd-Dienst + `/opt/logbot-agent` + Cursor-Verzeichnis. Server-Purge übernimmt Host/Port/Token automatisch aus `config.json`.

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
