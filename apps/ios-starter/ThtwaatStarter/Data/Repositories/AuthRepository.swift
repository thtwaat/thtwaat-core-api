import Foundation

actor AuthRepository {
    private let client: APIClient
    private let sessionStore: any SessionStore

    init(client: APIClient, sessionStore: any SessionStore) {
        self.client = client
        self.sessionStore = sessionStore
    }

    func login(email: String, password: String) async -> APIResult<TokenResponse> {
        let result: APIResult<TokenResponse> = await client.post(
            "/api/v1/auth/login",
            body: LoginRequest(email: email, password: password),
            auth: false
        )
        if case .success(let tokens) = result {
            await sessionStore.saveTokens(access: tokens.accessToken, refresh: tokens.refreshToken)
        }
        return result
    }

    func signup(email: String, password: String, first: String, last: String) async -> APIResult<UserProfile> {
        await client.post(
            "/api/v1/users/",
            body: SignupRequest(email: email, password: password, firstName: first, lastName: last, companyId: nil),
            auth: false
        )
    }

    func forgotPassword(email: String) async -> APIResult<APIClient.EmptyResponse> {
        await client.post("/api/v1/auth/forgot-password", body: ForgotPasswordRequest(email: email), auth: false)
    }

    func me() async -> APIResult<UserProfile> {
        await client.get("/api/v1/auth/me")
    }

    func logout() async -> APIResult<APIClient.EmptyResponse> {
        let refresh = await sessionStore.refreshToken() ?? ""
        let result: APIResult<APIClient.EmptyResponse> = await client.post(
            "/api/v1/auth/logout",
            body: LogoutRequest(refreshToken: refresh)
        )
        await sessionStore.clearSession()
        return result
    }

    @discardableResult
    func refreshIfPossible() async -> Bool {
        guard let refresh = await sessionStore.refreshToken(), !refresh.isEmpty else { return false }
        let result: APIResult<TokenResponse> = await client.post(
            "/api/v1/auth/refresh",
            body: RefreshRequest(refreshToken: refresh),
            auth: false
        )
        if case .success(let tokens) = result {
            await sessionStore.saveTokens(access: tokens.accessToken, refresh: tokens.refreshToken)
            return true
        }
        await sessionStore.clearSession()
        return false
    }
}
