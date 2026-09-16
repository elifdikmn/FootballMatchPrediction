import SwiftUI

struct CheckOutWhyView: View {
    let fixtureId: Int
    let homeTeam: String
    let awayTeam: String
    let scoreText: String?
    var league: String? = nil
    var statusText: String = "MATCH"

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
        .navigationTitle("Prediction")
        .navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(Theme.card, for: .navigationBar)
        .toolbarColorScheme(.dark, for: .navigationBar)
        .task { await load() }
    }

    private func body(for detail: MatchPredictionDetail) -> some View {
        VStack(alignment: .leading, spacing: 20) {
            VStack(alignment: .leading, spacing: 6) {
                Text("THE MATCH, EXPLAINED").font(.caption.weight(.bold)).tracking(2).foregroundStyle(Theme.warm)
                Text("Why this prediction?").font(.system(.largeTitle, design: .rounded).weight(.bold)).foregroundStyle(Theme.ink)
                Text("Probabilities, recent form and the factors to watch.").font(.subheadline).foregroundStyle(Theme.inkMuted)
            }
            matchCard(detail)
            mostLikelyOutcome(detail)
            recentForm(detail)
            if let comment = detail.comment, !comment.isEmpty {
                whySection(title: "Key insight", text: comment)
            }
            if let advice = detail.advice, !advice.isEmpty {
                whySection(title: "Prediction summary", text: advice)
            }
        }
        .padding(.horizontal, 22)
        .padding(.vertical, 20)
    }

    private func matchCard(_ detail: MatchPredictionDetail) -> some View {
        VStack(spacing: 18) {
            if let league { LeagueBadge(name: league, size: 32) }
            if let scoreText {
                HStack(spacing: 6) {
                    Circle().fill(statusText == "FULL TIME" ? Theme.success : Theme.warm).frame(width: 6, height: 6)
                    Text("\(statusText) · \(scoreText)")
                        .font(.system(size: 11, weight: .bold))
                        .tracking(0.5)
                        .foregroundStyle(Theme.warm)
                }
                .padding(.vertical, 5).padding(.leading, 9).padding(.trailing, 12)
                .background(Capsule().fill(Theme.warmSoft))
            }

            HStack(spacing: 20) {
                teamColumn(homeTeam)
                if let scoreText {
                    Text(scoreText).font(.system(.largeTitle, design: .rounded).weight(.bold)).foregroundStyle(Theme.success)
                } else {
                    Text("VS").font(.caption.weight(.bold)).foregroundStyle(Theme.inkFaint)
                }
                teamColumn(awayTeam)
            }

            Divider().background(Theme.line)

            let home = MatchPredictionDetail.parsePercent(detail.homePct)
            let draw = MatchPredictionDetail.parsePercent(detail.drawPct)
            let away = MatchPredictionDetail.parsePercent(detail.awayPct)
            if detail.homePct != nil || detail.drawPct != nil || detail.awayPct != nil {
                OutcomeBar(homePct: home, drawPct: draw, awayPct: away)
            } else {
                Text("Probabilities unavailable").font(.subheadline).foregroundStyle(Theme.inkMuted)
            }
        }
        .padding(20)
        .background(Theme.card)
        .clipShape(RoundedRectangle(cornerRadius: 26))
        .overlay(RoundedRectangle(cornerRadius: 26).stroke(Theme.line, lineWidth: 1))
    }

    private func teamColumn(_ name: String) -> some View {
        VStack(spacing: 8) {
            CrestBadge(teamName: name, size: 60, league: league)
            Text(name).font(.system(size: 15, weight: .semibold)).foregroundStyle(Theme.ink).multilineTextAlignment(.center).fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity)
    }

    private func mostLikelyOutcome(_ detail: MatchPredictionDetail) -> some View {
        let home = MatchPredictionDetail.parsePercent(detail.homePct)
        let draw = MatchPredictionDetail.parsePercent(detail.drawPct)
        let away = MatchPredictionDetail.parsePercent(detail.awayPct)
        let top = max(home, max(draw, away))
        let tied = [home, draw, away].filter { $0 == top }.count > 1
        let winnerName = top == 0 ? "Prediction pending" : tied ? "No clear favorite" : top == home ? homeTeam : top == away ? awayTeam : "Draw"
        let pctText = top > 0 ? " · \(Int(top.rounded()))%" : ""

        return VStack(alignment: .leading, spacing: 6) {
            Text("MOST LIKELY OUTCOME")
                .font(.system(size: 10, weight: .bold))
                .tracking(1)
                .foregroundStyle(Theme.warm)
            Text("\(winnerName)\(pctText)")
                .font(.system(size: 24, weight: .bold, design: .rounded))
                .foregroundStyle(Theme.ink)
            Text(top > 0 ? "Estimated probabilities; every outcome remains possible." : "There is not enough data to show an outcome yet.")
                .font(.subheadline)
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
            VStack(spacing: 18) {
                formColumn(homeTeam, form: detail.lastFiveHome?.form)
                formColumn(awayTeam, form: detail.lastFiveAway?.form)
            }
            Text("W Win · D Draw · L Loss")
                .font(.system(size: 11))
                .foregroundStyle(Theme.inkFaint)
        }
        .padding(18)
        .background(Theme.card, in: RoundedRectangle(cornerRadius: 20))
    }

    private func formColumn(_ name: String, form: String?) -> some View {
        VStack(alignment: .leading, spacing: 9) {
            Text(name).font(.system(size: 12.5, weight: .semibold)).foregroundStyle(Theme.ink)
            HStack(spacing: 5) {
                if let form, !form.isEmpty, form.uppercased().allSatisfy({ "WDL".contains($0) }) {
                    ForEach(Array(form.uppercased().filter { "WDL".contains($0) }.suffix(5).enumerated()), id: \.offset) { _, letter in
                        formBadge(letter)
                    }
                } else if let form, !form.isEmpty {
                    Text("Form rating: \(form)").font(.subheadline.weight(.semibold)).foregroundStyle(Theme.warm)
                } else {
                    Text("Form unavailable").font(.caption).foregroundStyle(Theme.inkFaint)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func formBadge(_ letter: Character) -> some View {
        let (border, textColor): (Color, Color) = {
            switch letter {
            case "W": return (Theme.success, Theme.success)
            case "D": return (Theme.draw, Theme.draw)
            default: return (Theme.warm, Theme.warm)
            }
        }()
        return Text(String(letter))
            .font(.system(size: 11, weight: .bold))
            .foregroundStyle(textColor)
            .frame(width: 34, height: 34)
            .background(Theme.card)
            .overlay(RoundedRectangle(cornerRadius: 7).stroke(border, lineWidth: letter == "W" ? 1.5 : 1))
            .clipShape(RoundedRectangle(cornerRadius: 7))
    }

    private func whySection(title: String, text: String) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(title)
                .font(.headline)
                .foregroundStyle(Theme.ink)
            Text(text)
                .font(.subheadline)
                .foregroundStyle(Theme.inkMuted)
                .lineSpacing(3)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(18)
        .background(Theme.card, in: RoundedRectangle(cornerRadius: 20))
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
