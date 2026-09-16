import SwiftUI

struct FixturesView: View {
    @State private var fixtures: [ScheduledPrediction] = []
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var selectedLeagues: Set<League> = []
    @State private var showingFilter = false

    private var visibleFixtures: [ScheduledPrediction] {
        guard !selectedLeagues.isEmpty else { return fixtures }
        return fixtures.filter { fx in selectedLeagues.contains { $0.rawValue == fx.league } }
    }

    var body: some View {
        NavigationStack {
            ZStack {
                Theme.bg.ignoresSafeArea()
                content
            }
            .navigationTitle("Fixtures")
            .toolbarBackground(Theme.card, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        showingFilter = true
                    } label: {
                        Image(systemName: "line.3.horizontal.decrease.circle")
                    }
                }
            }
            .sheet(isPresented: $showingFilter) {
                LeagueFilterView(selected: selectedLeagues) { newSelection in
                    selectedLeagues = newSelection
                }
            }
            .task { await load() }
            .refreshable { await load() }
        }
    }

    @ViewBuilder
    private var content: some View {
        if isLoading && fixtures.isEmpty {
            ProgressView().tint(Theme.ink)
        } else if let errorMessage, fixtures.isEmpty {
            ErrorStateView(message: errorMessage) { Task { await load() } }
        } else if visibleFixtures.isEmpty {
            EmptyStateView(text: "No scheduled fixtures.")
        } else {
            ScrollView {
                LazyVStack(spacing: 14) {
                    ForEach(visibleFixtures) { fx in
                        NavigationLink {
                            MatchDetailView(
                                fixtureId: fx.fixtureId,
                                homeTeam: fx.homeTeam,
                                awayTeam: fx.awayTeam,
                                league: fx.league,
                                scoreText: nil
                            )
                        } label: {
                            PredictionCard(
                                leagueLabel: League(rawValue: fx.league)?.displayName ?? fx.league,
                                trailingLabel: fx.date,
                                homeTeam: fx.homeTeam,
                                awayTeam: fx.awayTeam,
                                homePct: fx.homeWinPct,
                                drawPct: fx.drawPct,
                                awayPct: fx.awayWinPct
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
            fixtures = try await APIClient.shared.scheduledPredictions()
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }
}

/// Shared match card used by the Fixtures and Live tabs.
struct PredictionCard: View {
    let leagueLabel: String
    let trailingLabel: String
    let homeTeam: String
    let awayTeam: String
    let homePct: Double?
    let drawPct: Double?
    let awayPct: Double?
    var trailingBadge: AnyView? = nil

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Text(leagueLabel.uppercased())
                    .font(.system(size: 10.5, weight: .semibold))
                    .tracking(1)
                    .foregroundStyle(Theme.inkMuted)
                Spacer()
                if let trailingBadge {
                    trailingBadge
                } else {
                    Text(trailingLabel)
                        .font(.system(size: 12))
                        .foregroundStyle(Theme.inkFaint)
                }
            }

            HStack(alignment: .top, spacing: 12) {
                teamColumn(homeTeam)
                Text("vs")
                    .italic()
                    .font(.system(size: 13, design: .serif))
                    .foregroundStyle(Theme.inkFaint)
                    .padding(.top, 16)
                teamColumn(awayTeam)
            }

            if homePct != nil || drawPct != nil || awayPct != nil {
                Divider().background(Theme.line)
                OutcomeBar(homePct: homePct ?? 0, drawPct: drawPct ?? 0, awayPct: awayPct ?? 0)
            }
        }
        .padding(18)
        .background(Theme.card)
        .clipShape(RoundedRectangle(cornerRadius: 18))
        .overlay(RoundedRectangle(cornerRadius: 18).stroke(Theme.line, lineWidth: 1))
    }

    private func teamColumn(_ name: String) -> some View {
        VStack(spacing: 8) {
            CrestBadge(teamName: name, size: 50)
            Text(name)
                .font(.system(size: 12.5, weight: .semibold))
                .foregroundStyle(Theme.ink)
                .multilineTextAlignment(.center)
                .lineLimit(2)
        }
        .frame(maxWidth: .infinity)
    }
}

struct OutcomeBar: View {
    let homePct: Double
    let drawPct: Double
    let awayPct: Double

    var body: some View {
        HStack(alignment: .top, spacing: 4) {
            outcome("Home", homePct, .leading, Theme.warm)
            outcome("Draw", drawPct, .center, Theme.draw)
            outcome("Away", awayPct, .trailing, Theme.cool)
        }
    }

    private func outcome(_ label: String, _ pct: Double, _ alignment: HorizontalAlignment, _ color: Color) -> some View {
        let isWinner = pct >= max(homePct, max(drawPct, awayPct))
        return VStack(alignment: alignment, spacing: 7) {
            RoundedRectangle(cornerRadius: 5)
                .fill(color)
                .frame(height: 7)
            VStack(alignment: alignment, spacing: 1) {
                Text("\(Int(pct.rounded()))%")
                    .font(.system(size: isWinner ? 16 : 13, weight: isWinner ? .bold : .semibold))
                    .foregroundStyle(isWinner ? Theme.ink : Theme.inkMuted)
                Text(label.uppercased())
                    .font(.system(size: 9.5, weight: .semibold))
                    .tracking(0.5)
                    .foregroundStyle(Theme.inkFaint)
            }
        }
        .frame(maxWidth: .infinity, alignment: Alignment(horizontal: alignment, vertical: .center))
    }
}

struct EmptyStateView: View {
    let text: String
    var body: some View {
        VStack(spacing: 8) {
            Image(systemName: "sportscourt")
                .font(.system(size: 28))
                .foregroundStyle(Theme.inkFaint)
            Text(text)
                .font(.system(size: 14))
                .foregroundStyle(Theme.inkFaint)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct ErrorStateView: View {
    let message: String
    let retry: () -> Void
    var body: some View {
        VStack(spacing: 12) {
            Text(message)
                .font(.system(size: 13))
                .foregroundStyle(Theme.inkFaint)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 32)
            Button("Retry", action: retry)
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(Theme.warm)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
