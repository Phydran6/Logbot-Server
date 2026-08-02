# Changelog — Frontend

Vue-3-Weboberfläche (`frontend/`). Versionsformat: `YYYY.MM.DD.HH.MM.SS`.

## 2026.08.02.14.00.00
### Changed
- **Oberfläche neu gestaltet.** Grundlage ist ein Design-System in
  `assets/css/main.css`: Tokens für Radien, Schatten, Abstände und Zustandsfarben plus
  fertige Klassen (`.card`, `.btn`, `.input`, `.badge`, `.table`, `.stat-card`, `.modal`, …).
  Die Zustandsfarben (Hover, „soft"-Flächen, Fokusring) entstehen per `color-mix()` aus den
  Markenfarben — eine im Branding geänderte Primärfarbe zieht damit überall automatisch mit.
- **Farbschema**: dunkler, kontrastreicher Hintergrund (`#16161f`) statt des blaugrauen
  Vorgängers; hell entsprechend ruhiger. Bestehende Installationen, die die Farben nie
  angepasst haben, werden beim Start automatisch übernommen (siehe `CHANGELOG/backend.md`).
- **Seitenmenü**: Navigation in Gruppen (Überwachung / Verwaltung / System), eigene
  Icon-Komponente (`components/AppIcon.vue`, Inline-SVG statt Emoji), aktiver Eintrag mit
  Farbfläche und Markierungsbalken — auch im angedockten Zustand erkennbar. Marke, Theme-
  Umschalter und Benutzer sitzen in eigenen Bereichen; darüber liegt eine Kopfleiste mit
  dem Titel der aktuellen Seite.
- **Anmeldung**: zweispaltig mit Markenseite (Logo, Tagline) und Formular, Passwort ein-/
  ausblendbar, Fehler als Hinweisfeld statt roter Box, MFA-Schritt mit eigenem Code-Feld.
- **Dashboard**: Kennzahlen als Kacheln mit Icon und Einordnung, die in die passend
  gefilterte Log-Ansicht führen (z. B. „Fehler & kritisch" → `?min_severity=error`),
  dazu Verteilung nach Schweregrad und aktivste Quellen als Balken sowie Ladeskelette.
- **Geräte**: Karten mit Statuspunkt, Eckdaten als Definitionsliste und eigenen Knöpfen
  für Aufbewahrung/Löschen; Aufbewahrungs-Dialog auf die neue Modal-Klasse umgestellt.
- Log-Level-Abzeichen nutzen jetzt die Badge-Klassen des Design-Systems statt fester
  Tailwind-Farben (`bg-red-500` …) — dadurch im hellen Theme lesbar und brandingfähig.

### Fixed
- **Zoom auf Mobilgeräten war gesperrt** (`user-scalable=no` in `index.html`) — entfernt.
- Beim Start blitzte kurz ein weißer Hintergrund auf (`<body class="bg-gray-100">`);
  die Seite startet jetzt direkt im Theme-Hintergrund.
- Tastatur-Fokus ist durchgängig sichtbar (`:focus-visible`), Scrollbars folgen dem Theme.

### Performance
- Der globale Übergang `* { transition: … }` galt für **jedes** Element im Dokument und
  kostete bei Loglisten mit tausenden Zeilen spürbar Rechenzeit. Er gilt jetzt nur noch für
  die Bausteine, die beim Theme-Wechsel tatsächlich die Farbe wechseln; zusätzlich werden
  Animationen bei `prefers-reduced-motion` abgeschaltet.

## 2026.07.31.23.30.00
### Added
- Geräteart **FRITZ!Box** wird in Geräteliste, Geräte-Ansicht und Log-Filter mit Klarnamen
  angezeigt (statt `fritzbox`) und ist im Typ-Filter der Geräteliste auswählbar.

## 2026.07.31.23.00.00
### Added
- **Hinweis bei unverschlüsselter Verbindung** (`components/InsecureConnectionBanner.vue`):
  wird die Oberfläche über `http://` geladen, erscheint oben ein Balken mit Link auf HTTPS.
  Wegklickbar, die Entscheidung gilt bis zum Schließen des Tabs. Auf localhost erscheint er nicht.
- Reverse-Proxy-Einstellungen: Modus **selbstsigniert (interne CA)**, Feld für **zusätzliche
  HTTPS-Adressen** (mit „Aktuelle Adresse übernehmen"), Anzeige von Server-Warnungen und
  ein Knopf **„Zurück auf HTTP"** als Notausstieg.

### Fixed
- „Apply" wendet jetzt **exakt den Editor-Inhalt** an (vorher überschrieb der gewählte Modus
  serverseitig alle manuellen Änderungen).
- Beim Wechsel auf den HTTP-Modus wird die Seite **nicht mehr automatisch umgeleitet** und es
  öffnet sich kein neuer Tab mehr — es erscheint nur ein Hinweis mit Link. Die harte
  Weiterleitung riss die laufende Sitzung mitten im Speichern ab.
- Vorlagen werden beim Tippen im FQDN-Feld gebündelt nachgeladen (400 ms) statt bei jedem Zeichen.

## 2026.07.31.22.10.00
### Added
- **Logtyp-Filter im Filter-Panel** (`components/LogTable.vue`), oberhalb der bisherigen Felder:
  - **Schweregrad** als Knopfreihe (Alle / Nur kritisch / Fehler und dringender / …) —
    ein Klick statt Level-Dropdown, der aktive Knopf ist farbig.
  - **Kategorie** (Anmeldung & Rechte, Kernel, Netzwerk, Firewall, Container, Cron, Mail,
    System, Audit), **Syslog-Facility** und **Geräteart** als Auswahlfelder.
- Die neuen Filter erscheinen als Chips, landen in der URL und gelten auch für den Export.
- In der Geräte-Ansicht ist die Geräteart ausgeblendet (dort ist das Gerät bereits gesetzt).

## 2026.07.31.21.10.00
### Added
- **Log-Ansicht pro Gerät**: neue Route `/devices/:hostname` (`views/DeviceLogs.vue`) mit
  Steckbrief (Status, IP, MAC, Typ, erst-/zuletzt gesehen, gespeicherte Logs, Retention)
  und darunter der Logliste, fest auf dieses Gerät gefiltert (exakter Hostname-Vergleich).
- **Einstiege dorthin**: Klick auf eine Agent-Karte (`views/Agents.vue`), Klick auf einen
  Hostnamen im Dashboard oder in der allgemeinen Logliste, sowie ein Link im Log-Detail.
  Die Kachel „Hosts" im Dashboard führt zur Geräte-Übersicht.
- **`components/LogTable.vue`**: Filter, Tabelle, Pagination, Detail-Dialog und Export als
  eine wiederverwendbare Komponente — genutzt von der allgemeinen und der Geräte-Ansicht.
  `views/Logs.vue` ist dadurch nur noch ein dünner Rahmen.
- Filter der allgemeinen Log-Ansicht stehen jetzt in der URL (teilbare, reload-feste Links).
- **Ein-/ausklappbares Seitenmenü** (`views/Layout.vue`): Button im Sidebar-Kopf klappt die
  Navigation auf Desktop zu einer schmalen Icon-Leiste (`md:w-16`) zusammen und wieder auf.
  Beschriftungen erscheinen im eingeklappten Zustand als Tooltip (`title`).
- Zustand wird in `localStorage` (`logbot.sidebarCollapsed`) gemerkt und beim nächsten
  Reload wiederhergestellt; ohne verfügbaren `localStorage` gilt er nur für die Sitzung.
- Mobile: zusätzlicher **Schließen-Button** im Sidebar-Kopf (bisher nur Klick auf das Overlay).

### Fixed
- **CSV-/JSON-Export funktioniert wieder.** Die Buttons riefen `/api/logs/export` auf, das es
  im Backend nicht gab (die Anfrage landete auf `/api/logs/{log_id}` und schlug fehl).
  Der Download läuft jetzt über `fetch` + Blob, weil `window.open` keinen Auth-Header setzen kann.

### Changed
- Navigationseinträge kommen jetzt aus einer Liste (`navItems`) statt aus acht einzeln
  ausgeschriebenen `<li>` — Icons/Labels an einer Stelle pflegbar.
- Angezeigte Versionsnummer in der Sidebar kommt jetzt aus `package.json` (war fest auf
  einem alten Stand von 2026.05 verdrahtet und musste doppelt gepflegt werden).
- Footer sitzt jetzt immer am unteren Rand des Inhaltsbereichs (`flex flex-col` + `flex-1`).

## 2026.07.18.16.00.00
### Added
- **Agents:** Gerätetyp **Linux-Agent** (`linux_agent`) im Typ-Filter und in der Typ-Beschriftung ergänzt – passend zum neuen Linux-HTTPS-Agent.

## 2026.07.11.13.03.42
### Changed
- Einstellungen: Reiter **Reverse Proxy** ersetzt durch **Netzwerk** mit zwei Bereichen — **Reverse Proxy** (unverändert) und **DNS** (neu).

### Added
- **DNS**-Bereich: Umschaltung DHCP-automatisch / manuell, Anzeige der erkannten System-DNS, eigene Server + Such-Domains, aktive Nameserver und „Auflösung testen".

## 2026.05.30.18.02.35
### Added
- Ausgangsbasis dieses Changelogs.

_Änderungen vor Einführung des Changelogs wurden nicht einzeln erfasst._
