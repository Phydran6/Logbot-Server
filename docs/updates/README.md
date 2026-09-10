# Updates

Patchmanagement: prüfen, auswählen, einspielen, zurückfallen.

← [Übersicht](../../README.md) · [Alle Dokumente](../README.md)

---

## Sofortmeldung

Der Wunsch dahinter: *Sobald auf GitHub etwas gepusht wird, sollen alle
laufenden Server das mitbekommen — nicht erst, wenn jemand zufällig die
Update-Seite öffnet.*

Zwei Wege führen dahin. Beide enden im selben Verteiler, von dort geht der
Hinweis per Server-Sent Events in jedes offene Browser-Fenster:

### 1. Eigener Beobachter *(läuft von selbst)*

Der Server sieht alle 120 Sekunden bei GitHub nach. Erst wenn wirklich etwas
Neues da ist, gibt es eine Meldung — nicht bei jeder Abfrage.

```bash
# .env
LOGBOT_UPDATE_WATCH=true
LOGBOT_UPDATE_WATCH_INTERVAL=120
```

Das ist der Weg für jeden Server hinter einer Firewall — also für die meisten.

### 2. GitHub-Webhook *(wirklich sofort)*

Ist der Server aus dem Internet erreichbar, meldet GitHub den Push direkt.

1. In der `.env` ein Secret setzen *(der Installer würfelt eines aus)*:
   ```
   LOGBOT_WEBHOOK_SECRET=<langer Zufallswert>
   ```
2. Im Repository unter **Settings → Webhooks → Add webhook**:
   - **Payload URL:** `https://dein-logbot.example.com/api/updates/webhook`
   - **Content type:** `application/json`
   - **Secret:** derselbe Wert
   - **Events:** *Just the push event*

Ohne gesetztes Secret nimmt der Server **gar keine** Webhook-Meldung an — ein
offener Endpunkt wäre eine Einladung, den Server im Takt Anfragen an GitHub
schicken zu lassen. Die Signatur (`X-Hub-Signature-256`) wird bei jeder Meldung
geprüft.

Angezeigt wird der Hinweis als Pille oben rechts in der Kopfleiste, in jedem
offenen Fenster, ohne Neuladen.

---

## Welchen Stand soll der Server fahren?

Nicht jeder will immer den letzten Commit. Drei Möglichkeiten, einzustellen
unter *System → Updates*:

| Kanal | Bedeutung | Für wen |
|-------|-----------|---------|
| **Stabil** | das zuletzt veröffentlichte Release | Regelbetrieb — Voreinstellung |
| **Aktuell** | der Kopf des Zweiges, jeder Push | Test- und Entwicklungsserver |
| **Festgelegt** | genau ein Release, Tag oder Commit | wenn nichts mehr wackeln darf |

Die Wahl steht in der Datenbank und übersteht ein Update. Die Prüfung richtet
sich danach: Wer auf **Stabil** steht, bekommt keine Meldung, weil jemand einen
Zwischenstand gepusht hat.

Bei **Festgelegt** bleibt der Server auf dem gewählten Punkt stehen, bis jemand
ihn bewusst weiterzieht. Zur Auswahl stehen die Releases des Repositories; gibt
es keine, werden die Tags gelistet.

---

## Update einspielen

*System → Updates → **Update einspielen***

Davor stehen zwei Sperren:

1. **Ein Hinweis**, was passiert und was es kosten kann — mit Häkchen zum
   Bestätigen. Gegen den versehentlichen Klick.
2. **Die Sicherungsfrage.** Vorher sichern — ja oder nein? Ohne beantwortete
   Frage weist der Server den Aufruf ab. Auch das „Nein“ muss man wählen.
   Siehe [Sicherung](../backup/README.md).

Dann läuft, **auf dem Host** und nicht im Container:

1. Sichern nach `/opt/logbot-backups/<Zeitstempel>/` — Dateien und auf Wunsch
   ein `pg_dump`.
2. Den gewählten Stand holen (`git fetch` + `reset --hard` auf Tag, Zweig oder
   Commit; ersatzweise ein frischer Clone).
3. `docker compose build && docker compose up -d --remove-orphans`.
4. Warten, bis `/api/health` wieder antwortet.

Schlägt Schritt 2, 3 oder 4 fehl, spielt das Skript die Sicherung **selbsttätig**
zurück. Fortschritt: `/opt/logbot/data/update-state.json`, Protokoll:
`/opt/logbot/data/update.log` — beides zeigt die Oberfläche an.

> Der Lauf startet über `systemd-run` als eigene Unit. Nötig, weil er die
> Container neu baut — inklusive des Backends, das ihn angestoßen hat. Ein
> Kindprozess des Containers stürbe dabei mitten im Update.

---

## Über die Kommandozeile

```bash
curl -sSL https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/install.sh \
  | sudo bash -s -- update -y
```

Ein bestimmtes Release:

```bash
sudo bash /opt/logbot/backend/scripts/logbot-update.sh apply --ref v2026.08.14
```

Von Hand, mit allen Schaltern:

```bash
sudo bash /opt/logbot/backend/scripts/logbot-update.sh apply \
  --dir /opt/logbot --branch main --ref v2026.08.14 --db-backup
sudo bash /opt/logbot/backend/scripts/logbot-update.sh rollback --backup 20260814-120000
sudo bash /opt/logbot/backend/scripts/logbot-update.sh status
```

---

## Zurückfallen

*System → Updates → **Auf vorherigen Stand zurück***

Zeigt die Sicherungen des Wartungsskripts (Dateien, optional Datenbankabzug).
Auch hier läuft vorher die Sicherungsfrage.

> **Achtung:** Enthält die gewählte Sicherung einen Datenbankabzug, wird er
> eingespielt — **alle Logs seit dieser Sicherung sind dann weg.** Die
> Oberfläche sagt das für jede Sicherung einzeln an.

Nicht zu verwechseln mit den [ZIP-Sicherungen](../backup/README.md): Die
gehören zum Datenbestand und lassen sich granular zurückspielen. Der Rückfall
hier setzt den ganzen Stand auf einen früheren Zeitpunkt.

---

## Zum Datenbestand

Die Logs liegen in einem eigenen Docker-Volume und überstehen ein Update
normalerweise unbeschadet. Verlassen sollte man sich darauf nicht: Ändert sich
das Datenbankschema oder bricht der Lauf ab, können Logs verloren gehen.

Deshalb die Sicherungsfrage vor jedem Eingriff — und deshalb lässt sie sich
nicht wegklicken, sondern nur beantworten.

---

## Wenn das Update über die Oberfläche fehlt

Läuft LogBot mit `deploy/hardened.yml`, hat das Backend keinen Zugriff auf den
Host — dann geht das Update nur über die Kommandozeile. Der Systemcheck sagt das
ausdrücklich an, und die Update-Seite zeigt statt des Knopfes den Einzeiler.

---

## PostgreSQL-Major-Upgrade

Ein Image-Tausch reicht **nicht** — Datenverzeichnisse sind zwischen
Major-Versionen nicht kompatibel. Siehe [Datenbank](../../db/README.md).

Notbremse, falls schon aktualisiert und die Datenbank nicht mehr startet:

```bash
echo "POSTGRES_VERSION=16" >> .env
docker compose up -d
```

---

## Weiter

- [Sicherung](../backup/README.md)
- [Installation](../install/README.md)
- [Changelog](../../CHANGELOG/README.md)
