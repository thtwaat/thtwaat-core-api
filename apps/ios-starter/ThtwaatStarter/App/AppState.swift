import SwiftUI
import Combine

@MainActor
final class AppState: ObservableObject {
    @Published var isAuthenticated = false
    @Published var themeMode: ThemeMode = .system

    var colorScheme: ColorScheme? {
        switch themeMode {
        case .system: return nil
        case .light: return .light
        case .dark: return .dark
        }
    }
}

enum ThemeMode: String, CaseIterable, Codable, Sendable {
    case system, light, dark
}
