# Agents

Kleine Dienste, die Logs von einem Rechner an den LogBot-Server schicken.
Für **Linux** und **Windows**, jeweils als Einzeiler installierbar.

← [Zurück zur Übersicht](../README.md) · [Alle Dokumente](../docs/README.md)

---

## Zwei Betriebsarten

|                     | **Agent-basiert (HTTPS)** — Standard        | **Syslog (UDP/TCP)**              |
|---------------------|---------------------------------------------|-----------------------------------|
| Transport           | HTTPS an `/api/agents/ingest`               | Port 514                          |
| Verschlüsselt       | ja                                           | nein                              |
| Anmeldung           | Agent-Token (Bearer)                         | keine                             |
| Über das Internet   | **ja** — dafür ist er gedacht                | nein, nur im eigenen Netz         |
| Adressierung        | FQDN (DNS), IP als Rückfallebene             | FQDN oder IP                      |
| Braucht auf Linux   | python3 + systemd + journald                 | rsyslog                           |

**Kurz:** Rechner im eigenen Netz können Syslog sprechen. Alles, was **nicht im
gleichen Netz** hängt, geht agent-basiert — nur dort sind die Daten unterwegs
verschlüsselt und der Absender nachweisbar.

Beide Wege funktionieren mit einem **FQDN**. Beim HTTPS-Modus ist er faktisch
Pflicht: ein Zertifikat lautet auf einen Namen, nicht auf eine IP.

---

## Linux — Einzeiler

**Voll automatisch** (FQDN und Token mitgeben, nichts wird gefragt):

```bash
curl -sSL https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/agents/install-linux.sh \
  | sudo bash -s -- --fqdn logbot.example.com --token DEIN-AGENT-TOKEN --yes
```

**Mit Rückfragen** (5 s Countdown; eine Taste drücken schaltet auf manuell):

```bash
curl -sSL https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/agents/install-linux.sh | sudo bash
```

**Syslog statt HTTPS:**

```bash
curl -sSL https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/agents/install-linux.sh \
  | sudo bash -s -- --mode syslog --fqdn logbot.example.com --port 514 --yes
```

| Aktion | Befehl |
|--------|--------|
| Testnachrichten senden | `sudo bash install-linux.sh test` |
| Deinstallieren | → [Einzeiler zum Deinstallieren](#deinstallieren--einzeiler) |

**Optionen:** `--fqdn` · `--token` · `--ip` · `--port` · `--mode https\|syslog` ·
`--proto udp\|tcp` *(Syslog)* · `--min-level info\|warning\|error` · `--insecure` · `--yes` · `--timeout <s>`
(alle auch als `LOGBOT_*`-Umgebungsvariable).

Alles liegt unter `/opt/logbot-agent/`, der Dienst heißt `logbot-agent`:

```bash
systemctl status logbot-agent
journalctl -u logbot-agent -f
```

---

## Windows — Einzeiler

PowerShell **als Administrator**:

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/agents/install-windows.ps1))) -Action install -Fqdn logbot.example.com -Token DEIN-AGENT-TOKEN -Yes
```

> **Warum diese Schreibweise und nicht `irm … | iex`?**
> Eine Pipeline reicht nur Text weiter — Parameter kommen dabei nicht an.
> `[scriptblock]::Create` macht aus dem geholten Text einen echten Skriptblock,
> und der nimmt Parameter entgegen wie eine Funktion.

**Ohne Parameter** erscheint das gewohnte Menü:

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/agents/install-windows.ps1)))
```

| Aktion | Befehl |
|--------|--------|
| Testnachrichten | `-Action test` |
| Deinstallieren | → [Einzeiler zum Deinstallieren](#deinstallieren--einzeiler) |

**Parameter:** `-Action install\|test\|uninstall` · `-Fqdn` · `-ServerIP` ·
`-ServerPort` · `-Token` · `-Mode https\|syslog` · `-MinLevel` · `-Insecure` ·
`-Yes` · `-PurgeServer`

Installation unter `%ProgramData%\LogBot-Agent`, Ausführung als geplante Aufgabe
`LogBotAgent` unter `SYSTEM`:

```powershell
Get-ScheduledTask -TaskName LogBotAgent
```

### MSI-Paket?

Noch nicht dabei. Der PowerShell-Einzeiler deckt dasselbe ab und lässt sich per
GPO, Intune oder Softwareverteilung ausrollen — ohne Signaturkette und ohne
Paketpflege bei jeder Version. Für eine unbeaufsichtigte Verteilung genügt:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& ([scriptblock]::Create((irm <URL>))) -Action install -Fqdn logbot.example.com -Token XXX -Yes"
```

---

## Agent-Token

Im Web-UI unter **Einstellungen → Agent-Token**. Ein Token gilt für beliebig
viele Rechner; wer sie trennen will, legt mehrere an. Ein zurückgezogener Token
sperrt sofort alle Agents, die ihn benutzen.

---

## Deinstallieren — Einzeiler

Einfach kopieren und auf dem Rechner ausführen, von dem der Agent weg soll.
Keine Rückfragen, Adresse und Token nimmt der Agent aus seiner eigenen Konfiguration.

### Linux

```bash
# Komplett: Agent weg + Gerät und Logs auf dem Server gelöscht
curl -sSL https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/agents/install-linux.sh | sudo bash -s -- uninstall-purge --yes

# Nur hier: Agent weg, Gerät und Logs bleiben auf dem Server
curl -sSL https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/agents/install-linux.sh | sudo bash -s -- uninstall --yes
```

### Windows (PowerShell als Administrator)

```powershell
# Komplett: Agent weg + Gerät und Logs auf dem Server gelöscht
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/agents/install-windows.ps1))) -Action uninstall -PurgeServer -Yes

# Nur hier: Agent weg, Gerät und Logs bleiben auf dem Server
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/Phydran6/Logbot-Server/main/agents/install-windows.ps1))) -Action uninstall -Yes
```

### Was wird entfernt?

| | Komplett | Nur hier |
|---|---|---|
| Dienst bzw. geplante Aufgabe, Agent-Verzeichnis, Konfiguration mit Token | ✔ | ✔ |
| Gerät auf dem Server, **auch ältere Einträge mit demselben Hostnamen** | ✔ | – |
| Logs dieses Geräts auf dem Server | ✔ | – |

**Gut zu wissen**

- **Server nicht erreichbar?** Der Agent wird trotzdem lokal entfernt (nach höchstens 20 s).
  Das Gerät dann im Web-UI unter *Geräte* von Hand löschen.
- **Syslog-Agent (Linux):** Er hat keinen Token. Für „komplett“ deshalb Adresse und
  Token mitgeben: `… uninstall-purge --fqdn logbot.example.com --port 443 --token DEIN-AGENT-TOKEN --yes`
- **Lieber mit Menü?** Unter Linux den [Setup-Assistenten](../README.md#schnellstart)
  nehmen (Punkt 7/8). Unter Windows den Einzeiler ohne Parameter starten (Punkt 3).

<details>
<summary>Wie findet der Server das richtige Gerät?</summary>

Der Agent merkt sich beim ersten Senden seine Gerätenummer
(`/opt/logbot-agent/agent_id` bzw. `%ProgramData%\LogBot-Agent\agent_id`) und nennt
sie beim Abmelden. Fehlt sie, sucht der Server nach MAC, dann Hostname + IP, dann
Hostname allein. Welcher Weg gegriffen hat, steht in der Antwort (`matched_by`).
</details>

---

## Fehlersuche

| Symptom | Ursache und Abhilfe |
|---------|---------------------|
| Installer bleibt stehen | Behoben: Rückfragen haben jetzt ein Zeitlimit (60 s, `LOGBOT_ASK_TIMEOUT`), ohne Terminal wird gar nicht gefragt. `--yes` überspringt alles. |
| Deinstallation hängt | Behoben: `systemctl stop` bekommt 20 s, dann wird der Dienst abgeschossen; der Server-Aufruf hat 20 s Zeitlimit. |
| `HTTP 401` beim Senden | Token stimmt nicht oder wurde zurückgezogen. Im Web-UI neu holen. |
| Keine Logs, Dienst läuft | `journalctl -u logbot-agent -f` ansehen. Meist DNS oder eine Firewall auf 443. |
| Zertifikat wird abgelehnt | Bei eigener CA: `--insecure` bzw. `-Insecure`. Besser: die CA auf dem Rechner bekannt machen. |
| Gerät steht doppelt im Web-UI | Der Rechner hat die IP gewechselt. Einmal `uninstall-purge` räumt alle Einträge des Hostnamens ab. |

---

## Verwandte Dokumente

- [Installation des Servers](../docs/install/README.md)
- [API und Ingest](../docs/api/README.md)
- [Änderungen an den Agents](../CHANGELOG/agents.md)
