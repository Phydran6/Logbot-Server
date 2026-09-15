# Installation

← [Übersicht](../../README.md) · [Alle Dokumente](../README.md)

---

## Der kurze Weg

```bash
curl -sSL https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/install.sh | sudo bash
```

Der Installer läuft in dieser Reihenfolge:

1. **5 Sekunden Countdown.** Eine Taste drücken → Rückfragen werden gestellt.
   Nichts drücken → alles läuft mit Standardwerten durch.
2. **Auswahl:** LogBot allein oder mit Zusatzdiensten.
3. **Systemprüfung** gegen genau diese Auswahl.
4. **Docker** wird geholt, falls er fehlt.
5. **Bauen und starten.**

Ohne jede Rückfrage:

```bash
curl -sSL … /install.sh | sudo bash -s -- --yes
```

Mit Zusatzdiensten, unbeaufsichtigt:

```bash
curl -sSL … /install.sh | sudo bash -s -- --with portainer,watchtower --yes
```

Aus einem geklonten Repository:

```bash
git clone https://github.com/Phydran6/Logbot-Server.git
cd Logbot-Server
sudo bash install.sh
```

---

## Systemprüfung

Läuft von selbst mit — und auch allein:

```bash
sudo bash install/preflight.sh                      # nur LogBot
sudo bash install/preflight.sh portainer n8n        # mit Zusatzdiensten
sudo bash install/preflight.sh all                  # alles

curl -sSL …/install/preflight.sh | sudo bash        # ohne Repository
```

Geprüft werden Architektur, Kernel, Betriebssystem, Rechte, RAM, Platte,
Prozessorkerne, Docker samt Compose, belegte Ports, DNS, GitHub-Erreichbarkeit
und ob die Uhr per NTP gestellt wird.

Die Antwort ist bewusst dreistufig:

| Rückgabe | Bedeutung | Folge |
|----------|-----------|-------|
| `0` | passt | läuft durch |
| `2` | wird knapp | Rückfrage, dann weiter |
| `1` | geht nicht | Abbruch (übergehbar) |

**Warum nicht einfach ja/nein?** Ein kleiner Server trägt LogBot problemlos —
nur eben nicht mit Portainer, n8n und Postfix obendrauf. Das gehört gesagt,
nicht verboten. Ein harter Ausschluss ist nur, was wirklich nicht geht: 32-Bit
ARM, fehlendes Compose-Plugin, zu wenig Speicher für PostgreSQL.

Übergehen (auf eigene Verantwortung): `--skip-preflight`.

---

## Hardware-Bedarf

| Baustein | RAM | Platte |
|----------|----:|-------:|
| **LogBot** (Postgres, Backend, Frontend, Caddy, Syslog) | 1024 MB | 4096 MB |
| Portainer | 256 MB | 400 MB |
| Watchtower | 128 MB | 150 MB |
| n8n | 768 MB | 1200 MB |
| Postfix | 128 MB | 200 MB |

Untergrenze: 768 MB RAM und 2 GB Platte — darunter startet PostgreSQL nicht
zuverlässig. Ab zwei Zusatzdiensten sind zwei Prozessorkerne empfohlen.

Die Werte für die Platte sind der **Grundbedarf**. Logs kommen dazu: Als
Faustzahl braucht eine Million Logzeilen rund 300–500 MB. LogBot räumt ab 80 %
Belegung selbst auf (siehe [Betrieb](../operate/README.md#platte-läuft-voll)).

---

## Zusatzdienste

Vier Dienste stehen bereit. Keiner läuft, bevor er ausgewählt wird.

| Dienst | Wofür | Achtung |
|--------|-------|---------|
| **Portainer** | Container im Browser ansehen und verwalten | braucht den Docker-Socket (lesend) |
| **Watchtower** | hält die Images der Zusatzdienste aktuell | braucht den Docker-Socket (schreibend) |
| **n8n** | Automatisierung, u. a. für die KI-Auswertung | eigene Oberfläche, eigene Anmeldung |
| **Postfix** | Mailversand vom Server | konfiguriert wird er später im Web-UI |

Bei der Installation:

```bash
sudo bash install.sh --with portainer,watchtower
sudo bash install.sh --no-addons        # ausdrücklich ohne
```

Nachträglich jederzeit im Web-UI unter **System → Zusatzdienste** —
ein Schalter je Dienst, mit Sicherungsfrage davor.

> **Zum Docker-Socket, offen gesagt:** Wer darauf schreiben kann, ist faktisch
> root auf diesem Server. Genau deshalb liegen diese Dienste hinter einem
> Profil, das man bewusst einschaltet, und nicht im Standard-Stack. Portainer
> bekommt den Socket nur lesend — die Oberfläche zeigt dann alles, kann aber
> nichts starten oder löschen. Wer auch verwalten will, nimmt das `:ro` in
> [`deploy/optional.yml`](../../deploy/optional.yml) heraus.

### Zugangsdaten

Der Installer würfelt sie aus und legt sie in der `.env` ab. Einsehbar sind sie
jederzeit im Web-UI unter **System → Zusatzdienste** — für Administratoren, auf
Klick. Genau dafür ist das gedacht: Ein Passwort, das man nur einmal beim
Installieren sieht, ist zwei Wochen später verloren.

---

## Aktionen des Installers

| Aktion | Wirkung |
|--------|---------|
| `install` *(Standard)* | Installiert; eine vorhandene Installation wird auf Wunsch aktualisiert |
| `update` | Holt den neuen Stand und startet neu gebaute Container |
| `uninstall` | Stoppt und entfernt die Container — **Daten bleiben** |
| `uninstall-purge` | Löscht zusätzlich Volumes, **alle Logs** und `/opt/logbot` |

**Optionen:** `--dir` · `--repo` · `--branch` · `--with` · `--no-addons` ·
`--skip-preflight` · `--no-build` · `--yes` · `--timeout`
(alle auch als `LOGBOT_*`-Umgebungsvariable).

Eine vorhandene `.env` wird **nie** überschrieben — sonst passte das
Datenbank-Passwort nicht mehr zum bestehenden PostgreSQL-Volume.

---

## Andere Betriebsarten

Die Compose-Varianten liegen in [`deploy/`](../../deploy/README.md):

```bash
# Externe Datenbank
docker compose -f docker-compose.yml -f deploy/external-db.yml up -d

# Ohne erweiterte Container-Rechte
docker compose -f docker-compose.yml -f deploy/hardened.yml up -d

# Mit Zusatzdiensten
docker compose -f docker-compose.yml -f deploy/optional.yml --profile portainer up -d
```

Damit man das nicht jedes Mal tippt, in die `.env`:

```
COMPOSE_FILE=docker-compose.yml:deploy/optional.yml
COMPOSE_PROFILES=portainer,watchtower
```

> **Zur gehärteten Variante:** Sie nimmt dem Backend `privileged`, `pid: host`
> und `SYS_BOOT`. LogBot läuft normal weiter — es entfallen aber der
> Neustart-Knopf, das Update über die Oberfläche, das Terminal und die
> Zusatzdienst-Schalter. Der Systemcheck sagt das ausdrücklich an.

---

## Nach der Installation

1. **Passwort ändern** — `admin`/`admin` ist nur der Einstieg.
2. **HTTPS einschalten** — Einstellungen → Netzwerk → Reverse Proxy.
   Let's Encrypt, eigenes Zertifikat oder selbstsigniert.
3. **Systemcheck laufen lassen** — System → Systemzustand.
4. **Agent-Token holen** — Einstellungen → Agent-Token, dann
   [Rechner anbinden](../../agents/README.md).
5. **Sicherung einrichten** — [System → Sicherung](../backup/README.md).

---

## Wenn etwas klemmt

| Symptom | Ursache |
|---------|---------|
| `DB_PASSWORD muss gesetzt sein` | `.env` fehlt oder ist leer. `install.sh` erneut laufen lassen. |
| Backend startet nicht, alles 502 | `docker compose logs backend` ansehen. Meist die Datenbank. |
| Port 80 belegt | Ein anderer Webserver läuft. Die Systemprüfung sagt das vorher. |
| PostgreSQL startet nicht nach Update | Major-Upgrade nötig — siehe [Datenbank](../../db/README.md). |
| Zusatzdienst startet nicht | `docker compose logs <name>`, oder im Web-UI unter System → Zusatzdienste das Protokoll ansehen. |

---

## Weiter

- [Betrieb](../operate/README.md) — der Alltag danach
- [Updates](../updates/README.md) — aktuell bleiben
- [Sicherung](../backup/README.md) — bevor etwas schiefgeht
