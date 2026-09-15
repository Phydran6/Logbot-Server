<div align="center">

<img src="docs/assets/logbot-icon.png" alt="LogBot" width="120">

# LogBot

**Zentraler Log-Server für Linux, Windows und Netzwerkgeräte.**

Entwickelt von Phydran6

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub stars](https://img.shields.io/github/stars/Phydran6/Logbot-Server?style=social)](https://github.com/Phydran6/Logbot-Server/stargazers)
[![GitHub issues](https://img.shields.io/github/issues/Phydran6/Logbot-Server)](https://github.com/Phydran6/Logbot-Server/issues)
[![GitHub last commit](https://img.shields.io/github/last-commit/Phydran6/Logbot-Server)](https://github.com/Phydran6/Logbot-Server/commits/main)
[![GitHub release](https://img.shields.io/github/v/release/Phydran6/Logbot-Server?include_prereleases)](https://github.com/Phydran6/Logbot-Server/releases)

</div>

---

## Was LogBot ist

Ein Ort, an dem die Logs aller Systeme zusammenlaufen — und an dem man sie auch
wiederfindet. Server, Arbeitsplätze, Switches, Access Points, Firewalls,
FRITZ!Box: Was Syslog spricht oder einen Agent tragen kann, meldet hierher.

Ein Docker-Stack, ein Installationsbefehl, eine Oberfläche im Browser.

## Was LogBot kann

**Logs annehmen**
Syslog auf UDP/TCP 514. Agents für Linux und Windows, die über HTTPS mit Token
senden — auch aus fremden Netzen übers Internet. Sammler wie n8n dürfen im
Namen anderer Geräte liefern (z. B. für die FRITZ!Box).

**Logs lesbar machen**
Ein Parser zerlegt die Rohzeilen: RFC 5424 und 3164, UniFi, Cisco IOS,
Fortinet-`key=value`, JSON, Netfilter. Aus dreißig Feldern wird eine Zeile, die
man versteht — die Rohzeile bleibt daneben stehen.

**Logs durchsuchen**
Filter nach Host, Zeit, Schweregrad, Kategorie, Facility und Geräteart. Filter
stehen in der Adresse, gelten auch für den Export (CSV/JSON) und lassen sich als
Lesezeichen ablegen.

**Auswerten lassen**
Optional an eine KI geben: direkt an Claude oder ChatGPT, oder über n8n —
extern oder als Container daneben. Nichts davon ist voreingestellt.

**Sich selbst verwalten**
Systemcheck auf Knopfdruck. Patchmanagement, das sich meldet, sobald etwas
Neues da ist. Sicherungen als ZIP, granular und optional verschlüsselt.
Reverse Proxy, TLS, DNS, Archivierung, LDAP, MFA und Passkeys — alles im
Browser, ohne eine einzige Konfigurationsdatei anzufassen.

**Erweitert werden**
Portainer, Watchtower, n8n und Postfix stehen bereit — jeder einzeln zuschaltbar,
keiner läuft ungefragt.

---

## Schnellstart

**Ein Befehl für alles auf Linux** — der Setup-Assistent:

```bash
curl -sSL https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/setup.sh | sudo bash
```

Er zeigt, was auf dem Rechner schon installiert ist, und bietet an:

| | LogBot-Server | Linux-Agent |
|---|---|---|
| **Installieren** | Verzeichnis, Zusatzdienste, Release, Systemprüfung | HTTPS oder Syslog, Adresse, Port, Token, Schweregrad, Zertifikat |
| **Aktualisieren / Testen** | Release, Zusatzdienste ändern, neu bauen ja/nein | Testnachrichten senden |
| **Deinstallieren** | Container weg, Daten bleiben | nur auf diesem Rechner |
| **Komplett entfernen** | inkl. aller Logs und Sicherungen | inkl. Gerät und Logs auf dem Server |

Dazu kommt eine reine **Systemprüfung**: Reicht der Rechner, auch mit Zusatzdiensten?

Jede Option wird abgefragt, Enter nimmt den Standard. **Vor dem Start zeigt der
Assistent den passenden direkten Einzeiler** — den kann man sich für den
nächsten Rechner merken. Löschen muss man ausdrücklich mit `LÖSCHEN` bestätigen.

**Windows-Agent** — PowerShell als Administrator, ohne Parameter mit Menü:

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/agents/install-windows.ps1)))
```

Nach der Server-Installation:

- **Oberfläche:** `http://SERVER-IP` — Anmeldung `admin` / `admin`
  *(bitte sofort ändern; HTTPS danach unter Einstellungen → Netzwerk einschalten)*
- **API-Doku:** `http://SERVER-IP/api/docs`
- **Syslog:** Port 514 (UDP/TCP)
- **Agent-Token** für die Agents: Einstellungen → Agent-Token

### Wenn du schon weißt, was drauf soll

Dieselben Schritte direkt, ohne Assistent. Mit `--yes` bzw. `-Yes` läuft alles ohne
Rückfrage durch, also auch per Automatisierung. Ohne `--yes` läuft ein
5-Sekunden-Countdown: Wer eine Taste drückt, bekommt die Rückfragen.

**Server**

Nur LogBot, Standardwerte:

```bash
curl -sSL https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/install.sh | sudo bash -s -- --yes
```

Mit Zusatzdiensten (portainer, watchtower, n8n, postfix):

```bash
curl -sSL https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/install.sh \
  | sudo bash -s -- --with portainer,watchtower --yes
```

Bestimmtes Release in eigenes Verzeichnis:

```bash
curl -sSL https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/install.sh \
  | sudo bash -s -- --ref v2026.09.10 --dir /srv/logbot --yes
```

Optionen: `--dir` · `--branch` · `--ref` · `--with` · `--no-addons` ·
`--skip-preflight` · `--no-build` · `--yes` · `--timeout` · `--help`

**Linux-Agent**

HTTPS mit Token (empfohlen, auch übers Internet):

```bash
curl -sSL https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/agents/install-linux.sh \
  | sudo bash -s -- --fqdn logbot.example.com --token DEIN-AGENT-TOKEN --yes
```

Syslog im eigenen Netz (UDP oder TCP):

```bash
curl -sSL https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/agents/install-linux.sh \
  | sudo bash -s -- --mode syslog --fqdn logbot.example.com --port 514 --proto tcp --yes
```

Optionen: `--fqdn` · `--token` · `--port` · `--mode https|syslog` · `--proto udp|tcp` ·
`--ip` · `--min-level info|warning|error` · `--insecure` · `--yes` · `--help`

**Windows-Agent**

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/agents/install-windows.ps1))) -Action install -Fqdn logbot.example.com -Token DEIN-AGENT-TOKEN -Yes
```

→ Ausführlich: **[Installation](docs/install/README.md)** · **[Agents](agents/README.md)**

---

## Deinstallieren

Am einfachsten über den [Setup-Assistenten](#schnellstart), Punkt 3/4 (Server) oder
7/8 (Linux-Agent). Er zeigt vorher genau an, was entfernt wird und was bleibt.

> **Alles abbauen? Dann in dieser Reihenfolge:** erst die Agents auf den anderen
> Rechnern, dann den Server. Andersherum senden die Agents ins Leere weiter.
> Wird der Server ohnehin komplett entfernt, reicht bei den Agents
> „nur lokal“.

### Server

| | `uninstall` | `uninstall-purge` |
|---|---|---|
| Container (auch Zusatzdienste) | entfernt | entfernt |
| Logs, Einstellungen, Benutzer, Zertifikate *(Docker-Volumes)* | **bleiben** | **gelöscht** |
| Sicherungs-ZIPs aus *System → Sicherung* *(Volume `backup_data`)* | **bleiben** | **gelöscht** |
| Daten von n8n und Portainer | **bleiben** | **gelöscht** |
| `/opt/logbot` samt `.env` (Passwörter) | **bleibt** | **gelöscht** |
| Update-Sicherungen in `/opt/logbot-backups/` | bleiben | bleiben |
| Gebaute Images, Docker selbst | bleiben | bleiben |
| Zurückholen | `cd /opt/logbot && sudo docker compose up -d` | nicht möglich |

Deinstallieren, Daten bleiben:

```bash
curl -sSL https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/install.sh | sudo bash -s -- uninstall --yes
```

Komplett entfernen, inkl. aller Logs:

```bash
curl -sSL https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/install.sh | sudo bash -s -- uninstall-purge --yes
```

Aus dem Installationsverzeichnis geht dasselbe mit `sudo bash /opt/logbot/install.sh uninstall`.
Bei eigenem Verzeichnis `--dir <pfad>` anhängen.

> ⚠️ **Vor `uninstall-purge`:** Werden die Daten noch gebraucht, zuerst im Web-UI unter
> *System → Sicherung* eine Sicherung erstellen **und herunterladen**. Die Sicherungen
> liegen in einem Docker-Volume und werden mitgelöscht.
>
> **Ohne `--yes`** fragt `uninstall-purge` nach, aber nur nach einem Tastendruck im
> 5-Sekunden-Countdown. Ohne Tastendruck bricht es ab und löscht **nichts**.
>
> **Externe Datenbank:** Die Daten auf dem fremden Datenbankserver bleiben unberührt.

**Reste nach `uninstall-purge` wegräumen** (optional):

Sicherungen vor Updates:

```bash
sudo rm -rf /opt/logbot-backups
```

Gebaute Images*:

```bash
sudo docker image rm logbot-backend logbot-frontend logbot-syslog
```

Nicht mehr genutzte Images:

```bash
sudo docker image prune
```

<sub>* Der Namensanfang entspricht dem Installationsverzeichnis. Bei `--dir /srv/logbot` also
ebenfalls `logbot-…`. Im Zweifel zeigt `sudo docker images` die Namen.</sub>

**Nur anhalten statt deinstallieren:** `cd /opt/logbot && sudo docker compose stop`,
weiter geht es mit `sudo docker compose start`.

### Linux-Agent

| | `uninstall` | `uninstall-purge` |
|---|---|---|
| Dienst `logbot-agent`, `/opt/logbot-agent`, rsyslog-Weiterleitung | entfernt | entfernt |
| Gerät und seine Logs auf dem Server | **bleiben** | **gelöscht**, dazu alle weiteren Einträge mit diesem Hostnamen |

Nur auf diesem Rechner:

```bash
curl -sSL https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/agents/install-linux.sh | sudo bash -s -- uninstall --yes
```

Inkl. Gerät und Logs auf dem Server:

```bash
curl -sSL https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/agents/install-linux.sh | sudo bash -s -- uninstall-purge --yes
```

Zum Abmelden am Server nimmt `uninstall-purge` Adresse und Token aus der
Agent-Konfiguration. Ein **Syslog-Agent** hat keinen Token, dann beides mitgeben:
`--fqdn logbot.example.com --port 443 --token DEIN-AGENT-TOKEN`.
Ist der Server nicht erreichbar, wird lokal trotzdem entfernt. Das Gerät dann im
Web-UI unter *Geräte* löschen.

### Windows-Agent

PowerShell als Administrator:

Nur auf diesem Rechner:

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/agents/install-windows.ps1))) -Action uninstall -Yes
```

Inkl. Gerät und Logs auf dem Server:

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/agents/install-windows.ps1))) -Action uninstall -PurgeServer -Yes
```

Entfernt werden die geplante Aufgabe `LogBotAgent` und `%ProgramData%\LogBot-Agent`.
Ohne `-Yes` fragt das Skript, ob auch der Server-Eintrag weg soll. Im Menü ist es
Punkt 3.

---

## Updates

In der Oberfläche unter *System → Updates*: prüfen, Release wählen, einspielen,
zurückfallen — mit Sicherung davor und selbsttätigem Rückfall, wenn etwas
schiefgeht. Wer will, bekommt die Meldung über einen neuen Stand in dem Moment,
in dem gepusht wird.

Auf der Kommandozeile reicht ein Einzeiler. **Den aktuellsten Stand
drüberbügeln** — mit Sicherung, Gesundheitsprüfung und Rückfall im Fehlerfall:

```bash
curl -sSL https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/backend/scripts/logbot-update.sh \
  | sudo bash -s -- apply --dir /opt/logbot
```

Dasselbe über den Installer — der zieht dabei auch neue `.env`-Schlüssel nach:

```bash
curl -sSL https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/install.sh \
  | sudo bash -s -- update -y
```

| Ich will … | Befehl |
|---|---|
| ein bestimmtes Release | `sudo bash /opt/logbot/backend/scripts/logbot-update.sh apply --ref v2026.09.10` |
| zurückfallen | `sudo bash /opt/logbot/backend/scripts/logbot-update.sh rollback` |
| wissen, was gerade läuft | `sudo bash /opt/logbot/backend/scripts/logbot-update.sh status` |
| das Protokoll mitlesen | `sudo tail -f /opt/logbot/data/update.log` |
| rohe Gewalt, ohne Netz | `cd /opt/logbot && sudo git fetch --all --tags --prune && sudo git reset --hard origin/main && sudo docker compose build --pull && sudo docker compose up -d --remove-orphans` |

→ Alles dazu — Kanäle, Sofortmeldung, Ablauf, Pfade, Schalter, API,
Fehlersuche: **[Updates](docs/updates/README.md)**

---

## Dokumentation

| | |
|---|---|
| **[Installation](docs/install/README.md)** | Voraussetzungen, Systemprüfung, Zusatzdienste, Hardware-Bedarf |
| **[Betrieb](docs/operate/README.md)** | Tägliche Handgriffe, Menüführung, Sprache, Systemcheck, Terminal |
| **[Updates](docs/updates/README.md)** | Patchmanagement, Release-Auswahl, Sofortmeldung bei neuem Stand |
| **[Sicherung](docs/backup/README.md)** | Sichern, Zurückspielen, Verschlüsselung, Versionsprüfung |
| **[Integrationen](docs/integrations/README.md)** | Webhooks, n8n, KI, Mail, Portainer, Watchtower |
| **[API](docs/api/README.md)** | REST-API, Agent-Ingest, App-Schnittstelle |
| **[Agents](agents/README.md)** | Linux- und Windows-Agent, Einzeiler, Deinstallation |
| **[Changelog](CHANGELOG/README.md)** | Was sich wann geändert hat |

---

## Aufbau

```
Logbot-Server/
├── backend/      FastAPI: API, Auth, Patchmanagement, Sicherung, KI, Mail
├── frontend/     Vue 3: Oberfläche, Sprachen, Design-System
├── syslog/       Syslog-Empfänger (UDP/TCP 514)
├── db/           Schema und Migrationswerkzeuge
├── caddy/        Reverse Proxy und TLS
├── agents/       Installer für Linux und Windows
├── deploy/       Compose-Varianten: extern, gehärtet, Zusatzdienste
├── install/      Systemprüfung vor der Installation
├── n8n/          Fertige Workflows
├── docs/         Diese Dokumentation
├── CHANGELOG/    Änderungen je Bereich
├── setup.sh      Setup-Assistent: Server und Linux-Agent, alle Optionen
└── install.sh    Server-Installer (install, update, uninstall, uninstall-purge)
```

Jedes Verzeichnis hat seine eigene README mit den Einzelheiten.

---

## Voraussetzungen

- Linux (Ubuntu 20.04+ oder vergleichbar), x86_64 oder ARM64
- Docker mit Compose-Plugin *(installiert der Installer bei Bedarf selbst)*
- Root-Zugriff
- 1 GB RAM und 4 GB Platte für LogBot allein — mehr, je nach Zusatzdiensten

Ob die Maschine reicht, sagt die Systemprüfung:

Nur LogBot:

```bash
sudo bash install/preflight.sh
```

Mit Zusatzdiensten:

```bash
sudo bash install/preflight.sh portainer n8n
```

---

## Mitmachen

Fehler und Wünsche gehören in die
[Issues](https://github.com/Phydran6/Logbot-Server/issues).
Wer Code beisteuert: Versionsstand im Datei-Kopf mitziehen und den passenden
Eintrag im [Changelog](CHANGELOG/README.md) ergänzen.

## Lizenz

[MIT](LICENSE)
