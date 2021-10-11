"""The FPL Api integration."""
import asyncio
import logging

from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from datetime import timedelta
from .sensor import FPLSensor

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["sensor"]

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Fantasy Premier League component."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up FPL Api from a config entry."""
    session = async_create_clientsession(hass)
    fpl_email = entry.data["fpl_email"] if "fpl_email" in entry.data else None
    fpl_password = entry.data["fpl_password"] if "fpl_password" in entry.data else None
    fpl_user_id = entry.data["fpl_user_id"] if "fpl_user_id" in entry.data else None
    fav_team = entry.data["fav_team"] if "fav_team" in entry.data else None
    hass.data[DOMAIN][entry.entry_id] = FPLSensor(
        hass, session, fpl_email, fpl_password, fpl_user_id, fav_team
    )
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
