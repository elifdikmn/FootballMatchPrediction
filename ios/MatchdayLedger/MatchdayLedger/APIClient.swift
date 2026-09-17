import Foundation

enum APIConfig {
    /// Simulator can reach the Flask dev server at localhost. A physical device
    /// cannot resolve "localhost" to your Mac — replace this with your Mac's LAN
    /// IP (e.g. "http://192.168.1.23:5001") when running on a real iPhone.
    /// Port 5001 because 5000 is taken by macOS's AirPlay Receiver — run the
    /// backend with `PORT=5001 python app.py` to match.
    nonisolated(unsafe) static var baseURL = URL(string: "http://localhost:5001")!
}

enum APIError: Error, LocalizedError {
    case invalidResponse
    case http(Int)

    var errorDescription: String? {
        switch self {
        case .invalidResponse: return "The server sent an unexpected response."
        case .http(let code): return "Server returned status \(code)."
        }
    }
}

final class APIClient: @unchecked Sendable {
    static let shared = APIClient()

    private let decoder = JSONDecoder()
    private let session: URLSession

    private init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 20
        session = URLSession(configuration: config)
    }

    private func get<T: Decodable>(_ path: String, query: [URLQueryItem] = []) async throws -> T {
        var components = URLComponents(
            url: APIConfig.baseURL.appendingPathComponent(path),
            resolvingAgainstBaseURL: false
        )!
        if !query.isEmpty { components.queryItems = query }

        let (data, response) = try await session.data(from: components.url!)
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200..<300).contains(http.statusCode) else { throw APIError.http(http.statusCode) }
        return try decoder.decode(T.self, from: data)
    }

    func scheduledPredictions(date: String) async throws -> [ScheduledPrediction] {
        try await get("/scheduled-predictions", query: [URLQueryItem(name: "date", value: date)])
    }

    func predictionDates() async throws -> [String: [String]] {
        try await get("/prediction-dates")
    }

    func branding() async throws -> [LeagueBranding] {
        try await get("/branding")
    }

    func liveMatches() async throws -> [LiveMatch] {
        try await get("/live-matches-with-predictions")
    }

    func matchEvents(fixtureId: Int) async throws -> [MatchEvent] {
        try await get("/events/\(fixtureId)")
    }

    func standings(leagueCode: String) async throws -> [StandingRow] {
        try await get("/standings/\(leagueCode)")
    }

    func predictionDetail(fixtureId: Int, live: Bool = false) async throws -> MatchPredictionDetail {
        try await get("/prediction/\(fixtureId)", query: live ? [URLQueryItem(name: "type", value: "live")] : [])
    }
}
