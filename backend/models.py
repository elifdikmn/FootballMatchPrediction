from sqlalchemy import Column, Integer, String, Float, Boolean, JSON, Text, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Fixture(Base):
    __tablename__ = 'fixtures'

    FixtureID = Column(Integer, primary_key=True)
    Date = Column(String)
    League = Column(String)
    HomeTeam = Column(String)
    AwayTeam = Column(String)
    Predicted_Label = Column(String)
    HomeWinPct = Column(Float)
    DrawPct = Column(Float)
    AwayWinPct = Column(Float)
    HomeGoals = Column(Float, nullable=True)
    AwayGoals = Column(Float, nullable=True)
    Status = Column(String)
    LastUpdated = Column(String)
    B365H = Column(Float, nullable=True)
    B365D = Column(Float, nullable=True)
    B365A = Column(Float, nullable=True)

class Event(Base):
    __tablename__ = 'events'

    id = Column(Integer, primary_key=True, autoincrement=True)
    FixtureID = Column(Integer)
    minute = Column(Integer)
    team = Column(String)
    player = Column(String)
    type = Column(String)
    detail = Column(String)
    assist = Column(String, nullable=True)

class Standing(Base):
    __tablename__ = 'standings'

    id = Column(Integer, primary_key=True, autoincrement=True)
    league = Column(String)
    team_name = Column(String)
    rank = Column(Integer)
    points = Column(Integer)
    goals_diff = Column(Integer)
    played = Column(Integer)
    win = Column(Integer)
    draw = Column(Integer)
    lose = Column(Integer)
    last_updated = Column(String)


class FixtureSyncState(Base):
    """Provider metadata kept separately so the existing fixtures table stays compatible."""

    __tablename__ = "fixture_sync_state"
    __table_args__ = (
        UniqueConstraint("provider", "provider_fixture_id", name="uq_fixture_provider_id"),
    )

    FixtureID = Column(Integer, primary_key=True)
    provider = Column(String, nullable=False)
    provider_fixture_id = Column(String, nullable=False)
    kickoff_utc = Column(String, nullable=False)
    source_hash = Column(String, nullable=False)
    needs_prediction = Column(Boolean, nullable=False, default=True)
    source_updated_at = Column(String, nullable=True)
    synced_at = Column(String, nullable=False)


class ModelPrediction(Base):
    __tablename__ = "model_predictions"
    __table_args__ = (
        UniqueConstraint("FixtureID", "model_version", name="uq_fixture_model_version"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    FixtureID = Column(Integer, nullable=False, index=True)
    model_version = Column(String, nullable=False)
    predicted_label = Column(String, nullable=False)
    home_win_pct = Column(Float, nullable=False)
    draw_pct = Column(Float, nullable=False)
    away_win_pct = Column(Float, nullable=False)
    feature_snapshot = Column(JSON, nullable=True)
    predicted_at = Column(String, nullable=False)


class PredictionSnapshot(Base):
    """Append-only prediction history for pre-match and live models."""

    __tablename__ = "prediction_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "FixtureID", "prediction_type", "version",
            name="uq_prediction_snapshot_version",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    FixtureID = Column(Integer, nullable=False, index=True)
    prediction_type = Column(String, nullable=False, index=True)
    version = Column(Integer, nullable=False)
    trigger = Column(String, nullable=False, default="INITIAL")
    model_version = Column(String, nullable=False)
    predicted_label = Column(String, nullable=False)
    home_win_pct = Column(Float, nullable=False)
    draw_pct = Column(Float, nullable=False)
    away_win_pct = Column(Float, nullable=False)
    feature_snapshot = Column(JSON, nullable=True)
    predicted_at = Column(String, nullable=False)


class LiveMatchState(Base):
    """Latest provider state for a live match, keyed to the canonical fixture."""

    __tablename__ = "live_match_states"

    FixtureID = Column(Integer, primary_key=True)
    provider = Column(String, nullable=False, default="api-football")
    provider_fixture_id = Column(String, nullable=False, unique=True)
    league = Column(String, nullable=False)
    score = Column(String, nullable=True)
    elapsed = Column(Integer, nullable=True)
    status = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String, nullable=False)
    mode = Column(String, nullable=False)
    started_at = Column(String, nullable=False)
    completed_at = Column(String, nullable=True)
    request_count = Column(Integer, nullable=False, default=0)
    inserted_count = Column(Integer, nullable=False, default=0)
    updated_count = Column(Integer, nullable=False, default=0)
    status = Column(String, nullable=False)
    error_message = Column(Text, nullable=True)


class ProviderRequestBudget(Base):
    __tablename__ = 'provider_request_budget'
    day = Column(String, primary_key=True)
    used = Column(Integer, nullable=False, default=0)


class ProviderCache(Base):
    __tablename__ = 'provider_cache'
    key = Column(String, primary_key=True)
    payload = Column(JSON, nullable=True)
    updated_at = Column(Float, nullable=False, default=0)
    lease_until = Column(Float, nullable=False, default=0)
