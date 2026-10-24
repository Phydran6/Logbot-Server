# ==============================================================================
# Name:        Phydran6
# Kontakt:     Phydran6
# Version:     2026.10.23.12.00.00
# Beschreibung: LogBot - Rate Limiter (slowapi) + echte Client-IP hinter Caddy
# ==============================================================================

import ipaddress
import os
import socket
import time
from typing import Set

from starlette.requests import Request
from slowapi import Limiter

# Wer X-Forwarded-For setzen darf: die Proxys dieses Stacks. Weitere (z.B. ein
# vorgeschalteter NPM im selben Docker-Netz) per LOGBOT_TRUSTED_PROXIES,
# Komma-getrennt, als Name, IP oder Netz.
_PROXY_NAMES = ["caddy", "logbot-caddy", "frontend", "logbot-frontend"]
_EXTRA = [p.strip() for p in os.getenv("LOGBOT_TRUSTED_PROXIES", "").split(",") if p.strip()]

_cache: Set[str] = set()
_networks: list = []
_cache_until = 0.0


def _trusted() -> tuple:
    """Die IPs der eigenen Proxys - per DNS im Docker-Netz, eine Minute gemerkt."""
    global _cache, _networks, _cache_until
    now = time.monotonic()
    if now < _cache_until:
        return _cache, _networks
    addresses: Set[str] = {"127.0.0.1", "::1"}
    networks = []
    for name in _PROXY_NAMES + _EXTRA:
        try:
            networks.append(ipaddress.ip_network(name, strict=False))
            continue
        except ValueError:
            pass
        try:
            for info in socket.getaddrinfo(name, None):
                addresses.add(info[4][0])
        except OSError:
            pass
    _cache, _networks, _cache_until = addresses, networks, now + 60
    return _cache, _networks


def _is_trusted(peer: str) -> bool:
    addresses, networks = _trusted()
    if peer in addresses:
        return True
    try:
        ip = ipaddress.ip_address(peer)
    except ValueError:
        return False
    return any(ip in net for net in networks)


def client_ip(request: Request) -> str:
    """IP des echten Absenders.

    Das Backend ist nur im Docker-Netz erreichbar (expose, kein ports), jede
    Anfrage kommt also normalerweise ueber Caddy. Caddy setzt X-Forwarded-For
    und haengt den direkten Absender als LETZTEN Eintrag an - der ist nicht
    faelschbar, weiter vorne stehende Eintraege schon.

    Neu: Der Kopf zaehlt nur noch, wenn die Anfrage tatsaechlich von einem der
    eigenen Proxys kommt. Vorher konnte jeder andere Container im Docker-Netz
    (n8n, Open WebUI, ...) das Backend direkt ansprechen und sich per Kopfzeile
    eine beliebige Absender-IP geben - an Netzbeschraenkungen von Schluesseln
    und an Bremsen vorbei.
    """
    peer = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded and _is_trusted(peer):
        last = forwarded.split(",")[-1].strip()
        if last:
            return last
    return peer


def agent_key(request: Request) -> str:
    """Limit-Schluessel fuer Agent-Lieferungen: der Agent, nicht die IP.

    Hinter NAT oder einem Proxy teilen sich sonst alle Agents EIN Limit - dann
    bekommen alle 429, und ein Agent, der bei Fehlern wiederholt, heizt das
    weiter an (so geschehen am 2026-10-10). Gespeichert wird nur ein Abdruck
    des Schluessels, nie der Schluessel selbst.
    """
    import hashlib
    auth = request.headers.get("authorization", "")
    if auth:
        return "agent:" + hashlib.sha256(auth.encode("utf-8", "replace")).hexdigest()[:24]
    return client_ip(request)


# Vorher get_remote_address -> alle Nutzer teilten sich das Limit der Caddy-IP.
limiter = Limiter(key_func=client_ip)
