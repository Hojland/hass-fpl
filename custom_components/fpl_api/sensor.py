"""Platform for sensor integration."""
from __future__ import annotations
import logging
import aiohttp
import jmespath
from datetime import datetime, timedelta
from typing import List
from dateutil import parser as dateparser
import pytz

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.event import track_point_in_time
from .const import DOMAIN
from .fpl_mod import FPL

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["sensor"]

LIVE_SCAN_INTERVAL = timedelta(seconds=10)
POSTGAME_SCAN_INTERVAL = timedelta(hours=1)
DEFAULT_SCAN_INTERVAL = POSTGAME_SCAN_INTERVAL.seconds


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""

    _LOGGER.info("Fantasy Premier League Sensor starting up")
    session = async_create_clientsession(hass)

    fpl_email = config.get("fpl_email")
    fpl_password = config.get("fpl_password")
    fpl_user_id = config.get("fpl_user_id")
    fav_team = config.get("fav_team")

    async_add_entities(
        [FPLSensor(hass, session, fpl_email, fpl_password, fpl_user_id, fav_team)]
    )


async def async_setup_entry(hass, config, async_add_entities):
    """Set up the sensor platform."""

    fplsensor = hass.data[DOMAIN][config.entry_id]

    sensors = []
    sensors.append(fplsensor)
    async_add_entities(sensors)


def get_gameweek_score(player, gameweek):
    gameweek_history = next(
        history for history in player.history if history["round"] == gameweek
    )
    return gameweek_history["total_points"]


class FPLSensor(SensorEntity):
    """
    Primary exported interface for Soccer Livescore based on FPL wrapper.
    """

    def __init__(
        self,
        hass=None,
        session: aiohttp.ClientSession = None,
        fpl_email: str = None,
        fpl_password: str = None,
        fpl_user_id: str = None,
        fav_team: str = None,
        tz="Europe/Copenhagen",
    ):
        self.entity_id = "sensor.fantasy_premier_league"
        self.hass = hass
        self.session = session
        self._state = "No games playing"
        self._state_attributes = {}
        self._scan_interval = DEFAULT_SCAN_INTERVAL
        hass.async_add_executor_job(self.timer)

        self.pytz_tz = pytz.timezone(tz)
        self.fpl_email = fpl_email
        self.fpl_password = fpl_password
        self.fpl_user_id = fpl_user_id
        self.fav_team = fav_team

        self.day = 0
        self.match_goals = []
        self.id2team: dict = {}
        self.team2id: dict = {}
        self.active_gameweek: int = 0
        self.kickoffs: List[datetime] = []
        self.fav_team_id: str = ""

    @property
    def should_poll(self):
        """Polling required."""
        return True

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:soccer-field"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return self._state_attributes

    def timer(self):
        nowtime = datetime.today()
        self.schedule_update_ha_state(True)
        polling_delta = self.set_polling()
        nexttime = nowtime + polling_delta
        # Setup timer to run again at polling delta
        track_point_in_time(self.hass, self.timer, nexttime)

    async def test_session(self):
        async with aiohttp.ClientSession() as session:
            fpl = FPL(session)
            await fpl.async_init(self.hass)
            if self.fpl_email and self.fpl_password:
                fpl = FPL(session)
                await fpl.async_init(self.hass)
                await fpl.login(email=self.fpl_email, password=self.fpl_password)
                if self.fpl_user_id:
                    self.user = await fpl.get_user(self.fpl_user_id)
            else:
                fpl = FPL(session)
                await fpl.async_init(self.hass)

    async def scroll_day(self):
        self.id2team = await self.get_id2team()
        self.team2id = {team: id for id, team in self.id2team.items()}
        self.active_gameweek = await self.get_active_gameweek()
        self.fav_team_id = self.team2id[self.fav_team]
        self.kickoffs = await self.get_fixture_kickoffs()
        self.match_goals = []

    async def get_team(self):
        async with aiohttp.ClientSession() as session:
            fpl = FPL(session)
            await fpl.async_init(self.hass)
            # fpl.init()
            if self.fpl_email and self.fpl_password:
                await fpl.login(email=self.fpl_email, password=self.fpl_password)
                self.user = await fpl.get_user(self.fpl_user_id)
                team = await self.user.get_team()
                player_ids = [player["element"] for player in team]
                # player_summaries = await fpl.get_player_summaries(
                #     player_ids, return_json=True
                # )
                players = await fpl.get_players(player_ids, include_summary=True)
                player_score = {
                    f"{player.first_name} {player.web_name}": get_gameweek_score(
                        player, self.active_gameweek
                    )
                    for player in players
                }
                top_scorer = max(
                    players, key=lambda x: get_gameweek_score(x, self.active_gameweek)
                )

                return team, top_scorer
            else:
                return None, None

    async def get_id2team(self):
        async with aiohttp.ClientSession() as session:
            fpl = FPL(session)
            await fpl.async_init(self.hass)
            id2teams = {}
            for i in range(1, 21, 1):
                res = await fpl.get_team(i, return_json=True)
                id2teams[i] = res["name"]
        return id2teams

    async def get_pl_teams(self):
        async with aiohttp.ClientSession() as session:
            fpl = FPL(session)
            await fpl.async_init(self.hass)
            id2teams = {}
            for i in range(1, 21, 1):
                res = await fpl.get_team(i, return_json=True)
                id2teams[i] = res["name"]
        return sorted(list(id2teams.values()))

    async def get_active_gameweek(self):
        async with aiohttp.ClientSession() as session:
            fpl = FPL(session)
            await fpl.async_init(self.hass)
            # fpl.init()
            gameweeks = await fpl.get_gameweeks(return_json=True)
        active_gameweek = jmespath.search("[?is_current].id | [0]", gameweeks)
        return active_gameweek

    async def get_fixture_kickoffs(self):
        async with aiohttp.ClientSession() as session:
            fpl = FPL(session)
            await fpl.async_init(self.hass)
            # fpl.init()
            fixtures = await fpl.get_fixtures_by_gameweek(
                gameweek=self.active_gameweek, return_json=True
            )
            fixtures = jmespath.search(
                "[?finished==`false` && started==`false`].{team_a: team_a, team_h: team_h, kickoff_time: kickoff_time}",
                fixtures,
            )
            fixtures = [
                dateparser.parse(fixture["kickoff_time"])
                .replace(tzinfo=pytz.utc)
                .astimezone(tz=self.pytz_tz)
                if fixture["team_a"] in self.fav_team_id
                or fixture["team_h"] in self.fav_team_id
                else None
                for fixture in fixtures
            ]
            fixtures = [x for x in fixtures if x is not None]
        return fixtures

    async def get_live_fixtures(self):
        async with aiohttp.ClientSession() as session:
            fpl = FPL(session)
            await fpl.async_init(self.hass)
            # fpl.init()
            fixtures = await fpl.get_fixtures_by_gameweek(
                gameweek=self.active_gameweek, return_json=True
            )
            fixtures = jmespath.search(
                "[?finished==`false` && started==`true`].{team_a: team_a, team_h: team_h, stats: stats, id: id}",
                fixtures,
            )
            fav_team_fixtures = [
                fixture
                if fixture["team_a"] in self.fav_team_id
                or fixture["team_h"] in self.fav_team_id
                else None
                for fixture in fixtures
            ]
            fav_team_fixtures = [x for x in fav_team_fixtures if x is not None]

            goals_scored = jmespath.search(
                "[].stats[?contains(identifier, 'goal') == `true`].{a: a, h: h}",
                fav_team_fixtures,
            )

            teams_per_match = [
                f"{self.id2team[fixture['team_h']]} v. {self.id2team[fixture['team_a']]}"
                for fixture in fav_team_fixtures
            ]
            goals_scored_per_match = [
                {
                    "home_goals": len(fixture[0]["h"]) + len(fixture[1]["h"]),
                    "away_goals": len(fixture[0]["a"]) + len(fixture[1]["a"]),
                }
                for fixture in goals_scored
            ]  # both goals and own goals

            # goal_scorers_per_match = [{fixture[0][""]} for fixture in goals_scored]
            # todo doesn't seem to include overtime goals
            match_goals = dict(zip(teams_per_match, goals_scored_per_match))
            return match_goals

    async def get_match_goals(self):
        match_goals = await self.get_live_fixtures()
        if not self.match_goals:
            self.match_goals = match_goals
        new_goals = [
            match_goals[match] == score
            for match, score in self.match_goals.items()
            if match in match_goals.keys()
        ]
        new_goal = any(new_goals)  # TODO WHO SCORED
        self.match_goals = match_goals
        return new_goal, match_goals

    async def async_update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        _LOGGER.debug("Fetching data from FPL")
        now = datetime.today().astimezone(tz=self.pytz_tz)

        if now.day != self.day:
            self.day = now.day
            await self.scroll_day()

        new_goal, match_goals = await self.get_match_goals()
        team, top_scorer = await self.get_team()
        new_goal = {"new_goal": new_goal}
        top_scorer = {
            "top_scorer": f"{top_scorer.first_name} {top_scorer.web_name}: {get_gameweek_score(top_scorer, self.active_gameweek)}"
            if top_scorer
            else top_scorer
        }

        # Move tracked team to here later
        ## Set attribute for goal scored by tracked team.
        # if self._state_attributes.get("goal_team_id", None) == self._team_id:
        #    self._state_attributes["goal_tracked_team"] = True
        # else:
        #    self._state_attributes["goal_tracked_team"] = False

        all_attr = {**new_goal, **top_scorer}  # **match_goals,
        self._state_attributes = all_attr
        self._state = (
            "In Progress"
            if any(
                [
                    kickoff < now < kickoff + timedelta(hours=2)
                    for kickoff in self.kickoffs
                ]
            )
            else "No games playing"
        )

        _LOGGER.debug("Done fetching data from FPL")

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Fantasy Premier League Sensor"

    def set_polling(self):
        game_state = self._state
        if game_state in [None, "In Progress"]:
            if self._scan_interval > LIVE_SCAN_INTERVAL:
                polling_delta = self._scan_interval
            else:
                polling_delta = LIVE_SCAN_INTERVAL
        else:
            polling_delta = POSTGAME_SCAN_INTERVAL
        return polling_delta
