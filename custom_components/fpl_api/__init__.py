"""The FPL Api integration."""
import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import Throttle
from datetime import timedelta
from .fpl import LiveScore

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["sensor"]

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Eloverblik component."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up FPL Api from a config entry."""
    tracked_teams = [entry.data["team_1"], entry.data["team_2"], entry.data["team_3"]]
    hass.data[DOMAIN][entry.entry_id] = HassFPL(tracked_teams)

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class HassFPL:
    def __init__(self, tracked_teams: list):
        self.livescore = LiveScore(tracked_teams)
        self.tracked_teams = tracked_teams
        self._state = False

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def update(self):
        _LOGGER.debug("Fetching data from FPL")

        try:
            new_goal = await self.livescore.update()
            self._state = new_goal
        except Exception as e:
            _LOGGER.warn(f"Exception: {e}")

        _LOGGER.debug("Done fetching data from FPL")
