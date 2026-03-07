
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
from homeassistant.helpers import entity_registry as er
from homeassistant.components import recorder
from homeassistant.components.recorder import history
import homeassistant.util.dt as dt_util
from datetime import timedelta
from .const import DOMAIN, SIGNAL_NEW_READING, SIGNAL_NEW_TREATMENT, SIGNAL_NEW_DEVICESTATUS

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

class _BasePostEventView(HomeAssistantView):
    """
    Generic POST view that accepts an array of JSON objects (entries, treatments, devicestatus),
    authenticates the request, and dispatches a Home Assistant event/signal for each item.
    """
    requires_auth = False

    def __init__(self, hass: HomeAssistant, get_token_map: Callable[[], dict[str, str]], signal_name: str) -> None:
        self.hass = hass
        self._get_token_map = get_token_map
        self._signal_name = signal_name

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

        items = data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
        _LOGGER.debug("%s: parsed %d items for entry_id=%s", self.__class__.__name__, len(items), entry_id)

        count_ok = 0
        signal = f"{self._signal_name}_{entry_id}"
        
        for item in items:
            # Special parsing only if it's the entries (glucose readings) endpoint,
            # otherwise just dispatch the raw JSON dictionary to the event bus.
            if self._signal_name == SIGNAL_NEW_READING:
                sgv = item.get("sgv") or item.get("mbg")
                if sgv is None:
                    _LOGGER.debug("Entry skipped (no sgv/mbg): %s", item)
                    continue
                epoch_ms = item.get("date")
                payload = {
                    "sgv": float(sgv),
                    "epoch_ms": float(epoch_ms) if epoch_ms is not None else None,
                    "direction": item.get("direction", "unknown"),
                    "raw": item,
                }
            else:
                payload = item

            _LOGGER.debug("Dispatching signal '%s'", signal)
            async_dispatcher_send(self.hass, signal, payload)
            
            # Fire a standard Home Assistant event for treatments/devicestatus so users can automate
            if self._signal_name != SIGNAL_NEW_READING:
                event_type = self._signal_name
                event_data = {
                    "entry_id": entry_id,
                    "payload": payload
                }
                self.hass.bus.async_fire(event_type, event_data)

            count_ok += 1

        _LOGGER.info("%s: accepted %d/%d items (entry_id=%s)", self.__class__.__name__, count_ok, len(items), entry_id)
        return web.json_response({"ok": True, "count": count_ok}, status=HTTPStatus.OK)

    async def get(self, request: web.Request):
        """
        Handle GET requests from Nightscout clients/followers.
        For entries, we query the Home Assistant recorder database to return historical states.
        For others, we return an empty array `[]` so the client doesn't crash. 
        """
        _LOGGER.debug("%s GET received. URL=%s", self.__class__.__name__, request.url)
        
        if self._signal_name != SIGNAL_NEW_READING:
            return web.json_response([], status=HTTPStatus.OK)
            
        token_map = self._get_token_map()
        entry_id = _check_auth(request, token_map)
        if not entry_id:
            _LOGGER.warning("%s GET: authentication failed → 401", self.__class__.__name__)
            return web.Response(status=HTTPStatus.UNAUTHORIZED, text="unauthorized")

        # Get the actual entity_id from the entity registry using the unique_id
        ent_reg = er.async_get(self.hass)
        unique_id = f"{entry_id}_glucose_value"
        entity_id = ent_reg.async_get_entity_id("sensor", DOMAIN, unique_id)
        
        if not entity_id:
            _LOGGER.warning("%s GET: could not find sensor in entity registry for entry_id=%s", self.__class__.__name__, entry_id)
            return web.json_response([], status=HTTPStatus.OK)
        
        try:
            count = int(request.rel_url.query.get("count", 10))
        except ValueError:
            count = 10
            
        # We query the last 24 hours just in case, but limit to `count` items
        start_time = dt_util.utcnow() - timedelta(hours=24)
        
        _LOGGER.debug("%s: Querying HA history for %s since %s", self.__class__.__name__, entity_id, start_time)
        
        # Run DB query in recorder's executor to avoid HA warnings
        states_dict = await recorder.get_instance(self.hass).async_add_executor_job(
            history.get_significant_states,
            self.hass,
            start_time,
            None, # end_time
            [entity_id],
            None, # filters
            True, # include_start_time_state
            True, # significant_changes_only
            False, # minimal_response (we need attributes)
            False, # no_attributes
        )
        
        states = states_dict.get(entity_id, [])
        _LOGGER.debug("%s: Found %d historical states for %s", self.__class__.__name__, len(states), entity_id)

        ns_entries = []
        for s in states:
            if s.state in (None, "unknown", "unavailable"):
                continue
                
            try:
                sgv = float(s.state)
            except ValueError:
                continue
                
            epoch_ms = s.attributes.get("epoch_ms", int(s.last_updated.timestamp() * 1000))
            direction = s.attributes.get("direction", "NONE")
            
            ns_entries.append({
                "sgv": sgv,
                "date": epoch_ms,
                "dateString": s.last_updated.isoformat(),
                "direction": direction,
                "type": "sgv",
                "sysTime": s.last_updated.isoformat()
            })
            
        # Nightscout expects newest first
        ns_entries.reverse()
        # Apply count limit
        ns_entries = ns_entries[:count]
        
        _LOGGER.debug("%s GET returning %d entries", self.__class__.__name__, len(ns_entries))
        return web.json_response(ns_entries, status=HTTPStatus.OK)


class _RouteView(_BasePostEventView):
    """ Helper class to register both /endpoint and /endpoint.json easily """
    pass

class GlucoseNGV1EntriesView(_BasePostEventView):
    url = "/api/v1/entries"
    extra_urls = ["/api/v1/entries.json"]
    name = "api:glucose_ng:v1_entries"
    def __init__(self, hass, get_token_map):
        super().__init__(hass, get_token_map, SIGNAL_NEW_READING)

class GlucoseNGV3EntriesView(_BasePostEventView):
    url = "/api/v3/entries"
    extra_urls = ["/api/v3/entries.json"]
    name = "api:glucose_ng:v3_entries"
    def __init__(self, hass, get_token_map):
        super().__init__(hass, get_token_map, SIGNAL_NEW_READING)

class GlucoseNGV1TreatmentsView(_BasePostEventView):
    url = "/api/v1/treatments"
    extra_urls = ["/api/v1/treatments.json"]
    name = "api:glucose_ng:v1_treatments"
    def __init__(self, hass, get_token_map):
        super().__init__(hass, get_token_map, SIGNAL_NEW_TREATMENT)

class GlucoseNGV3TreatmentsView(_BasePostEventView):
    url = "/api/v3/treatments"
    extra_urls = ["/api/v3/treatments.json"]
    name = "api:glucose_ng:v3_treatments"
    def __init__(self, hass, get_token_map):
        super().__init__(hass, get_token_map, SIGNAL_NEW_TREATMENT)

class GlucoseNGV1DeviceStatusView(_BasePostEventView):
    url = "/api/v1/devicestatus"
    extra_urls = ["/api/v1/devicestatus.json"]
    name = "api:glucose_ng:v1_devicestatus"
    def __init__(self, hass, get_token_map):
        super().__init__(hass, get_token_map, SIGNAL_NEW_DEVICESTATUS)

class GlucoseNGV3DeviceStatusView(_BasePostEventView):
    url = "/api/v3/devicestatus"
    extra_urls = ["/api/v3/devicestatus.json"]
    name = "api:glucose_ng:v3_devicestatus"
    def __init__(self, hass, get_token_map):
        super().__init__(hass, get_token_map, SIGNAL_NEW_DEVICESTATUS)


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


class GlucoseNGStatusView(HomeAssistantView):
    """
    Nightscout v1 status endpoint.
    Some uploaders verify server status before pushing data.
    """
    requires_auth = False
    url = "/api/v1/status"
    extra_urls = ["/api/v1/status.json"]
    name = "api:glucose_ng:v1_status"

    async def get(self, request: web.Request):
        return web.json_response({
            "status": "ok",
            "name": "Home Assistant Glucose NG",
            "version": "14.2.0",  # Fake Nightscout version
            "serverTime": int(time.time() * 1000),
            "settings": {
                "units": "mg/dL",
                "timeFormat": 24,
                "nightMode": False,
                "editMode": True,
                "showRawbg": "never",
                "customTitle": "Home Assistant",
                "theme": "colors",
                "alarmUrgentHigh": True,
                "alarmHigh": True,
                "alarmLow": True,
                "alarmUrgentLow": True,
            }
        }, status=HTTPStatus.OK)


class GlucoseNGVersionView(HomeAssistantView):
    """
    Nightscout v3 version endpoint.
    """
    requires_auth = False
    url = "/api/v3/version"
    extra_urls = ["/api/v3/version.json"]
    name = "api:glucose_ng:v3_version"

    async def get(self, request: web.Request):
        return web.json_response({
            "version": "14.2.0",
            "name": "Home Assistant Glucose NG"
        }, status=HTTPStatus.OK)

# ---------------------------------------------------------------------------
# Registration helpers
# ---------------------------------------------------------------------------

def register_http_views(hass: HomeAssistant, get_token_map: Callable[[], dict[str, str]]) -> None:
    global _registered
    if _registered:
        _LOGGER.debug("HTTP views already registered, skipping")
        return
    
    views = [
        GlucoseNGV1EntriesView(hass, get_token_map),
        GlucoseNGV3EntriesView(hass, get_token_map),
        GlucoseNGV1TreatmentsView(hass, get_token_map),
        GlucoseNGV3TreatmentsView(hass, get_token_map),
        GlucoseNGV1DeviceStatusView(hass, get_token_map),
        GlucoseNGV3DeviceStatusView(hass, get_token_map),
        GlucoseNGV2AuthView(hass, get_token_map),
        GlucoseNGStatusView(),
        GlucoseNGVersionView(),
    ]
    
    for view in views:
        hass.http.register_view(view)
        
    _registered = True
    _LOGGER.debug("Registered HTTP views: %s", ", ".join(v.url for v in views))


def unregister_http_views(hass: HomeAssistant) -> None:
    global _registered
    _registered = False
    _auth_sessions.clear()
    _LOGGER.debug("HTTP views unregistered, sessions cleared")
