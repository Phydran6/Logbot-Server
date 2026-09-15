# Dokumentation

Alles, was über die [Übersicht](../README.md) hinausgeht — nach Aufgaben
sortiert, nicht nach Bauteilen.

## Nach Aufgabe

| Ich will … | steht in |
|------------|----------|
| LogBot aufsetzen | [Installation](install/README.md) |
| wissen, ob mein Server reicht | [Installation → Systemprüfung](install/README.md#systemprüfung) |
| Portainer, n8n, Postfix dazunehmen | [Installation → Zusatzdienste](install/README.md#zusatzdienste) |
| täglich damit arbeiten | [Betrieb](operate/README.md) |
| die Oberfläche auf Englisch stellen | [Betrieb → Sprache](operate/README.md#sprache) |
| eine Shell auf dem Server öffnen | [Betrieb → Terminal](operate/README.md#terminal-im-browser) |
| aktualisieren | [Updates](updates/README.md) |
| den aktuellsten Stand per Einzeiler drüberbügeln | [Updates → Einzeiler](updates/README.md#einzeiler-auf-einen-blick) |
| wissen, welcher Update-Weg wann passt | [Updates → Welchen Weg nehmen?](updates/README.md#welchen-weg-nehmen) |
| auf einer bestimmten Version bleiben | [Updates → Kanal](updates/README.md#welchen-stand-soll-der-server-fahren) |
| sofort erfahren, wenn etwas gepusht wurde | [Updates → Sofortmeldung](updates/README.md#sofortmeldung) |
| auf einen früheren Stand zurückfallen | [Updates → Zurückfallen](updates/README.md#zurückfallen) |
| einem fehlgeschlagenen Update nachgehen | [Updates → Fehlersuche](updates/README.md#fehlersuche) |
| sichern und zurückspielen | [Sicherung](backup/README.md) |
| Logs von einer KI auswerten lassen | [Integrationen → KI](integrations/README.md#ki-auswertung) |
| Mails vom Server bekommen | [Integrationen → Mail](integrations/README.md#mail-postfix) |
| die API benutzen | [API](api/README.md) |
| Rechner anbinden | [Agents](../agents/README.md) |
| PostgreSQL migrieren | [Datenbank](../db/README.md) |

## Nach Bauteil

| Verzeichnis | Inhalt |
|-------------|--------|
| [`backend/`](../backend/README.md) | FastAPI: API, Auth, Patchmanagement, Sicherung, KI, Mail, Terminal |
| [`frontend/`](../frontend/README.md) | Vue 3: Oberfläche, Sprachen, Design-System |
| [`syslog/`](../syslog/README.md) | Syslog-Empfänger auf UDP/TCP 514 |
| [`db/`](../db/README.md) | Schema, Migration, PostgreSQL-Upgrade |
| [`caddy/`](../caddy/README.md) | Reverse Proxy und TLS |
| [`deploy/`](../deploy/README.md) | Compose-Varianten: externe DB, gehärtet, Zusatzdienste |
| [`install/`](../install/README.md) | Systemprüfung vor der Installation |
| [`agents/`](../agents/README.md) | Installer für Linux und Windows |
| [`n8n/`](../n8n/README.md) | Fertige Workflows |
| [`CHANGELOG/`](../CHANGELOG/README.md) | Änderungen je Bereich |

## Bilder und Zeichen

Unter [`assets/`](assets/README.md) liegt das LogBot-Zeichen — dasselbe wie in
der Android-App.
