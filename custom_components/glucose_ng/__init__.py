
from __future__ import annotations
import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import ConfigType
from homeassistant.const import Platform
from .const import (
    DOMAIN, CONF_SHARED_SECRET, CONF_NAME,
    CONF_LOW, CONF_HIGH, CONF_RATE_DROP,
    DEFAULT_NAME, DEFAULT_LOW, DEFAULT_HIGH, DEFAULT_RATE_DROP
)
from .http import register_http_views, unregister_http_views

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SENSOR]

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data[DOMAIN][entry.entry_id] = {
        CONF_SHARED_SECRET: entry.data.get(CONF_SHARED_SECRET),
        CONF_NAME: entry.data.get(CONF_NAME, DEFAULT_NAME),
        CONF_LOW: float(entry.data.get(CONF_LOW, DEFAULT_LOW)),
        CONF_HIGH: float(entry.data.get(CONF_HIGH, DEFAULT_HIGH)),
        CONF_RATE_DROP: float(entry.data.get(CONF_RATE_DROP, DEFAULT_RATE_DROP)),
    }
    # Registrar endpoints HTTP
    get_secret = lambda: hass.data[DOMAIN].get(entry.entry_id, {}).get(CONF_SHARED_SECRET)
    register_http_views(hass, get_secret)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True

async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry):
    await async_unload_entry(hass, entry)
    return await async_setup_entry(hass, entry)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        unregister_http_views(hass)
    return unload_ok
