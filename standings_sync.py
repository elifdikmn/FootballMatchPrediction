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

    response = http.get(
        API_URL,
        params={"league": SUPER_LIG_API_ID, "season": season_start_year(target_date)},
        headers={"x-apisports-key": api_key},
        timeout=30,
    )
    response.raise_for_status()
    table = _parse_table(response.json())
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-offset", type=int, default=0)
    parser.add_argument("--retry", action="store_true")
    args = parser.parse_args()
    target_date = datetime.now(ISTANBUL).date() + timedelta(days=args.target_offset)
    init_db()
    with SessionLocal() as db:
        result = sync_super_lig_standings(
            db,
            os.environ.get("API_FOOTBALL_KEY", "").strip(),
            target_date,
            retry=args.retry,
        )
    print("Süper Lig standings sync:", {**result, "date": target_date.isoformat()})


if __name__ == "__main__":
    main()
