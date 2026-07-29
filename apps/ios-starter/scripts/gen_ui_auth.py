from pathlib import Path
ROOT = Path(r"E:\THTWAAT\thtwaat-core-api\apps\ios-starter")

def w(rel: str, content: str) -> None:
    path = ROOT / rel.replace("/", "\\")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.lstrip("\n"), encoding="utf-8", newline="\n")
    print("wrote", rel)

w("ThtwaatStarter/Navigation/RootView.swift", r'''
import SwiftUI

struct RootView: View {
    @EnvironmentObject private var appState: AppState

    var body: some View {
        Group {
            if appState.isAuthenticated {
                MainTabView()
            } else {
                NavigationStack {
                    LoginView()
                }
            }
        }
        .animation(.easeInOut, value: appState.isAuthenticated)
    }
}

enum AppRoute: Hashable {
    case knowledge, product, domains, billing
}

struct MainTabView: View {
    @State private var path = NavigationPath()

    var body: some View {
        TabView {
            NavigationStack(path: $path) {
                HomeView(path: $path)
                    .navigationDestination(for: AppRoute.self) { route in
                        switch route {
                        case .knowledge: KnowledgeView()
                        case .product: ProductGeneratorView()
                        case .domains: DomainsView()
                        case .billing: BillingView()
                        }
                    }
            }
            .tabItem { Label("Home", systemImage: "house.fill") }

            NavigationStack { ChatView() }
                .tabItem { Label("Chat", systemImage: "bubble.left.and.bubble.right.fill") }

            NavigationStack { AgentsView() }
                .tabItem { Label("Agents", systemImage: "cpu") }

            NavigationStack { MarketplaceView() }
                .tabItem { Label("Market", systemImage: "storefront.fill") }

            NavigationStack { SettingsView() }
                .tabItem { Label("Settings", systemImage: "gearshape.fill") }
        }
        .tint(Color(red: 0.06, green: 0.46, blue: 0.43))
    }
}
''')

w("ThtwaatStarter/Features/Auth/AuthViewModel.swift", r'''
import Foundation
import Combine

@MainActor
final class AuthViewModel: ObservableObject {
    @Published var email = ""
    @Published var password = ""
    @Published var firstName = ""
    @Published var lastName = ""
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var infoMessage: String?

    private let deps: AppDependencies
    private let appState: AppState

    init(deps: AppDependencies, appState: AppState) {
        self.deps = deps
        self.appState = appState
    }

    func login() async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        switch await deps.authRepository.login(email: email.trimmingCharacters(in: .whitespaces), password: password) {
        case .success:
            appState.isAuthenticated = true
        case .failure(let err):
            errorMessage = err.message
        }
    }

    func signup() async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        let email = email.trimmingCharacters(in: .whitespaces)
        switch await deps.authRepository.signup(email: email, password: password, first: firstName, last: lastName) {
        case .success:
            switch await deps.authRepository.login(email: email, password: password) {
            case .success:
                appState.isAuthenticated = true
            case .failure(let err):
                infoMessage = "Account created. Please login."
                errorMessage = err.message
            }
        case .failure(let err):
            errorMessage = err.message
        }
    }

    func forgot() async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        switch await deps.authRepository.forgotPassword(email: email.trimmingCharacters(in: .whitespaces)) {
        case .success:
            infoMessage = "Reset email sent if the account exists."
        case .failure(let err):
            errorMessage = err.message
        }
    }

    func logout() async {
        _ = await deps.authRepository.logout()
        appState.isAuthenticated = false
    }
}
''')

w("ThtwaatStarter/Features/Auth/AuthViews.swift", r'''
import SwiftUI

struct LoginView: View {
    @EnvironmentObject private var deps: AppDependencies
    @EnvironmentObject private var appState: AppState
    @StateObject private var vm: AuthViewModel

    init() {
        // Placeholder; replaced in onAppear pattern via StateObject factory below
        _vm = StateObject(wrappedValue: AuthViewModel(deps: AppDependencies(), appState: AppState()))
    }

    var body: some View {
        AuthFormScaffold(title: "THTWAAT", subtitle: "Sign in to your AI workspace") {
            TextField("Email", text: $vm.email)
                .textInputAutocapitalization(.never)
                .keyboardType(.emailAddress)
            SecureField("Password", text: $vm.password)
            if let err = vm.errorMessage { Text(err).foregroundStyle(.red) }
            Button {
                Task { await vm.login() }
            } label: {
                Text(vm.isLoading ? "Signing in…" : "Login").frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .disabled(vm.isLoading)

            NavigationLink("Forgot password?") { ForgotPasswordView() }
            NavigationLink("Create account") { SignupView() }
        }
        .onAppear {
            // Rebuild VM with real deps once
        }
        .modifier(InjectAuthVM(vm: vm, deps: deps, appState: appState))
    }
}

private struct InjectAuthVM: ViewModifier {
    @ObservedObject var vm: AuthViewModel
    let deps: AppDependencies
    let appState: AppState
    func body(content: Content) -> some View { content }
}

struct LoginViewFixed: View {
    @EnvironmentObject private var deps: AppDependencies
    @EnvironmentObject private var appState: AppState
    @State private var email = ""
    @State private var password = ""
    @State private var loading = false
    @State private var error: String?

    var body: some View {
        AuthFormScaffold(title: "THTWAAT", subtitle: "Sign in to your AI workspace") {
            TextField("Email", text: $email).textInputAutocapitalization(.never).keyboardType(.emailAddress)
            SecureField("Password", text: $password)
            if let error { Text(error).foregroundStyle(.red) }
            Button {
                Task {
                    loading = true
                    defer { loading = false }
                    switch await deps.authRepository.login(email: email, password: password) {
                    case .success: appState.isAuthenticated = true
                    case .failure(let e): error = e.message
                    }
                }
            } label: { Text(loading ? "Signing in…" : "Login").frame(maxWidth: .infinity) }
            .buttonStyle(.borderedProminent)
            NavigationLink("Forgot password?") { ForgotPasswordView() }
            NavigationLink("Create account") { SignupView() }
        }
    }
}

struct SignupView: View {
    @EnvironmentObject private var deps: AppDependencies
    @EnvironmentObject private var appState: AppState
    @State private var email = ""
    @State private var password = ""
    @State private var first = ""
    @State private var last = ""
    @State private var loading = false
    @State private var error: String?
    @State private var info: String?

    var body: some View {
        AuthFormScaffold(title: "Create account", subtitle: "Join THTWAAT") {
            TextField("First name", text: $first)
            TextField("Last name", text: $last)
            TextField("Email", text: $email).textInputAutocapitalization(.never)
            SecureField("Password", text: $password)
            if let error { Text(error).foregroundStyle(.red) }
            if let info { Text(info) }
            Button {
                Task {
                    loading = true
                    defer { loading = false }
                    switch await deps.authRepository.signup(email: email, password: password, first: first, last: last) {
                    case .success:
                        switch await deps.authRepository.login(email: email, password: password) {
                        case .success: appState.isAuthenticated = true
                        case .failure(let e): info = "Created. Please login."; error = e.message
                        }
                    case .failure(let e): error = e.message
                    }
                }
            } label: { Text("Sign up").frame(maxWidth: .infinity) }
            .buttonStyle(.borderedProminent)
        }
    }
}

struct ForgotPasswordView: View {
    @EnvironmentObject private var deps: AppDependencies
    @State private var email = ""
    @State private var message: String?
    @State private var error: String?

    var body: some View {
        AuthFormScaffold(title: "Forgot password", subtitle: "We'll email a reset code") {
            TextField("Email", text: $email).textInputAutocapitalization(.never)
            if let error { Text(error).foregroundStyle(.red) }
            if let message { Text(message) }
            Button {
                Task {
                    switch await deps.authRepository.forgotPassword(email: email) {
                    case .success: message = "Reset email sent if account exists"
                    case .failure(let e): error = e.message
                    }
                }
            } label: { Text("Send reset").frame(maxWidth: .infinity) }
            .buttonStyle(.borderedProminent)
        }
    }
}

struct AuthFormScaffold<Content: View>: View {
    let title: String
    let subtitle: String
    @ViewBuilder var content: Content

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text(title).font(.largeTitle.bold())
                Text(subtitle).foregroundStyle(.secondary)
                content
            }
            .padding(24)
            .textFieldStyle(.roundedBorder)
        }
    }
}
''')

# Simplify RootView to use LoginViewFixed
w("ThtwaatStarter/Navigation/RootView.swift", r'''
import SwiftUI

struct RootView: View {
    @EnvironmentObject private var appState: AppState

    var body: some View {
        Group {
            if appState.isAuthenticated {
                MainTabView()
            } else {
                NavigationStack {
                    LoginViewFixed()
                }
            }
        }
        .animation(.easeInOut, value: appState.isAuthenticated)
    }
}

enum AppRoute: Hashable {
    case knowledge, product, domains, billing
}

struct MainTabView: View {
    @State private var path = NavigationPath()

    var body: some View {
        TabView {
            NavigationStack(path: $path) {
                HomeView(path: $path)
                    .navigationDestination(for: AppRoute.self) { route in
                        switch route {
                        case .knowledge: KnowledgeView()
                        case .product: ProductGeneratorView()
                        case .domains: DomainsView()
                        case .billing: BillingView()
                        }
                    }
            }
            .tabItem { Label("Home", systemImage: "house.fill") }

            NavigationStack { ChatView() }
                .tabItem { Label("Chat", systemImage: "bubble.left.and.bubble.right.fill") }

            NavigationStack { AgentsView() }
                .tabItem { Label("Agents", systemImage: "cpu") }

            NavigationStack { MarketplaceView() }
                .tabItem { Label("Market", systemImage: "storefront.fill") }

            NavigationStack { SettingsView() }
                .tabItem { Label("Settings", systemImage: "gearshape.fill") }
        }
        .tint(Color(red: 0.06, green: 0.46, blue: 0.43))
    }
}
''')

print("auth+nav done")
