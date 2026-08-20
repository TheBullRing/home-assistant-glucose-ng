
from __future__ import annotations
import asyncio
import hashlib
import hmac
import json
import logging
import time
import uuid
from collections import defaultdict
from datetime import timedelta, datetime, timezone
from http import HTTPStatus
from typing import Callable, Optional

from aiohttp import web
from homeassistant.components import recorder
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.recorder import history
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
import homeassistant.util.dt as dt_util

from .const import DOMAIN, SIGNAL_NEW_READING, SIGNAL_NEW_TREATMENT, SIGNAL_NEW_DEVICESTATUS

_LOGGER = logging.getLogger(__name__)
_registered = False      # Views are registered once for all entries
_registered_prefix = ""  # Tracks which prefix the views were registered under

MAX_BODY_BYTES = 512 * 1024  # 512 KB — guards against memory exhaustion attacks
MAX_ITEMS = 500               # max items processed per POST request
MAX_HISTORY_COUNT = 1000      # max entries returned per GET request

# ---------------------------------------------------------------------------
# Brute-force rate limiting
# ---------------------------------------------------------------------------

_FAIL_WINDOW_SECONDS = 60   # sliding window length
_FAIL_MAX = 10               # max failures allowed per IP per window
_FAIL_DELAY_SECONDS = 2      # sleep added after threshold is reached

# ip -> list of failure timestamps (monotonic)
_fail_log: dict[str, list[float]] = defaultdict(list)


def _record_auth_failure(remote_ip: str) -> bool:
    """Record a failure for remote_ip. Returns True if the rate limit is now exceeded."""
    now = time.monotonic()
    timestamps = _fail_log[remote_ip]
    # Discard entries outside the window
    _fail_log[remote_ip] = [t for t in timestamps if now - t < _FAIL_WINDOW_SECONDS]
    _fail_log[remote_ip].append(now)
    return len(_fail_log[remote_ip]) > _FAIL_MAX


def _clear_auth_failures(remote_ip: str) -> None:
    _fail_log.pop(remote_ip, None)


def _sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def _find_entry_by_token(token_map: dict[str, str], token: str) -> Optional[str]:
    """
    Given a raw token value, find the matching entry_id.
    token_map: {sha1(shared_secret) → entry_id}  (keys are digests, never plaintext)
    Accepts both plaintext and SHA1(plaintext) as the token sent by the uploader.
    """
    if not token:
        return None

    token_s = token.strip()
    # Normalise the incoming token to its SHA-1 digest for comparison.
    # Uploaders (e.g. Juggluco) may send either the plaintext secret or its SHA-1.
    token_digest = _sha1(token_s).lower()
    token_lower = token_s.lower()

    for stored_digest, entry_id in token_map.items():
        stored_lower = stored_digest.strip().lower()

        # 1. Incoming token is already a SHA-1 digest — compare directly
        if hmac.compare_digest(token_lower, stored_lower):
            return entry_id

        # 2. Incoming token is plaintext — compare its SHA-1 against the stored digest
        if hmac.compare_digest(token_digest, stored_lower):
            return entry_id

    return None


def _check_auth(request: web.Request, token_map: dict[str, str], req_id: str = "no-id") -> Optional[str]:
    """
    Authenticate the request against all registered entries.
    Returns the matching entry_id, or None if unauthorized.

    The shared secret must be presented on every request via one of:
      1. api-secret header (plain or SHA1).
      2. Authorization: Bearer <token>.
      3. X-Shared-Secret header.
      4. ?token= query param.
    """
    _LOGGER.debug("[%s] _check_auth: %d entry/entries registered", req_id, len(token_map))

    if not token_map:
        _LOGGER.warning("[%s] _check_auth: no entries registered → deny", req_id)
        return None

    # --- 1. api-secret header ---
    api_sec = request.headers.get("api-secret")
    if api_sec is not None:
        api_sec_s = api_sec.strip()
        entry_id = _find_entry_by_token(token_map, api_sec_s)
        if entry_id:
            _LOGGER.debug("[%s] _check_auth: matched api-secret → entry_id=%s ✓", req_id, entry_id)
            return entry_id
        _LOGGER.debug("[%s] _check_auth: api-secret did not match any entry", req_id)

    # --- 2. Authorization: Bearer ---
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1].strip()
        entry_id = _find_entry_by_token(token_map, token)
        if entry_id:
            _LOGGER.debug("[%s] _check_auth: matched Bearer → entry_id=%s ✓", req_id, entry_id)
            return entry_id
        _LOGGER.debug("[%s] _check_auth: Bearer did not match any entry", req_id)

    # --- 3. X-Shared-Secret ---
    xsec = request.headers.get("X-Shared-Secret")
    if xsec:
        entry_id = _find_entry_by_token(token_map, xsec)
        if entry_id:
            _LOGGER.debug("[%s] _check_auth: matched X-Shared-Secret → entry_id=%s ✓", req_id, entry_id)
            return entry_id
        _LOGGER.debug("[%s] _check_auth: X-Shared-Secret did not match any entry", req_id)

    # --- 4. ?token= query param ---
    qtoken = request.rel_url.query.get("token")
    if qtoken:
        entry_id = _find_entry_by_token(token_map, qtoken)
        if entry_id:
            _LOGGER.debug("[%s] _check_auth: matched ?token= → entry_id=%s ✓", req_id, entry_id)
            return entry_id
        _LOGGER.debug("[%s] _check_auth: ?token= did not match any entry", req_id)

    _LOGGER.warning(
        "[%s] _check_auth: UNAUTHORIZED — no match found.",
        req_id,
    )
    return None


async def _check_auth_with_ratelimit(
    request: web.Request,
    token_map: dict[str, str],
    req_id: str = "no-id",
) -> Optional[str]:
    """
    Wrapper around _check_auth that adds per-IP brute-force protection.
    Uses request.remote (TCP peer address — not spoofable via headers).
    On success clears the failure counter for that IP.
    After _FAIL_MAX failures in _FAIL_WINDOW_SECONDS, inserts a delay before responding.
    """
    remote_ip = request.remote or "unknown"
    entry_id = _check_auth(request, token_map, req_id)
    if entry_id:
        _clear_auth_failures(remote_ip)
        return entry_id

    exceeded = _record_auth_failure(remote_ip)
    if exceeded:
        _LOGGER.warning(
            "[%s] Rate limit exceeded for %s — adding %ds delay",
            req_id, remote_ip, _FAIL_DELAY_SECONDS,
        )
        await asyncio.sleep(_FAIL_DELAY_SECONDS)
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
            "[%s] %s POST received. URL=%s",
            req_id, self.__class__.__name__, request.url,
        )

        token_map = self._get_token_map()
        entry_id = await _check_auth_with_ratelimit(request, token_map, req_id)
        if not entry_id:
            _LOGGER.warning("[%s] %s: authentication failed → 401", req_id, self.__class__.__name__)
            return web.Response(status=HTTPStatus.UNAUTHORIZED, text="unauthorized")

        try:
            body = await request.text()
            if len(body.encode()) > MAX_BODY_BYTES:
                _LOGGER.warning("[%s] %s: request body too large (%d bytes) → 413", req_id, self.__class__.__name__, len(body.encode()))
                return web.Response(status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE, text="payload too large")
            _LOGGER.debug("[%s] %s: raw request body: %s", req_id, self.__class__.__name__, body)
            data = json.loads(body)
        except Exception as exc:
            _LOGGER.error("[%s] %s: failed to parse JSON: %s", req_id, self.__class__.__name__, exc)
            return web.Response(status=HTTPStatus.BAD_REQUEST, text="invalid json")

        items = data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
        if len(items) > MAX_ITEMS:
            _LOGGER.warning("[%s] %s: too many items (%d > %d), truncating", req_id, self.__class__.__name__, len(items), MAX_ITEMS)
            items = items[:MAX_ITEMS]
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
                # Whitelist only the fields we actually use — never store the
                # full client-controlled dict as a sensor attribute.
                _READING_FIELDS = ("device", "noise", "rssi", "type", "filtered", "unfiltered")
                payload = {
                    "sgv": float(sgv),
                    "epoch_ms": float(epoch_ms) if epoch_ms is not None else None,
                    "direction": item.get("direction", "unknown"),
                    **{k: item[k] for k in _READING_FIELDS if k in item},
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
        return web.json_response(resp_data, status=HTTPStatus.OK)

    async def get(self, request: web.Request):
        """
        Handle GET requests from Nightscout clients/followers.
        For entries, we query the Home Assistant recorder database to return historical states.
        For treatments, we query the Home Assistant recorder database to return historical event data.
        For others, we return an empty array `[]` so the client doesn't crash.
        """
        req_id = uuid.uuid4().hex[:6]
        _LOGGER.debug("[%s] %s GET received. URL=%s", req_id, self.__class__.__name__, request.url)

        if self._signal_name not in (SIGNAL_NEW_READING, SIGNAL_NEW_TREATMENT):
            _LOGGER.debug("[%s] %s: unsupported GET endpoint for signal %s. returning empty [].", req_id, self.__class__.__name__, self._signal_name)
            return web.json_response([], status=HTTPStatus.OK)

        token_map = self._get_token_map()
        entry_id = await _check_auth_with_ratelimit(request, token_map, req_id)
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
            count = min(int(limit_val), MAX_HISTORY_COUNT) if limit_val else 10
        except ValueError:
            count = 10

        def _parse_date(date_str):
            try:
                epoch = float(date_str)
                if epoch > 1e11:  # milliseconds
                    epoch = epoch / 1000.0
                return datetime.fromtimestamp(epoch, tz=timezone.utc)
            except (ValueError, OSError, OverflowError):
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
            end_time,  # end_time
            [entity_id],
            None,  # filters
            True,  # include_start_time_state
            True,  # significant_changes_only
            False,  # minimal_response (we need attributes)
            False,  # no_attributes
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
                if "eventType" not in s.attributes:
                    continue  # Not a valid treatment event payload

                treatment_dict = {
                    "eventType": s.attributes.get("eventType"),
                    "created_at": s.attributes.get("created_at", s.last_updated.isoformat())
                }

                for key in ("insulin", "carbs", "notes", "duration", "percent", "profile", "reason", "absolute", "rate"):
                    if key in s.attributes:
                        treatment_dict[key] = s.attributes[key]

                ns_entries.append(treatment_dict)

        # Sorting: history is ascending (oldest first)
        sort_val = request.rel_url.query.get("sort", "")
        if sort_val in ("date", "created_at", "+date", "+created_at", "date asc", "created_at asc"):
            pass  # Ascending requested
        else:
            ns_entries.reverse()  # Default to newest first

        ns_entries = ns_entries[:count]

        _LOGGER.debug("[%s] %s GET returning %d entries", req_id, self.__class__.__name__, len(ns_entries))
        return web.json_response(ns_entries, status=HTTPStatus.OK)


class _RouteView(_BasePostEventView):
    """ Helper class to register both /endpoint and /endpoint.json easily """
    pass

class GlucoseNGV1EntriesView(_BasePostEventView):
    name = "api:glucose_ng:v1_entries"
    def __init__(self, hass, get_token_map, url_base):
        self.url = f"{url_base}/api/v1/entries"
        self.extra_urls = [f"{url_base}/api/v1/entries.json"]
        super().__init__(hass, get_token_map, SIGNAL_NEW_READING)

class GlucoseNGV3EntriesView(_BasePostEventView):
    name = "api:glucose_ng:v3_entries"
    def __init__(self, hass, get_token_map, url_base):
        self.url = f"{url_base}/api/v3/entries"
        self.extra_urls = [f"{url_base}/api/v3/entries.json"]
        super().__init__(hass, get_token_map, SIGNAL_NEW_READING)

class GlucoseNGV1TreatmentsView(_BasePostEventView):
    name = "api:glucose_ng:v1_treatments"
    def __init__(self, hass, get_token_map, url_base):
        self.url = f"{url_base}/api/v1/treatments"
        self.extra_urls = [f"{url_base}/api/v1/treatments.json"]
        super().__init__(hass, get_token_map, SIGNAL_NEW_TREATMENT)

class GlucoseNGV3TreatmentsView(_BasePostEventView):
    name = "api:glucose_ng:v3_treatments"
    def __init__(self, hass, get_token_map, url_base):
        self.url = f"{url_base}/api/v3/treatments"
        self.extra_urls = [f"{url_base}/api/v3/treatments.json"]
        super().__init__(hass, get_token_map, SIGNAL_NEW_TREATMENT)

class GlucoseNGV1DeviceStatusView(_BasePostEventView):
    name = "api:glucose_ng:v1_devicestatus"
    def __init__(self, hass, get_token_map, url_base):
        self.url = f"{url_base}/api/v1/devicestatus"
        self.extra_urls = [f"{url_base}/api/v1/devicestatus.json"]
        super().__init__(hass, get_token_map, SIGNAL_NEW_DEVICESTATUS)

class GlucoseNGV3DeviceStatusView(_BasePostEventView):
    name = "api:glucose_ng:v3_devicestatus"
    def __init__(self, hass, get_token_map, url_base):
        self.url = f"{url_base}/api/v3/devicestatus"
        self.extra_urls = [f"{url_base}/api/v3/devicestatus.json"]
        super().__init__(hass, get_token_map, SIGNAL_NEW_DEVICESTATUS)


class GlucoseNGV2AuthView(HomeAssistantView):
    """
    Nightscout v2 authorization endpoint.
    Validates the token against the shared secret and returns 200 on success,
    or 401 if the token does not match any registered entry.
    """
    requires_auth = False
    name = "api:glucose_ng:v2_auth"

    def __init__(self, hass: HomeAssistant, get_token_map: Callable[[], dict[str, str]], url_base: str):
        self.hass = hass
        self._get_token_map = get_token_map
        self.url = f"{url_base}/api/v2/authorization/request/{{token}}"

    async def get(self, request: web.Request, token: str):
        _LOGGER.debug("GlucoseNGV2AuthView GET received")

        token_map = self._get_token_map()
        entry_id = _find_entry_by_token(token_map, token)

        if not entry_id:
            remote_ip = request.remote or "unknown"
            exceeded = _record_auth_failure(remote_ip)
            if exceeded:
                _LOGGER.warning("GlucoseNGV2AuthView: rate limit exceeded for %s — adding delay", remote_ip)
                await asyncio.sleep(_FAIL_DELAY_SECONDS)
            else:
                _LOGGER.warning("GlucoseNGV2AuthView: token did not match any registered entry → 401")
            return web.Response(status=HTTPStatus.UNAUTHORIZED, text="unauthorized")

        _clear_auth_failures(request.remote or "unknown")

        _LOGGER.debug("GlucoseNGV2AuthView: token matched entry_id=%s ✓", entry_id)
        return web.json_response(
            {
                "status": 200,
                "result": "ok",
                "token": token,
                "roles": ["readable", "devicestatus-upload"],
            },
            status=HTTPStatus.OK,
        )


class GlucoseNGStatusView(HomeAssistantView):
    """
    Nightscout v1 status endpoint.
    Some uploaders verify server status before pushing data.
    Authentication is required.
    """
    requires_auth = False
    name = "api:glucose_ng:v1_status"

    def __init__(self, get_token_map: Callable[[], dict[str, str]], url_base: str):
        self._get_token_map = get_token_map
        self.url = f"{url_base}/api/v1/status"
        self.extra_urls = [f"{url_base}/api/v1/status.json"]

    async def get(self, request: web.Request):
        req_id = uuid.uuid4().hex[:6]
        token_map = self._get_token_map()
        entry_id = await _check_auth_with_ratelimit(request, token_map, req_id)
        if not entry_id:
            return web.Response(status=HTTPStatus.UNAUTHORIZED, text="unauthorized")

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
    Authentication is required.
    """
    requires_auth = False
    name = "api:glucose_ng:v3_version"

    def __init__(self, get_token_map: Callable[[], dict[str, str]], url_base: str):
        self._get_token_map = get_token_map
        self.url = f"{url_base}/api/v3/version"
        self.extra_urls = [f"{url_base}/api/v3/version.json"]

    async def get(self, request: web.Request):
        req_id = uuid.uuid4().hex[:6]
        token_map = self._get_token_map()
        entry_id = await _check_auth_with_ratelimit(request, token_map, req_id)
        if not entry_id:
            return web.Response(status=HTTPStatus.UNAUTHORIZED, text="unauthorized")

        return web.json_response({
            "version": "14.2.0",
            "name": "Home Assistant Glucose NG"
        }, status=HTTPStatus.OK)

# ---------------------------------------------------------------------------
# Registration helpers
# ---------------------------------------------------------------------------

def register_http_views(hass: HomeAssistant, get_token_map: Callable[[], dict[str, str]], url_prefix: str) -> None:
    global _registered, _registered_prefix
    prefix_clean = url_prefix.strip("/")
    if _registered:
        if prefix_clean == _registered_prefix:
            _LOGGER.debug("HTTP views already registered with same prefix, skipping")
            return
        # Prefix has changed — force re-registration.
        # HA does not support un-registering individual routes at runtime, so we
        # log a warning and leave old routes in place; the new prefix gets added.
        _LOGGER.warning(
            "URL prefix changed from '%s' to '%s'. "
            "Old routes will persist until Home Assistant is restarted.",
            _registered_prefix, prefix_clean,
        )
        _registered = False

    prefix = prefix_clean
    if not prefix:
        raise ValueError(
            "url_prefix must not be empty. "
            "A non-empty prefix is required to avoid mounting routes under the reserved /api/ namespace."
        )

    url_base = f"/{prefix}"

    views = [
        GlucoseNGV1EntriesView(hass, get_token_map, url_base),
        GlucoseNGV3EntriesView(hass, get_token_map, url_base),
        GlucoseNGV1TreatmentsView(hass, get_token_map, url_base),
        GlucoseNGV3TreatmentsView(hass, get_token_map, url_base),
        GlucoseNGV1DeviceStatusView(hass, get_token_map, url_base),
        GlucoseNGV3DeviceStatusView(hass, get_token_map, url_base),
        GlucoseNGV2AuthView(hass, get_token_map, url_base),
        GlucoseNGStatusView(get_token_map, url_base),
        GlucoseNGVersionView(get_token_map, url_base),
    ]

    for view in views:
        hass.http.register_view(view)

    _registered = True
    _registered_prefix = prefix
    _LOGGER.debug("Registered HTTP views under prefix='%s': %s", prefix, ", ".join(v.url for v in views))


def unregister_http_views(hass: HomeAssistant) -> None:
    global _registered, _registered_prefix
    _registered = False
    _registered_prefix = ""
    _fail_log.clear()
    _LOGGER.debug("HTTP views unregistered")
