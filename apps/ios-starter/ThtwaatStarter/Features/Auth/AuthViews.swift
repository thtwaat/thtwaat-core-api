import SwiftUI

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
            .disabled(loading)
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
