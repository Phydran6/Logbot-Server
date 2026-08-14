# Changelog — Backend

FastAPI-API (`backend/`). Versionsformat: `YYYY.MM.DD.HH.MM.SS`.

## 2026.08.14.12.00.00
### Added
- **Systemcheck** (`app/diagnostics.py`, `routes/diagnostics.py`): prüft das System in einem
  Durchlauf und sagt bei jedem Fund, *was* nicht geht, *woran* das gemessen wurde und *was zu
  tun ist*. 24 Prüfungen in fünf Bereichen:
  - **Kern**: Backend, Datenbankverbindung samt Antwortzeit, vollständiges Schema (Tabellen
    *und* die per Startup-Migration nachgezogenen Spalten), Indizes, Platte, Speicher, CPU.
  - **Dienste**: Weboberfläche, Caddy-Admin-API, Syslog-Empfänger auf 514, Zustand aller
    `logbot-*`-Container (über den Host).
  - **Sicherheit**: `JWT_SECRET` noch auf `change-me`, Standardpasswörter auf Admin-Konten
    (bcrypt-Vergleich gegen `admin`/`password`/`logbot`), HTTPS aktiv, TLS zur externen
    Datenbank.
  - **Betrieb**: Logeingang (Alter des neuesten Eintrags), stille Geräte, gesetzte
    Aufbewahrung, Archivierung (letzter Lauf), LDAP-Erreichbarkeit — beides nur, wenn
    eingeschaltet.
  - **Netz & Updates**: DNS, GitHub, Aktualität, Host-Zugriff.
  Jede Prüfung läuft einzeln abgesichert und mit eigenem Zeitlimit (20 s): fällt eine aus,
  bleibt der Rest des Berichts brauchbar. `GET /api/diagnostics/last` liefert den letzten
  Bericht ohne neue Messung, `POST /api/diagnostics/run` misst neu (nur Admin).
- **Patchmanagement** (`app/updater.py`, `routes/updates.py`, `scripts/logbot-update.sh`):
  - `GET /api/updates/status` vergleicht den installierten Commit bzw. die `VERSION`-Datei mit
    dem Stand auf GitHub (`api.github.com`, Ergebnis 15 Minuten zwischengespeichert — anonym
    sind nur 60 Abfragen pro Stunde erlaubt; `GITHUB_TOKEN` hebt das an).
  - `POST /api/updates/apply` spielt den neuen Stand ein, `POST /api/updates/rollback` fällt auf
    eine Sicherung zurück. Beide verlangen ein Bestätigungswort im Rumpf, damit ein
    versehentlicher Klick nichts auslöst.
  - Das eigentliche Update läuft als Skript auf dem **Host**, nicht im Container — der
    Container kann sich nicht selbst ersetzen. Gestartet wird es über `systemd-run`, damit der
    Lauf den Neubau der Container überlebt (ein per `nsenter` gestarteter Kindprozess läge in
    der Control-Group des Containers und würde mitgetötet).
  - Ablauf: sichern (Dateien + optional `pg_dump`) → `git fetch`/`reset --hard` bzw. frischer
    Clone → `docker compose build && up -d` → warten, bis `/api/health` wieder antwortet.
    Schlägt ein Schritt fehl, spielt das Skript die Sicherung **selbsttätig** zurück.
  - Fortschritt und Ergebnis stehen in `<install>/data/update-state.json`, das ausführliche
    Protokoll in `<install>/data/update.log` (`GET /api/updates/log`). Bewusst Dateien auf dem
    Host und keine Tabelle: während des Updates ist die Datenbank zeitweise weg.
- `app/hostexec.py`: gemeinsamer Helfer für Befehle auf dem Host (`nsenter`), inklusive
  Dateien lesen/schreiben und dem Start langlaufender Vorgänge.
- `VERSION` im Projektwurzelverzeichnis als eindeutiger Versionsstand für den Abgleich.

### Changed
- Neue Umgebungsvariablen (alle mit sinnvollen Vorgaben): `LOGBOT_INSTALL_DIR` (`/opt/logbot`),
  `LOGBOT_REPO_SLUG`, `LOGBOT_BRANCH`, `GITHUB_TOKEN`.

## 2026.08.02.20.00.00
### Fixed
- **Backend startete nicht mehr, jede Anfrage endete mit HTTP 502.** `app/branding.py` lag als
  Windows-1252 statt UTF-8 auf der Platte: das „ü" in „Backend für Whitelabel-System" war ein
  einzelnes Byte `0xFC`. Python liest Quelldateien immer als UTF-8 und brach beim Import ab
  (`SyntaxError: (unicode error) 'utf-8' codec can't decode byte 0xfc`). Der Container lief
  damit in eine Neustartschleife, und Caddy meldete für Oberfläche, Login **und** den
  Agenten-Ingest 502.
  Ursache war ein Reparaturlauf gegen doppelt kodierte Umlaute, der bei dieser Datei aus
  korrektem UTF-8 wieder Windows-1252 gemacht hat. Alle übrigen Quell- und
  Konfigurationsdateien wurden byteweise geprüft und sind gültiges UTF-8.

## 2026.08.02.18.00.00
### Added
- **Passkeys / WebAuthn** (`routes/passkey.py`): Anmeldung mit Windows Hello, Face ID,
  Fingerabdruck oder Sicherheitsschlüssel statt Passwort und Einmalcode.
  - Registrieren (angemeldet): `POST /register/options` → `POST /register/verify`;
    verwalten über `GET/PUT/DELETE /credentials`.
  - Anmelden (offen): `POST /login/options` → `POST /login/verify` liefert das Zugangstoken.
    Ohne Benutzernamen sucht der Browser selbst einen passenden Passkey; ein unbekannter
    Benutzername liefert trotzdem gültige Optionen, damit sich darüber keine Konten ausspähen
    lassen.
  - Herkunft und Domäne für die Signaturprüfung kommen aus `SITE_URL`, ersatzweise aus dem
    `Origin`-Header. Jede Challenge gilt genau einmal und läuft nach 5 Minuten ab.
  - Neue Tabelle `webauthn_credentials` (Startup-Migration und `db/init.sql`), `sign_count`
    wird fortgeschrieben — er entlarvt geklonte Schlüssel.
  - Bewusst **kein** zusätzlicher MFA-Schritt nach dem Passkey: er ist bereits Gerätebesitz
    plus Entsperrung durch PIN oder Biometrie.
- Neue Abhängigkeit: `webauthn`.

### Security
- **Webhook-Abruf ohne Bremse**: `GET /api/webhook/{id}/call` ist ohne Anmeldung erreichbar
  (Token als Parameter) und liefert Logdaten — jetzt auf 60 Aufrufe pro Minute begrenzt.

### Performance
- `GET /api/database/status` schätzt die Zeilenzahl über `pg_class.reltuples`, statt
  `count(*)` über die gesamte `logs`-Tabelle laufen zu lassen (bei Millionen Zeilen ein
  Sekunden-Scan bei jedem Aufruf der Systemzustand-Seite).

## 2026.08.02.16.00.00
### Added
- **Externe Datenbank** (`app/config.py`): neue Umgebungsvariablen `DATABASE_URL` (komplette
  Verbindung, hat Vorrang) und `DB_SSLMODE` (`require`/`verify-ca`/`verify-full`). `postgresql://`
  wird automatisch auf den async-Treiber gehoben, Benutzer/Passwort werden URL-sicher kodiert.
  Der Syslog-Dienst versteht dieselben Variablen (`syslog/syslog_server.py`).
- **`GET /api/database/status`** (Admin): zeigt Verbindungsziel ohne Zugangsdaten, ob die
  Datenbank extern liegt, ob TLS aktiv ist, PostgreSQL-Version, Größe, Verbindungen und
  Antwortzeit. Jede Kennzahl einzeln abgesichert, damit fehlende Rechte auf einer verwalteten
  Datenbank nicht die ganze Auskunft kippen.
- **Anmeldung gegen LDAP / Active Directory** (`app/ldap_auth.py`, `routes/ldap.py`), optional
  und über die Oberfläche einzurichten:
  - Schlägt die lokale Anmeldung fehl, wird zusätzlich das Verzeichnis gefragt. Lokale Konten
    funktionieren unverändert weiter.
  - Passwortprüfung immer über einen **zweiten Bind mit dem DN des Benutzers** — die reine
    Suche beweist gar nichts. Leere Passwörter werden abgelehnt, weil LDAP-Server sie als
    anonyme Anmeldung akzeptieren und Erfolg melden würden.
  - Eingaben werden nach RFC 4515 escaped (sonst ließe sich der Suchfilter umschreiben).
  - Gruppen → Rollen (`admin_group`), optionale Pflichtgruppe, Benutzer werden auf Wunsch beim
    ersten Anmelden angelegt. Neue Spalte `users.auth_source` (`local`/`ldap`) samt
    Startup-Migration; ein bereits vorhandenes **lokales** Konto gleichen Namens wird nie
    übernommen, sonst könnte ein gleichnamiges Verzeichniskonto den lokalen Admin kapern.
  - `POST /api/ldap/test` spielt eine echte Anmeldung durch und zeigt DN, Gruppen und die
    daraus abgeleitete Rolle — auch bevor LDAP scharf geschaltet ist.
- **Archivierung alter Logs** (`app/archiving.py`, `routes/archiving.py`): schreibt Logs älter
  als N Tage als `.ndjson.gz` und überträgt sie per **SFTP, FTPS, FTP, SMB** oder in einen
  eingebundenen Ordner. Zeitplan (täglich zur eingestellten Stunde, Hintergrund-Task ohne
  zusätzlichen Dienst), Verbindungstest mit echter Testdatei, Historie der letzten 20 Läufe.
  Das Löschen nach der Übertragung läuft über die **gemerkten Zeilen-IDs**, nicht über den
  Zeitstempel — sonst könnten zwischenzeitlich eingetroffene Einträge mit altem Datum
  ungesichert verschwinden.

### Changed
- Neue Abhängigkeiten: `ldap3` (LDAP), `paramiko` (SFTP), `smbprotocol` (SMB).

## 2026.08.02.14.00.00
### Security
- **Branding-Endpunkte waren ohne Anmeldung beschreibbar** (`app/branding.py`). `PUT /config`,
  `POST /upload/logo`, `POST /upload/favicon` und `POST /reset` hingen an keiner Prüfung —
  wer den Server erreichte, konnte Farben, Firmenname und vor allem **`custom_css`** setzen,
  das die Oberfläche bei jedem Besucher ungefiltert in ein `<style>`-Element schreibt, und
  beliebige Dateien ablegen. Alle vier verlangen jetzt einen Admin (`get_current_admin`).
- **Pfad-Ausbruch beim Asset-Abruf**: `GET /assets/{filename}` reichte den Namen direkt an
  `os.path.join` weiter — `../../etc/passwd` hätte damit jede lesbare Datei des Containers
  ausgeliefert. Der Name muss jetzt exakt dem Muster der eigenen Upload-Routine entsprechen,
  zusätzlich wird der aufgelöste Pfad gegen den Asset-Ordner geprüft.
- **Uploads ohne Größenbegrenzung** konnten die Platte füllen: jetzt stückweises Schreiben
  mit Abbruch bei 5 MB (`MAX_UPLOAD_BYTES`) und Aufräumen der angefangenen Datei.

### Changed
- Neue Standard-Farbschemata passend zum überarbeiteten Design. Damit bestehende
  Installationen nicht beim alten Aussehen hängen bleiben, hebt `_migrate_legacy_schemes`
  die gespeicherte Konfiguration **nur dann** auf die neuen Werte, wenn dort exakt die alten
  Standardfarben stehen — selbst gewählte Farben bleiben unangetastet.

## 2026.08.02.13.30.00
### Fixed
- **Ingest lehnte große Lieferungen ab.** Die FRITZ!Box liefert ihren kompletten Puffer auf
  einmal — beobachtet wurden 800 Einträge, das Limit lag bei 500 („List should have at most
  500 items"). Obergrenze jetzt **5000**. Zusätzlich stückelt der n8n-Workflow die Einträge
  in Pakete zu 400, damit die Größe des Puffers keine Rolle mehr spielt.

## 2026.07.31.23.30.00
### Added
- **Ingest für Sammler erweitert** (`POST /api/agents/ingest`). Bisher konnte ein Agent nur
  eigene Logs melden — Hostname kam aus dem Payload, die IP war die des Absenders, ein
  Zeitstempel war nicht vorgesehen. Neu sind optional:
  - `ip_address` / `device_type` im Request: ein Sammler (z. B. n8n) meldet die Logs eines
    *anderen* Geräts, das dann mit **eigener IP, eigenem Hostnamen und eigener Geräteart**
    in der Geräteliste steht statt unter der IP des Sammlers.
  - pro Eintrag `timestamp`, `event_id`, `group`, `facility` sowie optionales `level`/`source`
    (bisher Pflicht mit Default). Ohne `timestamp` gilt weiterhin die Empfangszeit.
  - Paketgröße von 50 auf 1000 Einträge angehoben (die FRITZ!Box liefert ~500 auf einmal).
- **Duplikate werden verworfen statt gespeichert.** Einträge mit eigenem `timestamp` bekommen
  einen `dedup_key` (SHA256 aus Hostname, Zeit, Ereignis-ID und Text); der Insert läuft mit
  `ON CONFLICT DO NOTHING` gegen einen partiellen Unique-Index. Damit darf dieselbe Quelle
  beliebig oft ihren kompletten Puffer schicken — gespeichert wird nur, was neu ist. Die
  Antwort enthält jetzt `accepted` **und** `duplicates`. Doppelte innerhalb einer Lieferung
  werden schon vor dem Insert zusammengefasst.
- **Einstufung von FRITZ!Box-Ereignissen** (`app/fritzbox.py`): die Box liefert keinen
  Schweregrad, nur eine Ereignis-ID. Bekannte IDs werden über eine Tabelle eingestuft
  (z. B. 503 „Anmeldung gescheitert" → `warning`, 122 „VPN-Fehler" → `error`, 121
  „VPN getrennt" → `warning`), unbekannte über Stichwörter im Meldungstext. Zusätzlich
  entsteht ein Dienstname aus der Gruppe (`fritzbox-net`, `fritzbox-wlan`, `fritzbox-sys`,
  `fritzbox-auth`, `fritzbox-audit`). Greift nur bei `device_type: "fritzbox"`.
- **Log-Kategorien erweitert** (`routes/logs.py`): die FRITZ!Box-Dienstnamen zählen zu
  „Anmeldung & Rechte", „Netzwerk", „System & Dienste" und „Audit" — die vorhandenen
  Logtyp-Filter greifen also ohne Zusatzarbeit.

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
