import SwiftUI

@main
struct ThtwaatStarterApp: App {
    @StateObject private var appState = AppState()
    @StateObject private var dependencies = AppDependencies()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(appState)
                .environmentObject(dependencies)
                .preferredColorScheme(appState.colorScheme)
                .task {
                    await dependencies.bootstrap()
                    appState.isAuthenticated = await dependencies.sessionStore.hasAccessToken()
                    appState.themeMode = await dependencies.sessionStore.themeMode()
                }
        }
    }
}
