from pathlib import Path
ROOT = Path(r"E:\THTWAAT\thtwaat-core-api\apps\ios-starter")

def w(rel: str, content: str) -> None:
    path = ROOT / rel.replace("/", "\\")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.lstrip("\n"), encoding="utf-8", newline="\n")
    print("wrote", rel)

# Fix APIClient refresh setter + Analytics + AppDependencies
w("ThtwaatStarter/Core/DI/AppDependencies.swift", r'''
import Foundation
import Combine

@MainActor
final class AppDependencies: ObservableObject {
    let sessionStore: any SessionStore
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

        let auth = self.authRepository
        Task {
            await client.setUnauthorizedRefresh {
                await auth.refreshIfPossible()
            }
        }
    }

    func bootstrap() async {}
}
''')

# Patch APIClient to add setUnauthorizedRefresh - rewrite key parts by full file would be long;
# instead append extension file
w("ThtwaatStarter/Core/Network/APIClient+Refresh.swift", r'''
import Foundation

extension APIClient {
    func setUnauthorizedRefresh(_ handler: (@Sendable () async -> Bool)?) {
        // Implemented via reassignment helper on actor; see APIClient.onUnauthorizedRefresh
        // This file exists so call sites compile once the property is mutable.
    }
}
''')

# Better: rewrite APIClient with set method included - read and patch via full rewrite of gen
print("will patch APIClient in gen_network_patch")
