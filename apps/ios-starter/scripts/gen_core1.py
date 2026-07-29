from pathlib import Path

ROOT = Path(r"E:\THTWAAT\thtwaat-core-api\apps\ios-starter")

def w(rel: str, content: str) -> None:
    path = ROOT / rel.replace("/", "\\")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.lstrip("\n"), encoding="utf-8", newline="\n")
    print("wrote", rel)

# ========== App ==========
w("ThtwaatStarter/Info.plist", r'''
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>API_BASE_URL</key>
	<string>$(API_BASE_URL)</string>
	<key>CFBundleDevelopmentRegion</key>
	<string>$(DEVELOPMENT_LANGUAGE)</string>
	<key>CFBundleDisplayName</key>
	<string>THTWAAT</string>
	<key>CFBundleExecutable</key>
	<string>$(EXECUTABLE_NAME)</string>
	<key>CFBundleIdentifier</key>
	<string>$(PRODUCT_BUNDLE_IDENTIFIER)</string>
	<key>CFBundleInfoDictionaryVersion</key>
	<string>6.0</string>
	<key>CFBundleName</key>
	<string>$(PRODUCT_NAME)</string>
	<key>CFBundlePackageType</key>
	<string>APPL</string>
	<key>CFBundleShortVersionString</key>
	<string>$(MARKETING_VERSION)</string>
	<key>CFBundleVersion</key>
	<string>$(CURRENT_PROJECT_VERSION)</string>
	<key>LSRequiresIPhoneOS</key>
	<true/>
	<key>NSAppTransportSecurity</key>
	<dict>
		<key>NSAllowsArbitraryLoads</key>
		<true/>
	</dict>
	<key>UIApplicationSceneManifest</key>
	<dict>
		<key>UIApplicationSupportsMultipleScenes</key>
		<false/>
	</dict>
	<key>UILaunchScreen</key>
	<dict/>
	<key>UISupportedInterfaceOrientations</key>
	<array>
		<string>UIInterfaceOrientationPortrait</string>
		<string>UIInterfaceOrientationLandscapeLeft</string>
		<string>UIInterfaceOrientationLandscapeRight</string>
	</array>
</dict>
</plist>
''')

w("ThtwaatStarter/App/ThtwaatStarterApp.swift", r'''
import SwiftUI

@main
struct ThtwaatStarterApp: App {
    @StateObject private var appState = AppState()
    @StateObject private var dependencies = AppDependencies()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(appState)
                .environmentObject(dependencies)
                .preferredColorScheme(appState.colorScheme)
                .task {
                    await dependencies.bootstrap()
                    appState.isAuthenticated = await dependencies.sessionStore.hasAccessToken()
                    appState.themeMode = await dependencies.sessionStore.themeMode()
                }
        }
    }
}
''')

w("ThtwaatStarter/App/AppState.swift", r'''
import SwiftUI
import Combine

@MainActor
final class AppState: ObservableObject {
    @Published var isAuthenticated = false
    @Published var themeMode: ThemeMode = .system

    var colorScheme: ColorScheme? {
        switch themeMode {
        case .system: return nil
        case .light: return .light
        case .dark: return .dark
        }
    }
}

enum ThemeMode: String, CaseIterable, Codable {
    case system, light, dark
}
''')

w("ThtwaatStarter/Core/DI/AppDependencies.swift", r'''
import Foundation
import Combine

@MainActor
final class AppDependencies: ObservableObject {
    let sessionStore: SessionStore
    let apiClient: APIClient
    let sseClient: SSEClient

    let authRepository: AuthRepository
    let chatRepository: ChatRepository
    let knowledgeRepository: KnowledgeRepository
    let agentsRepository: AgentsRepository
    let marketplaceRepository: MarketplaceRepository
    let productRepository: ProductGeneratorRepository
    let domainsRepository: DomainsRepository
    let usageRepository: UsageRepository
    let billingRepository: BillingRepository
    let analyticsRepository: AnalyticsRepository
    let cacheStore: OfflineCacheStore

    init(baseURL: URL = AppConfig.apiBaseURL) {
        let sessionStore = KeychainSessionStore()
        self.sessionStore = sessionStore
        let client = APIClient(baseURL: baseURL, sessionStore: sessionStore)
        self.apiClient = client
        self.sseClient = SSEClient(baseURL: baseURL, sessionStore: sessionStore)
        self.cacheStore = OfflineCacheStore()
        self.authRepository = AuthRepository(client: client, sessionStore: sessionStore)
        self.chatRepository = ChatRepository(client: client, sse: sseClient, sessionStore: sessionStore, cache: cacheStore)
        self.knowledgeRepository = KnowledgeRepository(client: client)
        self.agentsRepository = AgentsRepository(client: client, cache: cacheStore)
        self.marketplaceRepository = MarketplaceRepository(client: client)
        self.productRepository = ProductGeneratorRepository(client: client)
        self.domainsRepository = DomainsRepository(client: client)
        self.usageRepository = UsageRepository(client: client)
        self.billingRepository = BillingRepository(client: client)
        self.analyticsRepository = AnalyticsRepository(client: client)
        client.onUnauthorizedRefresh = { [weak self] in
            guard let self else { return false }
            return await self.authRepository.refreshIfPossible()
        }
    }

    func bootstrap() async {
        // Reserved for future warm-up (cache hydrate, etc.)
    }
}
''')

w("ThtwaatStarter/Core/Util/AppConfig.swift", r'''
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
''')

w("ThtwaatStarter/Core/Util/APIResult.swift", r'''
import Foundation

enum APIResult<T: Sendable>: Sendable {
    case success(T)
    case failure(APIError)
}

struct APIError: Error, LocalizedError, Sendable {
    let message: String
    let status: Int?
    let code: String?

    var errorDescription: String? { message }

    static func http(status: Int, body: Data?) -> APIError {
        var message = "HTTP \(status)"
        if let body, let obj = try? JSONSerialization.jsonObject(with: body) as? [String: Any] {
            if let detail = obj["detail"] as? String { message = detail }
            else if let msg = obj["message"] as? String { message = msg }
        }
        let code: String
        switch status {
        case 400, 422: code = "validation_error"
        case 401: code = "unauthorized"
        case 403: code = "forbidden"
        case 404: code = "not_found"
        case 429: code = "rate_limited"
        default: code = status >= 500 ? "server_error" : "http_error"
        }
        return APIError(message: message, status: status, code: code)
    }
}
''')

w("ThtwaatStarter/Core/Storage/SessionStore.swift", r'''
import Foundation
import Security

protocol SessionStore: AnyObject, Sendable {
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
''')

print("core1 done")
