"""Persist the Süper Lig table after the day's matches have finished."""

import argparse
from datetime import date, datetime, time, timedelta, timezone
import os
from zoneinfo import ZoneInfo

import requests

from db_setup import SessionLocal, init_db
from models import Fixture, Standing
from team_normalizer import normalize_team_name


API_URL = "https://v3.football.api-sports.io/standings"
SUPER_LIG_API_ID = 203
ISTANBUL = ZoneInfo("Europe/Istanbul")
FINISHED_STATUSES = {"FINISHED", "FT", "AET", "PEN"}


def season_start_year(day: date) -> int:
    return day.year if day.month >= 7 else day.year - 1


def _already_updated(db, target_date: date) -> bool:
    latest = (
        db.query(Standing.last_updated)
        .filter_by(league=str(SUPER_LIG_API_ID))
        .order_by(Standing.last_updated.desc())
        .first()
    )
    if not latest or not latest[0]:
        return False
    try:
        updated_at = datetime.fromisoformat(latest[0].replace("Z", "+00:00"))
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    expected_after = datetime.combine(target_date, time(23, 0), ISTANBUL).astimezone(timezone.utc)
    return updated_at >= expected_after


def _parse_table(payload: dict) -> list[dict]:
    response = payload.get("response") or []
    if not response:
        errors = payload.get("errors") or "empty response"
        raise RuntimeError(f"Süper Lig standings unavailable: {errors}")
    groups = response[0].get("league", {}).get("standings", [])
    if not groups:
        raise RuntimeError("Süper Lig standings response has no table")
    return groups[0]


def sync_super_lig_standings(
    db,
    api_key: str,
    target_date: date,
    retry: bool = False,
    http=requests,
) -> dict:
    fixtures = db.query(Fixture).filter_by(League="T1", Date=target_date.isoformat()).all()
    if not fixtures:
        return {"status": "skipped", "reason": "no Süper Lig matches", "rows": 0}
    if _already_updated(db, target_date):
        return {"status": "skipped", "reason": "already updated", "rows": 0}
    if not retry and any((fixture.Status or "").upper() not in FINISHED_STATUSES for fixture in fixtures):
        return {"status": "skipped", "reason": "matches still in progress", "rows": 0}
    if not api_key:
        raise RuntimeError("API_FOOTBALL_KEY is required for Süper Lig standings")

    from provider_cache import FootballClient
    from sqlalchemy.orm import sessionmaker
    client = FootballClient(sessions=sessionmaker(bind=db.bind, expire_on_commit=False), http=http, key=api_key)
    payload, fetched_at = client.fetch(
        "standings", {"league": SUPER_LIG_API_ID, "season": season_start_year(target_date)},
        ttl=300, purpose="standings",
    )
    if payload is None or client.clock() - fetched_at > 300:
        return {"status": "skipped", "reason": "provider unavailable or request budget exhausted", "rows": 0}
    table = _parse_table(payload)
    updated_at = datetime.now(timezone.utc).isoformat()
    returned_names = set()

    for item in table:
        team_name = normalize_team_name(item["team"]["name"])
        returned_names.add(team_name)
        stats = item.get("all") or {}
        row = (
            db.query(Standing)
            .filter_by(league=str(SUPER_LIG_API_ID), team_name=team_name)
            .first()
        )
        if row is None:
            row = Standing(league=str(SUPER_LIG_API_ID), team_name=team_name)
            db.add(row)
        row.rank = item.get("rank")
        row.points = item.get("points")
        row.goals_diff = item.get("goalsDiff")
        row.played = stats.get("played")
        row.win = stats.get("win")
        row.draw = stats.get("draw")
        row.lose = stats.get("lose")
        row.last_updated = updated_at

    stale = (
        db.query(Standing)
        .filter(Standing.league == str(SUPER_LIG_API_ID))
        .filter(~Standing.team_name.in_(returned_names))
        .all()
    )
    for row in stale:
        db.delete(row)
    db.commit()
    return {"status": "updated", "reason": None, "rows": len(table)}



def sync_european_standings(db, token: str, http=requests) -> dict:
    """Fetch the overall table once per league, retaining old data on errors."""
    from fixture_sync import FOOTBALL_DATA_COMPETITIONS, FOOTBALL_DATA_URL

    if not token:
        raise RuntimeError("FOOTBALL_DATA_TOKEN is required for European standings")
    api_ids = {"D1": "78", "E0": "39", "SP1": "140", "I1": "135", "F1": "61"}
    counts = {}
    errors = []
    for code, competition in FOOTBALL_DATA_COMPETITIONS.items():
        try:
            response = http.get(
                f"{FOOTBALL_DATA_URL}/competitions/{competition}/standings",
                headers={"X-Auth-Token": token}, timeout=30,
            )
            response.raise_for_status()
            tables = response.json().get("standings", [])
            table = next((entry["table"] for entry in tables if entry.get("type") == "TOTAL"), [])
            if not table:
                raise ValueError("No TOTAL standings returned")
            # Validate the entire response before replacing the stored table.
            now = datetime.now(timezone.utc).isoformat()
            rows = [Standing(
                league=api_ids[code], team_name=normalize_team_name(item["team"]["name"]),
                rank=item["position"], points=item["points"], goals_diff=item["goalDifference"],
                played=item["playedGames"], win=item["won"], draw=item["draw"],
                lose=item["lost"], last_updated=now,
            ) for item in table]
            db.query(Standing).filter_by(league=api_ids[code]).delete()
            db.add_all(rows)
            db.commit()
            counts[code] = len(rows)
        except (requests.RequestException, ValueError, KeyError, TypeError) as error:
            db.rollback()
            errors.append(f"{code}: {type(error).__name__}")
    if errors:
        raise RuntimeError("Standings sync incomplete: " + "; ".join(errors))
    return counts

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-offset", type=int, default=0)
    parser.add_argument("--retry", action="store_true")
    parser.add_argument("--europe", action="store_true")
    args = parser.parse_args()
    target_date = datetime.now(ISTANBUL).date() + timedelta(days=args.target_offset)
    init_db()
    with SessionLocal() as db:
        if args.europe:
            result = sync_european_standings(db, os.environ.get("FOOTBALL_DATA_TOKEN", "").strip())
            print("European standings sync:", result)
            return
        result = sync_super_lig_standings(
            db,
            os.environ.get("API_FOOTBALL_KEY", "").strip(),
            target_date,
            retry=args.retry,
        )
    print("Süper Lig standings sync:", {**result, "date": target_date.isoformat()})


if __name__ == "__main__":
    main()
