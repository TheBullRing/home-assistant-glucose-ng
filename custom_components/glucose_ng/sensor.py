
from __future__ import annotations
import logging, time
from typing import Optional
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from .const import (
    DOMAIN, SIGNAL_NEW_READING, CONF_NAME, DEFAULT_NAME,
    CONF_LOW, CONF_HIGH, CONF_RATE_DROP
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    name = data.get(CONF_NAME, DEFAULT_NAME)
    low = float(data.get(CONF_LOW))
    high = float(data.get(CONF_HIGH))
    rate_drop = float(data.get(CONF_RATE_DROP))

    main = GlucoseValueSensor(hass, name, low, high, rate_drop)
    delta = GlucoseDeltaSensor(hass, f"{name} Delta")
    rate  = GlucoseRateSensor(hass, f"{name} Velocidad")

    # Vincular referencias para cómputo cruzado
    main.attach_derivatives(delta, rate)

    async_add_entities([main, delta, rate], True)

class BaseGlucoseSensor(SensorEntity):
    _attr_icon = "mdi:diabetes"

    def __init__(self, hass: HomeAssistant, name: str):
        self.hass = hass
        self._attr_name = name
        self._value = None
        self._attrs = {}

    @property
    def native_value(self):
        return self._value

    @property
    def extra_state_attributes(self):
        return self._attrs

class GlucoseValueSensor(BaseGlucoseSensor):
    _attr_native_unit_of_measurement = "mg/dL"
    _attr_state_class = "measurement"
    _attr_unique_id = "glucose_ng_value"

    def __init__(self, hass: HomeAssistant, name: str, low: float, high: float, rate_drop: float):
        super().__init__(hass, name)
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
        self.async_on_remove(async_dispatcher_connect(
            self.hass, SIGNAL_NEW_READING, self._handle_reading
        ))

    async def _handle_reading(self, reading: dict):
        new_val = reading.get("sgv")
        ts_ms = reading.get("epoch_ms")
        now_ts = time.time()
        ts = (ts_ms/1000.0) if ts_ms else now_ts

        # Derivadas
        delta = None
        rate = None
        if self._last_value is not None and self._last_ts is not None:
            delta = float(new_val) - float(self._last_value)
            dt_min = max((ts - self._last_ts) / 60.0, 1e-6)
            rate = delta / dt_min

        # Actualiza self
        self._value = new_val
        self._attrs = {
            "direction": reading.get("direction"),
            "timestamp_ms": ts_ms,
        }
        self._last_value = new_val
        self._last_ts = ts
        self.async_write_ha_state()

        # Actualiza derivados
        if self._delta_sensor is not None and delta is not None:
            self._delta_sensor.update_value(delta)
        if self._rate_sensor is not None and rate is not None:
            self._rate_sensor.update_value(rate)

        # Alertas básicas: hipo / hiper / caída rápida
        try:
            if new_val is not None:
                if float(new_val) < self._low:
                    await self._notify("Hipoglucemia", f"Glucosa {new_val} mg/dL < {self._low}")
                elif float(new_val) > self._high:
                    await self._notify("Hiperglucemia", f"Glucosa {new_val} mg/dL > {self._high}")
            if rate is not None and rate <= -abs(self._rate_drop):
                await self._notify("Caída rápida", f"Δ {rate:.1f} mg/dL/min")
        except Exception as e:
            _LOGGER.debug("Notification error: %s", e)

    async def _notify(self, title: str, message: str):
        # Evento + notificación persistente (el usuario puede añadir también notify móvil por automatización)
        self.hass.bus.async_fire("glucose_ng_alert", {"title": title, "message": message})
        await self.hass.services.async_call(
            "persistent_notification", "create",
            {"title": f"[Glucose NG] {title}", "message": message},
            blocking=False
        )

class GlucoseDeltaSensor(BaseGlucoseSensor):
    _attr_native_unit_of_measurement = "mg/dL"
    _attr_state_class = "measurement"
    _attr_unique_id = "glucose_ng_delta"

    def update_value(self, delta: float):
        self._value = round(delta, 1)
        self._attrs = {}
        self.async_write_ha_state()

class GlucoseRateSensor(BaseGlucoseSensor):
    _attr_native_unit_of_measurement = "mg/dL/min"
    _attr_state_class = "measurement"
    _attr_unique_id = "glucose_ng_rate"

    def update_value(self, rate: float):
        self._value = round(rate, 2)
        self._attrs = {}
        self.async_write_ha_state()
