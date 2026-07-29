from pathlib import Path
ROOT = Path(r"E:\THTWAAT\thtwaat-core-api\apps\ios-starter")

def w(rel: str, content: str) -> None:
    path = ROOT / rel.replace("/", "\\")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.lstrip("\n"), encoding="utf-8", newline="\n")
    print("wrote", rel)

# Fix: public empty body + correct publish returns
w("ThtwaatStarter/Data/Models/EmptyJSON.swift", r'''
import Foundation

struct EmptyJSON: Codable, Sendable {}
''')

w("ThtwaatStarter/Data/Repositories/FeatureRepositories.swift", r'''
import Foundation

actor KnowledgeRepository {
    private let client: APIClient
    init(client: APIClient) { self.client = client }

    func listBases() async -> APIResult<[KnowledgeBase]> { await client.getList("/v2/knowledge/bases") }
    func createBase(name: String, description: String?) async -> APIResult<KnowledgeBase> {
        await client.post("/v2/knowledge/bases", body: KnowledgeBaseCreateRequest(name: name, description: description))
    }
    func search(query: String, kbId: String? = nil, topK: Int = 5) async -> APIResult<[SearchResultItem]> {
        await client.post("/v2/knowledge/search", body: KnowledgeSearchRequest(query: query, kbId: kbId, topK: topK))
    }
    func upload(data: Data, filename: String, kbId: String?) async -> APIResult<KnowledgeDocument> {
        await client.upload(path: "/v2/knowledge/upload", fileData: data, filename: filename, query: ["knowledge_base_id": kbId])
    }
    func deleteDocument(id: String) async -> APIResult<APIClient.EmptyResponse> {
        await client.delete("/v2/knowledge/documents/\(id)")
    }
}

actor AgentsRepository {
    private let client: APIClient
    private let cache: OfflineCacheStore
    init(client: APIClient, cache: OfflineCacheStore) {
        self.client = client
        self.cache = cache
    }

    func list() async -> APIResult<[Agent]> {
        let result: APIResult<[Agent]> = await client.getList("/v2/agents")
        if case .success(let items) = result {
            await cache.saveAgents(items)
            return result
        }
        let cached = await cache.loadAgents()
        return cached.isEmpty ? result : .success(cached)
    }

    func create(name: String, prompt: String, description: String?) async -> APIResult<Agent> {
        await client.post(
            "/v2/agents",
            body: AgentCreateRequest(name: name, systemPromptTemplate: prompt, description: description, temperature: 0.7, isTemplate: false)
        )
    }

    func publish(id: String) async -> APIResult<PublishResult> {
        await client.post("/api/v1/agents/\(id)/publish", body: EmptyJSON())
    }
    func unpublish(id: String) async -> APIResult<APIClient.EmptyResponse> {
        await client.post("/api/v1/agents/\(id)/unpublish", body: EmptyJSON())
    }
    func createKey(id: String, name: String = "Default") async -> APIResult<AgentAPIKey> {
        await client.post("/api/v1/agents/\(id)/api-keys", body: CreateAPIKeyRequest(name: name))
    }
    func listKeys(id: String) async -> APIResult<[AgentAPIKey]> { await client.getList("/api/v1/agents/\(id)/api-keys") }
}

actor MarketplaceRepository {
    private let client: APIClient
    init(client: APIClient) { self.client = client }

    func templates(q: String? = nil, category: String? = nil) async -> APIResult<[TemplateItem]> {
        await client.getList("/api/v1/marketplace/templates", query: ["q": q, "category": category, "limit": "50"])
    }
    func install(idOrSlug: String) async -> APIResult<Installation> {
        await client.post("/api/v1/marketplace/templates/\(idOrSlug)/install", body: InstallRequest(createApiKey: true, agentId: nil))
    }
    func installed() async -> APIResult<[Installation]> { await client.getList("/api/v1/marketplace/installed") }
    func updates() async -> APIResult<[UpdateNotification]> { await client.getList("/api/v1/marketplace/updates") }
    func connect(id: String, agentId: String? = nil) async -> APIResult<Installation> {
        await client.post("/api/v1/marketplace/installations/\(id)/connect", body: ConnectRequest(agentId: agentId, domainId: nil, createApiKey: true))
    }
    func publish(id: String) async -> APIResult<Installation> {
        await client.post("/api/v1/marketplace/installations/\(id)/publish", body: EmptyJSON())
    }
    func update(id: String) async -> APIResult<Installation> {
        await client.post("/api/v1/marketplace/installations/\(id)/update", body: EmptyJSON())
    }
    func rollback(id: String) async -> APIResult<Installation> {
        await client.post("/api/v1/marketplace/installations/\(id)/rollback", body: EmptyJSON())
    }
    func uninstall(id: String) async -> APIResult<APIClient.EmptyResponse> {
        await client.delete("/api/v1/marketplace/installations/\(id)")
    }
}

actor ProductGeneratorRepository {
    private let client: APIClient
    init(client: APIClient) { self.client = client }

    func analyze(prompt: String) async -> APIResult<ProductAnalysis> {
        await client.post("/api/v1/product-generator/analyze", body: ProductAnalyzeRequest(prompt: prompt))
    }
    func generate(prompt: String, templateSlug: String? = nil, autoPublish: Bool = false) async -> APIResult<ProductGeneration> {
        await client.post("/api/v1/product-generator/generate", body: ProductGenerateRequest(prompt: prompt, templateSlug: templateSlug, autoPublish: autoPublish))
    }
    func publish(id: String, hostname: String? = nil) async -> APIResult<ProductGeneration> {
        await client.post("/api/v1/product-generator/generations/\(id)/publish", body: ProductPublishRequest(hostname: hostname))
    }
    func list() async -> APIResult<[ProductGeneration]> { await client.getList("/api/v1/product-generator/generations") }
}

actor DomainsRepository {
    private let client: APIClient
    init(client: APIClient) { self.client = client }

    func list() async -> APIResult<[DomainRecord]> { await client.getList("/api/v1/domains/") }
    func create(hostname: String) async -> APIResult<DomainRecord> {
        await client.post("/api/v1/domains/", body: DomainCreateRequest(hostname: hostname, verificationMethod: "TXT", isPrimary: false))
    }
    func verify(id: String) async -> APIResult<DomainRecord> {
        await client.post("/api/v1/domains/\(id)/verify", body: EmptyJSON())
    }
    func retry(id: String) async -> APIResult<DomainRecord> {
        await client.post("/api/v1/domains/\(id)/retry", body: EmptyJSON())
    }
    func requestSSL(id: String) async -> APIResult<DomainRecord> {
        await client.post("/api/v1/domains/\(id)/ssl/request", body: EmptyJSON())
    }
}

actor UsageRepository {
    private let client: APIClient
    init(client: APIClient) { self.client = client }
    func current() async -> APIResult<UsageSnapshot> { await client.get("/api/v1/usage/current") }
}

actor BillingRepository {
    private let client: APIClient
    init(client: APIClient) { self.client = client }
    func plans() async -> APIResult<[Plan]> { await client.getList("/api/v1/payments/plans/") }
    func invoices() async -> APIResult<[Invoice]> { await client.getList("/api/v1/payments/invoices/") }
    func subscription() async -> APIResult<Subscription> { await client.get("/api/v1/payments/subscriptions/me") }
}

actor AnalyticsRepository {
    private let client: APIClient
    init(client: APIClient) { self.client = client }

    func overviewText() async -> APIResult<String> {
        // Analytics payload shape varies; surface raw JSON string for dashboard cards.
        let result: APIResult<UsageSnapshot> = await client.get("/api/v1/usage/dashboard")
        switch result {
        case .success(let snap):
            return .success("messages=\(snap.aiMessages ?? 0) tokens=\(snap.totalTokens ?? 0)")
        case .failure(let err):
            // Fallback attempt to overview endpoint as opaque success message
            let _: APIResult<APIClient.EmptyResponse> = await client.get("/api/v1/analytics/overview")
            return .failure(err)
        }
    }
}
''')

print("repos fixed")
