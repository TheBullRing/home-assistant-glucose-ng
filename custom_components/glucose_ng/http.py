
from __future__ import annotations
import logging, hashlib
from typing import Callable, Optional
from http import HTTPStatus
from aiohttp import web
from homeassistant.core import HomeAssistant
from homeassistant.components.http import HomeAssistantView
from homeassistant.helpers.dispatcher import async_dispatcher_send
from .const import SIGNAL_NEW_READING

_LOGGER = logging.getLogger(__name__)
_registered = []

def unregister_http_views(hass: HomeAssistant):
    _registered.clear()

def register_http_views(hass: HomeAssistant, get_secret: Callable[[], Optional[str]]) -> None:
    v1 = GlucoseNGV1EntriesView(hass, get_secret)
    v3 = GlucoseNGV3EntriesView(hass, get_secret)
    v2 = GlucoseNGV2AuthView(hass, get_secret)
    hass.http.register_view(v1)
    hass.http.register_view(v3)
    hass.http.register_view(v2)
    _registered.extend([v1, v3, v2])

def _coerce_entries(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        return [payload]
    return []

def _sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()

def _check_auth(request: web.Request, shared_secret: Optional[str]) -> bool:
    if not shared_secret:
        return True
    api_sec = request.headers.get("api-secret")
    if api_sec:
        if api_sec == shared_secret or api_sec.lower() == _sha1(shared_secret).lower():
            return True
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1].strip()
        if token == shared_secret:
            return True
    xsec = request.headers.get("X-Shared-Secret")
    if xsec and xsec == shared_secret:
        return True
    qtoken = request.rel_url.query.get("token")
    if qtoken and qtoken == shared_secret:
        return True
    return False

class _BaseEntriesView(HomeAssistantView):
    requires_auth = False
    name = "api:glucose_ng:entries_base"

    def __init__(self, hass: HomeAssistant, get_secret: Callable[[], Optional[str]]) -> None:
        self.hass = hass
        self._get_secret = get_secret

    async def post(self, request: web.Request):
        shared_secret = self._get_secret()
        if not _check_auth(request, shared_secret):
            return web.Response(status=HTTPStatus.UNAUTHORIZED, text="unauthorized")
        try:
            data = await request.json()
        except Exception:
            return web.Response(status=HTTPStatus.BAD_REQUEST, text="invalid json")
        entries = _coerce_entries(data)
        count_ok = 0
        for e in entries:
            sgv = e.get("sgv") or e.get("mbg")
            if sgv is None:
                continue
            epoch_ms = e.get("date")
            direction = e.get("direction", "unknown")
            reading = {
                "sgv": float(sgv),
                "epoch_ms": float(epoch_ms) if epoch_ms is not None else None,
                "direction": direction,
                "raw": e,
            }
            async_dispatcher_send(self.hass, SIGNAL_NEW_READING, reading)
            count_ok += 1
        return web.json_response({"ok": True, "count": count_ok}, status=HTTPStatus.OK)

class GlucoseNGV1EntriesView(_BaseEntriesView):
    url  = "/api/v1/entries"
    name = "api:glucose_ng:v1_entries"

class GlucoseNGV3EntriesView(_BaseEntriesView):
    url  = "/api/v3/entries"
    name = "api:glucose_ng:v3_entries"

class GlucoseNGV2AuthView(HomeAssistantView):
    requires_auth = False
    url  = r"/api/v2/authorization/request/{token}"
    name = "api:glucose_ng:v2_auth"

    def __init__(self, hass: HomeAssistant, get_secret):
        self.hass = hass
        self._get_secret = get_secret

    async def get(self, request: web.Request, token: str):
        return web.json_response({"status": 200, "result": "ok"}, status=HTTPStatus.OK)
