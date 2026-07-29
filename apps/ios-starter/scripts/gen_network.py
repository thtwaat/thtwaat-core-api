from pathlib import Path
ROOT = Path(r"E:\THTWAAT\thtwaat-core-api\apps\ios-starter")

def w(rel: str, content: str) -> None:
    path = ROOT / rel.replace("/", "\\")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.lstrip("\n"), encoding="utf-8", newline="\n")
    print("wrote", rel)

w("ThtwaatStarter/Core/Network/APIClient.swift", r'''
import Foundation

actor APIClient {
    private let baseURL: URL
    private let session: URLSession
    private let sessionStore: any SessionStore
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder
    var onUnauthorizedRefresh: (@Sendable () async -> Bool)?

    init(baseURL: URL, sessionStore: any SessionStore, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.sessionStore = sessionStore
        self.session = session
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        self.decoder = decoder
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        self.encoder = encoder
    }

    func get<T: Decodable>(_ path: String, query: [String: String?] = [:], auth: Bool = true) async -> APIResult<T> {
        await request(method: "GET", path: path, query: query, body: Optional<EmptyBody>.none, auth: auth)
    }

    func getList<T: Decodable>(_ path: String, query: [String: String?] = [:], auth: Bool = true) async -> APIResult<[T]> {
        await request(method: "GET", path: path, query: query, body: Optional<EmptyBody>.none, auth: auth)
    }

    func post<T: Decodable, B: Encodable>(_ path: String, body: B, query: [String: String?] = [:], auth: Bool = true) async -> APIResult<T> {
        await request(method: "POST", path: path, query: query, body: body, auth: auth)
    }

    func postEmpty(_ path: String, auth: Bool = true) async -> APIResult<EmptyResponse> {
        await request(method: "POST", path: path, query: [:], body: EmptyBody(), auth: auth)
    }

    func patch<T: Decodable, B: Encodable>(_ path: String, body: B, auth: Bool = true) async -> APIResult<T> {
        await request(method: "PATCH", path: path, query: [:], body: body, auth: auth)
    }

    func delete(_ path: String, auth: Bool = true) async -> APIResult<EmptyResponse> {
        await request(method: "DELETE", path: path, query: [:], body: Optional<EmptyBody>.none, auth: auth)
    }

    func upload(path: String, fileData: Data, filename: String, mime: String = "application/octet-stream", query: [String: String?] = [:]) async -> APIResult<KnowledgeDocument> {
        do {
            var comps = URLComponents(url: baseURL.appendingPathComponent(trim(path)), resolvingAgainstBaseURL: false)!
            let items = query.compactMap { k, v -> URLQueryItem? in
                guard let v else { return nil }
                return URLQueryItem(name: k, value: v)
            }
            if !items.isEmpty { comps.queryItems = items }
            var request = URLRequest(url: comps.url!)
            request.httpMethod = "POST"
            let boundary = "Boundary-\(UUID().uuidString)"
            request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
            await applyAuth(&request)
            var data = Data()
            data.append("--\(boundary)\r\n".data(using: .utf8)!)
            data.append("Content-Disposition: form-data; name=\"file\"; filename=\"\(filename)\"\r\n".data(using: .utf8)!)
            data.append("Content-Type: \(mime)\r\n\r\n".data(using: .utf8)!)
            data.append(fileData)
            data.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)
            request.httpBody = data
            let (respData, response) = try await session.data(for: request)
            return try decode(KnowledgeDocument.self, data: respData, response: response)
        } catch let err as APIError {
            return .failure(err)
        } catch {
            return .failure(APIError(message: error.localizedDescription, status: nil, code: "network_error"))
        }
    }

    private struct EmptyBody: Encodable {}
    struct EmptyResponse: Decodable {}

    private func request<T: Decodable, B: Encodable>(
        method: String,
        path: String,
        query: [String: String?],
        body: B?,
        auth: Bool,
        allowRefresh: Bool = true
    ) async -> APIResult<T> {
        do {
            var comps = URLComponents(url: baseURL.appendingPathComponent(trim(path)), resolvingAgainstBaseURL: false)!
            let items = query.compactMap { k, v -> URLQueryItem? in
                guard let v else { return nil }
                return URLQueryItem(name: k, value: v)
            }
            if !items.isEmpty { comps.queryItems = items }
            var request = URLRequest(url: comps.url!)
            request.httpMethod = method
            request.setValue("application/json", forHTTPHeaderField: "Accept")
            if body != nil {
                request.setValue("application/json", forHTTPHeaderField: "Content-Type")
                request.httpBody = try encoder.encode(body)
            }
            if auth { await applyAuth(&request) }
            let (data, response) = try await session.data(for: request)
            if let http = response as? HTTPURLResponse, http.statusCode == 401, allowRefresh, let refresh = onUnauthorizedRefresh {
                if await refresh() {
                    return await self.request(method: method, path: path, query: query, body: body, auth: auth, allowRefresh: false)
                }
            }
            return try decode(T.self, data: data, response: response)
        } catch let err as APIError {
            return .failure(err)
        } catch {
            return .failure(APIError(message: error.localizedDescription, status: nil, code: "network_error"))
        }
    }

    private func applyAuth(_ request: inout URLRequest) async {
        let access = await sessionStore.accessToken()
        let apiKey = await sessionStore.apiKey()
        let bearer = access ?? apiKey
        if let bearer, !bearer.isEmpty {
            request.setValue("Bearer \(bearer)", forHTTPHeaderField: "Authorization")
        }
        if let apiKey, !apiKey.isEmpty {
            request.setValue(apiKey, forHTTPHeaderField: "X-API-Key")
        }
    }

    private func decode<T: Decodable>(_ type: T.Type, data: Data, response: URLResponse) throws -> APIResult<T> {
        guard let http = response as? HTTPURLResponse else {
            throw APIError(message: "Invalid response", status: nil, code: "network_error")
        }
        guard (200..<300).contains(http.statusCode) else {
            throw APIError.http(status: http.statusCode, body: data)
        }
        if data.isEmpty, T.self == EmptyResponse.self {
            return .success(EmptyResponse() as! T)
        }
        do {
            return .success(try decoder.decode(T.self, from: data))
        } catch {
            // Some list endpoints return bare arrays; already handled by type.
            throw APIError(message: "Decode failed: \(error.localizedDescription)", status: http.statusCode, code: "decode_error")
        }
    }

    private func trim(_ path: String) -> String {
        path.hasPrefix("/") ? String(path.dropFirst()) : path
    }
}
''')

w("ThtwaatStarter/Core/Network/SSEClient.swift", r'''
import Foundation

struct SSEEvent: Sendable {
    let event: String
    let data: String

    var text: String? {
        guard let data = data.data(using: .utf8),
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return data.isEmpty ? nil : data
        }
        return (obj["text"] as? String) ?? (obj["reply"] as? String) ?? (obj["token"] as? String)
    }
}

actor SSEClient {
    private let baseURL: URL
    private let sessionStore: any SessionStore
    private let session: URLSession

    init(baseURL: URL, sessionStore: any SessionStore, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.sessionStore = sessionStore
        self.session = session
    }

    func streamPost(path: String, jsonBody: Data) -> AsyncThrowingStream<SSEEvent, Error> {
        AsyncThrowingStream { continuation in
            let task = Task {
                do {
                    var request = URLRequest(url: baseURL.appendingPathComponent(path.hasPrefix("/") ? String(path.dropFirst()) : path))
                    request.httpMethod = "POST"
                    request.setValue("text/event-stream", forHTTPHeaderField: "Accept")
                    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
                    request.httpBody = jsonBody
                    let access = await sessionStore.accessToken()
                    let apiKey = await sessionStore.apiKey()
                    let bearer = access ?? apiKey
                    if let bearer, !bearer.isEmpty {
                        request.setValue("Bearer \(bearer)", forHTTPHeaderField: "Authorization")
                    }
                    if let apiKey, !apiKey.isEmpty {
                        request.setValue(apiKey, forHTTPHeaderField: "X-API-Key")
                    }

                    let (bytes, response) = try await session.bytes(for: request)
                    if let http = response as? HTTPURLResponse, !(200..<300).contains(http.statusCode) {
                        throw APIError(message: "SSE failed: \(http.statusCode)", status: http.statusCode, code: "http_error")
                    }

                    var event = "message"
                    var dataBuf = ""
                    for try await line in bytes.lines {
                        if Task.isCancelled { break }
                        if line.isEmpty {
                            if !dataBuf.isEmpty {
                                continuation.yield(SSEEvent(event: event, data: dataBuf))
                                dataBuf = ""
                                event = "message"
                            }
                            continue
                        }
                        if line.hasPrefix(":") { continue }
                        if line.hasPrefix("event:") {
                            event = line.dropFirst(6).trimmingCharacters(in: .whitespaces)
                        } else if line.hasPrefix("data:") {
                            let chunk = line.dropFirst(5).trimmingCharacters(in: .whitespaces)
                            if !dataBuf.isEmpty { dataBuf += "\n" }
                            dataBuf += chunk
                        }
                    }
                    if !dataBuf.isEmpty {
                        continuation.yield(SSEEvent(event: event, data: dataBuf))
                    }
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
            continuation.onTermination = { _ in task.cancel() }
        }
    }
}
''')

w("ThtwaatStarter/Data/Cache/OfflineCacheStore.swift", r'''
import Foundation

actor OfflineCacheStore {
    private var conversations: [Conversation] = []
    private var agents: [Agent] = []

    func saveConversations(_ items: [Conversation]) {
        conversations = items
    }

    func loadConversations() -> [Conversation] { conversations }

    func saveAgents(_ items: [Agent]) { agents = items }
    func loadAgents() -> [Agent] { agents }
}
''')

print("network done")
