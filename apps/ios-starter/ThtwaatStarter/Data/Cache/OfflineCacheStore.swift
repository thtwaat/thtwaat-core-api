import Foundation

actor OfflineCacheStore {
    private let conversationsKey = "thtwaat.cache.conversations"
    private let agentsKey = "thtwaat.cache.agents"
    private let defaults = UserDefaults.standard
    private let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return d
    }()
    private let encoder: JSONEncoder = {
        let e = JSONEncoder()
        e.keyEncodingStrategy = .convertToSnakeCase
        return e
    }()

    func saveConversations(_ items: [Conversation]) {
        if let data = try? encoder.encode(items) {
            defaults.set(data, forKey: conversationsKey)
        }
    }

    func loadConversations() -> [Conversation] {
        guard let data = defaults.data(forKey: conversationsKey),
              let items = try? decoder.decode([Conversation].self, from: data) else { return [] }
        return items
    }

    func saveAgents(_ items: [Agent]) {
        if let data = try? encoder.encode(items) {
            defaults.set(data, forKey: agentsKey)
        }
    }

    func loadAgents() -> [Agent] {
        guard let data = defaults.data(forKey: agentsKey),
              let items = try? decoder.decode([Agent].self, from: data) else { return [] }
        return items
    }
}
