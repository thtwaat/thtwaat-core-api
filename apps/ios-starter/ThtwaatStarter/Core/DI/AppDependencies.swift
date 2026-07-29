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
