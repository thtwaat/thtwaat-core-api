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
