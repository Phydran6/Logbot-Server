# API

Die vollständige, immer aktuelle Referenz steht am laufenden Server:
**`http://SERVER-IP/api/docs`** (OpenAPI/Swagger).

Hier steht das, was man vorher wissen will.

← [Übersicht](../../README.md) · [Alle Dokumente](../README.md)

---

## Anmeldung

```bash
curl -X POST https://logbot.example.com/api/auth/login \
  -F "username=admin" -F "password=geheim"
```

`username` nimmt den Benutzernamen **oder die E-Mail-Adresse**.

Antwort: `{"access_token": "…", "token_type": "bearer"}` — oder bei aktivem MFA
`{"mfa_required": true, "mfa_token": "…"}`, dann Schritt zwei über
`POST /api/auth/login/mfa`.

Danach überall:

```
Authorization: Bearer <access_token>
```

**Ausnahmen von der Kopfzeile:** Ereignisstrom (`EventSource`), Terminal
(`WebSocket`) und Download-Links können keine Kopfzeilen mitschicken. Dafür
holt man vorher ein **Ticket** – 60 Sekunden gültig, nur einmal benutzbar, nur
für den genannten Zweck – und hängt es als `?ticket=` an:

```bash
curl -X POST https://logbot.example.com/api/auth/ticket \
  -H "Authorization: Bearer <access_token>" -H "Content-Type: application/json" \
  -d '{"purpose": "stream"}'
```

Zwecke: `stream`, `shell`, `download`. Der frühere Weg `?token=<access_token>`
wird übergangsweise noch angenommen, landet aber im Zugriffsprotokoll – nicht
mehr benutzen.

**Sitzungen:** Passwortwechsel, Deaktivierung und Rollenwechsel beenden alle
Sitzungen eines Kontos sofort; `POST /api/auth/logout-all` tut das von Hand.

### Konto

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/api/auth/account` | Was fehlt noch? (`needs_email`, `email_verified`, `must_change_password`, `mail_ready`) |
| POST | `/api/auth/email` | Adresse setzen, Bestätigungscode anfordern (`{email, current_password?}`) |
| POST | `/api/auth/email/verify` | `{code}` – sechsstellig aus der Mail |
| POST | `/api/auth/email/resend` | Code erneut senden |
| POST | `/api/auth/password/change` | `{current_password, new_password}` → neues Token |
| POST | `/api/auth/password/forgot` | `{login}` – Benutzername oder Adresse; antwortet **immer** 202 |
| POST | `/api/auth/password/reset` | `{token, new_password}` – Token aus dem Mail-Link |
| POST | `/api/auth/magic-link/request` | Anmelde-Link für die App per Mail (PKCE) |

---

## Logs von Agents annehmen

```
POST /api/agents/ingest
Authorization: Bearer <AGENT-TOKEN>
```

```json
{
  "hostname": "srv01",
  "ip_address": "10.0.0.5",
  "device_type": "linux_agent",
  "events": [
    {
      "message": "sshd: Accepted publickey for alice",
      "level": "info",
      "source": "sshd",
      "timestamp": "2026-09-09T12:00:00Z",
      "facility": 4
    }
  ]
}
```

Antwort:

```json
{ "accepted": 1, "duplicates": 0, "message": "ok", "agent_id": 42 }
```

**Bereit für Agents über HTTPS — was dafür da ist:**

| Punkt | Umsetzung |
|-------|-----------|
| Verschlüsselung | TLS über Caddy: Let's Encrypt, eigenes Zertifikat oder interne CA |
| Anmeldung | Agent-Token (Bearer), mehrere möglich, einzeln zurückziehbar |
| Paketgröße | bis 5000 Ereignisse je Aufruf |
| Doppelte Lieferungen | Einträge mit eigenem Zeitstempel bekommen einen `dedup_key` (SHA-256 aus Host, Zeit, Ereignis-ID und Text); Wiederholungen verwirft die Datenbank per `ON CONFLICT DO NOTHING` |
| Fremde Geräte melden | Sammler dürfen `hostname`, `ip_address` und `device_type` des **gemeldeten** Geräts mitschicken — dann erscheint es mit eigener Identität, nicht unter der IP des Sammlers |
| Zuordnung | `agent_id` in der Antwort: der Agent merkt sie sich und räumt beim Deinstallieren genau seinen Eintrag ab |
| Kompression | GZip ab 1 KB Antwortgröße |
| Zeitzonen | Zeitstempel mit Zone werden nach UTC gerechnet |

**Was fehlt:** eine Bremse speziell für den Ingest. Der globale Rate-Limiter
greift, ein eigenes Kontingent pro Token gibt es nicht. Bei vielen Agents
gehört vor den Server ohnehin ein Reverse Proxy — Caddy ist dabei.

---

## Heartbeat, Container und Agent-Updates

```
POST /api/agents/heartbeat
Authorization: Bearer <AGENT-TOKEN>
```

```json
{
  "hostname": "docker01", "device_type": "linux_agent",
  "agent_version": "2026.10.23.12.00.00",
  "capabilities": ["heartbeat", "self-update", "docker", "signed-update"],
  "docker": {"installed": true, "engine": "27.3.1", "compose": "2.29.7"},
  "containers": [{"name": "nextcloud-app-1", "image": "nextcloud:29", "state": "running",
                  "compose_project": "nextcloud", "compose_service": "app"}]
}
```

Antwort: `{"agent_id": 12, "update": null | {"action": "update", "version", "sha256",
"signature", "url"}, "config": {...}}`. Die Container werden Kind-Instanzen der
VM (`docker01/nextcloud-app-1`).

Container-Logs gehen über den normalen Ingest, je Eintrag mit `"container":
"<name>"` und `"stream": "stdout|stderr|event"`.

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/api/agents/tree` | Geräte als Baum (VM → Compose-Projekt → Container) |
| GET | `/api/agents/update/pubkey` | öffentlicher Schlüssel für die Paket-Unterschrift (PEM, XML, Fingerabdruck) |
| GET | `/api/agents/update/package/{linux\|windows}` | Paket (Agent-Schlüssel nötig), Kopfzeilen `X-LogBot-Version/SHA256/Signature` |
| POST | `/api/agents/update/report` | Agent meldet `downloading/installing/done/failed/rolled_back` |
| GET/PUT | `/api/agents/updates`, `/api/agents/updates/config` | Stand und Regel (Admin) |
| POST | `/api/agents/updates/request` | `{agent_ids}` oder `{all_outdated: true}` (Admin) |
| GET/PUT | `/api/agents/defaults` | Vorgaben: Aufbewahrung, Drossel (Admin) |

Unterschrift: RSA-3072, PKCS#1 v1.5, SHA-256 über die Bytes des Pakets.

---

## Meldungen

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/api/notifications` | Eingang (`before_id`, `since_id`, `severity`, `only_unread`) |
| GET | `/api/notifications/unread` | Zahl der ungelesenen |
| POST | `/api/notifications/read` | `{up_to_id}` |
| GET | `/api/notifications/config` | Regeln und Stand der Kanäle (Admin) |
| PUT | `/api/notifications/rules` | Regeln speichern (Admin) |
| POST | `/api/notifications/test` | Testmeldung über `{channels}` (Admin) |

**App:** `GET /api/app/notifications` (Cursor wie bei den Logs, `unread_count`,
`has_more`, `next_before_id`, `newest_id`), `POST /api/app/notifications/read`,
`GET /api/app/push/vapid`, `GET|POST|DELETE /api/app/push`
(`{endpoint, p256dh, auth, device_name, min_severity}` – nur `https`, keine
internen Ziele), `POST /api/app/push/test`. Push-Inhalt:
`{"type":"notification","id","severity","title"}`, verschlüsselt nach RFC 8291.

---

## Abmelden (Deinstallation)

```
POST /api/agents/decommission
Authorization: Bearer <AGENT-TOKEN>
```

```json
{
  "agent_id": 42,
  "hostname": "srv01",
  "ip_address": "10.0.0.5",
  "mac_address": "aa:bb:cc:dd:ee:ff",
  "purge": true,
  "all_for_hostname": true
}
```

`purge: true` löscht Gerät **und** Logs. Ohne wird das Gerät nur stillgelegt.

Zuordnung vom Genauesten zum Ungenauesten — welcher Weg gegriffen hat, steht in
der Antwort als `matched_by`:

1. `agent_id` · 2. `mac_address` · 3. `hostname` + `ip_address` · 4. `hostname`

`all_for_hostname: true` nimmt zusätzlich alle weiteren Einträge desselben
Hostnamens mit. Nötig, weil ein Rechner nach einem IP-Wechsel mehrfach in der
Liste steht — ohne das blieben die alten als Karteileichen mit ihren Logs
liegen.

---

## Schnittstelle für die App

Eigener Zweig unter **`/api/app`** — schlanker als die Browser-API, weil eine
App andere Sorgen hat:

| Endpunkt | Wofür |
|----------|-------|
| `GET /api/app/bootstrap` | alles für den Start in einem Aufruf: Server, Benutzer, Farben, Filterwerte |
| `GET /api/app/logs` | Logzeilen, per Cursor blätterbar (`before_id`) |
| `GET /api/app/logs/tail` | nur, was seit `since_id` dazukam |
| `GET /api/app/logs/{id}` | eine Zeile vollständig samt Rohtext |
| `GET /api/app/summary` | Zahlen für den Startbildschirm |
| `GET /api/app/devices` | kompakte Geräteliste mit Online-Zustand |

**Warum eine eigene Schnittstelle:**

- **Wenig Daten.** Über Mobilfunk zählt jedes Kilobyte. Rohzeilen kommen erst
  mit, wenn jemand eine Zeile aufklappt.
- **Cursor statt Seitenzahl.** Bei `page=42` verschiebt sich alles, sobald
  währenddessen neue Logs eintreffen — man sieht Zeilen doppelt oder
  überspringt welche. Mit `before_id` passiert das nicht.
- **Nachlaufen statt neu laden.** `since_id` liefert nur das Neue.
- **Lesbare Logs.** Jede Zeile kommt durch den Anzeige-Parser und bringt eine
  Zusammenfassung (`summary`) und Abzeichen (`badges`) mit.

`bootstrap` meldet `api_level` und `capabilities` — daran kann eine ältere App
ablesen, was dieser Server kann, statt es auszuprobieren.

---

## Logs lesen und filtern

| Anfrage | Liefert |
|---|---|
| `GET /api/logs?hostname=srv01&min_severity=error&page=1&page_size=100` | Logs, gefiltert und seitenweise |
| `GET /api/logs/filter-options` | verfügbare Werte für die Filter |
| `GET /api/logs/{id}/parsed` | eine Zeile zerlegt: Felder, Abzeichen |
| `GET /api/logs/export?format=csv` | Export, auch `json`, mit denselben Filtern |
| `GET /api/logs/stats` | Statistik |

---

## Verwaltung

| Bereich | Prefix |
|---------|--------|
| Updates, Releases, Kanal, Webhook | `/api/updates` |
| Sicherung und Wiederherstellung | `/api/backup` |
| KI-Auswertung | `/api/ai` |
| Zusatzdienste | `/api/stacks` |
| Mail | `/api/mail` |
| Terminal | `/api/shell` |
| Systemcheck | `/api/diagnostics` |
| Reverse Proxy und TLS | `/api/caddy` |
| Netzwerk und DNS | `/api/network` |

Alles davon ist Administratoren vorbehalten.

**Systemeingriffe verlangen zwei Dinge im Rumpf:** ein Bestätigungswort
(`confirm: "UPDATE"`, `"ROLLBACK"`, `"RESTORE"`, `"CHANGE"`) und die
beantwortete Sicherungsfrage:

```json
{
  "confirm": "UPDATE",
  "backup": { "create": true, "scopes": ["settings", "users"], "passphrase": "" }
}
```

oder, für den bewussten Verzicht:

```json
{ "confirm": "UPDATE", "backup": { "create": false } }
```

Fehlt `backup`, antwortet der Server mit 400. Die Rückfrage lässt sich also
nicht dadurch umgehen, dass man die Oberfläche wegläßt.

---

## Ereignisstrom

```
GET /api/updates/stream?token=<access_token>
```

Server-Sent Events. Ereignisse: `update.available`, `update.cleared`,
`update.state`, `backup.done`, `stack.changed`. Alle 20 Sekunden ein
Lebenszeichen, damit Proxys die Verbindung nicht kappen.

Bewusst kein WebSocket: Es fließt nur in eine Richtung, und SSE läuft ohne
Sonderbehandlung durch jeden Reverse Proxy.

---

## GitHub-Webhook

```
POST /api/updates/webhook
X-Hub-Signature-256: sha256=…
```

Von außen erreichbar, aber nicht offen: Ohne gültige HMAC-Signatur und ohne
gesetztes `LOGBOT_WEBHOOK_SECRET` wird nichts angenommen. Siehe
[Updates](../updates/README.md#sofortmeldung).

---

## Öffentliche Webhooks

```
GET /api/webhook/{id}/call?token={token}
```

Der einzige Endpunkt, der ohne Anmeldung Logdaten liefert. Gebremst auf 60
Aufrufe pro Minute. Siehe [Integrationen](../integrations/README.md#webhooks).

---

## Weiter

- [Agents](../../agents/README.md)
- [Integrationen](../integrations/README.md)
- [Backend](../../backend/README.md)
