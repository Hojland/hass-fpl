"""Config flow for FPL Api integration."""
from __future__ import annotations

import logging
from typing import Any, List

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

TEAMS = [
    "Arsenal",
    "Aston Villa",
    "Brentford",
    "Brighton",
    "Burnley",
    "Chelsea",
    "Crystal Palace",
    "Everton",
    "Leeds",
    "Leicester",
    "Liverpool",
    "Man City",
    "Man Utd",
    "Newcastle",
    "Norwich",
    "Southampton",
    "Spurs",
    "Watford",
    "West Ham",
    "Wolves",
]


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional("fpl_email"): cv.string,
        vol.Optional("fpl_password"): cv.string,
        vol.Optional("fpl_user_id"): cv.positive_int,
        vol.Optional("fav_team", default="Man Utd"): vol.In(TEAMS),
    }
)
DESCRIPTIONS = {
    "fpl_email": "Email to log into Fantasy Premier League",
    "fpl_password": "Password to log into Fantasy Premier League",
    "fpl_user_id": "User id for your team. Find it on the site",
    "fav_team": "Pick you favourite team to follow",
}


class PlaceholderHub:
    """Placeholder class to make tests pass."""

    def __init__(
        self, fpl_email: str, fpl_password: str, fpl_user_id: str, fav_team: str
    ) -> None:
        """Initialize."""
        self.fpl_email = fpl_email
        self.fpl_password = fpl_password
        self.fpl_user_id = fpl_user_id
        self.fav_team = fav_team

    async def authenticate(self) -> bool:
        """Test if we can authenticate with the host."""
        try:
            fpl = FantasyPremierLeague(
                self.fpl_email, self.fpl_password, self.fpl_user_id, self.fav_team
            )
            # await fpl.test_session()
        except Exception:
            return False

        return True


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    fpl_email = data["fpl_email"] if "fpl_email" in data.keys() else None
    fpl_password = data["fpl_password"] if "fpl_password" in data.keys() else None
    fpl_user_id = data["fpl_user_id"] if "fpl_user_id" in data.keys() else None
    fav_team = data["fav_team"] if "fav_team" in data.keys() else None

    hub = PlaceholderHub(fpl_email, fpl_password, fpl_user_id, fav_team)

    if not await hub.authenticate():
        raise InvalidAuth

    # Return info that you want to store in the config entry.
    return {"title": "Fantasy Premier League Integration"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for FPL Api."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                description_placeholders=DESCRIPTIONS,
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders=DESCRIPTIONS,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
