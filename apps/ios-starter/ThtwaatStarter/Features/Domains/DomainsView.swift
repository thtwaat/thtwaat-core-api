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
