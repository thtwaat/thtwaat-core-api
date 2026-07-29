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
    @Published var history: [Conversation] = []
    @Published var showHistory = false

    private var streamTask: Task<Void, Never>?
    private var lastUser: String?
    private let deps: AppDependencies

    init(deps: AppDependencies) { self.deps = deps }

    func loadHistory() async {
        if case .success(let list) = await deps.chatRepository.history(limit: 30) {
            history = list
        }
    }

    func openConversation(_ conversation: Conversation) {
        sessionId = conversation.id
        messages = (conversation.messages ?? []).map {
            ChatMessageItem(role: $0.role, content: $0.content)
        }
        showHistory = false
    }

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

    var body: some View {
        ChatScreen(deps: deps)
    }
}

private struct ChatScreen: View {
    @StateObject private var vm: ChatViewModel

    init(deps: AppDependencies) {
        _vm = StateObject(wrappedValue: ChatViewModel(deps: deps))
    }

    var body: some View {
        VStack(spacing: 0) {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 12) {
                        ForEach(vm.messages) { msg in
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
                        if vm.typing {
                            Text("Assistant is typing…").foregroundStyle(.secondary).id("typing")
                        }
                    }
                    .padding()
                }
                .onChange(of: vm.messages.count) { _, _ in
                    if let last = vm.messages.last?.id {
                        proxy.scrollTo(last, anchor: .bottom)
                    }
                }
            }

            if let err = vm.error {
                Text(err).foregroundStyle(.red).padding(.horizontal)
            }

            ScrollView(.horizontal, showsIndicators: false) {
                HStack {
                    ForEach(vm.suggested, id: \.self) { s in
                        Button(s) { vm.useSuggestion(s) }
                            .buttonStyle(.bordered)
                    }
                }
                .padding(.horizontal)
            }

            HStack {
                TextField("Message", text: $vm.input)
                    .textFieldStyle(.roundedBorder)
                Button("Send") { vm.send(stream: true) }
                    .buttonStyle(.borderedProminent)
                    .disabled(vm.streaming)
            }
            .padding()

            HStack {
                Button("Stop") { vm.stop() }.disabled(!vm.streaming)
                Button("Retry") { vm.retry() }.disabled(vm.streaming)
            }
            .padding(.bottom)
        }
        .navigationTitle("Chat")
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button("History") {
                    Task {
                        await vm.loadHistory()
                        vm.showHistory = true
                    }
                }
            }
        }
        .sheet(isPresented: $vm.showHistory) {
            NavigationStack {
                List(vm.history) { c in
                    Button {
                        vm.openConversation(c)
                    } label: {
                        VStack(alignment: .leading) {
                            Text(c.id).font(.headline)
                            Text("\(c.messages?.count ?? 0) messages · \(c.updatedAt ?? c.createdAt ?? "")")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
                .navigationTitle("Conversations")
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("Close") { vm.showHistory = false }
                    }
                }
            }
        }
    }
}
