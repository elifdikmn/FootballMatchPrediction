#!/usr/bin/env bash
# Smoke-tests the FootballMatchPrediction Flask backend (app.py).
# Boots the server, hits the routes that work fully offline (local
# CSVs/pickles/SQLite - no live api-sports.io access needed), checks
# their responses, then shuts the server down.
#
# Run from the repo root:
#   bash .claude/skills/run-footballmatchprediction/smoke.sh
set -uo pipefail
cd "$(dirname "$0")/../../.."

PORT=5000
LOG=/tmp/fmp_app.log
RESP=/tmp/fmp_resp.json
FAIL=0

if lsof -ti:$PORT -sTCP:LISTEN > /dev/null 2>&1; then
  echo "Port $PORT already in use - stopping whatever is listening first."
  lsof -ti:$PORT -sTCP:LISTEN | xargs -r kill
  sleep 1
fi

echo "== Launching app.py (log: $LOG) =="
python3 app.py &> "$LOG" &
PID=$!

echo "== Waiting for readiness (GET /predictioncache) =="
ready=0
for i in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:$PORT/predictioncache" > /dev/null 2>&1; then
    ready=1
    echo "Ready after ${i}s"
    break
  fi
  sleep 1
done

if [ "$ready" -ne 1 ]; then
  echo "SERVER NEVER CAME UP. Log tail:"
  tail -50 "$LOG"
  kill "$PID" 2>/dev/null
  exit 1
fi

check() {
  local desc="$1" url="$2"
  code=$(curl -s -o "$RESP" -w "%{http_code}" "$url")
  if [ "$code" != "200" ]; then
    echo "FAIL [$desc] -> HTTP $code"
    FAIL=1
  else
    echo "OK   [$desc] -> HTTP $code ($(wc -c < "$RESP" | tr -d ' ') bytes)"
  fi
}

check "/predictioncache"       "http://127.0.0.1:$PORT/predictioncache"
check "/scheduled-predictions" "http://127.0.0.1:$PORT/scheduled-predictions"
check "/api/evaluation"        "http://127.0.0.1:$PORT/api/evaluation"
for code in E0 SP1 I1 D1 F1 T1; do
  check "/standings/$code" "http://127.0.0.1:$PORT/standings/$code"
done

echo "== Stopping server =="
lsof -ti:$PORT -sTCP:LISTEN | xargs -r kill

if [ "$FAIL" -ne 0 ]; then
  echo "SMOKE TEST FAILED. Full server log at $LOG"
  exit 1
fi
echo "ALL OK"
