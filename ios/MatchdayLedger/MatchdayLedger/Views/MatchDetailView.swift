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
            VStack(spacing: 0) {
                header
                tabBar
                ScrollView {
                    switch tab {
                    case .events: eventsList
                    case .standings: standingsTable
                    }
                }
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
                teamColumn(homeTeam)
                if let scoreText {
                    Text(scoreText)
                        .font(.system(size: 30, weight: .bold))
                        .foregroundStyle(Theme.ink)
                } else {
                    Text(statusText == "FULL TIME" ? "Score unavailable" : "vs")
                        .italic()
                        .font(.system(size: 15, design: .serif))
                        .foregroundStyle(Theme.inkFaint)
                }
                teamColumn(awayTeam)
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
                Label("Explore prediction", systemImage: "chart.bar.xaxis")
                    .font(.system(size: 14, weight: .bold))
                    .foregroundStyle(Theme.bg)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 13)
                    .background(RoundedRectangle(cornerRadius: 12).fill(Theme.warm))
            }
        }
        .padding(18)
        .background(Theme.card)
        .clipShape(RoundedRectangle(cornerRadius: 18))
        .overlay(RoundedRectangle(cornerRadius: 18).stroke(Theme.line, lineWidth: 1))
        .padding(.horizontal, 16)
        .padding(.top, 16)
    }

    private func teamColumn(_ name: String) -> some View {
        VStack(spacing: 8) {
            CrestBadge(teamName: name, size: 56, league: league)
            Text(name)
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(Theme.ink)
                .multilineTextAlignment(.center)
                .lineLimit(2)
        }
        .frame(maxWidth: .infinity)
    }

    private var tabBar: some View {
        HStack {
            tabButton("Events", .events)
            Spacer()
            tabButton("Standings", .standings)
        }
        .padding(.horizontal, 22)
        .padding(.top, 22)
        .overlay(Rectangle().fill(Theme.line).frame(height: 1), alignment: .bottom)
    }

    private func tabButton(_ title: String, _ value: Tab) -> some View {
        Button { tab = value } label: {
            Text(title)
                .font(.system(size: 14, weight: tab == value ? .bold : .medium))
                .foregroundStyle(tab == value ? Theme.ink : Theme.inkFaint)
                .padding(.bottom, 12)
                .overlay(Rectangle().fill(tab == value ? Theme.ink : .clear).frame(height: 2), alignment: .bottom)
        }
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
            .font(.system(size: 11, weight: .bold))
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
                let color = event.detail.lowercased().contains("red") ? Color(hex: "E23D3D") : Color(hex: "E8C15A")
                return AnyView(RoundedRectangle(cornerRadius: 3).fill(color).frame(width: 12, height: 16))
            case "subst", "substitution":
                return AnyView(Image(systemName: "arrow.left.arrow.right").font(.system(size: 12)).foregroundStyle(Theme.inkMuted))
            default:
                return AnyView(Text("⚽").font(.system(size: 14)))
            }
        }()

        let text = VStack(alignment: home ? .trailing : .leading, spacing: 1) {
            Text(event.player ?? event.detail)
                .font(.system(size: 13.5, weight: .semibold))
                .foregroundStyle(Theme.ink)
            Text(subtitle(for: event))
                .font(.system(size: 11.5))
                .foregroundStyle(Theme.inkFaint)
        }

        return HStack(spacing: 10) {
            if home {
                Text(minuteText).font(.system(size: 12.5, weight: .bold)).foregroundStyle(Theme.inkMuted).frame(minWidth: 26, alignment: .leading)
                icon
                text
                Spacer(minLength: 0)
            } else {
                Spacer(minLength: 0)
                text
                icon
                Text(minuteText).font(.system(size: 12.5, weight: .bold)).foregroundStyle(Theme.inkMuted).frame(minWidth: 26, alignment: .trailing)
            }
        }
        .padding(.vertical, 10)
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
            VStack(spacing: 2) {
                standingsHeaderRow
                ForEach(standings) { row in
                    standingsRow(row)
                }
            }
            .padding(.horizontal, 18)
            .padding(.vertical, 20)
        }
    }

    private var standingsHeaderRow: some View {
        HStack(spacing: 2) {
            Text("#").frame(width: 20, alignment: .leading)
            Text("Club").frame(maxWidth: .infinity, alignment: .leading)
            Text("P").frame(width: 24, alignment: .center)
            Text("W").frame(width: 24, alignment: .center)
            Text("D").frame(width: 24, alignment: .center)
            Text("L").frame(width: 24, alignment: .center)
            Text("GD").frame(width: 30, alignment: .center)
            Text("Pts").frame(width: 34, alignment: .trailing)
        }
        .font(.system(size: 10, weight: .bold))
        .foregroundStyle(Theme.inkFaint)
        .padding(.bottom, 10)
        .overlay(Rectangle().fill(Theme.line).frame(height: 1), alignment: .bottom)
    }

    private func standingsRow(_ row: StandingRow) -> some View {
        let isHome = row.team.lowercased() == homeTeam.lowercased()
        let isAway = row.team.lowercased() == awayTeam.lowercased()
        let highlight: Color? = isHome ? Theme.warm.opacity(0.16) : (isAway ? Theme.cool.opacity(0.14) : nil)

        return HStack(spacing: 2) {
            Text("\(row.position)").frame(width: 20, alignment: .leading).fontWeight(.bold)
            HStack(spacing: 6) {
                SmallCrest(teamName: row.team, size: 20, league: league)
                Text(row.team).lineLimit(1)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .fontWeight(.semibold)
            Text("\(row.playedGames)").frame(width: 24, alignment: .center).foregroundStyle(Theme.inkMuted)
            Text("\(row.won)").frame(width: 24, alignment: .center).foregroundStyle(Theme.inkMuted)
            Text("\(row.draw)").frame(width: 24, alignment: .center).foregroundStyle(Theme.inkMuted)
            Text("\(row.lost)").frame(width: 24, alignment: .center).foregroundStyle(Theme.inkMuted)
            Text(row.goalDifference > 0 ? "+\(row.goalDifference)" : "\(row.goalDifference)")
                .frame(width: 30, alignment: .center).foregroundStyle(Theme.inkMuted)
            Text("\(row.points)").frame(width: 34, alignment: .trailing).fontWeight(.bold)
        }
        .font(.system(size: 12.5))
        .foregroundStyle(Theme.ink)
        .padding(.vertical, 10)
        .padding(.horizontal, 6)
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
