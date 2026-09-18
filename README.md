# Football Match Prediction / MatchdayLedger

MatchdayLedger is an iOS football application backed by a Flask API, a
PostgreSQL/Supabase database, scheduled data synchronization and league-specific
machine-learning models. It covers Premier League (`E0`), Bundesliga (`D1`),
La Liga (`SP1`), Serie A (`I1`), Ligue 1 (`F1`) and Turkish Süper Lig (`T1`).

The app shows fixtures, saved pre-match predictions, results, league tables,
team/league branding and a separate live-match experience. The original thesis
and evaluation are in [FOOTBALLMATCHPREDICTION.pdf](docs/FOOTBALLMATCHPREDICTION.pdf).

## Current architecture

```text
football-data.org ─┐
                   ├─ fixture_sync.py ── Supabase/PostgreSQL ── Flask API ── SwiftUI app
OpenFootball/ESPN ─┘                         ▲
                                             │
API-Football ── central live worker ─────────┘
                       │
                       └─ shared cache + daily request budget
```

Five European leagues use football-data.org for scheduled fixtures, results and
standings. Süper Lig fixtures use OpenFootball with an ESPN fallback.
API-Football supplies the six-league live-score batch, on-demand events,
in-play odds and the nightly Süper Lig table.

The database is the source of truth. Mobile clients never receive provider API
keys and never contact upstream football providers directly.

## Prediction behavior

- Pre-match probabilities remain stored on the fixture while a match is live.
- Every changed pre-match prediction creates a versioned `PRE_MATCH` snapshot.
- A live prediction creates a separate `LIVE` snapshot and cannot overwrite the
  pre-match prediction.
- The home screen displays the pre-match prediction with a `LIVE NOW` marker.
- The Live tab can request a live prediction from match detail. Live odds and
  events are fetched only when needed and shared through the database cache.

Pre-match features include recent form, Elo ratings, xG-derived values and
normalized market probabilities. Live-model features include half-time
score/result, cards and normalized in-play odds.

## Live-score quota protection

- `.github/workflows/sync-live.yml` is scheduled approximately every five
  minutes.
- Before a provider call, the worker checks whether a supported fixture is
  inside its match window.
- One `fixtures?live=all` request covers all six leagues.
- The response is stored in Supabase and shared by all users.
- Events and live odds are requested only from match detail.
- Successful empty responses are cached; failed responses retain prior data.
- Request reservations are atomic and failed HTTP requests still count.
- Detail calls stop at 80 tracked requests, live-score calls at 98 and standings
  at 100, leaving quota for essential updates.

GitHub scheduled jobs may start late, so a five-minute cron expression is not a
real-time service guarantee. Calls made outside this project with the same key
cannot be counted by the application.

## Repository layout

```text
.
├── backend/                       Flask API, synchronization, ML code and tests
├── datasets/historical/           Six league historical CSV datasets
├── datasets/external/             Supplementary xG data
├── datasets/snapshots/            Committed research snapshots
├── models/artifacts/              Versioned pre-match and live model artifacts
├── frontend/ios/MatchdayLedger/   SwiftUI app and local logo assets
├── docs/                          Thesis and entity-relationship diagrams
├── assets/                        Thesis figures and screenshots
├── .github/workflows/             Scheduled production jobs
└── scripts/create_release_zip.py  Reproducible clean ZIP exporter
```

The former cache migration, local scheduler, scraper and duplicate evaluation
scripts were removed. Production scheduling lives in GitHub Actions. Runtime
cache files and local databases are excluded from the repository and clean
releases.

## Backend setup

Python 3.12 is recommended. The saved pre-match models use the pinned
scikit-learn version in `backend/requirements.txt`.

```bash
git clone https://github.com/elifdikmn/FootballMatchPrediction.git
cd FootballMatchPrediction
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
cp .env.example .env
```

Edit `.env` locally:

```dotenv
DATABASE_URL=postgresql://postgres.PROJECT_REF:PASSWORD@HOST:6543/postgres
FOOTBALL_DATA_TOKEN=your-football-data-org-token
API_FOOTBALL_KEY=your-api-football-key
MODEL_VERSION=baseline-v1
PORT=5001
```

If `DATABASE_URL` is omitted, development falls back to `sqlite:///matches.db`.
Never commit `.env` or paste credentials into source files.

Initialize/synchronize data and run the API:

```bash
cd backend
python sync_pipeline.py --mode full
PORT=5001 python app.py
```

Useful local checks:

```bash
python -m unittest discover -s tests -v
python live_sync.py
python standings_sync.py --europe
```

## iOS setup

Open `frontend/ios/MatchdayLedger/MatchdayLedger.xcodeproj` in Xcode.

`APIConfig.baseURL` in `frontend/ios/MatchdayLedger/MatchdayLedger/APIClient.swift`
defaults to `http://localhost:5001`, which works in the iOS Simulator. For a
physical iPhone, use the Mac's LAN address or a deployed HTTPS API.

The backend must be running or deployed for the iOS app to load data. GitHub
Actions can update Supabase while the Mac terminal is closed, but Actions do not
host the Flask API.

## GitHub configuration

Add these under **Settings → Secrets and variables → Actions**:

| Secret | Purpose |
| --- | --- |
| `DATABASE_URL` | Supabase session-pooler/PostgreSQL connection string |
| `FOOTBALLDATATOKEN` | football-data.org fixture and standings access |
| `API_FOOTBALL_KEY` | live scores, events, live odds and Süper Lig standings |

Optional repository variables:

| Variable | Purpose |
| --- | --- |
| `MODEL_VERSION` | Snapshot model label; defaults to `baseline-v1` |
| `OPENFOOTBALL_SEASON` | Pins Süper Lig season, e.g. `2026-27` |

Workflows:

- `sync-football-data.yml`: daily 45-day sync, three-hour near-term refresh,
  pending predictions and five European league tables.
- `sync-live.yml`: central live-score polling during match windows.
- `sync-super-lig-standings.yml`: 23:00 Türkiye update with midnight retry.

If `API_FOOTBALL_KEY` is missing, live sync warns and skips provider calls. Add
the secret and run **Sync live scores → Run workflow** to verify it.

## API routes used by the app

| Route | Purpose |
| --- | --- |
| `GET /prediction-dates` | Dates with saved predictions |
| `GET /scheduled-predictions?date=YYYY-MM-DD` | Fixtures and pre-match predictions |
| `GET /live-matches-with-predictions` | Shared live cache and latest live snapshot |
| `GET /prediction/<id>` | Stored pre-match explanation |
| `GET /prediction/<id>?type=live` | On-demand live prediction |
| `GET /events/<id>` | Cached/on-demand match events |
| `GET /standings/<league_code>` | Stored league table |
| `GET /branding` | League and team logo catalogue |

## Database tables

- `fixtures`: canonical fixture, score/status and pre-match prediction
- `fixture_sync_state`: upstream identity, kickoff and change tracking
- `model_predictions`: current result per fixture/model version
- `prediction_snapshots`: append-only `PRE_MATCH` and `LIVE` history
- `live_match_states`: canonical-to-API-Football live mapping
- `events`: cached match incidents
- `standings`: stored league tables
- `provider_cache`: shared upstream responses and leases
- `provider_request_budget`: atomic UTC daily API-Football counter
- `sync_runs`: fixture synchronization audit records

Tables are created automatically by `init_db()`.

## Clean release ZIP

```bash
python scripts/create_release_zip.py
```

The archive includes tracked source code, models, historical data, assets,
tests, documentation and workflows. It excludes credentials, Git history,
virtual environments, Xcode user settings, local databases, empty legacy model
placeholders and generated caches. The script verifies archive integrity and
checks filenames/content for accidental credentials.

## Tests and limitations

The backend suite covers fixture normalization/upserts, date queries,
prediction versioning, live reconciliation, central cache behavior, concurrent
quota reservation, standings and branding.

Known limitations:

- Draw remains the hardest class in the original evaluation.
- Live models were trained with an older scikit-learn version. They pass
  inference smoke tests but should be retrained with the production version.
- Live features do not directly model substitutions, injuries, current minute
  or full current score.
- Automatic lineup/injury ingestion and pre-match recalculation triggers remain
  future model work.
- A production deployment is required for terminal-independent mobile API
  access.

The thesis reports 57.5% accuracy and macro F1 of 54.3% for its evaluation set.
Those figures describe that experiment and do not guarantee future results.

## Next model-development phase

1. Freeze leakage-safe, time-based train/validation/test splits.
2. Add log loss, Brier score and reliability/calibration curves.
3. Retrain saved models under the pinned production environment.
4. Build timestamped features for lineups, injuries, substitutions, current
   score/minute and odds movement.
5. Compare calibrated baselines with gradient boosting and class-aware models.
6. Version datasets, features and models; test shadow predictions before
   promotion.

## License and author

Created by **Elif Dikmen**. Licensed under the [MIT License](LICENSE).

For academic use, cite this repository and the included thesis.
