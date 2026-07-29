import Foundation
import Security

protocol SessionStore: Sendable {
    func accessToken() async -> String?
    func refreshToken() async -> String?
    func apiKey() async -> String?
    func themeMode() async -> ThemeMode
    func hasAccessToken() async -> Bool
    func saveTokens(access: String, refresh: String) async
    func saveAPIKey(_ key: String) async
    func setThemeMode(_ mode: ThemeMode) async
    func clearSession() async
    func clearAll() async
}

actor KeychainSessionStore: SessionStore {
    private let accessKey = "com.thtwaat.starter.access"
    private let refreshKey = "com.thtwaat.starter.refresh"
    private let apiKeyKey = "com.thtwaat.starter.apikey"
    private let themeKey = "com.thtwaat.starter.theme"

    func accessToken() async -> String? { Keychain.read(accessKey) }
    func refreshToken() async -> String? { Keychain.read(refreshKey) }
    func apiKey() async -> String? { Keychain.read(apiKeyKey) }
    func themeMode() async -> ThemeMode {
        ThemeMode(rawValue: UserDefaults.standard.string(forKey: themeKey) ?? "") ?? .system
    }
    func hasAccessToken() async -> Bool { !(await accessToken() ?? "").isEmpty }

    func saveTokens(access: String, refresh: String) async {
        Keychain.write(accessKey, access)
        Keychain.write(refreshKey, refresh)
    }

    func saveAPIKey(_ key: String) async { Keychain.write(apiKeyKey, key) }

    func setThemeMode(_ mode: ThemeMode) async {
        UserDefaults.standard.set(mode.rawValue, forKey: themeKey)
    }

    func clearSession() async {
        Keychain.delete(accessKey)
        Keychain.delete(refreshKey)
    }

    func clearAll() async {
        await clearSession()
        Keychain.delete(apiKeyKey)
    }
}

enum Keychain {
    static func write(_ key: String, _ value: String) {
        let data = Data(value.utf8)
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key,
        ]
        SecItemDelete(query as CFDictionary)
        var attrs = query
        attrs[kSecValueData as String] = data
        attrs[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        SecItemAdd(attrs as CFDictionary, nil)
    }

    static func read(_ key: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        guard status == errSecSuccess, let data = item as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    static func delete(_ key: String) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key,
        ]
        SecItemDelete(query as CFDictionary)
    }
}
