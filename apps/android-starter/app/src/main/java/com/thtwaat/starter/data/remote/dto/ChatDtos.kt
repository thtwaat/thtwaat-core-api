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
