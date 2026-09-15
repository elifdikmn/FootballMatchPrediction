---
name: run-footballmatchprediction
description: Build, run, and smoke-test the FootballMatchPrediction Flask backend. Use when asked to start the app, run it, boot the server, test it, hit its API, or verify a change actually works.
---

This is a Flask API (`app.py`) serving football match predictions and
standings from local CSVs, pickled scikit-learn models, and a SQLite
DB. Drive it with `curl` via the smoke-test script at
`.claude/skills/run-footballmatchprediction/smoke.sh` — it boots the
server, hits every route that works without live internet access, and
checks the responses.

All paths below are relative to the repo root.

## Prerequisites

No system packages needed beyond Python 3 and pip. Python deps:

```bash
pip install -r requirements.txt --ignore-installed blinker
```

`--ignore-installed blinker` is required in a container that ships a
Debian-packaged `blinker` — plain `pip install` fails with
`Cannot uninstall blinker 1.7.0, RECORD file not found`.

## Setup

The app needs a `.env` file (gitignored, not in the repo) with the
football API keys. Copy the template and fill in real values:

```bash
cp .env.example .env
```

```
API_FOOTBALL_KEY=...   # required for live-data routes; offline routes below don't need a real key
THE_ODDS_API_KEY=...   # same
FLASK_DEBUG=false       # optional, default false
SQL_ECHO=false          # optional, default false
```

`config.py` loads these via `python-dotenv`. The app will still boot
and serve the offline routes even with placeholder key values — they
only matter for routes that call `v3.football.api-sports.io` directly.

No separate build step.

## Run (agent path)

```bash
bash .claude/skills/run-footballmatchprediction/smoke.sh
```

This launches `python3 app.py` in the background, polls
`GET /predictioncache` until it's ready (usually ~2-5s), then hits:

| route | needs live internet? |
|---|---|
| `GET /predictioncache` | no — reads local `prediction_cache.json` |
| `GET /scheduled-predictions` | no — same cache file |
| `GET /api/evaluation` | no — reads local `matches.db` |
| `GET /standings/<E0\|SP1\|I1\|D1\|F1\|T1>` | no — reads local `matches.db` |

and reports `OK`/`FAIL` per route, then shuts the server down (kills
whatever is listening on port 5000). Exit code is non-zero if anything
failed. Server log is written to `/tmp/fmp_app.log` — check it first
on any failure.

To drive it manually instead of the script (e.g. to hit one specific
route or watch startup logs):

```bash
python3 app.py &> /tmp/fmp_app.log &
sleep 3
curl http://127.0.0.1:5000/standings/E0
lsof -ti:5000 -sTCP:LISTEN | xargs -r kill   # stop when done
```

Routes that call the live API directly — `/data-range`,
`/live-matches-with-predictions`, `/standings/grouped`, `/live-simple`,
`/events/<id>`, `/prediction/<id>` — are **not** covered by the smoke
script. They need real outbound access to
`v3.football.api-sports.io`, which a network-restricted container
(like this one) blocks with a `ProxyError`/`403` — that's an
environment limitation, not something the smoke test can verify.

## Run (human path)

```bash
python3 app.py
```

Runs the Flask dev server in the foreground on `0.0.0.0:5000`.
`Ctrl-C` to stop. Not meaningfully different from the agent path
beyond blocking the terminal — same entrypoint either way.

## Test

No test suite exists in this repo (`find . -iname '*test*'` turns up
nothing). The smoke script above is the only verification available.

---

## Gotchas

- **Importing `fixture` or `app` used to crash immediately** if
  outbound access to `v3.football.api-sports.io` wasn't available —
  `live_predictor.py` had module-level code that called the live API
  as a side effect of just being imported. This was fixed (see git
  history), but if a future edit reintroduces top-level code in
  `live_predictor.py`, the app will silently stop being importable
  again in any offline/sandboxed environment. Keep all API calls
  inside functions.
- **`/standings/<code>` takes football-data.co.uk-style codes**
  (`E0`, `SP1`, `I1`, `D1`, `F1`, `T1`), but the `standings` table in
  `matches.db` stores numeric api-sports.io league IDs (`39`, `140`,
  etc.). The route translates through `fixture.py`'s `league_ids`
  dict — if you add a new league, it must go in that dict or the
  route will silently return `[]`.
- **`scikit-learn` version-mismatch warnings on startup** (`Trying to
  unpickle estimator ... from version 1.6.1 when using version
  1.9.1`) are expected noise from the installed sklearn being newer
  than the one the `.pkl` models were trained with. Not a failure —
  the models still load and predict fine.

## Troubleshooting

- **`Cannot uninstall blinker 1.7.0, RECORD file not found`** during
  `pip install -r requirements.txt`: add `--ignore-installed blinker`
  to the install command (see Prerequisites).
- **`ModuleNotFoundError: No module named 'dotenv'` (or `flask`,
  `sqlalchemy`, etc.)**: dependencies weren't installed — run the
  `pip install` command above. If new imports get added to the code
  without a matching entry in `requirements.txt`, add it there too.
- **Smoke script hangs at "Waiting for readiness"**: check
  `/tmp/fmp_app.log` — most likely a missing dependency or a `.env`
  file that doesn't exist yet (see Setup).
- **`requests.exceptions.ProxyError` / HTTP 500 on `/data-range` or
  other live-data routes**: expected in a network-restricted
  container. Not a code bug — those routes need real access to
  `v3.football.api-sports.io`.
