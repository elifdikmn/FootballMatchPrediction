import SwiftUI

struct LeagueBranding: Decodable {
    let code: String
    let logo: URL
    let teams: [TeamBranding]
}

struct TeamBranding: Decodable {
    let id: Int
    let names: [String]
    let logo: URL
}

@MainActor
final class BrandingStore: ObservableObject {
    static let shared = BrandingStore()
    @Published private var leagues: [LeagueBranding] = []

    private func normalized(_ name: String) -> String {
        name.folding(options: [.diacriticInsensitive, .caseInsensitive], locale: Locale(identifier: "en_US_POSIX"))
            .filter { $0.isLetter || $0.isNumber }
    }

    func teamURL(_ name: String, league: String?) -> URL? {
        let candidates = leagues.filter { league == nil || $0.code == league }
            .flatMap(\.teams).filter { team in team.names.contains { normalized($0) == normalized(name) } }
        // Never guess a crest when names identify different clubs.
        guard Set(candidates.map(\.id)).count == 1 else { return nil }
        return candidates.first?.logo
    }

    func load() async {
        do { leagues = try await APIClient.shared.branding() }
        catch { /* Preserve existing logos; neutral placeholders remain usable offline. */ }
    }
}

struct RemoteBadge: View {
    let url: URL?
    let label: String
    let size: CGFloat
    var body: some View {
        AsyncImage(url: url) { phase in
            if let image = phase.image {
                image.resizable().scaledToFit().padding(size * 0.1)
            } else {
                Image(systemName: "shield.lefthalf.filled")
                    .font(.system(size: size * 0.45, weight: .medium))
                    .foregroundStyle(Color.gray)
            }
        }
        .frame(width: size, height: size)
        .background(.white.opacity(0.95), in: RoundedRectangle(cornerRadius: size * 0.25))
        .accessibilityLabel(label)
    }
}

struct CrestBadge: View {
    let teamName: String
    var size: CGFloat = 44
    var league: String? = nil
    @ObservedObject private var branding = BrandingStore.shared

    var body: some View {
        RemoteBadge(url: branding.teamURL(teamName, league: league), label: teamName, size: size)
    }
}

struct SmallCrest: View {
    let teamName: String
    var size: CGFloat = 20
    var league: String? = nil
    var body: some View { CrestBadge(teamName: teamName, size: size, league: league) }
}

struct LeagueBadge: View {
    let name: String
    var size: CGFloat = 28
    private var league: League? {
        League.allCases.first { $0.rawValue == name || $0.displayName == name }
    }
    var body: some View {
        RemoteBadge(url: league.map { URL(string: "https://media.api-sports.io/football/leagues/\($0.apiID).png")! },
                    label: league?.displayName ?? name, size: size)
    }
}

extension League {
    var apiID: Int {
        switch self {
        case .bundesliga: return 78
        case .premierLeague: return 39
        case .laLiga: return 140
        case .serieA: return 135
        case .ligue1: return 61
        case .superLig: return 203
        }
    }
}
