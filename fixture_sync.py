"""Batch fixture ingestion for the database-first mobile API.

Five leagues come from football-data.org. Süper Lig uses the CC0 OpenFootball
JSON feed, so the scheduled job needs only one request per competition rather
than one request per match.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
import os
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

import requests

from db_setup import SessionLocal
from models import Fixture, FixtureSyncState, SyncRun
from team_normalizer import normalize_team_name


FOOTBALL_DATA_COMPETITIONS = {
    "D1": "BL1",
    "E0": "PL",
    "SP1": "PD",
    "I1": "SA",
    "F1": "FL1",
}

FOOTBALL_DATA_URL = "https://api.football-data.org/v4"
OPENFOOTBALL_URL = (
    "https://raw.githubusercontent.com/openfootball/football.json/master/"
    "{season}/tr.1.json"
)
ESPN_SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/soccer/tur.1/scoreboard"
)


@dataclass(frozen=True)
class ExternalFixture:
    provider: str
    provider_fixture_id: str
    fixture_id: int
    league: str
    kickoff_utc: str
    home_team: str
    away_team: str
    status: str
    home_goals: Optional[int] = None
    away_goals: Optional[int] = None
    source_updated_at: Optional[str] = None

    @property
    def match_date(self) -> str:
        return self.kickoff_utc[:10]

    @property
    def source_hash(self) -> str:
        values = (
            self.league,
            self.kickoff_utc,
            self.home_team,
            self.away_team,
            self.status,
            self.home_goals,
            self.away_goals,
        )
        return hashlib.sha256(json.dumps(values).encode("utf-8")).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def season_slug(day: Optional[date] = None) -> str:
    day = day or datetime.now(timezone.utc).date()
    start = day.year if day.month >= 7 else day.year - 1
    return f"{start}-{str(start + 1)[-2:]}"


def normalize_status(value: str) -> str:
    value = (value or "").upper()
    if value in {"FINISHED", "FT", "AET", "PEN"}:
        return "FINISHED"
    if value in {"IN_PLAY", "PAUSED", "LIVE", "1H", "2H", "HT", "ET", "P"}:
        return "LIVE"
    if value in {"POSTPONED", "SUSPENDED", "CANCELLED", "CANCELED"}:
        return value.replace("CANCELED", "CANCELLED")
    return "SCHEDULED"


def parse_football_data_matches(payload: dict, league: str) -> list[ExternalFixture]:
    fixtures = []
    for item in payload.get("matches", []):
        fixture_id = int(item["id"])
        score = item.get("score", {}).get("fullTime") or {}
        fixtures.append(
            ExternalFixture(
                provider="football-data.org",
                provider_fixture_id=str(fixture_id),
                fixture_id=fixture_id,
                league=league,
                kickoff_utc=item["utcDate"],
                home_team=normalize_team_name(item["homeTeam"]["name"]),
                away_team=normalize_team_name(item["awayTeam"]["name"]),
                status=normalize_status(item.get("status", "SCHEDULED")),
                home_goals=score.get("home"),
                away_goals=score.get("away"),
                source_updated_at=item.get("lastUpdated"),
            )
        )
    return fixtures


def parse_espn_matches(payload: dict) -> list[ExternalFixture]:
    fixtures = []
    for item in payload.get("events", []):
        competition = item["competitions"][0]
        status_data = competition.get("status", {}).get("type", {})
        status_name = status_data.get("name", "STATUS_SCHEDULED").removeprefix("STATUS_")
        status = normalize_status(status_name)
        if status_data.get("state") == "post" and status_data.get("completed"):
            status = "FINISHED"
        elif status_data.get("state") == "in":
            status = "LIVE"
        competitors = {
            entry["homeAway"]: entry for entry in competition.get("competitors", [])
        }
        home = competitors["home"]
        away = competitors["away"]
        fixture_id = int(item["id"])
        fixtures.append(
            ExternalFixture(
                provider="espn",
                provider_fixture_id=str(fixture_id),
                fixture_id=fixture_id,
                league="T1",
                kickoff_utc=item["date"],
                home_team=normalize_team_name(home["team"]["displayName"]),
                away_team=normalize_team_name(away["team"]["displayName"]),
                status=status,
                home_goals=int(home["score"]) if status == "FINISHED" else None,
                away_goals=int(away["score"]) if status == "FINISHED" else None,
            )
        )
    return fixtures


def _openfootball_fixture_id(season: str, item: dict) -> int:
    identity = "|".join(
        str(item.get(key, ""))
        for key in ("round", "date", "time", "team1", "team2")
    )
    digest = hashlib.sha256(f"{season}|{identity}".encode("utf-8")).hexdigest()
    # Keep synthetic IDs inside PostgreSQL INTEGER while avoiding provider IDs.
    return 1_500_000_000 + (int(digest[:12], 16) % 500_000_000)


def _score_pair(score) -> tuple[Optional[int], Optional[int]]:
    if isinstance(score, dict):
        score = score.get("ft")
    if isinstance(score, list) and len(score) == 2:
        return score[0], score[1]
    return None, None


def parse_openfootball_matches(
    payload: dict,
    season: str,
    today: Optional[date] = None,
) -> list[ExternalFixture]:
    today = today or datetime.now(timezone.utc).date()
    istanbul = ZoneInfo("Europe/Istanbul")
    fixtures = []
    for item in payload.get("matches", []):
        match_day = date.fromisoformat(item["date"])
        kickoff_time = time.fromisoformat(item.get("time") or "12:00")
        kickoff = datetime.combine(match_day, kickoff_time, istanbul).astimezone(timezone.utc)
        home_goals, away_goals = _score_pair(item.get("score"))
        finished = match_day < today and home_goals is not None and away_goals is not None
        status = "FINISHED" if finished else "SCHEDULED"
        if match_day < today and not finished:
            # OpenFootball sometimes leaves postponed/unplayed matches without a
            # score in an older season file. They must not re-enter the app as
            # upcoming fixtures.
            status = "POSTPONED"
        fixture_id = _openfootball_fixture_id(season, item)
        fixtures.append(
            ExternalFixture(
                provider="openfootball",
                provider_fixture_id=str(fixture_id),
                fixture_id=fixture_id,
                league="T1",
                kickoff_utc=kickoff.isoformat().replace("+00:00", "Z"),
                home_team=normalize_team_name(item["team1"]),
                away_team=normalize_team_name(item["team2"]),
                status=status,
                home_goals=home_goals if finished else None,
                away_goals=away_goals if finished else None,
            )
        )
    return fixtures


class FixtureProvider:
    def __init__(self, http=None):
        self.http = http or requests.Session()
        self.request_count = 0

    def football_data(
        self,
        token: str,
        date_from: date,
        date_to: date,
    ) -> list[ExternalFixture]:
        fixtures = []
        for league, competition in FOOTBALL_DATA_COMPETITIONS.items():
            response = self.http.get(
                f"{FOOTBALL_DATA_URL}/competitions/{competition}/matches",
                headers={"X-Auth-Token": token},
                params={"dateFrom": date_from.isoformat(), "dateTo": date_to.isoformat()},
                timeout=30,
            )
            self.request_count += 1
            response.raise_for_status()
            fixtures.extend(parse_football_data_matches(response.json(), league))
        return fixtures

    def openfootball(
        self,
        season: str,
        today: Optional[date] = None,
    ) -> list[ExternalFixture]:
        start_year = int(season[:4])
        for offset in range(3):
            candidate_start = start_year - offset
            candidate = f"{candidate_start}-{str(candidate_start + 1)[-2:]}"
            response = self.http.get(OPENFOOTBALL_URL.format(season=candidate), timeout=30)
            self.request_count += 1
            if response.status_code == 404:
                continue
            response.raise_for_status()
            return parse_openfootball_matches(response.json(), candidate, today=today)
        raise RuntimeError(f"No OpenFootball Süper Lig dataset found near season {season}")

    def espn_super_lig(
        self,
        date_from: date,
        date_to: date,
    ) -> list[ExternalFixture]:
        month = date_from.replace(day=1)
        last_month = date_to.replace(day=1)
        fixtures = []
        while month <= last_month:
            response = self.http.get(
                ESPN_SCOREBOARD_URL,
                params={"dates": month.strftime("%Y%m"), "limit": 1000},
                timeout=30,
            )
            self.request_count += 1
            response.raise_for_status()
            fixtures.extend(parse_espn_matches(response.json()))
            month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
        return [
            fixture
            for fixture in fixtures
            if date_from <= date.fromisoformat(fixture.match_date) <= date_to
        ]


def upsert_fixtures(fixtures: Iterable[ExternalFixture], db) -> tuple[int, int]:
    inserted = 0
    updated = 0
    synced_at = utc_now()
    for incoming in fixtures:
        state = (
            db.query(FixtureSyncState)
            .filter_by(
                provider=incoming.provider,
                provider_fixture_id=incoming.provider_fixture_id,
            )
            .first()
        )
        fixture = db.get(Fixture, state.FixtureID if state else incoming.fixture_id)
        if state is None and fixture is None:
            # A fallback provider can later be replaced by the primary source.
            # Reuse the natural match identity so that this source switch does
            # not create a duplicate fixture in the mobile API.
            fixture = (
                db.query(Fixture)
                .filter_by(
                    Date=incoming.match_date,
                    League=incoming.league,
                    HomeTeam=incoming.home_team,
                    AwayTeam=incoming.away_team,
                )
                .first()
            )
            if fixture is not None:
                state = db.get(FixtureSyncState, fixture.FixtureID)
                if state is not None:
                    state.provider = incoming.provider
                    state.provider_fixture_id = incoming.provider_fixture_id
        schedule_changed = fixture is None or any(
            (
                fixture.Date != incoming.match_date,
                fixture.League != incoming.league,
                fixture.HomeTeam != incoming.home_team,
                fixture.AwayTeam != incoming.away_team,
                state is not None and state.kickoff_utc != incoming.kickoff_utc,
            )
        )

        if fixture is None:
            fixture = Fixture(FixtureID=incoming.fixture_id)
            db.add(fixture)
            inserted += 1
        elif state is not None and state.source_hash != incoming.source_hash:
            updated += 1

        fixture.Date = incoming.match_date
        fixture.League = incoming.league
        fixture.HomeTeam = incoming.home_team
        fixture.AwayTeam = incoming.away_team
        fixture.Status = incoming.status
        fixture.HomeGoals = incoming.home_goals
        fixture.AwayGoals = incoming.away_goals
        fixture.LastUpdated = synced_at

        if state is None:
            state = FixtureSyncState(
                FixtureID=fixture.FixtureID,
                provider=incoming.provider,
                provider_fixture_id=incoming.provider_fixture_id,
                kickoff_utc=incoming.kickoff_utc,
                source_hash=incoming.source_hash,
                needs_prediction=incoming.status == "SCHEDULED",
                synced_at=synced_at,
            )
            db.add(state)
        else:
            state.kickoff_utc = incoming.kickoff_utc
            state.source_hash = incoming.source_hash
            state.source_updated_at = incoming.source_updated_at
            state.synced_at = synced_at
            if incoming.status == "SCHEDULED" and (
                schedule_changed or fixture.Predicted_Label is None
            ):
                state.needs_prediction = True
            elif incoming.status != "SCHEDULED":
                state.needs_prediction = False
        state.source_updated_at = incoming.source_updated_at
    db.commit()
    return inserted, updated


def _record_sync(provider: str, mode: str, fetch, db) -> tuple[int, int]:
    run = SyncRun(provider=provider, mode=mode, started_at=utc_now(), status="RUNNING")
    db.add(run)
    db.commit()
    try:
        fixtures, request_count = fetch()
        inserted, updated = upsert_fixtures(fixtures, db)
        run.request_count = request_count
        run.inserted_count = inserted
        run.updated_count = updated
        run.status = "SUCCESS"
        return inserted, updated
    except Exception as exc:
        db.rollback()
        run = db.get(SyncRun, run.id)
        run.status = "FAILED"
        run.error_message = str(exc)[:2000]
        raise
    finally:
        run.completed_at = utc_now()
        db.commit()


def sync_all(mode: str = "refresh", today: Optional[date] = None) -> dict:
    today = today or datetime.now(timezone.utc).date()
    days_forward = 45 if mode == "full" else 2
    date_from = today - timedelta(days=1)
    date_to = today + timedelta(days=days_forward)
    token = os.environ.get("FOOTBALL_DATA_TOKEN", "").strip()
    season = os.environ.get("OPENFOOTBALL_SEASON", season_slug(today))
    provider = FixtureProvider()
    totals = {"inserted": 0, "updated": 0, "requests": 0}

    with SessionLocal() as db:
        if token:
            start = provider.request_count
            added, changed = _record_sync(
                "football-data.org",
                mode,
                lambda: (
                    provider.football_data(token, date_from, date_to),
                    provider.request_count - start,
                ),
                db,
            )
            totals["inserted"] += added
            totals["updated"] += changed
        elif os.environ.get("CI"):
            raise RuntimeError("FOOTBALL_DATA_TOKEN is required in GitHub Actions")

        start = provider.request_count

        def fetch_openfootball_window():
            try:
                fixtures = provider.openfootball(season, today=today)
            except (RuntimeError, requests.RequestException):
                fixtures = []
            fixtures = [
                fixture
                for fixture in fixtures
                if date_from <= date.fromisoformat(fixture.match_date) <= date_to
            ]
            if not fixtures:
                fixtures = provider.espn_super_lig(date_from, date_to)
            return fixtures, provider.request_count - start

        added, changed = _record_sync(
            "super-lig",
            mode,
            fetch_openfootball_window,
            db,
        )
        totals["inserted"] += added
        totals["updated"] += changed
        totals["requests"] = provider.request_count
    return totals
