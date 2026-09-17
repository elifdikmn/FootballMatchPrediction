import Foundation

/// Matches GET /scheduled-predictions
struct ScheduledPrediction: Codable, Identifiable {
    let fixtureId: Int
    let homeTeam: String
    let awayTeam: String
    let homeTeamLogo: URL?
    let awayTeamLogo: URL?
    let league: String
    let date: String
    let status: String?
    let homeGoals: Int?
    let awayGoals: Int?
    let predictedLabel: String?
    let homeWinPct: Double?
    let drawPct: Double?
    let awayWinPct: Double?
    let isLive: Bool?
    let predictionVersion: Int?
    let predictionUpdatedAt: String?
    let predictionTrigger: String?
    let homeDelta: Double?
    let drawDelta: Double?
    let awayDelta: Double?

    var id: Int { fixtureId }

    var isFinished: Bool { ["FINISHED", "FT", "AET", "PEN"].contains(status?.uppercased() ?? "") }

    var scoreText: String? {
        guard let homeGoals, let awayGoals else { return nil }
        return "\(homeGoals) – \(awayGoals)"
    }

    var statusText: String {
        if isLive == true { return "LIVE" }
        if isFinished { return "FULL TIME" }
        switch status?.uppercased() {
        case "SCHEDULED", "NS", nil: return "UPCOMING"
        case "PST", "POSTPONED": return "POSTPONED"
        case "CANC", "CANCELLED": return "CANCELLED"
        default: return status?.uppercased() ?? "MATCH"
        }
    }

    enum CodingKeys: String, CodingKey {
        case fixtureId = "fixture_id"
        case homeTeam = "home_team"
        case awayTeam = "away_team"
        case homeTeamLogo = "home_team_logo"
        case awayTeamLogo = "away_team_logo"
        case league, date, status
        case homeGoals = "home_goals"
        case awayGoals = "away_goals"
        case predictedLabel = "predicted_label"
        case homeWinPct = "home_win_pct"
        case drawPct = "draw_pct"
        case awayWinPct = "away_win_pct"
        case isLive = "is_live"
        case predictionVersion = "prediction_version"
        case predictionUpdatedAt = "prediction_updated_at"
        case predictionTrigger = "prediction_trigger"
        case homeDelta = "home_delta"
        case drawDelta = "draw_delta"
        case awayDelta = "away_delta"
    }
}

/// Matches GET /live-matches-with-predictions
struct LiveMatch: Codable, Identifiable {
    let fixtureId: Int
    let homeTeam: String
    let awayTeam: String
    let homeTeamLogo: URL?
    let awayTeamLogo: URL?
    let league: String
    let score: String
    let elapsed: Int?
    let status: String
    let predictedLabel: String?
    let homeWinPct: Double?
    let drawPct: Double?
    let awayWinPct: Double?

    var id: Int { fixtureId }

    enum CodingKeys: String, CodingKey {
        case fixtureId = "fixture_id"
        case homeTeam = "home_team"
        case awayTeam = "away_team"
        case homeTeamLogo = "home_team_logo"
        case awayTeamLogo = "away_team_logo"
        case league, score, elapsed, status
        case predictedLabel = "predicted_label"
        case homeWinPct = "home_win_pct"
        case drawPct = "draw_pct"
        case awayWinPct = "away_win_pct"
    }
}

/// Matches GET /events/<fixture_id>
struct MatchEvent: Codable, Identifiable {
    let minute: Int?
    let team: String?
    let player: String?
    let assist: String?
    let type: String
    let detail: String

    var id: String { "\(minute ?? -1)-\(player ?? "")-\(type)-\(detail)" }
}

/// Matches GET /standings/<league_code>
struct StandingRow: Codable, Identifiable {
    let position: Int
    let team: String
    let teamLogo: URL?
    let playedGames: Int
    let won: Int
    let draw: Int
    let lost: Int
    let points: Int
    let goalDifference: Int

    var id: String { team }

    enum CodingKeys: String, CodingKey {
        case position, team, playedGames, won, draw, lost, points, goalDifference
        case teamLogo = "team_logo"
    }
}

/// Matches GET /prediction/<fixture_id>
struct MatchPredictionDetail: Codable {
    let winner: String?
    let comment: String?
    let advice: String?
    let homePct: String?
    let drawPct: String?
    let awayPct: String?
    let lastFiveHome: LastFive?
    let lastFiveAway: LastFive?

    enum CodingKeys: String, CodingKey {
        case winner, comment, advice
        case homePct = "home_pct"
        case drawPct = "draw_pct"
        case awayPct = "away_pct"
        case lastFiveHome = "last_5_home"
        case lastFiveAway = "last_5_away"
    }

    /// api-sports.io returns these as strings like "45%" — parsed for the bar widths.
    static func parsePercent(_ raw: String?) -> Double {
        guard let raw else { return 0 }
        let digits = raw.filter { $0.isNumber || $0 == "." }
        return Double(digits) ?? 0
    }
}

struct LastFive: Codable {
    let form: String?
}

/// The 6 leagues the backend's models are trained on (fixture.py's league_ids).
enum League: String, CaseIterable, Identifiable {
    case bundesliga = "D1"
    case premierLeague = "E0"
    case laLiga = "SP1"
    case serieA = "I1"
    case ligue1 = "F1"
    case superLig = "T1"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .bundesliga: return "Bundesliga"
        case .premierLeague: return "Premier League"
        case .laLiga: return "La Liga"
        case .serieA: return "Serie A"
        case .ligue1: return "Ligue 1"
        case .superLig: return "Süper Lig"
        }
    }
}
