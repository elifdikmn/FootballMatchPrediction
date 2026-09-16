import SwiftUI

struct MatchDetailView: View {
    let fixtureId: Int
    let homeTeam: String
    let awayTeam: String
    let league: String
    let scoreText: String?
    var statusText: String = "MATCH"

    private enum Tab { case events, standings }

    @State private var tab: Tab = .events
    @State private var events: [MatchEvent] = []
    @State private var standings: [StandingRow] = []
    @State private var isLoadingEvents = false
    @State private var isLoadingStandings = false
    @State private var eventsError: String?
    @State private var standingsError: String?

    var body: some View {
        ZStack {
            Theme.bg.ignoresSafeArea()
            ScrollView {
                VStack(spacing: 20) {
                    header
                    tabBar
                    switch tab {
                    case .events: eventsList
                    case .standings: standingsTable
                    }
                }.padding(.bottom, 24)
            }
        }
        .navigationTitle("Match Detail")
        .navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(Theme.card, for: .navigationBar)
        .toolbarColorScheme(.dark, for: .navigationBar)
        .task { await loadEvents() }
        .onChange(of: tab) { newValue in
            if newValue == .standings && standings.isEmpty { Task { await loadStandings() } }
        }
    }

    private var header: some View {
        VStack(spacing: 16) {
            LeagueBadge(name: league, size: 32)
            Text(League(rawValue: league)?.displayName ?? league)
                .font(.system(size: 11, weight: .semibold))
                .tracking(1)
                .foregroundStyle(Theme.inkMuted)

            Text(statusText).font(.caption.weight(.bold)).foregroundStyle(statusText == "FULL TIME" ? Theme.success : Theme.warm)

            HStack(spacing: 12) {
                teamColumn(homeTeam, role: "Home")
                if let scoreText {
                    Text(scoreText)
                        .font(.system(.largeTitle, design: .rounded).weight(.heavy))
                        .monospacedDigit().foregroundStyle(Theme.success)
                } else {
                    Text(statusText == "FULL TIME" ? "Score unavailable" : "vs")
                        .italic()
                        .font(.system(size: 15, design: .serif))
                        .foregroundStyle(Theme.inkFaint)
                }
                teamColumn(awayTeam, role: "Away")
            }

            NavigationLink {
                CheckOutWhyView(
                    fixtureId: fixtureId,
                    homeTeam: homeTeam,
                    awayTeam: awayTeam,
                    scoreText: scoreText,
                    league: league,
                    statusText: statusText
                )
            } label: {
                Text("Show Prediction")
                    .font(.subheadline.weight(.medium))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 22).padding(.vertical, 10)
                    .background(RoundedRectangle(cornerRadius: 10).fill(Theme.warm))
                    .frame(minHeight: 44)
            }
        }
        .padding(18)
        .background(Theme.card)
        .clipShape(RoundedRectangle(cornerRadius: 26))
        .overlay(RoundedRectangle(cornerRadius: 26).stroke(Theme.line, lineWidth: 1))
        .padding(.horizontal, 16)
        .padding(.top, 16)
    }

    private func teamColumn(_ name: String, role: String) -> some View {
        VStack(spacing: 9) {
            Text(role).font(.subheadline).foregroundStyle(Theme.inkMuted)
            CrestBadge(teamName: name, size: 56, league: league)
            Text(name)
                .font(.body.weight(.medium))
                .foregroundStyle(Theme.ink)
                .multilineTextAlignment(.center)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity)
    }

    private var tabBar: some View {
        HStack(spacing: 4) {
            tabButton("Events", .events)
            tabButton("Standings", .standings)
        }
        .padding(4)
        .background(Color(hex: "202024"), in: RoundedRectangle(cornerRadius: 13))
        .padding(.horizontal, 16)
    }

    private func tabButton(_ title: String, _ value: Tab) -> some View {
        Button { tab = value } label: {
            Text(title).font(.headline).foregroundStyle(Theme.ink)
                .frame(maxWidth: .infinity).padding(.vertical, 12)
                .background(tab == value ? Color(hex: "55555E") : .clear,
                            in: RoundedRectangle(cornerRadius: 10))
        }.buttonStyle(.plain)
        .accessibilityAddTraits(tab == value ? .isSelected : [])
    }

    // MARK: - Events

    @ViewBuilder
    private var eventsList: some View {
        if isLoadingEvents {
            ProgressView().tint(Theme.ink).padding(.top, 40)
        } else if let eventsError {
            ErrorStateView(message: eventsError) { Task { await loadEvents() } }.frame(height: 200)
        } else if events.isEmpty {
            EmptyStateView(text: "No events yet.").frame(height: 200)
        } else {
            let firstHalf = events.filter { ($0.minute ?? 0) <= 45 }
            let secondHalf = events.filter { ($0.minute ?? 0) > 45 }
            VStack(alignment: .leading, spacing: 4) {
                if !firstHalf.isEmpty {
                    sectionHeader("First Half")
                    ForEach(firstHalf) { eventRow($0) }
                }
                if !secondHalf.isEmpty {
                    sectionHeader("Second Half")
                    ForEach(secondHalf) { eventRow($0) }
                }
            }
            .padding(.horizontal, 22)
            .padding(.bottom, 24)
        }
    }

    private func sectionHeader(_ text: String) -> some View {
        Text(text.uppercased())
            .font(.title3.weight(.bold))
            .tracking(1)
            .foregroundStyle(Theme.ink)
            .padding(.top, 18)
            .padding(.bottom, 6)
    }

    private func isHomeEvent(_ event: MatchEvent) -> Bool {
        guard let team = event.team?.lowercased(), !team.isEmpty else { return true }
        let home = homeTeam.lowercased()
        let away = awayTeam.lowercased()
        if team.contains(home) || home.contains(team) { return true }
        if team.contains(away) || away.contains(team) { return false }
        return true
    }

    private func eventRow(_ event: MatchEvent) -> some View {
        let home = isHomeEvent(event)
        let minuteText = "\(event.minute ?? 0)'"
        let icon: AnyView = {
            switch event.type.lowercased() {
            case "card":
                let color = event.detail.lowercased().contains("red") ? Theme.warm : Theme.cool
                return AnyView(RoundedRectangle(cornerRadius: 3).fill(color).frame(width: 16, height: 21))
            case "subst", "substitution":
                return AnyView(Image(systemName: "arrow.left.arrow.right").font(.title3).foregroundStyle(Theme.draw))
            default:
                return AnyView(Image(systemName: event.type.lowercased() == "goal" ? "soccerball" : "info.circle").font(.title3).foregroundStyle(Theme.success))
            }
        }()

        let text = VStack(alignment: home ? .leading : .trailing, spacing: 1) {
            Text(event.player ?? event.detail)
                .font(.body.weight(.semibold))
                .foregroundStyle(Theme.ink)
            Text(subtitle(for: event))
                .font(.subheadline)
                .foregroundStyle(Theme.inkFaint)
        }

        return HStack(spacing: 10) {
            if home {
                Text(minuteText).font(.subheadline.weight(.bold)).foregroundStyle(Theme.inkMuted).frame(minWidth: 26, alignment: .leading)
                icon
                text
                Spacer(minLength: 0)
            } else {
                Spacer(minLength: 0)
                text
                icon
                Text(minuteText).font(.subheadline.weight(.bold)).foregroundStyle(Theme.inkMuted).frame(minWidth: 26, alignment: .trailing)
            }
        }
        .padding(.vertical, 14)
        .overlay(Rectangle().fill(Theme.line).frame(height: 1), alignment: .bottom)
    }

    private func subtitle(for event: MatchEvent) -> String {
        if let assist = event.assist, !assist.isEmpty {
            return "Assist: \(assist)"
        }
        return event.detail
    }

    private func loadEvents() async {
        isLoadingEvents = true
        eventsError = nil
        do {
            events = try await APIClient.shared.matchEvents(fixtureId: fixtureId)
        } catch {
            eventsError = error.localizedDescription
        }
        isLoadingEvents = false
    }

    // MARK: - Standings

    @ViewBuilder
    private var standingsTable: some View {
        if isLoadingStandings {
            ProgressView().tint(Theme.ink).padding(.top, 40)
        } else if let standingsError {
            ErrorStateView(message: standingsError) { Task { await loadStandings() } }.frame(height: 200)
        } else if standings.isEmpty {
            EmptyStateView(text: "No standings available.").frame(height: 200)
        } else {
            VStack(spacing: 4) {
                standingsHeaderRow
                ForEach(standings) { row in standingsRow(row) }
            }
            .padding(8)
            .background(Color(hex: "13223E"), in: RoundedRectangle(cornerRadius: 18))
            .padding(.horizontal, 12)
        }
    }

    private var standingsHeaderRow: some View {
        HStack(spacing: 2) {
            Text("#").frame(width: 18, alignment: .leading)
            Text("Club").frame(maxWidth: .infinity, alignment: .leading)
            Text("P").frame(width: 22, alignment: .center)
            Text("W").frame(width: 22, alignment: .center)
            Text("D").frame(width: 22, alignment: .center)
            Text("L").frame(width: 22, alignment: .center)
            Text("GD").frame(width: 28, alignment: .center)
            Text("Pts").frame(width: 26, alignment: .trailing)
        }
        .font(.system(size: 12, weight: .bold))
        .foregroundStyle(Theme.ink)
        .padding(.bottom, 10)
        .overlay(Rectangle().fill(Theme.line).frame(height: 1), alignment: .bottom)
    }

    private func standingsRow(_ row: StandingRow) -> some View {
        let isHome = row.team.lowercased() == homeTeam.lowercased()
        let isAway = row.team.lowercased() == awayTeam.lowercased()
        let highlight: Color? = isHome ? Theme.warm.opacity(0.16) : (isAway ? Theme.cool.opacity(0.14) : nil)

        return HStack(spacing: 2) {
            Text("\(row.position)").frame(width: 18, alignment: .leading).fontWeight(.bold)
            HStack(spacing: 4) {
                SmallCrest(teamName: row.team, size: 18, league: league)
                Text(row.team).fixedSize(horizontal: false, vertical: true)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .fontWeight(.semibold)
            Text("\(row.playedGames)").frame(width: 22, alignment: .center).foregroundStyle(Theme.inkMuted)
            Text("\(row.won)").frame(width: 22, alignment: .center).foregroundStyle(Theme.inkMuted)
            Text("\(row.draw)").frame(width: 22, alignment: .center).foregroundStyle(Theme.inkMuted)
            Text("\(row.lost)").frame(width: 22, alignment: .center).foregroundStyle(Theme.inkMuted)
            Text(row.goalDifference > 0 ? "+\(row.goalDifference)" : "\(row.goalDifference)")
                .frame(width: 28, alignment: .center).foregroundStyle(Theme.inkMuted)
            Text("\(row.points)").frame(width: 26, alignment: .trailing).fontWeight(.bold)
        }
        .font(.system(size: 13))
        .monospacedDigit()
        .foregroundStyle(Theme.ink)
        .padding(.vertical, 12)
        .accessibilityElement(children: .combine)
        .background(highlight.map { RoundedRectangle(cornerRadius: 10).fill($0) })
    }

    private func loadStandings() async {
        isLoadingStandings = true
        standingsError = nil
        do {
            standings = try await APIClient.shared.standings(leagueCode: league)
        } catch {
            standingsError = error.localizedDescription
        }
        isLoadingStandings = false
    }
}
