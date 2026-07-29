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
