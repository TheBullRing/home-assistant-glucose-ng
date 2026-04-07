
from __future__ import annotations
import logging
import hashlib
import time
import uuid
import json
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
from datetime import timedelta, datetime, timezone
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


def _check_session(client_ip: str, req_id: str = "no-id") -> Optional[str]:
    """Return the entry_id for a valid session, or None."""
    record = _auth_sessions.get(client_ip)
    if record is None:
        _LOGGER.debug("[%s] _check_session: no session for ip=%s", req_id, client_ip)
        return None
    entry_id, expiry = record
    remaining = expiry - time.monotonic()
    if remaining > 0:
        _LOGGER.debug("[%s] _check_session: valid session ip=%s → entry_id=%s (%.0fs left)", req_id, client_ip, entry_id, remaining)
        return entry_id
    _LOGGER.debug("[%s] _check_session: expired session for ip=%s", req_id, client_ip)
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
    if not token:
        return None
        
    token_s = token.strip()
    for secret, entry_id in token_map.items():
        # Strip potential whitespace from stored secret for robustness
        secret_s = secret.strip()
        
        # 1. Direct match (plaintext or both are same hash format)
        if token_s == secret_s:
            return entry_id
            
        # 2. Match token against SHA1 of stored secret
        if token_s.lower() == _sha1(secret_s).lower():
            return entry_id
            
    return None


def _check_auth(request: web.Request, token_map: dict[str, str], req_id: str = "no-id") -> Optional[str]:
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
    _LOGGER.debug("[%s] _check_auth: client_ip=%s, %d entry/entries registered", req_id, client_ip, len(token_map))

    if not token_map:
        _LOGGER.warning("[%s] _check_auth: no entries registered → deny", req_id)
        return None

    # --- 1. IP session ---
    entry_id = _check_session(client_ip, req_id)
    if entry_id:
        _LOGGER.debug("[%s] _check_auth: authorized via IP session → entry_id=%s ✓", req_id, entry_id)
        return entry_id

    # --- 2. api-secret header ---
    api_sec = request.headers.get("api-secret")
    if api_sec is not None:
        api_sec_s = api_sec.strip()
        _LOGGER.debug("[%s] _check_auth: api-secret header: '%s' (len=%d)", 
                      req_id,
                      api_sec_s[:4] + "***" + api_sec_s[-4:] if len(api_sec_s) > 8 else "***", 
                      len(api_sec_s))
        
        for secret, eid in token_map.items():
            secret_s = secret.strip()
            
            # Masked comparison logging for debugging
            m_sec = secret_s[:2] + "***" + secret_s[-2:] if len(secret_s) > 4 else "***"
            m_sha = _sha1(secret_s)
            m_sha_disp = m_sha[:4] + "***" + m_sha[-4:]
            
            _LOGGER.debug("[%s] _check_auth: comparing api-secret against entry '%s': direct_match=%s, sha1_match=%s",
                          req_id, eid, (api_sec_s == secret_s), (api_sec_s.lower() == m_sha.lower()))

            if api_sec_s == secret_s or api_sec_s.lower() == m_sha.lower():
                _LOGGER.debug("[%s] _check_auth: matched api-secret → entry_id=%s ✓", req_id, eid)
                return eid
        _LOGGER.debug("[%s] _check_auth: api-secret did not match any entry", req_id)

    # --- 3. Authorization: Bearer ---
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1].strip()
        _LOGGER.debug("[%s] _check_auth: Bearer token detected (masked)", req_id)
        entry_id = _find_entry_by_token(token_map, token)
        if entry_id:
            _LOGGER.debug("[%s] _check_auth: matched Bearer → entry_id=%s ✓", req_id, entry_id)
            return entry_id
        _LOGGER.debug("[%s] _check_auth: Bearer did not match any entry", req_id)

    # --- 4. X-Shared-Secret ---
    xsec = request.headers.get("X-Shared-Secret")
    if xsec:
        _LOGGER.debug("[%s] _check_auth: X-Shared-Secret detected (masked)", req_id)
        entry_id = _find_entry_by_token(token_map, xsec)
        if entry_id:
            _LOGGER.debug("[%s] _check_auth: matched X-Shared-Secret → entry_id=%s ✓", req_id, entry_id)
            return entry_id
        _LOGGER.debug("[%s] _check_auth: X-Shared-Secret did not match any entry", req_id)

    # --- 5. ?token= query param ---
    qtoken = request.rel_url.query.get("token")
    if qtoken:
        _LOGGER.debug("[%s] _check_auth: ?token= detected (masked)", req_id)
        entry_id = _find_entry_by_token(token_map, qtoken)
        if entry_id:
            _LOGGER.debug("[%s] _check_auth: matched ?token= → entry_id=%s ✓", req_id, entry_id)
            return entry_id
        _LOGGER.debug("[%s] _check_auth: ?token= did not match any entry", req_id)

    _LOGGER.warning(
        "[%s] _check_auth: UNAUTHORIZED — no match found. client_ip=%s | headers=%s | query=%s",
        req_id,
        client_ip,
        {k: (v if k.lower() not in ("api-secret", "authorization", "x-shared-secret") else "***") 
         for k, v in request.headers.items()},
        {k: "***" for k in request.rel_url.query},
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
        req_id = uuid.uuid4().hex[:6]
        _LOGGER.debug(
            "[%s] %s POST received. URL=%s, Headers=%s",
            req_id, self.__class__.__name__, request.url, dict(request.headers),
        )

        token_map = self._get_token_map()
        entry_id = _check_auth(request, token_map, req_id)
        if not entry_id:
            _LOGGER.warning("[%s] %s: authentication failed → 401", req_id, self.__class__.__name__)
            return web.Response(status=HTTPStatus.UNAUTHORIZED, text="unauthorized")

        try:
            body = await request.text()
            _LOGGER.debug("[%s] %s: raw request body: %s", req_id, self.__class__.__name__, body)
            data = json.loads(body)
        except Exception as exc:
            _LOGGER.error("[%s] %s: failed to parse JSON: %s", req_id, self.__class__.__name__, exc)
            return web.Response(status=HTTPStatus.BAD_REQUEST, text="invalid json")

        items = data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
        _LOGGER.debug("[%s] %s: parsed %d items for entry_id=%s", req_id, self.__class__.__name__, len(items), entry_id)

        count_ok = 0
        signal = f"{self._signal_name}_{entry_id}"

        if self._signal_name == SIGNAL_NEW_READING:
            try:
                # Ensure we sort by integer timestamp, defaulting to 0 if missing/invalid
                items.sort(key=lambda x: int(x.get("date") or 0))
                _LOGGER.debug("[%s] %s: Sorted %d entries chronologically", req_id, self.__class__.__name__, len(items))
            except Exception as exc:
                _LOGGER.error("[%s] %s: Sorting failed: %s", req_id, self.__class__.__name__, exc)

        for item in items:
            # Special parsing only if it's the entries (glucose readings) endpoint,
            # otherwise just dispatch the raw JSON dictionary to the event bus.
            if self._signal_name == SIGNAL_NEW_READING:
                sgv = item.get("sgv") or item.get("mbg")
                if sgv is None:
                    _LOGGER.debug("[%s] Entry skipped (no sgv/mbg): %s", req_id, item)
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

            _LOGGER.debug("[%s] Dispatching signal '%s'", req_id, signal)
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

        _LOGGER.info("[%s] %s: accepted %d/%d items (entry_id=%s)", req_id, self.__class__.__name__, count_ok, len(items), entry_id)
        
        resp_data = {"ok": True, "count": count_ok}
        _LOGGER.debug("[%s] %s: raw response payload: %s", req_id, self.__class__.__name__, json.dumps(resp_data))
        return web.json_response(resp_data, status=HTTPStatus.OK)

    async def get(self, request: web.Request):
        """
        Handle GET requests from Nightscout clients/followers.
        For entries, we query the Home Assistant recorder database to return historical states.
        For treatments, we query the Home Assistant recorder database to return historical event data.
        For others, we return an empty array `[]` so the client doesn't crash. 
        """
        req_id = uuid.uuid4().hex[:6]
        _LOGGER.debug("[%s] %s GET received. URL=%s, Headers=%s", req_id, self.__class__.__name__, request.url, dict(request.headers))
        
        if self._signal_name not in (SIGNAL_NEW_READING, SIGNAL_NEW_TREATMENT):
            _LOGGER.debug("[%s] %s: unsupported GET endpoint for signal %s. returning empty [].", req_id, self.__class__.__name__, self._signal_name)
            return web.json_response([], status=HTTPStatus.OK)
            
        token_map = self._get_token_map()
        entry_id = _check_auth(request, token_map, req_id)
        if not entry_id:
            _LOGGER.warning("[%s] %s GET: authentication failed → 401", req_id, self.__class__.__name__)
            return web.Response(status=HTTPStatus.UNAUTHORIZED, text="unauthorized")

        ent_reg = er.async_get(self.hass)

        if self._signal_name == SIGNAL_NEW_READING:
            unique_id = f"{entry_id}_glucose_value"
            entity_id = ent_reg.async_get_entity_id("sensor", DOMAIN, unique_id)
        elif self._signal_name == SIGNAL_NEW_TREATMENT:
            unique_id = f"{entry_id}_glucose_treatment"
            entity_id = ent_reg.async_get_entity_id("event", DOMAIN, unique_id)
        else:
            return web.json_response([], status=HTTPStatus.OK)
        
        if not entity_id:
            _LOGGER.warning("[%s] %s GET: could not find entity in registry for entry_id=%s", req_id, self.__class__.__name__, entry_id)
            return web.json_response([], status=HTTPStatus.OK)
        
        try:
            # OpenAGP uses limit, Nightscout standard uses count
            limit_val = request.rel_url.query.get("limit") or request.rel_url.query.get("count")
            count = int(limit_val) if limit_val else 10
        except ValueError:
            count = 10
            
        def _parse_date(date_str):
            try:
                epoch = float(date_str)
                if epoch > 1e11: # milliseconds
                    epoch = epoch / 1000.0
                return datetime.fromtimestamp(epoch, tz=timezone.utc)
            except ValueError:
                return dt_util.parse_datetime(date_str)

        start_time = None
        query_date_gte = (
            request.rel_url.query.get("date$gte") or 
            request.rel_url.query.get("created_at$gte") or 
            request.rel_url.query.get("find[date][$gte]") or 
            request.rel_url.query.get("find[created_at][$gte]")
        )
        if query_date_gte:
            start_time = _parse_date(query_date_gte)
            
        if not start_time:
            start_time = dt_util.utcnow() - timedelta(hours=24)

        end_time = None
        query_date_lte = (
            request.rel_url.query.get("date$lte") or 
            request.rel_url.query.get("created_at$lte") or 
            request.rel_url.query.get("find[date][$lte]") or 
            request.rel_url.query.get("find[created_at][$lte]")
        )
        if query_date_lte:
            end_time = _parse_date(query_date_lte)
        
        _LOGGER.debug("[%s] %s: Querying HA history for %s since %s to %s", req_id, self.__class__.__name__, entity_id, start_time, end_time)
        
        states_dict = await recorder.get_instance(self.hass).async_add_executor_job(
            history.get_significant_states,
            self.hass,
            start_time,
            end_time, # end_time
            [entity_id],
            None, # filters
            True, # include_start_time_state
            True, # significant_changes_only
            False, # minimal_response (we need attributes)
            False, # no_attributes
        )
        
        states = states_dict.get(entity_id, [])
        _LOGGER.debug("[%s] %s: Found %d historical states for %s", req_id, self.__class__.__name__, len(states), entity_id)

        ns_entries = []
        seen_epochs = set()
        last_sgv = None

        for s in states:
            if s.state in (None, "unknown", "unavailable"):
                continue

            if self._signal_name == SIGNAL_NEW_READING:
                try:
                    sgv = float(s.state)
                except ValueError:
                    continue
                    
                epoch_ms = s.attributes.get("epoch_ms")
                is_fallback = False
                if epoch_ms is None:
                    epoch_ms = int(s.last_updated.timestamp() * 1000)
                    is_fallback = True
                    
                if epoch_ms in seen_epochs:
                    continue
                    
                # If we don't have exact epoch_ms and SGV hasn't changed, assume it's a duplicate HA state update
                if is_fallback and sgv == last_sgv:
                    continue
                    
                seen_epochs.add(epoch_ms)
                last_sgv = sgv
                
                direction = s.attributes.get("direction", "NONE")
                
                entry_dict = {
                    "sgv": int(sgv) if sgv.is_integer() else sgv,
                    "date": int(epoch_ms),
                    "dateString": s.last_updated.isoformat(),
                    "direction": direction,
                    "type": s.attributes.get("type", "sgv"),
                    "sysTime": s.last_updated.isoformat()
                }
                
                for key in ("device", "noise", "rssi", "filtered", "unfiltered"):
                    if key in s.attributes:
                        entry_dict[key] = s.attributes[key]
                        
                ns_entries.append(entry_dict)

            elif self._signal_name == SIGNAL_NEW_TREATMENT:
                # Treatments are stored as EventEntities inside attributes["event"] (sometimes with an ID or directly)
                event_type_str = s.attributes.get("event_type", "unknown")
                # Because the event platform might stash payload in attributes directly or under `event_type` 
                # (For generic EventEntities, it puts them directly as extra_state_attributes or they come from the trigger event)
                # But since our GlucoseTreatmentEvent triggers `self._trigger_event("treatment", treatment)`
                # The payload goes to `s.attributes.get("eventType")` natively because we passed raw dict keys.
                # Actually during EventEntity update if we just pass a dict, HA sets the attributes. Let's extract.
                
                if "eventType" not in s.attributes:
                    continue # Not a valid treatment event payload
                
                treatment_dict = {
                    "eventType": s.attributes.get("eventType"),
                    "created_at": s.attributes.get("created_at", s.last_updated.isoformat())
                }

                # Copy other standard treatment fields from attributes if they exist
                for key in ("insulin", "carbs", "notes", "duration", "percent", "profile", "reason", "absolute", "rate"):
                    if key in s.attributes:
                        treatment_dict[key] = s.attributes[key]
                        
                ns_entries.append(treatment_dict)
            
        # Sorting: history is ascending (oldest first)
        sort_val = request.rel_url.query.get("sort", "")
        if sort_val in ("date", "created_at", "+date", "+created_at", "date asc", "created_at asc"):
            # Ascending requested
            pass
        else:
            # Default to newest first
            ns_entries.reverse()

        # Apply count limit
        ns_entries = ns_entries[:count]
        
        _LOGGER.debug("[%s] %s GET returning %d entries", req_id, self.__class__.__name__, len(ns_entries))
        _LOGGER.debug("[%s] %s GET raw response payload: %s", req_id, self.__class__.__name__, json.dumps(ns_entries))
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
        now_ms = int(time.time() * 1000)
        now_iso = dt_util.utcnow().isoformat()
        
        return web.json_response({
            "status": "ok",
            "name": "nightscout",
            "version": "15.0.6",
            "serverTime": now_iso,
            "serverTimeEpoch": now_ms,
            "apiEnabled": True,
            "careportalEnabled": True,
            "boluscalcEnabled": True,
            "settings": {
                "units": "mg/dl",
                "timeFormat": 24,
                "dayStart": 7,
                "dayEnd": 21,
                "nightMode": False,
                "editMode": True,
                "showRawbg": "never",
                "customTitle": "Nightscout",
                "theme": "default",
                "alarmUrgentHigh": True,
                "alarmUrgentHighMins": [30, 60, 90, 120],
                "alarmHigh": True,
                "alarmHighMins": [30, 60, 90, 120],
                "alarmLow": True,
                "alarmLowMins": [15, 30, 45, 60],
                "alarmUrgentLow": True,
                "alarmUrgentLowMins": [15, 30, 45],
                "alarmUrgentMins": [30, 60, 90, 120],
                "alarmWarnMins": [30, 60, 90, 120],
                "alarmTimeagoWarn": True,
                "alarmTimeagoWarnMins": 15,
                "alarmTimeagoUrgent": True,
                "alarmTimeagoUrgentMins": 30,
                "alarmPumpBatteryLow": False,
                "language": "en",
                "scaleY": "log",
                "showPlugins": "dbsize delta direction upbat",
                "showForecast": "ar2",
                "focusHours": 3,
                "heartbeat": 60,
                "baseURL": "",
                "authDefaultRoles": "denied",
                "thresholds": {"bgHigh": 260, "bgTargetTop": 180, "bgTargetBottom": 80, "bgLow": 55},
                "insecureUseHttp": True,
                "secureHstsHeader": True,
                "secureHstsHeaderIncludeSubdomains": False,
                "secureHstsHeaderPreload": False,
                "secureCsp": False,
                "deNormalizeDates": False,
                "showClockDelta": False,
                "showClockLastTime": False,
                "frameUrl1": "",
                "frameUrl2": "",
                "frameUrl3": "",
                "frameUrl4": "",
                "frameUrl5": "",
                "frameUrl6": "",
                "frameUrl7": "",
                "frameUrl8": "",
                "frameName1": "",
                "frameName2": "",
                "frameName3": "",
                "frameName4": "",
                "frameName5": "",
                "frameName6": "",
                "frameName7": "",
                "frameName8": "",
                "authFailDelay": 5000,
                "adminNotifiesEnabled": True,
                "authenticationPromptOnLoad": False,
                "DEFAULT_FEATURES": ["bgnow", "delta", "direction", "timeago", "devicestatus", "upbat", "errorcodes", "profile", "bolus", "dbsize", "runtimestate", "basal", "careportal"],
                "alarmTypes": ["predict"],
                "enable": ["careportal", "basal", "iob", "cob", "bwp", "cage", "iage", "sage", "boluscalc", "food", "rawbg", "treatmentnotify", "bgnow", "delta", "direction", "timeago", "devicestatus", "upbat", "errorcodes", "profile", "bolus", "dbsize", "runtimestate", "ar2"]
            },
            "extendedSettings": {"devicestatus": {"advanced": True, "days": 1}},
            "authorized": {
                "token": "mock-authorized-token",
                "sub": "user",
                "permissionGroups": [["*:*:read"], []],
                "iat": int(now_ms / 1000),
                "exp": int(now_ms / 1000) + 86400
            },
            "runtimeState": "loaded"
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
