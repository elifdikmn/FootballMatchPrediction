"""Canonical filesystem locations for the backend and research assets."""

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DATASETS_DIR = REPOSITORY_ROOT / "datasets"
HISTORICAL_DATA_DIR = DATASETS_DIR / "historical"
EXTERNAL_DATA_DIR = DATASETS_DIR / "external"
MODEL_ARTIFACTS_DIR = REPOSITORY_ROOT / "models" / "artifacts"
RUNTIME_DIR = REPOSITORY_ROOT / "runtime"
RUNTIME_DIR.mkdir(exist_ok=True)


def historical_dataset(league: str) -> Path:
    return HISTORICAL_DATA_DIR / f"{league}_matches.csv"
