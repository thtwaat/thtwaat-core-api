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
