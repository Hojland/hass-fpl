"""Platform for sensor integration."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from .const import DOMAIN


async def async_setup_entry(hass, config, async_add_entities):
    """Set up the sensor platform."""

    livescore = hass.data[DOMAIN][config.entry_id]

    sensors = []
    sensors.append(FPLSensor(livescore))
    async_add_entities(sensors)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""
    livescore = hass.data[DOMAIN][config.entry_id]
    add_entities([FPLSensor(livescore)])


class FPLSensor(SensorEntity):
    """Representation of a Sensor."""

    def __init__(
        self,
        livescore,
    ):
        """Initialize the sensor."""
        self._state = False
        self.livescore = livescore

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "FPL API"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    async def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        new_goal = await self.livescore.update()

        self._state = new_goal
