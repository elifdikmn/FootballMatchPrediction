import SwiftUI

struct LiveView: View {
    @State private var matches: [LiveMatch] = []
    @State private var isLoading = false
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            ZStack {
                Theme.bg.ignoresSafeArea()
                content
            }
            .navigationTitle("Live")
            .toolbarBackground(Theme.card, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .task { await load() }
            .refreshable { await load() }
        }
    }

    @ViewBuilder
    private var content: some View {
        if isLoading && matches.isEmpty {
            ProgressView().tint(Theme.ink)
        } else if let errorMessage, matches.isEmpty {
            ErrorStateView(message: errorMessage) { Task { await load() } }
        } else if matches.isEmpty {
            EmptyStateView(text: "No matches live right now.")
        } else {
            ScrollView {
                LazyVStack(spacing: 14) {
                    ForEach(matches) { match in
                        NavigationLink {
                            MatchDetailView(
                                fixtureId: match.fixtureId,
                                homeTeam: match.homeTeam,
                                awayTeam: match.awayTeam,
                                league: match.league,
                                scoreText: match.score
                            )
                        } label: {
                            PredictionCard(
                                leagueLabel: League(rawValue: match.league)?.displayName ?? match.league,
                                trailingLabel: match.score,
                                homeTeam: match.homeTeam,
                                awayTeam: match.awayTeam,
                                homePct: match.homeWinPct,
                                drawPct: match.drawPct,
                                awayPct: match.awayWinPct,
                                trailingBadge: AnyView(LiveMinuteBadge(elapsed: match.elapsed))
                            )
                        }
                        .buttonStyle(.plain)
                    }
                }
                .padding(16)
            }
        }
    }

    private func load() async {
        isLoading = true
        errorMessage = nil
        do {
            matches = try await APIClient.shared.liveMatches()
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }
}

struct LiveMinuteBadge: View {
    let elapsed: Int?

    var body: some View {
        HStack(spacing: 6) {
            Circle()
                .fill(Theme.warm)
                .frame(width: 6, height: 6)
            Text(elapsed != nil ? "\(elapsed!)'" : "LIVE")
                .font(.system(size: 12, weight: .bold))
                .foregroundStyle(Theme.warm)
        }
        .padding(.vertical, 4)
        .padding(.leading, 8)
        .padding(.trailing, 10)
        .background(Capsule().fill(Theme.warmSoft))
    }
}
