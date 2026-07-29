package com.thtwaat.starter.data.repository

import com.thtwaat.starter.core.datastore.SessionStore
import com.thtwaat.starter.core.network.SseClient
import com.thtwaat.starter.core.network.safeApiCall
import com.thtwaat.starter.core.util.Result
import com.thtwaat.starter.data.local.dao.ConversationDao
import com.thtwaat.starter.data.local.entity.ConversationEntity
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
    private val conversationDao: ConversationDao,
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
        if (result is Result.Success) {
            cachedConversations = result.data
            conversationDao.upsertAll(
                result.data.map { c ->
                    ConversationEntity(
                        id = c.id,
                        title = c.messages.lastOrNull()?.content?.take(80) ?: "Conversation",
                        updatedAt = c.updatedAt,
                    )
                },
            )
        }
        return if (result is Result.Error && cachedConversations.isNotEmpty()) {
            Result.Success(cachedConversations)
        } else result
    }

    suspend fun conversation(id: String): Result<ConversationDto> =
        safeApiCall { api.conversation(id) }

    fun cachedHistory(): List<ConversationDto> = cachedConversations
}
