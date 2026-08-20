from __future__ import annotations
import logging
import voluptuous as vol
from homeassistant import config_entries
from .const import (
    DOMAIN, CONF_SHARED_SECRET, CONF_NAME, DEFAULT_NAME,
    CONF_URL_PREFIX, DEFAULT_URL_PREFIX,
    CONF_LOW, CONF_HIGH, CONF_RATE_DROP,
    DEFAULT_LOW, DEFAULT_HIGH, DEFAULT_RATE_DROP,
)

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_SHARED_SECRET): str,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
    vol.Optional(CONF_URL_PREFIX, default=DEFAULT_URL_PREFIX): str,
    vol.Optional(CONF_LOW, default=DEFAULT_LOW): vol.Coerce(float),
    vol.Optional(CONF_HIGH, default=DEFAULT_HIGH): vol.Coerce(float),
    vol.Optional(CONF_RATE_DROP, default=DEFAULT_RATE_DROP): vol.Coerce(float),
})


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                low = float(user_input.get(CONF_LOW, DEFAULT_LOW))
                high = float(user_input.get(CONF_HIGH, DEFAULT_HIGH))
                url_prefix = user_input.get(CONF_URL_PREFIX, DEFAULT_URL_PREFIX).strip().strip("/")

                if not url_prefix:
                    errors[CONF_URL_PREFIX] = "prefix_required"
                elif low >= high:
                    errors["base"] = "range_invalid"
                else:
                    _LOGGER.debug(
                        "Creating config entry: name=%s, url_prefix=%s, low=%.1f, high=%.1f",
                        user_input.get(CONF_NAME), url_prefix, low, high,
                    )
                    return self.async_create_entry(
                        title="Home Assistant Glucose NG",
                        data={
                            CONF_SHARED_SECRET: user_input[CONF_SHARED_SECRET],
                            CONF_NAME: user_input.get(CONF_NAME, DEFAULT_NAME),
                            CONF_URL_PREFIX: url_prefix,
                            CONF_LOW: low,
                            CONF_HIGH: high,
                            CONF_RATE_DROP: float(user_input.get(CONF_RATE_DROP, DEFAULT_RATE_DROP)),
                        },
                    )
            except Exception as exc:
                _LOGGER.exception("Config flow error: %s", exc)
                errors["base"] = "invalid"

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

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
