import Foundation

enum AppConfig {
    static var apiBaseURL: URL {
        if let env = ProcessInfo.processInfo.environment["API_BASE_URL"], let url = URL(string: env) {
            return url
        }
        if let raw = Bundle.main.object(forInfoDictionaryKey: "API_BASE_URL") as? String,
           let url = URL(string: raw.replacingOccurrences(of: "\\/", with: "/")) {
            return url
        }
        return URL(string: "http://127.0.0.1:8000")!
    }
}
