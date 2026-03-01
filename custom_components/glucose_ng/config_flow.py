
from __future__ import annotations
import voluptuous as vol
from homeassistant import config_entries
from .const import (
    DOMAIN, CONF_SHARED_SECRET, CONF_NAME, DEFAULT_NAME,
    CONF_LOW, CONF_HIGH, CONF_RATE_DROP, DEFAULT_LOW, DEFAULT_HIGH, DEFAULT_RATE_DROP
)

DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_SHARED_SECRET): str,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
    vol.Optional(CONF_LOW, default=DEFAULT_LOW): float,
    vol.Optional(CONF_HIGH, default=DEFAULT_HIGH): float,
    vol.Optional(CONF_RATE_DROP, default=DEFAULT_RATE_DROP): float,
})

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            # Validaciones básicas
            try:
                low = float(user_input.get(CONF_LOW))
                high = float(user_input.get(CONF_HIGH))
                if low >= high:
                    errors["base"] = "range_invalid"
                else:
                    return self.async_create_entry(
                        title="Home Assistant Glucose NG",
                        data={
                            CONF_SHARED_SECRET: user_input[CONF_SHARED_SECRET],
                            CONF_NAME: user_input.get(CONF_NAME, DEFAULT_NAME),
                            CONF_LOW: low,
                            CONF_HIGH: high,
                            CONF_RATE_DROP: float(user_input.get(CONF_RATE_DROP)),
                        }
                    )
            except Exception:
                errors["base"] = "invalid"
        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA, errors=errors)

    async def async_step_import(self, user_input=None):
        return await self.async_step_user(user_input)

class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input=None):
        return self.async_create_entry(title="", data={})

async def async_get_options_flow(config_entry):
    return OptionsFlowHandler(config_entry)
