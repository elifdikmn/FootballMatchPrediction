import SwiftUI

struct FixturesView: View {
    @State private var fixtures: [ScheduledPrediction] = []
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var selectedLeagues: Set<League> = []
    @State private var selectedDay = Date()
    @State private var showingCalendar = false

    private var selectedDate: String { Self.dateKey(selectedDay) }

    private static func dateKey(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.string(from: date)
    }
    @State private var showingFilter = false

    private var leagueFiltered: [ScheduledPrediction] {
        guard !selectedLeagues.isEmpty else { return fixtures }
        return fixtures.filter { fx in selectedLeagues.contains { $0.rawValue == fx.league } }
    }

    private var visibleFixtures: [ScheduledPrediction] { leagueFiltered }

    var body: some View {
        NavigationStack {
            ZStack {
                Theme.bg.ignoresSafeArea()
                VStack(spacing: 0) {
                    dateStrip
                    content
                }
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
            .task(id: selectedDate) { await load() }
            .refreshable { await load() }
        }
    }

    private var dateStrip: some View {
        VStack(spacing: 14) {
            HStack {
                Text("MATCHDAY").font(.caption.weight(.bold)).tracking(2).foregroundStyle(Theme.warm)
                Spacer()
                Button("Today") { selectedDay = Date() }
                    .font(.subheadline.weight(.semibold)).tint(Theme.warm)
            }
            HStack(spacing: 12) {
                dayArrow(-1, icon: "chevron.left", label: "Previous day")
                Button { showingCalendar.toggle() } label: {
                    VStack(spacing: 4) {
                        Text(selectedDay, format: .dateTime.weekday(.wide))
                            .font(.caption).foregroundStyle(Theme.inkMuted)
                        HStack(spacing: 8) {
                            Text(selectedDay, format: .dateTime.day().month(.wide).year())
                            Image(systemName: "chevron.down").font(.caption)
                        }
                        .font(.headline).foregroundStyle(Theme.ink)
                    }.frame(maxWidth: .infinity)
                }
                .accessibilityLabel("Choose match date")
                dayArrow(1, icon: "chevron.right", label: "Next day")
            }
            if showingCalendar {
                DatePicker("Match date", selection: $selectedDay, displayedComponents: .date)
                    .datePickerStyle(.graphical).tint(Theme.warm)
            }
        }
        .padding(20)
        .background(Theme.card)
        .clipShape(RoundedRectangle(cornerRadius: 22))
        .padding(.horizontal, 16).padding(.top, 8)
    }

    private func dayArrow(_ offset: Int, icon: String, label: String) -> some View {
        Button {
            if let date = Calendar.current.date(byAdding: .day, value: offset, to: selectedDay) {
                selectedDay = date
            }
        } label: {
            Image(systemName: icon).font(.system(size: 15, weight: .bold))
                .frame(width: 44, height: 44)
                .background(Theme.line, in: RoundedRectangle(cornerRadius: 14))
        }
        .tint(Theme.ink).accessibilityLabel(label)
    }

    @ViewBuilder
    private var content: some View {
        if isLoading && fixtures.isEmpty {
            ProgressView().tint(Theme.ink)
        } else if let errorMessage, fixtures.isEmpty {
            ErrorStateView(message: errorMessage) { Task { await load() } }
        } else if visibleFixtures.isEmpty {
            EmptyStateView(text: "No saved predictions for this date. Try another day.")
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
        fixtures = []
        errorMessage = nil
        do {
            let date = selectedDate
            let result = try await APIClient.shared.scheduledPredictions(date: date)
            try Task.checkCancellation()
            guard date == selectedDate else { return }
            fixtures = result
        } catch is CancellationError {
            return
        } catch {
            guard !Task.isCancelled else { return }
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
                LeagueBadge(name: leagueLabel)
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
        .padding(20)
        .background(Theme.card)
        .clipShape(RoundedRectangle(cornerRadius: 22))
        .overlay(RoundedRectangle(cornerRadius: 22).stroke(Theme.line, lineWidth: 1))
    }

    private func teamColumn(_ name: String) -> some View {
        VStack(spacing: 8) {
            CrestBadge(teamName: name, size: 56, league: League.allCases.first { $0.displayName == leagueLabel }?.rawValue)
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
        VStack(spacing: 12) {
            GeometryReader { geometry in
                let total = max(homePct + drawPct + awayPct, 1)
                HStack(spacing: 0) {
                    Theme.warm.frame(width: geometry.size.width * max(0, homePct) / total)
                    Theme.draw.frame(width: geometry.size.width * max(0, drawPct) / total)
                    Theme.cool.frame(width: geometry.size.width * max(0, awayPct) / total)
                }
            }
            .frame(height: 8).clipShape(Capsule())
            HStack(alignment: .top, spacing: 4) {
                outcome("Home", homePct, .leading, Theme.warm)
                outcome("Draw", drawPct, .center, Theme.draw)
                outcome("Away", awayPct, .trailing, Theme.cool)
            }
        }
    }

    private func outcome(_ label: String, _ pct: Double, _ alignment: HorizontalAlignment, _ color: Color) -> some View {
        let isWinner = pct >= max(homePct, max(drawPct, awayPct))
        return VStack(alignment: alignment, spacing: 7) {
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
