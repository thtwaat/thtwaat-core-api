from pathlib import Path
ROOT = Path(r"E:\THTWAAT\thtwaat-core-api\apps\android-starter")

def w(rel: str, content: str) -> None:
    path = ROOT / rel.replace("/", "\\")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.lstrip("\n"), encoding="utf-8", newline="\n")
    print("wrote", rel)

w("app/src/main/java/com/thtwaat/starter/data/remote/api/AuthApi.kt", r'''
package com.thtwaat.starter.data.remote.api

import com.thtwaat.starter.data.remote.dto.ForgotPasswordRequestDto
import com.thtwaat.starter.data.remote.dto.LoginRequestDto
import com.thtwaat.starter.data.remote.dto.LogoutRequestDto
import com.thtwaat.starter.data.remote.dto.RefreshRequestDto
import com.thtwaat.starter.data.remote.dto.ResetPasswordRequestDto
import com.thtwaat.starter.data.remote.dto.SignupRequestDto
import com.thtwaat.starter.data.remote.dto.TokenResponseDto
import com.thtwaat.starter.data.remote.dto.UserProfileDto
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST

interface AuthApi {
    @POST("/api/v1/auth/login")
    suspend fun login(@Body body: LoginRequestDto): TokenResponseDto

    @POST("/api/v1/auth/refresh")
    suspend fun refresh(@Body body: RefreshRequestDto): TokenResponseDto

    @POST("/api/v1/auth/logout")
    suspend fun logout(@Body body: LogoutRequestDto)

    @GET("/api/v1/auth/me")
    suspend fun me(): UserProfileDto

    @POST("/api/v1/auth/forgot-password")
    suspend fun forgotPassword(@Body body: ForgotPasswordRequestDto)

    @POST("/api/v1/auth/reset-password")
    suspend fun resetPassword(@Body body: ResetPasswordRequestDto)

    @POST("/api/v1/users/")
    suspend fun signup(@Body body: SignupRequestDto): UserProfileDto
}
''')

w("app/src/main/java/com/thtwaat/starter/data/remote/api/ChatApi.kt", r'''
package com.thtwaat.starter.data.remote.api

import com.thtwaat.starter.data.remote.dto.ChatRequestDto
import com.thtwaat.starter.data.remote.dto.ChatResponseDto
import com.thtwaat.starter.data.remote.dto.ConversationDto
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

interface ChatApi {
    @POST("/public/v1/chat")
    suspend fun chat(@Body body: ChatRequestDto): ChatResponseDto

    @GET("/v2/conversations")
    suspend fun conversations(@Query("limit") limit: Int? = null): List<ConversationDto>

    @GET("/v2/conversations/{id}")
    suspend fun conversation(@Path("id") id: String): ConversationDto
}
''')

w("app/src/main/java/com/thtwaat/starter/data/remote/api/KnowledgeApi.kt", r'''
package com.thtwaat.starter.data.remote.api

import com.thtwaat.starter.data.remote.dto.KnowledgeBaseCreateRequestDto
import com.thtwaat.starter.data.remote.dto.KnowledgeBaseDto
import com.thtwaat.starter.data.remote.dto.KnowledgeDocumentDto
import com.thtwaat.starter.data.remote.dto.KnowledgeSearchRequestDto
import com.thtwaat.starter.data.remote.dto.SearchResultItemDto
import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part
import retrofit2.http.Path
import retrofit2.http.Query

interface KnowledgeApi {
    @GET("/v2/knowledge/bases")
    suspend fun listBases(): List<KnowledgeBaseDto>

    @POST("/v2/knowledge/bases")
    suspend fun createBase(@Body body: KnowledgeBaseCreateRequestDto): KnowledgeBaseDto

    @POST("/v2/knowledge/search")
    suspend fun search(@Body body: KnowledgeSearchRequestDto): List<SearchResultItemDto>

    @Multipart
    @POST("/v2/knowledge/upload")
    suspend fun upload(
        @Part file: MultipartBody.Part,
        @Query("knowledge_base_id") kbId: String? = null,
    ): KnowledgeDocumentDto

    @DELETE("/v2/knowledge/documents/{id}")
    suspend fun deleteDocument(@Path("id") id: String)
}
''')

w("app/src/main/java/com/thtwaat/starter/data/remote/api/AgentsApi.kt", r'''
package com.thtwaat.starter.data.remote.api

import com.thtwaat.starter.data.remote.dto.AgentApiKeyDto
import com.thtwaat.starter.data.remote.dto.AgentCreateRequestDto
import com.thtwaat.starter.data.remote.dto.AgentDto
import com.thtwaat.starter.data.remote.dto.CreateApiKeyRequestDto
import com.thtwaat.starter.data.remote.dto.PublishResultDto
import kotlinx.serialization.json.JsonObject
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

interface AgentsApi {
    @GET("/v2/agents")
    suspend fun list(@Query("is_template") isTemplate: Boolean? = null): List<AgentDto>

    @GET("/v2/agents/{id}")
    suspend fun get(@Path("id") id: String): AgentDto

    @POST("/v2/agents")
    suspend fun create(@Body body: AgentCreateRequestDto): AgentDto

    @POST("/api/v1/agents/{id}/publish")
    suspend fun publish(@Path("id") id: String): PublishResultDto

    @POST("/api/v1/agents/{id}/unpublish")
    suspend fun unpublish(@Path("id") id: String)

    @GET("/api/v1/agents/{id}/embed")
    suspend fun embed(@Path("id") id: String): JsonObject

    @GET("/api/v1/agents/{id}/widget")
    suspend fun widget(@Path("id") id: String): JsonObject

    @PATCH("/api/v1/agents/{id}/widget")
    suspend fun updateWidget(@Path("id") id: String, @Body body: JsonObject): JsonObject

    @GET("/api/v1/agents/{id}/api-keys")
    suspend fun listApiKeys(@Path("id") id: String): List<AgentApiKeyDto>

    @POST("/api/v1/agents/{id}/api-keys")
    suspend fun createApiKey(@Path("id") id: String, @Body body: CreateApiKeyRequestDto): AgentApiKeyDto
}
''')

w("app/src/main/java/com/thtwaat/starter/data/remote/api/MarketplaceApi.kt", r'''
package com.thtwaat.starter.data.remote.api

import com.thtwaat.starter.data.remote.dto.ConnectRequestDto
import com.thtwaat.starter.data.remote.dto.InstallRequestDto
import com.thtwaat.starter.data.remote.dto.InstallationDto
import com.thtwaat.starter.data.remote.dto.TemplateItemDto
import com.thtwaat.starter.data.remote.dto.UpdateNotificationDto
import kotlinx.serialization.json.JsonObject
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

interface MarketplaceApi {
    @GET("/api/v1/marketplace/dashboard")
    suspend fun dashboard(): JsonObject

    @GET("/api/v1/marketplace/templates")
    suspend fun templates(
        @Query("q") q: String? = null,
        @Query("category") category: String? = null,
        @Query("featured") featured: Boolean? = null,
        @Query("newest") newest: Boolean? = null,
        @Query("limit") limit: Int = 50,
    ): List<TemplateItemDto>

    @GET("/api/v1/marketplace/templates/{idOrSlug}")
    suspend fun template(@Path("idOrSlug") idOrSlug: String): TemplateItemDto

    @POST("/api/v1/marketplace/templates/{idOrSlug}/install")
    suspend fun install(@Path("idOrSlug") idOrSlug: String, @Body body: InstallRequestDto): InstallationDto

    @GET("/api/v1/marketplace/installed")
    suspend fun installed(): List<InstallationDto>

    @GET("/api/v1/marketplace/updates")
    suspend fun updates(): List<UpdateNotificationDto>

    @POST("/api/v1/marketplace/installations/{id}/connect")
    suspend fun connect(@Path("id") id: String, @Body body: ConnectRequestDto): InstallationDto

    @POST("/api/v1/marketplace/installations/{id}/publish")
    suspend fun publish(@Path("id") id: String): InstallationDto

    @POST("/api/v1/marketplace/installations/{id}/update")
    suspend fun update(@Path("id") id: String, @Query("version") version: String? = null): InstallationDto

    @POST("/api/v1/marketplace/installations/{id}/rollback")
    suspend fun rollback(@Path("id") id: String): InstallationDto

    @DELETE("/api/v1/marketplace/installations/{id}")
    suspend fun uninstall(@Path("id") id: String)
}
''')

w("app/src/main/java/com/thtwaat/starter/data/remote/api/PlatformApis.kt", r'''
package com.thtwaat.starter.data.remote.api

import com.thtwaat.starter.data.remote.dto.DomainCreateRequestDto
import com.thtwaat.starter.data.remote.dto.DomainRecordDto
import com.thtwaat.starter.data.remote.dto.InvoiceDto
import com.thtwaat.starter.data.remote.dto.PlanDto
import com.thtwaat.starter.data.remote.dto.ProductAnalysisDto
import com.thtwaat.starter.data.remote.dto.ProductAnalyzeRequestDto
import com.thtwaat.starter.data.remote.dto.ProductGenerateRequestDto
import com.thtwaat.starter.data.remote.dto.ProductGenerationDto
import com.thtwaat.starter.data.remote.dto.ProductPublishRequestDto
import com.thtwaat.starter.data.remote.dto.SubscriptionDto
import com.thtwaat.starter.data.remote.dto.UsageSnapshotDto
import kotlinx.serialization.json.JsonObject
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

interface ProductGeneratorApi {
    @POST("/api/v1/product-generator/analyze")
    suspend fun analyze(@Body body: ProductAnalyzeRequestDto): ProductAnalysisDto

    @POST("/api/v1/product-generator/generate")
    suspend fun generate(@Body body: ProductGenerateRequestDto): ProductGenerationDto

    @GET("/api/v1/product-generator/generations")
    suspend fun list(): List<ProductGenerationDto>

    @GET("/api/v1/product-generator/generations/{id}")
    suspend fun get(@Path("id") id: String): ProductGenerationDto

    @POST("/api/v1/product-generator/generations/{id}/publish")
    suspend fun publish(@Path("id") id: String, @Body body: ProductPublishRequestDto): ProductGenerationDto
}

interface DomainsApi {
    @GET("/api/v1/domains/dashboard")
    suspend fun dashboard(): JsonObject

    @GET("/api/v1/domains/")
    suspend fun list(): List<DomainRecordDto>

    @POST("/api/v1/domains/")
    suspend fun create(@Body body: DomainCreateRequestDto): DomainRecordDto

    @GET("/api/v1/domains/{id}")
    suspend fun get(@Path("id") id: String): DomainRecordDto

    @POST("/api/v1/domains/{id}/verify")
    suspend fun verify(@Path("id") id: String): DomainRecordDto

    @POST("/api/v1/domains/{id}/retry")
    suspend fun retry(@Path("id") id: String): DomainRecordDto

    @POST("/api/v1/domains/{id}/ssl/request")
    suspend fun requestSsl(@Path("id") id: String): DomainRecordDto
}

interface UsageApi {
    @GET("/api/v1/usage/current")
    suspend fun current(): UsageSnapshotDto

    @GET("/api/v1/usage/dashboard")
    suspend fun dashboard(): JsonObject

    @GET("/api/v1/usage/history")
    suspend fun history(): List<JsonObject>
}

interface BillingApi {
    @GET("/api/v1/payments/plans/")
    suspend fun plans(): List<PlanDto>

    @GET("/api/v1/payments/invoices/")
    suspend fun invoices(): List<InvoiceDto>

    @GET("/api/v1/payments/subscriptions/me")
    suspend fun subscription(): SubscriptionDto
}

interface AnalyticsApi {
    @GET("/api/v1/analytics/overview")
    suspend fun overview(): JsonObject
}
''')

print("apis done")
