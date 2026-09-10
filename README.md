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

```bash
curl -sSL https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/install.sh | sudo bash
```

Der Installer prüft zuerst, ob das System passt, fragt dann, was mitinstalliert
werden soll, und rechnet die Anforderungen gegen die Maschine. Nach ein paar
Minuten:

- **Oberfläche:** `http://SERVER-IP` — Anmeldung `admin` / `admin`
  *(bitte sofort ändern; HTTPS danach unter Einstellungen → Netzwerk einschalten)*
- **API-Doku:** `http://SERVER-IP/api/docs`
- **Syslog:** Port 514 (UDP/TCP)

Ohne jede Rückfrage, mit Zusatzdiensten:

```bash
curl -sSL https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/install.sh \
  | sudo bash -s -- --with portainer,watchtower --yes
```

→ Ausführlich: **[Installation](docs/install/README.md)**

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
└── CHANGELOG/    Änderungen je Bereich
```

Jedes Verzeichnis hat seine eigene README mit den Einzelheiten.

---

## Voraussetzungen

- Linux (Ubuntu 20.04+ oder vergleichbar), x86_64 oder ARM64
- Docker mit Compose-Plugin *(installiert der Installer bei Bedarf selbst)*
- Root-Zugriff
- 1 GB RAM und 4 GB Platte für LogBot allein — mehr, je nach Zusatzdiensten

Ob die Maschine reicht, sagt die Systemprüfung:

```bash
sudo bash install/preflight.sh              # nur LogBot
sudo bash install/preflight.sh portainer n8n  # mit Zusatzdiensten
```

---

## Mitmachen

Fehler und Wünsche gehören in die
[Issues](https://github.com/Phydran6/Logbot-Server/issues).
Wer Code beisteuert: Versionsstand im Datei-Kopf mitziehen und den passenden
Eintrag im [Changelog](CHANGELOG/README.md) ergänzen.

## Lizenz

[MIT](LICENSE)
