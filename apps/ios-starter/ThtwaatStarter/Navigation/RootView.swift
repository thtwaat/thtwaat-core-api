import SwiftUI

struct RootView: View {
    @EnvironmentObject private var appState: AppState

    var body: some View {
        Group {
            if appState.isAuthenticated {
                MainTabView()
            } else {
                NavigationStack {
                    LoginViewFixed()
                }
            }
        }
        .animation(.easeInOut, value: appState.isAuthenticated)
    }
}

enum AppRoute: Hashable {
    case knowledge, product, domains, billing
}

struct MainTabView: View {
    @State private var path = NavigationPath()

    var body: some View {
        TabView {
            NavigationStack(path: $path) {
                HomeView(path: $path)
                    .navigationDestination(for: AppRoute.self) { route in
                        switch route {
                        case .knowledge: KnowledgeView()
                        case .product: ProductGeneratorView()
                        case .domains: DomainsView()
                        case .billing: BillingView()
                        }
                    }
            }
            .tabItem { Label("Home", systemImage: "house.fill") }

            NavigationStack { ChatView() }
                .tabItem { Label("Chat", systemImage: "bubble.left.and.bubble.right.fill") }

            NavigationStack { AgentsView() }
                .tabItem { Label("Agents", systemImage: "cpu") }

            NavigationStack { MarketplaceView() }
                .tabItem { Label("Market", systemImage: "storefront.fill") }

            NavigationStack { SettingsView() }
                .tabItem { Label("Settings", systemImage: "gearshape.fill") }
        }
        .tint(Color(red: 0.06, green: 0.46, blue: 0.43))
    }
}
