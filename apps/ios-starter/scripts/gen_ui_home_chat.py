from pathlib import Path
ROOT = Path(r"E:\THTWAAT\thtwaat-core-api\apps\ios-starter")

def w(rel: str, content: str) -> None:
    path = ROOT / rel.replace("/", "\\")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.lstrip("\n"), encoding="utf-8", newline="\n")
    print("wrote", rel)

w("ThtwaatStarter/Features/Auth/AuthViews.swift", r'''
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
''')

w("ThtwaatStarter/Features/Home/HomeView.swift", r'''
import SwiftUI
import Charts

struct HomeView: View {
    @EnvironmentObject private var deps: AppDependencies
    @Binding var path: NavigationPath
    @State private var usage: UsageSnapshot?
    @State private var agents: [Agent] = []
    @State private var conversations: [Conversation] = []
    @State private var error: String?
    @State private var loading = true

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("Dashboard").font(.largeTitle.bold())
                if let error { Text(error).foregroundStyle(.red) }

                Card(title: "Usage summary") {
                    Text("Messages: \(usage?.aiMessages ?? 0)")
                    Text("Tokens: \(usage?.totalTokens ?? 0)")
                    Text("Max agents: \(usage?.maxAgents ?? 0)")
                    Chart {
                        BarMark(x: .value("Metric", "Messages"), y: .value("Count", usage?.aiMessages ?? 0))
                        BarMark(x: .value("Metric", "Tokens/1k"), y: .value("Count", (usage?.totalTokens ?? 0) / 1000))
                    }
                    .frame(height: 140)
                }

                Card(title: "Analytics") {
                    Text("Live usage + agent activity for your company.")
                    Button("Open billing / quota") { path.append(AppRoute.billing) }
                }

                Text("Recent conversations").font(.title2.bold())
                ForEach(conversations.prefix(5)) { c in
                    Card(title: c.id) {
                        Text("\(c.messages?.count ?? 0) messages")
                        Text(c.updatedAt ?? c.createdAt ?? "")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                }

                Text("Recent agents").font(.title2.bold())
                ForEach(agents.prefix(5)) { a in
                    Card(title: a.name) {
                        Text(a.status ?? "unknown")
                    }
                }

                HStack {
                    Button("Knowledge") { path.append(AppRoute.knowledge) }
                    Button("Product") { path.append(AppRoute.product) }
                    Button("Domains") { path.append(AppRoute.domains) }
                }
                .buttonStyle(.bordered)
            }
            .padding()
        }
        .overlay { if loading { ProgressView() } }
        .refreshable { await load() }
        .task { await load() }
        .navigationTitle("Home")
    }

    private func load() async {
        loading = true
        defer { loading = false }
        async let u = deps.usageRepository.current()
        async let a = deps.agentsRepository.list()
        async let c = deps.chatRepository.history(limit: 5)
        if case .success(let snap) = await u { usage = snap }
        if case .success(let list) = await a { agents = list }
        if case .success(let list) = await c { conversations = list }
        if case .failure(let e) = await u { error = e.message }
    }
}

struct Card<Content: View>: View {
    let title: String
    @ViewBuilder var content: Content
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title).font(.headline)
            content
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 14))
    }
}
''')

w("ThtwaatStarter/Features/Chat/ChatView.swift", r'''
import SwiftUI
import MarkdownUI

struct ChatMessageItem: Identifiable, Equatable {
    let id = UUID()
    let role: String
    var content: String
}

@MainActor
final class ChatViewModel: ObservableObject {
    @Published var messages: [ChatMessageItem] = []
    @Published var input = ""
    @Published var streaming = false
    @Published var typing = false
    @Published var error: String?
    @Published var suggested = ["Summarize my product", "Draft a welcome reply", "Explain pricing"]
    @Published var sessionId: String?

    private var streamTask: Task<Void, Never>?
    private var lastUser: String?
    private let deps: AppDependencies

    init(deps: AppDependencies) { self.deps = deps }

    func send(stream: Bool = true) {
        let text = input.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !streaming else { return }
        lastUser = text
        messages.append(ChatMessageItem(role: "user", content: text))
        input = ""
        streaming = true
        typing = true
        error = nil
        if stream {
            startStream(text)
        } else {
            Task { await sendOnce(text) }
        }
    }

    private func sendOnce(_ text: String) async {
        switch await deps.chatRepository.chat(message: text, sessionId: sessionId) {
        case .success(let res):
            sessionId = res.conversationId ?? sessionId
            if let prompts = res.suggestedPrompts, !prompts.isEmpty { suggested = prompts }
            messages.append(ChatMessageItem(role: "assistant", content: res.text))
        case .failure(let e):
            error = e.message
        }
        streaming = false
        typing = false
    }

    private func startStream(_ text: String) {
        streamTask?.cancel()
        streamTask = Task {
            do {
                let stream = try await deps.chatRepository.stream(message: text, sessionId: sessionId)
                var buffer = ""
                for try await token in stream {
                    if Task.isCancelled { break }
                    switch token.event {
                    case "token", "message":
                        if let chunk = token.text, !chunk.isEmpty {
                            buffer += chunk
                            if messages.last?.role == "assistant" {
                                messages[messages.count - 1].content = buffer
                            } else {
                                messages.append(ChatMessageItem(role: "assistant", content: buffer))
                            }
                        }
                    case "done":
                        streaming = false
                        typing = false
                    case "error":
                        error = token.text ?? "Stream error"
                        streaming = false
                        typing = false
                    default:
                        break
                    }
                }
            } catch {
                self.error = error.localizedDescription
            }
            streaming = false
            typing = false
        }
    }

    func stop() {
        streamTask?.cancel()
        streaming = false
        typing = false
    }

    func retry() {
        guard let lastUser else { return }
        input = lastUser
        send(stream: true)
    }

    func useSuggestion(_ text: String) {
        input = text
        send(stream: true)
    }
}

struct ChatView: View {
    @EnvironmentObject private var deps: AppDependencies
    @StateObject private var vmHolder = ChatVMHolder()

    var body: some View {
        VStack(spacing: 0) {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 12) {
                        ForEach(vmHolder.vm?.messages ?? []) { msg in
                            VStack(alignment: .leading, spacing: 4) {
                                Text(msg.role.uppercased()).font(.caption).foregroundStyle(.secondary)
                                if msg.role == "assistant" {
                                    Markdown(msg.content)
                                } else {
                                    Text(msg.content)
                                }
                            }
                            .padding()
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 12))
                            .id(msg.id)
                        }
                        if vmHolder.vm?.typing == true {
                            Text("Assistant is typing…").foregroundStyle(.secondary).id("typing")
                        }
                    }
                    .padding()
                }
                .onChange(of: vmHolder.vm?.messages.count ?? 0) { _, _ in
                    if let last = vmHolder.vm?.messages.last?.id {
                        proxy.scrollTo(last, anchor: .bottom)
                    }
                }
            }

            if let err = vmHolder.vm?.error {
                Text(err).foregroundStyle(.red).padding(.horizontal)
            }

            ScrollView(.horizontal, showsIndicators: false) {
                HStack {
                    ForEach(vmHolder.vm?.suggested ?? [], id: \.self) { s in
                        Button(s) { vmHolder.vm?.useSuggestion(s) }
                            .buttonStyle(.bordered)
                    }
                }
                .padding(.horizontal)
            }

            HStack {
                TextField("Message", text: Binding(
                    get: { vmHolder.vm?.input ?? "" },
                    set: { vmHolder.vm?.input = $0 }
                ))
                .textFieldStyle(.roundedBorder)
                Button("Send") { vmHolder.vm?.send(stream: true) }
                    .buttonStyle(.borderedProminent)
                    .disabled(vmHolder.vm?.streaming == true)
            }
            .padding()

            HStack {
                Button("Stop") { vmHolder.vm?.stop() }.disabled(vmHolder.vm?.streaming != true)
                Button("Retry") { vmHolder.vm?.retry() }.disabled(vmHolder.vm?.streaming == true)
            }
            .padding(.bottom)
        }
        .navigationTitle("Chat")
        .onAppear {
            if vmHolder.vm == nil { vmHolder.vm = ChatViewModel(deps: deps) }
        }
    }
}

@MainActor
final class ChatVMHolder: ObservableObject {
    @Published var vm: ChatViewModel?
}
''')

print("home+chat done")
