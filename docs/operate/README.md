# Betrieb

Der Alltag mit einem laufenden LogBot.

← [Übersicht](../../README.md) · [Alle Dokumente](../README.md)

---

## Die Oberfläche

Alles hängt am **linken Menü**, in drei Ebenen:

```
Überwachung
  Dashboard · Logs · Geräte
Verwaltung
  Webhooks · Benutzer
System
  Einstellungen
      Allgemein · Aufbewahrung · Agent-Token · Archivierung
      Netzwerk · Datenbank · Passwort · Anmeldesicherheit
      Verzeichnis (LDAP) · Erscheinungsbild · Neustart
  Systemzustand · Updates · Sicherung
  KI-Auswertung · Zusatzdienste · Mail · Terminal
```

Die Einstellungen haben ihre Unterpunkte links im Baum — nicht mehr als
Reiterleiste rechts im Inhalt. Wer die alten Adressen gespeichert hat:
`/settings/ldap` und Konsorten funktionieren unverändert weiter.

**Einklappen:** Der Pfeil unten links ist immer sichtbar und zeigt in die
Richtung, in die es geht — nach links zum Einklappen, nach rechts zum
Ausklappen. Eingeklappt bleibt eine reine Icon-Leiste; ein Punkt markiert den
Bereich, in dem die offene Seite liegt. Der Zustand wird gemerkt.

---

## Sprache

Unten links im Menü, neben dem Weltkugel-Zeichen: **Deutsch** oder **English**.

Die Wahl gilt sofort, ohne Neuladen, und wird im Browser gemerkt — sie ist also
pro Person und Gerät, nicht pro Server. Ohne gemerkte Wahl entscheidet die
Spracheinstellung des Browsers; versteht der Server sie nicht, gilt Deutsch.

Fehlt eine Übersetzung, erscheint der deutsche Text — nie eine leere Stelle.
Neue Sprachen kommen als Datei in [`frontend/src/i18n/`](../../frontend/README.md)
dazu.

---

## Logs ansehen

**Filter:** Host, Zeitraum, Schweregrad (dieser und alles Dringendere),
Kategorie (Auth, Kernel, Netzwerk, Firewall, Container, Cron, Mail, System,
Audit), Syslog-Facility und Geräteart.

Die Filter stehen in der Adresse. Damit ist jede Ansicht verlinkbar, als
Lesezeichen ablegbar — und der Export (CSV/JSON) liefert genau das, was auf dem
Bildschirm steht.

**Rohdaten lesbar:** Jede Zeile läuft durch den Anzeige-Parser. Aus

```
<134>Sep  9 12:00:01 fw01 kernel: [12345.6] IN=eth0 OUT= MAC=aa:bb:… SRC=192.168.1.10 DST=8.8.8.8 PROTO=TCP SPT=44321 DPT=443
```

wird

> **von 192.168.1.10 nach 8.8.8.8:443 (TCP)**
> `Quelle 192.168.1.10` `Ziel 8.8.8.8` `Ziel-Port 443` `Protokoll TCP` `Eingang eth0`

Die Rohzeile bleibt daneben stehen — wenn die Erkennung danebenliegt, muss man
nachsehen können, was wirklich ankam. Der Parser fasst die Datenbank nie an, er
stellt nur anders dar.

Erkannt werden RFC 5424 und 3164, UniFi Netconsole und MAC/Modell, Cisco IOS,
`key=value` (Fortinet, Netfilter), JSON und journald.

---

## Systemcheck

*System → Systemzustand → **Systemcheck starten***

24 Prüfungen in fünf Bereichen auf einen Knopfdruck: Datenbank, Dienste,
Sicherheit, Betrieb, Netz. Zu jedem Fund steht **was** nicht geht, **woran** das
gemessen wurde und **was zu tun ist**. Angezeigt werden zuerst nur die
Auffälligkeiten.

---

## Terminal im Browser

*System → Terminal* — nur für Administratoren.

Eine echte Shell auf dem Server, **als root**. Wer sie erreicht, hat den Server.
Deshalb ist sie standardmäßig **aus**:

In die `.env` eintragen:

```
LOGBOT_WEBSHELL=true
```

Danach `docker compose up -d backend`.

Zusätzliche Sicherungen:

- nur Administratoren, Token wird bei jedem Verbindungsaufbau geprüft
- nur mit Host-Zugriff (bei der gehärteten Variante gibt es sie schlicht nicht)
- jede Sitzung wird protokolliert: wer, wann, wie lange
- höchstens 3 Sitzungen gleichzeitig (`LOGBOT_WEBSHELL_MAX_SESSIONS`)
- nach 15 Minuten ohne Eingabe endet die Sitzung (`LOGBOT_WEBSHELL_IDLE_TIMEOUT`)

**Was das Terminal nicht kann:** Programme mit voller Bildschirmsteuerung —
`top`, `htop`, `nano`, `vim`. Der Bildschirm ist bewusst schlank gehalten
(keine 300-kB-Bibliothek für ein Nebenwerkzeug) und hängt Ausgabe hinten an,
statt einen Cursor zu führen. Für solche Fälle: SSH.

---

## Befehle auf dem Server

Zuerst ins Installationsverzeichnis wechseln:

```bash
cd /opt/logbot
```

Status:

```bash
docker compose ps
```

Protokolle:

```bash
docker compose logs -f
```

Nur das Backend:

```bash
docker compose logs -f backend
```

Neustart:

```bash
docker compose restart
```

Stoppen:

```bash
docker compose down
```

Starten:

```bash
docker compose up -d
```

---

## Aufbewahrung und Archivierung

**Global:** Einstellungen → Aufbewahrung. Logs älter als X Tage werden gelöscht.

**Pro Gerät:** in der Geräte-Ansicht — nach Alter oder nach Anzahl. Nützlich für
das eine geschwätzige Gerät, das sonst alles zumüllt.

**Archivierung:** Einstellungen → Archivierung. Alte Logs gepackt auf SFTP,
FTPS, FTP, SMB oder in einen eingebundenen Ordner — täglich zur festgelegten
Stunde oder auf Knopfdruck, auf Wunsch mit anschließendem Löschen. Mit
Verbindungstest und Verlauf.

### Platte läuft voll

LogBot greift von selbst ein, in drei Stufen:

| Belegung | Was passiert |
|---------:|--------------|
| ab 80 % | abgelaufene Anmelde-Token weg, `VACUUM` |
| ab 90 % | Logs älter als die eingestellte Aufbewahrung weg, `VACUUM FULL` |
| ab 95 % | **alle** Logs per `TRUNCATE` weg |

Stufe 3 ist die Notbremse: ein voller Datenträger legt auch die Datenbank still.
Wer die Logs braucht, sorgt vorher für Platz — oder für
[Archivierung](#aufbewahrung-und-archivierung).

---

## Benutzer und Anmeldung

- **Rollen:** Administrator und Benutzer.
- **MFA/TOTP:** jede gängige Authenticator-App, mit 10 Einmal-Codes.
  10 Fehlversuche → 15 Minuten Sperre. Admins können notfalls zurücksetzen.
- **Passkeys:** Windows Hello, Face ID, Fingerabdruck, Sicherheitsschlüssel.
  Braucht HTTPS mit gültigem Zertifikat.
- **LDAP / Active Directory:** optional. Schlägt die lokale Anmeldung fehl, wird
  zusätzlich das Verzeichnis gefragt. Gruppen lassen sich auf Rollen abbilden.

---

## Erscheinungsbild

Einstellungen → Erscheinungsbild: Firmenname, Slogan, Logo, Favicon,
Primärfarbe, Standard-Theme und eigenes CSS.

Die Zustandsfarben leiten sich aus der Markenfarbe ab — eine geänderte
Primärfarbe zieht überall mit. Ohne eigenes Logo steht das LogBot-Zeichen.

---

## Weiter

- [Updates](../updates/README.md)
- [Sicherung](../backup/README.md)
- [Integrationen](../integrations/README.md)
