#!/usr/bin/env python3
# ==============================================================================
# Name:        Philipp Fischer
# Kontakt:     p.fischer@itconex.de
# Version:     2026.02.16.12.00.00
# Beschreibung: LogBot v2026.02.16.12.00.00 - Syslog Server mit UniFi Parsing
#               EmpfÃ¤ngt Syslog auf UDP/TCP 514, parst verschiedene Formate
#               Optimiert: Agent-Cache, Batch-Inserts, gebÃ¼ndelte last_seen Updates
# ==============================================================================

import asyncio
import os
import re
import json
import logging
import time
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
import asyncpg

# Logging Setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('syslog_server')

# Umgebungsvariablen
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', '5432'))
DB_USER = os.getenv('DB_USER', 'logbot')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_NAME = os.getenv('DB_NAME', 'logbot')
SYSLOG_PORT = int(os.getenv('SYSLOG_PORT', '514'))

# Batch-Konfiguration
BATCH_SIZE = 100
BATCH_INTERVAL = 2.0  # Sekunden
AGENT_CACHE_TTL = 300  # 5 Minuten

# Syslog Level Namen
LEVEL_NAMES = {0: 'emergency', 1: 'alert', 2: 'critical', 3: 'error',
               4: 'warning', 5: 'notice', 6: 'info', 7: 'debug'}

# ==============================================================================
# REGEX PATTERNS - UniFi Netconsole und MAC/Model Format
# ==============================================================================

# Pattern 1: UniFi Netconsole - {hex} ist Sequenznummer, NICHT Hostname!
# Beispiel: <6>{f1d1} [1234.567890] mclagsyncd[1234]: Message
UNIFI_NETCONSOLE = re.compile(
    r'^<(\d+)>\{([a-fA-F0-9]+)\}\s*\[[\d.]+\]\s*(\S+?)(?:\[\d+\])?:\s*(.*)$'
)

# Pattern 2: UniFi MAC/Model Format
# Beispiel: <30>784558fc21cf,U6-LR-6.7.31+15618: hostapd: Message
UNIFI_MAC_MODEL = re.compile(
    r'^<(\d+)>([a-fA-F0-9]{12}),([^:]+):\s*(\S+?):\s*(.*)$'
)

# Pattern 3: Standard BSD Syslog
BSD_SYSLOG = re.compile(
    r'^<(\d+)>([A-Z][a-z]{2}\s+\d+\s+\d+:\d+:\d+)\s+(\S+)\s+(\S+?)(?:\[\d+\])?:\s*(.*)$'
)

# Pattern 4: Nur Priority
SIMPLE = re.compile(r'^<(\d+)>\s*(.*)$')


class SyslogParser:
    """Parst verschiedene Syslog-Formate inkl. UniFi."""

    @staticmethod
    def parse_priority(pri: int) -> Tuple[int, str]:
        """Zerlegt Priority in Facility und Level."""
        facility = pri >> 3
        severity = pri & 0x07
        return facility, LEVEL_NAMES.get(severity, 'info')

    @staticmethod
    def format_mac(mac: str) -> str:
        """Formatiert MAC: aabbccddeeff -> aa:bb:cc:dd:ee:ff"""
        return ':'.join(mac[i:i+2].lower() for i in range(0, 12, 2))

    def parse(self, raw: str, sender_ip: str) -> Dict[str, Any]:
        """Parst eine Syslog-Nachricht."""
        raw = raw.strip()
        result = {
            'hostname': sender_ip,
            'ip_address': sender_ip,
            'mac_address': None,
            'device_type': 'syslog',
            'facility': 1,
            'level': 'info',
            'source': 'unknown',
            'message': raw,
            'raw_message': raw,
            'extra_data': {}
        }

        # Pattern 1: UniFi Netconsole - {hex} ist KEINE Device-ID!
        m = UNIFI_NETCONSOLE.match(raw)
        if m:
            pri, hex_seq, source, msg = m.groups()
            fac, lvl = self.parse_priority(int(pri))
            result.update({
                'hostname': sender_ip,  # IP als Hostname, NICHT hex_seq!
                'facility': fac,
                'level': lvl,
                'source': source,
                'message': msg,
                'device_type': 'unifi_ap',
                'extra_data': {'format': 'netconsole', 'sequence': hex_seq}
            })
            return result

        # Pattern 2: UniFi MAC/Model
        m = UNIFI_MAC_MODEL.match(raw)
        if m:
            pri, mac_raw, model, source, msg = m.groups()
            fac, lvl = self.parse_priority(int(pri))
            mac = self.format_mac(mac_raw)
            result.update({
                'hostname': mac,  # MAC als Hostname
                'mac_address': mac,
                'facility': fac,
                'level': lvl,
                'source': source,
                'message': msg,
                'device_type': 'unifi_ap',
                'extra_data': {'format': 'mac_model', 'model': model}
            })
            return result

        # Pattern 3: BSD Syslog
        m = BSD_SYSLOG.match(raw)
        if m:
            pri, ts, host, source, msg = m.groups()
            fac, lvl = self.parse_priority(int(pri))
            result.update({
                'hostname': host,
                'facility': fac,
                'level': lvl,
                'source': source,
                'message': msg,
                'extra_data': {'format': 'bsd'}
            })
            return result

        # Pattern 4: Simple
        m = SIMPLE.match(raw)
        if m:
            pri, msg = m.groups()
            fac, lvl = self.parse_priority(int(pri))
            result.update({'facility': fac, 'level': lvl, 'message': msg})

        return result


class DatabaseManager:
    """Async PostgreSQL Verbindung mit Agent-Cache und Batch-Inserts."""

    def __init__(self):
        self.pool = None
        # Agent-Cache: key -> (agent_id, timestamp)
        self._agent_cache = {}
        # Batch-Buffer fÃ¼r Logs
        self._log_buffer = []
        self._buffer_lock = asyncio.Lock()
        # Set von Agent-IDs die ein last_seen Update brauchen
        self._agents_to_update = set()

    async def connect(self):
        """Verbindung herstellen mit Retry."""
        for i in range(30):
            try:
                self.pool = await asyncpg.create_pool(
                    host=DB_HOST, port=DB_PORT, user=DB_USER,
                    password=DB_PASSWORD, database=DB_NAME,
                    min_size=2, max_size=10
                )
                logger.info(f"DB verbunden: {DB_HOST}:{DB_PORT}/{DB_NAME}")
                return
            except Exception as e:
                logger.warning(f"DB Verbindung fehlgeschlagen ({i+1}/30): {e}")
                await asyncio.sleep(2)
        raise Exception("DB Verbindung fehlgeschlagen")

    async def close(self):
        if self.pool:
            await self._flush_buffer()
            await self.pool.close()

    def _cache_key(self, hostname: str, ip: str, mac: str) -> str:
        return f"{mac or ''}/{hostname}/{ip}"

    async def get_or_create_agent(self, hostname: str, ip: str, mac: str,
                                   device_type: str, extra_data: dict) -> int:
        """Agent finden oder erstellen - mit In-Memory-Cache."""
        key = self._cache_key(hostname, ip, mac)
        now = time.monotonic()

        # Cache prüfen
        cached = self._agent_cache.get(key)
        if cached and (now - cached[1]) < AGENT_CACHE_TTL:
            self._agents_to_update.add(cached[0])
            return cached[0]

        # DB abfragen / ggf. updaten
        async with self.pool.acquire() as conn:
            agent_row = None
            if mac:
                agent_row = await conn.fetchrow(
                    "SELECT id, device_type, mac_address FROM agents WHERE mac_address = $1", mac)

            if not agent_row:
                agent_row = await conn.fetchrow(
                    "SELECT id, device_type, mac_address FROM agents WHERE hostname=$1 AND ip_address=$2",
                    hostname, ip)

            if agent_row:
                agent_id = agent_row['id']
                updates = []
                params = []

                # Gerätetyp nachtragen, falls bisher unbekannt
                if (agent_row['device_type'] in (None, 'unknown')) and device_type and device_type != 'unknown':
                    updates.append(f"device_type = ${len(params) + 1}")
                    params.append(device_type)

                # MAC nachtragen, falls leer
                if (not agent_row['mac_address']) and mac:
                    updates.append(f"mac_address = ${len(params) + 1}")
                    params.append(mac)

                if updates:
                    params.append(agent_id)
                    await conn.execute(f"UPDATE agents SET {', '.join(updates)} WHERE id = ${len(params)}", *params)
            else:
                agent_id = await conn.fetchval(
                    """INSERT INTO agents (hostname, ip_address, mac_address, device_type, extra_data)
                       VALUES ($1, $2, $3, $4, $5::jsonb) RETURNING id""",
                    hostname, ip, mac, device_type, json.dumps(extra_data))

        # Cache aktualisieren
        self._agent_cache[key] = (agent_id, now)
        self._agents_to_update.add(agent_id)
        return agent_id

    async def queue_log(self, data: Dict[str, Any]):
        """Log in den Buffer legen statt direkt einzufÃ¼gen."""
        agent_id = await self.get_or_create_agent(
            data['hostname'], data['ip_address'], data.get('mac_address'),
            data['device_type'], data.get('extra_data', {}))

        row = (agent_id, data['hostname'], data['ip_address'], data['facility'],
               data['level'], data['source'], data['message'], data['raw_message'],
               json.dumps(data.get('extra_data', {})))

        async with self._buffer_lock:
            self._log_buffer.append(row)
            if len(self._log_buffer) >= BATCH_SIZE:
                await self._flush_buffer()

    async def _flush_buffer(self):
        """Buffer in die DB schreiben via COPY (schnellster Weg)."""
        if not self._log_buffer:
            return

        rows = self._log_buffer
        self._log_buffer = []

        try:
            async with self.pool.acquire() as conn:
                await conn.copy_records_to_table(
                    'logs',
                    records=rows,
                    columns=['agent_id', 'hostname', 'ip_address', 'facility',
                             'level', 'source', 'message', 'raw_message', 'extra_data']
                )
        except Exception as e:
            logger.error(f"Batch-Insert fehlgeschlagen ({len(rows)} Logs): {e}")

    async def _flush_agent_timestamps(self):
        """Alle ausstehenden last_seen Updates gebÃ¼ndelt schreiben."""
        if not self._agents_to_update:
            return

        agent_ids = list(self._agents_to_update)
        self._agents_to_update.clear()

        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "UPDATE agents SET last_seen = NOW() WHERE id = ANY($1::int[])",
                    agent_ids)
        except Exception as e:
            logger.error(f"Agent last_seen Update fehlgeschlagen: {e}")

    async def flush_loop(self):
        """Periodisch Buffer und Agent-Timestamps flushen."""
        while True:
            await asyncio.sleep(BATCH_INTERVAL)
            try:
                async with self._buffer_lock:
                    await self._flush_buffer()
                await self._flush_agent_timestamps()
            except Exception as e:
                logger.error(f"Flush-Loop Fehler: {e}")


class SyslogUDPProtocol(asyncio.DatagramProtocol):
    """UDP Syslog EmpfÃ¤nger."""

    def __init__(self, parser: SyslogParser, db: DatabaseManager):
        self.parser = parser
        self.db = db
        self.count = 0

    def datagram_received(self, data: bytes, addr: Tuple[str, int]):
        msg = data.decode('utf-8', errors='replace').strip()
        if msg:
            self.count += 1
            asyncio.create_task(self._process(msg, addr[0]))

    async def _process(self, msg: str, ip: str):
        try:
            parsed = self.parser.parse(msg, ip)
            await self.db.queue_log(parsed)
        except Exception as e:
            logger.error(f"Fehler: {e}")


async def handle_tcp(reader, writer, parser: SyslogParser, db: DatabaseManager):
    """TCP Syslog Handler."""
    addr = writer.get_extra_info('peername')
    ip = addr[0] if addr else 'unknown'
    try:
        while True:
            data = await reader.readline()
            if not data:
                break
            msg = data.decode('utf-8', errors='replace').strip()
            if msg:
                parsed = parser.parse(msg, ip)
                await db.queue_log(parsed)
    except:
        pass
    finally:
        writer.close()


async def main():
    logger.info("=" * 60)
    logger.info("LogBot Syslog Server v2026.02.16.12.00.00")
    logger.info("=" * 60)

    parser = SyslogParser()
    db = DatabaseManager()
    await db.connect()

    # Flush-Loop starten (Batch-Inserts + Agent last_seen)
    asyncio.create_task(db.flush_loop())

    loop = asyncio.get_event_loop()

    # UDP Server
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: SyslogUDPProtocol(parser, db),
        local_addr=('0.0.0.0', SYSLOG_PORT))

    # TCP Server
    tcp_server = await asyncio.start_server(
        lambda r, w: handle_tcp(r, w, parser, db),
        '0.0.0.0', SYSLOG_PORT)

    logger.info(f"Syslog Server lÃ¤uft auf UDP/TCP Port {SYSLOG_PORT}")
    logger.info(f"Batch-Modus: {BATCH_SIZE} Logs oder alle {BATCH_INTERVAL}s")

    try:
        await tcp_server.serve_forever()
    finally:
        transport.close()
        tcp_server.close()
        await db.close()


if __name__ == '__main__':
    asyncio.run(main())

