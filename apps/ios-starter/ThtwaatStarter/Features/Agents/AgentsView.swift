import SwiftUI

struct AgentsView: View {
    @EnvironmentObject private var deps: AppDependencies
    @State private var agents: [Agent] = []
    @State private var name = ""
    @State private var prompt = "You are a helpful assistant."
    @State private var editingId: String?
    @State private var welcome = "Hi! How can I help you today?"
    @State private var primaryColor = "#0F766E"
    @State private var info: String?
    @State private var error: String?

    var body: some View {
        List {
            if let error { Text(error).foregroundStyle(.red) }
            if let info { Text(info).font(.caption) }
            Section(editingId == nil ? "Create" : "Edit widget") {
                TextField("Name", text: $name)
                TextField("System prompt", text: $prompt, axis: .vertical)
                if editingId != nil {
                    TextField("Welcome message", text: $welcome, axis: .vertical)
                    TextField("Primary color", text: $primaryColor)
                        .textInputAutocapitalization(.never)
                }
                Button(editingId == nil ? "Create agent" : "Save widget") {
                    Task { await save() }
                }
                if editingId != nil {
                    Button("Cancel edit") { clearEdit() }
                }
            }
            Section("Agents") {
                ForEach(agents) { a in
                    VStack(alignment: .leading, spacing: 8) {
                        Text(a.name).font(.headline)
                        Text("\(a.status ?? "-") · \(a.id)").font(.caption)
                        HStack {
                            Button("Edit") { beginEdit(a) }
                            Button("Publish") {
                                Task {
                                    switch await deps.agentsRepository.publish(id: a.id) {
                                    case .success(let p):
                                        info = "Published \(p.agentId ?? a.id)\nkey=\(p.apiKey ?? "-")\n\(p.publicChatUrl ?? "")"
                                    case .failure(let e): error = e.message
                                    }
                                }
                            }
                            Button("API Key") {
                                Task {
                                    switch await deps.agentsRepository.createKey(id: a.id) {
                                    case .success(let k): info = "API key: \(k.displayKey)"
                                    case .failure(let e): error = e.message
                                    }
                                }
                            }
                        }
                        HStack {
                            Button("Widget") {
                                Task {
                                    switch await deps.agentsRepository.widget(id: a.id) {
                                    case .success(let w):
                                        info = "widget=\(w.widgetId ?? "-") theme=\(w.config?.theme ?? "-") welcome=\(w.config?.welcomeMessage ?? "-")"
                                    case .failure(let e): error = e.message
                                    }
                                }
                            }
                            Button("Embed") {
                                Task {
                                    switch await deps.agentsRepository.embed(id: a.id) {
                                    case .success(let e):
                                        info = e.script ?? e.previewUrl ?? "Embed ready"
                                    case .failure(let err): error = err.message
                                    }
                                }
                            }
                        }
                        .buttonStyle(.bordered)
                    }
                    .padding(.vertical, 4)
                }
            }
        }
        .navigationTitle("Agents")
        .task { await refresh() }
        .refreshable { await refresh() }
    }

    private func beginEdit(_ agent: Agent) {
        editingId = agent.id
        name = agent.name
        prompt = agent.systemPromptTemplate ?? prompt
        Task {
            if case .success(let w) = await deps.agentsRepository.widget(id: agent.id) {
                welcome = w.config?.welcomeMessage ?? welcome
                primaryColor = w.config?.primaryColor ?? primaryColor
            }
        }
    }

    private func clearEdit() {
        editingId = nil
        name = ""
        prompt = "You are a helpful assistant."
    }

    private func save() async {
        if let id = editingId {
            switch await deps.agentsRepository.updateWidget(
                id: id,
                welcome: welcome,
                primaryColor: primaryColor,
                agentName: name.isEmpty ? nil : name
            ) {
            case .success: info = "Widget updated"; clearEdit(); await refresh()
            case .failure(let e): error = e.message
            }
        } else {
            switch await deps.agentsRepository.create(name: name, prompt: prompt, description: nil) {
            case .success: name = ""; await refresh()
            case .failure(let e): error = e.message
            }
        }
    }

    private func refresh() async {
        switch await deps.agentsRepository.list() {
        case .success(let list): agents = list
        case .failure(let e): error = e.message
        }
    }
}
