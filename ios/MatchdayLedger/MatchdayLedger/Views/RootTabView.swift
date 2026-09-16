import SwiftUI

struct RootTabView: View {
    var body: some View {
        TabView {
            FixturesView()
                .tabItem { Label("Fixtures", systemImage: "calendar") }

            LiveView()
                .tabItem { Label("Live", systemImage: "dot.radiowaves.left.and.right") }
        }
        .tint(Theme.warm)
    }
}
