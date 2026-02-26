"""Config flow for Hello AWS IoT."""

from __future__ import annotations

from homeassistant.config_entries import ConfigFlow

from .const import DOMAIN


class HelloAwsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hello AWS IoT."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step — just a confirm button, no fields."""
        if user_input is not None:
            return self.async_create_entry(title="Hello AWS IoT", data={})

        return self.async_show_form(step_id="user")
