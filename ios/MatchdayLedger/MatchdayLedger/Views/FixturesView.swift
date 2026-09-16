import SwiftUI

struct FixturesView: View {
    @State private var fixtures: [ScheduledPrediction] = []
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var selectedLeagues: Set<League> = []
    @State private var selectedDay = Date()
    @State private var showingCalendar = false
    @State private var savedDates: [String: [String]] = [:]

    private var availableDates: [String] {
        Array(Set(savedDates.filter { code, _ in
            selectedLeagues.isEmpty || selectedLeagues.contains { $0.rawValue == code }
        }.values.flatMap { $0 })).sorted()
    }

    private var suggestedDate: String? {
        availableDates.first { $0 >= selectedDate } ?? availableDates.last
    }

    private func selectSavedDate(_ key: String) {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd"
        if let date = formatter.date(from: key) { selectedDay = date }
    }

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
                ScrollView {
                    LazyVStack(spacing: 20) {
                        dateStrip
                        content
                    }.padding(.bottom, 24)
                }
            }
            .navigationTitle("Matchday")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarBackground(Theme.card, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        showingFilter.toggle()
                    } label: {
                        Image(systemName: "line.3.horizontal.decrease.circle")
                            .foregroundStyle(.white)
                    }
                    .accessibilityLabel("Filter leagues")
                    .tint(.white)
                    .sheet(isPresented: $showingFilter) {
                        LeagueFilterView(selected: selectedLeagues) { selectedLeagues = $0 }
                    }
                }
            }
            .task(id: selectedDate) { await load() }
            .task { await loadDates() }
            .refreshable {
                await loadDates()
                await load()
            }
        }
    }

    private var dateStrip: some View {
        VStack(spacing: 14) {
            HStack {
                Text("MATCHDAY").font(.headline.weight(.bold)).tracking(2).foregroundStyle(Color.white)
                Spacer()
                Button("Today") { selectedDay = Date() }
                    .font(.subheadline.weight(.semibold)).tint(Color.white)
            }
            HStack(spacing: 12) {
                dayArrow(-1, icon: "chevron.left", label: "Previous day")
                Button { showingCalendar.toggle() } label: {
                    VStack(spacing: 4) {
                        Text(selectedDay, format: .dateTime.weekday(.wide))
                            .font(.caption).foregroundStyle(.white)
                        HStack(spacing: 8) {
                            Text(selectedDay, format: .dateTime.day().month(.wide).year())
                            Image(systemName: "chevron.down").font(.caption)
                        }
                        .font(.headline).foregroundStyle(.white)
                    }.frame(maxWidth: .infinity).padding(.vertical, 10)
                        .background(Theme.card, in: RoundedRectangle(cornerRadius: 14))
                }
                .accessibilityLabel("Choose match date")
                dayArrow(1, icon: "chevron.right", label: "Next day")
            }
            HStack(spacing: 4) {
                ForEach(-3...3, id: \.self) { offset in
                    let day = Calendar.current.date(byAdding: .day, value: offset, to: selectedDay) ?? selectedDay
                    Button { selectedDay = day } label: {
                        VStack(spacing: 5) {
                            Text(day, format: .dateTime.day()).font(.title3.weight(.semibold))
                            Text(day, format: .dateTime.month(.abbreviated)).font(.caption).lineLimit(1).minimumScaleFactor(0.8)
                        }
                        .frame(maxWidth: .infinity).padding(.vertical, 10)
                        .foregroundStyle(offset == 0 ? Color.white : Theme.inkMuted)
                        .background(offset == 0 ? Color.white.opacity(0.14) : .clear, in: RoundedRectangle(cornerRadius: 12))
                    }.accessibilityLabel(day.formatted(date: .complete, time: .omitted))
                }
            }
            if showingCalendar {
                DatePicker("Match date", selection: $selectedDay, displayedComponents: .date)
                    .datePickerStyle(.graphical).tint(Color.white)
            }
        }
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
                .background(Theme.card, in: RoundedRectangle(cornerRadius: 14))
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
            VStack(spacing: 16) {
                Image(systemName: "calendar.badge.exclamationmark")
                    .font(.largeTitle).foregroundStyle(Theme.warm)
                Text("No predictions for this day")
                    .font(.headline).foregroundStyle(Theme.ink)
                Text("Choose a saved date to explore match predictions.")
                    .font(.subheadline).foregroundStyle(Theme.inkMuted)
                    .multilineTextAlignment(.center)
                if let date = suggestedDate {
                    Button { selectSavedDate(date) } label: {
                        Label("Show saved matches · \(date)", systemImage: "calendar")
                    }
                    .buttonStyle(.borderedProminent).tint(Theme.warm)
                    .foregroundStyle(Theme.bg)
                    if let first = availableDates.first, let last = availableDates.last {
                        Text("Saved dates: \(first) – \(last)")
                            .font(.caption).foregroundStyle(Theme.inkMuted)
                    }
                } else if !selectedLeagues.isEmpty {
                    Button("Show all leagues") { selectedLeagues = [] }
                        .tint(Theme.warm)
                }
            }
            .padding(24)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        } else {
            LazyVStack(spacing: 24) {
                ForEach(League.allCases.filter { league in visibleFixtures.contains { $0.league == league.rawValue } }) { league in
                    VStack(spacing: 14) {
                        LeagueSectionHeader(league: league.rawValue, matchCount: visibleFixtures.filter { $0.league == league.rawValue }.count)
                        ForEach(visibleFixtures.filter { $0.league == league.rawValue }) { fx in
                            PredictionCard(
                                leagueLabel: league.displayName, trailingLabel: fx.date,
                                homeTeam: fx.homeTeam, awayTeam: fx.awayTeam,
                                homePct: fx.homeWinPct, drawPct: fx.drawPct, awayPct: fx.awayWinPct,
                                scoreText: fx.scoreText, statusText: fx.statusText,
                                fixtureId: fx.fixtureId, leagueCode: fx.league
                            )
                        }
                    }
                }
            }.padding(.horizontal, 16)
        }
    }

    private func loadDates() async {
        do { savedDates = try await APIClient.shared.predictionDates() }
        catch { /* Date navigation remains available if metadata cannot be loaded. */ }
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

struct LeagueSectionHeader: View {
    let league: String
    var matchCount: Int? = nil
    var body: some View {
        HStack(spacing: 12) {
            LeagueBadge(name: league, size: 28)
            Text(League(rawValue: league)?.displayName ?? league)
                .font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink)
            Spacer(minLength: 0)
            if let matchCount {
                Text("\(matchCount) matches").font(.caption).foregroundStyle(Theme.inkMuted)
            }
        }.padding(.vertical, 4)
    }
}

/// Separate navigation controls keep the two destinations accessible.
struct PredictionCard: View {
    let leagueLabel: String
    let trailingLabel: String
    let homeTeam: String
    let awayTeam: String
    let homePct: Double?
    let drawPct: Double?
    let awayPct: Double?
    var trailingBadge: AnyView? = nil
    var scoreText: String? = nil
    var statusText: String? = nil
    let fixtureId: Int
    let leagueCode: String

    private var scores: [String] {
        guard let scoreText else { return [] }
        let parts = scoreText.split(whereSeparator: { !$0.isNumber }).map(String.init)
        return parts.count == 2 ? parts : []
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                if let trailingBadge { trailingBadge }
                else {
                    HStack(spacing: 6) {
                        Circle().fill(statusText == "FULL TIME" ? Theme.success : Theme.inkMuted)
                            .frame(width: 6, height: 6)
                        Text(statusText ?? trailingLabel).font(.caption.weight(.semibold)).foregroundStyle(Theme.inkMuted)
                    }
                }
                Spacer()
                NavigationLink {
                    MatchDetailView(fixtureId: fixtureId, homeTeam: homeTeam, awayTeam: awayTeam,
                                    league: leagueCode, scoreText: scoreText, statusText: statusText ?? "MATCH")
                } label: {
                    Text("Detail").font(.subheadline.weight(.bold)).foregroundStyle(.white)
                        .padding(.horizontal, 16).padding(.vertical, 11)
                        .background(Theme.warm, in: RoundedRectangle(cornerRadius: 12))
                }
            }
            VStack(spacing: 14) {
                teamRow(homeTeam, role: "Home", score: scores.first, color: Theme.warm)
                teamRow(awayTeam, role: "Away", score: scores.count == 2 ? scores[1] : nil, color: Theme.cool)
            }
            if scores.isEmpty, let scoreText {
                Text(scoreText).font(.headline).foregroundStyle(Theme.success)
            } else if scores.isEmpty, statusText == "FULL TIME" {
                Text("Score unavailable").font(.caption).foregroundStyle(Theme.inkMuted)
            }
            if homePct != nil || drawPct != nil || awayPct != nil {
                OutcomeBar(homePct: homePct ?? 0, drawPct: drawPct ?? 0, awayPct: awayPct ?? 0)
            }
            NavigationLink {
                CheckOutWhyView(fixtureId: fixtureId, homeTeam: homeTeam, awayTeam: awayTeam,
                                scoreText: scoreText, league: leagueCode, statusText: statusText ?? "MATCH")
            } label: {
                HStack {
                    Image(systemName: "chart.bar.xaxis").foregroundStyle(Theme.warm)
                    Text("Show Prediction").foregroundStyle(Theme.ink)
                    Spacer()
                    Image(systemName: "arrow.up.right").foregroundStyle(Theme.warm)
                }
                .font(.subheadline.weight(.medium))
                .frame(minHeight: 44)
                .padding(.top, 4)
                .overlay(alignment: .top) { Rectangle().fill(Theme.line).frame(height: 1) }
                .contentShape(Rectangle())
            }
        }
        .buttonStyle(.plain)
        .padding(16)
        .background(Color(hex: "171B24"), in: RoundedRectangle(cornerRadius: 16))
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(Theme.line.opacity(0.7), lineWidth: 1))
    }

    private func teamRow(_ name: String, role: String, score: String?, color: Color) -> some View {
        HStack(spacing: 12) {
            CrestBadge(teamName: name, size: 38, league: leagueCode)
            VStack(alignment: .leading, spacing: 3) {
                Text(name).font(.body.weight(.semibold)).foregroundStyle(Theme.ink)
                    .fixedSize(horizontal: false, vertical: true)
                Text(role.uppercased()).font(.caption2.weight(.bold)).tracking(1).foregroundStyle(color)
            }
            Spacer(minLength: 8)
            Text(score ?? "—")
                .font(.system(.title, design: .rounded).weight(.bold))
                .monospacedDigit().foregroundStyle(score == nil ? Theme.inkMuted : Theme.success)
                .frame(minWidth: 32, alignment: .trailing)
        }
    }
}

struct OutcomeBar: View {
    let homePct: Double
    let drawPct: Double
    let awayPct: Double

    var body: some View {
        HStack(spacing: 8) {
            outcome("Home", homePct, Theme.warm)
            outcome("Draw", drawPct, Theme.draw)
            outcome("Away", awayPct, Theme.cool)
        }
    }

    private func outcome(_ label: String, _ pct: Double, _ color: Color) -> some View {
        let strongest = pct > 0 && pct == max(homePct, max(drawPct, awayPct))
        return VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 4) {
                Text(label).font(.caption.weight(.semibold))
                Spacer(minLength: 0)
                if strongest { Image(systemName: "arrow.up.right").font(.caption2.weight(.bold)) }
            }
            Text(pct / 100, format: .percent.precision(.fractionLength(1)))
                .font(.headline).monospacedDigit().lineLimit(1).minimumScaleFactor(0.8)
        }
        .foregroundStyle(color)
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(color.opacity(strongest ? 0.19 : 0.07), in: RoundedRectangle(cornerRadius: 10))
        .overlay(RoundedRectangle(cornerRadius: 10).stroke(color.opacity(strongest ? 0.85 : 0.25), lineWidth: 1))
        .accessibilityElement(children: .combine)
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
