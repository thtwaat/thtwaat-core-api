import SwiftUI
import UniformTypeIdentifiers

struct KnowledgeView: View {
    @EnvironmentObject private var deps: AppDependencies
    @State private var bases: [KnowledgeBase] = []
    @State private var results: [SearchResultItem] = []
    @State private var name = ""
    @State private var query = ""
    @State private var selectedBaseId: String?
    @State private var error: String?
    @State private var info: String?
    @State private var importing = false

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
            Section("Upload") {
                Picker("Base", selection: $selectedBaseId) {
                    Text("None").tag(Optional<String>.none)
                    ForEach(bases) { b in
                        Text(b.name).tag(Optional(b.id))
                    }
                }
                Button("Upload file") { importing = true }
            }
            Section("Search") {
                TextField("Query", text: $query)
                Button("Search") {
                    Task {
                        switch await deps.knowledgeRepository.search(query: query, kbId: selectedBaseId) {
                        case .success(let items): results = items
                        case .failure(let e): error = e.message
                        }
                    }
                }
            }
            Section("Bases") {
                ForEach(bases) { b in
                    Button {
                        selectedBaseId = b.id
                    } label: {
                        VStack(alignment: .leading) {
                            Text(b.name).font(.headline)
                            Text(b.description ?? b.id).font(.caption).foregroundStyle(.secondary)
                        }
                    }
                }
            }
            Section("Results") {
                ForEach(results) { r in
                    VStack(alignment: .leading) {
                        Text(String(format: "score %.3f", r.score ?? 0))
                        Text(r.body)
                        if let doc = r.documentId {
                            Button("Delete document", role: .destructive) {
                                Task {
                                    switch await deps.knowledgeRepository.deleteDocument(id: doc) {
                                    case .success: info = "Deleted \(doc)"; results.removeAll { $0.documentId == doc }
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
        .fileImporter(
            isPresented: $importing,
            allowedContentTypes: [.plainText, .pdf, .data, UTType(filenameExtension: "docx") ?? .data],
            allowsMultipleSelection: false
        ) { result in
            switch result {
            case .success(let urls):
                guard let url = urls.first else { return }
                Task { await upload(url: url) }
            case .failure(let e):
                error = e.localizedDescription
            }
        }
    }

    private func refresh() async {
        if case .success(let list) = await deps.knowledgeRepository.listBases() {
            bases = list
            if selectedBaseId == nil { selectedBaseId = list.first?.id }
        }
    }

    private func upload(url: URL) async {
        let access = url.startAccessingSecurityScopedResource()
        defer { if access { url.stopAccessingSecurityScopedResource() } }
        do {
            let data = try Data(contentsOf: url)
            switch await deps.knowledgeRepository.upload(data: data, filename: url.lastPathComponent, kbId: selectedBaseId) {
            case .success(let doc): info = "Uploaded \(doc.name ?? doc.id)"
            case .failure(let e): error = e.message
            }
        } catch {
            self.error = error.localizedDescription
        }
    }
}
