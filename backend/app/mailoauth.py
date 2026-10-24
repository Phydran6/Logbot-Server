# ==============================================================================
# Name:        Phydran6
# Kontakt:     Phydran6
# Changelog:   ../../CHANGELOG/backend.md
# Beschreibung: LogBot - Mail-Konten per OAuth anbinden (Google, Microsoft 365,
#               Outlook.com) und die Entra-App-Registrierung selbst anlegen
# ==============================================================================
"""
"Mit Google anmelden" / "Mit Microsoft anmelden" fuer den Mailversand.

Warum OAuth und nicht einfach SMTP mit Passwort
-----------------------------------------------
Microsoft hat die Passwort-Anmeldung per SMTP fuer Outlook.com 2024 und fuer
Exchange Online 2026 abgeschaltet. Google verlangt fuer Passwoerter ein
App-Passwort samt Zwei-Schritt-Bestaetigung. OAuth ist bei beiden der
vorgesehene Weg - und es liegt kein Passwort auf dem Server, nur ein
widerrufbarer Refresh-Token (verschluesselt, app/secretbox.py).

Die drei Ablaeufe
-----------------
1. **Browser + Code (PKCE)** - Google und Microsoft. Der Assistent oeffnet die
   Anmeldeseite des Anbieters. Hat LogBot eine oeffentliche HTTPS-Adresse,
   kommt der Browser von selbst zurueck (`/api/mail/oauth/callback`).
   Sonst landet er auf `http://localhost/...` - die Seite laedt nicht, und man
   kopiert die Adresse aus der Adresszeile in den Assistenten. Das geht in
   jedem Netz, auch ohne oeffentlichen Namen.
2. **Geraetecode** - Microsoft. Der Assistent zeigt einen Code; man gibt ihn
   unter microsoft.com/devicelogin ein und meldet sich an. Kein Kopieren.
3. **App-Registrierung anlegen** - Microsoft 365. Ein Administrator meldet sich
   einmal an (Geraetecode oder Browser) ueber Microsofts eigenes Werkzeug
   "Microsoft Graph Command Line Tools" - dasselbe, das `Connect-MgGraph` in
   PowerShell nutzt. Mit diesem Zugang legt LogBot die App-Registrierung
   "LogBot Mail" im Mandanten an, erteilt die Administratorzustimmung fuer
   `Mail.Send` und merkt sich die Anwendungs-ID. Der Admin-Zugang wird danach
   verworfen - er wird nirgends gespeichert.

Gebraucht wird dafuer eine dieser Rollen: Globaler Administrator,
Anwendungsadministrator oder Cloudanwendungsadministrator (fuer die Zustimmung
zu `Mail.Send` reicht bei letzteren je nach Mandant nicht - dann meldet der
Assistent das, und die Zustimmung erfolgt beim Anmelden des Postfachs).
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import secrets
import socket
import time
from typing import Dict, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx

from . import secretbox

logger = logging.getLogger("logbot.mailoauth")

FLOW_TTL = 900

GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_SCOPES = "openid email https://www.googleapis.com/auth/gmail.send"
GOOGLE_LOOPBACK = "http://127.0.0.1:53682/"

MS_LOGIN = "https://login.microsoftonline.com"
GRAPH = "https://graph.microsoft.com/v1.0"
MS_MAIL_SCOPES = ("offline_access openid email https://graph.microsoft.com/Mail.Send "
                  "https://graph.microsoft.com/User.Read")
MS_LOOPBACK = "http://localhost"

# Microsofts eigenes oeffentliches Werkzeug ("Microsoft Graph Command Line
# Tools", die Anwendung hinter Connect-MgGraph). Nur fuer das einmalige
# Anlegen der App-Registrierung.
MS_GRAPH_CLI_CLIENT = "14d82eec-204b-4c2f-b7e8-296a70dab67e"
MS_ADMIN_SCOPES = ("https://graph.microsoft.com/Application.ReadWrite.All "
                   "https://graph.microsoft.com/DelegatedPermissionGrant.ReadWrite.All "
                   "https://graph.microsoft.com/User.Read")

# Microsoft Graph und die Kennungen der delegierten Berechtigungen.
GRAPH_APP_ID = "00000003-0000-0000-c000-000000000000"
GRAPH_SCOPE_IDS = {
    "Mail.Send": "e383f46e-2787-4529-855e-0e479a3ffac0",
    "User.Read": "e1fe6dd8-ba31-4d61-89e7-88639da4683d",
    "offline_access": "7427e0e9-2fba-42fe-b0c0-848c9e6a8182",
    "openid": "37f7f235-527c-4136-accd-4a02d197296e",
    "email": "64a6cdd6-aab1-4aaf-94b8-3cc8405e90d0",
}


class OAuthError(Exception):
    """Ein Schritt ist schiefgegangen - die Meldung ist fuer die Oberflaeche."""


def error_text(response: httpx.Response) -> str:
    """Was der Anbieter zum Fehler sagt - ohne Token-Inhalte."""
    try:
        data = response.json()
    except ValueError:
        return response.text[:300]
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict):
            return str(err.get("message") or err.get("code") or err)[:400]
        desc = data.get("error_description") or ""
        return (f"{err}: {desc}" if err and desc else str(err or desc or data))[:400]
    return str(data)[:300]


def _pkce() -> Tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).decode().rstrip("=")
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()).decode().rstrip("=")
    return verifier, challenge


def _hostname() -> str:
    return socket.gethostname().split(".")[0][:30] or "logbot"


# =============================================================================
# Laufende Vorgaenge (nur im Arbeitsspeicher)
# =============================================================================
class _Flows:
    def __init__(self) -> None:
        self.items: Dict[str, dict] = {}

    def new(self, **data) -> str:
        self.expire()
        flow_id = secrets.token_urlsafe(24)
        data["created"] = time.time()
        data.setdefault("status", "pending")
        self.items[flow_id] = data
        return flow_id

    def get(self, flow_id: str, user_id: Optional[int] = None) -> dict:
        self.expire()
        flow = self.items.get(flow_id or "")
        if not flow:
            raise OAuthError("Dieser Anmeldevorgang ist abgelaufen. Bitte neu beginnen.")
        if user_id is not None and flow.get("user_id") != user_id:
            raise OAuthError("Dieser Anmeldevorgang gehört zu einem anderen Konto.")
        return flow

    def by_state(self, state: str) -> Tuple[str, dict]:
        self.expire()
        for flow_id, flow in self.items.items():
            if flow.get("state") and secrets.compare_digest(flow["state"], state or ""):
                return flow_id, flow
        raise OAuthError("Unbekannter oder abgelaufener Anmeldevorgang (state).")

    def drop(self, flow_id: str) -> None:
        self.items.pop(flow_id, None)

    def expire(self) -> None:
        deadline = time.time() - FLOW_TTL
        for key in [k for k, v in self.items.items() if v["created"] < deadline]:
            self.items.pop(key, None)
        if len(self.items) > 200:
            for key in sorted(self.items, key=lambda k: self.items[k]["created"])[:100]:
                self.items.pop(key, None)


flows = _Flows()


# =============================================================================
# 1. Browser + Code (PKCE)
# =============================================================================
def start_authorize(*, provider: str, user_id: int, client_id: str, client_secret: str = "",
                    tenant: str = "organizations", callback_url: str = "") -> dict:
    """Erzeugt die Anmeldeadresse. `callback_url` leer = Adresse zurueckkopieren."""
    client_id = (client_id or "").strip()
    if not client_id:
        raise OAuthError("Die Client-ID fehlt.")
    verifier, challenge = _pkce()
    state = secrets.token_urlsafe(32)

    if provider == "google":
        redirect = callback_url or GOOGLE_LOOPBACK
        params = {
            "client_id": client_id, "redirect_uri": redirect, "response_type": "code",
            "scope": GOOGLE_SCOPES, "access_type": "offline", "prompt": "consent",
            "include_granted_scopes": "true", "state": state,
            "code_challenge": challenge, "code_challenge_method": "S256",
        }
        url = f"{GOOGLE_AUTH}?{urlencode(params)}"
    elif provider == "microsoft":
        redirect = callback_url or MS_LOOPBACK
        params = {
            "client_id": client_id, "response_type": "code", "redirect_uri": redirect,
            "response_mode": "query", "scope": MS_MAIL_SCOPES, "state": state,
            "code_challenge": challenge, "code_challenge_method": "S256",
            "prompt": "select_account",
        }
        url = f"{MS_LOGIN}/{tenant or 'organizations'}/oauth2/v2.0/authorize?{urlencode(params)}"
    else:
        raise OAuthError(f"Unbekannter Anbieter '{provider}'.")

    flow_id = flows.new(kind="authorize", provider=provider, user_id=user_id,
                        client_id=client_id, client_secret=client_secret,
                        tenant=tenant or "organizations", verifier=verifier, state=state,
                        redirect_uri=redirect)
    return {"flow_id": flow_id, "auth_url": url, "redirect_uri": redirect,
            "returns_by_itself": bool(callback_url)}


def parse_pasted(value: str) -> Tuple[str, str]:
    """Code und state aus der zurueckkopierten Adresse (oder nur dem Code)."""
    value = (value or "").strip()
    if not value:
        raise OAuthError("Es wurde nichts eingefügt.")
    if "code=" in value or value.startswith("http"):
        query = parse_qs(urlsplit(value).query)
        if "error" in query:
            raise OAuthError("Die Anmeldung wurde abgelehnt: "
                             + (query.get("error_description") or query["error"])[0][:300])
        code = (query.get("code") or [""])[0]
        state = (query.get("state") or [""])[0]
        if not code:
            raise OAuthError("In der eingefügten Adresse steht kein Code.")
        return code, state
    return value, ""


async def complete_authorize(flow: dict, code: str, state: str = "") -> dict:
    """Tauscht den Code gegen Token und liest die Absenderadresse."""
    if state and not secrets.compare_digest(state, flow.get("state", "")):
        raise OAuthError("Die eingefügte Adresse gehört zu einem anderen Anmeldevorgang.")
    data = {"grant_type": "authorization_code", "code": code, "client_id": flow["client_id"],
            "redirect_uri": flow["redirect_uri"], "code_verifier": flow["verifier"]}
    if flow.get("client_secret"):
        data["client_secret"] = flow["client_secret"]

    if flow["provider"] == "google":
        url = GOOGLE_TOKEN
    else:
        url = f"{MS_LOGIN}/{flow['tenant']}/oauth2/v2.0/token"
        data["scope"] = MS_MAIL_SCOPES
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, data=data)
    if response.status_code >= 400:
        raise OAuthError(f"Der Anbieter hat den Code nicht angenommen: {error_text(response)}")
    tokens = response.json()
    return await _finish(flow, tokens)


async def _finish(flow: dict, tokens: dict) -> dict:
    refresh = tokens.get("refresh_token")
    access = tokens.get("access_token")
    if not refresh:
        raise OAuthError("Der Anbieter hat keinen Refresh-Token geschickt. Bei Google: "
                         "Zugriff unter myaccount.google.com/permissions entfernen und neu "
                         "anmelden. Bei Microsoft: fehlt 'offline_access'?")
    account = await _account(flow["provider"], access)
    result = {
        "provider": flow["provider"], "client_id": flow["client_id"],
        "client_secret": flow.get("client_secret") or "", "tenant": flow.get("tenant") or "",
        "refresh_token": refresh, "account": account,
        "app": flow.get("app") or {},
    }
    _cache_access(flow["provider"], flow["client_id"], account, access,
                  int(tokens.get("expires_in") or 3000))
    return result


async def _account(provider: str, access_token: str) -> str:
    async with httpx.AsyncClient(timeout=20.0) as client:
        if provider == "google":
            response = await client.get(GOOGLE_USERINFO,
                                        headers={"Authorization": f"Bearer {access_token}"})
            if response.status_code < 400:
                return (response.json() or {}).get("email") or ""
        else:
            response = await client.get(f"{GRAPH}/me?$select=mail,userPrincipalName",
                                        headers={"Authorization": f"Bearer {access_token}"})
            if response.status_code < 400:
                data = response.json() or {}
                return data.get("mail") or data.get("userPrincipalName") or ""
    raise OAuthError(f"Die Kontoadresse ließ sich nicht lesen: {error_text(response)}")


# =============================================================================
# 2. Geraetecode (Microsoft)
# =============================================================================
async def start_device(*, user_id: int, client_id: str, tenant: str, scopes: str,
                       purpose: str, retries: int = 0) -> dict:
    """Fordert einen Geraetecode an. `purpose`: mailbox oder register."""
    tenant = tenant or "organizations"
    last_error = ""
    for attempt in range(retries + 1):
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(f"{MS_LOGIN}/{tenant}/oauth2/v2.0/devicecode",
                                         data={"client_id": client_id, "scope": scopes})
        if response.status_code < 400:
            data = response.json()
            flow_id = flows.new(kind="device", provider="microsoft", purpose=purpose,
                                user_id=user_id, client_id=client_id, tenant=tenant,
                                scopes=scopes, device_code=data["device_code"],
                                interval=int(data.get("interval") or 5),
                                expires=time.time() + int(data.get("expires_in") or 900),
                                next_poll=time.time())
            return {"flow_id": flow_id, "user_code": data["user_code"],
                    "verification_uri": data.get("verification_uri") or "https://microsoft.com/devicelogin",
                    "expires_in": int(data.get("expires_in") or 900),
                    "message": data.get("message", "")}
        last_error = error_text(response)
        # Frisch angelegte Anwendungen kennt Microsoft erst nach ein paar
        # Sekunden ueberall (AADSTS700016).
        if "700016" in last_error and attempt < retries:
            await asyncio.sleep(6)
            continue
        break
    if "7000218" in last_error or "public client" in last_error.lower():
        last_error += (" — In der App-Registrierung unter „Authentifizierung“ die Option "
                       "„Öffentliche Clientflows zulassen“ einschalten.")
    raise OAuthError(f"Microsoft hat keinen Gerätecode ausgegeben: {last_error}")


async def poll_device(flow: dict) -> Optional[dict]:
    """Ein Blick, ob die Anmeldung erledigt ist. None = noch nicht."""
    if time.time() > flow["expires"]:
        raise OAuthError("Der Gerätecode ist abgelaufen. Bitte neu beginnen.")
    if time.time() < flow.get("next_poll", 0):
        return None
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{MS_LOGIN}/{flow['tenant']}/oauth2/v2.0/token",
            data={"grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                  "client_id": flow["client_id"], "device_code": flow["device_code"]})
    if response.status_code < 400:
        return response.json()
    data = {}
    try:
        data = response.json()
    except ValueError:
        pass
    code = data.get("error", "")
    if code == "authorization_pending":
        flow["next_poll"] = time.time() + flow["interval"]
        return None
    if code == "slow_down":
        flow["interval"] += 5
        flow["next_poll"] = time.time() + flow["interval"]
        return None
    if code == "authorization_declined":
        raise OAuthError("Die Anmeldung wurde abgelehnt.")
    if code == "expired_token":
        raise OAuthError("Der Gerätecode ist abgelaufen. Bitte neu beginnen.")
    raise OAuthError(f"Microsoft meldet: {error_text(response)}")


async def finish_mailbox_device(flow: dict, tokens: dict) -> dict:
    return await _finish(flow, tokens)


# =============================================================================
# 3. App-Registrierung im Mandanten anlegen (Microsoft 365)
# =============================================================================
def start_register_authorize(*, user_id: int) -> dict:
    """Wie der Browserweg, nur mit dem Werkzeug-Client und Admin-Berechtigungen."""
    verifier, challenge = _pkce()
    state = secrets.token_urlsafe(32)
    params = {
        "client_id": MS_GRAPH_CLI_CLIENT, "response_type": "code", "redirect_uri": MS_LOOPBACK,
        "response_mode": "query", "scope": MS_ADMIN_SCOPES, "state": state,
        "code_challenge": challenge, "code_challenge_method": "S256",
        "prompt": "select_account",
    }
    flow_id = flows.new(kind="register_authorize", provider="microsoft", purpose="register",
                        user_id=user_id, client_id=MS_GRAPH_CLI_CLIENT, tenant="organizations",
                        verifier=verifier, state=state, redirect_uri=MS_LOOPBACK)
    return {"flow_id": flow_id, "redirect_uri": MS_LOOPBACK,
            "auth_url": f"{MS_LOGIN}/organizations/oauth2/v2.0/authorize?{urlencode(params)}"}


async def admin_token_from_code(flow: dict, code: str, state: str = "") -> dict:
    if state and not secrets.compare_digest(state, flow.get("state", "")):
        raise OAuthError("Die eingefügte Adresse gehört zu einem anderen Anmeldevorgang.")
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{MS_LOGIN}/organizations/oauth2/v2.0/token",
            data={"grant_type": "authorization_code", "code": code,
                  "client_id": MS_GRAPH_CLI_CLIENT, "redirect_uri": MS_LOOPBACK,
                  "code_verifier": flow["verifier"], "scope": MS_ADMIN_SCOPES})
    if response.status_code >= 400:
        raise OAuthError(f"Microsoft hat die Anmeldung nicht angenommen: {error_text(response)}")
    return response.json()


async def _graph(client: httpx.AsyncClient, method: str, path: str, token: str,
                 json: Optional[dict] = None, ok_codes=(200, 201, 204)) -> dict:
    response = await client.request(method, f"{GRAPH}{path}", json=json,
                                    headers={"Authorization": f"Bearer {token}"})
    if response.status_code not in ok_codes:
        raise httpx.HTTPStatusError(error_text(response), request=response.request,
                                    response=response)
    return response.json() if response.content else {}


async def register_app(admin_access_token: str, *, personal_accounts: bool = False,
                       callback_url: str = "") -> dict:
    """Legt "LogBot Mail" im Mandanten an und erteilt die Zustimmung.

    Gibt zurueck, was fuer die Postfach-Anmeldung gebraucht wird: Anwendungs-ID
    und Mandanten-ID - und einen Bericht, was getan wurde.
    """
    steps = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            me = await _graph(client, "GET", "/me?$select=userPrincipalName,displayName",
                              admin_access_token)
            org = await _graph(client, "GET", "/organization?$select=id,displayName",
                               admin_access_token)
        except httpx.HTTPStatusError as exc:
            raise OAuthError(f"Microsoft Graph antwortet nicht wie erwartet: {exc}") from exc
        tenant_id = ((org.get("value") or [{}])[0]).get("id") or ""
        tenant_name = ((org.get("value") or [{}])[0]).get("displayName") or ""
        steps.append(f"Angemeldet als {me.get('userPrincipalName')} im Mandanten "
                     f"„{tenant_name}“.")

        redirect_uris = [MS_LOOPBACK]
        if callback_url:
            redirect_uris.append(callback_url)
        body = {
            "displayName": f"LogBot Mail ({_hostname()})",
            "signInAudience": "AzureADandPersonalMicrosoftAccount" if personal_accounts else "AzureADMyOrg",
            "isFallbackPublicClient": True,
            "publicClient": {"redirectUris": redirect_uris},
            "requiredResourceAccess": [{
                "resourceAppId": GRAPH_APP_ID,
                "resourceAccess": [{"id": scope_id, "type": "Scope"}
                                   for scope_id in GRAPH_SCOPE_IDS.values()],
            }],
            "notes": "Angelegt vom LogBot-Mail-Assistenten. Erlaubt nur das Versenden von Mails "
                     "im Namen des angemeldeten Postfachs (Mail.Send, delegiert).",
            "tags": ["LogBot"],
        }
        if personal_accounts:
            # Pflicht fuer Anwendungen, die auch private Konten zulassen.
            body["api"] = {"requestedAccessTokenVersion": 2}
        try:
            app = await _graph(client, "POST", "/applications", admin_access_token, json=body)
        except httpx.HTTPStatusError as exc:
            message = str(exc)
            if exc.response.status_code == 403:
                message = ("Dem angemeldeten Konto fehlt das Recht, Anwendungen zu registrieren. "
                           "Gebraucht wird die Rolle Globaler Administrator, "
                           "Anwendungsadministrator oder Cloudanwendungsadministrator.")
            raise OAuthError(f"Die App-Registrierung ließ sich nicht anlegen: {message}") from exc
        app_id = app["appId"]
        steps.append(f"App-Registrierung „{app['displayName']}“ angelegt (Anwendungs-ID {app_id}).")

        # Unternehmensanwendung (Dienstprinzipal). Frisch angelegte Anwendungen
        # sind nicht sofort ueberall bekannt - deshalb mehrere Versuche.
        sp = None
        for _ in range(10):
            try:
                sp = await _graph(client, "POST", "/servicePrincipals", admin_access_token,
                                  json={"appId": app_id})
                break
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in (400, 404, 409):
                    await asyncio.sleep(3)
                    continue
                raise OAuthError(f"Die Unternehmensanwendung ließ sich nicht anlegen: {exc}") from exc
        consent = False
        if sp:
            steps.append("Unternehmensanwendung im Mandanten angelegt.")
            try:
                graph_sp = await _graph(
                    client, "GET",
                    f"/servicePrincipals?$filter=appId eq '{GRAPH_APP_ID}'&$select=id",
                    admin_access_token)
                resource_id = (graph_sp.get("value") or [{}])[0].get("id")
                await _graph(client, "POST", "/oauth2PermissionGrants", admin_access_token, json={
                    "clientId": sp["id"], "consentType": "AllPrincipals",
                    "resourceId": resource_id, "scope": " ".join(GRAPH_SCOPE_IDS.keys()),
                })
                consent = True
                steps.append("Administratorzustimmung für Mail.Send erteilt.")
            except (httpx.HTTPStatusError, KeyError, IndexError) as exc:
                steps.append(f"Zustimmung nicht automatisch erteilt ({exc}). Beim Anmelden des "
                             f"Postfachs fragt Microsoft danach.")
        else:
            steps.append("Unternehmensanwendung noch nicht sichtbar - Microsoft legt sie beim "
                         "ersten Anmelden selbst an.")

    return {"app_id": app_id, "object_id": app.get("id"), "tenant_id": tenant_id,
            "tenant_name": tenant_name, "display_name": app.get("displayName"),
            "personal_accounts": personal_accounts, "consent_granted": consent,
            "registered_by": me.get("userPrincipalName"), "steps": steps}


# =============================================================================
# Zugriffstoken fuer den Versand
# =============================================================================
_access_cache: Dict[tuple, Tuple[str, float]] = {}


def _cache_access(provider: str, client_id: str, account: str, token: Optional[str],
                  expires_in: int) -> None:
    if token:
        _access_cache[(provider, client_id, account)] = (token, time.time() + max(60, expires_in - 120))


async def refresh(oauth: dict) -> dict:
    """Holt mit dem Refresh-Token neue Token. Gibt die Antwort des Anbieters."""
    provider = oauth.get("provider")
    refresh_token = secretbox.open_(oauth.get("refresh_token"))
    if not refresh_token:
        raise OAuthError("Die Anmeldung beim Mail-Anbieter ist nicht mehr lesbar - bitte im "
                         "Assistenten neu anmelden.")
    data = {"grant_type": "refresh_token", "refresh_token": refresh_token,
            "client_id": oauth.get("client_id", "")}
    secret = secretbox.open_(oauth.get("client_secret"))
    if secret:
        data["client_secret"] = secret
    if provider == "google":
        url = GOOGLE_TOKEN
    else:
        url = f"{MS_LOGIN}/{oauth.get('tenant') or 'organizations'}/oauth2/v2.0/token"
        data["scope"] = MS_MAIL_SCOPES
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, data=data)
    if response.status_code >= 400:
        raise OAuthError(f"Die Anmeldung beim Mail-Anbieter ist abgelaufen oder wurde "
                         f"widerrufen ({error_text(response)}). Bitte im Assistenten neu anmelden.")
    return response.json()


async def access_token(config: dict) -> str:
    """Ein gueltiges Zugriffstoken fuer den eingestellten Mail-Weg."""
    oauth = config.get("oauth") or {}
    key = (oauth.get("provider"), oauth.get("client_id"), oauth.get("account"))
    cached = _access_cache.get(key)
    if cached and cached[1] > time.time():
        return cached[0]
    tokens = await refresh(oauth)
    _cache_access(*key, tokens.get("access_token"), int(tokens.get("expires_in") or 3000))
    # Microsoft gibt bei jeder Erneuerung einen neuen Refresh-Token aus. Den
    # festhalten - sonst laeuft die Anmeldung nach 90 Tagen ab.
    new_refresh = tokens.get("refresh_token")
    if new_refresh and new_refresh != secretbox.open_(oauth.get("refresh_token")):
        await _persist_refresh(new_refresh)
    return tokens["access_token"]


async def _persist_refresh(new_refresh: str) -> None:
    from .database import async_session
    from . import mail

    try:
        async with async_session() as session:
            config = await mail.load_config(session)
            oauth = dict(config.get("oauth") or {})
            oauth["refresh_token"] = secretbox.seal(new_refresh)
            oauth["refreshed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
            config["oauth"] = oauth
            await mail._store(session, config)
    except Exception as exc:                                        # defensiv
        logger.warning("Neuer Refresh-Token nicht gespeichert: %s", exc)


async def keepalive() -> Optional[str]:
    """Taeglich einmal erneuern - damit die Anmeldung nicht aus Untaetigkeit verfaellt."""
    from .database import async_session
    from . import mail

    async with async_session() as session:
        config = await mail.load_config(session)
    if config.get("mode") not in ("google", "microsoft"):
        return None
    _access_cache.clear()
    try:
        await access_token(config)
        return None
    except Exception as exc:
        return str(exc)
