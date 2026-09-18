# Matchday interface refresh

The Fixtures screen has previous/next day controls, a graphical date picker and a Today action. It requests `/scheduled-predictions?date=YYYY-MM-DD`; the backend returns saved predictions for that day, including completed matches. An empty date is explicitly shown as having no saved predictions. It does not fabricate historical predictions or fetch a new prediction for an old match. Requests cancelled by a subsequent date selection cannot overwrite the selected day's results.

Match insights separates probabilities, the leading outcome, recent form and explanatory text. Tied or missing probabilities do not produce a false favorite. API-Football's aggregate last-five form percentage is displayed as a rating; W/D/L history is only displayed when actually supplied.

## Logos

Deploy the updated Flask backend alongside the iOS app. `/branding` obtains each supported league's current-season teams from API-Football using the existing server-side `API_FOOTBALL_KEY`. The API key is never sent to iOS. Successful catalogues are cached for 24 hours per process. Existing name aliases are shared with prediction processing; iOS scopes club lookup to the league and refuses ambiguous matches. New teams appear automatically when the provider returns them. Clubs outside the returned current-season catalogue use a neutral placeholder.

All six supported leagues use API-Football IDs: Bundesliga 78, Premier League 39, La Liga 140, Serie A 135, Ligue 1 61, Süper Lig 203. Official provider documentation: https://www.api-football.com/documentation-v3 . Logo PNGs are loaded over HTTPS from `media.api-sports.io`. Unavailable logos use a neutral shield, never a guessed club badge.

## Verification

- Run `python -m unittest discover -s tests -v` with project dependencies installed.
- Build the MatchdayLedger scheme for an iOS Simulator in Xcode.
- Check previous/next days across month/year boundaries, Today, date picker, league filters and empty dates.
- With a configured backend, check crests in fixtures, live matches, match detail and standings.
- Check Match insights on a small iPhone and with larger accessibility text.

The development sandbox passed Swift syntax parsing but blocked Xcode's SwiftUI macro subprocess and CoreSimulator, so a full build and rendered-device review still need to run in Xcode outside that sandbox. All six league PNG URLs returned HTTP 200. Live team catalogue verification needs a configured API key.
