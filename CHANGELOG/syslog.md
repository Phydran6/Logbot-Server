# Changelog — Syslog-Server

Syslog-Empfang & Parsing (`syslog/`). Versionsformat: `YYYY.MM.DD.HH.MM.SS`.

## 2026.10.23.12.00.00
### Security
- **Grenzen gegen Überflutung** – Port 514 ist ohne Anmeldung offen: Zeilen über 16 KiB werden gekürzt, höchstens 20 000 UDP-Zeilen warten (darüber wird verworfen und gezählt), höchstens 512 TCP-Verbindungen, stille Verbindungen nach 10 Minuten getrennt, überlange TCP-Zeilen verworfen statt den Leser zu blockieren.
- Ein Hostname mit Schrägstrich wird zu `_` – per Syslog kann sich niemand als Container einer VM (`vm/container`) ausgeben.
- asyncpg 0.32, Grundsystem beim Bauen aktualisiert.
## 2026.10.11.20.00.00
### Fixed
- **UDP-Aufgaben ohne Grenze:** bei langsamer Datenbank stauten sich je Meldung eine Aufgabe im Speicher. Jetzt höchstens `SYSLOG_UDP_MAX_INFLIGHT` (5.000), darüber wird verworfen und einmal pro Minute gezählt gemeldet; Aufgaben werden referenziert (vorher konnte der Garbage Collector sie einsammeln).
- Geräte-Zwischenspeicher wird ab 10.000 Einträgen um abgelaufene ausgedünnt.

## 2026.10.10.22.00.00
### Added
- **Annahme-Stopp bei voller Platte** (`DISK_INGEST_STOP`, 95 %): Meldungen werden verworfen (mit Zähler im Protokoll) statt die Datenbank zu ersticken. UDP kennt kein „später nochmal“ — aber eine Datenbank, die an voller Platte stirbt, verliert alles.
- **Wiederholungen zusammenfassen:** gleiche Meldung desselben Geräts innerhalb eines Stapels → eine Zeile mit `extra_data.repeat`.

### Fixed
- **Ein einziger kaputter Wert ließ den ganzen COPY-Stapel scheitern** (bis zu 100 Meldungen fremder Geräte): zu lange Felder, NUL-Zeichen, Zahlen statt Text in JSON-Feldern. Neu: `sanitize()`.
- JSON-Logs mit numerischem Level (pino/bunyan: `"level": 30`) gingen verloren, bei TCP samt Verbindung.
- TCP: eine schlechte Zeile beendete still die ganze Verbindung.
- Gelöschtes Gerät im Cache ließ jeden Stapel bis zu 5 min am Fremdschlüssel scheitern.

## 2026.05.13.20.58.33
### Added
- Ausgangsbasis dieses Changelogs. Unterstützte Formate: RFC 5424, RFC 3164 (BSD), UniFi Netconsole & MAC/Model, Cisco IOS, Fortinet `key=value`, JSON.

_Änderungen vor Einführung des Changelogs wurden nicht einzeln erfasst._
