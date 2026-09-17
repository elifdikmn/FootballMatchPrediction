"""Shared API-Football cache and atomic UTC daily request budget.

Every reservation commits before HTTP so even failed requests consume budget.
Detail requests stop at 80, score refreshes at 98, standings at 100.
"""
from datetime import datetime, timezone
from time import time
import json
import os

import requests
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from db_setup import SessionLocal
from models import ProviderCache, ProviderRequestBudget


def insert_missing(db, model, values):
    insert = pg_insert if db.bind.dialect.name == 'postgresql' else sqlite_insert
    db.execute(insert(model).values(**values).on_conflict_do_nothing())


class FootballClient:
    def __init__(self, sessions=SessionLocal, http=requests, key=None, clock=time):
        self.sessions, self.http, self.clock = sessions, http, clock
        self.key = key if key is not None else os.environ.get('API_FOOTBALL_KEY', '').strip()

    def read(self, key):
        with self.sessions() as db:
            row = db.get(ProviderCache, key)
            return (row.payload, row.updated_at) if row else (None, 0)

    def reserve(self, purpose):
        day = datetime.fromtimestamp(self.clock(), timezone.utc).date().isoformat()
        ceiling = {'detail': 80, 'live': 98, 'standings': 100}[purpose]
        with self.sessions() as db:
            insert_missing(db, ProviderRequestBudget, {'day': day, 'used': 0})
            result = db.execute(update(ProviderRequestBudget).where(
                ProviderRequestBudget.day == day, ProviderRequestBudget.used < ceiling
            ).values(used=ProviderRequestBudget.used + 1))
            db.commit()
            return result.rowcount == 1

    def fetch(self, path, params, ttl=300, purpose='detail'):
        key = path + ':' + json.dumps(params, sort_keys=True)
        now = self.clock()
        with self.sessions() as db:
            insert_missing(db, ProviderCache, {'key': key, 'updated_at': 0, 'lease_until': 0})
            row = db.get(ProviderCache, key)
            if row.payload is not None and now - row.updated_at < ttl:
                return row.payload, row.updated_at
            claimed = db.execute(update(ProviderCache).where(
                ProviderCache.key == key, ProviderCache.lease_until <= now,
            ).values(lease_until=now + 60)).rowcount
            old = (row.payload, row.updated_at)
            db.commit()
        if not claimed:
            return old
        if not self.key or not self.reserve(purpose):
            return old
        try:
            response = self.http.get('https://v3.football.api-sports.io/' + path,
                                     params=params, headers={'x-apisports-key': self.key}, timeout=25)
            response.raise_for_status()
            payload = response.json()
            if payload.get('errors') or not isinstance(payload.get('response'), list):
                return old
            with self.sessions() as db:
                db.execute(update(ProviderCache).where(ProviderCache.key == key).values(
                    payload=payload, updated_at=now, lease_until=0))
                db.commit()
            return payload, now
        except (requests.RequestException, ValueError):
            return old
