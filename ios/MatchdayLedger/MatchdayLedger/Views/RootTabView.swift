import SwiftUI

extension Notification.Name {
    static let openLiveTab = Notification.Name("MatchdayLedger.openLiveTab")
}

struct RootTabView: View {
    @State private var selectedTab: Int = 0

    var body: some View {
        TabView(selection: $selectedTab) {
            FixturesView()
                .tabItem { Label("Fixtures", systemImage: "calendar") }
                .tag(0)

            LiveView()
                .tabItem { Label("Live", systemImage: "dot.radiowaves.left.and.right") }
                .tag(1)
        }
        .tint(Theme.warm)
        .task { await BrandingStore.shared.load() }
        .onReceive(NotificationCenter.default.publisher(for: .openLiveTab)) { _ in
            selectedTab = 1
        }
    }
}
