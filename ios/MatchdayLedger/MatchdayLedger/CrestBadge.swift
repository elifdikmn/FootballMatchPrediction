import SwiftUI

/// A generic heraldic shield outline — original artwork, not any real club's crest.
struct ShieldShape: Shape {
    func path(in rect: CGRect) -> Path {
        let sx = rect.width / 40
        let sy = rect.height / 44
        func pt(_ x: CGFloat, _ y: CGFloat) -> CGPoint {
            CGPoint(x: rect.minX + x * sx, y: rect.minY + y * sy)
        }
        var path = Path()
        path.move(to: pt(20, 2))
        path.addLine(to: pt(36, 7))
        path.addLine(to: pt(36, 20))
        path.addCurve(to: pt(20, 42), control1: pt(36, 30), control2: pt(29, 38))
        path.addCurve(to: pt(4, 20), control1: pt(11, 38), control2: pt(4, 30))
        path.addLine(to: pt(4, 7))
        path.closeSubpath()
        return path
    }
}

/// Deterministically derives a color + monogram for any team name, so every
/// real team gets a stable, original crest without using anyone's actual logo.
enum CrestGenerator {
    private static func stableHash(_ s: String) -> UInt64 {
        var hash: UInt64 = 5381
        for byte in s.utf8 {
            hash = ((hash << 5) &+ hash) &+ UInt64(byte)
        }
        return hash
    }

    static func color(for teamName: String) -> Color {
        let hash = stableHash(teamName.lowercased())
        let hue = Double(hash % 360) / 360.0
        return Color(hue: hue, saturation: 0.55, brightness: 0.6)
    }

    static func textColor(for teamName: String) -> Color {
        let hash = stableHash(teamName.lowercased())
        let brightness = Double((hash / 360) % 100) / 100.0
        return brightness > 0.7 ? .black : .white
    }

    static func monogram(for teamName: String) -> String {
        let cleaned = teamName.replacingOccurrences(of: ".", with: "")
        let words = cleaned.split(separator: " ").filter { !$0.isEmpty }
        if words.count >= 2 {
            return (words[0].prefix(1) + words[1].prefix(1)).uppercased()
        } else if let word = words.first {
            return String(word.prefix(2)).uppercased()
        }
        return "?"
    }
}

struct CrestBadge: View {
    let teamName: String
    var size: CGFloat = 44

    var body: some View {
        ZStack {
            ShieldShape()
                .fill(CrestGenerator.color(for: teamName))
                .overlay(ShieldShape().stroke(Color.black.opacity(0.35), lineWidth: 1))
            Text(CrestGenerator.monogram(for: teamName))
                .font(.system(size: size * 0.32, weight: .bold, design: .serif))
                .foregroundStyle(.white)
        }
        .frame(width: size * 0.91, height: size)
    }
}

struct SmallCrest: View {
    let teamName: String
    var size: CGFloat = 13

    var body: some View {
        ShieldShape()
            .fill(CrestGenerator.color(for: teamName))
            .frame(width: size * 0.91, height: size)
    }
}
