from pathlib import Path
ROOT = Path(r"E:\THTWAAT\thtwaat-core-api\apps\ios-starter")

def w(rel: str, content: str) -> None:
    path = ROOT / rel.replace("/", "\\")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.lstrip("\n"), encoding="utf-8", newline="\n")
    print("wrote", rel)

w("ThtwaatStarter/Data/Models/Models.swift", r'''
import Foundation

struct LoginRequest: Encodable, Sendable {
    let email: String
    let password: String
}

struct RefreshRequest: Encodable, Sendable {
    let refreshToken: String
}

struct LogoutRequest: Encodable, Sendable {
    let refreshToken: String
}

struct ForgotPasswordRequest: Encodable, Sendable {
    let email: String
}

struct ResetPasswordRequest: Encodable, Sendable {
    let email: String
    let code: String
    let newPassword: String
}

struct SignupRequest: Encodable, Sendable {
    let email: String
    let password: String
    let firstName: String
    let lastName: String
    let companyId: String?
}

struct TokenResponse: Decodable, Sendable {
    let accessToken: String
    let refreshToken: String
    let tokenType: String?
    let expiresIn: Int?
}

struct UserProfile: Decodable, Sendable, Identifiable {
    let id: String
    let companyId: String?
    let email: String?
    let firstName: String?
    let lastName: String?
    let role: String?
}

struct ChatRequest: Encodable, Sendable {
    let message: String
    let sessionId: String?
    let apiKey: String?
}

struct ChatResponse: Decodable, Sendable {
    let reply: String?
    let response: String?
    let conversationId: String?
    let messageId: String?
    let suggestedPrompts: [String]?
    var text: String { reply ?? response ?? "" }
}

struct ConversationMessage: Decodable, Sendable, Identifiable {
    var id: String { _id ?? UUID().uuidString }
    let _id: String?
    let role: String
    let content: String
    let createdAt: String?

    enum CodingKeys: String, CodingKey {
        case _id = "id"
        case role, content, createdAt
    }
}

struct Conversation: Decodable, Sendable, Identifiable {
    let id: String
    let messages: [ConversationMessage]?
    let createdAt: String?
    let updatedAt: String?
}

struct AgentCreateRequest: Encodable, Sendable {
    let name: String
    let systemPromptTemplate: String
    let description: String?
    let temperature: Double
    let isTemplate: Bool
}

struct Agent: Decodable, Sendable, Identifiable {
    let id: String
    let name: String
    let companyId: String?
    let description: String?
    let systemPromptTemplate: String?
    let temperature: Double?
    let status: String?
    let version: Int?
    let isTemplate: Bool?
    let widgetId: String?
    let publishedAt: String?
}

struct PublishResult: Decodable, Sendable {
    let status: String?
    let agentId: String?
    let apiKey: String?
    let widgetId: String?
    let publicChatUrl: String?
    let embedScript: String?
}

struct AgentAPIKey: Decodable, Sendable, Identifiable {
    var id: String { _id ?? UUID().uuidString }
    let _id: String?
    let name: String?
    let keyPrefix: String?
    let apiKeyPrefix: String?
    let apiKey: String?
    let key: String?
    let plainKey: String?
    let message: String?

    enum CodingKeys: String, CodingKey {
        case _id = "id"
        case name, keyPrefix, apiKeyPrefix, apiKey, key, plainKey, message
    }

    var displayKey: String { apiKey ?? plainKey ?? key ?? keyPrefix ?? apiKeyPrefix ?? "-" }
}

struct CreateAPIKeyRequest: Encodable, Sendable { let name: String }

struct KnowledgeBaseCreateRequest: Encodable, Sendable {
    let name: String
    let description: String?
}

struct KnowledgeBase: Decodable, Sendable, Identifiable {
    let id: String
    let name: String
    let companyId: String?
    let description: String?
}

struct KnowledgeSearchRequest: Encodable, Sendable {
    let query: String
    let kbId: String?
    let topK: Int
}

struct SearchResultItem: Decodable, Sendable, Identifiable {
    var id: String { chunkId ?? documentId ?? UUID().uuidString }
    let chunkId: String?
    let documentId: String?
    let text: String?
    let content: String?
    let score: Double?
    var body: String { text ?? content ?? "" }
}

struct KnowledgeDocument: Decodable, Sendable, Identifiable {
    let id: String
    let knowledgeBaseId: String?
    let name: String?
    let status: String?
}

struct TemplateItem: Decodable, Sendable, Identifiable {
    let id: String
    let slug: String
    let name: String
    let category: String?
    let description: String?
    let version: String?
    let tags: [String]?
    let isFeatured: Bool?
    let installed: Bool?
    let updateAvailable: Bool?
}

struct Installation: Decodable, Sendable, Identifiable {
    let id: String
    let templateId: String
    let templateSlug: String?
    let templateName: String?
    let installedVersion: String?
    let status: String?
    let agentId: String?
    let apiKey: String?
    let domainId: String?
    let updateAvailable: Bool?
}

struct InstallRequest: Encodable, Sendable {
    let createApiKey: Bool
    let agentId: String?
}

struct ConnectRequest: Encodable, Sendable {
    let agentId: String?
    let domainId: String?
    let createApiKey: Bool
}

struct UpdateNotification: Decodable, Sendable, Identifiable {
    var id: String { installationId }
    let installationId: String
    let templateId: String
    let templateSlug: String?
    let templateName: String?
    let installedVersion: String?
    let latestVersion: String?
    let changelog: String?
}

struct ProductAnalyzeRequest: Encodable, Sendable { let prompt: String }

struct ProductAnalysis: Decodable, Sendable {
    let industry: String?
    let productType: String?
    let category: String?
    let requiredFeatures: [String]?
    let brandTone: String?
    let language: String?
    let suggestedName: String?
    let confidence: Double?
    let recommendedTemplateSlug: String?
}

struct ProductGenerateRequest: Encodable, Sendable {
    let prompt: String
    let templateSlug: String?
    let autoPublish: Bool
}

struct ProductGeneration: Decodable, Sendable, Identifiable {
    let id: String
    let companyId: String?
    let prompt: String?
    let status: String?
    let templateSlug: String?
    let previewUrl: String?
    let widgetSnippet: String?
    let publishStatus: String?
    let failureReason: String?
}

struct ProductPublishRequest: Encodable, Sendable { let hostname: String? }

struct DomainCreateRequest: Encodable, Sendable {
    let hostname: String
    let verificationMethod: String
    let isPrimary: Bool
}

struct DomainRecord: Decodable, Sendable, Identifiable {
    let id: String
    let hostname: String
    let status: String?
    let sslStatus: String?
    let verificationToken: String?
    let agentId: String?
}

struct UsageSnapshot: Decodable, Sendable {
    let aiMessages: Int?
    let totalTokens: Int?
    let storageBytes: Int64?
    let templatesPublished: Int?
    let maxTemplates: Int?
    let maxAgents: Int?
}

struct Plan: Decodable, Sendable, Identifiable {
    var id: String { _id ?? code ?? name ?? UUID().uuidString }
    let _id: String?
    let name: String?
    let code: String?
    let price: Double?
    let currency: String?
    let maxAgents: Int?

    enum CodingKeys: String, CodingKey {
        case _id = "id"
        case name, code, price, currency, maxAgents
    }
}

struct Invoice: Decodable, Sendable, Identifiable {
    var id: String { _id ?? invoiceNumber ?? UUID().uuidString }
    let _id: String?
    let invoiceNumber: String?
    let status: String?
    let amount: Double?
    let currency: String?

    enum CodingKeys: String, CodingKey {
        case _id = "id"
        case invoiceNumber, status, amount, currency
    }
}

struct Subscription: Decodable, Sendable {
    let id: String?
    let status: String?
    let provider: String?
    let planId: String?
}

struct JSONValue: Decodable, Sendable {
    // Opaque analytics/dashboard payloads
}
''')

w("ThtwaatStarter/Data/Repositories/AuthRepository.swift", r'''
import Foundation

actor AuthRepository {
    private let client: APIClient
    private let sessionStore: any SessionStore

    init(client: APIClient, sessionStore: any SessionStore) {
        self.client = client
        self.sessionStore = sessionStore
    }

    func login(email: String, password: String) async -> APIResult<TokenResponse> {
        let result: APIResult<TokenResponse> = await client.post(
            "/api/v1/auth/login",
            body: LoginRequest(email: email, password: password),
            auth: false
        )
        if case .success(let tokens) = result {
            await sessionStore.saveTokens(access: tokens.accessToken, refresh: tokens.refreshToken)
        }
        return result
    }

    func signup(email: String, password: String, first: String, last: String) async -> APIResult<UserProfile> {
        await client.post(
            "/api/v1/users/",
            body: SignupRequest(email: email, password: password, firstName: first, lastName: last, companyId: nil),
            auth: false
        )
    }

    func forgotPassword(email: String) async -> APIResult<APIClient.EmptyResponse> {
        await client.post("/api/v1/auth/forgot-password", body: ForgotPasswordRequest(email: email), auth: false)
    }

    func me() async -> APIResult<UserProfile> {
        await client.get("/api/v1/auth/me")
    }

    func logout() async -> APIResult<APIClient.EmptyResponse> {
        let refresh = await sessionStore.refreshToken() ?? ""
        let result: APIResult<APIClient.EmptyResponse> = await client.post(
            "/api/v1/auth/logout",
            body: LogoutRequest(refreshToken: refresh)
        )
        await sessionStore.clearSession()
        return result
    }

    @discardableResult
    func refreshIfPossible() async -> Bool {
        guard let refresh = await sessionStore.refreshToken(), !refresh.isEmpty else { return false }
        let result: APIResult<TokenResponse> = await client.post(
            "/api/v1/auth/refresh",
            body: RefreshRequest(refreshToken: refresh),
            auth: false
        )
        if case .success(let tokens) = result {
            await sessionStore.saveTokens(access: tokens.accessToken, refresh: tokens.refreshToken)
            return true
        }
        await sessionStore.clearSession()
        return false
    }
}
''')

w("ThtwaatStarter/Data/Repositories/ChatRepository.swift", r'''
import Foundation

struct StreamToken: Sendable {
    let event: String
    let text: String?
}

actor ChatRepository {
    private let client: APIClient
    private let sse: SSEClient
    private let sessionStore: any SessionStore
    private let cache: OfflineCacheStore

    init(client: APIClient, sse: SSEClient, sessionStore: any SessionStore, cache: OfflineCacheStore) {
        self.client = client
        self.sse = sse
        self.sessionStore = sessionStore
        self.cache = cache
    }

    func chat(message: String, sessionId: String?) async -> APIResult<ChatResponse> {
        let apiKey = await sessionStore.apiKey()
        return await client.post(
            "/public/v1/chat",
            body: ChatRequest(message: message, sessionId: sessionId, apiKey: apiKey)
        )
    }

    func stream(message: String, sessionId: String?) async throws -> AsyncThrowingStream<StreamToken, Error> {
        let apiKey = await sessionStore.apiKey()
        let body = ChatRequest(message: message, sessionId: sessionId, apiKey: apiKey)
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        let data = try encoder.encode(body)
        let upstream = await sse.streamPost(path: "/public/v1/chat/stream", jsonBody: data)
        return AsyncThrowingStream { continuation in
            Task {
                do {
                    for try await ev in upstream {
                        continuation.yield(StreamToken(event: ev.event, text: ev.text))
                    }
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
        }
    }

    func history(limit: Int = 20) async -> APIResult<[Conversation]> {
        let result: APIResult<[Conversation]> = await client.getList("/v2/conversations", query: ["limit": "\(limit)"])
        if case .success(let items) = result {
            await cache.saveConversations(items)
            return result
        }
        let cached = await cache.loadConversations()
        return cached.isEmpty ? result : .success(cached)
    }
}
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

    func publish(id: String) async -> APIResult<PublishResult> { await client.postEmpty("/api/v1/agents/\(id)/publish").mapPublish() }
    func unpublish(id: String) async -> APIResult<APIClient.EmptyResponse> { await client.postEmpty("/api/v1/agents/\(id)/unpublish") }
    func widget(id: String) async -> APIResult<[String: String]> {
        // Widget config returned as JSON object; decode loosely via Data path
        await client.get("/api/v1/agents/\(id)/widget")
    }
    func createKey(id: String, name: String = "Default") async -> APIResult<AgentAPIKey> {
        await client.post("/api/v1/agents/\(id)/api-keys", body: CreateAPIKeyRequest(name: name))
    }
    func listKeys(id: String) async -> APIResult<[AgentAPIKey]> { await client.getList("/api/v1/agents/\(id)/api-keys") }
}

private extension APIResult where T == APIClient.EmptyResponse {
    func mapPublish() -> APIResult<PublishResult> {
        switch self {
        case .success:
            return .success(PublishResult(status: "published", agentId: nil, apiKey: nil, widgetId: nil, publicChatUrl: nil, embedScript: nil))
        case .failure(let e):
            return .failure(e)
        }
    }
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
    func publish(id: String) async -> APIResult<Installation> { await client.postEmpty("/api/v1/marketplace/installations/\(id)/publish").mapInstall(id: id) }
    func update(id: String) async -> APIResult<Installation> { await client.postEmpty("/api/v1/marketplace/installations/\(id)/update").mapInstall(id: id) }
    func rollback(id: String) async -> APIResult<Installation> { await client.postEmpty("/api/v1/marketplace/installations/\(id)/rollback").mapInstall(id: id) }
    func uninstall(id: String) async -> APIResult<APIClient.EmptyResponse> { await client.delete("/api/v1/marketplace/installations/\(id)") }
}

private extension APIResult where T == APIClient.EmptyResponse {
    func mapInstall(id: String) -> APIResult<Installation> {
        switch self {
        case .success:
            return .success(Installation(id: id, templateId: "", templateSlug: nil, templateName: nil, installedVersion: nil, status: "ok", agentId: nil, apiKey: nil, domainId: nil, updateAvailable: nil))
        case .failure(let e):
            return .failure(e)
        }
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
    func verify(id: String) async -> APIResult<DomainRecord> { await client.postEmpty("/api/v1/domains/\(id)/verify").mapDomain(id: id) }
    func retry(id: String) async -> APIResult<DomainRecord> { await client.postEmpty("/api/v1/domains/\(id)/retry").mapDomain(id: id) }
    func requestSSL(id: String) async -> APIResult<DomainRecord> { await client.postEmpty("/api/v1/domains/\(id)/ssl/request").mapDomain(id: id) }
}

private extension APIResult where T == APIClient.EmptyResponse {
    func mapDomain(id: String) -> APIResult<DomainRecord> {
        switch self {
        case .success:
            return .success(DomainRecord(id: id, hostname: "", status: "ok", sslStatus: nil, verificationToken: nil, agentId: nil))
        case .failure(let e):
            return .failure(e)
        }
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
    func overview() async -> APIResult<[String: String]> { await client.get("/api/v1/analytics/overview") }
}
''')

print("models+repos done")
