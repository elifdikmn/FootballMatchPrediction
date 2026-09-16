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

/// Vibrant matchday palette: home red, away yellow, draw blue; form wins green.
enum Theme {
    static let bg = Color(hex: "0F1218")
    static let card = Color(hex: "191D25")
    static let ink = Color(hex: "F4F1ED")
    static let inkMuted = Color(hex: "A7ABB3")
    static let inkFaint = Color(hex: "8F9CAF")
    static let line = Color(hex: "31353E")
    static let warm = Color(hex: "FF3B45")
    static let warmSoft = Color(hex: "4A1720")
    static let cool = Color(hex: "FFD600")
    static let success = Color(hex: "28E878")
    static let draw = Color(hex: "168BFF")
}
