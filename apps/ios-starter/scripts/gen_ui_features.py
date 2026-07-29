from pathlib import Path
ROOT = Path(r"E:\THTWAAT\thtwaat-core-api\apps\ios-starter")

def w(rel: str, content: str) -> None:
    path = ROOT / rel.replace("/", "\\")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.lstrip("\n"), encoding="utf-8", newline="\n")
    print("wrote", rel)

w("ThtwaatStarter/Features/Knowledge/KnowledgeView.swift", r'''
import SwiftUI
import UniformTypeIdentifiers

struct KnowledgeView: View {
    @EnvironmentObject private var deps: AppDependencies
    @State private var bases: [KnowledgeBase] = []
    @State private var results: [SearchResultItem] = []
    @State private var name = ""
    @State private var query = ""
    @State private var error: String?
    @State private var info: String?

    var body: some View {
        List {
            if let error { Text(error).foregroundStyle(.red) }
            if let info { Text(info) }
            Section("Create") {
                TextField("Knowledge base name", text: $name)
                Button("Create") {
                    Task {
                        switch await deps.knowledgeRepository.createBase(name: name, description: nil) {
                        case .success: await refresh()
                        case .failure(let e): error = e.message
                        }
                    }
                }
            }
            Section("Search") {
                TextField("Query", text: $query)
                Button("Search") {
                    Task {
                        switch await deps.knowledgeRepository.search(query: query) {
                        case .success(let items): results = items
                        case .failure(let e): error = e.message
                        }
                    }
                }
            }
            Section("Bases") {
                ForEach(bases) { b in
                    VStack(alignment: .leading) {
                        Text(b.name).font(.headline)
                        Text(b.description ?? b.id).font(.caption).foregroundStyle(.secondary)
                    }
                }
            }
            Section("Results") {
                ForEach(results) { r in
                    VStack(alignment: .leading) {
                        Text(String(format: "score %.3f", r.score ?? 0))
                        Text(r.body)
                        if let doc = r.documentId {
                            Button("Delete document") {
                                Task {
                                    switch await deps.knowledgeRepository.deleteDocument(id: doc) {
                                    case .success: info = "Deleted \(doc)"
                                    case .failure(let e): error = e.message
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        .navigationTitle("Knowledge")
        .task { await refresh() }
    }

    private func refresh() async {
        if case .success(let list) = await deps.knowledgeRepository.listBases() {
            bases = list
        }
    }
}
''')

w("ThtwaatStarter/Features/Agents/AgentsView.swift", r'''
import SwiftUI

struct AgentsView: View {
    @EnvironmentObject private var deps: AppDependencies
    @State private var agents: [Agent] = []
    @State private var name = ""
    @State private var prompt = "You are a helpful assistant."
    @State private var info: String?
    @State private var error: String?

    var body: some View {
        List {
            if let error { Text(error).foregroundStyle(.red) }
            if let info { Text(info) }
            Section("Create") {
                TextField("Name", text: $name)
                TextField("System prompt", text: $prompt, axis: .vertical)
                Button("Create agent") {
                    Task {
                        switch await deps.agentsRepository.create(name: name, prompt: prompt, description: nil) {
                        case .success: await refresh()
                        case .failure(let e): error = e.message
                        }
                    }
                }
            }
            Section("Agents") {
                ForEach(agents) { a in
                    VStack(alignment: .leading, spacing: 8) {
                        Text(a.name).font(.headline)
                        Text("\(a.status ?? "-") · \(a.id)").font(.caption)
                        HStack {
                            Button("Publish") {
                                Task {
                                    switch await deps.agentsRepository.publish(id: a.id) {
                                    case .success(let p): info = "Published \(p.agentId ?? a.id) key=\(p.apiKey ?? "-")"
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

    private func refresh() async {
        switch await deps.agentsRepository.list() {
        case .success(let list): agents = list
        case .failure(let e): error = e.message
        }
    }
}
''')

w("ThtwaatStarter/Features/Marketplace/MarketplaceView.swift", r'''
import SwiftUI

struct MarketplaceView: View {
    @EnvironmentObject private var deps: AppDependencies
    @State private var templates: [TemplateItem] = []
    @State private var installed: [Installation] = []
    @State private var q = ""
    @State private var info: String?
    @State private var error: String?

    var body: some View {
        List {
            if let error { Text(error).foregroundStyle(.red) }
            if let info { Text(info) }
            Section("Browse") {
                TextField("Search", text: $q)
                Button("Search templates") { Task { await refresh() } }
            }
            Section("Templates") {
                ForEach(templates) { t in
                    VStack(alignment: .leading) {
                        Text(t.name).font(.headline)
                        Text("\(t.category ?? "") · v\(t.version ?? "")")
                        Text(t.description ?? "").font(.caption)
                        Button("Install") {
                            Task {
                                switch await deps.marketplaceRepository.install(idOrSlug: t.slug) {
                                case .success(let i): info = "Installed \(i.id)"; await refresh()
                                case .failure(let e): error = e.message
                                }
                            }
                        }
                    }
                }
            }
            Section("Installed") {
                ForEach(installed) { i in
                    VStack(alignment: .leading, spacing: 6) {
                        Text(i.templateName ?? i.templateSlug ?? i.id).font(.headline)
                        Text("status=\(i.status ?? "-") v=\(i.installedVersion ?? "-")")
                        HStack {
                            Button("Connect") { Task { _ = await deps.marketplaceRepository.connect(id: i.id); await refresh() } }
                            Button("Publish") { Task { _ = await deps.marketplaceRepository.publish(id: i.id); await refresh() } }
                            Button("Update") { Task { _ = await deps.marketplaceRepository.update(id: i.id); await refresh() } }
                        }
                        HStack {
                            Button("Rollback") { Task { _ = await deps.marketplaceRepository.rollback(id: i.id); await refresh() } }
                            Button("Uninstall", role: .destructive) {
                                Task { _ = await deps.marketplaceRepository.uninstall(id: i.id); await refresh() }
                            }
                        }
                        .buttonStyle(.bordered)
                    }
                }
            }
        }
        .navigationTitle("Marketplace")
        .task { await refresh() }
    }

    private func refresh() async {
        async let t = deps.marketplaceRepository.templates(q: q.isEmpty ? nil : q)
        async let i = deps.marketplaceRepository.installed()
        if case .success(let list) = await t { templates = list }
        if case .success(let list) = await i { installed = list }
        if case .failure(let e) = await t { error = e.message }
    }
}
''')

w("ThtwaatStarter/Features/ProductGenerator/ProductGeneratorView.swift", r'''
import SwiftUI

struct ProductGeneratorView: View {
    @EnvironmentObject private var deps: AppDependencies
    @State private var prompt = "Restaurant website with AI ordering"
    @State private var analysis: ProductAnalysis?
    @State private var generation: ProductGeneration?
    @State private var error: String?

    var body: some View {
        Form {
            if let error { Text(error).foregroundStyle(.red) }
            Section("Prompt wizard") {
                TextField("Describe your product", text: $prompt, axis: .vertical)
                Button("1. Analyze") {
                    Task {
                        switch await deps.productRepository.analyze(prompt: prompt) {
                        case .success(let a): analysis = a
                        case .failure(let e): error = e.message
                        }
                    }
                }
            }
            if let analysis {
                Section("Analysis") {
                    Text(analysis.suggestedName ?? "")
                    Text("\(analysis.industry ?? "") / \(analysis.category ?? "")")
                    Text(String(format: "confidence %.2f", analysis.confidence ?? 0))
                }
            }
            Section("Generate") {
                Button("2. Generate") {
                    Task {
                        switch await deps.productRepository.generate(prompt: prompt, templateSlug: analysis?.recommendedTemplateSlug) {
                        case .success(let g): generation = g
                        case .failure(let e): error = e.message
                        }
                    }
                }
            }
            if let generation {
                Section("Preview") {
                    Text("status=\(generation.status ?? "-")")
                    Text(generation.previewUrl ?? "No preview yet")
                    Button("3. Publish") {
                        Task {
                            switch await deps.productRepository.publish(id: generation.id) {
                            case .success(let g): self.generation = g
                            case .failure(let e): error = e.message
                            }
                        }
                    }
                }
            }
        }
        .navigationTitle("Product Generator")
    }
}
''')

w("ThtwaatStarter/Features/Domains/DomainsView.swift", r'''
import SwiftUI

struct DomainsView: View {
    @EnvironmentObject private var deps: AppDependencies
    @State private var domains: [DomainRecord] = []
    @State private var hostname = ""
    @State private var error: String?

    var body: some View {
        List {
            if let error { Text(error).foregroundStyle(.red) }
            Section("Add domain") {
                TextField("Hostname", text: $hostname)
                    .textInputAutocapitalization(.never)
                Button("Add") {
                    Task {
                        switch await deps.domainsRepository.create(hostname: hostname) {
                        case .success: await refresh()
                        case .failure(let e): error = e.message
                        }
                    }
                }
            }
            Section("Domains") {
                ForEach(domains) { d in
                    VStack(alignment: .leading, spacing: 6) {
                        Text(d.hostname).font(.headline)
                        Text("status=\(d.status ?? "-") ssl=\(d.sslStatus ?? "-")")
                        Text("token=\(d.verificationToken ?? "-")").font(.caption)
                        HStack {
                            Button("Verify") { Task { _ = await deps.domainsRepository.verify(id: d.id); await refresh() } }
                            Button("Retry") { Task { _ = await deps.domainsRepository.retry(id: d.id); await refresh() } }
                            Button("SSL") { Task { _ = await deps.domainsRepository.requestSSL(id: d.id); await refresh() } }
                        }
                        .buttonStyle(.bordered)
                    }
                }
            }
        }
        .navigationTitle("Domains")
        .task { await refresh() }
    }

    private func refresh() async {
        switch await deps.domainsRepository.list() {
        case .success(let list): domains = list
        case .failure(let e): error = e.message
        }
    }
}
''')

w("ThtwaatStarter/Features/Billing/BillingView.swift", r'''
import SwiftUI

struct BillingView: View {
    @EnvironmentObject private var deps: AppDependencies
    @State private var plans: [Plan] = []
    @State private var invoices: [Invoice] = []
    @State private var subscription: Subscription?
    @State private var usage: UsageSnapshot?
    @State private var error: String?

    var body: some View {
        List {
            if let error { Text(error).foregroundStyle(.red) }
            Section("Current plan") {
                Text("status=\(subscription?.status ?? "-")")
                Text("plan=\(subscription?.planId ?? "-")")
            }
            Section("Quota / usage") {
                Text("messages=\(usage?.aiMessages ?? 0)")
                Text("tokens=\(usage?.totalTokens ?? 0)")
                Text("storage=\(usage?.storageBytes ?? 0)")
                Text("max agents=\(usage?.maxAgents ?? 0)")
            }
            Section("Plans") {
                ForEach(plans) { p in
                    VStack(alignment: .leading) {
                        Text(p.name ?? p.code ?? "Plan").font(.headline)
                        Text("\(p.price ?? 0) \(p.currency ?? "") · max agents \(p.maxAgents ?? 0)")
                    }
                }
            }
            Section("Invoices") {
                ForEach(invoices) { inv in
                    Text("\(inv.invoiceNumber ?? inv.id) · \(inv.amount ?? 0) \(inv.currency ?? "") · \(inv.status ?? "")")
                }
            }
        }
        .navigationTitle("Billing")
        .task {
            async let p = deps.billingRepository.plans()
            async let i = deps.billingRepository.invoices()
            async let s = deps.billingRepository.subscription()
            async let u = deps.usageRepository.current()
            if case .success(let list) = await p { plans = list }
            if case .success(let list) = await i { invoices = list }
            if case .success(let sub) = await s { subscription = sub }
            if case .success(let snap) = await u { usage = snap }
            if case .failure(let e) = await p { error = e.message }
        }
    }
}
''')

w("ThtwaatStarter/Features/Settings/SettingsView.swift", r'''
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
''')

print("features done")
