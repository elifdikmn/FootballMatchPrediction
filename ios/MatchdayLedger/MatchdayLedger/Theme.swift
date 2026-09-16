import SwiftUI

extension Color {
    init(hex: String) {
        let scanner = Scanner(string: hex)
        var rgb: UInt64 = 0
        scanner.scanHexInt64(&rgb)
        let r = Double((rgb & 0xFF0000) >> 16) / 255
        let g = Double((rgb & 0x00FF00) >> 8) / 255
        let b = Double(rgb & 0x0000FF) / 255
        self.init(red: r, green: g, blue: b)
    }
}

/// Palette carried over from the Matchday Ledger design canvas (dark editorial theme,
/// red = home, yellow = away, green = draw).
enum Theme {
    static let bg = Color(hex: "0B1220")
    static let card = Color(hex: "141F30")
    static let ink = Color(hex: "F4F1ED")
    static let inkMuted = Color(hex: "A7ABB3")
    static let inkFaint = Color(hex: "8F9CAF")
    static let line = Color(hex: "29374B")
    static let warm = Color(hex: "72E5B1")
    static let warmSoft = Color(hex: "153A32")
    static let cool = Color(hex: "8CAEFF")
    static let draw = Color(hex: "D6B878")
}
