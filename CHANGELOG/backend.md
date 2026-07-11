# Changelog — Backend

FastAPI-API (`backend/`). Versionsformat: `YYYY.MM.DD.HH.MM.SS`.

## 2026.07.11.13.03.42
### Added
- **Netzwerk-DNS-Verwaltung** (`routes/network.py`): `GET/PUT /api/network/dns` und `POST /api/network/dns/test`. Standard = per DHCP vergebener System-DNS des Hosts (gelesen aus `/proc/1/root/.../resolv.conf`), optional eigene Server + Such-Domains; wird auf `/etc/resolv.conf` des Backend-Containers angewendet und beim Start erneut gesetzt.

### Changed
- Behebt „FQDN nicht auflösbar" im Reverse-Proxy-Check auf jedem Netz, ohne hartes `extra_hosts` in `docker-compose.yml` (entfernt).

## 2026.05.30.18.02.35
### Added
- Ausgangsbasis dieses Changelogs. Aktueller Funktionsstand u.a.: HTTPS-Log-Ingest (`/api/agents/ingest`), Agent- & Token-Verwaltung, MFA/TOTP, Caddy-Management (Reverse Proxy & TLS), Disk-Monitoring und Retention-Housekeeping.

_Änderungen vor Einführung des Changelogs wurden nicht einzeln erfasst._
