import SwiftUI

struct CheckOutWhyView: View {
    let fixtureId: Int
    let homeTeam: String
    let awayTeam: String
    let scoreText: String?

    @State private var detail: MatchPredictionDetail?
    @State private var isLoading = false
    @State private var errorMessage: String?

    var body: some View {
        ZStack {
            Theme.bg.ignoresSafeArea()
            if isLoading {
                ProgressView().tint(Theme.ink)
            } else if let errorMessage {
                ErrorStateView(message: errorMessage) { Task { await load() } }
            } else if let detail {
                ScrollView { body(for: detail) }
            } else {
                EmptyStateView(text: "No explanation available for this match.")
            }
        }
        .navigationTitle("Check Out Why")
        .navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(Theme.card, for: .navigationBar)
        .toolbarColorScheme(.dark, for: .navigationBar)
        .task { await load() }
    }

    private func body(for detail: MatchPredictionDetail) -> some View {
        VStack(alignment: .leading, spacing: 24) {
            matchCard(detail)
            mostLikelyOutcome(detail)
            recentForm(detail)
            if let comment = detail.comment, !comment.isEmpty {
                whySection(title: "Recent form", text: comment)
            }
            if let advice = detail.advice, !advice.isEmpty {
                whySection(title: "Advice", text: advice)
            }
        }
        .padding(.horizontal, 22)
        .padding(.vertical, 20)
    }

    private func matchCard(_ detail: MatchPredictionDetail) -> some View {
        VStack(spacing: 18) {
            if let scoreText {
                HStack(spacing: 6) {
                    Circle().fill(Theme.warm).frame(width: 6, height: 6)
                    Text("Live · \(scoreText)")
                        .font(.system(size: 11, weight: .bold))
                        .tracking(0.5)
                        .foregroundStyle(Color(hex: "FF7A7C"))
                }
                .padding(.vertical, 5).padding(.leading, 9).padding(.trailing, 12)
                .background(Capsule().fill(Theme.warmSoft))
            }

            HStack(spacing: 20) {
                teamColumn(homeTeam)
                if let scoreText {
                    Text(scoreText).font(.system(size: 30, weight: .bold)).foregroundStyle(Theme.ink)
                }
                teamColumn(awayTeam)
            }

            Divider().background(Theme.line)

            let home = MatchPredictionDetail.parsePercent(detail.homePct)
            let draw = MatchPredictionDetail.parsePercent(detail.drawPct)
            let away = MatchPredictionDetail.parsePercent(detail.awayPct)
            OutcomeBar(homePct: home, drawPct: draw, awayPct: away)
        }
        .padding(20)
        .background(Theme.card)
        .clipShape(RoundedRectangle(cornerRadius: 18))
        .overlay(RoundedRectangle(cornerRadius: 18).stroke(Theme.line, lineWidth: 1))
    }

    private func teamColumn(_ name: String) -> some View {
        VStack(spacing: 8) {
            CrestBadge(teamName: name, size: 50)
            Text(name).font(.system(size: 13, weight: .semibold)).foregroundStyle(Theme.ink)
        }
        .frame(maxWidth: .infinity)
    }

    private func mostLikelyOutcome(_ detail: MatchPredictionDetail) -> some View {
        let home = MatchPredictionDetail.parsePercent(detail.homePct)
        let draw = MatchPredictionDetail.parsePercent(detail.drawPct)
        let away = MatchPredictionDetail.parsePercent(detail.awayPct)
        let top = max(home, max(draw, away))
        let pctText = "\(Int(top.rounded()))%"
        let winnerName = detail.winner ?? (top == home ? homeTeam : (top == away ? awayTeam : "Draw"))

        return VStack(alignment: .leading, spacing: 6) {
            Text("MOST LIKELY OUTCOME")
                .font(.system(size: 10, weight: .bold))
                .tracking(1)
                .foregroundStyle(Color(hex: "FF7A7C"))
            Text("\(winnerName) · \(pctText)")
                .font(.system(size: 19, weight: .semibold, design: .serif))
                .foregroundStyle(Theme.ink)
            Text("The model favors this outcome, while other results remain possible.")
                .font(.system(size: 12.5))
                .foregroundStyle(Theme.inkMuted)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(18)
        .background(Theme.warmSoft)
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }

    private func recentForm(_ detail: MatchPredictionDetail) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("RECENT FORM · LAST FIVE MATCHES")
                .font(.system(size: 10.5, weight: .bold))
                .tracking(1)
                .foregroundStyle(Theme.inkFaint)
            HStack(alignment: .top, spacing: 24) {
                formColumn(homeTeam, form: detail.lastFiveHome?.form)
                formColumn(awayTeam, form: detail.lastFiveAway?.form)
            }
            Text("W Win · D Draw · L Loss")
                .font(.system(size: 11))
                .foregroundStyle(Theme.inkFaint)
        }
    }

    private func formColumn(_ name: String, form: String?) -> some View {
        VStack(alignment: .leading, spacing: 9) {
            Text(name).font(.system(size: 12.5, weight: .semibold)).foregroundStyle(Theme.ink)
            HStack(spacing: 5) {
                if let form, !form.isEmpty {
                    ForEach(Array(form.uppercased()), id: \.self) { letter in
                        formBadge(letter)
                    }
                } else {
                    Text("—").foregroundStyle(Theme.inkFaint)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func formBadge(_ letter: Character) -> some View {
        let (border, textColor): (Color, Color) = {
            switch letter {
            case "W": return (Theme.inkMuted, Theme.ink)
            case "D": return (Theme.line, Theme.inkMuted)
            default: return (Theme.line, Theme.inkFaint)
            }
        }()
        return Text(String(letter))
            .font(.system(size: 11, weight: .bold))
            .foregroundStyle(textColor)
            .frame(width: 26, height: 26)
            .background(Theme.card)
            .overlay(RoundedRectangle(cornerRadius: 7).stroke(border, lineWidth: letter == "W" ? 1.5 : 1))
            .clipShape(RoundedRectangle(cornerRadius: 7))
    }

    private func whySection(title: String, text: String) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(title)
                .font(.system(size: 15, weight: .semibold, design: .serif))
                .foregroundStyle(Theme.ink)
            Text(text)
                .font(.system(size: 12.5))
                .foregroundStyle(Theme.inkMuted)
                .lineSpacing(3)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.top, 12)
        .overlay(Rectangle().fill(Theme.line).frame(height: 1), alignment: .top)
    }

    private func load() async {
        isLoading = true
        errorMessage = nil
        do {
            detail = try await APIClient.shared.predictionDetail(fixtureId: fixtureId)
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }
}
