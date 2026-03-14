
from __future__ import annotations
import logging
import time
from typing import Optional
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from .const import (
    DOMAIN, SIGNAL_NEW_READING, CONF_NAME, DEFAULT_NAME,
    CONF_LOW, CONF_HIGH, CONF_RATE_DROP,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    data = hass.data[DOMAIN]["entries"][entry.entry_id]
    name = data.get(CONF_NAME, DEFAULT_NAME)
    low = float(data.get(CONF_LOW))
    high = float(data.get(CONF_HIGH))
    rate_drop = float(data.get(CONF_RATE_DROP))

    _LOGGER.debug(
        "Setting up sensors for entry '%s' (entry_id=%s): low=%.1f high=%.1f rate_drop=%.2f",
        name, entry.entry_id, low, high, rate_drop,
    )

    main = GlucoseValueSensor(hass, entry, name, low, high, rate_drop)
    delta = GlucoseDeltaSensor(hass, entry, f"{name} Delta")
    rate = GlucoseRateSensor(hass, entry, f"{name} Rate")
    main.attach_derivatives(delta, rate)

    async_add_entities([main, delta, rate], True)
    _LOGGER.info("Sensors added for '%s': value, delta, rate", name)


def _device_info(entry: ConfigEntry, name: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=f"Glucose NG — {name}",
        manufacturer="Juggluco / NightScout Gateway",
        model="CGM Sensor Bridge",
        sw_version="0.3.0",
    )


class BaseGlucoseSensor(SensorEntity):
    _attr_icon = "mdi:diabetes"
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, name: str):
        self.hass = hass
        self._entry = entry
        self._attr_name = name
        self._value = None
        self._attrs: dict = {}
        self._available = True

    @property
    def native_value(self):
        return self._value

    @property
    def extra_state_attributes(self):
        return self._attrs

    @property
    def available(self) -> bool:
        return self._available

    @property
    def device_info(self) -> DeviceInfo:
        return _device_info(self._entry, self._entry.data.get(CONF_NAME, DEFAULT_NAME))


class GlucoseValueSensor(BaseGlucoseSensor):
    _attr_native_unit_of_measurement = "mg/dL"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        name: str,
        low: float,
        high: float,
        rate_drop: float,
    ):
        super().__init__(hass, entry, name)
        self._attr_unique_id = f"{entry.entry_id}_glucose_value"
        self._low = low
        self._high = high
        self._rate_drop = rate_drop
        self._last_value: Optional[float] = None
        self._last_ts: Optional[float] = None
        self._delta_sensor: Optional[GlucoseDeltaSensor] = None
        self._rate_sensor: Optional[GlucoseRateSensor] = None

    def attach_derivatives(self, delta_sensor, rate_sensor):
        self._delta_sensor = delta_sensor
        self._rate_sensor = rate_sensor

    async def async_added_to_hass(self):
        # Subscribe to the entry-specific signal so readings are routed correctly
        # when multiple config entries (multiple devices/people) are active.
        signal = f"{SIGNAL_NEW_READING}_{self._entry.entry_id}"
        _LOGGER.debug("Subscribing to signal '%s'", signal)
        self.async_on_remove(
            async_dispatcher_connect(self.hass, signal, self._handle_reading)
        )

    async def _handle_reading(self, reading: dict):
        try:
            new_val = reading.get("sgv")
            ts_ms = reading.get("epoch_ms")
            now_ts = time.time()
            ts = (ts_ms / 1000.0) if ts_ms else now_ts

            _LOGGER.debug(
                "[%s] Handling reading: sgv=%.1f direction=%s",
                self._entry.entry_id, new_val, reading.get("direction"),
            )

            delta: Optional[float] = None
            rate: Optional[float] = None
            if self._last_value is not None and self._last_ts is not None:
                delta = float(new_val) - float(self._last_value)
                dt_min = max((ts - self._last_ts) / 60.0, 1e-6)
                rate = delta / dt_min

            self._value = new_val
            
            attrs = {
                "direction": reading.get("direction"),
                "timestamp_ms": ts_ms,
                "last_updated_ts": now_ts,
            }
            
            raw_data = reading.get("raw", {})
            for key in ("device", "noise", "rssi", "type", "filtered", "unfiltered"):
                if key in raw_data:
                    attrs[key] = raw_data[key]
                    
            self._attrs = attrs
            self._available = True
            self._last_value = new_val
            self._last_ts = ts
            
            _LOGGER.debug("[%s] Writing state: value=%s delta=%s", self._entry.entry_id, self._value, delta)
            self.async_write_ha_state()

            if self._delta_sensor is not None and delta is not None:
                self._delta_sensor.update_value(delta)
            if self._rate_sensor is not None and rate is not None:
                self._rate_sensor.update_value(rate)

            # Alerts in background to not block the dispatcher (and UI updates)
            if self.hass:
                self.hass.async_create_task(self._async_check_alerts(new_val, rate))
        except Exception as exc:
            _LOGGER.exception("[%s] Error in _handle_reading: %s", self._entry.entry_id, exc)

    async def _async_check_alerts(self, new_val: Optional[float], rate: Optional[float]):
        try:
            if new_val is not None:
                if float(new_val) < self._low:
                    await self._notify("Hypoglycemia", f"Glucose {new_val} mg/dL < {self._low}")
                elif float(new_val) > self._high:
                    await self._notify("Hyperglycemia", f"Glucose {new_val} mg/dL > {self._high}")
            if rate is not None and rate <= -abs(self._rate_drop):
                await self._notify("Rapid drop", f"Δ {rate:.1f} mg/dL/min")
        except Exception as exc:
            _LOGGER.debug("Alert error: %s", exc)

    async def _notify(self, title: str, message: str):
        _LOGGER.info("Alert [%s]: %s — %s", self._entry.data.get(CONF_NAME), title, message)
        self.hass.bus.async_fire(
            "glucose_ng_alert",
            {"title": title, "message": message, "entry_id": self._entry.entry_id},
        )


class GlucoseDeltaSensor(BaseGlucoseSensor):
    _attr_native_unit_of_measurement = "mg/dL"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:delta"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, name: str):
        super().__init__(hass, entry, name)
        self._attr_unique_id = f"{entry.entry_id}_glucose_delta"

    def update_value(self, delta: float):
        self._value = round(delta, 1)
        self._available = True
        self.async_write_ha_state()


class GlucoseRateSensor(BaseGlucoseSensor):
    _attr_native_unit_of_measurement = "mg/dL/min"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:trending-up"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, name: str):
        super().__init__(hass, entry, name)
        self._attr_unique_id = f"{entry.entry_id}_glucose_rate"

    def update_value(self, rate: float):
        self._value = round(rate, 2)
        self._available = True
        self.async_write_ha_state()
