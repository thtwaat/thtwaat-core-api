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
