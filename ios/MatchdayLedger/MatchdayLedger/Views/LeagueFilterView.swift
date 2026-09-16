import SwiftUI

struct LeagueFilterView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var selection: Set<League>
    let onApply: (Set<League>) -> Void

    init(selected: Set<League>, onApply: @escaping (Set<League>) -> Void) {
        _selection = State(initialValue: selected)
        self.onApply = onApply
    }

    var body: some View {
        NavigationStack {
            ZStack {
                Theme.bg.ignoresSafeArea()
                VStack(spacing: 0) {
                    ScrollView {
                        VStack(spacing: 10) {
                            row(title: "All Leagues", isSelected: selection.isEmpty) {
                                selection.removeAll()
                            }
                            ForEach(League.allCases) { league in
                                row(title: league.displayName, isSelected: selection.contains(league)) {
                                    if selection.contains(league) {
                                        selection.remove(league)
                                    } else {
                                        selection.insert(league)
                                    }
                                }
                            }
                        }
                        .padding(16)
                    }

                    Button {
                        onApply(selection)
                        dismiss()
                    } label: {
                        Text("Show Matches")
                            .font(.system(size: 14, weight: .bold))
                            .foregroundStyle(Theme.bg)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 15)
                            .background(RoundedRectangle(cornerRadius: 14).fill(Theme.warm))
                    }
                    .padding(16)
                }
            }
            .navigationTitle("Leagues")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarBackground(Theme.card, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
        .preferredColorScheme(.dark)
    }

    private func row(title: String, isSelected: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 12) {
                LeagueBadge(name: title, size: 36)
                Text(title)
                    .font(.system(size: 15, weight: .medium))
                    .foregroundStyle(Theme.ink)
                Spacer()
                Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                    .foregroundStyle(isSelected ? Theme.warm : Theme.inkFaint)
            }
            .padding(16)
            .background(Theme.card)
            .clipShape(RoundedRectangle(cornerRadius: 14))
            .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.line, lineWidth: 1))
        }
    }
}
