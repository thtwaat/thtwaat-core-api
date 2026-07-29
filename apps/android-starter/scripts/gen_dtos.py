# Generates remaining Android starter Kotlin sources
from pathlib import Path

ROOT = Path(r"E:\THTWAAT\thtwaat-core-api\apps\android-starter")

def w(rel: str, content: str) -> None:
    path = ROOT / rel.replace("/", "\\")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.lstrip("\n"), encoding="utf-8", newline="\n")
    print("wrote", rel)

# ===== DTOs =====
w("app/src/main/java/com/thtwaat/starter/data/remote/dto/AuthDtos.kt", r'''
package com.thtwaat.starter.data.remote.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class LoginRequestDto(val email: String, val password: String)

@Serializable
data class RefreshRequestDto(@SerialName("refresh_token") val refreshToken: String)

@Serializable
data class LogoutRequestDto(@SerialName("refresh_token") val refreshToken: String)

@Serializable
data class ForgotPasswordRequestDto(val email: String)

@Serializable
data class ResetPasswordRequestDto(
    val email: String,
    val code: String,
    @SerialName("new_password") val newPassword: String,
)

@Serializable
data class SignupRequestDto(
    val email: String,
    val password: String,
    @SerialName("first_name") val firstName: String,
    @SerialName("last_name") val lastName: String,
    @SerialName("company_id") val companyId: String? = null,
)

@Serializable
data class TokenResponseDto(
    @SerialName("access_token") val accessToken: String,
    @SerialName("refresh_token") val refreshToken: String,
    @SerialName("token_type") val tokenType: String = "bearer",
    @SerialName("expires_in") val expiresIn: Int? = null,
)

@Serializable
data class UserProfileDto(
    val id: String,
    @SerialName("company_id") val companyId: String? = null,
    val email: String? = null,
    @SerialName("first_name") val firstName: String? = null,
    @SerialName("last_name") val lastName: String? = null,
    val role: String? = null,
)
''')

w("app/src/main/java/com/thtwaat/starter/data/remote/dto/ChatDtos.kt", r'''
package com.thtwaat.starter.data.remote.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

@Serializable
data class ChatRequestDto(
    val message: String,
    @SerialName("session_id") val sessionId: String? = null,
    @SerialName("api_key") val apiKey: String? = null,
    val metadata: JsonObject? = null,
)

@Serializable
data class ChatUsageDto(
    @SerialName("prompt_tokens") val promptTokens: Int? = null,
    @SerialName("completion_tokens") val completionTokens: Int? = null,
    @SerialName("total_tokens") val totalTokens: Int? = null,
)

@Serializable
data class ChatResponseDto(
    val reply: String? = null,
    val response: String? = null,
    @SerialName("conversation_id") val conversationId: String? = null,
    @SerialName("message_id") val messageId: String? = null,
    @SerialName("suggested_prompts") val suggestedPrompts: List<String> = emptyList(),
    val usage: ChatUsageDto? = null,
)

@Serializable
data class ConversationMessageDto(
    val id: String? = null,
    val role: String = "assistant",
    val content: String = "",
    @SerialName("created_at") val createdAt: String? = null,
)

@Serializable
data class ConversationDto(
    val id: String,
    val messages: List<ConversationMessageDto> = emptyList(),
    @SerialName("created_at") val createdAt: String? = null,
    @SerialName("updated_at") val updatedAt: String? = null,
)
''')

w("app/src/main/java/com/thtwaat/starter/data/remote/dto/AgentDtos.kt", r'''
package com.thtwaat.starter.data.remote.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

@Serializable
data class AgentCreateRequestDto(
    val name: String,
    @SerialName("system_prompt_template") val systemPromptTemplate: String,
    val description: String? = null,
    val temperature: Double = 0.7,
    @SerialName("is_template") val isTemplate: Boolean = false,
    @SerialName("web_config") val webConfig: JsonObject? = null,
)

@Serializable
data class AgentDto(
    val id: String,
    val name: String,
    @SerialName("company_id") val companyId: String? = null,
    val description: String? = null,
    @SerialName("system_prompt_template") val systemPromptTemplate: String? = null,
    val temperature: Double? = null,
    val status: String? = null,
    val version: Int? = null,
    @SerialName("is_template") val isTemplate: Boolean = false,
    @SerialName("widget_id") val widgetId: String? = null,
    @SerialName("published_at") val publishedAt: String? = null,
    @SerialName("created_at") val createdAt: String? = null,
    @SerialName("updated_at") val updatedAt: String? = null,
)

@Serializable
data class PublishResultDto(
    val status: String = "",
    @SerialName("agent_id") val agentId: String = "",
    @SerialName("api_key") val apiKey: String? = null,
    @SerialName("widget_id") val widgetId: String? = null,
    @SerialName("public_chat_url") val publicChatUrl: String? = null,
    @SerialName("embed_script") val embedScript: String? = null,
    @SerialName("iframe_url") val iframeUrl: String? = null,
    @SerialName("published_at") val publishedAt: String? = null,
)

@Serializable
data class AgentApiKeyDto(
    val id: String? = null,
    val name: String? = null,
    @SerialName("key_prefix") val keyPrefix: String? = null,
    @SerialName("api_key_prefix") val apiKeyPrefix: String? = null,
    @SerialName("api_key") val apiKey: String? = null,
    val key: String? = null,
    @SerialName("plain_key") val plainKey: String? = null,
    @SerialName("expires_at") val expiresAt: String? = null,
    val message: String? = null,
)

@Serializable
data class CreateApiKeyRequestDto(val name: String = "Default")
''')

w("app/src/main/java/com/thtwaat/starter/data/remote/dto/KnowledgeDtos.kt", r'''
package com.thtwaat.starter.data.remote.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

@Serializable
data class KnowledgeBaseCreateRequestDto(
    val name: String,
    val description: String? = null,
)

@Serializable
data class KnowledgeBaseDto(
    val id: String,
    val name: String,
    @SerialName("company_id") val companyId: String? = null,
    val description: String? = null,
    @SerialName("created_at") val createdAt: String? = null,
)

@Serializable
data class KnowledgeSearchRequestDto(
    val query: String,
    @SerialName("kb_id") val kbId: String? = null,
    @SerialName("top_k") val topK: Int = 5,
)

@Serializable
data class SearchResultItemDto(
    @SerialName("chunk_id") val chunkId: String? = null,
    @SerialName("document_id") val documentId: String? = null,
    val text: String? = null,
    val content: String? = null,
    val score: Double? = null,
    val metadata: JsonObject? = null,
)

@Serializable
data class KnowledgeDocumentDto(
    val id: String,
    @SerialName("knowledge_base_id") val knowledgeBaseId: String? = null,
    val name: String? = null,
    @SerialName("source_type") val sourceType: String? = null,
    val status: String? = null,
    @SerialName("file_size_bytes") val fileSizeBytes: Long? = null,
)
''')

w("app/src/main/java/com/thtwaat/starter/data/remote/dto/MarketplaceDtos.kt", r'''
package com.thtwaat.starter.data.remote.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

@Serializable
data class TemplateItemDto(
    val id: String,
    val slug: String,
    val name: String,
    val category: String = "",
    val description: String = "",
    val version: String = "",
    val tags: List<String> = emptyList(),
    val author: String? = null,
    val status: String? = null,
    @SerialName("is_public") val isPublic: Boolean = true,
    @SerialName("is_featured") val isFeatured: Boolean = false,
    val installed: Boolean = false,
    @SerialName("update_available") val updateAvailable: Boolean = false,
    @SerialName("install_count") val installCount: Int = 0,
)

@Serializable
data class InstallationDto(
    val id: String,
    @SerialName("template_id") val templateId: String,
    @SerialName("template_slug") val templateSlug: String? = null,
    @SerialName("template_name") val templateName: String? = null,
    @SerialName("installed_version") val installedVersion: String = "",
    @SerialName("previous_version") val previousVersion: String? = null,
    val status: String = "",
    @SerialName("agent_id") val agentId: String? = null,
    @SerialName("api_key") val apiKey: String? = null,
    @SerialName("domain_id") val domainId: String? = null,
    @SerialName("update_available") val updateAvailable: Boolean = false,
    @SerialName("latest_available_version") val latestAvailableVersion: String? = null,
    val config: JsonObject? = null,
)

@Serializable
data class InstallRequestDto(
    @SerialName("create_api_key") val createApiKey: Boolean = true,
    @SerialName("agent_id") val agentId: String? = null,
    @SerialName("config_overrides") val configOverrides: JsonObject? = null,
)

@Serializable
data class ConnectRequestDto(
    @SerialName("agent_id") val agentId: String? = null,
    @SerialName("domain_id") val domainId: String? = null,
    @SerialName("create_api_key") val createApiKey: Boolean = true,
)

@Serializable
data class UpdateNotificationDto(
    @SerialName("installation_id") val installationId: String,
    @SerialName("template_id") val templateId: String,
    @SerialName("template_slug") val templateSlug: String = "",
    @SerialName("template_name") val templateName: String = "",
    @SerialName("installed_version") val installedVersion: String = "",
    @SerialName("latest_version") val latestVersion: String = "",
    val changelog: String? = null,
)
''')

w("app/src/main/java/com/thtwaat/starter/data/remote/dto/ProductDomainBillingDtos.kt", r'''
package com.thtwaat.starter.data.remote.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

@Serializable
data class ProductAnalyzeRequestDto(val prompt: String)

@Serializable
data class ProductAnalysisDto(
    val industry: String = "",
    @SerialName("product_type") val productType: String = "",
    val category: String = "",
    @SerialName("required_features") val requiredFeatures: List<String> = emptyList(),
    @SerialName("brand_tone") val brandTone: String = "",
    val language: String = "",
    @SerialName("suggested_name") val suggestedName: String = "",
    val confidence: Double = 0.0,
    @SerialName("keywords_matched") val keywordsMatched: List<String> = emptyList(),
    @SerialName("recommended_template_slug") val recommendedTemplateSlug: String? = null,
)

@Serializable
data class ProductGenerateRequestDto(
    val prompt: String,
    @SerialName("template_slug") val templateSlug: String? = null,
    @SerialName("config_overrides") val configOverrides: JsonObject? = null,
    @SerialName("create_domain_hostname") val createDomainHostname: String? = null,
    @SerialName("auto_publish") val autoPublish: Boolean = false,
)

@Serializable
data class ProductGenerationDto(
    val id: String,
    @SerialName("company_id") val companyId: String = "",
    val prompt: String = "",
    val status: String = "",
    val analysis: JsonObject? = null,
    @SerialName("template_slug") val templateSlug: String? = null,
    @SerialName("installation_id") val installationId: String? = null,
    @SerialName("agent_id") val agentId: String? = null,
    @SerialName("preview_url") val previewUrl: String? = null,
    @SerialName("widget_snippet") val widgetSnippet: String? = null,
    @SerialName("publish_status") val publishStatus: String? = null,
    @SerialName("failure_reason") val failureReason: String? = null,
)

@Serializable
data class ProductPublishRequestDto(val hostname: String? = null)

@Serializable
data class DomainCreateRequestDto(
    val hostname: String,
    @SerialName("verification_method") val verificationMethod: String = "TXT",
    @SerialName("agent_id") val agentId: String? = null,
    @SerialName("widget_id") val widgetId: String? = null,
    @SerialName("is_primary") val isPrimary: Boolean = false,
)

@Serializable
data class DomainRecordDto(
    val id: String,
    val hostname: String,
    val status: String? = null,
    @SerialName("ssl_status") val sslStatus: String? = null,
    @SerialName("verification_token") val verificationToken: String? = null,
    @SerialName("agent_id") val agentId: String? = null,
    @SerialName("widget_id") val widgetId: String? = null,
    @SerialName("created_at") val createdAt: String? = null,
)

@Serializable
data class UsageSnapshotDto(
    @SerialName("ai_messages") val aiMessages: Int? = null,
    @SerialName("total_tokens") val totalTokens: Int? = null,
    @SerialName("storage_bytes") val storageBytes: Long? = null,
    @SerialName("templates_published") val templatesPublished: Int? = null,
    @SerialName("max_templates") val maxTemplates: Int? = null,
    @SerialName("max_agents") val maxAgents: Int? = null,
)

@Serializable
data class PlanDto(
    val id: String? = null,
    val name: String? = null,
    val code: String? = null,
    val price: Double? = null,
    val currency: String? = null,
    @SerialName("max_agents") val maxAgents: Int? = null,
)

@Serializable
data class InvoiceDto(
    val id: String? = null,
    @SerialName("invoice_number") val invoiceNumber: String? = null,
    val status: String? = null,
    val amount: Double? = null,
    val currency: String? = null,
)

@Serializable
data class SubscriptionDto(
    val id: String? = null,
    val status: String? = null,
    val provider: String? = null,
    @SerialName("plan_id") val planId: String? = null,
)
''')

print("dto done")
