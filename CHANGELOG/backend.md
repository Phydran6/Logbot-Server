# Changelog — Backend

FastAPI-API (`backend/`). Versionsformat: `YYYY.MM.DD.HH.MM.SS`.

## 2026.07.31.23.00.00
### Fixed
- **Reverse Proxy sperrt sich nicht mehr aus.** Die erzeugte Caddyfile leitete Port 80
  bisher komplett auf `https://<FQDN>` um — bei fehlerhaftem Zertifikat oder DNS war die
  Oberfläche danach über *keinen* Weg mehr erreichbar. Jetzt bleibt `:80` in jeder Vorlage
  ein vollwertiger Zugang, IP- und FQDN-Zugriff funktionieren parallel auf 80 und 443.
- **Manuelle Änderungen im Caddyfile-Editor werden nicht mehr verworfen.** `POST /api/caddy/apply`
  baute die Datei aus `mode` neu, sobald ein Modus mitkam — der Editor-Inhalt wurde ignoriert
  („Einstellungen werden falsch übernommen"). Das Frontend schickt jetzt nur noch den Editor-Inhalt.
- **DNS-Prüfung bricht nicht mehr ab.** Ein im Container nicht auflösbarer FQDN führte zu
  HTTP 400; jetzt ist es eine Warnung im Ergebnis (der Container-Resolver ist oft ein anderer
  als der im restlichen Netz).

### Added
- **Vorab-Validierung**: jede Konfiguration geht zuerst durch Caddys `/adapt` — Syntaxfehler
  werden gemeldet, ohne den laufenden Zustand anzufassen.
- **Automatischer Rollback**: schlägt `/load` fehl oder antwortet Caddy danach nicht mehr,
  wird die zuvor laufende Konfiguration wiederhergestellt.
- **Modus `internal`**: Zertifikat aus Caddys eigener CA — HTTPS ohne Internet und ohne
  Let's Encrypt (Browser warnt einmalig).
- **`extra_hosts`**: zusätzliche Adressen (IPs oder interne Namen), die per HTTPS erreichbar
  sein sollen; erhalten ein internes Zertifikat, da es für IPs keine öffentlichen gibt.
- **`POST /api/caddy/reset`**: Notausstieg zurück auf reines HTTP.
- Startet die App mit einer gespeicherten Konfiguration, die nicht lädt, wird jetzt die
  HTTP-Grundkonfiguration geladen statt gar nichts.
- Zertifikat-Upload prüft auf PEM-Format und setzt `chmod 600` auf den Key.
- **`CADDY_FORCE_HTTP=true`** (Umgebungsvariable): Notausstieg ohne Web-UI — beim Start wird
  auf reines HTTP zurückgesetzt und die gespeicherte Konfiguration verworfen. Für den Fall,
  dass TLS klemmt und man deshalb gar nicht mehr an die Oberfläche kommt.

## 2026.07.31.22.10.00
### Added
- **Filter nach Logtypen** für `GET /api/logs` und den Export (`routes/logs.py`):
  - `min_severity` — Schweregrad-Gruppe, z. B. `warning` = Warnungen *und alles Dringendere*.
    Abbildung über `SEVERITY_ORDER` inkl. Kurzformen (`err`, `warn`, `crit`, `emerg` …).
  - `category` — fachliche Kategorien (`auth`, `kernel`, `network`, `firewall`, `container`,
    `cron`, `mail`, `system`, `audit`); Treffer über Syslog-Facility **oder** Dienstnamen.
  - `facility` — Syslog-Facility 0–23.
  - `device_type` — Geräteart des sendenden Systems (Subquery über `agents`, nutzt `idx_logs_agent_id`).
- `GET /api/logs/filter-options` liefert zusätzlich `severities`, `categories`, `facilities`
  und `device_types`. Die Logtyp-Listen sind fest hinterlegt — ein `DISTINCT` über die
  Millionen Zeilen der `logs`-Tabelle wäre dafür zu teuer.
- Startup-Migration `ensure_log_indexes` legt `idx_logs_facility` an (`CREATE INDEX
  CONCURRENTLY`, blockiert also keine Schreibzugriffe); für Neuinstallationen auch in `db/init.sql`.

### Changed
- `hostname_exact` vergleicht per `ilike` ohne Wildcards statt `lower(hostname) = …` —
  gleiches Ergebnis, nutzt aber den vorhandenen Trigramm-Index.

## 2026.07.31.21.10.00
### Added
- **`GET /api/logs/export`** (`routes/logs.py`): Export der aktuell gefilterten Logs als
  **CSV** oder **JSON**, gestreamt (kein Vollpuffer im RAM), `limit` bis 500.000 Zeilen.
  Der Endpoint fehlte bisher komplett — die Export-Buttons im Frontend liefen ins Leere.
  Er steht bewusst **vor** `GET /api/logs/{log_id}`, sonst schluckt die ID-Route den Pfad.
- **`hostname_exact`**-Parameter für `GET /api/logs` und den Export: vergleicht den Hostnamen
  exakt (case-insensitiv) statt als Teilstring — die Geräte-Ansicht braucht das, damit
  z. B. `srv1` nicht auch die Logs von `srv10` mitzieht.

### Security
- CSV-Export entschärft Werte, die mit `=`, `+`, `-` oder `@` beginnen (Formel-Injection in
  Excel/LibreOffice), und schreibt ein UTF-8-BOM für korrekte Umlaute in Excel.

### Hinweis
- Der Streaming-Export öffnet bewusst eine **eigene** DB-Session: ab FastAPI 0.106 ist die per
  `Depends` injizierte Session beendet, bevor der Response-Body gesendet wird.

## 2026.07.18.16.00.00
### Changed
- **Ingest `device_type` dynamisch aus dem Agent-Token** (`/api/agents/ingest`): `linux` → `linux_agent`, `windows` → `windows_agent`, sonst Bestandsverhalten `windows_agent`. Vorher hart `windows_agent` – Linux-HTTPS-Agenten erschienen dadurch fälschlich als Windows. Für korrekte Anzeige ein Token mit Typ `linux` verwenden.

## 2026.07.11.13.03.42
### Added
- **Netzwerk-DNS-Verwaltung** (`routes/network.py`): `GET/PUT /api/network/dns` und `POST /api/network/dns/test`. Standard = per DHCP vergebener System-DNS des Hosts (gelesen aus `/proc/1/root/.../resolv.conf`), optional eigene Server + Such-Domains; wird auf `/etc/resolv.conf` des Backend-Containers angewendet und beim Start erneut gesetzt.

### Changed
- Behebt „FQDN nicht auflösbar" im Reverse-Proxy-Check auf jedem Netz, ohne hartes `extra_hosts` in `docker-compose.yml` (entfernt).

## 2026.05.30.18.02.35
### Added
- Ausgangsbasis dieses Changelogs. Aktueller Funktionsstand u.a.: HTTPS-Log-Ingest (`/api/agents/ingest`), Agent- & Token-Verwaltung, MFA/TOTP, Caddy-Management (Reverse Proxy & TLS), Disk-Monitoring und Retention-Housekeeping.

_Änderungen vor Einführung des Changelogs wurden nicht einzeln erfasst._
