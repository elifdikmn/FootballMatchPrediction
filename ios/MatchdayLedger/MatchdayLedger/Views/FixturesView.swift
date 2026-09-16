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

    private var weekDays: [Date] {
        let start = Calendar.current.dateInterval(of: .weekOfYear, for: selectedDay)?.start ?? selectedDay
        return (0..<7).compactMap { Calendar.current.date(byAdding: .day, value: $0, to: start) }
    }

    private var dateStrip: some View {
        VStack(spacing: 16) {
            HStack(alignment: .center) {
                Button { withAnimation { showingCalendar.toggle() } } label: {
                    HStack(spacing: 8) {
                        Image(systemName: "calendar").font(.subheadline)
                        Text(selectedDay, format: .dateTime.month(.wide).year())
                            .font(.headline)
                        Image(systemName: showingCalendar ? "chevron.up" : "chevron.down").font(.caption2)
                    }.foregroundStyle(.white).frame(minHeight: 44)
                }.accessibilityLabel("Choose match date")
                Spacer(minLength: 8)
            }
            HStack(spacing: 2) {
                dayArrow(-7, icon: "chevron.left", label: "Previous week")
                ForEach(weekDays, id: \.self) { day in
                    let selected = Calendar.current.isDate(day, inSameDayAs: selectedDay)
                    Button { selectedDay = day } label: {
                        VStack(spacing: 8) {
                            Text(day, format: .dateTime.weekday(.narrow))
                                .font(.caption2.weight(.medium))
                            Text(day, format: .dateTime.day())
                                .font(.body.weight(.bold)).monospacedDigit()
                            Circle().fill(availableDates.contains(Self.dateKey(day)) ? (selected ? Color.black : Color.white) : .clear)
                                .frame(width: 4, height: 4)
                        }
                        .frame(maxWidth: .infinity).padding(.vertical, 10)
                        .foregroundStyle(selected ? .black : Theme.inkMuted)
                        .background(selected ? Color.white : .clear, in: RoundedRectangle(cornerRadius: 12))
                    }
                    .accessibilityLabel(day.formatted(date: .complete, time: .omitted))
                    .accessibilityAddTraits(selected ? .isSelected : [])
                }
                dayArrow(7, icon: "chevron.right", label: "Next week")
            }
            if showingCalendar {
                DatePicker("Match date", selection: $selectedDay, displayedComponents: .date)
                    .datePickerStyle(.graphical).tint(.white)
            }
        }
        .padding(14)
        .background(Color(hex: "11151C"), in: RoundedRectangle(cornerRadius: 18))
        .padding(.horizontal, 16).padding(.top, 8)
    }

    private func dayArrow(_ offset: Int, icon: String, label: String) -> some View {
        Button {
            if let date = Calendar.current.date(byAdding: .day, value: offset, to: selectedDay) {
                selectedDay = date
            }
        } label: {
            Image(systemName: icon).font(.system(size: 15, weight: .bold))
                .frame(width: 30, height: 44)
                .contentShape(Rectangle())
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
                    .foregroundStyle(.white)
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
        let values = scoreText.split(whereSeparator: { !$0.isNumber }).map(String.init)
        return values.count == 2 ? values : []
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
                    HStack(spacing: 6) {
                        Text("Match details").font(.caption.weight(.semibold))
                        Image(systemName: "chevron.right").font(.caption2.weight(.bold))
                    }
                    .foregroundStyle(Theme.ink)
                    .padding(.leading, 12).frame(minHeight: 44)
                    .contentShape(Rectangle())
                }
            }
            HStack(alignment: .top, spacing: 10) {
                teamColumn(homeTeam, role: "Home")
                VStack(spacing: 6) {
                    if scores.count == 2 {
                        HStack(spacing: 5) {
                            Text(scores[0])
                            Text("–")
                            Text(scores[1])
                        }
                        .font(.system(.title2, design: .rounded).weight(.bold))
                        .monospacedDigit()
                        .foregroundStyle(.white)
                    } else {
                        Text(scoreText ?? (statusText == "FULL TIME" ? "—" : "VS"))
                            .font(.system(.title2, design: .rounded).weight(.bold))
                            .foregroundStyle(scoreText == nil ? Theme.inkMuted : Theme.ink)
                            .multilineTextAlignment(.center)
                    }
                    if scoreText == nil, statusText == "FULL TIME" {
                        Text("Score unavailable").font(.caption2).foregroundStyle(Theme.inkMuted)
                    }
                }.frame(maxWidth: 88).padding(.top, 17)
                teamColumn(awayTeam, role: "Away")
            }
            .padding(.vertical, 4)
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
                    Image(systemName: "arrow.up.right").foregroundStyle(Theme.inkMuted)
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

    private func teamColumn(_ name: String, role: String) -> some View {
        VStack(spacing: 8) {
            CrestBadge(teamName: name, size: 48, league: leagueCode)
            Text(name).font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink)
                .multilineTextAlignment(.center).fixedSize(horizontal: false, vertical: true)
            Text(role.uppercased()).font(.caption2.weight(.bold))
                .tracking(1).foregroundStyle(Theme.inkMuted)
        }.frame(maxWidth: .infinity)
    }
}

struct OutcomeBar: View {
    let homePct: Double
    let drawPct: Double
    let awayPct: Double

    private var total: Double {
        max(max(0, homePct) + max(0, drawPct) + max(0, awayPct), 1)
    }

    var body: some View {
        VStack(spacing: 12) {
            GeometryReader { geometry in
                let usableWidth = max(0, geometry.size.width - 12)
                HStack(spacing: 6) {
                    segment(width: usableWidth * max(0, homePct) / total, color: Theme.warm)
                    segment(width: usableWidth * max(0, drawPct) / total, color: Theme.cool)
                    segment(width: usableWidth * max(0, awayPct) / total, color: Theme.success)
                }
            }
            .frame(height: 8)

            HStack(spacing: 8) {
                outcome("Home", homePct, Theme.warm, alignment: .leading)
                outcome("Draw", drawPct, Theme.cool, alignment: .center)
                outcome("Away", awayPct, Theme.success, alignment: .trailing)
            }
        }
    }

    private func segment(width: CGFloat, color: Color) -> some View {
        Capsule().fill(color).frame(width: max(0, width))
    }

    private func outcome(
        _ label: String,
        _ pct: Double,
        _ color: Color,
        alignment: HorizontalAlignment
    ) -> some View {
        let strongest = pct > 0 && pct == max(homePct, max(drawPct, awayPct))
        return VStack(alignment: alignment, spacing: 3) {
            Text(pct / 100, format: .percent.precision(.fractionLength(1)))
                .font(.system(size: strongest ? 17 : 15, weight: .bold, design: .rounded))
                .monospacedDigit()
                .lineLimit(1)
                .minimumScaleFactor(0.75)
                .foregroundStyle(.white)
            Text(label.uppercased())
                .font(.caption2.weight(.bold))
                .tracking(0.7)
                .foregroundStyle(Theme.inkMuted)
        }
        .frame(maxWidth: .infinity, alignment: Alignment(horizontal: alignment, vertical: .center))
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
