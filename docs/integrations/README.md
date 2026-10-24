# Integrationen

Webhooks, KI, Mail und die Zusatzdienste.

← [Übersicht](../../README.md) · [Alle Dokumente](../README.md)

---

## Webhooks

Zugriff auf gefilterte Logs **ohne Anmeldung** — gedacht für Abholdienste wie
n8n, Make oder Zapier.

```
GET /api/webhook/{id}/call?token={token}
```

Einrichten unter *Webhooks → Neuer Webhook*: Filter festlegen (Hostname,
Quelle, Level), Höchstzahl der Ergebnisse, ob die Rohzeilen mitkommen. Die
fertige URL kommt in den HTTP-Request-Knoten.

Gebremst auf 60 Aufrufe pro Minute: Der Endpunkt ist ohne Anmeldung erreichbar
und liefert Logdaten — das reicht für Abholdienste und begrenzt zugleich, was
jemand mit geratenen Tokens anrichten kann.

---

## KI-Auswertung

*Auswertung → KI-Auswertung* — einrichten dürfen nur Administratoren.

Mehrere Wege, keiner davon voreingestellt:

| Weg | Was passiert | Wann sinnvoll |
|-----|--------------|---------------|
| **Aus** | nichts verlässt den Server | Voreinstellung |
| **Claude (Anthropic)** | direkt an die API | „Erklär mir diese 200 Zeilen“ |
| **ChatGPT (OpenAI)** | direkt an die API | dasselbe, anderer Anbieter |
| **OpenRouter** | ein Konto, viele Modelle (Claude, GPT, Gemini, Llama, kostenlose) | Modell frei wählen, per Assistent eingerichtet |
| **Open WebUI** | eigene KI, auch lokal (Ollama) | nichts soll das Haus verlassen |
| **n8n extern** | an einen Webhook außerhalb | wenn n8n schon läuft |
| **n8n als Container** | an das n8n daneben | alles auf einer Maschine |

**Warum alle vier?** n8n kann mehr — Telegram, Ticketsystem, Datenbanken. Es ist
aber ein weiteres System, das laufen und gepflegt werden muss. Wer nur eine
Erklärung zu ein paar Logzeilen will, braucht das nicht.

> **Was den Server verlässt:** Bei jedem Weg außer „Aus“ gehen die
> **ausgewählten Logzeilen** an den eingestellten Empfänger. Das steht auch so
> in der Oberfläche. Der Knopf *Vorschau* zeigt vorher genau, was gesendet
> würde — Zeichenzahl, geschätzte Token und die ersten Zeilen im Klartext.

### OpenRouter-Assistent

1. Weg **OpenRouter** wählen, *Mit OpenRouter anmelden* klicken.
2. Bei OpenRouter anmelden und zustimmen. OpenRouter legt dabei einen Schlüssel
   **nur für LogBot** an (jederzeit unter openrouter.ai widerrufbar) und schickt
   den Browser zurück. Das Geheimnis des Ablaufs (PKCE) verlässt den Server nie.
3. Modell wählen – die Liste kommt live von OpenRouter, mit Preisen und
   Kontextlänge; „nur kostenlose“ filtert die Gratis-Modelle.

Alternativ *Schlüssel selbst einfügen* (sk-or-…). Kostenlose Modelle haben enge
Tageslimits und dürfen Anfragen u. U. für Training nutzen – für Logdaten
besser ein bezahltes Modell.

### Einrichten (andere Wege)

1. Weg wählen.
2. API-Schlüssel bzw. Webhook-Adresse eintragen. Der Schlüssel wird **nie**
   zurückgegeben — die Oberfläche zeigt nur, *dass* einer hinterlegt ist. Ein
   leeres Feld beim Speichern heißt „unverändert lassen“.
3. Höchstzahl der Zeilen festlegen (Standard 100, Maximum 500). Ohne Grenze
   schickt ein unbedachter Klick den halben Logbestand ins Internet — und die
   Rechnung kommt später.
4. *Verbindung testen* — läuft mit einer **erfundenen** Logzeile, nicht mit
   echten Daten.
5. Optional für alle angemeldeten Benutzer freigeben. Standardmäßig dürfen nur
   Administratoren fragen.

### Was gesendet wird

Nicht die Rohzeilen, sondern die **zerlegte** Fassung: Zeitstempel, Host, Level,
Quelle, die lesbare Zusammenfassung und die erkannten Felder. Eine
Firewall-Zeile mit dreißig `key=value`-Paaren kostet sonst mehr Zeichen, als sie
an Erkenntnis bringt. Rohzeilen kommen nur mit, wenn man es anhakt.

### Fertiger n8n-Workflow

Unter [`n8n/`](../../n8n/README.md) liegt ein Telegram-Bot, der Logs vom
Webhook holt, von Claude auswerten lässt und die Antwort in den Chat schickt.

---

## Meldungen: E-Mail, Telegram, App

*Meldungen → Kanäle* — nur für Administratoren. Welche Ereignisse wohin gehen,
steht unter *Meldungen → Regeln* (siehe [Betrieb](../operate/README.md#meldungen)).

### E-Mail

Der Assistent kennt fünf Wege:

| Weg | Wie |
|---|---|
| **Google** | *App-Passwort* (zwei Felder: Adresse + 16-stelliges App-Passwort, braucht die Bestätigung in zwei Schritten) **oder** *Mit Google anmelden* (OAuth, Gmail-API; eigener OAuth-Client vom Typ „Desktop-App“ in der Google Cloud Console – der Assistent verlinkt jeden Schritt). |
| **Microsoft 365** | Der Assistent **legt die App-Registrierung selbst an**: einmal mit einem Konto anmelden, das Anwendungen registrieren darf (Globaler Administrator, Anwendungs- oder Cloudanwendungsadministrator) – per Gerätecode oder im Browser. LogBot erzeugt „LogBot Mail (…)“ im Mandanten, nur mit der delegierten Berechtigung `Mail.Send`, und erteilt die Administratorzustimmung. Danach mit dem Postfach anmelden, von dem die Mails kommen. Gesendet wird über Microsoft Graph. |
| **Outlook.com** | Wie Microsoft 365, die App wird dabei für private Konten freigegeben (dafür braucht es einmalig irgendeinen Entra-Mandanten mit Admin-Recht) – oder eine vorhandene App-Registrierung eintragen. |
| **Anderer Anbieter** | SMTP mit Vorlagen für GMX, WEB.DE, IONOS, Strato, T-Online, Posteo, mailbox.org, iCloud, Yahoo – oder ein eigener Mailserver. |
| **Eigener Postfix** | LogBots Mailserver (Zusatzdienst `postfix`), optional mit Smarthost. Die Konfiguration entsteht im Browser und landet in `data/postfix/settings.env`. |

Für die Microsoft-App-Registrierung meldet sich LogBot über Microsofts eigenes
Werkzeug *Microsoft Graph Command Line Tools* an – dieselbe Anwendung, die
`Connect-MgGraph` in PowerShell benutzt. Der Admin-Zugang wird nur für diesen
einen Schritt gebraucht und nirgends gespeichert.

Der einfachste Weg ist der **Gerätecode**: Code eingeben, der Assistent macht
von selbst weiter. Beim **Browser-Weg** kommt der Browser nicht immer von selbst
zurück – bei der App-Registrierung nie (Microsofts Werkzeug kennt nur
`http://localhost` als Rücksprung), sonst wenn LogBot keine öffentliche
HTTPS-Adresse hat. Der Assistent zeigt dann drei Schritte: Anmeldeseite per Knopf
öffnen, anmelden und zustimmen; der Tab landet auf `http://localhost/?code=…` bzw.
`http://127.0.0.1:53682/?code=…` und zeigt eine Fehlerseite – **das ist
richtig**; die komplette Adresse aus der Adresszeile kopieren und im Assistenten
einfügen (er schließt sofort ab). Der Code gilt nur wenige Minuten; ist er
abgelaufen, den Schritt einfach neu starten. Ohne den Assistenten, der die
Anmeldung begonnen hat, ist der Code wertlos (PKCE).

Alle Zugangsdaten (SMTP-Passwörter, Refresh-Token, Client-Geheimnisse) liegen
**verschlüsselt** in der Datenbank (Schlüssel aus `JWT_SECRET`) und kommen nie
zurück in den Browser. Microsoft-Anmeldungen werden täglich erneuert, damit sie
nicht aus Untätigkeit verfallen; scheitert das, steht es als Meldung im Eingang.

**Öffentliche Adresse:** Links in Mails (Passwort-Reset, App-Anmeldung,
Meldungen) zeigen auf die Adresse, die oben im Assistenten steht – bewusst fest
eingestellt und nie aus der Anfrage gelesen (sonst ließen sich Links auf fremde
Seiten in echte Mails schmuggeln).

### Telegram

1. In Telegram [@BotFather](https://t.me/BotFather) öffnen, `/newbot`, Namen
   vergeben, den Token einfügen. LogBot prüft ihn sofort.
2. *Verbindungslink erzeugen* – Link öffnen oder den QR-Code am Handy scannen
   und auf **Starten** tippen. LogBot erkennt den Chat von selbst und schickt
   eine Bestätigung. Gruppen: Bot aufnehmen und `/start@<bot> <code>` senden.
3. Testnachricht.

Der Token liegt verschlüsselt in der Datenbank. Ab Werk gehen nach Telegram
nur die wirklich kritischen Logzeilen und Fehler von LogBot selbst.

### App & Push

Jede Meldung steht im Eingang der App (`/api/app/notifications`). Für Push
meldet sich die App mit ihrem UnifiedPush-Verteiler an (z. B. ntfy) – ohne
Google-Konto. Der Inhalt ist nach RFC 8291 verschlüsselt und nach RFC 8292
(VAPID) unterschrieben; er enthält nur Schweregrad und Überschrift.

---

## Portainer

Container-Oberfläche im Browser: Zustände, Protokolle, Konsole.

Standardmäßig nur vom Server selbst erreichbar (`127.0.0.1:9000`). Wer aus dem
Netz herankommen will, setzt `PORTAINER_BIND=0.0.0.0` — und sollte vorher HTTPS
einrichten.

Zugangsdaten: *System → Zusatzdienste → Zugangsdaten anzeigen*. Dort lässt sich
auch ein neues Passwort setzen.

> Portainer spricht Docker **nur über einen Filter** (`socket-proxy`), der
> ausschließlich lesende Abfragen durchlässt. Die Oberfläche zeigt damit alles
> an, kann aber nichts starten, stoppen oder löschen.
>
> **Korrektur:** Bis 2026.10.08 stand hier, ein mit `:ro` eingehängter Socket
> sei „nur lesend“. Das stimmte nicht – `:ro` schützt nur die Datei, nicht die
> Befehle, die man darüber schickt. Der Filter ist die echte Sperre.

---

## Tugtainer (löst Watchtower ab)

Sieht nach, ob für die **fremden** Images Updates bereitliegen — und meldet sie.
Mehr nicht.

**Warum Watchtower raus ist:** Es hat Images geholt *und* Container
eigenmächtig ausgetauscht. Nachts, ohne Ansage, und hinterher war schwer
zuzuordnen, warum ein Dienst plötzlich anders lief. Auf einem Log-Server, der
Nachvollziehbarkeit verspricht, ist das der falsche Mechanismus.

Tugtainer spricht Docker deshalb nur über den **lesenden Filter**
(`socket-proxy`): es *kann* gar nichts austauschen, selbst wenn jemand die
Automatik einschaltet. Eingespielt
wird bewusst — in LogBots Oberfläche unter *System → Container*, in Tugtainers
eigener Oberfläche oder auf der Kommandozeile.

**Zum Zusammenspiel mit dem Patchmanagement:** LogBots eigene Container
(`logbot-app-*`) werden aus dem Quellcode gebaut, es gibt für sie gar kein
Image in einer Registry. Tugtainer kann dort also nichts finden; zuständig ist
*System → Updates*. Tugtainer kümmert sich um die fertigen Images:
PostgreSQL, Caddy, n8n, Portainer, Open WebUI, Postfix.

Oberfläche unter `127.0.0.1:9412`. Wer Tugtainer doch selbst austauschen
lassen will, hängt in einer eigenen `docker-compose.override.yml` den echten
Socket ein und setzt in der `.env`:

```
TUGTAINER_DOCKER_HOST=unix:///var/run/docker.sock
```

> LogBot prüft Image-Updates auch **ohne** Tugtainer: *System → Container →
> Auf Updates prüfen* fragt die Registry direkt nach dem Abdruck des benutzten
> Tags. Tugtainer bringt Zeitplan, eigene Oberfläche und mehrere Hosts dazu.

---

## Open WebUI

KI-Oberfläche, die dieselbe Schnittstelle spricht wie OpenAI — dahinter aber
das Modell hat, das man selbst wählt.

**Warum das interessant ist:** Mit einem lokalen Modell über Ollama verlässt
bei der KI-Auswertung **keine einzige Logzeile den Server**. Für Logdaten, in
denen Benutzernamen, interne Adressen und Fehlermeldungen stehen, ist das oft
der Unterschied zwischen „geht“ und „geht nicht“.

Ollama selbst ist bewusst **nicht** Teil dieses Stacks: Ein Sprachmodell will
mehrere Gigabyte Arbeitsspeicher und möglichst eine Grafikkarte, und das gehört
nicht nebenbei auf einen Log-Server. In die `.env` kommt die Adresse einer
vorhandenen Installation:

```
OLLAMA_BASE_URL=http://192.168.1.50:11434
```

Einzurichten unter *Auswertung → KI-Auswertung*, Anbieter **Open WebUI**. Es
braucht die Adresse (intern: `http://logbot-openwebui:8080`) und einen
API-Schlüssel aus Open WebUI (dort unter *Profil → Einstellungen → Konto*).
Der Knopf „Modelle holen“ liest die verfügbaren Modelle aus, damit der Name
nicht geraten werden muss.

---

## n8n als Container

Läuft neben LogBot, erreichbar unter `127.0.0.1:5678`. Anmeldung ist Pflicht —
ohne stünde die Oberfläche offen, und mit ihr jeder hinterlegte Zugang zu
Telegram, Mail oder KI-Anbietern.

Zugangsdaten wie bei Portainer unter *System → Zusatzdienste*.

Für die KI-Auswertung ist die interne Adresse
`http://logbot-n8n:5678/webhook/logbot` einzutragen — dann bleiben die Daten im
Docker-Netz, solange der Workflow sie nicht weitergibt.

---

## Weiter

- [API](../api/README.md)
- [Installation → Zusatzdienste](../install/README.md#zusatzdienste)
- [n8n-Workflows](../../n8n/README.md)
