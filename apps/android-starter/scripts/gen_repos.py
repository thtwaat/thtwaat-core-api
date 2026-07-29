from pathlib import Path
ROOT = Path(r"E:\THTWAAT\thtwaat-core-api\apps\android-starter")

def w(rel: str, content: str) -> None:
    path = ROOT / rel.replace("/", "\\")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.lstrip("\n"), encoding="utf-8", newline="\n")
    print("wrote", rel)

w("app/src/main/java/com/thtwaat/starter/data/repository/AuthRepository.kt", r'''
package com.thtwaat.starter.data.repository

import com.thtwaat.starter.core.datastore.SessionStore
import com.thtwaat.starter.core.network.safeApiCall
import com.thtwaat.starter.core.util.Result
import com.thtwaat.starter.data.remote.api.AuthApi
import com.thtwaat.starter.data.remote.dto.ForgotPasswordRequestDto
import com.thtwaat.starter.data.remote.dto.LoginRequestDto
import com.thtwaat.starter.data.remote.dto.LogoutRequestDto
import com.thtwaat.starter.data.remote.dto.ResetPasswordRequestDto
import com.thtwaat.starter.data.remote.dto.SignupRequestDto
import com.thtwaat.starter.data.remote.dto.TokenResponseDto
import com.thtwaat.starter.data.remote.dto.UserProfileDto
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AuthRepository @Inject constructor(
    private val api: AuthApi,
    private val sessionStore: SessionStore,
) {
    val isLoggedIn: Flow<Boolean> = sessionStore.accessToken.map { !it.isNullOrBlank() }

    suspend fun login(email: String, password: String): Result<TokenResponseDto> {
        val result = safeApiCall { api.login(LoginRequestDto(email, password)) }
        if (result is Result.Success) {
            sessionStore.saveTokens(result.data.accessToken, result.data.refreshToken)
        }
        return result
    }

    suspend fun signup(
        email: String,
        password: String,
        firstName: String,
        lastName: String,
        companyId: String? = null,
    ): Result<UserProfileDto> = safeApiCall {
        api.signup(SignupRequestDto(email, password, firstName, lastName, companyId))
    }

    suspend fun forgotPassword(email: String): Result<Unit> =
        safeApiCall { api.forgotPassword(ForgotPasswordRequestDto(email)) }

    suspend fun resetPassword(email: String, code: String, newPassword: String): Result<Unit> =
        safeApiCall { api.resetPassword(ResetPasswordRequestDto(email, code, newPassword)) }

    suspend fun me(): Result<UserProfileDto> = safeApiCall { api.me() }

    suspend fun logout(): Result<Unit> {
        val refresh = sessionStore.getRefreshToken()
        val result = if (refresh.isNullOrBlank()) {
            Result.Success(Unit)
        } else {
            safeApiCall { api.logout(LogoutRequestDto(refresh)) }
        }
        sessionStore.clearSession()
        return result
    }
}
''')

w("app/src/main/java/com/thtwaat/starter/data/repository/ChatRepository.kt", r'''
package com.thtwaat.starter.data.repository

import com.thtwaat.starter.core.datastore.SessionStore
import com.thtwaat.starter.core.network.SseClient
import com.thtwaat.starter.core.network.safeApiCall
import com.thtwaat.starter.core.util.Result
import com.thtwaat.starter.data.remote.api.ChatApi
import com.thtwaat.starter.data.remote.dto.ChatRequestDto
import com.thtwaat.starter.data.remote.dto.ChatResponseDto
import com.thtwaat.starter.data.remote.dto.ConversationDto
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import javax.inject.Inject
import javax.inject.Singleton

data class StreamToken(val event: String, val text: String?)

@Singleton
class ChatRepository @Inject constructor(
    private val api: ChatApi,
    private val sseClient: SseClient,
    private val sessionStore: SessionStore,
    private val json: Json,
) {
    private var cachedConversations: List<ConversationDto> = emptyList()

    suspend fun chat(message: String, sessionId: String? = null): Result<ChatResponseDto> {
        val apiKey = sessionStore.getApiKey()
        return safeApiCall {
            api.chat(ChatRequestDto(message = message, sessionId = sessionId, apiKey = apiKey))
        }
    }

    fun stream(message: String, sessionId: String? = null): Flow<StreamToken> {
        val body = ChatRequestDto(message = message, sessionId = sessionId)
        val payload = json.encodeToString(body)
        return sseClient.streamPost("/public/v1/chat/stream", payload).map {
            StreamToken(event = it.event, text = sseClient.extractText(it))
        }
    }

    suspend fun history(limit: Int? = 20): Result<List<ConversationDto>> {
        val result = safeApiCall { api.conversations(limit) }
        if (result is Result.Success) cachedConversations = result.data
        return if (result is Result.Error && cachedConversations.isNotEmpty()) {
            Result.Success(cachedConversations)
        } else result
    }

    suspend fun conversation(id: String): Result<ConversationDto> =
        safeApiCall { api.conversation(id) }

    fun cachedHistory(): List<ConversationDto> = cachedConversations
}
''')

w("app/src/main/java/com/thtwaat/starter/data/repository/FeatureRepositories.kt", r'''
package com.thtwaat.starter.data.repository

import com.thtwaat.starter.core.network.safeApiCall
import com.thtwaat.starter.core.util.Result
import com.thtwaat.starter.data.remote.api.AgentsApi
import com.thtwaat.starter.data.remote.api.AnalyticsApi
import com.thtwaat.starter.data.remote.api.BillingApi
import com.thtwaat.starter.data.remote.api.DomainsApi
import com.thtwaat.starter.data.remote.api.KnowledgeApi
import com.thtwaat.starter.data.remote.api.MarketplaceApi
import com.thtwaat.starter.data.remote.api.ProductGeneratorApi
import com.thtwaat.starter.data.remote.api.UsageApi
import com.thtwaat.starter.data.remote.dto.AgentCreateRequestDto
import com.thtwaat.starter.data.remote.dto.AgentDto
import com.thtwaat.starter.data.remote.dto.ConnectRequestDto
import com.thtwaat.starter.data.remote.dto.CreateApiKeyRequestDto
import com.thtwaat.starter.data.remote.dto.DomainCreateRequestDto
import com.thtwaat.starter.data.remote.dto.InstallRequestDto
import com.thtwaat.starter.data.remote.dto.KnowledgeBaseCreateRequestDto
import com.thtwaat.starter.data.remote.dto.KnowledgeSearchRequestDto
import com.thtwaat.starter.data.remote.dto.ProductAnalyzeRequestDto
import com.thtwaat.starter.data.remote.dto.ProductGenerateRequestDto
import com.thtwaat.starter.data.remote.dto.ProductPublishRequestDto
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class KnowledgeRepository @Inject constructor(private val api: KnowledgeApi) {
    suspend fun listBases() = safeApiCall { api.listBases() }
    suspend fun createBase(name: String, description: String?) =
        safeApiCall { api.createBase(KnowledgeBaseCreateRequestDto(name, description)) }
    suspend fun search(query: String, kbId: String? = null, topK: Int = 5) =
        safeApiCall { api.search(KnowledgeSearchRequestDto(query, kbId, topK)) }
    suspend fun upload(bytes: ByteArray, filename: String, kbId: String?) = safeApiCall {
        val body = bytes.toRequestBody("application/octet-stream".toMediaTypeOrNull())
        val part = MultipartBody.Part.createFormData("file", filename, body)
        api.upload(part, kbId)
    }
    suspend fun deleteDocument(id: String) = safeApiCall { api.deleteDocument(id) }
}

@Singleton
class AgentsRepository @Inject constructor(private val api: AgentsApi) {
    private var cache: List<AgentDto> = emptyList()
    suspend fun list(): Result<List<AgentDto>> {
        val result = safeApiCall { api.list() }
        if (result is Result.Success) cache = result.data
        return if (result is Result.Error && cache.isNotEmpty()) Result.Success(cache) else result
    }
    fun cached() = cache
    suspend fun get(id: String) = safeApiCall { api.get(id) }
    suspend fun create(name: String, prompt: String, description: String?) =
        safeApiCall { api.create(AgentCreateRequestDto(name, prompt, description)) }
    suspend fun publish(id: String) = safeApiCall { api.publish(id) }
    suspend fun unpublish(id: String) = safeApiCall { api.unpublish(id) }
    suspend fun embed(id: String) = safeApiCall { api.embed(id) }
    suspend fun widget(id: String) = safeApiCall { api.widget(id) }
    suspend fun listKeys(id: String) = safeApiCall { api.listApiKeys(id) }
    suspend fun createKey(id: String, name: String = "Default") =
        safeApiCall { api.createApiKey(id, CreateApiKeyRequestDto(name)) }
}

@Singleton
class MarketplaceRepository @Inject constructor(private val api: MarketplaceApi) {
    suspend fun templates(q: String? = null, category: String? = null) =
        safeApiCall { api.templates(q = q, category = category) }
    suspend fun template(idOrSlug: String) = safeApiCall { api.template(idOrSlug) }
    suspend fun install(idOrSlug: String) = safeApiCall { api.install(idOrSlug, InstallRequestDto()) }
    suspend fun installed() = safeApiCall { api.installed() }
    suspend fun updates() = safeApiCall { api.updates() }
    suspend fun connect(id: String, agentId: String? = null) =
        safeApiCall { api.connect(id, ConnectRequestDto(agentId = agentId)) }
    suspend fun publish(id: String) = safeApiCall { api.publish(id) }
    suspend fun update(id: String) = safeApiCall { api.update(id) }
    suspend fun rollback(id: String) = safeApiCall { api.rollback(id) }
    suspend fun uninstall(id: String) = safeApiCall { api.uninstall(id) }
    suspend fun dashboard() = safeApiCall { api.dashboard() }
}

@Singleton
class ProductGeneratorRepository @Inject constructor(private val api: ProductGeneratorApi) {
    suspend fun analyze(prompt: String) = safeApiCall { api.analyze(ProductAnalyzeRequestDto(prompt)) }
    suspend fun generate(prompt: String, templateSlug: String? = null, autoPublish: Boolean = false) =
        safeApiCall { api.generate(ProductGenerateRequestDto(prompt, templateSlug, autoPublish = autoPublish)) }
    suspend fun list() = safeApiCall { api.list() }
    suspend fun get(id: String) = safeApiCall { api.get(id) }
    suspend fun publish(id: String, hostname: String? = null) =
        safeApiCall { api.publish(id, ProductPublishRequestDto(hostname)) }
}

@Singleton
class DomainsRepository @Inject constructor(private val api: DomainsApi) {
    suspend fun list() = safeApiCall { api.list() }
    suspend fun create(hostname: String) = safeApiCall { api.create(DomainCreateRequestDto(hostname)) }
    suspend fun verify(id: String) = safeApiCall { api.verify(id) }
    suspend fun retry(id: String) = safeApiCall { api.retry(id) }
    suspend fun requestSsl(id: String) = safeApiCall { api.requestSsl(id) }
    suspend fun dashboard() = safeApiCall { api.dashboard() }
}

@Singleton
class UsageRepository @Inject constructor(private val api: UsageApi) {
    suspend fun current() = safeApiCall { api.current() }
    suspend fun dashboard() = safeApiCall { api.dashboard() }
}

@Singleton
class BillingRepository @Inject constructor(private val api: BillingApi) {
    suspend fun plans() = safeApiCall { api.plans() }
    suspend fun invoices() = safeApiCall { api.invoices() }
    suspend fun subscription() = safeApiCall { api.subscription() }
}

@Singleton
class AnalyticsRepository @Inject constructor(private val api: AnalyticsApi) {
    suspend fun overview() = safeApiCall { api.overview() }
}
''')

print("repos done")
