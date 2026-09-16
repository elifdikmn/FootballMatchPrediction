import SwiftUI

struct RootTabView: View {
    var body: some View {
        TabView {
            FixturesView()
                .tabItem { Label("Fixtures", systemImage: "calendar") }

            LiveView()
                .tabItem { Label("Live", systemImage: "dot.radiowaves.left.and.right") }

            StandingsTabView()
                .tabItem { Label("Table", systemImage: "list.number") }
        }
        .tint(Theme.warm)
    }
}

/// The "Table" tab: pick a league, browse its standings.
private struct StandingsTabView: View {
    @State private var league: League = .premierLeague
    @State private var rows: [StandingRow] = []
    @State private var isLoading = false
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            ZStack {
                Theme.bg.ignoresSafeArea()
                VStack(spacing: 0) {
                    leaguePicker
                    ScrollView {
                        content
                            .padding(.horizontal, 18)
                            .padding(.vertical, 16)
                    }
                }
            }
            .navigationTitle("Table")
            .toolbarBackground(Theme.card, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .task { await load() }
            .onChange(of: league) { _ in Task { await load() } }
        }
    }

    private var leaguePicker: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(League.allCases) { item in
                    let selected = item == league
                    Text(item.displayName)
                        .font(.system(size: 12, weight: selected ? .semibold : .medium))
                        .foregroundStyle(selected ? Color(hex: "FF7A7C") : Theme.inkMuted)
                        .padding(.vertical, 7).padding(.horizontal, 16)
                        .background(
                            Capsule().fill(selected ? Theme.warmSoft : Theme.card)
                        )
                        .overlay(Capsule().stroke(selected ? Theme.warm.opacity(0.4) : Theme.line, lineWidth: 1))
                        .onTapGesture { league = item }
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
        }
    }

    @ViewBuilder
    private var content: some View {
        if isLoading {
            ProgressView().tint(Theme.ink).padding(.top, 60)
        } else if let errorMessage {
            ErrorStateView(message: errorMessage) { Task { await load() } }.frame(height: 200)
        } else if rows.isEmpty {
            EmptyStateView(text: "No standings available.").frame(height: 200)
        } else {
            VStack(spacing: 2) {
                headerRow
                ForEach(rows) { row in rowView(row) }
            }
        }
    }

    private var headerRow: some View {
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

    private func rowView(_ row: StandingRow) -> some View {
        HStack(spacing: 2) {
            Text("\(row.position)").frame(width: 20, alignment: .leading).fontWeight(.bold)
            HStack(spacing: 6) {
                SmallCrest(teamName: row.team, size: 13)
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
    }

    private func load() async {
        isLoading = true
        errorMessage = nil
        do {
            rows = try await APIClient.shared.standings(leagueCode: league.rawValue)
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }
}
