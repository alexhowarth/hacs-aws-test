"""Sensor platform for Hello AWS IoT — reports SDK versions to prove they loaded."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            AwsSdkVersionSensor(entry, "awscrt", data["awscrt_version"]),
            AwsSdkVersionSensor(entry, "awsiot", data["awsiot_version"]),
        ]
    )


class AwsSdkVersionSensor(SensorEntity):
    """Sensor that exposes the version of an AWS SDK package."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, package: str, version: str) -> None:
        self._attr_unique_id = f"{entry.entry_id}_{package}_version"
        self._attr_name = f"{package} version"
        self._attr_native_value = version
        self._attr_icon = "mdi:aws"
