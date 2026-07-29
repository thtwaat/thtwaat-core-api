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
