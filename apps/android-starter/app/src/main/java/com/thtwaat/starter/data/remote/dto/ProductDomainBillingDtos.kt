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
