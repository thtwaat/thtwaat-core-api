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

struct ConversationMessage: Codable, Sendable, Identifiable {
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

struct Conversation: Codable, Sendable, Identifiable {
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

struct Agent: Codable, Sendable, Identifiable {
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

struct WidgetConfigPayload: Decodable, Sendable {
    let theme: String?
    let primaryColor: String?
    let welcomeMessage: String?
    let agentName: String?
    let position: String?
}

struct WidgetConfigResponse: Decodable, Sendable {
    let agentId: String?
    let widgetId: String?
    let status: String?
    let config: WidgetConfigPayload?
}

struct EmbedSnippetResponse: Decodable, Sendable {
    let agentId: String?
    let widgetId: String?
    let status: String?
    let script: String?
    let iframe: String?
    let previewUrl: String?
}

struct WidgetConfigUpdateRequest: Encodable, Sendable {
    let theme: String?
    let primaryColor: String?
    let welcomeMessage: String?
    let agentName: String?
}

