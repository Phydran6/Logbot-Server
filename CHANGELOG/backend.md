# Changelog — Backend

FastAPI-API (`backend/`). Versionsformat: `YYYY.MM.DD.HH.MM.SS`.

## 2026.09.15.20.00.00
### Fixed
- **HTTPS-Agents bekamen die IP von Caddy statt der Geräte-IP** (z. B. `172.18.0.3`). Das Backend hängt hinter Caddy und nahm `request.client.host`. Neue Funktion `client_ip()` in `app/limiter.py`: Sie liest den letzten Eintrag aus `X-Forwarded-For`, den Caddy setzt und den ein Client nicht fälschen kann. Vorrang hat weiterhin eine vom Agent gemeldete `ip_address`.
- **Altbestand wird übernommen, nicht verdoppelt.** Findet der Ingest kein Gerät mit Hostname + echter IP, aber eines mit Hostname + Caddy-IP, bekommt dieser Eintrag die richtige IP und Geräteart. So entsteht keine zweite Karte, und die Logs bleiben am Gerät.
- **Linux-Agents erschienen als „Windows-Agent“.** Ohne `device_type` im Payload und mit untypisiertem Token (z. B. `global-agent`) galt stur `windows_agent`. Jetzt gilt diese Reihenfolge: Payload → Token-Typ → User-Agent (`Python-urllib` = Linux-Agent, `PowerShell` = Windows-Agent) → `unknown`. Eine vom Agent gemeldete Geräteart überschreibt einen gespeicherten falschen Wert.

### Security
- **Rate-Limits griffen für alle Nutzer gemeinsam.** slowapi zählte pro Caddy-IP. Damit konnten zehn Fehlversuche irgendeines Nutzers den Login für alle sperren, und ein Angreifer sah das Limit nur als Summe aller Nutzer. Das Limit zählt jetzt pro echter Client-IP.
## 2026.09.10.20.00.00
### Fixed
- **Der Kanal „stabil" konnte ein Downgrade als Update anbieten.** `compare()` verglich
  installierten und entfernten Stand nur auf *Ungleichheit*, nicht auf *Reihenfolge*.
  Zeigt der Kanal auf ein Release, das älter ist als der installierte Stand — was
  passiert, sobald für den aktuellen Stand noch kein Release angelegt wurde —, meldete
  die Oberfläche „Update verfügbar", und das Einspielen fuhr den Server in Wahrheit
  zurück.
  `compare()` ordnet Versionen jetzt (`parse_version`) und gibt zusätzlich das
  Verhältnis zurück: `behind` (echtes Update), `same`, `ahead` (Server ist neuer als
  der Kanal) oder `unknown`. Bei gleicher Version entscheidet weiterhin der Commit —
  ein weitergelaufener Zweig ohne angehobene VERSION-Datei bleibt damit ein Update.
- `POST /api/updates/apply` weist einen Rückschritt mit HTTP 409 ab und nennt beide
  Auswege (Release anlegen oder Kanal wechseln). Wer den Rückschritt wirklich will,
  setzt `allow_downgrade` oder gibt ein `ref` von Hand an.
- Die Update-Seite zeigt bei diesem Zustand **„Server ist voraus"** statt eines
  Update-Knopfs, dazu eine Erklärung, was zu tun ist. Der Knopf bleibt aus, statt nur
  eine Fehlermeldung zu erzeugen.
- `import re` fehlte in `app/updater.py` — fiel erst beim Test der neuen
  Versionsordnung auf.

## 2026.09.09.22.00.00
### Added
- **Sicherung und Wiederherstellung** (`app/backup.py`, `routes/backup.py`): ZIP-Datei mit
  aussen liegendem, immer lesbarem `manifest.json` und innen liegender Nutzlast — wahlweise
  im Klartext (`payload.zip`) oder AES-256-GCM-verschlüsselt (`payload.bin`, PBKDF2-HMAC-SHA256
  mit 210 000 Runden). Sechs Bereiche einzeln wählbar, beim Sichern wie beim Zurückspielen.
  Tabellen liegen als `jsonl.gz` und werden in Blöcken von 5000 Zeilen gelesen und geschrieben,
  damit die `logs`-Tabelle den Speicher nicht sprengt.
  *Warum das Manifest aussen liegt:* Beim Zurückspielen muss **vor** der Passwortabfrage
  erkennbar sein, von welcher Version die Sicherung stammt — sonst fällt ein Versionskonflikt
  erst auf, wenn die Daten halb in der Datenbank stehen.
- **Versionsprüfung beim Zurückspielen**: gleich / älter / unlesbar / **neuer als der Server**.
  Der letzte Fall blockiert und lässt sich nur ausdrücklich übergehen.
- **Pflicht-Rückfrage vor Systemeingriffen** (`app/guard.py`): Update, Rückfall, Zurückspielen
  und das Schalten eines Zusatzdienstes verlangen im Rumpf ein `backup`-Objekt. Fehlt es,
  gibt es HTTP 400 — die Rückfrage lässt sich also nicht durch Weglassen der Oberfläche
  umgehen. Scheitert die Sicherung, startet der Eingriff nicht.
- **Ereignisverteiler** (`app/events.py`): Server-Sent Events an alle offenen Oberflächen,
  mit gemerktem letztem Stand je Ereignistyp und Lebenszeichen alle 20 s. Bewusst kein
  WebSocket — es fliesst nur in eine Richtung und läuft so durch jeden Reverse Proxy.
- **Update-Beobachter** (`updater.watch_task`): fragt GitHub im kurzen Takt ab und meldet
  einen neuen Stand genau einmal. Dazu **GitHub-Webhook** (`POST /api/updates/webhook`) mit
  HMAC-Prüfung; ohne gesetztes `LOGBOT_WEBHOOK_SECRET` wird nichts angenommen.
- **Release-Kanäle**: `stable`, `edge`, `pinned`. `remote_state()` prüft gegen den Kanal,
  `start_run()` gibt `--ref` an das Wartungsskript weiter.
- **Anzeige-Parser** (`app/logparse.py`): zerlegt Rohzeilen in Zusammenfassung, benannte
  Felder und Abzeichen. RFC 5424/3164, UniFi Netconsole und MAC/Modell, Cisco IOS,
  `key=value`, JSON, journald, Netfilter. Ändert nie Daten — reine Anzeige.
- **App-Schnittstelle** (`routes/mobile.py`) unter `/api/app`: Cursor-Blättern (`before_id`),
  Nachlaufen (`since_id`), kompakte Antworten, `bootstrap` mit `api_level`/`capabilities`.
- **KI-Auswertung** (`app/ai.py`, `routes/ai.py`): Anthropic, OpenAI, n8n extern, n8n lokal.
  Mit Vorschau des Sendeinhalts und Verbindungstest gegen eine erfundene Logzeile.
- **Zusatzdienste** (`app/stacks.py`, `routes/stacks.py`): Compose-Profile schalten, Zugangs-
  daten anzeigen und neu setzen, Protokolle lesen, Kapazität prüfen.
- **Mailversand** (`app/mail.py`, `routes/mail.py`): erzeugt die vollständige
  Postfix-Konfiguration und verschickt über SMTP — Container oder vorhandener Server.
- **Terminal** (`app/shell.py`, `routes/shell.py`): PTY auf dem Host über WebSocket. Nur
  Administratoren, nur mit `LOGBOT_WEBSHELL=true`, mit Sitzungsgrenze, Leerlauf-Abbruch und
  Protokollierung.
- `auth.admin_from_token()` für die beiden Wege ohne Kopfzeile (SSE, WebSocket).
- `GET /api/logs/{id}/parsed` und `agent_id` in der Antwort von `/api/agents/ingest`.

### Changed
- `POST /api/updates/apply` und `/rollback` verlangen zusätzlich zum Bestätigungswort die
  beantwortete Sicherungsfrage; `/apply` nimmt `ref` für ein bestimmtes Release entgegen.
- `POST /api/agents/decommission` ordnet vom Genauesten zum Ungenauesten zu (`agent_id`,
  MAC, Hostname+IP, Hostname) und meldet in `matched_by`, welcher Weg gegriffen hat.
  `all_for_hostname` räumt zusätzlich alle weiteren Einträge desselben Hostnamens ab.

### Fixed
- **Zurückspielen scheiterte an Zeitstempeln.** JSON kennt keinen Datumstyp, asyncpg verlangte
  beim Einfügen aber `datetime`-Objekte. Jeder Wert geht jetzt als Text und wird per
  `CAST(CAST(:x AS text) AS <typ>)` von PostgreSQL umgewandelt — der innere Cast legt den
  Parametertyp fest, der äussere den Zieltyp. ID-Zähler werden danach per `setval` nachgezogen.

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
