
from __future__ import annotations
import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import ConfigType
from homeassistant.const import Platform
from .const import (
    DOMAIN, CONF_SHARED_SECRET, CONF_NAME,
    CONF_LOW, CONF_HIGH, CONF_RATE_DROP,
    DEFAULT_NAME, DEFAULT_LOW, DEFAULT_HIGH, DEFAULT_RATE_DROP,
)
from .http import register_http_views, unregister_http_views

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SENSOR]

# token_map key inside hass.data[DOMAIN]
_TOKEN_MAP = "token_map"
# per-entry config data
_ENTRIES = "entries"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    hass.data.setdefault(DOMAIN, {_TOKEN_MAP: {}, _ENTRIES: {}})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {_TOKEN_MAP: {}, _ENTRIES: {}})

    entry_data = {
        CONF_SHARED_SECRET: entry.data.get(CONF_SHARED_SECRET),
        CONF_NAME: entry.data.get(CONF_NAME, DEFAULT_NAME),
        CONF_LOW: float(entry.data.get(CONF_LOW, DEFAULT_LOW)),
        CONF_HIGH: float(entry.data.get(CONF_HIGH, DEFAULT_HIGH)),
        CONF_RATE_DROP: float(entry.data.get(CONF_RATE_DROP, DEFAULT_RATE_DROP)),
    }
    hass.data[DOMAIN][_ENTRIES][entry.entry_id] = entry_data

    # Maintain a token_map: {shared_secret → entry_id} for all active entries.
    # HTTP views use this map to route requests to the correct set of sensors.
    secret = entry_data[CONF_SHARED_SECRET]
    if secret:
        hass.data[DOMAIN][_TOKEN_MAP][secret] = entry.entry_id
        _LOGGER.debug(
            "Registered token for entry '%s' (entry_id=%s). Total entries: %d",
            entry_data[CONF_NAME], entry.entry_id,
            len(hass.data[DOMAIN][_TOKEN_MAP]),
        )

    # Pass a live reference to the token_map so views always see the current state.
    def get_token_map() -> dict[str, str]:
        return hass.data[DOMAIN].get(_TOKEN_MAP, {})

    # Views are registered only once (the helper is idempotent).
    register_http_views(hass, get_token_map)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    _LOGGER.info("Glucose NG entry '%s' set up (entry_id=%s)", entry_data[CONF_NAME], entry.entry_id)
    return True


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry):
    await async_unload_entry(hass, entry)
    return await async_setup_entry(hass, entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entry_data = hass.data[DOMAIN][_ENTRIES].pop(entry.entry_id, {})
        secret = entry_data.get(CONF_SHARED_SECRET)
        if secret:
            hass.data[DOMAIN][_TOKEN_MAP].pop(secret, None)
        _LOGGER.debug(
            "Unloaded entry_id=%s. Remaining entries: %d",
            entry.entry_id, len(hass.data[DOMAIN][_TOKEN_MAP]),
        )
        # If no entries remain, also clear HTTP view registration flag
        # so views can be re-registered if the integration is fully removed and re-added.
        if not hass.data[DOMAIN][_TOKEN_MAP]:
            unregister_http_views(hass)
    return unload_ok
