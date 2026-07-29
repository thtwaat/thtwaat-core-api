import SwiftUI

struct SettingsView: View {
    @EnvironmentObject private var deps: AppDependencies
    @EnvironmentObject private var appState: AppState
    @State private var profile: UserProfile?
    @State private var apiKey = ""
    @State private var error: String?

    var body: some View {
        Form {
            if let error { Text(error).foregroundStyle(.red) }
            Section("Profile") {
                Text("\((profile?.firstName ?? "")) \((profile?.lastName ?? ""))")
                Text(profile?.email ?? "-")
                Text("role=\(profile?.role ?? "-")")
            }
            Section("Company") {
                Text("company_id=\(profile?.companyId ?? "-")")
            }
            Section("Theme") {
                Picker("Theme", selection: $appState.themeMode) {
                    ForEach(ThemeMode.allCases, id: \.self) { mode in
                        Text(mode.rawValue.capitalized).tag(mode)
                    }
                }
                .onChange(of: appState.themeMode) { _, mode in
                    Task { await deps.sessionStore.setThemeMode(mode) }
                }
            }
            Section("API Keys") {
                SecureField("Agent API key", text: $apiKey)
                Button("Save API key") {
                    Task { await deps.sessionStore.saveAPIKey(apiKey) }
                }
            }
            Section {
                Button("Logout", role: .destructive) {
                    Task {
                        _ = await deps.authRepository.logout()
                        appState.isAuthenticated = false
                    }
                }
            }
        }
        .navigationTitle("Settings")
        .task {
            switch await deps.authRepository.me() {
            case .success(let p): profile = p
            case .failure(let e): error = e.message
            }
            appState.themeMode = await deps.sessionStore.themeMode()
            apiKey = await deps.sessionStore.apiKey() ?? ""
        }
    }
}
