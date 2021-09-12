from fpl import FPL
import aiohttp
import asyncio
import jmespath
from datetime import datetime, timedelta
from typing import List
from dateutil import parser as dateparser
import pytz


class LiveScore:
    """
    Primary exported interface for Soccer Livescore based on FPL wrapper.
    """

    def __init__(self, tracked_teams: List[str], tz="Europe/Copenhagen"):
        self.pytz_tz = pytz.timezone(tz)
        self.tracked_teams = tracked_teams
        self.day = 0

    async def scroll_day(self):
        self.id2team = await self.get_id2team()
        self.team2id = {team: id for id, team in self.id2team.items()}
        self.active_gameweek = await self.get_active_gameweek()
        self.tracked_ids = [self.team2id[team] for team in self.tracked_teams]
        self.kickoffs = await self.get_fixture_kickoffs()
        self.match_goals = []

    async def get_id2team(self):
        async with aiohttp.ClientSession() as session:
            fpl = FPL(session)
            id2teams = {}
            for i in range(1, 21, 1):
                res = await fpl.get_team(i, return_json=True)
                id2teams[i] = res["name"]
        return id2teams

    async def get_active_gameweek(self):
        async with aiohttp.ClientSession() as session:
            fpl = FPL(session)
            gameweeks = await fpl.get_gameweeks(return_json=True)
            active_gameweek = jmespath.search("[?is_current].id | [0]", gameweeks)
        return active_gameweek

    async def get_fixture_kickoffs(self):
        async with aiohttp.ClientSession() as session:
            fpl = FPL(session)
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
                if fixture["team_a"] in self.tracked_ids
                or fixture["team_h"] in self.tracked_ids
                else None
                for fixture in fixtures
            ]
            fixtures = [x for x in fixtures if x is not None]
        return fixtures

    async def get_live_fixtures(self):
        async with aiohttp.ClientSession() as session:
            fpl = FPL(session)
            fixtures = await fpl.get_fixtures_by_gameweek(
                gameweek=self.active_gameweek, return_json=True
            )
            fixtures = jmespath.search(
                "[?finished==`false` && started==`true`].{team_a: team_a, team_h: team_h, stats: stats, id: id}",
                fixtures,
            )
            fixtures = [
                fixture
                if fixture["team_a"] in self.tracked_ids
                or fixture["team_h"] in self.tracked_ids
                else None
                for fixture in fixtures
            ]
            fixtures = [x for x in fixtures if x is not None]
            goals_scored = jmespath.search(
                "[].stats[?contains(identifier, 'goal') == `true`].{a: a, h: h}",
                fixtures,
            )
            teams_per_match = [
                f"{self.id2team[fixture['team_h']]} v. {self.id2team[fixture['team_a']]}"
                for fixture in fixtures
            ]
            goals_scored_per_match = [
                {
                    "home_goals": len(fixture[0]["h"]) + len(fixture[1]["h"]),
                    "away_goals": len(fixture[0]["a"]) + len(fixture[1]["a"]),
                }
                for fixture in goals_scored
            ]  # both goals and own goals
            # todo doesn't seem to include overtime goals
            match_goals = dict(zip(teams_per_match, goals_scored_per_match))
            return match_goals

    async def get_new_goal(self):
        match_goals = await self.get_live_fixtures()
        if not self.match_goals:
            self.match_goals = match_goals
        new_goals = [
            match_goals[match] == score
            for match, score in self.match_goals.items()
            if match in match_goals.keys()
        ]
        new_goal = any(new_goals)
        self.match_goals = match_goals
        return new_goal

    async def update(self):
        now = datetime.today().astimezone(tz=self.pytz_tz)
        if now.day != self.day:
            self.day = now.day
            await self.scroll_day()

        if not self.kickoffs:
            asyncio.sleep(3 * 60 * 60)

        if any(
            [kickoff < now < kickoff + timedelta(hours=2) for kickoff in self.kickoffs]
        ):

            new_goal = await self.get_new_goal()
            return new_goal

        else:
            # Seconds until next kickoff
            next_kickoff = [kickoff for kickoff in self.kickoffs if kickoff > now]
            next_kickoff.sort()
            next_kickoff = next_kickoff[0]
            seconds = (next_kickoff - now).seconds
            await asyncio.sleep(seconds)
