from __future__ import annotations
import logging
import time
from typing import Optional, Any
from homeassistant.components.event import EventEntity, EventDeviceClass
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN, CONF_NAME, DEFAULT_NAME, SIGNAL_NEW_TREATMENT

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    data = hass.data[DOMAIN]["entries"][entry.entry_id]
    name = data.get(CONF_NAME, DEFAULT_NAME)

    _LOGGER.debug(
        "Setting up event entity for entry '%s' (entry_id=%s)",
        name, entry.entry_id,
    )

    event_entity = GlucoseTreatmentEvent(hass, entry, f"{name} Treatment")
    async_add_entities([event_entity], True)
    _LOGGER.info("Event entity added for '%s': treatment", name)


def _device_info(entry: ConfigEntry, name: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=f"Glucose NG — {name}",
        manufacturer="Juggluco / NightScout Gateway",
        model="CGM Sensor Bridge",
        sw_version="0.3.0",
    )


class GlucoseTreatmentEvent(EventEntity):
    _attr_icon = "mdi:pill"
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_event_types = ["treatment"]

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, name: str):
        self.hass = hass
        self._entry = entry
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_glucose_treatment"
        self._available = True

    @property
    def available(self) -> bool:
        return self._available

    @property
    def device_info(self) -> DeviceInfo:
        return _device_info(self._entry, self._entry.data.get(CONF_NAME, DEFAULT_NAME))

    async def async_added_to_hass(self):
        # Subscribe to the entry-specific signal for new treatments
        signal = f"{SIGNAL_NEW_TREATMENT}_{self._entry.entry_id}"
        _LOGGER.debug("Subscribing to signal '%s'", signal)
        self.async_on_remove(
            async_dispatcher_connect(self.hass, signal, self._handle_treatment)
        )

    async def _handle_treatment(self, treatment: dict):
        _LOGGER.debug(
            "[%s] Treatment received: eventType=%s",
            self._entry.entry_id, treatment.get("eventType", "unknown"),
        )
        
        # We fire an event with the payload
        self._trigger_event("treatment", treatment)
        self.async_write_ha_state()

