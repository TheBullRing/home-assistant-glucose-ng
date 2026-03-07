
from __future__ import annotations
import logging
import hashlib
import time
from typing import Callable, Optional
from http import HTTPStatus
from aiohttp import web
from homeassistant.core import HomeAssistant
from homeassistant.components.http import HomeAssistantView
from homeassistant.helpers.dispatcher import async_dispatcher_send
from .const import SIGNAL_NEW_READING

_LOGGER = logging.getLogger(__name__)
_registered = False  # Views are registered once for all entries

# ---------------------------------------------------------------------------
# IP-based session store
#
# Maps client_ip -> entry_id. Populated when a client passes the GET auth
# check. Used on POST to route readings to the correct entry's sensors.
#
# Background: HA's own auth middleware strips/empties the Authorization header
# before our view sees it, making Bearer-based auth unreliable. IP sessions
# are the pragmatic workaround.
# ---------------------------------------------------------------------------
SESSION_TTL_SECONDS = 300  # 5 minutes

_auth_sessions: dict[str, tuple[str, float]] = {}  # ip -> (entry_id, expiry)


def _get_client_ip(request: web.Request) -> str:
    return (
        request.headers.get("X-Real-IP")
        or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or request.remote
        or "unknown"
    )


def _grant_session(client_ip: str, entry_id: str) -> None:
    expiry = time.monotonic() + SESSION_TTL_SECONDS
    _auth_sessions[client_ip] = (entry_id, expiry)
    _LOGGER.debug("Session granted: ip=%s → entry_id=%s (TTL=%ds)", client_ip, entry_id, SESSION_TTL_SECONDS)


def _check_session(client_ip: str) -> Optional[str]:
    """Return the entry_id for a valid session, or None."""
    record = _auth_sessions.get(client_ip)
    if record is None:
        _LOGGER.debug("_check_session: no session for ip=%s", client_ip)
        return None
    entry_id, expiry = record
    remaining = expiry - time.monotonic()
    if remaining > 0:
        _LOGGER.debug("_check_session: valid session ip=%s → entry_id=%s (%.0fs left)", client_ip, entry_id, remaining)
        return entry_id
    _LOGGER.debug("_check_session: expired session for ip=%s", client_ip)
    _auth_sessions.pop(client_ip, None)
    return None


def _purge_expired_sessions() -> None:
    now = time.monotonic()
    expired = [ip for ip, (_, exp) in _auth_sessions.items() if exp <= now]
    for ip in expired:
        _auth_sessions.pop(ip, None)
    if expired:
        _LOGGER.debug("Purged %d expired session(s)", len(expired))


def _sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def _find_entry_by_token(token_map: dict[str, str], token: str) -> Optional[str]:
    """
    Given a raw token value, find the matching entry_id.
    token_map: {shared_secret: entry_id}
    Accepts both plaintext and SHA1(plaintext) as the token.
    """
    for secret, entry_id in token_map.items():
        if token == secret or token.lower() == _sha1(secret).lower():
            return entry_id
    return None


def _check_auth(request: web.Request, token_map: dict[str, str]) -> Optional[str]:
    """
    Authenticate the request against all registered entries.
    Returns the matching entry_id, or None if unauthorized.

    Strategy (in order):
      1. No entries configured → deny.
      2. IP session from prior GET auth  (primary path for Juggluco).
      3. Header api-secret (plain or SHA1).
      4. Authorization: Bearer <token>.
      5. X-Shared-Secret header.
      6. ?token= query param.
    """
    _purge_expired_sessions()
    client_ip = _get_client_ip(request)
    _LOGGER.debug("_check_auth: client_ip=%s, %d entry/entries registered", client_ip, len(token_map))

    if not token_map:
        _LOGGER.warning("_check_auth: no entries registered → deny")
        return None

    # --- 1. IP session ---
    entry_id = _check_session(client_ip)
    if entry_id:
        _LOGGER.debug("_check_auth: authorized via IP session → entry_id=%s ✓", entry_id)
        return entry_id

    # --- 2. api-secret header ---
    api_sec = request.headers.get("api-secret")
    if api_sec is not None:
        _LOGGER.debug("_check_auth: api-secret header: '%s'", api_sec)
        for secret, eid in token_map.items():
            if api_sec == secret or api_sec.lower() == _sha1(secret).lower():
                _LOGGER.debug("_check_auth: matched api-secret → entry_id=%s ✓", eid)
                return eid
        _LOGGER.debug("_check_auth: api-secret did not match any entry")

    # --- 3. Authorization: Bearer ---
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1].strip()
        _LOGGER.debug("_check_auth: Bearer token: '%s'", token)
        entry_id = _find_entry_by_token(token_map, token)
        if entry_id:
            _LOGGER.debug("_check_auth: matched Bearer → entry_id=%s ✓", entry_id)
            return entry_id
        _LOGGER.debug("_check_auth: Bearer did not match any entry")

    # --- 4. X-Shared-Secret ---
    xsec = request.headers.get("X-Shared-Secret")
    if xsec:
        entry_id = _find_entry_by_token(token_map, xsec)
        if entry_id:
            _LOGGER.debug("_check_auth: matched X-Shared-Secret → entry_id=%s ✓", entry_id)
            return entry_id
        _LOGGER.debug("_check_auth: X-Shared-Secret did not match any entry")

    # --- 5. ?token= query param ---
    qtoken = request.rel_url.query.get("token")
    if qtoken:
        entry_id = _find_entry_by_token(token_map, qtoken)
        if entry_id:
            _LOGGER.debug("_check_auth: matched ?token= → entry_id=%s ✓", entry_id)
            return entry_id
        _LOGGER.debug("_check_auth: ?token= did not match any entry")

    _LOGGER.warning(
        "_check_auth: UNAUTHORIZED — no match found. client_ip=%s | headers=%s | query=%s",
        client_ip,
        dict(request.headers),
        dict(request.rel_url.query),
    )
    return None


# ---------------------------------------------------------------------------
# HTTP Views
# ---------------------------------------------------------------------------

class _BaseEntriesView(HomeAssistantView):
    requires_auth = False
    name = "api:glucose_ng:entries_base"

    def __init__(self, hass: HomeAssistant, get_token_map: Callable[[], dict[str, str]]) -> None:
        self.hass = hass
        self._get_token_map = get_token_map

    async def post(self, request: web.Request):
        _LOGGER.debug(
            "%s POST received. URL=%s, Headers=%s",
            self.__class__.__name__, request.url, dict(request.headers),
        )

        token_map = self._get_token_map()
        entry_id = _check_auth(request, token_map)
        if not entry_id:
            _LOGGER.warning("%s: authentication failed → 401", self.__class__.__name__)
            return web.Response(status=HTTPStatus.UNAUTHORIZED, text="unauthorized")

        try:
            import json as _json
            body = await request.text()
            _LOGGER.debug("%s: raw body: %s", self.__class__.__name__, body)
            data = _json.loads(body)
        except Exception as exc:
            _LOGGER.error("%s: failed to parse JSON: %s", self.__class__.__name__, exc)
            return web.Response(status=HTTPStatus.BAD_REQUEST, text="invalid json")

        entries = data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
        _LOGGER.debug("%s: parsed %d entries for entry_id=%s", self.__class__.__name__, len(entries), entry_id)

        count_ok = 0
        signal = f"{SIGNAL_NEW_READING}_{entry_id}"
        for e in entries:
            sgv = e.get("sgv") or e.get("mbg")
            if sgv is None:
                _LOGGER.debug("Entry skipped (no sgv/mbg): %s", e)
                continue
            epoch_ms = e.get("date")
            reading = {
                "sgv": float(sgv),
                "epoch_ms": float(epoch_ms) if epoch_ms is not None else None,
                "direction": e.get("direction", "unknown"),
                "raw": e,
            }
            _LOGGER.debug(
                "Dispatching signal '%s': sgv=%.1f direction=%s",
                signal, reading["sgv"], reading["direction"],
            )
            async_dispatcher_send(self.hass, signal, reading)
            count_ok += 1

        _LOGGER.info("%s: accepted %d/%d entries (entry_id=%s)", self.__class__.__name__, count_ok, len(entries), entry_id)
        return web.json_response({"ok": True, "count": count_ok}, status=HTTPStatus.OK)


class GlucoseNGV1EntriesView(_BaseEntriesView):
    url = "/api/v1/entries"
    name = "api:glucose_ng:v1_entries"


class GlucoseNGV3EntriesView(_BaseEntriesView):
    url = "/api/v3/entries"
    name = "api:glucose_ng:v3_entries"


class GlucoseNGV2AuthView(HomeAssistantView):
    """
    Nightscout v2 authorization endpoint.
    On success, grants an IP session mapped to the matching entry_id.
    """
    requires_auth = False
    url = r"/api/v2/authorization/request/{token}"
    name = "api:glucose_ng:v2_auth"

    def __init__(self, hass: HomeAssistant, get_token_map: Callable[[], dict[str, str]]):
        self.hass = hass
        self._get_token_map = get_token_map

    async def get(self, request: web.Request, token: str):
        client_ip = _get_client_ip(request)
        _LOGGER.debug("GlucoseNGV2AuthView GET. client_ip=%s, token='%s'", client_ip, token)

        token_map = self._get_token_map()
        entry_id = _find_entry_by_token(token_map, token)

        if entry_id:
            _LOGGER.debug("GlucoseNGV2AuthView: token matched entry_id=%s ✓", entry_id)
            _grant_session(client_ip, entry_id)
            issued_token = token  # echo back the raw token Juggluco sent
        else:
            _LOGGER.warning(
                "GlucoseNGV2AuthView: token '%s' did not match any registered entry. "
                "Available entries: %d. Returning 200 anyway but POST will fail.",
                token, len(token_map),
            )
            issued_token = token

        return web.json_response(
            {
                "status": 200,
                "result": "ok",
                "token": issued_token,
                "roles": ["readable", "devicestatus-upload"],
            },
            status=HTTPStatus.OK,
        )


# ---------------------------------------------------------------------------
# Registration helpers
# ---------------------------------------------------------------------------

def register_http_views(hass: HomeAssistant, get_token_map: Callable[[], dict[str, str]]) -> None:
    global _registered
    if _registered:
        _LOGGER.debug("HTTP views already registered, skipping")
        return
    v1 = GlucoseNGV1EntriesView(hass, get_token_map)
    v3 = GlucoseNGV3EntriesView(hass, get_token_map)
    v2 = GlucoseNGV2AuthView(hass, get_token_map)
    hass.http.register_view(v1)
    hass.http.register_view(v3)
    hass.http.register_view(v2)
    _registered = True
    _LOGGER.debug("Registered HTTP views: %s, %s, %s", v1.url, v3.url, v2.url)


def unregister_http_views(hass: HomeAssistant) -> None:
    global _registered
    _registered = False
    _auth_sessions.clear()
    _LOGGER.debug("HTTP views unregistered, sessions cleared")
