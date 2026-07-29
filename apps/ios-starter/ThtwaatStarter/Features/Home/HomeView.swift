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
